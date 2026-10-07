from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from typing import ClassVar

from osint_harness.investigation.evidence import Evidence, Stance
from osint_harness.investigation.independence import PublisherClusters, QueryLedger
from osint_harness.investigation.inquiry import Inquiry, Step
from osint_harness.investigation.posterior import EvidencePosterior
from osint_harness.investigation.question import Question, QuestionRole
from osint_harness.investigation.source import PublisherOutcome, ResolvedBy, Source
from osint_harness.investigation.subject import Subject
from osint_harness.investigation.verdict import Belief, Verdict


class MemoryMode(StrEnum):
    """What an investigation may remember, from nothing at all to everything.

    closed_book  no tools and no memory: the model answers from what it already knows (the floor)
    none         tools, but each round sees only its own findings; the stopping gate sees the same window
    short        tools plus the whole case file of this investigation
    long         short, plus what earlier investigations taught (long-term memory)
    long_only    long-term memory, but each round sees only its own findings, as in none
    """

    CLOSED_BOOK = "closed_book"
    NONE = "none"
    SHORT = "short"
    LONG = "long"
    LONG_ONLY = "long_only"

    @property
    def investigates(self) -> bool:
        return self is not MemoryMode.CLOSED_BOOK

    @property
    def uses_long_term(self) -> bool:
        return self in (MemoryMode.LONG, MemoryMode.LONG_ONLY)

    def visible_from(self, step: int) -> int:
        """First step whose findings the agent, and the stopping gate, can still see."""
        return step if self in (MemoryMode.NONE, MemoryMode.LONG_ONLY) else 0


@dataclass(frozen=True)
class EvidenceBalance:
    """Independent weight for and against one question: each publisher cluster counts once, on one side.
    A publisher on both sides counts on its heavier side; one that weighs both sides equally counts on
    neither, since it corroborates nothing."""

    supporting: dict[str, float]
    refuting: dict[str, float]

    @classmethod
    def of(
        cls,
        evidence: list[Evidence],
        publisher: "PublisherKey",
        weigh: Callable[[Evidence], float] = lambda item: item.weight,
    ) -> "EvidenceBalance":
        sides: dict[Stance, dict[str, float]] = {Stance.SUPPORTS: {}, Stance.REFUTES: {}}
        for item in evidence:
            if item.stance in sides:
                side = sides[item.stance]
                key = publisher(item)
                side[key] = max(side.get(key, 0.0), weigh(item))
        support, refute = sides[Stance.SUPPORTS], sides[Stance.REFUTES]
        return cls(
            supporting={d: w for d, w in support.items() if w > refute.get(d, 0.0)},
            refuting={d: w for d, w in refute.items() if w > support.get(d, 0.0)},
        )

    @property
    def support_weight(self) -> float:
        return sum(self.supporting.values())

    @property
    def refute_weight(self) -> float:
        return sum(self.refuting.values())

    @property
    def winners(self) -> dict[str, float]:
        """The heavier side's publishers; nobody wins a tie."""
        if self.support_weight > self.refute_weight:
            return self.supporting
        if self.refute_weight > self.support_weight:
            return self.refuting
        return {}


class PublisherKey:
    """Maps an evidence item to the publisher cluster that independently stands behind it."""

    def __init__(self, clusters: PublisherClusters) -> None:
        self._clusters = clusters

    def __call__(self, item: Evidence) -> str:
        return self._clusters.of(item.source_url, item.domain)


@dataclass(frozen=True)
class Conflict:
    question: Question
    balance: EvidenceBalance


