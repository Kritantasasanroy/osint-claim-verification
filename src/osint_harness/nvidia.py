import hashlib
import json
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel, Field, JsonValue, ValidationError

from osint_harness.settings import Settings, TokenPrice
from osint_harness.transport import Transport


class MalformedCompletion(RuntimeError):
    def __init__(self, schema_name: str, content: str, reason: str) -> None:
        super().__init__(f"The model did not return a valid {schema_name}: {reason}. Got: {content[:300]}")
        self.reason = reason


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
        )

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def cost_usd(self, price: TokenPrice) -> float:
        return (
            self.prompt_tokens * price.input_per_mtok + self.completion_tokens * price.output_per_mtok
        ) / 1_000_000


@dataclass(frozen=True)
class ModelCall:
    """One completion exactly as sent and received, so a trace can be audited without the response cache."""

    model: str
    system: str
    user: str
    raw_output: str

    @staticmethod
    def digest(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class Metered[T]:
    """A value from a paid call, with what the call cost in tokens and time."""

    value: T
    usage: TokenUsage
    latency_s: float
    cached: bool = False
    calls: tuple[ModelCall, ...] = ()


class _Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0


class _Message(BaseModel):
    content: str | None = None


class _Choice(BaseModel):
    message: _Message
    finish_reason: str = ""


class _ChatReply(BaseModel):
    choices: list[_Choice] = Field(min_length=1)
    usage: _Usage


class _EmbeddingRow(BaseModel):
    embedding: list[float]


class _EmbeddingReply(BaseModel):
    data: list[_EmbeddingRow]
    usage: _Usage


class EmbeddingPurpose(StrEnum):
    QUERY = "query"
    PASSAGE = "passage"


class ConstrainedEnums:
    """Mixin for answer schemas that share an enum but may only use some of its values; the decoded schema
    is narrowed to those values so the model is never offered an answer its validator would reject."""

    @classmethod
    def enum_choices(cls) -> dict[str, tuple[str, ...]]:
        return {}


class NvidiaChat:
    """Structured (JSON-schema constrained) chat completions from an NVIDIA-hosted model."""

    URL: ClassVar[str] = "https://integrate.api.nvidia.com/v1/chat/completions"
    MAX_TOKENS: ClassVar[int] = 8192
    # A model whose thinking cannot be capped (the judge's GLM ignores both switches) spends output tokens on
    # hidden reasoning; 8192 ran out on large gradings in the v2 dev run.
    MAX_TOKENS_UNCAPPED_THINKING: ClassVar[int] = 16384
    MAX_THINKING_TOKENS: ClassVar[int] = 3072

    def __init__(
        self, transport: Transport, settings: Settings, model: str | None = None, seed: int | None = None
    ) -> None:
        self._transport = transport
        self._settings = settings
        self._model = model or settings.llm_model
        # Thinking controls are a feature of the agent model's chat template; another family (the judge's)
        # may reject them.
        self._thinking_controls = self._model == settings.llm_model
        self._reasoning = settings.llm_reasoning and self._thinking_controls
        self._temperature = settings.temperature
        self._use_cache = settings.llm_cache
        self._seed = seed
        self._headers = {"Authorization": f"Bearer {settings.nvidia_api_key}"}

    @property
    def model(self) -> str:
        return self._model

    def with_seed(self, seed: int | None) -> "NvidiaChat":
        """The same model sampled with another seed; the seed is part of every request (and cache key)."""
        return NvidiaChat(self._transport, self._settings, self._model, seed)

    def for_model(self, model: str) -> "NvidiaChat":
        return NvidiaChat(self._transport, self._settings, model, self._seed)

    MAX_ATTEMPTS: ClassVar[int] = 3

    async def ask[T: BaseModel](self, system: str, user: str, schema: type[T]) -> Metered[T]:
        """A truncated or off-schema reply is retried, up to three attempts in all, each told what was wrong
        (the failing fields, or that it ran out of tokens, in which case it also gets twice the budget and no
        thinking). Every attempt is billed and recorded."""
        spent, latency = TokenUsage(), 0.0
        calls: tuple[ModelCall, ...] = ()
        attempt_user, thinking, budget = user, self._reasoning, None
        for number in range(1, self.MAX_ATTEMPTS + 1):
            attempt = await self._attempt(system, attempt_user, schema, thinking, budget)
            try:
                parsed = attempt.parsed(schema, spent, latency)
            except MalformedCompletion as problem:
                self._transport.forget_post(self.URL, attempt.payload)
                spent, latency, calls = (
                    spent + attempt.usage,
                    latency + attempt.latency_s,
                    (*calls, attempt.call),
                )
                if number == self.MAX_ATTEMPTS:
                    raise
                attempt_user = (
                    f"{user}\n\nYour previous reply was unusable ({problem.reason}). "
                    "Reply with the JSON only."
                )
                thinking = False
                if attempt.truncated:
                    budget = 2 * (budget or self._max_tokens())
                continue
            return replace(parsed, calls=(*calls, *parsed.calls))
        raise AssertionError("unreachable: the last attempt either returns or raises")

    def _max_tokens(self) -> int:
        return self.MAX_TOKENS if self._thinking_controls else self.MAX_TOKENS_UNCAPPED_THINKING

    @staticmethod
    def _decoding_schema(schema: type[BaseModel]) -> dict[str, JsonValue]:
        """The JSON schema the model sees and is decoded into, with any shared enums narrowed."""
        decoded: dict[str, JsonValue] = schema.model_json_schema()
        definitions = decoded.get("$defs")
        if issubclass(schema, ConstrainedEnums):
            for name, values in schema.enum_choices().items():
                enum = definitions.get(name) if isinstance(definitions, dict) else None
                if not isinstance(enum, dict):
                    raise ValueError(
                        f"{schema.__name__} narrows the enum {name}, which its schema does not define"
                    )
                enum["enum"] = list(values)
        return decoded

    @staticmethod
    def _answer_format(schema: type[BaseModel]) -> str:
        """The model must plan its answer in the shape it will be decoded into, so it sees the schema."""
        return (
            "Answer with exactly one JSON object that matches this JSON Schema; every field's description "
            f"says what it must contain:\n{json.dumps(NvidiaChat._decoding_schema(schema))}"
        )

    async def _attempt(
        self,
        system: str,
        user: str,
        schema: type[BaseModel],
        thinking: bool,
        max_tokens: int | None = None,
    ) -> "_Attempt":
        full_system = f"{system}\n\n{self._answer_format(schema)}"
        payload: dict[str, JsonValue] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": full_system},
                {"role": "user", "content": user},
            ],
            "temperature": self._temperature,
            "max_tokens": max_tokens or self._max_tokens(),
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": self._decoding_schema(schema)},
            },
        }
        if self._thinking_controls:
            payload["chat_template_kwargs"] = {"enable_thinking": thinking}
            payload["nvext"] = {"max_thinking_tokens": self.MAX_THINKING_TOKENS}
        if self._seed is not None:
            payload["seed"] = self._seed
        reply = await self._transport.post(self.URL, payload, self._headers, self._use_cache)
        try:
            parsed = _ChatReply.model_validate_json(reply.text)
        except ValidationError as error:
            self._transport.forget_post(self.URL, payload)
            raise MalformedCompletion(
                schema.__name__, reply.text, "the service reply was not a completion"
            ) from error
        choice = parsed.choices[0]
        content = choice.message.content or ""
        return _Attempt(
            payload=payload,
            call=ModelCall(self._model, full_system, user, content),
            content=content,
            truncated=choice.finish_reason == "length",
            usage=TokenUsage(parsed.usage.prompt_tokens, parsed.usage.completion_tokens),
            latency_s=reply.latency_s,
            cached=reply.cached,
        )


