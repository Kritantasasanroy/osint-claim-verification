import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import ClassVar, Protocol

import numpy as np

from osint_harness.investigation.source import PublisherOutcome, TrackRecord
from osint_harness.nvidia import EmbeddingPurpose, Metered, NvidiaEmbedder, TokenUsage


class MemoryKind(StrEnum):
    ENTITY_FACT = "entity_fact"
    LESSON = "lesson"


def entity_key(name: str) -> str:
    """A namesake-safe key: the entity's name plus whatever disambiguates it, normalised."""
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def name_tokens(name: str) -> frozenset[str]:
    """A name as a set of words, initials dropped: "Michael I. Jordan" and "Michael Jordan" share one."""
    return frozenset(word for word in entity_key(name).split() if len(word) > 1)


@dataclass(frozen=True)
class MemoryRecord:
    """A typed fact (entity, relation, value, valid from/to) or a lesson; free text is only its rendering.

    A fact is current until a later fact with the same entity and relation but another value supersedes it,
    so "sentenced to four years" becomes history, not a contradiction, once "pardoned" is learned.
    """

    kind: MemoryKind
    subject: str
    text: str
    confidence: float
    learned_in: str
    entity_id: str = ""
    entity_label: str = ""
    relation: str = ""
    value: str = ""
    valid_from: date | None = None
    valid_to: date | None = None
    observed_at: date | None = None
    source_urls: tuple[str, ...] = ()

    @property
    def is_current(self) -> bool:
        return self.valid_to is None


@dataclass(frozen=True)
class Recollection:
    memory_id: int
    record: MemoryRecord
    similarity: float
    times_recalled: int = 0
    times_distrusted: int = 0

    @property
    def label(self) -> str:
        """How agents, the judge and the scoreboard all refer to this memory."""
        return f"M{self.memory_id}"

    def describe(self) -> str:
        record = self.record
        parts = [record.kind.value, f"from investigation of '{record.subject}'"]
        if record.observed_at:
            parts.append(f"observed {record.observed_at.isoformat()}")
        if record.valid_from:
            parts.append(f"valid from {record.valid_from.isoformat()}")
        if record.valid_to:
            parts.append(f"SUPERSEDED on {record.valid_to.isoformat()}, historical only")
        parts.append(f"confidence {record.confidence:.0%}")
        if self.times_distrusted:
            parts.append(f"distrusted {self.times_distrusted} of {self.times_recalled} times recalled")
        return f"[{', '.join(parts)}] {record.text}"


class MemoryStore(Protocol):
    async def recall(
        self, query: str, entity: str = "", identity: str = ""
    ) -> Metered[list[Recollection]]: ...

    async def remember(self, records: list[MemoryRecord]) -> Metered[int]: ...

    def record_publisher_outcomes(self, investigation: str, outcomes: list[PublisherOutcome]) -> None: ...

    def record_distrust(self, memory_ids: list[int]) -> None: ...

    def track_records(self) -> dict[str, TrackRecord]: ...

    def forget_investigation(self, investigation: str) -> None: ...


class NoLongTermMemory:
    """Stands in for long-term memory in the ablations without it: recalls nothing, keeps nothing."""

    async def recall(self, query: str, entity: str = "", identity: str = "") -> Metered[list[Recollection]]:
        return Metered([], TokenUsage(), 0.0)

    async def remember(self, records: list[MemoryRecord]) -> Metered[int]:
        return Metered(0, TokenUsage(), 0.0)

    def record_publisher_outcomes(self, investigation: str, outcomes: list[PublisherOutcome]) -> None:
        return None

    def record_distrust(self, memory_ids: list[int]) -> None:
        return None

    def track_records(self) -> dict[str, TrackRecord]:
        return {}

    def forget_investigation(self, investigation: str) -> None:
        return None


class LessonCheck:
    """A lesson is kept only if it names something concrete to do: a tool, a publisher or a kind of record.
    "Corroborate with multiple sources" teaches nothing the prompts do not already say."""

    CONCRETE: ClassVar[re.Pattern[str]] = re.compile(
        r"\b(web_search|news_search|read_page|encyclopedia|wikidata|gleif|sec_edgar|court_records|wayback|"
        r"sanctions|registry|register|docket|filing|10-k|8-k|edgar|lei|handelsregister|companies house|"
        r"courtlistener|pacer|archive)\b|\b[a-z0-9-]+\.(com|org|gov|de|uk|eu|int|net)\b",
        re.IGNORECASE,
    )

    @classmethod
    def is_specific(cls, lesson: str) -> bool:
        return bool(cls.CONCRETE.search(lesson))


