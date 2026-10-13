import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import ClassVar

import httpx
import pytest

from fakes import Handler
from osint_harness.investigation.case_file import CaseFile
from osint_harness.investigation.evidence import Evidence, Stance, Strength
from osint_harness.investigation.inquiry import Inquiry, InquiryOutcome, ToolName
from osint_harness.investigation.source import PublisherOutcome, ResolvedBy, SourceTier
from osint_harness.investigation.subject import Subject
from osint_harness.investigation.verdict import SubjectKind, Verdict
from osint_harness.memory import LongTermMemory, MemoryKind, MemoryRecord
from osint_harness.nvidia import NvidiaEmbedder
from osint_harness.settings import Settings
from osint_harness.tools import Toolbox
from osint_harness.transport import ResponseCache, Transport

type ToolUse = Callable[[ToolName, str, "WebServices"], Inquiry]


class WebServices:
    """Tavily and Wikipedia as the tools see them: one healthy search, a broken extractor, a working wiki."""

    def __init__(self, empty_wiki_search_errors: bool = False) -> None:
        self.extracted: list[str] = []
        self.empty_wiki_search_errors = empty_wiki_search_errors

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/search":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "url": "https://www.reuters.com/a",
                            "title": "Wirecard collapse",
                            "content": "1.9bn gone",
                        },
                        {"url": "https://blog.example/b", "title": "Rumour", "content": ""},
                    ]
                },
            )
        if request.url.path == "/extract":
            self.extracted += json.loads(request.content)["urls"]
            if "sec.gov" in self.extracted[-1]:
                return httpx.Response(
                    200, json={"results": [{"url": self.extracted[-1], "raw_content": "Filing"}]}
                )
            return httpx.Response(500, text="down")
        if self.empty_wiki_search_errors:
            return httpx.Response(
                200, json={"error": {"code": "nosrsearch", "info": "The search parameter must be set."}}
            )
        if request.url.params.get("list") == "search":
            return httpx.Response(200, json={"query": {"search": [{"title": "Wirecard"}]}})
        return httpx.Response(
            200, json={"query": {"pages": [{"title": "Wirecard", "extract": "Wirecard AG was..."}]}}
        )


class EmbeddingService:
    VOCABULARY: ClassVar[list[str]] = ["wirecard", "theranos", "audit", "blood"]

    def handle(self, request: httpx.Request) -> httpx.Response:
        texts: list[str] = json.loads(request.content)["input"]
        vectors = [[float(word in text.lower()) + 0.01 for word in self.VOCABULARY] for text in texts]
        return httpx.Response(
            200,
            json={
                "data": [{"embedding": v} for v in vectors],
                "usage": {"prompt_tokens": 3, "completion_tokens": 0},
            },
        )


@pytest.fixture
def use_tool(settings: Settings, make_transport: Callable[[Handler], Transport]) -> ToolUse:
    def use(tool: ToolName, argument: str, services: WebServices) -> Inquiry:
        toolbox = Toolbox.standard(make_transport(services.handle), settings)
        return asyncio.run(toolbox.use(tool, argument, "Q1", 1))

    return use


@pytest.fixture
def memory(
    tmp_path: Path, settings: Settings, make_transport: Callable[[Handler], Transport]
) -> LongTermMemory:
    return LongTermMemory(
        tmp_path / "m.sqlite3", NvidiaEmbedder(make_transport(EmbeddingService().handle), settings)
    )


def test_search_returns_tiered_sources_and_drops_empty_snippets(use_tool: ToolUse) -> None:
    inquiry = use_tool(ToolName.NEWS_SEARCH, "Wirecard insolvency", WebServices())

    assert [(s.url, s.tier) for s in inquiry.sources] == [
        ("https://www.reuters.com/a", SourceTier.MAJOR_NEWS)
    ]
    assert (inquiry.outcome, inquiry.question_id, inquiry.step) == (InquiryOutcome.FOUND, "Q1", 1)


def test_encyclopedia_resolves_the_article_then_reads_it(use_tool: ToolUse) -> None:
    inquiry = use_tool(ToolName.ENCYCLOPEDIA, "Wirecard", WebServices())

    assert inquiry.sources[0].url == "https://en.wikipedia.org/wiki/Wirecard"
    assert inquiry.sources[0].tier is SourceTier.REFERENCE


