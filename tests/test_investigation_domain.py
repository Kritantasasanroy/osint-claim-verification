import json
from collections.abc import Callable

import pytest

from osint_harness.investigation.case_file import CaseFile
from osint_harness.investigation.evidence import Evidence, Stance, Strength
from osint_harness.investigation.inquiry import Inquiry, InquiryOutcome, Step, ToolName
from osint_harness.investigation.report import Coverage, Finding, Report
from osint_harness.investigation.source import DomainCatalogue, ResolvedBy, Source, SourceTier, TrackRecord
from osint_harness.investigation.subject import Subject
from osint_harness.investigation.verdict import Belief, SubjectKind, Verdict

type EvidenceMaker = Callable[[str, str, Stance, float], Evidence]


@pytest.fixture
def evidence() -> EvidenceMaker:
    def make(question_id: str, domain: str, stance: Stance, reliability: float = 0.9) -> Evidence:
        return Evidence(
            question_id, f"https://{domain}/a", domain, "s", "q", stance, Strength.DIRECT, reliability, 1
        )

    return make


def test_belief_normalises_over_the_verdicts_the_subject_kind_allows() -> None:
    belief = Belief.over(SubjectKind.PERSON, {Verdict.ADVERSE: 3, Verdict.NO_ADVERSE: 1}, Verdict.ADVERSE)

    assert belief.verdict is Verdict.ADVERSE
    assert belief.confidence == pytest.approx(0.75)
    assert belief.probability_of(Verdict.UNVERIFIABLE) == 0.0


@pytest.mark.parametrize(
    "scores",
    [{Verdict.TRUE: 1.0, Verdict.ADVERSE: 0.5}, {}],
    ids=["a verdict the kind does not allow", "no probability at all"],
)
def test_a_belief_refuses_to_invent_or_redistribute_probability(scores: dict[Verdict, float]) -> None:
    with pytest.raises(ValueError, match="positive scores"):
        Belief.over(SubjectKind.PERSON, scores, Verdict.ADVERSE)


@pytest.mark.parametrize(
    ("url", "tier"),
    [
        ("https://www.sec.gov/filing", SourceTier.OFFICIAL),
        ("https://www.nasa.gov/moon", SourceTier.OFFICIAL),
        ("https://www.reuters.com/x", SourceTier.MAJOR_NEWS),
        ("https://en.wikipedia.org/wiki/Wirecard", SourceTier.REFERENCE),
        ("https://cs.stanford.edu/x", SourceTier.REFERENCE),
        ("https://randomblog.example/p", SourceTier.UNVETTED),
        ("https://randomblog.substack.com/p", SourceTier.USER_GENERATED),
        ("https://www.youtube.com/watch?v=1", SourceTier.USER_GENERATED),
        ("https://www.gov.uk/x", SourceTier.OFFICIAL),
        ("https://www.mca.gov.in/x", SourceTier.OFFICIAL),
    ],
)
def test_publisher_tier_comes_from_its_domain(url: str, tier: SourceTier) -> None:
    assert Source.from_web(url, "t", "c").tier is tier


def test_lookalike_domain_is_not_trusted() -> None:
    assert DomainCatalogue.tier_of("notreuters.com") is SourceTier.UNVETTED


def test_track_record_moves_reliability_away_from_the_prior() -> None:
    prior = SourceTier.UNVETTED.prior_reliability

    assert TrackRecord().reliability(prior) == pytest.approx(prior)
    assert TrackRecord(corroborated=8).reliability(prior) > prior
    assert TrackRecord(contradicted=8).reliability(prior) < prior


def test_a_publisher_counts_once_and_opposing_independent_weight_is_a_conflict(
    evidence: EvidenceMaker,
) -> None:
    case = CaseFile(Subject(SubjectKind.CLAIM, "X happened"))
    question = case.raise_question("Did X happen?")
    for item in [
        evidence(question.id, "reuters.com", Stance.SUPPORTS, 0.9),
        evidence(question.id, "reuters.com", Stance.SUPPORTS, 0.9),
        evidence(question.id, "bbc.com", Stance.REFUTES, 0.6),
    ]:
        case.record_evidence(item)

    assert case.balance(question.id).support_weight == pytest.approx(0.9)
    assert [conflict.question.id for conflict in case.conflicts] == [question.id]
    assert case.independent_domains == {"reuters.com"}


