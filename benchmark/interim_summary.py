"""Summarises the finished episodes of a run that is still going (or was stopped), without touching the run
directory's own summary. Prints accuracy with CIs per mode, the paired comparison on the cases both modes
finished, accuracy by slice, and crash counts. Usage: python benchmark/interim_summary.py RUN_DIR"""

import sys
from pathlib import Path

from osint_harness.evaluation.episode import CrashedEpisode, EpisodeResult
from osint_harness.evaluation.scoreboard import Scoreboard


def main(run_dir: Path) -> None:
    results = [
        EpisodeResult.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted(run_dir.glob("*/seed*/*/result.json"))
    ]
    crashes = [
        CrashedEpisode.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted(run_dir.glob("*/seed*/*/crash.json"))
        if not (p.parent / "result.json").exists()
    ]
    board = Scoreboard(results, crashes)
    print(f"INTERIM: {len(results)} finished episodes, {len(crashes)} crashed (excluded), from {run_dir}\n")
    print(
        "| Mode | Episodes | Accuracy [95% CI] | Scope acc. | Brier shipped/LLM | AURC shipped/LLM | "
        "Rounds | Tokens [95% CI] | ADVERSE citing primary record | Crashed |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|")
    for mode in board.modes:
        m = board.summary(mode)
        primary = "-" if m.adverse_citing_primary_record is None else f"{m.adverse_citing_primary_record:.0%}"
        scope = "-" if m.scope_accuracy is None else f"{m.scope_accuracy:.0%}"
        print(
            f"| {mode.value} | {m.episodes} | {m.accuracy.percent()} | {scope} | "
            f"{m.shipped.brier:.3f}/{m.llm_verbalised.brier:.3f} | {m.shipped.aurc:.3f}/{m.llm_verbalised.aurc:.3f} | "
            f"{m.steps:.2f} | {m.tokens.mean:,.0f} [{m.tokens.low:,.0f}, {m.tokens.high:,.0f}] | {primary} | {m.crashed} |"
        )
    print("\nPaired (only cases both modes finished):\n")
    print(
        "| Treated vs baseline | Cases | Difference [95% CI] | Discordant (+/-) | McNemar p | Permutation p |"
    )
    print("|---|---|---|---|---|---|")
    for c in board.comparisons():
        print(
            f"| {c.treated} vs {c.baseline} | {c.difference.cases} | {c.difference.mean:+.3f} "
            f"[{c.difference.low:+.3f}, {c.difference.high:+.3f}] | {c.discordant_treated_better}/"
            f"{c.discordant_baseline_better} | {c.mcnemar_p:.3f} | {c.permutation_p:.3f} |"
        )
    print("\nBy slice:\n")
    names = sorted({s for r in results for s in r.slices})
    print("| Slice | " + " | ".join(m.value for m in board.modes) + " |")
    print("|---|" + "---|" * len(board.modes))
    for name in names:
        cells = []
        for mode in board.modes:
            summary = board.summary(mode).accuracy_by_slice.get(name)
            cells.append(f"{summary.percent()} (n={summary.cases})" if summary else "-")
        print(f"| {name} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