@dataclass
class CaseFile:
    """Everything gathered about one subject during one investigation: the short-term memory.

    Every controller computation (conflicts, the stopping gate, the posterior) takes a `from_step` window, so
    a memory mode that hides earlier rounds from the agents hides them from the controller too.
    """

    subject: Subject
    questions: list[Question] = field(default_factory=list)
    sources: dict[str, Source] = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    _clusters: PublisherClusters | None = None
    UPLOAD_STEP: ClassVar[int] = 0
    CONFLICT_THRESHOLD: ClassVar[float] = 0.5
    SETTLED_MARGIN: ClassVar[float] = 2.0
    CONCLUSIVE_CONFIDENCE: ClassVar[float] = 0.8
    MIN_INDEPENDENT_PUBLISHERS: ClassVar[int] = 2
    SETTLING_WEIGHT: ClassVar[float] = 1.0
    MATERIAL_ADVERSE_WEIGHT: ClassVar[float] = 0.5
    ROUNDS_BEFORE_UNVERIFIABLE: ClassVar[int] = 2
    STALE_HORIZON: ClassVar[timedelta] = timedelta(days=365)
    STALE_DISCOUNT: ClassVar[float] = 0.5

    def raise_question(self, text: str, role: QuestionRole = QuestionRole.VERDICT_DECIDING) -> Question:
        question = Question(id=f"Q{len(self.questions) + 1}", text=text, role=role)
        self.questions.append(question)
        return question

    def question(self, question_id: str) -> Question:
        return next(q for q in self.questions if q.id == question_id)

    def has_question(self, question_id: str) -> bool:
        return any(q.id == question_id for q in self.questions)

    def file_source(self, source: Source) -> bool:
        if source.url in self.sources:
            return False
        self.sources[source.url] = source
        self._clusters = None
        return True

    def record_evidence(self, item: Evidence) -> None:
        self.evidence.append(item)

    def record_step(self, step: Step) -> None:
        self.steps.append(step)

    @property
    def tool_calls(self) -> int:
        return sum(len(step.inquiries) for step in self.steps)

    @property
    def beliefs(self) -> list[Belief]:
        return [step.belief for step in self.steps]

    @property
    def inquiries(self) -> list[Inquiry]:
        return self.inquiries_from_step(0)

    def inquiries_from_step(self, step: int) -> list[Inquiry]:
        return [inquiry for s in self.steps if s.number >= step for inquiry in s.inquiries]

    def evidence_of_step(self, step: int) -> list[Evidence]:
        return [item for item in self.evidence if item.step == step]

    def evidence_from_step(self, step: int) -> list[Evidence]:
        """Evidence from that step on, plus the analyst's own documents, which are part of the subject."""
        return [item for item in self.evidence if item.step >= step or item.step == self.UPLOAD_STEP]

    def external_evidence_from(self, step: int = 0) -> list[Evidence]:
        """What independent publishers said: the analyst's uploads are what is being checked, never proof."""
        return [item for item in self.evidence if item.step >= step and item.step != self.UPLOAD_STEP]

    @property
    def external_evidence(self) -> list[Evidence]:
        return self.external_evidence_from(0)

    @property
    def publisher(self) -> PublisherKey:
        if self._clusters is None:
            self._clusters = PublisherClusters(list(self.sources.values()))
        return PublisherKey(self._clusters)

    @property
    def ledger(self) -> QueryLedger:
        return QueryLedger(self.inquiries)

    def is_stale(self, item: Evidence) -> bool:
        """On a claim about the present, dated evidence is stale once newer dated evidence on the same
        question is more than a year younger: the latest authoritative report describes the present."""
        if not (self.subject.is_state_claim and item.published):
            return False
        newer = [
            other.published
            for other in self.external_evidence
            if other.question_id == item.question_id and other.published is not None
        ]
        return bool(newer) and max(newer) - item.published > self.STALE_HORIZON

    def weigh(self, item: Evidence) -> float:
        return item.weight * (self.STALE_DISCOUNT if self.is_stale(item) else 1.0)

    def balance(self, question_id: str, from_step: int = 0) -> EvidenceBalance:
        return EvidenceBalance.of(
            [item for item in self.external_evidence_from(from_step) if item.question_id == question_id],
            self.publisher,
            self.weigh,
        )

    def posterior(self, from_step: int = 0) -> EvidencePosterior:
        identity: dict[str, float] = {}
        for key, weight in self._identity_weights(from_step):
            identity[key] = max(identity.get(key, 0.0), weight)
        return EvidencePosterior.of(
            self.subject.kind.allowed_verdicts,
            self.external_evidence_from(from_step),
            self.publisher,
            self.weigh,
            identity.values(),
            self.screening(from_step),
        )

    def screening(self, from_step: int = 0) -> float:
        """How thoroughly an adverse screen looked and came back clean: 0.5 per search on a verdict-deciding
        question that returned sources, up to 1, and 0 once any material adverse item is on file."""
        if self._material_adverse(from_step):
            return 0.0
        verdict_questions = {q.id for q in self.questions if q.role is QuestionRole.VERDICT_DECIDING}
        looked = [
            i for i in self.inquiries_from_step(from_step) if i.question_id in verdict_questions and i.sources
        ]
        return min(1.0, 0.5 * len(looked))

    def _material_adverse(self, from_step: int) -> bool:
        adverse = self.supporters_of(Verdict.ADVERSE, from_step)
        return any(self.weigh(item) >= self.MATERIAL_ADVERSE_WEIGHT for item in adverse.values())

    @property
    def conflicts(self) -> list[Conflict]:
        return self.conflicts_among(self.evidence)

    def conflicts_from(self, step: int) -> list[Conflict]:
        return self.conflicts_among(self.evidence_from_step(step))

    def conflicts_among(self, evidence: list[Evidence]) -> list[Conflict]:
        """Questions where independent support and refutation are both weighty and neither outweighs 2:1."""
        by_question: dict[str, list[Evidence]] = defaultdict(list)
        for item in evidence:
            if item.step != self.UPLOAD_STEP:
                by_question[item.question_id].append(item)
        found: list[Conflict] = []
        for question_id, items in by_question.items():
            balance = EvidenceBalance.of(items, self.publisher, self.weigh)
            weaker, stronger = sorted((balance.support_weight, balance.refute_weight))
            if weaker >= self.CONFLICT_THRESHOLD and stronger < self.SETTLED_MARGIN * weaker:
                found.append(Conflict(self.question(question_id), balance))
        return found

    def supporters_of(self, verdict: Verdict, from_step: int = 0) -> dict[str, Evidence]:
        """The heaviest item per independent publisher pointing at a verdict, on verdict questions only."""
        identity = {q.id for q in self.questions if q.role is QuestionRole.IDENTITY}
        best: dict[str, Evidence] = {}
        for item in self.external_evidence_from(from_step):
            if item.direction is verdict and item.question_id not in identity:
                key = self.publisher(item)
                if key not in best or self.weigh(item) > self.weigh(best[key]):
                    best[key] = item
        return best

    def support(self, verdict: Verdict, from_step: int = 0) -> tuple[int, bool]:
        """How many independent publishers point at a verdict, and whether one of them is authoritative."""
        supporters = self.supporters_of(verdict, from_step).values()
        return len(supporters), any(self.sources[i.source_url].tier.is_authoritative for i in supporters)

    def identity_confirmations(self, from_step: int = 0) -> set[str]:
        """Publishers confirming which entity this is; any supporting item counts if no question asks."""
        return {key for key, _ in self._identity_weights(from_step)}

    def _identity_weights(self, from_step: int) -> list[tuple[str, float]]:
        identity = {q.id for q in self.questions if q.role is QuestionRole.IDENTITY}
        return [
            (self.publisher(item), self.weigh(item))
            for item in self.external_evidence_from(from_step)
            if item.stance is Stance.SUPPORTS
            and (item.question_id in identity or (not identity and item.direction is None))
        ]

    def is_settled(self, belief: Belief, from_step: int = 0) -> bool:
        return not self.unmet_conditions(belief, from_step)

    def unmet_conditions(self, belief: Belief, from_step: int = 0) -> list[str]:
        """Why the case may not close yet on this belief, judged only on the evidence in the window.

        A verdict that asserts something (TRUE, FALSE, MIXED, ADVERSE) needs two independent publishers on
        verdict-deciding questions pointing at it with summed weight >= 1.0, and an ADVERSE or FALSE verdict
        also needs one authoritative source. NO_ADVERSE needs a confirmed identity, an adverse screen and no
        material adverse evidence. UNVERIFIABLE is a judgement about search effort, not a probability: two
        rounds that turned up nothing decisive.
        """
        unmet: list[str] = []
        verdict = belief.verdict
        if verdict is not Verdict.UNVERIFIABLE and belief.confidence < self.CONCLUSIVE_CONFIDENCE:
            unmet.append(f"confidence {belief.confidence:.0%} is below {self.CONCLUSIVE_CONFIDENCE:.0%}")
        if self.conflicts_from(from_step):
            unmet.append("an open conflict between independent publishers")
        if verdict is Verdict.NO_ADVERSE:
            unmet += self._unmet_for_clean_record(from_step)
        elif verdict is Verdict.UNVERIFIABLE:
            unmet += self._unmet_for_insufficiency(from_step)
        else:
            supporters = self.supporters_of(verdict, from_step)
            weight = sum(self.weigh(item) for item in supporters.values())
            if len(supporters) < self.MIN_INDEPENDENT_PUBLISHERS:
                unmet.append(f"{len(supporters)} independent publisher(s) point at {verdict.value}, need 2")
            if weight < self.SETTLING_WEIGHT:
                unmet.append(
                    f"evidence weight for {verdict.value} is {weight:.2f}, need {self.SETTLING_WEIGHT}"
                )
            if verdict in (Verdict.ADVERSE, Verdict.FALSE) and not any(
                self.sources[item.source_url].tier.is_authoritative for item in supporters.values()
            ):
                unmet.append(f"{verdict.value} rests on no official, major-news or reference source")
        return unmet

    def _unmet_for_clean_record(self, from_step: int) -> list[str]:
        unmet: list[str] = []
        if len(self.identity_confirmations(from_step)) < self.MIN_INDEPENDENT_PUBLISHERS:
            unmet.append("identity is not confirmed by 2 independent publishers")
        verdict_questions = {q.id for q in self.questions if q.role is QuestionRole.VERDICT_DECIDING}
        if not any(i.question_id in verdict_questions for i in self.inquiries_from_step(from_step)):
            unmet.append("no adverse-signal search has been run")
        if self._material_adverse(from_step):
            unmet.append("material adverse evidence is on file")
        return unmet

    def _unmet_for_insufficiency(self, from_step: int) -> list[str]:
        unmet: list[str] = []
        if len(self.steps) < self.ROUNDS_BEFORE_UNVERIFIABLE:
            unmet.append(f"UNVERIFIABLE needs {self.ROUNDS_BEFORE_UNVERIFIABLE} rounds of searching")
        for verdict in self.subject.kind.allowed_verdicts:
            if verdict is Verdict.UNVERIFIABLE:
                continue
            weight = sum(self.weigh(item) for item in self.supporters_of(verdict, from_step).values())
            if weight >= self.SETTLING_WEIGHT:
                unmet.append(f"evidence for {verdict.value} weighs {weight:.2f}: not insufficient")
        return unmet

    def minor_adverse_items(self) -> list[Evidence]:
        return [item for item in self.external_evidence if item.is_minor_adverse]

    def publisher_outcomes(self, truth: Verdict, resolved_by: ResolvedBy) -> list[PublisherOutcome]:
        """Which publishers pointed at the verdict ground truth confirmed. Only a resolved case teaches
        anything; a publisher that pointed both ways in one case is not scored on it."""
        if truth in (Verdict.MIXED, Verdict.UNVERIFIABLE):
            return []
        sides: dict[str, set[bool]] = defaultdict(set)
        for item in self.external_evidence:
            if item.direction is not None:
                sides[item.domain].add(item.direction is truth)
        return [
            PublisherOutcome(domain, agreed.pop(), resolved_by)
            for domain, agreed in sorted(sides.items())
            if len(agreed) == 1
        ]

    def independent_publishers(self, from_step: int = 0) -> set[str]:
        """Publisher clusters on the heavier side of some question, counted across questions."""
        balances = [self.balance(question.id, from_step) for question in self.questions]
        return {key for balance in balances for key in balance.winners}

    @property
    def independent_domains(self) -> set[str]:
        return self.independent_publishers(0)
