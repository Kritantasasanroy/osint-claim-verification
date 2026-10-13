import asyncio
import json
import time
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel

from fakes import Handler
from osint_harness.nvidia import EmbeddingPurpose, MalformedCompletion, NvidiaChat, NvidiaEmbedder, TokenUsage
from osint_harness.settings import Settings, TokenPrice
from osint_harness.transport import ResponseCache, ServiceRejected, ServiceUnavailable, Transport


class Answer(BaseModel):
    verdict: str
    confidence: float

    @staticmethod
    def reply(content: str) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )


def test_cache_replays_a_response_without_calling_the_service(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, text="hello")

    cache = ResponseCache(tmp_path / "c.sqlite3")
    transport = Transport(httpx.AsyncClient(transport=httpx.MockTransport(handler)), cache, 2)

    first = asyncio.run(transport.post("https://x.test/a", {"q": 1}, {}))
    second = asyncio.run(transport.post("https://x.test/a", {"q": 1}, {}))

    assert (first.text, first.cached) == ("hello", False)
    assert (second.text, second.cached) == ("hello", True)
    assert len(calls) == 1


def test_transient_failure_is_retried(make_transport: Callable[[Handler], Transport]) -> None:
    statuses = iter([429, 200])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(next(statuses), text="ok")

    reply = asyncio.run(make_transport(handler).get("https://x.test/b", {"a": "1"}, {}))

    assert reply.text == "ok"


def test_client_error_is_raised_not_retried(make_transport: Callable[[Handler], Transport]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="bad key")

    with pytest.raises(ServiceRejected, match="401"):
        asyncio.run(make_transport(handler).get("https://x.test/c", {}, {}))


def test_chat_parses_schema_and_usage(
    settings: Settings, make_transport: Callable[[Handler], Transport]
) -> None:
    sent: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return Answer.reply('```json\n{"verdict": "TRUE", "confidence": 0.9}\n```')

    completion = asyncio.run(NvidiaChat(make_transport(handler), settings).ask("sys", "user", Answer))

    assert completion.value == Answer(verdict="TRUE", confidence=0.9)
    assert completion.usage == TokenUsage(10, 5)
    assert sent[0]["model"] == "test/llm"


def test_chat_rejects_output_that_breaks_the_schema(
    settings: Settings, make_transport: Callable[[Handler], Transport]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return Answer.reply('{"verdict": "TRUE"}')

    with pytest.raises(MalformedCompletion):
        asyncio.run(NvidiaChat(make_transport(handler), settings).ask("sys", "user", Answer))


def test_a_reply_cut_off_while_thinking_is_retried_without_thinking(
    settings: Settings, make_transport: Callable[[Handler], Transport]
) -> None:
    sent: list[dict[str, dict[str, bool]]] = []
    replies = iter(
        [
            httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": None}, "finish_reason": "length"}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 8192},
                },
            ),
            Answer.reply('{"verdict": "FALSE", "confidence": 0.8}'),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return next(replies)

    completion = asyncio.run(NvidiaChat(make_transport(handler), settings).ask("sys", "user", Answer))

    assert completion.value.verdict == "FALSE"
    assert completion.usage == TokenUsage(20, 8197)
    assert sent[1]["chat_template_kwargs"]["enable_thinking"] is False


def test_token_cost_uses_per_million_prices() -> None:
    usage = TokenUsage(1_000_000, 500_000) + TokenUsage(0, 500_000)

    assert usage.total == 2_000_000
    assert usage.cost_usd(TokenPrice(input_per_mtok=1.0, output_per_mtok=2.0)) == 3.0


def test_a_reply_that_is_not_a_completion_is_evicted_and_reported(settings: Settings, tmp_path: Path) -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, json={"error": "upstream hiccup"})

    cache = ResponseCache(tmp_path / "c.sqlite3")
    chat = NvidiaChat(
        Transport(httpx.AsyncClient(transport=httpx.MockTransport(handler)), cache, 2, 0.0), settings
    )

    with pytest.raises(MalformedCompletion, match="not a completion"):
        asyncio.run(chat.ask("sys", "user", Answer))
    with pytest.raises(MalformedCompletion):
        asyncio.run(chat.ask("sys", "user", Answer))

    assert len(calls) == 2


def test_a_reply_that_is_not_embeddings_is_evicted_and_reported(settings: Settings, tmp_path: Path) -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, json={"detail": "model warming up"})

    cache = ResponseCache(tmp_path / "c.sqlite3")
    embedder = NvidiaEmbedder(
        Transport(httpx.AsyncClient(transport=httpx.MockTransport(handler)), cache, 2, 0.0), settings
    )

    for _ in range(2):
        with pytest.raises(MalformedCompletion, match="not embeddings"):
            asyncio.run(embedder.embed(["x"], EmbeddingPurpose.QUERY))

    assert len(calls) == 2


def test_no_wait_after_the_last_failed_attempt(make_transport: Callable[[Handler], Transport]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="busy")

    transport = Transport(
        httpx.AsyncClient(transport=httpx.MockTransport(handler)), ResponseCache.disabled(), 1, 0.01
    )
    started = time.perf_counter()

    with pytest.raises(ServiceUnavailable):
        asyncio.run(transport.get("https://x.test/d", {}, {}))

    assert time.perf_counter() - started < 0.01 * (2**Transport.MAX_ATTEMPTS - 1)


def test_the_model_is_shown_the_schema_it_will_be_decoded_into(
    settings: Settings, make_transport: Callable[[Handler], Transport]
) -> None:
    sent: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content)["messages"][0]["content"])
        return Answer.reply('{"verdict": "TRUE", "confidence": 0.9}')

    asyncio.run(NvidiaChat(make_transport(handler), settings).ask("You are a checker.", "user", Answer))

    assert sent[0].startswith("You are a checker.")
    assert '"confidence"' in sent[0] and "JSON Schema" in sent[0]


