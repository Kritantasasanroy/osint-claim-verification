import asyncio
import json
import math
import sqlite3
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from fakes import FakeServices, Handler
from osint_harness.evaluation.benchmark import Benchmark, BenchmarkCase
from osint_harness.evaluation.episode import CrashedEpisode, EpisodeResult, FailureMode
from osint_harness.evaluation.judge import Grading, Judge, MemoryLabel
from osint_harness.evaluation.rewards import EpisodeReward, StepReward
from osint_harness.evaluation.runner import BenchmarkRunner, RunPlan
from osint_harness.evaluation.scoreboard import Scoreboard
from osint_harness.harness import Harness
from osint_harness.investigation.case_file import MemoryMode
from osint_harness.investigation.verdict import SubjectKind, Verdict
from osint_harness.investigator import Budget
from osint_harness.settings import Settings
from osint_harness.trace import TraceEventKind, TraceLog
from osint_harness.transport import Transport

AS_OF = date(2026, 10, 1)


def runner_for(
    harness: Harness, cases: list[BenchmarkCase], tmp_path: Path, concurrency: int = 2
) -> BenchmarkRunner:
    benchmark = Benchmark(description="t", as_of=AS_OF, cases=cases)
    cases_file = tmp_path / "cases.json"
    cases_file.write_text(benchmark.model_dump_json(), encoding="utf-8")
    return BenchmarkRunner(
        harness, benchmark, cases_file, tmp_path / "run", Budget(), concurrency, retry_pause_s=0.0
    )


class BrokenReflectionServices(FakeServices):
    """A model that keeps answering the Reflector off-schema: the investigation cannot complete."""

    def __init__(self, publishers: list[str]) -> None:
        super().__init__(publishers)
        self.broken = True

    def reflection(self) -> dict[str, object]:
        return {"critique": "?"} if self.broken else super().reflection()


@pytest.fixture
def case() -> BenchmarkCase:
    return BenchmarkCase(
        id="T1",
        kind=SubjectKind.CLAIM,
        subject="Wirecard was audited by EY",
        expected_verdict=Verdict.TRUE,
        acceptable_verdicts=[Verdict.TRUE],
        key_facts=["EY audited Wirecard", "EY refused to sign the 2019 accounts"],
    )


@pytest.fixture
def harness_with(
    settings: Settings, make_transport: Callable[[Handler], Transport]
) -> Callable[[FakeServices], Harness]:
    return lambda services: services.harness(settings, make_transport)


@pytest.fixture
def graded(
    tmp_path: Path, settings: Settings, case: BenchmarkCase, harness_with: Callable[[FakeServices], Harness]
) -> Callable[[list[str]], EpisodeResult]:
    def grade(publishers: list[str]) -> EpisodeResult:
        harness = harness_with(FakeServices(publishers))
        investigator = harness.investigator(MemoryMode.SHORT, tmp_path / "m", Budget(max_steps=2))
        investigation = asyncio.run(
            investigator.investigate(case.as_subject(AS_OF), TraceLog(tmp_path / "t.jsonl", "t"))
        )
        judge = Judge(harness.judge_chat)
        grading = asyncio.run(judge.grade(case, investigation)).value
        return EpisodeResult.grade(case, investigation, grading, 2, settings.price, judge_model=judge.model)

    return grade


def test_shipped_benchmark_covers_every_subject_kind_and_the_hard_cases() -> None:
    benchmark = Benchmark.load(Path("benchmark/cases.json"))
    tags = {tag for case in benchmark.cases for tag in case.tags}

    assert len(benchmark.cases) >= 30
    assert {case.kind for case in benchmark.cases} == set(SubjectKind)
    assert {"conflicting", "insufficient", "ambiguous_name"} <= tags
    unverifiable = [case for case in benchmark.cases if case.expected_verdict is Verdict.UNVERIFIABLE]
    assert {case.kind for case in unverifiable} >= {
        SubjectKind.COMPANY,
        SubjectKind.PERSON,
        SubjectKind.CLAIM,
    }
    assert len({case.id for case in benchmark.cases}) == len(benchmark.cases)


