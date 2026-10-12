from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel

from osint_harness.evaluation.benchmark import BenchmarkCase, ScopeGrade, Split
from osint_harness.evaluation.judge import Grading, MemoryLabel
from osint_harness.evaluation.rewards import EpisodeReward, StepReward
from osint_harness.investigation.case_file import CaseFile, MemoryMode
from osint_harness.investigation.confidence import ConfidenceInputs
from osint_harness.investigation.evidence import Stance
from osint_harness.investigation.inquiry import InquiryOutcome
from osint_harness.investigation.source import SourceTier
from osint_harness.investigation.verdict import Belief, SubjectKind, Verdict
from osint_harness.investigator import Investigation, StopReason
from osint_harness.settings import TokenPrice
from osint_harness.trace import TraceEvent, TraceEventKind


class FailureMode(StrEnum):
    """Descriptive tags, each with a threshold that does not fire on most answers by construction. Causes
    are established by counterfactual replay (evaluation/counterfactual.py), not by these tags."""

    SCOPE_ERROR = "scope_error"
    MEMORY_INTERFERENCE = "memory_interference"
    NO_AUTHORITATIVE_SOURCE = "no_authoritative_source"
    WEAK_EVIDENCE = "weak_evidence"
    UNRESOLVED_CONFLICT = "unresolved_conflict"
    BUDGET_EXHAUSTED = "budget_exhausted"
    TOOL_FAILURES = "tool_failures"
    UNBACKED_CONFIDENCE = "unbacked_confidence"
    MISREASONED = "misreasoned"
    RIGHT_FOR_WRONG_REASON = "right_for_wrong_reason"
    INCOMPLETE_FINDINGS = "incomplete_findings"


class StepRecord(BaseModel):
    step: int
    verdict: Verdict
    confidence: float
    p_correct: float
    llm_p_correct: float
    posterior_p_correct: float
    reward: StepReward


class EpisodeDiagnosis(BaseModel):
    """What an episode's numbers mean: how it converged and, if it went wrong, what it looked like."""

    case_id: str
    mode: MemoryMode
    seed: int
    correct: bool
    verdict_flips: int
    steps_to_stable: int
    misleading_memories_trusted: int
    failure_modes: list[FailureMode]


class CrashedEpisode(BaseModel):
    """A case whose investigation failed after retries: counted on its own, never averaged into quality."""

    case_id: str
    mode: MemoryMode
    kind: SubjectKind
    error: str
    seed: int = 0


