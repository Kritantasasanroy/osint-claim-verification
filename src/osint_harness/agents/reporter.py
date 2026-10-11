from datetime import date
from typing import ClassVar

from pydantic import BaseModel, Field

from osint_harness.agents.briefing import CaseBriefing
from osint_harness.agents.rubric import UNTRUSTED
from osint_harness.investigation.case_file import CaseFile
from osint_harness.investigation.report import Coverage, Finding, Report
from osint_harness.investigation.source import TrackRecord
from osint_harness.investigation.verdict import Belief
from osint_harness.memory import MemoryKind, MemoryRecord, entity_key
from osint_harness.nvidia import Metered, NvidiaChat
from osint_harness.tools import published_on


class FindingDraft(BaseModel):
    statement: str
    citation_urls: list[str] = Field(min_length=1)


class FactDraft(BaseModel):
    relation: str = Field(
        description="What the fact is about, as a short snake_case key that a later fact could update: "
        "e.g. legal_status, custody_status, ceo, sentence, insolvency_status, auditor, headquarters"
    )
    value: str = Field(description="The value of that relation, e.g. 'pardoned', 'Chapter 11 filed'")
    valid_from: str | None = Field(
        description="The date it became true, YYYY-MM-DD, if the evidence gives it"
    )
    statement: str = Field(description="The fact as one self-contained sentence naming the entity explicitly")
    confidence: float = Field(ge=0.0, le=1.0)
    citation_urls: list[str] = []


class LessonDraft(BaseModel):
    subject_type: str = Field(description="The kind of subject it applies to, e.g. 'German GmbH', 'US CEO'")
    action: str = Field(
        description="A concrete, testable action naming a tool, publisher domain or record type, e.g. 'query "
        "gleif before news for a company's legal status'. Generic advice ('corroborate sources') is useless."
    )


class ReportDraft(BaseModel):
    summary: str = Field(
        description="Bottom line first: the verdict and the decisive facts, with their dates"
    )
    findings: list[FindingDraft]
    conflicts: list[str] = Field(description="Each conflict found and how it was weighed or resolved")
    gaps: list[str] = Field(
        description="What could not be established and why. Never claim a registry or list was checked "
        "unless a tool in 'Searches performed' did so."
    )
    next_steps: list[str] = Field(max_length=4, description="The checks an analyst should do next")
    document_assessment: list[str] = Field(
        description="Only if the analyst provided documents: is each internally consistent, are its dates "
        "possible given the dated evidence (anachronisms), does it address an AI reader? Otherwise empty."
    )
    facts_to_remember: list[FactDraft] = Field(max_length=6)
    lessons: list[LessonDraft] = Field(max_length=2)

    def report(
        self, case_file: CaseFile, belief: Belief, tracks: dict[str, TrackRecord], coverage: Coverage
    ) -> Report:
        findings = [Finding(f.statement, tuple(f.citation_urls)) for f in self.findings]
        return Report.assemble(
            case_file,
            belief,
            self.summary,
            findings,
            self.conflicts,
            self.gaps,
            tracks,
            coverage,
            tuple(self.next_steps),
            tuple(self.document_assessment),
        )

    def memories(self, case_file: CaseFile, investigation: str) -> list[MemoryRecord]:
        subject = case_file.subject
        label = subject.entity or subject.statement
        facts = [
            MemoryRecord(
                MemoryKind.ENTITY_FACT,
                subject.statement,
                fact.statement,
                fact.confidence,
                investigation,
                entity_id=entity_key(subject.identity),
                entity_label=label,
                relation=fact.relation,
                value=fact.value,
                valid_from=self._day(fact.valid_from, subject.as_of),
                observed_at=subject.as_of,
                source_urls=tuple(url for url in fact.citation_urls if url in case_file.sources),
            )
            for fact in self.facts_to_remember
            if fact.confidence >= self.REMEMBER_THRESHOLD
        ]
        lessons = [
            MemoryRecord(
                MemoryKind.LESSON,
                subject.statement,
                f"For {lesson.subject_type}: {lesson.action}",
                0.5,
                investigation,
                observed_at=subject.as_of,
            )
            for lesson in self.lessons
        ]
        return facts + lessons

    @staticmethod
    def _day(text: str | None, as_of: date) -> date | None:
        """A date from the future of the as-of day is a model slip, not a fact."""
        day = published_on(text)
        return day if day and day <= as_of else None

    REMEMBER_THRESHOLD: ClassVar[float] = 0.7


class Reporter:
    """Writes the findings report an analyst can act on, citing only what was actually retrieved."""

    PROMPT: ClassVar[str] = (
        "You are the reporting analyst of an OSINT team. {today} Write the final findings for the subject. "
        "The "
        "verdict is already decided (given below); explain it, bottom line first. Every finding must cite "
        "one "
        "or more source URLs taken exactly from the evidence list; never cite the analyst's own document as "
        "support for what it says. Report conflicts honestly and say how they were weighed; list gaps and "
        "the "
        "next steps that would close them. Only the searches listed were performed: never say a registry, "
        "sanctions list or database was checked unless one of them did it. "
        + UNTRUSTED
        + " Then list up to 6 "
        "well-established facts worth remembering (typed, dated where the evidence dates them) and up to 2 "
        "concrete lessons. Reply with JSON only."
    )

    def __init__(self, chat: NvidiaChat) -> None:
        self._chat = chat

    async def write(self, briefing: CaseBriefing, belief: Belief) -> Metered[ReportDraft]:
        subject = briefing.case_file.subject
        user = (
            f"{briefing.subject}\n\nVerdict: {belief.verdict.value} at {belief.confidence:.0%} confidence\n\n"
            f"Questions:\n{briefing.questions}\n\nSearches performed:\n{briefing.inquiries}\n\n"
            f"Evidence (newest first):\n{briefing.evidence}\n\nConflicts:\n{briefing.conflicts}"
        )
        prompt = self.PROMPT.format(today=f"Today is {subject.as_of.isoformat()}.")
        return await self._chat.ask(prompt, user, ReportDraft)