def test_a_case_whose_verdict_does_not_fit_its_kind_is_rejected() -> None:
    with pytest.raises(ValidationError, match="verdicts must be among"):
        BenchmarkCase(
            id="X",
            kind=SubjectKind.PERSON,
            subject="Someone",
            expected_verdict=Verdict.TRUE,
            acceptable_verdicts=[Verdict.TRUE],
            key_facts=["f"],
        )


def test_step_reward_rewards_progress_and_penalises_waste() -> None:
    useful = StepReward.measure(1, 0.25, 0.85, 2.0, 3, 6, 0, 3, 0, 10_000)
    wasteful = StepReward.measure(2, 0.85, 0.85, 0.0, 0, 6, 6, 3, 3, 20_000)

    assert useful.total == pytest.approx(0.5 * 0.6 + 0.2 * (1 - math.exp(-1)) + 0.15 - 0.05 * 0.5)
    assert wasteful.total == pytest.approx(-0.1 - 0.05 - 0.05)
    assert wasteful.process < useful.process


def test_episode_reward_prefers_a_calibrated_correct_answer() -> None:
    calibrated = EpisodeReward.measure(True, 0.9, 1.0, 1.0, tokens=30_000)
    overconfident_wrong = EpisodeReward.measure(False, 0.95, 0.5, 1.0, tokens=30_000)

    assert calibrated.calibration == pytest.approx(0.99)
    assert overconfident_wrong.calibration == pytest.approx(1 - 0.95**2)
    assert calibrated.total > overconfident_wrong.total


def test_an_episode_is_graded_from_its_steps_and_the_judge(
    graded: Callable[[list[str]], EpisodeResult],
) -> None:
    result = graded([FakeServices.REUTERS, FakeServices.FT])

    assert result.correct
    assert result.kind is SubjectKind.CLAIM
    assert (result.key_fact_recall, result.citation_precision) == (0.5, 1.0)
    assert [s.step for s in result.steps] == [1]
    assert result.steps[0].llm_p_correct == pytest.approx(0.9)
    assert result.steps[0].p_correct == pytest.approx(result.confidence)
    assert result.steps[0].reward.progress == pytest.approx(result.confidence - 0.25)
    assert result.steps[0].reward.corroboration == pytest.approx(2 / 3)
    assert result.steps_to_stable == 1 and result.verdict_flips == 0
    assert result.failure_modes == []
    assert result.judge_model == Settings.judge_model
    assert EpisodeResult.model_validate_json(result.model_dump_json()) == result


def test_a_wrong_single_source_episode_is_tagged_by_what_it_lacked(
    graded: Callable[[list[str]], EpisodeResult],
) -> None:
    wrong = graded([FakeServices.REUTERS]).model_copy(update={"correct": False, "expected": Verdict.FALSE})

    assert set(wrong.failure_modes) == {FailureMode.WEAK_EVIDENCE, FailureMode.BUDGET_EXHAUSTED}


def test_crashed_episodes_are_counted_but_never_averaged(
    graded: Callable[[list[str]], EpisodeResult],
) -> None:
    base = graded([FakeServices.REUTERS, FakeServices.FT])
    crash = CrashedEpisode(
        case_id="T2", mode=MemoryMode.SHORT, kind=SubjectKind.CLAIM, error="ServiceUnavailable"
    )

    summary = Scoreboard([base], [crash]).summary(MemoryMode.SHORT)

    assert (summary.episodes, summary.crashed, summary.accuracy.mean) == (1, 1, 1.0)
    assert summary.shipped.brier == pytest.approx((base.confidence - 1) ** 2)


