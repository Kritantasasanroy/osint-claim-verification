import asyncio
import json
from collections.abc import Callable
from datetime import date
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from fakes import FakeServices, Handler
from osint_harness.agents.briefing import CaseBriefing
from osint_harness.agents.reflector import Reflection
from osint_harness.harness import Harness
from osint_harness.investigation.case_file import CaseFile, MemoryMode
from osint_harness.investigation.evidence import Evidence, Stance, Strength
from osint_harness.investigation.inquiry import Inquiry, Step, ToolName
from osint_harness.investigation.source import Source
from osint_harness.investigation.subject import Subject
from osint_harness.investigation.verdict import Belief, SubjectKind, Verdict
from osint_harness.investigator import Budget, StopReason
from osint_harness.nvidia import NvidiaChat
from osint_harness.settings import Settings
from osint_harness.trace import TraceEventKind, TraceLog
from osint_harness.transport import Transport


@pytest.fixture
def harness_with(
    settings: Settings, make_transport: Callable[[Handler], Transport]
) -> Callable[[FakeServices], Harness]:
    return lambda services: services.harness(settings, make_transport)


@pytest.fixture
def reflection_fields() -> dict[str, object]:
    return {
        "critique": "Independent sources agree on the core facts and no open conflict remains.",
        "verdict": "TRUE",
        "verdict_scores": [{"verdict": "TRUE", "probability": 0.9}, {"verdict": "FALSE", "probability": 0.1}],
        "answered_question_ids": [],
        "dropped_question_ids": [],
        "follow_up_questions": [],
        "distrusted_memory_ids": [],
        "decision": "continue",
    }


def test_investigation_concludes_with_a_cited_report_steps_and_a_full_trace(
    tmp_path: Path, harness_with: Callable[[FakeServices], Harness]
) -> None:
    services = FakeServices([FakeServices.REUTERS, FakeServices.FT])
    investigator = harness_with(services).investigator(MemoryMode.SHORT, tmp_path / "m", Budget(max_steps=3))
    trace = TraceLog(tmp_path / "run" / "trace.jsonl", "run-1")

    subject = asyncio.run(investigator.scope("Was Wirecard audited by EY?", (), trace, date(2026, 10, 1)))
    investigation = asyncio.run(investigator.investigate(subject, trace))

    assert investigation.report.verdict is Verdict.TRUE
    assert investigation.stop_reason is StopReason.CONCLUDED
    assert [step.number for step in investigation.case_file.steps] == [1]
    assert investigation.tool_calls == 1
    assert investigation.report.findings[0].citations == (FakeServices.REUTERS,)
    assert {e.kind for e in TraceLog.read(trace.path)} >= {
        TraceEventKind.SCOPED,
        TraceEventKind.PLANNED,
        TraceEventKind.TOOL_CALLED,
        TraceEventKind.EVIDENCE_ASSESSED,
        TraceEventKind.REFLECTED,
        TraceEventKind.CRITIQUED,
        TraceEventKind.REPORTED,
    }
    # scope, plan, research, assess, reflect, red-team critic, report
    assert investigation.usage.prompt_tokens == 100 * 7
    assert subject.as_of == date(2026, 10, 1)
    assert investigation.wall_clock_s > 0


def test_a_single_publisher_never_settles_the_case(
    tmp_path: Path, harness_with: Callable[[FakeServices], Harness]
) -> None:
    investigator = harness_with(FakeServices([FakeServices.REUTERS])).investigator(
        MemoryMode.SHORT, tmp_path / "m", Budget(max_steps=2)
    )
    subject = Subject(SubjectKind.CLAIM, "Wirecard was audited by EY")

    investigation = asyncio.run(investigator.investigate(subject, TraceLog(tmp_path / "t.jsonl", "run-2")))

    assert investigation.stop_reason is StopReason.STEP_BUDGET
    assert len(investigation.case_file.steps) == 2


def test_long_term_memory_carries_facts_forward_and_its_cost_is_logged(
    tmp_path: Path, harness_with: Callable[[FakeServices], Harness]
) -> None:
    services = FakeServices([FakeServices.REUTERS, FakeServices.FT])
    harness = harness_with(services)
    memory_path = tmp_path / "long.sqlite3"
    subject = Subject(SubjectKind.CLAIM, "Wirecard was audited by EY")

    asyncio.run(
        harness.investigator(MemoryMode.LONG, memory_path, Budget()).investigate(
            subject, TraceLog(tmp_path / "a.jsonl", "run-a")
        )
    )
    second_trace = TraceLog(tmp_path / "b.jsonl", "run-b")
    second = asyncio.run(
        harness.investigator(MemoryMode.LONG, memory_path, Budget()).investigate(subject, second_trace)
    )

    recalled_event = next(e for e in second_trace.events if e.kind is TraceEventKind.MEMORY_RECALLED)
    assert any("auditor was EY" in r.record.text for r in second.recollections)
    assert "auditor was EY" in services.prompts["Plan"][-1]
    assert recalled_event.prompt_tokens == FakeServices.EMBEDDING_TOKENS