class EpisodeResult(BaseModel):
    """One completed investigation graded against ground truth, from its Steps and Evidence."""

    case_id: str
    mode: MemoryMode
    seed: int = 0
    split: Split = Split.TEST
    slices: list[str] = []
    kind: SubjectKind
    tags: list[str]
    expected: Verdict
    verdict: Verdict
    correct: bool
    confidence: float
    llm_confidence: float = 0.0
    posterior_confidence: float = 0.0
    confidence_inputs: dict[str, float] = {}
    scope: ScopeGrade | None = None
    stop_reason: StopReason
    max_steps: int
    steps: list[StepRecord]
    tool_calls: int
    tool_failures: int
    rejected_repeats: int = 0
    critic_checks: int = 0
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    wall_clock_s: float
    call_latency_s: float
    key_fact_recall: float
    citation_precision: float
    findings: int
    conflicts_final: int
    independent_domains: int
    evidence_weight: float
    supporting_weight: float = 0.0
    mean_evidence_reliability: float
    authoritative_evidence: bool
    primary_record_cited: bool = False
    withdrawn_statements: int = 0
    manipulation_flags: int = 0
    memories_retrieved: int
    memory_labels: dict[str, MemoryLabel]
    memories_distrusted: list[str]
    judge_model: str = ""
    attempts: int = 1
    episode_reward: EpisodeReward

    STABLE_CONFIDENCE_BAND: ClassVar[float] = 0.1
    CLOSING_EVENTS: ClassVar[frozenset[TraceEventKind]] = frozenset(
        {TraceEventKind.REPORTED, TraceEventKind.MEMORY_WRITTEN}
    )

    @classmethod
    def grade(
        cls,
        case: BenchmarkCase,
        investigation: Investigation,
        grading: Grading,
        max_steps: int,
        price: TokenPrice,
        seed: int = 0,
        scope: ScopeGrade | None = None,
        judge_model: str = "",
        attempts: int = 1,
    ) -> "EpisodeResult":
        report = investigation.report
        case_file = investigation.case_file
        correct = case.accepts(report.verdict)
        usage = investigation.usage
        decisive = [item for item in case_file.external_evidence if item.stance is not Stance.CONTEXT]
        memory_ids = [r.label for r in investigation.recollections]
        last = case_file.steps[-1]
        inputs = last.inputs
        supporters = case_file.supporters_of(report.verdict)
        return cls(
            case_id=case.id,
            mode=investigation.mode,
            seed=seed,
            split=case.split,
            slices=case.slices,
            kind=case.kind,
            tags=case.tags,
            expected=case.expected_verdict,
            verdict=report.verdict,
            correct=correct,
            confidence=report.confidence,
            llm_confidence=(last.llm_belief or last.belief).probability_of(report.verdict),
            posterior_confidence=last.posterior.probability_of(report.verdict) if last.posterior else 0.0,
            confidence_inputs=cls._inputs(inputs),
            scope=scope,
            stop_reason=investigation.stop_reason,
            max_steps=max_steps,
            steps=cls._step_records(case, case_file, investigation.trace.events),
            tool_calls=investigation.tool_calls,
            tool_failures=sum(
                1 for inquiry in case_file.inquiries if inquiry.outcome is InquiryOutcome.FAILED
            ),
            rejected_repeats=investigation.rejected_repeats,
            critic_checks=investigation.critic_checks,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            cost_usd=usage.cost_usd(price),
            wall_clock_s=investigation.wall_clock_s,
            call_latency_s=investigation.call_latency_s,
            key_fact_recall=grading.key_fact_recall,
            citation_precision=grading.citation_precision,
            findings=len(report.findings),
            conflicts_final=len(case_file.conflicts),
            independent_domains=len(case_file.independent_domains),
            evidence_weight=sum(item.weight for item in decisive),
            supporting_weight=sum(item.weight for item in supporters.values()),
            mean_evidence_reliability=(
                sum(item.reliability for item in decisive) / len(decisive) if decisive else 0.0
            ),
            authoritative_evidence=any(
                case_file.sources[item.source_url].tier.is_authoritative for item in decisive
            ),
            primary_record_cited=any(cited.source.tier is SourceTier.OFFICIAL for cited in report.sources),
            withdrawn_statements=len(report.withdrawn),
            manipulation_flags=len(report.manipulation_flags),
            memories_retrieved=len(memory_ids),
            memory_labels=grading.memory_labels(memory_ids),
            memories_distrusted=sorted(investigation.distrusted_memory_ids),
            judge_model=judge_model,
            attempts=attempts,
            episode_reward=EpisodeReward.measure(
                correct, report.confidence, grading.key_fact_recall, grading.citation_precision, usage.total
            ),
        )

    @staticmethod
    def _inputs(inputs: ConfidenceInputs | None) -> dict[str, float]:
        if inputs is None:
            return {}
        return {
            "llm_probability": inputs.llm_probability,
            "posterior_probability": inputs.posterior_probability,
            "independent_supporters": float(inputs.independent_supporters),
            "authoritative_support": float(inputs.authoritative_support),
        }

    @property
    def calibration_inputs(self) -> ConfidenceInputs | None:
        values = self.confidence_inputs
        if not values:
            return None
        return ConfidenceInputs(
            values["llm_probability"],
            values["posterior_probability"],
            int(values["independent_supporters"]),
            bool(values["authoritative_support"]),
        )

    @classmethod
    def _step_records(
        cls, case: BenchmarkCase, case_file: CaseFile, events: list[TraceEvent]
    ) -> list[StepRecord]:
        def p_correct(belief: Belief | None) -> float:
            return sum(belief.probability_of(v) for v in case.acceptable_verdicts) if belief else 0.0

        p_before = len(case.acceptable_verdicts) / len(case.kind.allowed_verdicts)
        uploads = case_file.evidence_of_step(CaseFile.UPLOAD_STEP)
        seen_domains = {item.domain for item in uploads if item.stance is not Stance.CONTEXT}
        seen_urls = {item.source_url for item in uploads}
        records: list[StepRecord] = []
        for step in case_file.steps:
            items = [e for e in case_file.evidence_of_step(step.number) if e.stance is not Stance.CONTEXT]
            new_domains = {item.domain for item in items} - seen_domains
            seen_domains |= new_domains
            returned = [source.url for inquiry in step.inquiries for source in inquiry.sources]
            first_seen = set(returned) - seen_urls
            seen_urls |= first_seen
            p_after = p_correct(step.belief)
            posterior = step.posterior
            reward = StepReward.measure(
                step=step.number,
                p_correct_before=p_before,
                p_correct_after=p_after,
                new_evidence_weight=sum(item.weight for item in items),
                new_domains=len(new_domains),
                returned=len(returned),
                duplicates=len(returned) - len(first_seen),
                tool_calls=len(step.inquiries),
                tool_failures=sum(1 for i in step.inquiries if i.outcome is InquiryOutcome.FAILED),
                tokens=sum(
                    event.usage.total
                    for event in events
                    if event.step == step.number and event.kind not in cls.CLOSING_EVENTS
                ),
            )
            records.append(
                StepRecord(
                    step=step.number,
                    verdict=step.belief.verdict,
                    confidence=step.belief.confidence,
                    p_correct=p_after,
                    llm_p_correct=p_correct(step.llm_belief),
                    posterior_p_correct=(
                        sum(posterior.probability_of(v) for v in case.acceptable_verdicts)
                        if posterior
                        else 0.0
                    ),
                    reward=reward,
                )
            )
            p_before = p_after
        return records

    @property
    def diagnosis(self) -> EpisodeDiagnosis:
        return EpisodeDiagnosis(
            case_id=self.case_id,
            mode=self.mode,
            seed=self.seed,
            correct=self.correct,
            verdict_flips=self.verdict_flips,
            steps_to_stable=self.steps_to_stable,
            misleading_memories_trusted=self.misleading_memories_trusted,
            failure_modes=self.failure_modes,
        )

    @property
    def verdict_flips(self) -> int:
        return sum(1 for a, b in zip(self.steps, self.steps[1:], strict=False) if a.verdict is not b.verdict)

    @property
    def steps_to_stable(self) -> int:
        """First step after which the verdict never changes and confidence stays within 0.1 of final."""
        final = self.steps[-1]
        stable_from = final.step
        for record in reversed(self.steps):
            if (
                record.verdict is not final.verdict
                or abs(record.confidence - final.confidence) > self.STABLE_CONFIDENCE_BAND
            ):
                break
            stable_from = record.step
        return stable_from

    @property
    def misleading_memories_trusted(self) -> int:
        return sum(
            1
            for memory_id, label in self.memory_labels.items()
            if label is MemoryLabel.MISLEADING and memory_id not in self.memories_distrusted
        )

    WEAK_SUPPORT: ClassVar[float] = 1.0

    @property
    def failure_modes(self) -> list[FailureMode]:
        if self.mode is MemoryMode.CLOSED_BOOK:
            return [] if self.correct else [FailureMode.MISREASONED]
        scope_error = self.scope is not None and not self.scope.correct
        if self.correct:
            return [
                mode
                for mode, applies in [
                    (FailureMode.SCOPE_ERROR, scope_error),
                    (
                        FailureMode.RIGHT_FOR_WRONG_REASON,
                        self.verdict is not Verdict.UNVERIFIABLE
                        and self.supporting_weight < self.WEAK_SUPPORT,
                    ),
                    (FailureMode.INCOMPLETE_FINDINGS, self.key_fact_recall < 0.5),
                ]
                if applies
            ]
        causes = [
            mode
            for mode, applies in [
                (FailureMode.SCOPE_ERROR, scope_error),
                (FailureMode.MEMORY_INTERFERENCE, self.misleading_memories_trusted > 0),
                (FailureMode.NO_AUTHORITATIVE_SOURCE, not self.authoritative_evidence),
                (FailureMode.WEAK_EVIDENCE, self.supporting_weight < self.WEAK_SUPPORT),
                (FailureMode.UNRESOLVED_CONFLICT, self.conflicts_final > 0),
                (
                    FailureMode.BUDGET_EXHAUSTED,
                    self.stop_reason in (StopReason.TOOL_BUDGET, StopReason.STEP_BUDGET),
                ),
                (
                    FailureMode.TOOL_FAILURES,
                    self.tool_calls > 0 and self.tool_failures / self.tool_calls > 0.3,
                ),
                (
                    FailureMode.UNBACKED_CONFIDENCE,
                    self.confidence >= 0.8 and self.posterior_confidence < 0.5,
                ),
            ]
            if applies
        ]
        return causes or [FailureMode.MISREASONED]
