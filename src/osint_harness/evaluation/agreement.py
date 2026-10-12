"""Who grades the grader (E5), and does the reward track what a human cares about (E7)?

`template` exports, from a finished run, the items a human labels blind: whether each key fact is
established, whether each atomic fact is supported by its excerpts, and a 1-5 "would I act on this report"
rating. The judge's answers and the mode stay out of the file a human sees (they live in the run directory).
`measure` then joins the human labels to the judge's and reports Cohen's kappa per item kind and Spearman's
rho between episode reward and the human rating. Nothing here invents a label: unlabelled items are counted.
"""

import json
import random
from pathlib import Path

from pydantic import BaseModel

from osint_harness.evaluation import stats
from osint_harness.evaluation.episode import EpisodeResult
from osint_harness.evaluation.judge import Grading


class GoldItem(BaseModel):
    key: str
    episode: str
    kind: str
    prompt: str
    human: str | None = None


class ReportRating(BaseModel):
    episode: str
    report: str
    human_rating: int | None = None


class GoldFile(BaseModel):
    instructions: str
    items: list[GoldItem]
    ratings: list[ReportRating]


class Agreement(BaseModel):
    kind: str
    labelled: int
    unlabelled: int
    kappa: float


class AgreementSummary(BaseModel):
    judge_model: str
    agreements: list[Agreement]
    rated_reports: int
    reward_vs_rating_spearman: float

    def to_markdown(self) -> str:
        lines = [f"Judge: {self.judge_model}", "", "| Item kind | Labelled | Unlabelled | Cohen's kappa |"]
        lines += ["|---|---|---|---|"]
        lines += [f"| {a.kind} | {a.labelled} | {a.unlabelled} | {a.kappa:.2f} |" for a in self.agreements]
        lines += [
            "",
            f"Reports rated: {self.rated_reports}; Spearman rho(episode reward, rating) = "
            f"{self.reward_vs_rating_spearman:.2f}",
        ]
        return "\n".join(lines) + "\n"


def episodes(run_dir: Path) -> list[Path]:
    return sorted(path.parent for path in run_dir.glob("*/seed*/*/result.json"))


def template(run_dir: Path, items: int = 60, reports: int = 40, seed: int = 0) -> GoldFile:
    """A blind sample of judge items and reports to label, in random order across modes."""
    rng = random.Random(seed)
    folders = episodes(run_dir)
    gold: list[GoldItem] = []
    for folder in folders:
        result = EpisodeResult.model_validate_json((folder / "result.json").read_text(encoding="utf-8"))
        report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
        grading = json.loads((folder / "grading.json").read_text(encoding="utf-8"))
        name = str(folder.relative_to(run_dir))
        summary = report.get("summary", "")
        for n, _ in enumerate(grading.get("key_facts_established", [])):
            gold.append(
                GoldItem(
                    key=f"{name}#fact{n}",
                    episode=name,
                    kind="key_fact",
                    prompt=f"Report summary: {summary}\nDoes the report establish key fact #{n + 1} "
                    f"of case {result.case_id}? (yes/no)",
                )
            )
        for f, finding in enumerate(grading.get("findings", [])):
            for a, atom in enumerate(finding.get("atomic_facts", [])):
                gold.append(
                    GoldItem(
                        key=f"{name}#finding{f}.{a}",
                        episode=name,
                        kind="atomic_fact",
                        prompt=f"Atomic fact: {atom['fact']}\nIs it supported by the excerpts cited "
                        f"for finding {f + 1} of this report? (yes/no)",
                    )
                )
    rng.shuffle(gold)
    rated = [ReportRating(episode=str(f.relative_to(run_dir)), report=str(f / "report.md")) for f in folders]
    rng.shuffle(rated)
    return GoldFile(
        instructions=(
            "Label each item 'yes' or 'no' in `human` without opening grading.json; rate each report 1-5 on "
            "'would I act on this' without looking at its mode or result.json."
        ),
        items=gold[:items],
        ratings=rated[:reports],
    )


def measure(run_dir: Path, gold: GoldFile) -> AgreementSummary:
    judge_answers: dict[str, str] = {}
    judge_model = ""
    rewards: dict[str, float] = {}
    for folder in episodes(run_dir):
        name = str(folder.relative_to(run_dir))
        result = EpisodeResult.model_validate_json((folder / "result.json").read_text(encoding="utf-8"))
        judge_model = judge_model or result.judge_model
        rewards[name] = result.episode_reward.total
        grading = Grading.model_validate_json((folder / "grading.json").read_text(encoding="utf-8"))
        for n, answer in enumerate(grading.key_facts_established):
            judge_answers[f"{name}#fact{n}"] = "yes" if answer else "no"
        for f, finding in enumerate(grading.findings):
            for a, atom in enumerate(finding.atomic_facts):
                judge_answers[f"{name}#finding{f}.{a}"] = "yes" if atom.supported else "no"
    agreements = []
    for kind in ("key_fact", "atomic_fact"):
        items = [item for item in gold.items if item.kind == kind]
        labelled = [item for item in items if item.human and item.key in judge_answers]
        agreements.append(
            Agreement(
                kind=kind,
                labelled=len(labelled),
                unlabelled=len(items) - len(labelled),
                kappa=stats.cohen_kappa(
                    [item.human.strip().lower() for item in labelled if item.human],
                    [judge_answers[item.key] for item in labelled],
                ),
            )
        )
    rated = [r for r in gold.ratings if r.human_rating is not None and r.episode in rewards]
    return AgreementSummary(
        judge_model=judge_model,
        agreements=agreements,
        rated_reports=len(rated),
        reward_vs_rating_spearman=stats.spearman(
            [rewards[r.episode] for r in rated], [float(r.human_rating or 0) for r in rated]
        ),
    )
