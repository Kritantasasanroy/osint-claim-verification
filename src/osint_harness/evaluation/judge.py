from enum import StrEnum
from statistics import fmean
from typing import ClassVar

from pydantic import BaseModel, Field, create_model

from osint_harness.evaluation.benchmark import BenchmarkCase
from osint_harness.investigator import Investigation
from osint_harness.nvidia import Metered, NvidiaChat


class MemoryLabel(StrEnum):
    RELEVANT = "relevant"
    IRRELEVANT = "irrelevant"
    MISLEADING = "misleading"


class AtomicCheck(BaseModel):
    fact: str = Field(description="One atomic fact the finding asserts")
    supported: bool = Field(description="Do the cited excerpts state or directly entail this fact?")


class FindingCheck(BaseModel):
    atomic_facts: list[AtomicCheck] = Field(min_length=1)


class Grading(BaseModel):
    """One verdict per numbered item, in order; the schema is sized per case so none can be skipped.
    Each finding is split into atomic facts and every atom is checked against its cited excerpts, so a
    finding with one true half and one invented half counts as half supported."""

    key_facts_established: list[bool]
    findings: list[FindingCheck]
    memory_labels_in_order: list[MemoryLabel]

    @classmethod
    def sized(cls, facts: int, findings: int, memories: int) -> type["Grading"]:
        return create_model(
            "Grading",
            __base__=cls,
            key_facts_established=(list[bool], Field(min_length=facts, max_length=facts)),
            findings=(list[FindingCheck], Field(min_length=findings, max_length=findings)),
            memory_labels_in_order=(list[MemoryLabel], Field(min_length=memories, max_length=memories)),
        )

    @property
    def key_fact_recall(self) -> float:
        return fmean(self.key_facts_established)

    @property
    def atoms(self) -> list[bool]:
        return [atom.supported for finding in self.findings for atom in finding.atomic_facts]

    @property
    def citation_precision(self) -> float:
        """Share of atomic facts supported by their own citations; no findings supports nothing, so zero."""
        return fmean(self.atoms) if self.atoms else 0.0

    @property
    def findings_supported(self) -> list[bool]:
        return [all(atom.supported for atom in finding.atomic_facts) for finding in self.findings]

    def memory_labels(self, memory_ids: list[str]) -> dict[str, MemoryLabel]:
        return dict(zip(memory_ids, self.memory_labels_in_order, strict=True))


class Judge:
    """Grades a finished investigation against ground truth, from its outputs only, never its reasoning.
    It runs on another model family than the agents (JUDGE_MODEL), so it does not grade its own writing."""

    PROMPT: ClassVar[str] = (
        "You grade OSINT investigations against ground truth. Answer every numbered item, in order. "
        "(1) key_facts_established: for each key fact, does the report's summary or findings establish it "
        "(same meaning, not exact words)? "
        "(2) findings: split each finding into its atomic facts (each a single checkable statement) and, for "
        "each atom, say whether the quoted source excerpts cited for that finding state or directly entail "
        "it. "
        "Background knowledge does not count: only the excerpts. "
        "(3) memory_labels_in_order: for each recalled memory, label it 'relevant' (about this subject "
        "and consistent with ground truth), 'irrelevant' (about something else and harmless), or "
        "'misleading' (contradicts ground truth, is outdated, or is about a different entity with a "
        "similar name in a way that could mislead). Be strict. Reply with JSON only."
    )

    def __init__(self, chat: NvidiaChat) -> None:
        self._chat = chat

    @property
    def model(self) -> str:
        return self._chat.model

    async def grade(self, case: BenchmarkCase, investigation: Investigation) -> Metered[Grading]:
        report = investigation.report
        sources = investigation.case_file.sources
        facts = "\n".join(f"{n}. {fact}" for n, fact in enumerate(case.key_facts, start=1))
        findings = "\n\n".join(
            f"FINDING {n}: {finding.statement}\n"
            + "\n".join(f"  excerpt from {url}: {sources[url].content}" for url in finding.citations)
            for n, finding in enumerate(report.findings, start=1)
        )
        memories = "\n".join(
            f"{r.label}: {r.record.text} (learned while investigating '{r.record.subject}')"
            for r in investigation.recollections
        )
        user = (
            f"Subject: {case.subject}\nAs of: {investigation.case_file.subject.as_of.isoformat()}\n"
            f"Ground-truth verdict: {case.expected_verdict.value}\n"
            f"Key facts:\n{facts}\n\nReport summary: {report.summary}\n\n{findings or '(no findings)'}\n\n"
            f"Recalled memories:\n{memories or '(none)'}"
        )
        schema = Grading.sized(len(case.key_facts), len(report.findings), len(investigation.recollections))
        return await self._chat.ask(self.PROMPT, user, schema)
