import asyncio
import random
from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel

from osint_harness.evaluation.benchmark import Benchmark, BenchmarkCase, ScopeGrade, Split
from osint_harness.evaluation.charts import BenchmarkCharts
from osint_harness.evaluation.episode import CrashedEpisode, EpisodeDiagnosis, EpisodeResult
from osint_harness.evaluation.judge import Judge
from osint_harness.evaluation.manifest import RunManifest
from osint_harness.evaluation.scoreboard import MemoryImpact, ModeSummary, Scoreboard
from osint_harness.evaluation.stats import Comparison
from osint_harness.harness import Harness
from osint_harness.investigation.case_file import MemoryMode
from osint_harness.investigation.source import ResolvedBy
from osint_harness.investigator import Budget, Investigates, Resolution
from osint_harness.nvidia import MalformedCompletion
from osint_harness.trace import TraceLog
from osint_harness.transport import ServiceRejected, ServiceUnavailable

type Episode = EpisodeResult | CrashedEpisode


@dataclass(frozen=True)
class RunPlan:
    """What one benchmark run covers: which modes and seeds, which split, and whether scoping is graded."""

    modes: tuple[MemoryMode, ...]
    seeds: tuple[int, ...] = (0,)
    split: Split | None = None
    pre_scoped: bool = False
    shuffle_long_order: bool = False
    force_new: bool = False