@dataclass
class LongTermMemory:
    """What past investigations concluded, recalled by meaning; written only from the agent's own reports,
    and its publisher track records only from outcomes ground truth or an analyst confirmed."""

    path: Path
    embedder: NvidiaEmbedder
    _db: sqlite3.Connection = field(init=False)
    TOP_K: ClassVar[int] = 6
    MIN_SIMILARITY: ClassVar[float] = 0.3
    COLUMNS: ClassVar[str] = (
        "id, kind, subject, text, confidence, learned_in, entity_id, entity_label, relation, value, "
        "valid_from, valid_to, observed_at, source_urls, embedding, recalled, distrusted"
    )

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self.path))
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, subject TEXT, text TEXT,
                confidence REAL, learned_in TEXT, entity_id TEXT, entity_label TEXT, relation TEXT,
                value TEXT, valid_from TEXT, valid_to TEXT, observed_at TEXT, source_urls TEXT,
                embedding TEXT, recalled INTEGER DEFAULT 0, distrusted INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS publisher_outcomes (
                domain TEXT, investigation TEXT, agreed INTEGER, resolved_by TEXT);
            """
        )

    async def recall(self, query: str, entity: str = "", identity: str = "") -> Metered[list[Recollection]]:
        """Current facts and lessons by meaning, after two gates: a fact about a namesake (same name, another
        identity) is never shown, and a memory the agent keeps distrusting ranks lower."""
        rows = self._db.execute(f"SELECT {self.COLUMNS} FROM facts").fetchall()
        if not rows:
            return Metered([], TokenUsage(), 0.0)
        embedded = await self.embedder.embed([query], EmbeddingPurpose.QUERY)
        [query_vector] = embedded.value
        matrix = np.array([json.loads(row[14]) for row in rows], dtype=float)
        target = np.array(query_vector, dtype=float)
        similarities = matrix @ target / (np.linalg.norm(matrix, axis=1) * np.linalg.norm(target) + 1e-12)
        key, name = entity_key(identity or entity), name_tokens(entity)
        scored: list[tuple[float, Recollection]] = []
        for row, similarity in zip(rows, similarities.tolist(), strict=True):
            recollection = Recollection(row[0], self._record(row), similarity, int(row[15]), int(row[16]))
            record = recollection.record
            if record.kind is MemoryKind.ENTITY_FACT and not record.is_current:
                continue
            if key and self._is_namesake(record, key, name):
                continue
            exact = bool(key) and record.entity_id == key
            distrust = recollection.times_distrusted / max(1, recollection.times_recalled)
            score = (similarity + (0.5 if exact else 0.0)) * (1 - 0.5 * distrust)
            if similarity >= self.MIN_SIMILARITY or exact:
                scored.append((score, recollection))
        recalled = [r for _, r in sorted(scored, key=lambda pair: -pair[0])[: self.TOP_K]]
        self._db.executemany(
            "UPDATE facts SET recalled = recalled + 1 WHERE id = ?", [(r.memory_id,) for r in recalled]
        )
        self._db.commit()
        return Metered(recalled, embedded.usage, embedded.latency_s)

    @staticmethod
    def _is_namesake(record: MemoryRecord, key: str, name: frozenset[str]) -> bool:
        """Same name, another identity: the one memory that must never reach the agents."""
        if record.kind is not MemoryKind.ENTITY_FACT or not record.entity_id or record.entity_id == key:
            return False
        return bool(name) and name_tokens(record.entity_label) == name

    def history(self, entity: str) -> list[MemoryRecord]:
        """Every fact ever learned about an entity, superseded ones included, oldest first."""
        rows = self._db.execute(
            f"SELECT {self.COLUMNS} FROM facts WHERE entity_id = ? ORDER BY id", (entity_key(entity),)
        ).fetchall()
        return [self._record(row) for row in rows]

    async def remember(self, records: list[MemoryRecord]) -> Metered[int]:
        kept = [r for r in records if r.kind is MemoryKind.ENTITY_FACT or LessonCheck.is_specific(r.text)]
        if not kept:
            return Metered(0, TokenUsage(), 0.0)
        embedded = await self.embedder.embed(
            [f"{record.entity_label or record.subject}: {record.text}" for record in kept],
            EmbeddingPurpose.PASSAGE,
        )
        for record, vector in zip(kept, embedded.value, strict=True):
            self._supersede(record)
            self._db.execute(
                "INSERT INTO facts (kind, subject, text, confidence, learned_in, entity_id, entity_label, "
                "relation, value, valid_from, valid_to, observed_at, source_urls, embedding) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.kind.value,
                    record.subject,
                    record.text,
                    record.confidence,
                    record.learned_in,
                    record.entity_id,
                    record.entity_label,
                    record.relation,
                    record.value,
                    self._iso(record.valid_from),
                    self._iso(record.valid_to),
                    self._iso(record.observed_at),
                    json.dumps(list(record.source_urls)),
                    json.dumps(vector),
                ),
            )
        self._db.commit()
        return Metered(len(kept), embedded.usage, embedded.latency_s)

    def _supersede(self, record: MemoryRecord) -> None:
        """A current fact with the same entity and relation but another value ends where this one begins."""
        if record.kind is not MemoryKind.ENTITY_FACT or not (record.entity_id and record.relation):
            return
        ended = record.valid_from or record.observed_at or date.today()
        self._db.execute(
            "UPDATE facts SET valid_to = ? WHERE kind = ? AND entity_id = ? AND relation = ? "
            "AND valid_to IS NULL AND lower(value) != lower(?)",
            (
                ended.isoformat(),
                MemoryKind.ENTITY_FACT.value,
                record.entity_id,
                record.relation,
                record.value,
            ),
        )

    def record_distrust(self, memory_ids: list[int]) -> None:
        self._db.executemany(
            "UPDATE facts SET distrusted = distrusted + 1 WHERE id = ?", [(i,) for i in memory_ids]
        )
        self._db.commit()

    def record_publisher_outcomes(self, investigation: str, outcomes: list[PublisherOutcome]) -> None:
        self._db.executemany(
            "INSERT INTO publisher_outcomes VALUES (?,?,?,?)",
            [(o.domain, investigation, int(o.agreed), o.resolved_by.value) for o in outcomes],
        )
        self._db.commit()

    def outcome_investigations(self) -> set[str]:
        return {row[0] for row in self._db.execute("SELECT DISTINCT investigation FROM publisher_outcomes")}

    def track_records(self) -> dict[str, TrackRecord]:
        rows = self._db.execute(
            "SELECT domain, SUM(agreed), SUM(1 - agreed) FROM publisher_outcomes GROUP BY domain"
        ).fetchall()
        return {domain: TrackRecord(int(agreed), int(disagreed)) for domain, agreed, disagreed in rows}

    def forget_investigation(self, investigation: str) -> None:
        """Erases what one investigation taught, so re-running it starts from what came before it."""
        self._db.execute("DELETE FROM facts WHERE learned_in = ?", (investigation,))
        self._db.execute("DELETE FROM publisher_outcomes WHERE investigation = ?", (investigation,))
        self._db.commit()

    @staticmethod
    def _iso(day: date | None) -> str | None:
        return day.isoformat() if day else None

    @staticmethod
    def _day(text: str | None) -> date | None:
        return date.fromisoformat(text) if text else None

    @classmethod
    def _record(cls, row: tuple[object, ...]) -> MemoryRecord:
        return MemoryRecord(
            kind=MemoryKind(str(row[1])),
            subject=str(row[2]),
            text=str(row[3]),
            confidence=float(str(row[4])),
            learned_in=str(row[5]),
            entity_id=str(row[6] or ""),
            entity_label=str(row[7] or ""),
            relation=str(row[8] or ""),
            value=str(row[9] or ""),
            valid_from=cls._day(row[10] if isinstance(row[10], str) else None),
            valid_to=cls._day(row[11] if isinstance(row[11], str) else None),
            observed_at=cls._day(row[12] if isinstance(row[12], str) else None),
            source_urls=tuple(json.loads(str(row[13] or "[]"))),
        )
