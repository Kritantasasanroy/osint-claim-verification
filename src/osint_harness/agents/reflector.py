from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel, Field, field_validator, model_validator

from osint_harness.agents.briefing import CaseBriefing
from osint_harness.agents.rubric import UNTRUSTED, VERDICTS
from osint_harness.investigation.case_file import CaseFile
from osint_harness.investigation.question import Question
from osint_harness.investigation.verdict import Belief, SubjectKind, Verdict
from osint_harness.nvidia import ConstrainedEnums, Metered, NvidiaChat


class Decision(StrEnum):
    CONTINUE = "continue"
    CONCLUDE = "conclude"


class VerdictScore(BaseModel):
    verdict: Verdict
    probability: float = Field(ge=0.0, le=1.0)


class Reflection(ConstrainedEnums, BaseModel):
    ALLOWED: ClassVar[tuple[Verdict, ...]] = tuple(Verdict)

    critique: str = Field(
        min_length=40, description="What the evidence shows, its weaknesses, and what is still missing"
    )
    verdict: Verdict = Field(description="The one overall verdict on the subject that your critique supports")
    verdict_scores: list[VerdictScore] = Field(
        min_length=2, description="One probability per allowed verdict, for the subject as a whole"
    )
    answered_question_ids: list[str]
    dropped_question_ids: list[str] = Field(
        description="Questions that are unanswerable or no longer relevant"
    )
    follow_up_questions: list[str] = Field(
        max_length=3, description="New questions to resolve gaps/conflicts"
    )
    distrusted_memory_ids: list[str] = Field(
        description="IDs (e.g. M3) of recalled memories about another entity or contradicted by evidence"
    )
    decision: Decision

    @classmethod
    def for_kind(cls, kind: SubjectKind) -> type["Reflection"]:
        """A Reflection that only accepts the verdicts this subject kind allows."""
        return type(f"{kind.value.title()}Reflection", (cls,), {"ALLOWED": kind.allowed_verdicts})

    @classmethod
    def enum_choices(cls) -> dict[str, tuple[str, ...]]:
        return {Verdict.__name__: tuple(verdict.value for verdict in cls.ALLOWED)}

    @field_validator("verdict_scores")
    @classmethod
    def _each_verdict_scored_once(cls, scores: list[VerdictScore]) -> list[VerdictScore]:
        verdicts = [score.verdict for score in scores]
        if len(verdicts) != len(set(verdicts)):
            raise ValueError("each verdict may be scored only once")
        return scores

    @model_validator(mode="after")
    def _forms_a_belief(self) -> "Reflection":
        """Validated by the Belief rule itself, so a polarity slip or an off-vocabulary verdict is a schema
        error (and retried) rather than a crash later."""
        Belief.among(self.ALLOWED, self.scores, self.verdict)
        return self

    @property
    def scores(self) -> dict[Verdict, float]:
        return {score.verdict: score.probability for score in self.verdict_scores}

    def belief(self, case_file: CaseFile) -> Belief:
        return Belief.over(case_file.subject.kind, self.scores, self.verdict)

    def update_questions(self, case_file: CaseFile) -> list[Question]:
        for question_id in self.answered_question_ids:
            if case_file.has_question(question_id):
                case_file.question(question_id).answer()
        for question_id in self.dropped_question_ids:
            if case_file.has_question(question_id):
                case_file.question(question_id).drop()
        return [case_file.raise_question(text) for text in self.follow_up_questions if text.strip()]


class Reflector:
    """Steps back after each round: weighs the evidence, criticises it, and decides whether to go on."""

    PROMPT: ClassVar[str] = (
        "You are the reflective reviewer of an OSINT team. {today} Weigh the evidence by its weight (source "
        "reliability x strength) and independence, not by how often a claim is repeated; the evidence-weight "
        "posterior and the competing-hypotheses matrix below are computed from the evidence by code, and "
        "your "
        "probabilities will be pooled with that posterior. " + VERDICTS + " Give ONE overall verdict for the "
        "subject as a whole, never one per question; the questions are only how you got there. Be "
        "calibrated: "
        "probabilities should reflect how likely each verdict is correct. Check for premature conclusions: "
        "unresolved conflicts, a single publisher, an unconfirmed identity, a namesake, or stale "
        "information. "
        "Recalled memories come from earlier investigations and may be outdated or about a namesake: flag "
        "any "
        "that the evidence contradicts. "
        + UNTRUSTED
        + " Choose 'conclude' only if more research is unlikely "
        "to change the verdict. The controller will not close a case on TRUE, FALSE, MIXED or ADVERSE "
        "without "
        "two independent publishers pointing at it (and, for ADVERSE or FALSE, an official, major-news or "
        "reference source), nor on NO_ADVERSE without a confirmed identity and an adverse screen. {budget} "
        "Reply with JSON only."
    )

    def __init__(self, chat: NvidiaChat) -> None:
        self._chat = chat

    async def reflect(self, briefing: CaseBriefing, steps_left: int) -> Metered[Reflection]:
        budget = f"Research rounds left after this one: {steps_left}."
        case = briefing.case_file
        user = (
            f"{briefing.subject}\n\nQuestions:\n{briefing.questions}\n\nEvidence (newest first):\n"
            f"{briefing.evidence}\n\nConflicts:\n{briefing.conflicts}\n\nEvidence-weight posterior: "
            f"{briefing.posterior}\n\nCompeting hypotheses (+ consistent, - "
            f"inconsistent):\n{briefing.hypotheses}"
            f"\n\nYour earlier verdicts:\n{briefing.belief_history}\n\nRecalled long-term memories:\n"
            f"{briefing.memories}"
        )
        prompt = self.PROMPT.format(today=f"Today is {case.subject.as_of.isoformat()}.", budget=budget)
        return await self._chat.ask(prompt, user, Reflection.for_kind(case.subject.kind))
