"""Does the mode ranking depend on the hand-picked episode-reward weights? (E7b)

Recomputes the mean episode reward per mode from the stored components (correctness, key-fact recall, citation
precision, calibration, cost) with each weight scaled by 0.5 and 1.5 in turn, and reports whether the ranking of
modes ever changes. Post-hoc analysis over result.json files: it changes nothing about how a run behaves.
Usage: python benchmark/reward_sensitivity.py RUN_DIR [RUN_DIR ...]"""

import sys
from pathlib import Path
from statistics import fmean

from osint_harness.evaluation.episode import EpisodeResult
from osint_harness.evaluation.rewards import EpisodeReward

WEIGHTS = {
    "correctness": "CORRECTNESS_WEIGHT",
    "key_fact_recall": "RECALL_WEIGHT",
    "citation_precision": "CITATION_WEIGHT",
    "calibration": "CALIBRATION_WEIGHT",
    "cost (penalty)": "COST_PENALTY",
}


def reward(episode: EpisodeResult, scale: dict[str, float]) -> float:
    r = episode.episode_reward
    return (
        EpisodeReward.CORRECTNESS_WEIGHT * scale.get("correctness", 1) * r.correctness
        + EpisodeReward.RECALL_WEIGHT * scale.get("key_fact_recall", 1) * r.key_fact_recall
        + EpisodeReward.CITATION_WEIGHT * scale.get("citation_precision", 1) * r.citation_precision
        + EpisodeReward.CALIBRATION_WEIGHT * scale.get("calibration", 1) * r.calibration
        - EpisodeReward.COST_PENALTY * scale.get("cost (penalty)", 1) * r.cost
    )


def ranking(episodes: list[EpisodeResult], scale: dict[str, float]) -> list[str]:
    by_mode: dict[str, list[float]] = {}
    for e in episodes:
        by_mode.setdefault(e.mode.value, []).append(reward(e, scale))
    return [mode for mode, _ in sorted(by_mode.items(), key=lambda item: -fmean(item[1]))]


def main(run_dirs: list[Path]) -> None:
    episodes = [
        EpisodeResult.model_validate_json(p.read_text(encoding="utf-8"))
        for run in run_dirs
        for p in sorted(run.glob("*/seed*/*/result.json"))
    ]
    base = ranking(episodes, {})
    print(f"{len(episodes)} episodes; baseline ranking (best first): {' > '.join(base)}\n")
    print("| Weight scaled | x0.5 ranking | x1.5 ranking | Ranking changed? |")
    print("|---|---|---|---|")
    changed_any = False
    for name in WEIGHTS:
        low, high = ranking(episodes, {name: 0.5}), ranking(episodes, {name: 1.5})
        changed = low != base or high != base
        changed_any |= changed
        print(f"| {name} | {' > '.join(low)} | {' > '.join(high)} | {'YES' if changed else 'no'} |")
    print(f"\nRanking {'is sensitive to' if changed_any else 'is stable under'} +/-50% on any single weight.")


if __name__ == "__main__":
    main([Path(arg) for arg in sys.argv[1:]])