@pytest.mark.parametrize(
    ("supporters", "refuter_reliability"),
    [(["reuters.com"], 0.4), (["justice.gov", "npr.org", "apnews.com"], 0.75)],
    ids=["weak opposition", "lopsided dissent"],
)
def test_one_sided_weight_is_not_a_conflict(
    evidence: EvidenceMaker, supporters: list[str], refuter_reliability: float
) -> None:
    case = CaseFile(Subject(SubjectKind.COMPANY, "Theranos"))
    question = case.raise_question("Was anyone convicted?")
    for domain in supporters:
        case.record_evidence(evidence(question.id, domain, Stance.SUPPORTS, 0.9))
    case.record_evidence(evidence(question.id, "dissent.example", Stance.REFUTES, refuter_reliability))

    assert case.conflicts == []


def test_steps_carry_the_inquiries_and_the_belief_they_ended_on() -> None:
    case = CaseFile(Subject(SubjectKind.CLAIM, "X happened"))
    source = Source.from_web("https://www.reuters.com/a", "t", "c")
    found = Inquiry(ToolName.NEWS_SEARCH, "x", "Q1", 1, (source,), 0.5)
    failed = Inquiry(ToolName.READ_PAGE, "y", "Q1", 2, (), 0.1, failure="HTTP 500")
    empty = Inquiry(ToolName.ENCYCLOPEDIA, "z", "Q1", 2, (), 0.1)
    belief = Belief.over(SubjectKind.CLAIM, {Verdict.TRUE: 1.0}, Verdict.TRUE)

    case.record_step(Step(1, (found,), belief))
    case.record_step(Step(2, (failed, empty), belief))

    assert [i.outcome for i in case.inquiries_from_step(1)] == [
        InquiryOutcome.FOUND,
        InquiryOutcome.FAILED,
        InquiryOutcome.EMPTY,
    ]
    assert case.inquiries_from_step(2) == [failed, empty]
    assert case.beliefs == [belief, belief]


def test_sources_are_filed_once_and_questions_close_once() -> None:
    case = CaseFile(Subject(SubjectKind.COMPANY, "Wirecard AG"))
    source = Source.from_web("https://reuters.com/a", "t", "c")
    question = case.raise_question("Who audited it?")

    question.answer()
    question.drop()

    assert case.file_source(source) is True
    assert case.file_source(source) is False
    assert not question.is_open
    assert question.status.value == "answered"


def test_report_drops_citations_it_never_retrieved_and_turns_uncited_findings_into_gaps() -> None:
    case = CaseFile(Subject(SubjectKind.CLAIM, "Wirecard was audited by EY"))
    case.file_source(Source.from_web("https://www.reuters.com/a", "EY audit", "c"))
    belief = Belief.over(SubjectKind.CLAIM, {Verdict.TRUE: 0.9, Verdict.FALSE: 0.1}, Verdict.TRUE)

    report = Report.assemble(
        case,
        belief,
        summary="EY audited Wirecard.",
        findings=[
            Finding("EY was the auditor", ("https://www.reuters.com/a", "https://made.up/x")),
            Finding("KPMG did a special audit", ("https://made.up/y",)),
        ],
        conflicts=[],
        gaps=[],
        tracks={},
        coverage=Coverage({}, frozenset()),
    )

    assert report.verdict is Verdict.TRUE
    assert [f.citations for f in report.findings] == [("https://www.reuters.com/a",)]
    assert any("KPMG" in gap for gap in report.gaps)
    assert "[1B]" in report.to_markdown()
    assert json.loads(report.to_json())["sources"][0]["tier"] == "major_news"


def test_a_tie_is_settled_by_the_analysts_choice_not_by_list_order() -> None:
    scores = {Verdict.TRUE: 0.4, Verdict.MIXED: 0.4, Verdict.FALSE: 0.2}

    belief = Belief.over(SubjectKind.CLAIM, scores, Verdict.MIXED)

    assert (belief.verdict, belief.confidence) == (Verdict.MIXED, pytest.approx(0.4))
    with pytest.raises(ValueError, match="not among the most probable"):
        Belief.over(SubjectKind.CLAIM, scores, Verdict.FALSE)


def test_the_analysts_upload_is_not_an_independent_publisher(evidence: EvidenceMaker) -> None:
    case = CaseFile(Subject(SubjectKind.CLAIM, "X happened"))
    question = case.raise_question("Did X happen?")
    upload = Evidence(
        question.id,
        "upload://memo.pdf",
        "memo.pdf",
        "s",
        "q",
        Stance.SUPPORTS,
        Strength.DIRECT,
        0.5,
        CaseFile.UPLOAD_STEP,
    )
    case.record_evidence(upload)
    case.record_evidence(evidence(question.id, "reuters.com", Stance.SUPPORTS, 0.9))
    confident = Belief.over(SubjectKind.CLAIM, {Verdict.TRUE: 0.9, Verdict.FALSE: 0.1}, Verdict.TRUE)

    assert case.independent_domains == {"reuters.com"}
    assert not case.is_settled(confident)
    assert all(
        outcome.domain != "memo.pdf"
        for outcome in case.publisher_outcomes(Verdict.TRUE, ResolvedBy.BENCHMARK_LABEL)
    )


