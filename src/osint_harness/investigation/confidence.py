import json
import math
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import ClassVar

import numpy as np

from osint_harness.investigation.posterior import EvidencePosterior
from osint_harness.investigation.verdict import Belief, Verdict


@dataclass(frozen=True)
class ConfidenceInputs:
    """Everything the shipped confidence is computed from, persisted on each step so it can be audited and
    the calibrator refitted: the model's own probability is one input among four, never the output."""

    llm_probability: float
    posterior_probability: float
    independent_supporters: int
    authoritative_support: bool

    def features(self) -> list[float]:
        return [
            self._logit(self.llm_probability),
            self._logit(self.posterior_probability),
            min(self.independent_supporters, 5) / 5,
            float(self.authoritative_support),
        ]

    @staticmethod
    def _logit(p: float) -> float:
        p = min(max(p, 1e-3), 1 - 1e-3)
        return math.log(p / (1 - p))


@dataclass(frozen=True)
class ConfidenceCalibrator:
    """Turns ConfidenceInputs into P(the chosen verdict is correct).

    The evidence is a brake, not a steering wheel. The model chooses the verdict (it reads the claim; the
    posterior only counts labelled evidence). The confidence in that verdict is then, unfitted (the default
    until a dev split has been run), the evidence posterior's probability *of the model's verdict*, so a
    model saying 99% over two weak sources ships about 60%, and a model whose verdict the evidence does not
    back ships low and cannot close the case: it keeps researching. Fitted, the confidence is a logistic
    regression on the four inputs, learned on the dev split only, under benchmark/calibration/.

    Two alternatives were tried and rejected. Pooling the confidence (geometric mean, renormalised) still
    shipped 90% on two weak sources. Pooling the verdict let mislabelled evidence overturn a correct model
    verdict: live run H4 (Do Kwon) went to TRUE 85% when the model said FALSE 78%, because the Evaluator had
    labelled answers to follow-up questions as TRUE (tests/test_remediation.py replays it).
    """

    weights: tuple[float, ...] = ()
    bias: float = 0.0
    fitted_on: str = ""

    @property
    def is_fitted(self) -> bool:
        return bool(self.weights)

    def ship(
        self,
        llm: Belief,
        posterior: EvidencePosterior,
        support: Callable[[Verdict], tuple[int, bool]],
    ) -> tuple[Belief, ConfidenceInputs]:
        """The belief a step ships, and the inputs its confidence was computed from. `support` says, for the
        chosen verdict, how many independent publishers back it and whether one is authoritative."""
        verdict = llm.verdict
        supporters, authoritative = support(verdict)
        inputs = ConfidenceInputs(
            llm_probability=llm.probability_of(verdict),
            posterior_probability=posterior.probability_of(verdict),
            independent_supporters=supporters,
            authoritative_support=authoritative,
        )
        return llm.with_confidence(self.confidence(inputs)), inputs

    CEILING: ClassVar[float] = 0.99

    def confidence(self, inputs: ConfidenceInputs) -> float:
        """Never 100%: independent-looking sources can share an error the posterior cannot see."""
        if not self.is_fitted:
            return min(self.CEILING, inputs.posterior_probability)
        z = self.bias + sum(w * x for w, x in zip(self.weights, inputs.features(), strict=True))
        return min(self.CEILING, 1 / (1 + math.exp(-z)))

    @classmethod
    def fit(cls, rows: list[tuple[ConfidenceInputs, bool]], fitted_on: str) -> "ConfidenceCalibrator":
        """L2-regularised logistic regression by gradient descent: small n, four features, no extra deps."""
        x = np.array([inputs.features() for inputs, _ in rows], dtype=float)
        y = np.array([float(correct) for _, correct in rows], dtype=float)
        w, b = np.zeros(x.shape[1]), 0.0
        for _ in range(5000):
            p = 1 / (1 + np.exp(-(x @ w + b)))
            w -= 0.1 * (x.T @ (p - y) / len(y) + 0.01 * w)
            b -= 0.1 * float(np.mean(p - y))
        return cls(tuple(float(v) for v in w), float(b), fitted_on)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "ConfidenceCalibrator":
        if not path.exists():
            return cls()
        record = json.loads(path.read_text(encoding="utf-8"))
        return cls(tuple(record["weights"]), float(record["bias"]), str(record["fitted_on"]))