def test_scoreboard_measures_calibration_and_paired_memory_impact(
    graded: Callable[[list[str]], EpisodeResult],
) -> None:
    base = graded([FakeServices.REUTERS, FakeServices.FT])
    short_wrong = base.model_copy(update={"mode": MemoryMode.SHORT, "correct": False})
    long_right = base.model_copy(
        update={
            "mode": MemoryMode.LONG,
            "memory_labels": {"M1": MemoryLabel.RELEVANT, "M2": MemoryLabel.MISLEADING},
        }
    )
    board = Scoreboard([short_wrong, long_right], [])

    impact = board.memory_impact()
    long_summary = board.summary(MemoryMode.LONG)

    assert impact.long_vs_short_accuracy == 1.0
    assert impact.short_vs_none_accuracy is None
    assert impact.long_improved_cases == ["T1"]
    assert impact.cases_with_relevant_memory == 1
    assert long_summary.memory_misleading_rate == 0.5
    assert long_summary.misleading_memories_trusted == 1
    assert board.summary(MemoryMode.SHORT).shipped.ece == pytest.approx(base.confidence)


def test_the_judge_schema_demands_one_answer_per_item(
    tmp_path: Path, case: BenchmarkCase, harness_with: Callable[[FakeServices], Harness]
) -> None:
    services = FakeServices([FakeServices.REUTERS, FakeServices.FT])
    harness = harness_with(services)
    investigation = asyncio.run(
        harness.investigator(MemoryMode.SHORT, tmp_path / "m", Budget()).investigate(
            case.as_subject(AS_OF), TraceLog(tmp_path / "t.jsonl", "t")
        )
    )

    grading = asyncio.run(Judge(harness.judge_chat).grade(case, investigation)).value

    assert services.items_demanded["Grading"]["key_facts_established"] == 2
    assert services.models["Grading"] == [Settings.judge_model]
    assert grading.key_fact_recall == 0.5
    with pytest.raises(ValidationError):
        Grading.sized(2, 1, 0).model_validate(
            {
                "key_facts_established": [True],
                "findings": [{"atomic_facts": [{"fact": "f", "supported": True}]}],
                "memory_labels_in_order": [],
            }
        )


def test_runner_grades_every_mode_writes_charts_and_resumes(
    tmp_path: Path, case: BenchmarkCase, harness_with: Callable[[FakeServices], Harness]
) -> None:
    services = FakeServices([FakeServices.REUTERS, FakeServices.FT])
    runner = runner_for(harness_with(services), [case, case.model_copy(update={"id": "T2"})], tmp_path)

    summary = asyncio.run(runner.run(RunPlan(tuple(MemoryMode))))
    calls_after_first_run = sum(len(prompts) for prompts in services.prompts.values())
    asyncio.run(runner.run(RunPlan(tuple(MemoryMode))))

    run = tmp_path / "run"
    assert [m.mode for m in summary.modes] == list(MemoryMode)
    assert summary.modes[0].mode is MemoryMode.CLOSED_BOOK
    assert all(m.accuracy.mean == 1.0 and m.crashed == 0 for m in summary.modes)
    assert json.loads((run / "summary.json").read_text())["cases"] == 2
    assert len(list((run / "charts").glob("*.png"))) == 7
    assert sum(len(prompts) for prompts in services.prompts.values()) == calls_after_first_run
    assert [c.baseline for c in summary.comparisons][:4] == ["closed_book"] * 4


def test_a_crashed_case_is_recorded_and_retried_on_resume(
    tmp_path: Path, case: BenchmarkCase, harness_with: Callable[[FakeServices], Harness]
) -> None:
    services = BrokenReflectionServices([FakeServices.REUTERS, FakeServices.FT])
    runner = runner_for(harness_with(services), [case], tmp_path, 1)
    folder = tmp_path / "run" / "short" / "seed0" / "T1"

    first = asyncio.run(runner.run(RunPlan((MemoryMode.SHORT,))))
    crash_recorded = (folder / "crash.json").exists()
    services.broken = False
    second = asyncio.run(runner.run(RunPlan((MemoryMode.SHORT,))))

    assert [c.case_id for c in first.crashes] == ["T1"] and first.modes == []
    assert crash_recorded
    assert second.crashes == [] and second.modes[0].accuracy.mean == 1.0
    assert not (folder / "crash.json").exists()
    assert json.loads((folder / "diagnosis.json").read_text())["correct"] is True
    assert "| T1 | short | 0 | yes |" in (tmp_path / "run" / "summary.md").read_text()


