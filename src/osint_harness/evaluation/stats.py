"""Uncertainty for every headline number: bootstrap intervals over cases (and seeds within cases), paired
tests for every comparison, and the calibration and selective-prediction measures used in the report."""

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel

RESAMPLES = 2000


class Estimate(BaseModel):
    """A mean with its 95% bootstrap interval and how many cases and samples it rests on."""

    mean: float
    low: float
    high: float
    cases: int
    samples: int

    def __str__(self) -> str:
        return f"{self.mean:.3f} [{self.low:.3f}, {self.high:.3f}]"

    def percent(self) -> str:
        return f"{self.mean:.0%} [{self.low:.0%}, {self.high:.0%}]"


def bootstrap(per_case: Sequence[Sequence[float]], seed: int = 0) -> Estimate:
    """Two-level bootstrap: resample cases, then seeds within each resampled case. `per_case` holds one list
    of values per case (one value per seed)."""
    groups = [np.asarray(values, dtype=float) for values in per_case if len(values)]
    if not groups:
        return Estimate(mean=float("nan"), low=float("nan"), high=float("nan"), cases=0, samples=0)
    rng = np.random.default_rng(seed)
    point = float(np.mean([g.mean() for g in groups]))
    # Pad cases to the same number of seeds (NaN), then resample cases and seeds-within-case at once.
    width = max(len(g) for g in groups)
    table = np.full((len(groups), width), np.nan)
    for i, g in enumerate(groups):
        table[i, : len(g)] = g
    counts = np.array([len(g) for g in groups])
    cases = rng.integers(0, len(groups), (RESAMPLES, len(groups)))
    draws = (rng.random((RESAMPLES, len(groups), width)) * counts[cases][..., None]).astype(int)
    picked = table[cases[..., None], draws]
    valid = np.arange(width)[None, None, :] < counts[cases][..., None]
    case_means = np.where(valid, picked, 0.0).sum(axis=2) / counts[cases]
    means = case_means.mean(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return Estimate(
        mean=point, low=float(low), high=float(high), cases=len(groups), samples=sum(len(g) for g in groups)
    )


class Comparison(BaseModel):
    """Treated minus baseline on the same cases: the bootstrap interval of the difference, an exact McNemar
    test on seed-majority correctness, and a paired permutation test on per-case mean correctness."""

    treated: str
    baseline: str
    difference: Estimate
    discordant_treated_better: int
    discordant_baseline_better: int
    mcnemar_p: float
    permutation_p: float

    @property
    def significant(self) -> bool:
        return self.mcnemar_p < 0.05 and self.permutation_p < 0.05


def compare(
    treated_name: str,
    baseline_name: str,
    treated: dict[str, list[float]],
    baseline: dict[str, list[float]],
    seed: int = 0,
) -> Comparison:
    cases = sorted(set(treated) & set(baseline))
    diffs = [[float(np.mean(treated[c]) - np.mean(baseline[c]))] for c in cases]
    majority_t = [bool(np.mean(treated[c]) > 0.5) for c in cases]
    majority_b = [bool(np.mean(baseline[c]) > 0.5) for c in cases]
    better = sum(1 for t, b in zip(majority_t, majority_b, strict=True) if t and not b)
    worse = sum(1 for t, b in zip(majority_t, majority_b, strict=True) if b and not t)
    return Comparison(
        treated=treated_name,
        baseline=baseline_name,
        difference=bootstrap(diffs, seed),
        discordant_treated_better=better,
        discordant_baseline_better=worse,
        mcnemar_p=mcnemar_exact(better, worse),
        permutation_p=paired_permutation([d[0] for d in diffs], seed),
    )


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact binomial test on the discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / math.pow(2, n)
    return min(1.0, 2 * tail)


def paired_permutation(differences: Sequence[float], seed: int = 0) -> float:
    """Sign-flip permutation test that the mean paired difference is zero."""
    d = np.asarray(differences, dtype=float)
    if len(d) == 0 or not np.any(d):
        return 1.0
    rng = np.random.default_rng(seed)
    observed = float(abs(d.mean()))
    signs = rng.choice([-1.0, 1.0], size=(RESAMPLES, len(d)))
    flipped = np.abs((signs * d).mean(axis=1))
    return float((np.sum(flipped >= observed - 1e-12) + 1) / (RESAMPLES + 1))


def stability(verdicts_by_case: dict[str, list[str]]) -> float:
    """Share of cases (with two or more seeds) whose verdict was the same in every seed."""
    repeated = [v for v in verdicts_by_case.values() if len(v) > 1]
    if not repeated:
        return float("nan")
    return sum(len(set(v)) == 1 for v in repeated) / len(repeated)


def brier(confidences: Sequence[float], correct: Sequence[bool]) -> float:
    return float(np.mean([(p - c) ** 2 for p, c in zip(confidences, correct, strict=True)]))


def ece(confidences: Sequence[float], correct: Sequence[bool], bins: int = 10) -> float:
    """Expected calibration error over equal-mass (adaptive) bins, robust when confidences cluster."""
    if not confidences:
        return float("nan")
    order = np.argsort(confidences)
    p = np.asarray(confidences, dtype=float)[order]
    y = np.asarray(correct, dtype=float)[order]
    total = 0.0
    for chunk_p, chunk_y in zip(np.array_split(p, bins), np.array_split(y, bins), strict=True):
        if len(chunk_p):
            total += len(chunk_p) / len(p) * abs(chunk_y.mean() - chunk_p.mean())
    return float(total)


@dataclass(frozen=True)
class RiskCoverage:
    coverage: list[float]
    risk: list[float]
    aurc: float


def risk_coverage(confidences: Sequence[float], correct: Sequence[bool]) -> RiskCoverage:
    """Answer only the most confident fraction of cases: the error rate at each coverage, and the area under
    that curve (lower is better), the standard selective-prediction measure."""
    if not confidences:
        return RiskCoverage([], [], float("nan"))
    order = np.argsort(-np.asarray(confidences, dtype=float), kind="stable")
    wrong = 1 - np.asarray(correct, dtype=float)[order]
    n = len(wrong)
    risk = np.cumsum(wrong) / np.arange(1, n + 1)
    coverage = np.arange(1, n + 1) / n
    return RiskCoverage(coverage.tolist(), risk.tolist(), float(np.mean(risk)))


def auroc(scores: Sequence[float], labels: Sequence[bool]) -> float:
    """Probability a random positive outranks a random negative (ties count half)."""
    pos = [s for s, y in zip(scores, labels, strict=True) if y]
    neg = [s for s, y in zip(scores, labels, strict=True) if not y]
    if not pos or not neg:
        return float("nan")
    wins = sum((p > q) + 0.5 * (p == q) for p in pos for q in neg)
    return wins / (len(pos) * len(neg))


def cohen_kappa(a: Sequence[str], b: Sequence[str]) -> float:
    n = len(a)
    if n == 0:
        return float("nan")
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n**2
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def spearman(x: Sequence[float], y: Sequence[float]) -> float:
    def ranks(values: Sequence[float]) -> np.ndarray:
        array = np.asarray(values, dtype=float)
        order = array.argsort()
        ranked = np.empty(len(array))
        ranked[order] = np.arange(len(array))
        for value in set(array.tolist()):
            tied = array == value
            ranked[tied] = ranked[tied].mean()
        return ranked

    if len(x) < 3:
        return float("nan")
    return float(np.corrcoef(ranks(x), ranks(y))[0, 1])


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    spread = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - spread, centre + spread
