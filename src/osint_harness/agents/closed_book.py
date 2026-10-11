from typing import ClassVar

from pydantic import BaseModel, Field

from osint_harness.agents.rubric import VERDICTS, dated
from osint_harness.investigation.subject import Subject
from osint_harness.investigation.verdict import Belief, SubjectKind, Verdict
from osint_harness.nvidia import ConstrainedEnums, Metered, NvidiaChat


class ClosedBookAnswer(ConstrainedEnums, BaseModel):
    ALLOWED: ClassVar[tuple[Verdict, ...]] = tuple(Verdict)
    reasoning: str = Field(description="One or two sentences")
    verdict: Verdict
    confidence: float = Field(ge=0, le=1, description="Calibrated probability that the verdict is correct")

    @classmethod
    def for_kind(cls, kind: SubjectKind) -> type["ClosedBookAnswer"]:
        return type(f"{kind.value.title()}ClosedBookAnswer", (cls,), {"ALLOWED": kind.allowed_verdicts})

    @classmethod
    def enum_choices(cls) -> dict[str, tuple[str, ...]]:
        return {Verdict.__name__: tuple(v.value for v in cls.ALLOWED)}

    def belief(self, kind: SubjectKind) -> Belief:
        """The stated confidence on the verdict, the rest spread evenly: all a closed book can say."""
        allowed = kind.allowed_verdicts
        verdict = self.verdict if self.verdict in allowed else Verdict.UNVERIFIABLE
        rest = (1 - self.confidence) / (len(allowed) - 1)
        scores = {v: (self.confidence if v is verdict else rest) for v in allowed}
        top = max(scores.values())
        return Belief.among(
            allowed, scores, verdict if scores[verdict] >= top else max(scores, key=scores.__getitem__)
        )


class ClosedBookAnalyst:
    """The floor every investigation must beat: the same model, the same rubric, no tools and no memory."""

    PROMPT: ClassVar[str] = (
        "You are an OSINT analyst answering from memory only; you have no tools. " + VERDICTS + " Give a "
        "calibrated probability that your verdict is correct. Reply with JSON only."
    )

    def __init__(self, chat: NvidiaChat) -> None:
        self._chat = chat

    async def answer(self, subject: Subject) -> Metered[ClosedBookAnswer]:
        allowed = ", ".join(v.value for v in subject.kind.allowed_verdicts)
        user = (
            f"{dated(subject)}\nSubject ({subject.kind.value}): {subject.statement}\n"
            f"Allowed verdicts: {allowed}"
        )
        return await self._chat.ask(self.PROMPT, user, ClosedBookAnswer.for_kind(subject.kind))
