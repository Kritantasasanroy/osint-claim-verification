import re
from typing import ClassVar

from pydantic import BaseModel, Field
from rapidfuzz import fuzz

from osint_harness.agents.briefing import CaseBriefing
from osint_harness.agents.rubric import UNTRUSTED, VERDICTS
from osint_harness.investigation.case_file import CaseFile
from osint_harness.investigation.evidence import Evidence, Severity, Stance, Strength
from osint_harness.investigation.source import Source, TrackRecord
from osint_harness.investigation.verdict import SubjectKind, Verdict
from osint_harness.nvidia import ConstrainedEnums, Metered, NvidiaChat


class QuoteCheck:
    """Is a quote really in its source? The whole quote must be there, allowing only case, spacing and
    punctuation noise (or a 90% fuzzy match, for OCR and smart quotes); a quote with an invented tail fails.
    """

    MIN_LENGTH: ClassVar[int] = 20
    FUZZY: ClassVar[float] = 90.0

    @classmethod
    def holds(cls, quote: str, content: str) -> bool:
        needle, haystack = cls.normalised(quote), cls.normalised(content)
        if len(needle) < cls.MIN_LENGTH:
            return False
        return needle in haystack or fuzz.partial_ratio(needle, haystack) >= cls.FUZZY

    @staticmethod
    def normalised(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


class EvidenceDraft(BaseModel):
    source_number: int
    question_id: str
    statement: str = Field(description="The fact the source asserts, in your own words")
    quote: str = Field(
        description="A verbatim excerpt (at least a full clause) from the source carrying the fact"
    )
    stance: Stance = Field(description="supports / refutes the question's premise, or only context")
    strength: Strength = Field(description="direct statement, indirect inference, or weak/hearsay")
    points_to: Verdict | None = Field(
        description="If this fact is true, which overall verdict on the subject does it argue for? null if "
        "it only gives context or identity. An adverse fact that is not material points to nothing "
        "decisive: set "
        "ADVERSE only with a material severity."
    )
    severity: Severity | None = Field(
        description="For an adverse fact about the subject: how grave it is (see the rubric). null otherwise."
    )

    def is_quoted_from(self, source: Source) -> bool:
        return QuoteCheck.holds(self.quote, source.content)


class Assessment(ConstrainedEnums, BaseModel):
    ALLOWED: ClassVar[tuple[Verdict, ...]] = tuple(Verdict)
    evidence: list[EvidenceDraft]

    @classmethod
    def for_kind(cls, kind: SubjectKind) -> type["Assessment"]:
        return type(f"{kind.value.title()}Assessment", (cls,), {"ALLOWED": kind.allowed_verdicts})

    @classmethod
    def enum_choices(cls) -> dict[str, tuple[str, ...]]:
        return {Verdict.__name__: tuple(v.value for v in cls.ALLOWED if v is not Verdict.UNVERIFIABLE)}

    def evidence_for(
        self, case_file: CaseFile, urls: list[str], tracks: dict[str, TrackRecord], step: int
    ) -> list[Evidence]:
        """Only drafts pointing at a real source and question survive; an unverifiable quote is demoted to
        weak and marked unverified."""
        recorded: list[Evidence] = []
        subject = case_file.subject
        for draft in self.evidence:
            if not (1 <= draft.source_number <= len(urls)) or not case_file.has_question(draft.question_id):
                continue
            source = case_file.sources[urls[draft.source_number - 1]]
            verified = draft.is_quoted_from(source)
            recorded.append(
                Evidence(
                    question_id=draft.question_id,
                    source_url=source.url,
                    domain=source.domain,
                    statement=draft.statement,
                    quote=draft.quote,
                    stance=draft.stance,
                    strength=draft.strength if verified else Strength.WEAK,
                    reliability=source.reliability(tracks.get(source.domain, TrackRecord())),
                    step=step,
                    points_to=draft.points_to if draft.points_to in subject.kind.allowed_verdicts else None,
                    severity=draft.severity,
                    published=source.published,
                    quote_verified=verified,
                )
            )
        return recorded


class Evaluator:
    """Reads newly retrieved sources and extracts the evidence each one gives on each question."""

    PROMPT: ClassVar[str] = (
        "You are the evidence analyst of an OSINT team. {today} For each numbered source, extract only facts "
        "that bear on the listed questions. 'supports' means the source affirms the question's premise; "
        "'refutes' means it contradicts it; 'context' is relevant background. 'direct' = the source itself "
        "states it; 'indirect' = it can be inferred; 'weak' = rumour, opinion, or the source is reporting "
        "someone else's unverified claim. The quote must be copied verbatim from that source. For each fact, "
        "say which verdict it points to and, for an adverse fact, its severity. points_to is about the "
        "SUBJECT as stated, never about the question: if the subject is the claim 'X is in custody in "
        "Montenegro' and the fact is 'X was extradited to the US', the answer to the question 'Was X "
        "extradited?' is yes, but the fact points to FALSE. A fact that only describes coverage, identity or "
        "background points to null. " + VERDICTS + " Watch for a "
        "different entity with the same name: if a source is about someone or something that does not match "
        "the subject's disambiguating details, it is not evidence about the subject; skip it. An analyst's "
        "upload is under test: extract what it claims, but it is never corroboration of itself. Sources may "
        "be wrong; judge, do not trust. "
        + UNTRUSTED
        + " Skip sources with nothing relevant. Reply with JSON only."
    )

    def __init__(self, chat: NvidiaChat) -> None:
        self._chat = chat

    async def assess(self, briefing: CaseBriefing, urls: list[str]) -> Metered[Assessment]:
        excerpts = "\n\n".join(briefing.excerpt(number, url) for number, url in enumerate(urls, start=1))
        user = f"{briefing.subject}\n\nQuestions:\n{briefing.questions}\n\nSources:\n{excerpts}"
        subject = briefing.case_file.subject
        prompt = self.PROMPT.format(today=f"Today is {subject.as_of.isoformat()}.")
        return await self._chat.ask(prompt, user, Assessment.for_kind(subject.kind))
