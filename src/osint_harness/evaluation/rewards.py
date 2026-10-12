import math
from typing import ClassVar

from pydantic import BaseModel


class StepReward(BaseModel):
    """Reward for one research round: did it move belief toward the truth, and did it do so efficiently?

    progress      change in probability mass on an acceptable verdict (outcome, needs ground truth)
    information   1 - exp(-w/2), w = summed weight of new non-context evidence (diminishing returns)
    corroboration new independent publishers this round / 3, capped at 1
    redundancy    share of returned sources already in the case file
    tool_failure  share of tool calls that failed
    cost          tokens this round / 20k, capped at 1
    """

    step: int
    progress: float
    information: float
    corroboration: float
    redundancy: float
    tool_failure: float
    cost: float

    PROGRESS_WEIGHT: ClassVar[float] = 0.5
    INFORMATION_WEIGHT: ClassVar[float] = 0.2
    CORROBORATION_WEIGHT: ClassVar[float] = 0.15
    REDUNDANCY_PENALTY: ClassVar[float] = 0.1
    TOOL_FAILURE_PENALTY: ClassVar[float] = 0.05
    COST_PENALTY: ClassVar[float] = 0.05

    @classmethod
    def measure(
        cls,
        step: int,
        p_correct_before: float,
        p_correct_after: float,
        new_evidence_weight: float,
        new_domains: int,
        returned: int,
        duplicates: int,
        tool_calls: int,
        tool_failures: int,
        tokens: int,
    ) -> "StepReward":
        return cls(
            step=step,
            progress=p_correct_after - p_correct_before,
            information=1 - math.exp(-new_evidence_weight / 2),
            corroboration=min(1.0, new_domains / 3),
            redundancy=duplicates / returned if returned else 0.0,
            tool_failure=tool_failures / tool_calls if tool_calls else 0.0,
            cost=min(1.0, tokens / 20_000),
        )

    @property
    def process(self) -> float:
        """The ground-truth-free part: what an agent could optimise online."""
        return (
            self.INFORMATION_WEIGHT * self.information
            + self.CORROBORATION_WEIGHT * self.corroboration
            - self.REDUNDANCY_PENALTY * self.redundancy
            - self.TOOL_FAILURE_PENALTY * self.tool_failure
            - self.COST_PENALTY * self.cost
        )

    @property
    def total(self) -> float:
        return self.PROGRESS_WEIGHT * self.progress + self.process


class EpisodeReward(BaseModel):
    """Reward for a whole investigation.

    correctness        1 if the verdict is acceptable for the case, else 0
    key_fact_recall    share of ground-truth key facts the report establishes (judge)
    citation_precision share of findings whose cited excerpts support them (judge)
    calibration        1 - (confidence - correctness)^2, i.e. one minus the Brier score
    cost               tokens / 150k, capped at 1
    """

    correctness: float
    key_fact_recall: float
    citation_precision: float
    calibration: float
    cost: float

    CORRECTNESS_WEIGHT: ClassVar[float] = 0.4
    RECALL_WEIGHT: ClassVar[float] = 0.2
    CITATION_WEIGHT: ClassVar[float] = 0.15
    CALIBRATION_WEIGHT: ClassVar[float] = 0.15
    COST_PENALTY: ClassVar[float] = 0.1

    @classmethod
    def measure(
        cls, correct: bool, confidence: float, key_fact_recall: float, citation_precision: float, tokens: int
    ) -> "EpisodeReward":
        correctness = float(correct)
        return cls(
            correctness=correctness,
            key_fact_recall=key_fact_recall,
            citation_precision=citation_precision,
            calibration=1 - (confidence - correctness) ** 2,
            cost=min(1.0, tokens / 150_000),
        )

    @property
    def total(self) -> float:
        return (
            self.CORRECTNESS_WEIGHT * self.correctness
            + self.RECALL_WEIGHT * self.key_fact_recall
            + self.CITATION_WEIGHT * self.citation_precision
            + self.CALIBRATION_WEIGHT * self.calibration
            - self.COST_PENALTY * self.cost
        )