class BenchmarkSummary(BaseModel):
    cases: int
    seeds: list[int]
    split: str
    pre_scoped: bool
    judge_model: str
    budget: Budget
    modes: list[ModeSummary]
    comparisons: list[Comparison]
    memory_impact: MemoryImpact
    crashes: list[CrashedEpisode]
    diagnoses: list[EpisodeDiagnosis]

    def to_markdown(self) -> str:
        rows: list[tuple[str, Callable[[ModeSummary], str]]] = [
            ("Episodes (cases x seeds)", lambda m: f"{m.episodes} ({m.cases} x {m.seeds})"),
            ("Accuracy [95% CI]", lambda m: m.accuracy.percent()),
            ("Verdict stability across seeds", lambda m: self._pct(m.verdict_stability)),
            ("Scope accuracy", lambda m: self._pct(m.scope_accuracy)),
            ("Episode reward [95% CI]", lambda m: str(m.episode_reward)),
            ("Mean step reward", lambda m: f"{m.step_reward:.3f}"),
            ("Process reward (no ground truth)", lambda m: f"{m.process_reward:.3f}"),
            ("Process reward AUROC for correctness", lambda m: self._num(m.process_reward_auroc)),
            ("Brier: shipped / LLM / posterior", lambda m: self._triple(m, "brier")),
            ("ECE: shipped / LLM / posterior", lambda m: self._triple(m, "ece")),
            ("AURC: shipped / LLM / posterior", lambda m: self._triple(m, "aurc")),
            ("Key-fact recall [95% CI] (judge)", lambda m: m.key_fact_recall.percent()),
            ("Citation precision, atomic [95% CI] (judge)", lambda m: m.citation_precision.percent()),
            ("Research rounds", lambda m: f"{m.steps:.2f}"),
            ("Multi-round episodes", lambda m: f"{m.multi_round_share:.0%}"),
            ("Rounds to stable verdict", lambda m: f"{m.steps_to_stable:.2f}"),
            ("Verdict flips", lambda m: f"{m.verdict_flips:.2f}"),
            ("Concluded (vs budget stop)", lambda m: f"{m.concluded_rate:.0%}"),
            ("Tool calls", lambda m: f"{m.tool_calls:.1f}"),
            ("Repeat queries rejected", lambda m: f"{m.rejected_repeats:.2f}"),
            ("Red-team checks run", lambda m: f"{m.critic_checks:.2f}"),
            (
                "ADVERSE verdicts citing a primary record",
                lambda m: self._pct(m.adverse_citing_primary_record),
            ),
            ("Tool failure rate", lambda m: f"{m.tool_failure_rate:.1%}"),
            ("Episodes that needed a retry", lambda m: f"{m.retried_episodes}"),
            (
                "Tokens per episode [95% CI]",
                lambda m: f"{m.tokens.mean:,.0f} [{m.tokens.low:,.0f}, {m.tokens.high:,.0f}]",
            ),
            ("Est. cost, all episodes (USD, assumed prices)", lambda m: f"{m.cost_usd_total:.3f}"),
            ("Wall-clock time per episode (s)", lambda m: f"{m.wall_clock_s:.0f}"),
            ("Reward per 10k tokens", lambda m: f"{m.reward_per_10k_tokens:.3f}"),
            ("Memories recalled per episode", lambda m: f"{m.memories_per_episode:.2f}"),
            (
                "Recalled memories: relevant / irrelevant / misleading",
                lambda m: (
                    f"{m.memory_relevant_rate:.0%} / {m.memory_irrelevant_rate:.0%} / "
                    f"{m.memory_misleading_rate:.0%}"
                ),
            ),
            ("Misleading memories not flagged", lambda m: str(m.misleading_memories_trusted)),
            ("Crashed cases (excluded above)", lambda m: str(m.crashed)),
        ]
        lines = [
            f"Judge model: {self.judge_model}. Split: {self.split}. Seeds: {self.seeds}. "
            f"Scoping: "
            f"{'gold (pre-scoped ablation)' if self.pre_scoped else 'graded from raw analyst text'}.",
            "Judge-graded rows are low-validity until judge-human agreement (kappa) is measured "
            "(benchmark/judge_gold.json).",
            "",
            "| Metric | " + " | ".join(m.mode.value for m in self.modes) + " |",
            "|---|" + "---|" * len(self.modes),
        ]
        lines += [f"| {label} | " + " | ".join(cell(m) for m in self.modes) + " |" for label, cell in rows]
        lines += ["", "## Paired comparisons (accuracy)", ""]
        lines += [
            "| Treated vs baseline | Difference [95% CI] | Discordant (+/-) | McNemar p | Permutation p |"
        ]
        lines += ["|---|---|---|---|---|"]
        lines += [
            f"| {c.treated} vs {c.baseline} | {c.difference.mean:+.3f} [{c.difference.low:+.3f}, "
            f"{c.difference.high:+.3f}] | {c.discordant_treated_better}/{c.discordant_baseline_better} | "
            f"{c.mcnemar_p:.3f} | {c.permutation_p:.3f} |"
            for c in self.comparisons
        ]
        slices = sorted({name for m in self.modes for name in m.accuracy_by_slice})
        if slices:
            lines += [
                "",
                "## Accuracy by slice",
                "",
                "| Slice | " + " | ".join(m.mode.value for m in self.modes) + " |",
            ]
            lines += ["|---|" + "---|" * len(self.modes)]
            lines += [
                f"| {name} | "
                + " | ".join(
                    m.accuracy_by_slice[name].percent() if name in m.accuracy_by_slice else "-"
                    for m in self.modes
                )
                + " |"
                for name in slices
            ]
        lines += ["", "## Per case", "", "| Case | Mode | Seed | Correct | Flips | Stable from | Tags |"]
        lines += ["|---|---|---|---|---|---|---|"]
        lines += [
            f"| {d.case_id} | {d.mode.value} | {d.seed} | {'yes' if d.correct else 'no'} | {d.verdict_flips} "
            f"| "
            f"{d.steps_to_stable} | {', '.join(m.value for m in d.failure_modes) or '-'} |"
            for d in sorted(self.diagnoses, key=lambda d: (d.case_id, d.mode.value, d.seed))
        ]
        lines += [
            f"| {c.case_id} | {c.mode.value} | {c.seed} | crashed | | | {c.error[:80]} |"
            for c in self.crashes
        ]
        return "\n".join(lines) + "\n"

    @staticmethod
    def _pct(value: float | None) -> str:
        return "-" if value is None or value != value else f"{value:.0%}"

    @staticmethod
    def _num(value: float) -> str:
        return "-" if value != value else f"{value:.2f}"

    @staticmethod
    def _triple(m: ModeSummary, name: str) -> str:
        values = [getattr(c, name) for c in (m.shipped, m.llm_verbalised, m.evidence_posterior)]
        return " / ".join("-" if v != v else f"{v:.3f}" for v in values)


