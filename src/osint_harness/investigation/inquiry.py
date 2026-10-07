from dataclasses import dataclass
from enum import StrEnum

from osint_harness.investigation.confidence import ConfidenceInputs
from osint_harness.investigation.posterior import EvidencePosterior
from osint_harness.investigation.source import Source
from osint_harness.investigation.verdict import Belief


class ToolName(StrEnum):
    WEB_SEARCH = "web_search"
    NEWS_SEARCH = "news_search"
    READ_PAGE = "read_page"
    ENCYCLOPEDIA = "encyclopedia"
    WIKIDATA = "wikidata"
    GLEIF = "gleif"
    SEC_EDGAR = "sec_edgar"
    COURT_RECORDS = "court_records"
    WAYBACK = "wayback"
    SANCTIONS = "sanctions"


class InquiryOutcome(StrEnum):
    FOUND = "found"
    EMPTY = "empty"
    FAILED = "failed"


@dataclass(frozen=True)
class Inquiry:
    """One research action and what it returned. `failure` is None when the tool answered, even if emptily."""

    tool: ToolName
    argument: str
    question_id: str
    step: int
    sources: tuple[Source, ...]
    latency_s: float
    failure: str | None = None

    def __post_init__(self) -> None:
        if self.failure is not None and self.sources:
            raise ValueError("an inquiry either returned sources or failed, not both")

    @property
    def outcome(self) -> InquiryOutcome:
        if self.failure is not None:
            return InquiryOutcome.FAILED
        return InquiryOutcome.FOUND if self.sources else InquiryOutcome.EMPTY


@dataclass(frozen=True)
class Step:
    """One research round: the inquiries made and the belief the round ended on.

    `belief` is what the harness ships: the model's distribution pooled with the evidence posterior, at the
    calibrated confidence. The model's own belief, the posterior and the calibrator's inputs are kept beside
    it, so every confidence number can be traced back to where it came from.
    """

    number: int
    inquiries: tuple[Inquiry, ...]
    belief: Belief
    llm_belief: Belief | None = None
    posterior: EvidencePosterior | None = None
    inputs: ConfidenceInputs | None = None