@pytest.mark.parametrize(
    ("tool", "argument", "services", "reason"),
    [
        (ToolName.READ_PAGE, "https://www.reuters.com/a", WebServices(), "500"),
        (ToolName.READ_PAGE, "the annual report", WebServices(), "needs a URL"),
        (ToolName.ENCYCLOPEDIA, "   ", WebServices(), "non-empty"),
        (ToolName.ENCYCLOPEDIA, "Wirecard", WebServices(empty_wiki_search_errors=True), "ValidationError"),
    ],
    ids=["service error", "no url", "blank argument", "unparseable reply"],
)
def test_a_tool_that_cannot_answer_reports_a_failed_inquiry_instead_of_crashing(
    use_tool: ToolUse, tool: ToolName, argument: str, services: WebServices, reason: str
) -> None:
    inquiry = use_tool(tool, argument, services)

    assert inquiry.outcome is InquiryOutcome.FAILED
    assert inquiry.failure is not None and reason in inquiry.failure
    assert inquiry.latency_s >= 0


def test_page_reader_pulls_the_url_out_of_a_wrapped_argument(use_tool: ToolUse) -> None:
    services = WebServices()

    inquiry = use_tool(ToolName.READ_PAGE, '{"url": "https://www.sec.gov/report.pdf"}', services)

    assert services.extracted == ["https://www.sec.gov/report.pdf"]
    assert inquiry.sources[0].tier is SourceTier.OFFICIAL


def test_memory_recalls_by_meaning_reports_its_cost_and_ignores_unrelated_records(
    memory: LongTermMemory,
) -> None:
    stored = asyncio.run(
        memory.remember(
            [
                MemoryRecord(MemoryKind.ENTITY_FACT, "Wirecard AG", "EY audited wirecard", 0.9, "case-1"),
                MemoryRecord(
                    MemoryKind.ENTITY_FACT, "Theranos", "theranos blood tests failed", 0.9, "case-2"
                ),
            ]
        )
    )

    recalled = asyncio.run(memory.recall("wirecard audit"))

    assert stored.value == 2 and stored.usage.prompt_tokens == 3
    assert recalled.value[0].record.text == "EY audited wirecard"
    assert all("theranos" not in r.record.text for r in recalled.value)
    assert recalled.usage.prompt_tokens == 3


def test_publisher_track_record_is_learned_only_from_ground_truth(memory: LongTermMemory) -> None:
    case = CaseFile(Subject(SubjectKind.CLAIM, "Wirecard was audited by EY"))
    question = case.raise_question("Who audited Wirecard?")
    for domain, stance, points_to in [
        ("reuters.com", Stance.SUPPORTS, Verdict.TRUE),
        ("ft.com", Stance.SUPPORTS, Verdict.TRUE),
        ("blog.x", Stance.REFUTES, Verdict.FALSE),
    ]:
        case.record_evidence(
            Evidence(
                question.id,
                f"https://{domain}/",
                domain,
                "s",
                "q",
                stance,
                Strength.DIRECT,
                0.8,
                1,
                points_to,
            )
        )

    outcomes = case.publisher_outcomes(Verdict.TRUE, ResolvedBy.BENCHMARK_LABEL)
    memory.record_publisher_outcomes("case-1", outcomes)

    assert PublisherOutcome("blog.x", False, ResolvedBy.BENCHMARK_LABEL) in outcomes
    assert memory.track_records()["reuters.com"].corroborated == 1
    assert memory.track_records()["blog.x"].contradicted == 1
    assert case.publisher_outcomes(Verdict.UNVERIFIABLE, ResolvedBy.ANALYST) == []


def test_an_unusable_tool_reply_is_not_replayed_from_the_cache(tmp_path: Path, settings: Settings) -> None:
    replies = iter([{"error": "temporarily unavailable"}, {"query": {"search": []}}])
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json=next(replies))

    cache = ResponseCache(tmp_path / "c.sqlite3")
    toolbox = Toolbox.standard(
        Transport(httpx.AsyncClient(transport=httpx.MockTransport(handler)), cache, 1, 0.0), settings
    )

    first = asyncio.run(toolbox.use(ToolName.ENCYCLOPEDIA, "Wirecard", "Q1", 1))
    second = asyncio.run(toolbox.use(ToolName.ENCYCLOPEDIA, "Wirecard", "Q1", 2))

    assert first.outcome is InquiryOutcome.FAILED
    assert second.outcome is InquiryOutcome.EMPTY
    assert len(calls) == 2


def test_a_page_the_extractor_could_not_read_is_a_failed_inquiry(
    settings: Settings, make_transport: Callable[[Handler], Transport]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = json.loads(request.content)["urls"][0]
        return httpx.Response(200, json={"results": [], "failed_results": [{"url": url, "error": "timeout"}]})

    toolbox = Toolbox.standard(make_transport(handler), settings)
    inquiry = asyncio.run(toolbox.use(ToolName.READ_PAGE, "https://www.reuters.com/x", "Q1", 1))

    assert inquiry.outcome is InquiryOutcome.FAILED
    assert inquiry.failure is not None and "timeout" in inquiry.failure