def test_the_report_lists_computed_conflicts_even_when_the_reporter_names_none(
    evidence: EvidenceMaker,
) -> None:
    case = CaseFile(Subject(SubjectKind.CLAIM, "X happened"))
    question = case.raise_question("Did X happen?")
    case.record_evidence(evidence(question.id, "reuters.com", Stance.SUPPORTS, 0.9))
    case.record_evidence(evidence(question.id, "bbc.com", Stance.REFUTES, 0.8))
    belief = Belief.over(SubjectKind.CLAIM, {Verdict.MIXED: 1.0}, Verdict.MIXED)

    report = Report.assemble(
        case, belief, "Contested.", [], conflicts=[], gaps=[], tracks={}, coverage=Coverage({}, frozenset())
    )

    assert len(report.conflicts) == 1 and "Did X happen?" in report.conflicts[0]
    assert "No open conflict" not in report.to_markdown()


def test_an_upload_opposed_by_one_outlet_is_not_a_conflict(evidence: EvidenceMaker) -> None:
    case = CaseFile(Subject(SubjectKind.CLAIM, "X happened"))
    question = case.raise_question("Did X happen?")
    case.record_evidence(
        Evidence(
            question.id,
            "upload://memo.pdf/page 1 part 1",
            "memo.pdf",
            "s",
            "q",
            Stance.SUPPORTS,
            Strength.DIRECT,
            0.5,
            CaseFile.UPLOAD_STEP,
        )
    )
    case.record_evidence(evidence(question.id, "reuters.com", Stance.REFUTES, 0.85))

    assert case.conflicts == []


def test_an_inquiry_cannot_both_find_sources_and_fail() -> None:
    source = Source.from_web("https://www.reuters.com/a", "t", "c")

    with pytest.raises(ValueError, match="not both"):
        Inquiry(ToolName.NEWS_SEARCH, "x", "Q1", 1, (source,), 0.1, failure="HTTP 500")


def test_every_agent_and_the_judge_read_the_same_window_of_a_source() -> None:
    long_page = "a" * (Source.READ_WINDOW + 500)

    assert len(Source.from_web("https://www.reuters.com/a", "t", long_page).content) == Source.READ_WINDOW


def test_a_publisher_on_both_sides_counts_once_on_its_heavier_side(evidence: EvidenceMaker) -> None:
    case = CaseFile(Subject(SubjectKind.CLAIM, "X happened"))
    question = case.raise_question("Did X happen?")
    case.record_evidence(evidence(question.id, "reuters.com", Stance.SUPPORTS, 0.85))
    case.record_evidence(evidence(question.id, "reuters.com", Stance.REFUTES, 0.85))
    case.record_evidence(evidence(question.id, "bbc.com", Stance.SUPPORTS, 0.9))
    case.record_evidence(evidence(question.id, "bbc.com", Stance.REFUTES, 0.3))

    balance = case.balance(question.id)

    assert (balance.supporting, balance.refuting) == ({"bbc.com": 0.9}, {})
    assert case.conflicts == []


def test_a_self_contradicting_publisher_does_not_help_settle_the_case(evidence: EvidenceMaker) -> None:
    case = CaseFile(Subject(SubjectKind.CLAIM, "X happened"))
    question = case.raise_question("Did X happen?")
    case.record_evidence(evidence(question.id, "reuters.com", Stance.SUPPORTS, 0.85))
    case.record_evidence(evidence(question.id, "reuters.com", Stance.REFUTES, 0.85))
    case.record_evidence(evidence(question.id, "bbc.com", Stance.SUPPORTS, 0.9))
    confident = Belief.over(SubjectKind.CLAIM, {Verdict.TRUE: 0.9, Verdict.FALSE: 0.1}, Verdict.TRUE)

    assert case.independent_domains == {"bbc.com"}
    assert not case.is_settled(confident)


def test_a_weak_dissenter_does_not_corroborate(evidence: EvidenceMaker) -> None:
    case = CaseFile(Subject(SubjectKind.CLAIM, "X happened"))
    question = case.raise_question("Did X happen?")
    case.record_evidence(evidence(question.id, "reuters.com", Stance.SUPPORTS, 0.9))
    case.record_evidence(evidence(question.id, "blog.example", Stance.REFUTES, 0.3))
    confident = Belief.over(SubjectKind.CLAIM, {Verdict.TRUE: 0.9, Verdict.FALSE: 0.1}, Verdict.TRUE)

    assert case.independent_domains == {"reuters.com"}
    assert not case.is_settled(confident)