@dataclass(frozen=True)
class _Attempt:
    """One completion request and its reply; an unusable reply is evicted from the cache, not replayed."""

    payload: JsonValue
    call: ModelCall
    content: str
    truncated: bool
    usage: TokenUsage
    latency_s: float
    cached: bool

    def parsed[T: BaseModel](
        self, schema: type[T], earlier: TokenUsage, earlier_latency_s: float
    ) -> Metered[T]:
        if self.truncated:
            raise MalformedCompletion(schema.__name__, self.content, "it ran out of output tokens")
        try:
            value = schema.model_validate_json(self._without_fences())
        except ValidationError as error:
            raise MalformedCompletion(schema.__name__, self.content, self._why(error)) from error
        return Metered(
            value, earlier + self.usage, earlier_latency_s + self.latency_s, self.cached, (self.call,)
        )

    @staticmethod
    def _why(error: ValidationError) -> str:
        """Which fields failed and why, so the one retry can tell the model what to fix."""
        problems = [
            f"{'.'.join(str(part) for part in item['loc']) or 'reply'}: {item['msg']}"
            for item in error.errors()[:3]
        ]
        return "; ".join(problems) or str(error).splitlines()[0]

    def _without_fences(self) -> str:
        text = self.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else ""
            text = text.rsplit("```", 1)[0]
        return text.strip()


class NvidiaEmbedder:
    URL: ClassVar[str] = "https://integrate.api.nvidia.com/v1/embeddings"

    def __init__(self, transport: Transport, settings: Settings) -> None:
        self._transport = transport
        self._model = settings.embedding_model
        self._headers = {"Authorization": f"Bearer {settings.nvidia_api_key}"}

    async def embed(self, texts: list[str], purpose: EmbeddingPurpose) -> Metered[list[list[float]]]:
        """A reply that is not a set of embeddings is evicted from the cache and reported, never replayed."""
        payload: JsonValue = {
            "model": self._model,
            "input": [text[:4000] for text in texts],
            "input_type": purpose.value,
            "encoding_format": "float",
            "truncate": "END",
        }
        reply = await self._transport.post(self.URL, payload, self._headers)
        try:
            parsed = _EmbeddingReply.model_validate_json(reply.text)
        except ValidationError as error:
            self._transport.forget_post(self.URL, payload)
            raise MalformedCompletion(
                "embeddings", reply.text, "the service reply was not embeddings"
            ) from error
        return Metered(
            [row.embedding for row in parsed.data],
            TokenUsage(parsed.usage.prompt_tokens, parsed.usage.completion_tokens),
            reply.latency_s,
            reply.cached,
        )