@pytest.mark.parametrize(("mode", "sees_step_one"), [(MemoryMode.NONE, False), (MemoryMode.SHORT, True)])
def test_without_memory_nothing_from_earlier_steps_reaches_the_agents(
    mode: MemoryMode, sees_step_one: bool
) -> None:
    case = CaseFile(Subject(SubjectKind.CLAIM, "X"))
    question = case.raise_question("Q?")
    old = Source.from_web("https://www.reuters.com/old", "Old report", "c")
    other = Source.from_web("https://www.bbc.com/old", "Other report", "d")
    for source, stance in [(old, Stance.SUPPORTS), (other, Stance.REFUTES)]:
        case.file_source(source)
        case.record_evidence(
            Evidence(
                question.id, source.url, source.domain, "old fact", "q", stance, Strength.DIRECT, 0.9, step=1
            )
        )
    failed = Inquiry(ToolName.READ_PAGE, "https://x", "Q1", 1, (), 0.2, failure="HTTP 500")
    found = Inquiry(ToolName.NEWS_SEARCH, "old query", "Q1", 1, (old,), 0.4)
    case.record_step(
        Step(1, (found, failed), Belief.over(SubjectKind.CLAIM, {Verdict.MIXED: 1.0}, Verdict.MIXED))
    )

    briefing = CaseBriefing(case, mode.visible_from(2))

    assert ("old fact" in briefing.evidence) is sees_step_one
    assert ("Q1" in briefing.conflicts) is sees_step_one
    assert (old.url in briefing.readable_urls) is sees_step_one
    assert ("old query" in briefing.inquiries) is sees_step_one
    assert ("MIXED" in briefing.belief_history) is sees_step_one
    assert ("failed" in briefing.inquiries and "HTTP 500" in briefing.inquiries) is sees_step_one


def test_a_reflection_needs_some_probability(reflection_fields: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Reflection.model_validate({**reflection_fields, "verdict_scores": []})
    with pytest.raises(ValidationError, match="positive scores"):
        Reflection.model_validate(
            {
                **reflection_fields,
                "verdict_scores": [
                    {"verdict": "TRUE", "probability": 0},
                    {"verdict": "FALSE", "probability": 0},
                ],
            }
        )


def test_a_reflection_whose_scores_contradict_its_verdict_is_rejected(
    reflection_fields: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="FALSE is not among the most probable"):
        Reflection.model_validate({**reflection_fields, "verdict": "FALSE"})


def test_a_reflection_may_only_use_its_subject_kinds_verdicts(reflection_fields: dict[str, object]) -> None:
    person = Reflection.for_kind(SubjectKind.PERSON)

    with pytest.raises(ValidationError, match="only on"):
        person.model_validate(reflection_fields)
    assert Reflection.for_kind(SubjectKind.CLAIM).model_validate(reflection_fields).verdict is Verdict.TRUE


def test_a_reflection_may_choose_either_side_of_a_tie(reflection_fields: dict[str, object]) -> None:
    tied = [{"verdict": "TRUE", "probability": 0.4}, {"verdict": "MIXED", "probability": 0.4}]

    reflection = Reflection.model_validate({**reflection_fields, "verdict": "MIXED", "verdict_scores": tied})

    assert reflection.verdict is Verdict.MIXED


def test_a_reflection_that_scores_a_verdict_twice_is_rejected(reflection_fields: dict[str, object]) -> None:
    repeated = [
        {"verdict": "TRUE", "probability": 0.6},
        {"verdict": "FALSE", "probability": 0.3},
        {"verdict": "TRUE", "probability": 0.1},
    ]

    with pytest.raises(ValidationError, match="only once"):
        Reflection.for_kind(SubjectKind.CLAIM).model_validate(
            {**reflection_fields, "verdict_scores": repeated}
        )


def test_the_analysts_own_documents_stay_visible_without_memory() -> None:
    case = CaseFile(Subject(SubjectKind.CLAIM, "X"))
    question = case.raise_question("Q?")
    case.record_evidence(
        Evidence(
            question.id,
            "upload://memo.pdf",
            "memo.pdf",
            "uploaded fact",
            "q",
            Stance.SUPPORTS,
            Strength.DIRECT,
            0.5,
            step=CaseFile.UPLOAD_STEP,
        )
    )

    assert "uploaded fact" in CaseBriefing(case, MemoryMode.NONE.visible_from(3)).evidence


def test_the_model_is_offered_only_the_subject_kinds_verdicts(
    settings: Settings, make_transport: Callable[[Handler], Transport], reflection_fields: dict[str, object]
) -> None:
    offered: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        schema = json.loads(request.content)["response_format"]["json_schema"]["schema"]
        offered.append(schema["$defs"]["Verdict"]["enum"])
        reply = {"choices": [{"message": {"content": json.dumps(reflection_fields)}}], "usage": {}}
        return httpx.Response(200, json=reply)

    chat = NvidiaChat(make_transport(handler), settings)
    asyncio.run(chat.ask("system", "user", Reflection.for_kind(SubjectKind.CLAIM)))

    assert offered == [["TRUE", "FALSE", "MIXED", "UNVERIFIABLE"]]


def test_asking_with_a_misdeclared_enum_fails_before_any_call(
    settings: Settings, make_transport: Callable[[Handler], Transport]
) -> None:
    class Misdeclared(Reflection):
        @classmethod
        def enum_choices(cls) -> dict[str, tuple[str, ...]]:
            return {"Verdikt": ("TRUE",)}

    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(500)

    with pytest.raises(ValueError, match="Verdikt"):
        asyncio.run(NvidiaChat(make_transport(handler), settings).ask("system", "user", Misdeclared))
    assert calls == []
