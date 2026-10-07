from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class Verdict(StrEnum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    MIXED = "MIXED"
    ADVERSE = "ADVERSE"
    NO_ADVERSE = "NO_ADVERSE"
    UNVERIFIABLE = "UNVERIFIABLE"


class SubjectKind(StrEnum):
    COMPANY = "company"
    PERSON = "person"
    CLAIM = "claim"

    @property
    def allowed_verdicts(self) -> tuple[Verdict, ...]:
        if self is SubjectKind.CLAIM:
            return (Verdict.TRUE, Verdict.FALSE, Verdict.MIXED, Verdict.UNVERIFIABLE)
        return (Verdict.ADVERSE, Verdict.NO_ADVERSE, Verdict.UNVERIFIABLE)


@dataclass(frozen=True)
class Belief:
    """A probability distribution over the verdicts a subject kind allows, and the verdict chosen from it.

    The chosen verdict must be among the most probable ones, so a tie is resolved by the analyst, not by
    the order verdicts happen to be listed in.
    """

    verdict: Verdict
    probabilities: tuple[tuple[Verdict, float], ...]

    @classmethod
    def over(cls, kind: SubjectKind, scores: Mapping[Verdict, float], verdict: Verdict) -> "Belief":
        return cls.among(kind.allowed_verdicts, scores, verdict)

    @classmethod
    def among(
        cls, allowed: tuple[Verdict, ...], scores: Mapping[Verdict, float], verdict: Verdict
    ) -> "Belief":
        """The one rule for a belief: positive mass only on allowed verdicts, choosing a most probable one."""
        foreign = {v for v, score in scores.items() if score > 0} - set(allowed)
        total = sum(scores.get(v, 0.0) for v in allowed)
        if foreign or total <= 0:
            raise ValueError(f"a belief needs positive scores, and only on {[v.value for v in allowed]}")
        if verdict not in allowed or scores.get(verdict, 0.0) < max(scores.values()):
            raise ValueError(f"{verdict.value} is not among the most probable allowed verdicts")
        return cls(verdict, tuple((v, scores.get(v, 0.0) / total) for v in allowed))

    def with_confidence(self, confidence: float) -> "Belief":
        """The same verdict at a calibrated confidence. The rest is spread evenly over the other verdicts,
        and the confidence never drops below an even share, so the chosen verdict stays a most probable one.
        """
        allowed = [v for v, _ in self.probabilities]
        p = min(1.0, max(confidence, 1 / len(allowed)))
        rest = (1 - p) / (len(allowed) - 1) if len(allowed) > 1 else 0.0
        return Belief(self.verdict, tuple((v, p if v is self.verdict else rest) for v in allowed))

    @property
    def confidence(self) -> float:
        return self.probability_of(self.verdict)

    def probability_of(self, verdict: Verdict) -> float:
        return dict(self.probabilities).get(verdict, 0.0)
