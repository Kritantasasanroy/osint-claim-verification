import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, JsonValue

from osint_harness.nvidia import Metered, ModelCall, TokenUsage


class TraceEventKind(StrEnum):
    SCOPED = "scoped"
    MEMORY_RECALLED = "memory_recalled"
    PLANNED = "planned"
    RESEARCH_CHOSEN = "research_chosen"
    QUERY_REJECTED = "query_rejected"
    TOOL_CALLED = "tool_called"
    EVIDENCE_ASSESSED = "evidence_assessed"
    REFLECTED = "reflected"
    CRITIQUED = "critiqued"
    REPORTED = "reported"
    MEMORY_WRITTEN = "memory_written"


class TraceEvent(BaseModel):
    kind: TraceEventKind
    investigation: str
    step: int
    at: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0
    cached: bool = False
    model: str = ""
    calls: list[dict[str, str]] = []
    detail: dict[str, JsonValue] = {}

    @property
    def usage(self) -> TokenUsage:
        return TokenUsage(self.prompt_tokens, self.completion_tokens)


@dataclass
class TraceLog:
    """Append-only JSONL record of every step of one investigation, written as it happens."""

    path: Path
    investigation: str
    events: list[TraceEvent] = field(default_factory=list)
    _prompts_seen: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")
        self.prompts_path.write_text("", encoding="utf-8")

    @property
    def prompts_path(self) -> Path:
        """Full prompt texts keyed by hash, kept beside the trace so the trace itself stays readable."""
        return self.path.with_name("prompts.jsonl")

    def append(
        self, kind: TraceEventKind, step: int, detail: dict[str, JsonValue], latency_s: float = 0.0
    ) -> None:
        self._write(self._event(kind, step, detail, latency_s))

    def append_metered[T](
        self, kind: TraceEventKind, step: int, detail: dict[str, JsonValue], metered: Metered[T]
    ) -> None:
        event = self._event(kind, step, detail, metered.latency_s)
        event.prompt_tokens = metered.usage.prompt_tokens
        event.completion_tokens = metered.usage.completion_tokens
        event.cached = metered.cached
        event.model = metered.calls[-1].model if metered.calls else ""
        event.calls = [self._audited(call) for call in metered.calls]
        self._write(event)

    def _audited(self, call: ModelCall) -> dict[str, str]:
        """Each model call as prompt hashes plus its raw output; prompts land once in the sidecar."""
        hashes = {"system_sha": ModelCall.digest(call.system), "user_sha": ModelCall.digest(call.user)}
        with self.prompts_path.open("a", encoding="utf-8") as handle:
            for text, digest in ((call.system, hashes["system_sha"]), (call.user, hashes["user_sha"])):
                if digest not in self._prompts_seen:
                    self._prompts_seen.add(digest)
                    handle.write(json.dumps({"sha": digest, "text": text}, ensure_ascii=False) + "\n")
        return {"model": call.model, **hashes, "raw_output": call.raw_output}

    @classmethod
    def prompts(cls, path: Path) -> dict[str, str]:
        lines = path.read_text(encoding="utf-8").splitlines()
        return {row["sha"]: row["text"] for row in map(json.loads, lines) if row}

    def _event(
        self, kind: TraceEventKind, step: int, detail: dict[str, JsonValue], latency_s: float
    ) -> TraceEvent:
        return TraceEvent(
            kind=kind,
            investigation=self.investigation,
            step=step,
            at=datetime.now(UTC).isoformat(timespec="milliseconds"),
            latency_s=round(latency_s, 3),
            detail=detail,
        )

    def _write(self, event: TraceEvent) -> None:
        self.events.append(event)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(event.model_dump_json() + "\n")

    @classmethod
    def read(cls, path: Path) -> list[TraceEvent]:
        return [
            TraceEvent.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
