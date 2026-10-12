from collections import Counter, defaultdict
from collections.abc import Callable
from statistics import fmean
from typing import ClassVar

from pydantic import BaseModel

from osint_harness.evaluation import stats
from osint_harness.evaluation.episode import CrashedEpisode, EpisodeResult, FailureMode, StepRecord
from osint_harness.evaluation.judge import MemoryLabel
from osint_harness.evaluation.stats import Comparison, Estimate
from osint_harness.investigation.case_file import MemoryMode
from osint_harness.investigation.verdict import SubjectKind, Verdict
from osint_harness.investigator import StopReason

type StepValue = Callable[[StepRecord], float]
type EpisodeValue = Callable[[EpisodeResult], float]


class Calibration(BaseModel):
    """How well one confidence signal predicts correctness: lower is better for all three."""

    brier: float
    ece: float
    aurc: float


class ModeSummary(BaseModel):
    """Aggregates over completed episodes only; crashed cases are counted in `crashed`, never averaged.
    Every rate that can be is an Estimate: mean with a 95% bootstrap interval over cases and seeds."""

    mode: MemoryMode
    episodes: int
    cases: int
    seeds: int
    crashed: int
    accuracy: Estimate
    accuracy_by_kind: dict[SubjectKind, float]
    accuracy_by_slice: dict[str, Estimate]
    verdict_stability: float
    scope_accuracy: float | None
    episode_reward: Estimate
    step_reward: float
    process_reward: float
    process_reward_auroc: float
    step_reward_by_step: list[float]
    p_correct_by_step: list[float]
    brier_by_round_multi_round: list[float]
    shipped: Calibration
    llm_verbalised: Calibration
    evidence_posterior: Calibration
    key_fact_recall: Estimate
    citation_precision: Estimate
    steps: float
    multi_round_share: float
    steps_to_stable: float
    verdict_flips: float
    concluded_rate: float
    tool_calls: float
    tool_failure_rate: float
    retried_episodes: int
    rejected_repeats: float
    critic_checks: float
    adverse_citing_primary_record: float | None
    tokens: Estimate
    cost_usd_total: float
    wall_clock_s: float
    call_latency_s: float
    reward_per_10k_tokens: float
    memories_per_episode: float
    memory_relevant_rate: float
    memory_irrelevant_rate: float
    memory_misleading_rate: float
    misleading_memories_trusted: int
    memories_distrusted: int
    failure_modes: dict[FailureMode, int]
    episode_reward_in_order: list[float]


class MemoryImpact(BaseModel):
    """Paired deltas on the same cases. None means the two modes were not both run, not "no effect"."""

    short_vs_none_accuracy: float | None
    long_vs_short_accuracy: float | None
    long_vs_short_reward: float | None
    long_vs_short_tokens: float | None
    long_vs_short_steps: float | None
    long_vs_short_accuracy_when_memory_relevant: float | None
    cases_with_relevant_memory: int
    long_improved_cases: list[str]
    long_worsened_cases: list[str]


