"""Counterfactual failure diagnosis (E6): why did an episode go wrong?

Each wrong episode of a run is re-run once per intervention, changing exactly one thing:

continue         the gate may not close until two extra rounds (and six extra tool calls) have been spent
no_memory        memory mode `none`
gold_source      round 1 also reads the case's ground-truth source URLs
pre_scoped       the gold scope instead of the agent's own scoping
strong_reasoner  the Reflector runs on another model (the judge's family)

An intervention that turns the verdict correct is a *cause*: without that limitation, the agent would have
been right. An episode no intervention fixes is `unresolved`. Re-runs are single samples, so a flip is
evidence, not proof; the counts carry Wilson intervals. The judge is not called: only the verdict matters.
"""

import asyncio
from dataclasses import replace
from pathlib import Path

from pydantic import BaseModel

from osint_harness.evaluation import stats
from osint_harness.evaluation.benchmark import Benchmark, BenchmarkCase
from osint_harness.evaluation.episode import EpisodeResult
from osint_harness.harness import Harness, Intervention
from osint_harness.investigation.verdict import Verdict
from osint_harness.investigator import Budget
from osint_harness.nvidia import MalformedCompletion
from osint_harness.trace import TraceLog
from osint_harness.transport import ServiceRejected, ServiceUnavailable


class Replay(BaseModel):
    intervention: Intervention
    verdict: Verdict | None
    correct: bool
    error: str = ""


class Diagnosis(BaseModel):
    case_id: str
    seed: int
    original: Verdict
    expected: Verdict
    replays: list[Replay]

    @property
    def causes(self) -> list[Intervention]:
        """Interventions that fixed the verdict. The control (`repeat`) is not a cause: if it fixes the
        episode too, the original answer was sampling noise, and no cause can be read from the others."""
        return [
            r.intervention for r in self.replays if r.correct and r.intervention is not Intervention.REPEAT
        ]

    @property
    def noise(self) -> bool:
        return any(r.correct for r in self.replays if r.intervention is Intervention.REPEAT)


class CauseCount(BaseModel):
    cause: str
    episodes: int
    share: float
    low: float
    high: float


class CounterfactualSummary(BaseModel):
    diagnosed: int
    counts: list[CauseCount]
    diagnoses: list[Diagnosis]

    def to_markdown(self) -> str:
        lines = [
            f"Wrong episodes diagnosed: {self.diagnosed}. A cause is an intervention that made the verdict "
            f"correct.",
            "",
            "| Cause | Episodes | Share [95% Wilson CI] |",
            "|---|---|---|",
        ]
        lines += [
            f"| {c.cause} | {c.episodes} | {c.share:.0%} [{c.low:.0%}, {c.high:.0%}] |" for c in self.counts
        ]
        lines += [
            "",
            "| Case | Seed | Verdict | Expected | " + " | ".join(i.value for i in Intervention) + " |",
        ]
        lines += ["|---|---|---|---|" + "---|" * len(Intervention)]
        for d in self.diagnoses:
            by = {r.intervention: r for r in d.replays}
            cells = [self._cell(by[i]) if i in by else "-" for i in Intervention]
            lines.append(
                f"| {d.case_id} | {d.seed} | {d.original.value} | {d.expected.value} | "
                + " | ".join(cells)
                + " |"
            )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _cell(replay: Replay) -> str:
        if replay.verdict is None:
            return f"error: {replay.error[:30]}"
        return ("✔ " if replay.correct else "") + replay.verdict.value


