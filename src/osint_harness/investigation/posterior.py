import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import ClassVar

from osint_harness.investigation.evidence import Evidence
from osint_harness.investigation.verdict import Verdict


@dataclass(frozen=True)
class EvidencePosterior:
    """A distribution over the allowed verdicts computed from the evidence weights alone, never from what a
    model says it believes. Log-odds against a uniform prior, with K = 1.5 per unit of weight:

    - each *independent* item (the heaviest per publisher cluster and verdict) adds K x weight to the verdict
      it points to; weight = reliability x strength (x 0.5 if stale), at most 1;
    - for a company or person, each independent identity confirmation adds K x weight to both ADVERSE and
      NO_ADVERSE (an identified entity is not UNVERIFIABLE), capped at 1.5 units in all;
    - an adverse screen that ran and found nothing material adds K x screened (0..1) to NO_ADVERSE: absence
      of evidence counts only where someone looked.

    So two 0.40 sources lift ADVERSE to about 0.6, while three direct major-publisher items take a verdict
    past 0.9.
    """

    probabilities: tuple[tuple[Verdict, float], ...]
    supporters: tuple[tuple[Verdict, int], ...]

    K: ClassVar[float] = 1.5
    IDENTITY_CAP: ClassVar[float] = 1.5

    @classmethod
    def of(
        cls,
        allowed: tuple[Verdict, ...],
        evidence: Iterable[Evidence],
        publisher: Callable[[Evidence], str],
        weigh: Callable[[Evidence], float] = lambda item: item.weight,
        identity: Iterable[float] = (),
        screened: float = 0.0,
    ) -> "EvidencePosterior":
        heaviest: dict[tuple[Verdict, str], float] = {}
        for item in evidence:
            verdict = item.direction
            if verdict is None or verdict not in allowed:
                continue
            key = (verdict, publisher(item))
            heaviest[key] = max(heaviest.get(key, 0.0), min(1.0, weigh(item)))
        log_odds = dict.fromkeys(allowed, 0.0)
        counts = dict.fromkeys(allowed, 0)
        for (verdict, _), weight in heaviest.items():
            log_odds[verdict] += cls.K * weight
            counts[verdict] += 1
        if Verdict.NO_ADVERSE in allowed:
            identified = cls.K * min(cls.IDENTITY_CAP, sum(min(1.0, w) for w in identity))
            log_odds[Verdict.ADVERSE] += identified
            log_odds[Verdict.NO_ADVERSE] += identified + cls.K * min(1.0, max(0.0, screened))
        top = max(log_odds.values())
        unnormalised = {v: math.exp(score - top) for v, score in log_odds.items()}
        total = sum(unnormalised.values())
        return cls(
            tuple((v, unnormalised[v] / total) for v in allowed),
            tuple((v, counts[v]) for v in allowed),
        )

    def probability_of(self, verdict: Verdict) -> float:
        return dict(self.probabilities).get(verdict, 0.0)

    def independent_supporters(self, verdict: Verdict) -> int:
        return dict(self.supporters).get(verdict, 0)