def test_a_rate_limit_is_waited_out_with_the_servers_retry_after(
    make_transport: Callable[[Handler], Transport],
) -> None:
    """A dev run lost 42 of 53 cases to HTTP 429 after 6 attempts; rate limits now get 10 and Retry-After."""
    statuses = iter([429] * 8 + [200])

    def handler(request: httpx.Request) -> httpx.Response:
        status = next(statuses)
        return httpx.Response(status, text="ok", headers={"retry-after": "5"} if status == 429 else {})

    transport = make_transport(handler)

    assert asyncio.run(transport.get("https://x.test/limited", {}, {})).text == "ok"
    assert transport._wait(0, 5.0) == 0.0 and Transport.MAX_ATTEMPTS == 10


def test_a_schema_failure_names_the_field_so_the_retry_can_fix_it(
    settings: Settings, make_transport: Callable[[Handler], Transport]
) -> None:
    """Found in the v2 dev run: crashes said only '1 validation error', and so did the retry prompt."""
    users: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        users.append(json.loads(request.content)["messages"][1]["content"])
        return Answer.reply('{"verdict": "TRUE", "confidence": "high"}')

    with pytest.raises(MalformedCompletion, match="confidence"):
        asyncio.run(NvidiaChat(make_transport(handler), settings).ask("sys", "user", Answer))
    assert "confidence" in users[1]


def test_a_model_without_thinking_controls_gets_a_larger_output_budget(
    settings: Settings, make_transport: Callable[[Handler], Transport]
) -> None:
    sent: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return Answer.reply('{"verdict": "TRUE", "confidence": 0.9}')

    chat = NvidiaChat(make_transport(handler), settings)
    asyncio.run(chat.ask("s", "u", Answer))
    asyncio.run(chat.for_model("other/judge").ask("s", "u", Answer))

    assert [body["max_tokens"] for body in sent] == [8192, 16384]
    assert "chat_template_kwargs" not in sent[1]


def test_a_throttled_host_halves_its_concurrency_and_makes_every_caller_wait() -> None:
    """Crash fix: workers used to retry into a throttled API independently; now they share one cooldown."""
    statuses = iter([429, 200, 200, 200])
    arrivals: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        arrivals.append(time.monotonic())
        return httpx.Response(next(statuses), text="ok", headers={"retry-after": "1"})

    transport = Transport(
        httpx.AsyncClient(transport=httpx.MockTransport(handler)), ResponseCache.disabled(), 4, backoff_s=0.2
    )

    async def scenario() -> None:
        await asyncio.gather(*(transport.get(f"https://api.test/x{i}", {}, {}) for i in range(3)))

    asyncio.run(scenario())
    limiter = transport.limiter("https://api.test/x")

    assert limiter.limit == 2 and limiter.ceiling == 4
    # the first call was throttled; nobody (including the two that had not started) retried before the pause
    assert max(arrivals[1:]) - arrivals[0] >= 0.2


def test_concurrency_recovers_after_clean_replies_and_each_host_has_its_own_limit() -> None:
    from osint_harness.transport import AdaptiveLimiter

    limiter = AdaptiveLimiter(4)
    limiter.throttled(0.0)
    limiter.throttled(0.0)
    assert limiter.limit == 1
    for _ in range(AdaptiveLimiter.RECOVER_AFTER * 3):
        limiter.succeeded()
    transport = Transport(httpx.AsyncClient(), ResponseCache.disabled(), 4)

    assert limiter.limit == 4
    assert transport.limiter("https://a.test/x") is not transport.limiter("https://b.test/x")
    assert transport.limiter("https://a.test/x") is transport.limiter("https://a.test/y")


def test_a_third_attempt_rescues_a_reply_that_failed_twice(
    settings: Settings, make_transport: Callable[[Handler], Transport]
) -> None:
    """Crash fix: 3 of 50 test-run investigations died on two bad replies in a row."""
    replies = iter(
        [
            '{"verdict": "TRUE"}',
            '{"verdict": "TRUE", "confidence": "high"}',
            '{"verdict": "TRUE", "confidence": 0.9}',
        ]
    )
    sent: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content)["messages"][1]["content"])
        return Answer.reply(next(replies))

    completion = asyncio.run(NvidiaChat(make_transport(handler), settings).ask("sys", "user", Answer))

    assert completion.value == Answer(verdict="TRUE", confidence=0.9)
    assert len(sent) == 3 and "confidence" in sent[2]
    assert completion.usage.prompt_tokens == 30 and len(completion.calls) == 3


def test_a_truncated_reply_is_retried_with_twice_the_output_budget(
    settings: Settings, make_transport: Callable[[Handler], Transport]
) -> None:
    budgets: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        budgets.append(json.loads(request.content)["max_tokens"])
        if len(budgets) == 1:
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": '{"verd'}, "finish_reason": "length"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                },
            )
        return Answer.reply('{"verdict": "TRUE", "confidence": 0.9}')

    asyncio.run(NvidiaChat(make_transport(handler), settings).ask("sys", "user", Answer))

    assert budgets == [NvidiaChat.MAX_TOKENS, 2 * NvidiaChat.MAX_TOKENS]


def test_three_bad_replies_in_a_row_still_fail_and_say_which_field(
    settings: Settings, make_transport: Callable[[Handler], Transport]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return Answer.reply('{"verdict": "TRUE", "confidence": "high"}')

    with pytest.raises(MalformedCompletion, match="confidence"):
        asyncio.run(NvidiaChat(make_transport(handler), settings).ask("sys", "user", Answer))