class Scoreboard:
    BASELINE: ClassVar[MemoryMode] = MemoryMode.CLOSED_BOOK
    PAIRS: ClassVar[tuple[tuple[MemoryMode, MemoryMode], ...]] = (
        (MemoryMode.SHORT, MemoryMode.NONE),
        (MemoryMode.LONG, MemoryMode.SHORT),
        (MemoryMode.LONG_ONLY, MemoryMode.NONE),
        (MemoryMode.LONG, MemoryMode.LONG_ONLY),
    )

    def __init__(self, results: list[EpisodeResult], crashes: list[CrashedEpisode]) -> None:
        self._results = results
        self._crashes = crashes

    def by_mode(self, mode: MemoryMode) -> list[EpisodeResult]:
        return [r for r in self._results if r.mode is mode]

    @property
    def modes(self) -> list[MemoryMode]:
        return [mode for mode in MemoryMode if self.by_mode(mode)]

    @staticmethod
    def per_case(runs: list[EpisodeResult], value: EpisodeValue) -> dict[str, list[float]]:
        grouped: dict[str, list[float]] = defaultdict(list)
        for r in runs:
            grouped[r.case_id].append(value(r))
        return dict(grouped)

    def estimate(self, runs: list[EpisodeResult], value: EpisodeValue) -> Estimate:
        return stats.bootstrap(list(self.per_case(runs, value).values()))

    def summary(self, mode: MemoryMode) -> ModeSummary:
        runs = self.by_mode(mode)
        memories = [label for r in runs for label in r.memory_labels.values()]
        retrieved = len(memories) or 1
        tokens = [r.prompt_tokens + r.completion_tokens for r in runs]
        correct = [r.correct for r in runs]
        slices = sorted({s for r in runs for s in r.slices})
        adverse = [r for r in runs if r.verdict is Verdict.ADVERSE]
        scoped = [r.scope.correct for r in runs if r.scope is not None]
        steps = [s for r in runs for s in r.steps]
        return ModeSummary(
            mode=mode,
            episodes=len(runs),
            cases=len({r.case_id for r in runs}),
            seeds=len({r.seed for r in runs}),
            crashed=sum(1 for crash in self._crashes if crash.mode is mode),
            accuracy=self.estimate(runs, self._correctness),
            accuracy_by_kind={
                kind: fmean(r.correct for r in runs if r.kind is kind)
                for kind in SubjectKind
                if any(r.kind is kind for r in runs)
            },
            accuracy_by_slice={
                name: self.estimate([r for r in runs if name in r.slices], self._correctness)
                for name in slices
            },
            verdict_stability=stats.stability(
                {case: [v for v in verdicts] for case, verdicts in self._verdicts(runs).items()}
            ),
            scope_accuracy=fmean(scoped) if scoped else None,
            episode_reward=self.estimate(runs, lambda r: r.episode_reward.total),
            step_reward=self._mean([s.reward.total for s in steps]),
            process_reward=self._mean([s.reward.process for s in steps]),
            process_reward_auroc=stats.auroc(
                [self._mean([s.reward.process for s in r.steps]) for r in runs], correct
            ),
            step_reward_by_step=self._increments_by_step(runs, lambda record: record.reward.total),
            p_correct_by_step=self._levels_by_step(runs, lambda record: record.p_correct),
            brier_by_round_multi_round=self._brier_by_round([r for r in runs if len(r.steps) > 1]),
            shipped=self._calibration([r.confidence for r in runs], correct),
            llm_verbalised=self._calibration([r.llm_confidence for r in runs], correct),
            evidence_posterior=self._calibration([r.posterior_confidence for r in runs], correct),
            key_fact_recall=self.estimate(runs, lambda r: r.key_fact_recall),
            citation_precision=self.estimate(runs, lambda r: r.citation_precision),
            steps=fmean(len(r.steps) for r in runs),
            multi_round_share=fmean(len(r.steps) > 1 for r in runs),
            steps_to_stable=fmean(r.steps_to_stable for r in runs),
            verdict_flips=fmean(r.verdict_flips for r in runs),
            concluded_rate=fmean(r.stop_reason is StopReason.CONCLUDED for r in runs),
            tool_calls=fmean(r.tool_calls for r in runs),
            tool_failure_rate=sum(r.tool_failures for r in runs) / (sum(r.tool_calls for r in runs) or 1),
            retried_episodes=sum(1 for r in runs if r.attempts > 1),
            rejected_repeats=fmean(r.rejected_repeats for r in runs),
            critic_checks=fmean(r.critic_checks for r in runs),
            adverse_citing_primary_record=fmean(r.primary_record_cited for r in adverse) if adverse else None,
            tokens=self.estimate(runs, lambda r: float(r.prompt_tokens + r.completion_tokens)),
            cost_usd_total=sum(r.cost_usd for r in runs),
            wall_clock_s=fmean(r.wall_clock_s for r in runs),
            call_latency_s=fmean(r.call_latency_s for r in runs),
            reward_per_10k_tokens=sum(r.episode_reward.total for r in runs) / (sum(tokens) / 10_000 or 1),
            memories_per_episode=fmean(r.memories_retrieved for r in runs),
            memory_relevant_rate=memories.count(MemoryLabel.RELEVANT) / retrieved,
            memory_irrelevant_rate=memories.count(MemoryLabel.IRRELEVANT) / retrieved,
            memory_misleading_rate=memories.count(MemoryLabel.MISLEADING) / retrieved,
            misleading_memories_trusted=sum(r.misleading_memories_trusted for r in runs),
            memories_distrusted=sum(len(r.memories_distrusted) for r in runs),
            failure_modes=dict(Counter(mode for r in runs for mode in r.failure_modes)),
            episode_reward_in_order=[r.episode_reward.total for r in runs],
        )

    def comparisons(self) -> list[Comparison]:
        """Every investigating mode against the closed-book floor, then the memory ablations pairwise."""
        present = set(self.modes)
        pairs = [(mode, self.BASELINE) for mode in self.modes if mode is not self.BASELINE]
        pairs += [pair for pair in self.PAIRS if set(pair) <= present]
        if self.BASELINE not in present:
            pairs = [pair for pair in pairs if pair[1] is not self.BASELINE]
        return [
            stats.compare(
                treated.value,
                baseline.value,
                self.per_case(self.by_mode(treated), self._correctness),
                self.per_case(self.by_mode(baseline), self._correctness),
            )
            for treated, baseline in pairs
        ]

    def memory_impact(self) -> MemoryImpact:
        none, short, long = (
            {r.case_id: r for r in self.by_mode(m) if r.seed == self._first_seed(m)}
            for m in (MemoryMode.NONE, MemoryMode.SHORT, MemoryMode.LONG)
        )
        paired = sorted(set(long) & set(short))
        relevant = [c for c in paired if MemoryLabel.RELEVANT in long[c].memory_labels.values()]
        return MemoryImpact(
            short_vs_none_accuracy=self._paired(
                sorted(set(short) & set(none)), short, none, self._correctness
            ),
            long_vs_short_accuracy=self._paired(paired, long, short, self._correctness),
            long_vs_short_reward=self._paired(paired, long, short, lambda r: r.episode_reward.total),
            long_vs_short_tokens=self._paired(
                paired, long, short, lambda r: r.prompt_tokens + r.completion_tokens
            ),
            long_vs_short_steps=self._paired(paired, long, short, lambda r: len(r.steps)),
            long_vs_short_accuracy_when_memory_relevant=self._paired(
                relevant, long, short, self._correctness
            ),
            cases_with_relevant_memory=len(relevant),
            long_improved_cases=[c for c in paired if long[c].correct and not short[c].correct],
            long_worsened_cases=[c for c in paired if short[c].correct and not long[c].correct],
        )

    def _first_seed(self, mode: MemoryMode) -> int:
        return min((r.seed for r in self.by_mode(mode)), default=0)

    @staticmethod
    def _verdicts(runs: list[EpisodeResult]) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = defaultdict(list)
        for r in runs:
            grouped[r.case_id].append(r.verdict.value)
        return grouped

    @staticmethod
    def _calibration(confidences: list[float], correct: list[bool]) -> Calibration:
        return Calibration(
            brier=stats.brier(confidences, correct),
            ece=stats.ece(confidences, correct, bins=min(10, max(1, len(confidences) // 3))),
            aurc=stats.risk_coverage(confidences, correct).aurc,
        )

    @staticmethod
    def _correctness(result: EpisodeResult) -> float:
        return float(result.correct)

    @staticmethod
    def _paired(
        cases: list[str],
        treated: dict[str, EpisodeResult],
        baseline: dict[str, EpisodeResult],
        value: EpisodeValue,
    ) -> float | None:
        if not cases:
            return None
        return fmean(value(treated[c]) - value(baseline[c]) for c in cases)

    @staticmethod
    def _mean(values: list[float]) -> float:
        return fmean(values) if values else 0.0

    def _increments_by_step(self, runs: list[EpisodeResult], value: StepValue) -> list[float]:
        """A per-round quantity (a reward) is 0 in rounds an episode never ran: nothing happened there."""
        depth = max((len(r.steps) for r in runs), default=0)
        return [fmean(value(r.steps[i]) if i < len(r.steps) else 0.0 for r in runs) for i in range(depth)]

    def _levels_by_step(self, runs: list[EpisodeResult], value: StepValue) -> list[float]:
        """A level (a belief) carries forward: an episode that concluded early keeps its last value,
        so later rounds are not an average over only the hard cases still running."""
        depth = max((len(r.steps) for r in runs), default=0)
        return [fmean(value(r.steps[min(i, len(r.steps) - 1)]) for r in runs) for i in range(depth)]

    @staticmethod
    def _brier_by_round(runs: list[EpisodeResult]) -> list[float]:
        """Squared distance of the shipped belief from the truth, (1 - p(acceptable verdict))^2, per round,
        over multi-round episodes only (no single-round floor), carrying the last belief forward."""
        depth = max((len(r.steps) for r in runs), default=0)
        return [
            fmean((1 - r.steps[min(i, len(r.steps) - 1)].p_correct) ** 2 for r in runs) for i in range(depth)
        ]