class BenchmarkRunner:
    """Runs every case under every mode and seed, grades each run, and resumes where a stopped run left off,
    but only within one code version (run_manifest.json)."""

    def __init__(
        self,
        harness: Harness,
        benchmark: Benchmark,
        benchmark_file: Path,
        run_dir: Path,
        budget: Budget,
        concurrency: int,
        retry_pause_s: float = 30.0,
    ) -> None:
        self._retry_pause_s = retry_pause_s
        self._harness = harness
        self._judge = Judge(harness.judge_chat)
        self._benchmark = benchmark
        self._benchmark_file = benchmark_file
        self._run_dir = run_dir
        self._budget = budget
        self._slots = asyncio.Semaphore(concurrency)
        self._pre_scoped = False

    def manifest(self, plan: RunPlan) -> RunManifest:
        sha, dirty = RunManifest.code_version()
        return RunManifest(
            git_sha=sha,
            dirty=dirty,
            settings=self._harness.settings.public(),
            budget={
                "max_steps": self._budget.max_steps,
                "max_tool_calls": self._budget.max_tool_calls,
                "actions_per_step": self._budget.actions_per_step,
            },
            benchmark_file=str(self._benchmark_file),
            benchmark_sha256=RunManifest.digest(self._benchmark_file),
            split=plan.split.value if plan.split else "all",
            seeds=list(plan.seeds),
            modes=[m.value for m in plan.modes],
            pre_scoped=plan.pre_scoped,
            started_at=RunManifest.now(),
        )

    async def run(self, plan: RunPlan) -> BenchmarkSummary:
        manifest = self.manifest(plan)
        manifest.open_in(self._run_dir, plan.force_new)
        self._pre_scoped = plan.pre_scoped
        per_stream = await asyncio.gather(
            *(
                self._run_mode(mode, seed, plan.shuffle_long_order)
                for mode in plan.modes
                for seed in plan.seeds
            )
        )
        episodes = [episode for episodes in per_stream for episode in episodes]
        results = [e for e in episodes if isinstance(e, EpisodeResult)]
        crashes = [e for e in episodes if isinstance(e, CrashedEpisode)]
        summary = self.summarise(results, crashes, plan)
        manifest.close_in(self._run_dir)
        return summary

    def summarise(
        self, results: list[EpisodeResult], crashes: list[CrashedEpisode], plan: RunPlan
    ) -> BenchmarkSummary:
        scoreboard = Scoreboard(results, crashes)
        summary = BenchmarkSummary(
            cases=len(self._benchmark.cases),
            seeds=list(plan.seeds),
            split=plan.split.value if plan.split else "all",
            pre_scoped=plan.pre_scoped,
            judge_model=self._judge.model,
            budget=self._budget,
            modes=[scoreboard.summary(mode) for mode in scoreboard.modes],
            comparisons=scoreboard.comparisons(),
            memory_impact=scoreboard.memory_impact(),
            crashes=crashes,
            diagnoses=[result.diagnosis for result in results],
        )
        (self._run_dir / "summary.json").write_text(summary.model_dump_json(indent=2), encoding="utf-8")
        (self._run_dir / "summary.md").write_text(summary.to_markdown(), encoding="utf-8")
        if scoreboard.modes:
            BenchmarkCharts(scoreboard).draw(self._run_dir / "charts")
        return summary

    def _memory_path(self, mode: MemoryMode, seed: int) -> Path:
        """Each long-memory stream learns only from its own mode and seed."""
        return self._run_dir / f"memory-{mode.value}-seed{seed}.sqlite3"

    async def _run_mode(self, mode: MemoryMode, seed: int, shuffle: bool) -> list[Episode]:
        investigator = self._harness.investigator(mode, self._memory_path(mode, seed), self._budget, seed)
        if mode.uses_long_term:
            return await self._run_long_memory_stream(investigator, mode, seed, shuffle)
        return list(
            await asyncio.gather(
                *(self._run_case_in_slot(investigator, mode, seed, case) for case in self._benchmark.cases)
            )
        )

    async def _run_long_memory_stream(
        self, investigator: Investigates, mode: MemoryMode, seed: int, shuffle: bool
    ) -> list[Episode]:
        """Cases run in benchmark order (or a seed-specific shuffle, to measure order effects). Before a case
        runs fresh, whatever an interrupted earlier attempt of it wrote to memory is erased; a crash stops the
        stream so no later case learns past it."""
        cases = list(self._benchmark.cases)
        if shuffle:
            random.Random(seed).shuffle(cases)
        episodes: list[Episode] = []
        for case in cases:
            if not self._result_path(mode, seed, case).exists():
                investigator.forget(self._investigation_id(mode, seed, case))
            episode = await self._run_case(investigator, mode, seed, case)
            episodes.append(episode)
            if isinstance(episode, CrashedEpisode):
                print(f"[{mode.value:>11} s{seed}] stream stopped at {case.id}; re-run to resume", flush=True)
                break
        return episodes

    def _result_path(self, mode: MemoryMode, seed: int, case: BenchmarkCase) -> Path:
        return self._run_dir / mode.value / f"seed{seed}" / case.id / "result.json"

    @staticmethod
    def _investigation_id(mode: MemoryMode, seed: int, case: BenchmarkCase) -> str:
        return f"{mode.value}-s{seed}-{case.id}"

    async def _run_case_in_slot(
        self, investigator: Investigates, mode: MemoryMode, seed: int, case: BenchmarkCase
    ) -> Episode:
        """Parallel modes share the slots; the sequential long-memory streams keep their own lanes."""
        async with self._slots:
            return await self._run_case(investigator, mode, seed, case)

    async def _run_case(
        self, investigator: Investigates, mode: MemoryMode, seed: int, case: BenchmarkCase
    ) -> Episode:
        """A finished case is reused on resume; a crashed one is tried again."""
        result_path = self._result_path(mode, seed, case)
        folder = result_path.parent
        if result_path.exists():
            return EpisodeResult.model_validate_json(result_path.read_text(encoding="utf-8"))
        episode = await self._investigate(investigator, mode, seed, case, folder)
        if isinstance(episode, CrashedEpisode):
            (folder / "crash.json").write_text(episode.model_dump_json(indent=2), encoding="utf-8")
            print(f"[{mode.value:>11} s{seed}] {case.id} CRASHED {episode.error}", flush=True)
            return episode
        result_path.write_text(episode.model_dump_json(indent=2), encoding="utf-8")
        (folder / "diagnosis.json").write_text(episode.diagnosis.model_dump_json(indent=2), encoding="utf-8")
        (folder / "crash.json").unlink(missing_ok=True)
        print(
            f"[{mode.value:>11} s{seed}] {case.id} {episode.verdict.value} "
            f"({'correct' if episode.correct else 'wrong'})",
            flush=True,
        )
        return episode

    MAX_ATTEMPTS: ClassVar[int] = 3
    TRANSIENT: ClassVar[tuple[type[Exception], ...]] = (ServiceUnavailable, MalformedCompletion)

    async def _investigate(
        self, investigator: Investigates, mode: MemoryMode, seed: int, case: BenchmarkCase, folder: Path
    ) -> Episode:
        """A transient failure (a throttled or timed-out API, a malformed reply that survived the chat
        client's own retries) restarts the investigation, up to three attempts; a search replays from the
        search cache, so a retry costs model tokens but almost no search credits. Judging is retried on its
        own, so a bad grading never repeats an investigation. Only a case still failing after that becomes a
        crashed episode, so one outage can't void the run. Publisher track records learn from the label only
        on dev cases, never on the test split."""
        investigation_id = self._investigation_id(mode, seed, case)
        as_of = self._benchmark.case_as_of(case)
        resolution = (
            Resolution(case.expected_verdict, ResolvedBy.BENCHMARK_LABEL) if case.split is Split.DEV else None
        )
        crash = partial(CrashedEpisode, case_id=case.id, mode=mode, kind=case.kind, seed=seed)
        investigation = scope = None
        used = 1
        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            trace = TraceLog(folder / "trace.jsonl", investigation_id)
            try:
                documents = tuple(
                    [
                        await self._harness.intake.read(self._benchmark_file.parent / name)
                        for name in case.documents
                    ]
                )
                if self._pre_scoped:
                    subject = replace(case.as_subject(as_of), documents=documents)
                else:
                    subject = await investigator.scope(case.analyst_text, documents, trace, as_of)
                scope = ScopeGrade.of(case.expected_scope, subject) if case.expected_scope else None
                investigation = await investigator.investigate(subject, trace, resolution)
                used = attempt
                break
            except self.TRANSIENT as error:
                if attempt == self.MAX_ATTEMPTS:
                    return crash(error=f"{type(error).__name__}: {error} (after {attempt} attempts)")
                investigator.forget(investigation_id)
                await asyncio.sleep(self._retry_pause_s * attempt)
            except (ServiceRejected, OSError) as error:
                return crash(error=f"{type(error).__name__}: {error}")
        if investigation is None:
            return crash(error="no investigation was produced")
        graded = None
        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                graded = await self._judge.grade(case, investigation)
                break
            except self.TRANSIENT as error:
                if attempt == self.MAX_ATTEMPTS:
                    return crash(error=f"judge: {type(error).__name__}: {error} (after {attempt} attempts)")
                await asyncio.sleep(self._retry_pause_s * attempt)
            except ServiceRejected as error:
                return crash(error=f"judge: {type(error).__name__}: {error}")
        if graded is None:
            return crash(error="no grading was produced")
        (folder / "report.md").write_text(investigation.report.to_markdown(), encoding="utf-8")
        (folder / "report.json").write_text(investigation.report.to_json(), encoding="utf-8")
        (folder / "grading.json").write_text(graded.value.model_dump_json(indent=2), encoding="utf-8")
        return EpisodeResult.grade(
            case,
            investigation,
            graded.value,
            self._budget.max_steps,
            self._harness.settings.price,
            seed,
            scope,
            self._judge.model,
            attempts=used,
        )