class CounterfactualRunner:
    def __init__(
        self, harness: Harness, benchmark: Benchmark, cases_dir: Path, run_dir: Path, budget: Budget
    ) -> None:
        self._cases_dir = cases_dir
        self._harness = harness
        self._benchmark = benchmark
        self._run_dir = run_dir
        self._budget = budget

    def wrong_episodes(self, mode: str) -> list[EpisodeResult]:
        paths = sorted(self._run_dir.glob(f"{mode}/seed*/*/result.json"))
        results = [EpisodeResult.model_validate_json(p.read_text(encoding="utf-8")) for p in paths]
        return [r for r in results if not r.correct]

    async def diagnose(
        self, mode: str, interventions: tuple[Intervention, ...] = tuple(Intervention)
    ) -> CounterfactualSummary:
        cases = {case.id: case for case in self._benchmark.cases}
        diagnoses = []
        for episode in self.wrong_episodes(mode):
            replays = await asyncio.gather(
                *(self._replay(episode, cases[episode.case_id], i) for i in interventions)
            )
            diagnoses.append(
                Diagnosis(
                    case_id=episode.case_id,
                    seed=episode.seed,
                    original=episode.verdict,
                    expected=episode.expected,
                    replays=list(replays),
                )
            )
        folder = self._run_dir / "counterfactuals"
        folder.mkdir(parents=True, exist_ok=True)
        diagnoses = self._merged(folder / f"{mode}.json", diagnoses)
        summary = self.summarise(diagnoses)
        (folder / f"{mode}.json").write_text(summary.model_dump_json(indent=2), encoding="utf-8")
        (folder / f"{mode}.md").write_text(summary.to_markdown(), encoding="utf-8")
        return summary

    @staticmethod
    def _merged(path: Path, fresh: list[Diagnosis]) -> list[Diagnosis]:
        """Replays from an earlier call are kept; a repeated intervention replaces its older replay."""
        if not path.exists():
            return fresh
        earlier = CounterfactualSummary.model_validate_json(path.read_text(encoding="utf-8")).diagnoses
        by_key = {(d.case_id, d.seed): d for d in earlier}
        for d in fresh:
            old = by_key.get((d.case_id, d.seed))
            replays = {r.intervention: r for r in (old.replays if old else [])} | {
                r.intervention: r for r in d.replays
            }
            by_key[(d.case_id, d.seed)] = d.model_copy(update={"replays": list(replays.values())})
        return list(by_key.values())

    @staticmethod
    def summarise(diagnoses: list[Diagnosis]) -> CounterfactualSummary:
        n = len(diagnoses)
        counts = []
        for cause in [*(i for i in Intervention if i is not Intervention.REPEAT), "unresolved"]:
            hits = sum(1 for d in diagnoses if (cause in d.causes if cause != "unresolved" else not d.causes))
            low, high = stats.wilson(hits, n) if n else (float("nan"), float("nan"))
            counts.append(
                CauseCount(
                    cause=str(cause), episodes=hits, share=hits / n if n else float("nan"), low=low, high=high
                )
            )
        counts.append(
            CauseCount(
                cause="fixed by a plain re-run (sampling noise)",
                episodes=sum(1 for d in diagnoses if d.noise),
                share=sum(1 for d in diagnoses if d.noise) / n if n else float("nan"),
                low=stats.wilson(sum(1 for d in diagnoses if d.noise), n)[0] if n else float("nan"),
                high=stats.wilson(sum(1 for d in diagnoses if d.noise), n)[1] if n else float("nan"),
            )
        )
        return CounterfactualSummary(diagnosed=n, counts=counts, diagnoses=diagnoses)

    async def _replay(
        self, episode: EpisodeResult, case: BenchmarkCase, intervention: Intervention
    ) -> Replay:
        folder = self._run_dir / "counterfactuals" / episode.mode.value / f"seed{episode.seed}" / case.id
        trace = TraceLog(folder / f"{intervention.value}.trace.jsonl", f"cf-{intervention.value}-{case.id}")
        investigator = self._harness.investigator(
            episode.mode,
            folder / f"{intervention.value}.memory.sqlite3",
            self._budget,
            episode.seed,
            intervention,
            tuple(case.ground_truth_sources),
        )
        as_of = self._benchmark.case_as_of(case)
        try:
            documents = tuple(
                [await self._harness.intake.read(self._cases_dir / name) for name in case.documents]
            )
            if intervention is Intervention.PRE_SCOPED:
                subject = replace(case.as_subject(as_of), documents=documents)
            else:
                subject = await investigator.scope(case.analyst_text, documents, trace, as_of)
            investigation = await investigator.investigate(subject, trace)
        except (ServiceUnavailable, ServiceRejected, MalformedCompletion) as error:
            return Replay(
                intervention=intervention, verdict=None, correct=False, error=f"{type(error).__name__}"
            )
        verdict = investigation.report.verdict
        return Replay(intervention=intervention, verdict=verdict, correct=case.accepts(verdict))
