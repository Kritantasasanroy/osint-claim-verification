import re
from collections import Counter
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field, model_validator

from osint_harness.investigation.subject import Subject
from osint_harness.investigation.verdict import SubjectKind, Verdict


class Split(StrEnum):
    """Dev cases may tune thresholds, prompts and the calibrator, and teach publisher track records; test
    cases are only ever run for the reported numbers."""

    DEV = "dev"
    TEST = "test"


class ExpectedScope(BaseModel):
    kind: SubjectKind
    entity: str
    assertion: str | None = None
    disambiguators: list[str] = []


class ScopeGrade(BaseModel):
    """Did scoping keep what the analyst wrote? Graded by word overlap, not by a model."""

    kind_correct: bool
    assertion_preserved: bool
    disambiguators_preserved: bool

    @property
    def correct(self) -> bool:
        return self.kind_correct and self.assertion_preserved and self.disambiguators_preserved

    @classmethod
    def of(cls, expected: ExpectedScope, subject: Subject) -> "ScopeGrade":
        kept = cls._words(" ".join([subject.statement, subject.entity, *subject.disambiguators]))
        assertion = cls._words(expected.assertion or expected.entity)
        details = [cls._words(d) for d in expected.disambiguators]
        return cls(
            kind_correct=subject.kind is expected.kind,
            assertion_preserved=cls._overlap(assertion, kept) >= 0.7,
            disambiguators_preserved=all(cls._overlap(d, kept) >= 0.6 for d in details if d),
        )

    STOP: ClassVar[frozenset[str]] = frozenset(
        {"the", "a", "an", "of", "for", "and", "in", "at", "on", "to", "with", "by", "is", "was", "were"}
    )

    @classmethod
    def _words(cls, text: str) -> set[str]:
        return {w for w in re.sub(r"[^a-z0-9]+", " ", text.lower()).split() if len(w) > 1} - cls.STOP

    @staticmethod
    def _overlap(needed: set[str], kept: set[str]) -> float:
        return len(needed & kept) / len(needed) if needed else 1.0


class BenchmarkCase(BaseModel):
    id: str
    kind: SubjectKind
    subject: str
    expected_verdict: Verdict
    acceptable_verdicts: list[Verdict]
    key_facts: list[str] = Field(min_length=1)
    tags: list[str] = []
    input_text: str = Field("", description="What an analyst would type; the subject when empty")
    expected_scope: ExpectedScope | None = None
    ground_truth_sources: list[str] = []
    documents: list[str] = Field(
        default_factory=list, description="Files the analyst attaches, relative to the cases file"
    )
    as_of: date | None = None
    slices: list[str] = []
    split: Split = Split.TEST
    closed_book_correct: bool | None = None

    @model_validator(mode="after")
    def _verdicts_fit_the_kind(self) -> "BenchmarkCase":
        allowed = set(self.kind.allowed_verdicts)
        if not {self.expected_verdict, *self.acceptable_verdicts} <= allowed:
            raise ValueError(
                f"case {self.id}: verdicts must be among {sorted(allowed)} for a {self.kind.value}"
            )
        if self.expected_verdict not in self.acceptable_verdicts:
            raise ValueError(f"case {self.id}: the expected verdict must also be acceptable")
        return self

    @property
    def analyst_text(self) -> str:
        return self.input_text or self.subject

    def as_subject(self, as_of: date) -> Subject:
        """The gold scope, for the pre-scoped ablation: what scoping should have produced."""
        scope = self.expected_scope
        return Subject(
            kind=self.kind,
            statement=self.subject,
            as_of=self.as_of or as_of,
            entity=scope.entity if scope else "",
            disambiguators=tuple(scope.disambiguators) if scope else (),
        )

    def accepts(self, verdict: Verdict) -> bool:
        return verdict in self.acceptable_verdicts


class Benchmark(BaseModel):
    description: str
    as_of: date
    cases: list[BenchmarkCase]

    @classmethod
    def load(cls, path: Path) -> "Benchmark":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def only(self, case_ids: list[str]) -> "Benchmark":
        wanted = set(case_ids)
        return self.model_copy(update={"cases": [case for case in self.cases if case.id in wanted]})

    def split(self, split: Split | None) -> "Benchmark":
        if split is None:
            return self
        return self.model_copy(update={"cases": [case for case in self.cases if case.split is split]})

    def case_as_of(self, case: BenchmarkCase) -> date:
        return case.as_of or self.as_of


class BenchmarkAudit:
    """The rules a headline benchmark must meet before its numbers are worth reporting (E2)."""

    REQUIRED_SLICES: ClassVar[tuple[str, ...]] = (
        "post_cutoff",
        "long_tail",
        "materiality",
        "namesake",
        "temporal_state",
        "documents",
        "injection",
        "non_english",
        "mixed",
    )
    MIN_PER_SLICE: ClassVar[int] = 12
    MIN_CASES: ClassVar[int] = 120

    @classmethod
    def problems(cls, benchmark: Benchmark) -> list[str]:
        cases = benchmark.cases
        found: list[str] = []
        ids = Counter(case.id for case in cases)
        found += [f"duplicate case id {case_id}" for case_id, n in ids.items() if n > 1]
        if len(cases) < cls.MIN_CASES:
            found.append(f"{len(cases)} cases, need at least {cls.MIN_CASES}")
        per_slice = Counter(s for case in cases for s in case.slices)
        for name in cls.REQUIRED_SLICES:
            if per_slice[name] < cls.MIN_PER_SLICE:
                found.append(f"slice {name} has {per_slice[name]} cases, need {cls.MIN_PER_SLICE}")
        for name in cls.REQUIRED_SLICES:
            splits = {case.split for case in cases if name in case.slices}
            if per_slice[name] and splits != {Split.DEV, Split.TEST}:
                found.append(f"slice {name} is not represented in both dev and test")
        found += [
            f"case {c.id} has neither input_text nor documents"
            for c in cases
            if not (c.input_text or c.documents)
        ]
        found += [f"case {c.id} has no expected_scope" for c in cases if c.expected_scope is None]
        found += [f"case {c.id} has no ground_truth_sources" for c in cases if not c.ground_truth_sources]
        # A document-only input is scoped into the claim the document makes, so it must be labelled as one.
        found += [
            f"case {c.id} is document-only but labelled {c.kind.value}, not claim"
            for c in cases
            if c.documents and not c.input_text and c.kind is not SubjectKind.CLAIM
        ]
        entity = [c for c in cases if c.kind is not SubjectKind.CLAIM]
        if entity:
            share = Counter(c.expected_verdict for c in entity)
            for verdict, low, high in (
                (Verdict.ADVERSE, 0.3, 0.5),
                (Verdict.NO_ADVERSE, 0.3, 0.5),
                (Verdict.UNVERIFIABLE, 0.1, 0.3),
            ):
                fraction = share[verdict] / len(entity)
                if not low <= fraction <= high:
                    found.append(
                        f"entity cases are {fraction:.0%} {verdict.value}, want {low:.0%}-{high:.0%}"
                    )
        claims = [c for c in cases if c.kind is SubjectKind.CLAIM]
        if claims:
            share = Counter(c.expected_verdict for c in claims)
            for verdict in (Verdict.TRUE, Verdict.FALSE, Verdict.MIXED, Verdict.UNVERIFIABLE):
                if share[verdict] / len(claims) < 0.1:
                    found.append(f"claims are only {share[verdict] / len(claims):.0%} {verdict.value}")
        return found