def test_a_long_memory_crash_erases_its_memories_and_stops_the_stream(
    tmp_path: Path, case: BenchmarkCase, harness_with: Callable[[FakeServices], Harness]
) -> None:
    services = BrokenReflectionServices([FakeServices.REUTERS, FakeServices.FT])
    services.broken = False
    later = case.model_copy(update={"id": "T2"})
    runner = runner_for(harness_with(services), [case, later], tmp_path, 1)
    asyncio.run(runner.run(RunPlan((MemoryMode.LONG,))))
    (tmp_path / "run" / "long" / "seed0" / "T1" / "result.json").unlink()
    services.broken = True

    summary = asyncio.run(runner.run(RunPlan((MemoryMode.LONG,))))
    memory = sqlite3.connect(str(tmp_path / "run" / "memory-long-seed0.sqlite3"))

    assert [c.case_id for c in summary.crashes] == ["T1"]
    assert memory.execute("SELECT COUNT(*) FROM facts WHERE learned_in = 'long-s0-T1'").fetchone() == (0,)
    assert memory.execute(
        "SELECT COUNT(*) FROM publisher_outcomes WHERE investigation = 'long-s0-T1'"
    ).fetchone() == (0,)


def test_round_cost_excludes_the_closing_report_and_memory_write(
    graded: Callable[[list[str]], EpisodeResult],
) -> None:
    result = graded([FakeServices.REUTERS, FakeServices.FT])

    # research choice, assessment, reflection and the red-team pass; not the closing report
    round_tokens = result.steps[0].reward.cost * 20_000
    assert round_tokens == pytest.approx(4 * 120)


def test_a_long_case_interrupted_after_writing_memory_does_not_recall_itself_on_resume(
    tmp_path: Path, case: BenchmarkCase, harness_with: Callable[[FakeServices], Harness]
) -> None:
    services = FakeServices([FakeServices.REUTERS, FakeServices.FT])
    runner = runner_for(harness_with(services), [case], tmp_path, 1)
    asyncio.run(runner.run(RunPlan((MemoryMode.LONG,))))
    folder = tmp_path / "run" / "long" / "seed0" / "T1"
    (folder / "result.json").unlink()

    asyncio.run(runner.run(RunPlan((MemoryMode.LONG,))))
    trace = TraceLog.read(folder / "trace.jsonl")

    recalled = next(event for event in trace if event.kind is TraceEventKind.MEMORY_RECALLED)
    assert recalled.detail["memories"] == []


def test_an_episode_that_concluded_early_still_counts_in_later_rounds(
    graded: Callable[[list[str]], EpisodeResult],
) -> None:
    one_round = graded([FakeServices.REUTERS, FakeServices.FT])
    first = one_round.steps[0]
    later = first.model_copy(update={"step": 2, "p_correct": 0.2})
    two_rounds = one_round.model_copy(update={"case_id": "T2", "steps": [first, later]})

    curve = Scoreboard([one_round, two_rounds], []).summary(MemoryMode.SHORT).p_correct_by_step

    assert curve == pytest.approx([first.p_correct, (first.p_correct + 0.2) / 2])


def test_reward_curves_count_unrun_rounds_as_nothing_happening(
    graded: Callable[[list[str]], EpisodeResult],
) -> None:
    one_round = graded([FakeServices.REUTERS, FakeServices.FT])
    first = one_round.steps[0]
    second = first.model_copy(update={"step": 2})
    two_rounds = one_round.model_copy(update={"case_id": "T2", "steps": [first, second]})

    rewards = Scoreboard([one_round, two_rounds], []).summary(MemoryMode.SHORT).step_reward_by_step

    assert rewards == pytest.approx([first.reward.total, second.reward.total / 2])
