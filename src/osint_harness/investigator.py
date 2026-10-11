import asyncio
import time
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import ClassVar, Protocol

from pydantic import JsonValue

from osint_harness.agents.briefing import CaseBriefing
from osint_harness.agents.closed_book import ClosedBookAnalyst
from osint_harness.agents.critic import Critic
from osint_harness.agents.evaluator import Evaluator
from osint_harness.agents.planner import Planner
from osint_harness.agents.reflector import Decision, Reflection, Reflector
from osint_harness.agents.reporter import Reporter
from osint_harness.agents.researcher import ResearchAction, Researcher
from osint_harness.intake.documents import Document
from osint_harness.investigation.case_file import CaseFile, MemoryMode
from osint_harness.investigation.confidence import ConfidenceCalibrator
from osint_harness.investigation.independence import Repeat
from osint_harness.investigation.inquiry import Inquiry, Step, ToolName
from osint_harness.investigation.question import QuestionRole
from osint_harness.investigation.report import Coverage, Report
from osint_harness.investigation.source import ResolvedBy, Source, TrackRecord
from osint_harness.investigation.subject import Subject
from osint_harness.investigation.verdict import Belief, Verdict
from osint_harness.memory import MemoryStore, Recollection
from osint_harness.nvidia import TokenUsage
from osint_harness.tools import Toolbox
from osint_harness.trace import TraceEventKind, TraceLog


class StopReason(StrEnum):
    CONCLUDED = "concluded"
    STEP_BUDGET = "step_budget"
    TOOL_BUDGET = "tool_budget"
    CLOSED_BOOK = "closed_book"


@dataclass(frozen=True)
class Budget:
    max_steps: int = 4
    max_tool_calls: int = 12
    actions_per_step: int = 3

    def __post_init__(self) -> None:
        if min(self.max_steps, self.max_tool_calls, self.actions_per_step) < 1:
            raise ValueError(
                "Budget limits must all be at least 1: an investigation needs one research round."
            )


@dataclass(frozen=True)
class Resolution:
    """Ground truth for a case, when there is some: only then do publishers earn a track record."""

    verdict: Verdict
    resolved_by: ResolvedBy


@dataclass(frozen=True)
class Investigation:
    """One finished run over one subject: the report, the case file behind it, and its trace."""

    case_file: CaseFile
    report: Report
    mode: MemoryMode
    stop_reason: StopReason
    recollections: tuple[Recollection, ...]
    distrusted_memory_ids: frozenset[str]
    wall_clock_s: float
    trace: TraceLog
    critic_checks: int = 0
    rejected_repeats: int = 0

    @property
    def tool_calls(self) -> int:
        return self.case_file.tool_calls

    @property
    def usage(self) -> TokenUsage:
        return sum((event.usage for event in self.trace.events), TokenUsage())

    @property
    def call_latency_s(self) -> float:
        """Summed latency of every model, embedding and tool call; concurrent calls each count."""
        return sum(event.latency_s for event in self.trace.events)


class Investigates(Protocol):
    async def scope(
        self, text: str, documents: tuple[Document, ...], trace: TraceLog, as_of: date
    ) -> Subject: ...

    async def investigate(
        self, subject: Subject, trace: TraceLog, resolution: Resolution | None = None
    ) -> Investigation: ...

    def forget(self, investigation: str) -> None: ...


class Investigator:
    """Runs the plan -> research -> evaluate -> reflect loop until the case settles or the budget runs out."""

    SOURCES_PER_ASSESSMENT: ClassVar[int] = 6

    def __init__(
        self,
        planner: Planner,
        researcher: Researcher,
        evaluator: Evaluator,
        reflector: Reflector,
        reporter: Reporter,
        critic: Critic,
        toolbox: Toolbox,
        memory: MemoryStore,
        mode: MemoryMode,
        budget: Budget,
        calibrator: ConfidenceCalibrator,
        min_rounds: int = 1,
        seed_urls: tuple[str, ...] = (),
    ) -> None:
        """`min_rounds` and `seed_urls` exist for counterfactual replays: keep researching past the point the
        gate would allow, or start from the ground-truth sources (evaluation/counterfactual.py)."""
        self._min_rounds = min_rounds
        self._seed_urls = seed_urls
        self._planner = planner
        self._researcher = researcher
        self._evaluator = evaluator
        self._reflector = reflector
        self._reporter = reporter
        self._critic = critic
        self._toolbox = toolbox
        self._memory = memory
        self._mode = mode
        self._budget = budget
        self._calibrator = calibrator

    async def scope(
        self, text: str, documents: tuple[Document, ...], trace: TraceLog, as_of: date
    ) -> Subject:
        return await scope_subject(self._planner, text, documents, trace, as_of)

    async def investigate(
        self, subject: Subject, trace: TraceLog, resolution: Resolution | None = None
    ) -> Investigation:
        started = time.perf_counter()
        case = CaseFile(subject)
        tracks = self._memory.track_records()
        recollections = await self._recall(subject.statement, subject, (), 0, trace, len(tracks))
        await self._plan(case, recollections, trace)
        await self._file_uploads(case, recollections, tracks, trace)

        stop_reason, distrusted = StopReason.STEP_BUDGET, set[str]()
        forced: ResearchAction | None = None
        critic_checks = rejected = 0
        for number in range(1, self._budget.max_steps + 1):
            inquiries, repeats = await self._research(case, recollections, tracks, number, trace, forced)
            rejected += repeats
            forced = None
            reflection, belief = await self._reflect(case, recollections, number, trace, inquiries)
            distrusted |= self._distrusted(reflection, recollections)
            recollections = await self._recall_more(reflection, subject, recollections, number, trace)
            settled = case.is_settled(belief, self._mode.visible_from(number))
            if reflection.decision is Decision.CONCLUDE and settled and number >= self._min_rounds:
                if critic_checks == 0 and case.tool_calls < self._budget.max_tool_calls:
                    forced = await self._challenge(case, recollections, belief, number, trace)
                    critic_checks += forced is not None
                if forced is None:
                    stop_reason = StopReason.CONCLUDED
                    break
            if case.tool_calls >= self._budget.max_tool_calls:
                stop_reason = StopReason.TOOL_BUDGET
                break

        self._memory.record_distrust([int(label[1:]) for label in distrusted])
        report = await self._report(case, recollections, tracks, trace, resolution)
        return Investigation(
            case,
            report,
            self._mode,
            stop_reason,
            recollections,
            frozenset(distrusted),
            time.perf_counter() - started,
            trace,
            critic_checks,
            rejected,
        )

    def forget(self, investigation: str) -> None:
        self._memory.forget_investigation(investigation)

    @staticmethod
    def _distrusted(reflection: Reflection, recollections: tuple[Recollection, ...]) -> set[str]:
        """Only ids of memories that were actually recalled count; anything else the model named is noise."""
        recalled_ids = {r.label for r in recollections}
        return recalled_ids & set(reflection.distrusted_memory_ids)

    async def _recall(
        self,
        query: str,
        subject: Subject,
        already: tuple[Recollection, ...],
        step: int,
        trace: TraceLog,
        known_publishers: int,
    ) -> tuple[Recollection, ...]:
        recalled = await self._memory.recall(query, subject.entity or subject.statement, subject.identity)
        seen = {r.memory_id for r in already}
        fresh = tuple(r for r in recalled.value if r.memory_id not in seen)
        trace.append_metered(
            TraceEventKind.MEMORY_RECALLED,
            step,
            {
                "query": query,
                "memories": [
                    {
                        "id": r.label,
                        "text": r.record.text,
                        "from": r.record.subject,
                        "similarity": round(r.similarity, 3),
                    }
                    for r in fresh
                ],
                "known_publishers": known_publishers,
            },
            recalled,
        )
        return already + fresh

    async def _recall_more(
        self,
        reflection: Reflection,
        subject: Subject,
        recollections: tuple[Recollection, ...],
        step: int,
        trace: TraceLog,
    ) -> tuple[Recollection, ...]:
        """Long-term memory is asked again when the investigation raises new questions, not only at the "
        "start."""
        if not (self._mode.uses_long_term and reflection.follow_up_questions):
            return recollections
        query = " ".join(reflection.follow_up_questions)[:500]
        return await self._recall(query, subject, recollections, step, trace, 0)

    async def _plan(self, case: CaseFile, recollections: tuple[Recollection, ...], trace: TraceLog) -> None:
        planned = await self._planner.plan(CaseBriefing(case, 0, recollections))
        questions = planned.value.raise_on(case)
        trace.append_metered(
            TraceEventKind.PLANNED,
            0,
            {"questions": [{"id": q.id, "text": q.text, "role": q.role.value} for q in questions]},
            planned,
        )

    async def _file_uploads(
        self,
        case: CaseFile,
        recollections: tuple[Recollection, ...],
        tracks: dict[str, TrackRecord],
        trace: TraceLog,
    ) -> None:
        uploads = [
            Source.from_upload(document.name, piece.location, piece.text)
            for document in case.subject.documents
            for piece in document.pieces(Source.READ_WINDOW)
        ]
        fresh = [source.url for source in uploads if case.file_source(source)]
        upload_step = CaseFile.UPLOAD_STEP
        await self._assess(
            case, CaseBriefing(case, upload_step, recollections), fresh, tracks, upload_step, trace
        )

    async def _choose(
        self,
        case: CaseFile,
        briefing: CaseBriefing,
        number: int,
        trace: TraceLog,
        forced: ResearchAction | None,
    ) -> tuple[list[ResearchAction], int]:
        """The researcher proposes, the query ledger disposes: a repeat of an earlier query is rejected, and
        the researcher gets one more try with the rejected list in front of it."""
        limit = min(self._budget.actions_per_step, self._budget.max_tool_calls - case.tool_calls)
        ledger = case.ledger
        actions: list[ResearchAction] = []
        if forced is not None and ledger.admit(forced.tool, forced.argument) is None:
            actions.append(forced)
        rejected: list[Repeat] = []
        for attempt in range(2):
            if len(actions) >= limit:
                break
            agenda = await self._researcher.choose(
                briefing, self._toolbox.catalogue, limit - len(actions), tuple(rejected)
            )
            trace.append_metered(
                TraceEventKind.RESEARCH_CHOSEN,
                number,
                {
                    "attempt": attempt + 1,
                    "actions": [a.model_dump(mode="json") for a in agenda.value.actions],
                },
                agenda,
            )
            fresh_rejections: list[Repeat] = []
            for action in agenda.value.actions:
                if len(actions) >= limit:
                    break
                repeat = ledger.admit(action.tool, action.argument)
                if repeat is None:
                    actions.append(action)
                else:
                    fresh_rejections.append(repeat)
            rejected += fresh_rejections
            if not fresh_rejections:
                break
        if rejected:
            trace.append(
                TraceEventKind.QUERY_REJECTED,
                number,
                {
                    "rejected": [
                        {"tool": r.tool.value, "query": r.argument, "repeats": r.earlier} for r in rejected
                    ]
                },
            )
        return actions, len(rejected)

    async def _research(
        self,
        case: CaseFile,
        recollections: tuple[Recollection, ...],
        tracks: dict[str, TrackRecord],
        number: int,
        trace: TraceLog,
        forced: ResearchAction | None,
    ) -> tuple[list[Inquiry], int]:
        briefing = CaseBriefing(case, self._mode.visible_from(number), recollections)
        actions, rejected = await self._choose(case, briefing, number, trace, forced)
        seeded = self._seed_urls if number == 1 else ()
        target = next((q.id for q in case.questions if q.role is QuestionRole.VERDICT_DECIDING), "Q1")
        inquiries = list(
            await asyncio.gather(
                *(self._toolbox.use(ToolName.READ_PAGE, url, target, number) for url in seeded),
                *(self._toolbox.use(a.tool, a.argument, a.question_id, number) for a in actions),
            )
        )
        fresh_urls: list[str] = []
        for inquiry in inquiries:
            filed = [(source, case.file_source(source)) for source in inquiry.sources]
            fresh_urls += [source.url for source, is_new in filed if is_new]
            trace.append(
                TraceEventKind.TOOL_CALLED,
                number,
                {
                    "tool": inquiry.tool.value,
                    "argument": inquiry.argument,
                    "question_id": inquiry.question_id,
                    "outcome": inquiry.outcome.value,
                    "failure": inquiry.failure,
                    "returned": [source.url for source in inquiry.sources],
                    "new": [source.url for source, is_new in filed if is_new],
                    "tiers": [source.tier.value for source in inquiry.sources],
                    "published": [s.published.isoformat() if s.published else None for s in inquiry.sources],
                    "manipulation_flags": [len(source.manipulation_flags) for source in inquiry.sources],
                },
                latency_s=inquiry.latency_s,
            )
        await self._assess(case, briefing, fresh_urls, tracks, number, trace)
        return inquiries, rejected

    async def _assess(
        self,
        case: CaseFile,
        briefing: CaseBriefing,
        urls: list[str],
        tracks: dict[str, TrackRecord],
        number: int,
        trace: TraceLog,
    ) -> None:
        size = self.SOURCES_PER_ASSESSMENT
        batches = [urls[i : i + size] for i in range(0, len(urls), size)]
        assessments = await asyncio.gather(*(self._evaluator.assess(briefing, batch) for batch in batches))
        for batch, assessment in zip(batches, assessments, strict=True):
            evidence = assessment.value.evidence_for(case, batch, tracks, number)
            for item in evidence:
                case.record_evidence(item)
            trace.append_metered(
                TraceEventKind.EVIDENCE_ASSESSED,
                number,
                {
                    "source_count": len(batch),
                    "proposed": len(assessment.value.evidence),
                    "evidence": [
                        {
                            "question_id": e.question_id,
                            "domain": e.domain,
                            "stance": e.stance.value,
                            "strength": e.strength.value,
                            "points_to": e.direction.value if e.direction else None,
                            "severity": e.severity.value if e.severity else None,
                            "quote_verified": e.quote_verified,
                            "stale": case.is_stale(e),
                            "weight": round(e.weight, 3),
                            "statement": e.statement,
                            "source": e.source_url,
                        }
                        for e in evidence
                    ],
                },
                assessment,
            )

    async def _reflect(
        self,
        case: CaseFile,
        recollections: tuple[Recollection, ...],
        number: int,
        trace: TraceLog,
        inquiries: list[Inquiry],
    ) -> tuple[Reflection, Belief]:
        """The model's belief is one input. The shipped belief pools it with the evidence posterior and is
        then calibrated; all three are kept on the step."""
        window = self._mode.visible_from(number)
        briefing = CaseBriefing(case, window, recollections)
        reflected = await self._reflector.reflect(briefing, self._budget.max_steps - number)
        reflection = reflected.value
        llm_belief = reflection.belief(case)
        posterior = case.posterior(window)
        belief, inputs = self._calibrator.ship(
            llm_belief, posterior, lambda verdict: case.support(verdict, window)
        )
        follow_ups = reflection.update_questions(case)
        case.record_step(Step(number, tuple(inquiries), belief, llm_belief, posterior, inputs))
        distrusted: list[JsonValue] = list(sorted(self._distrusted(reflection, recollections)))
        trace.append_metered(
            TraceEventKind.REFLECTED,
            number,
            {
                "verdict": belief.verdict.value,
                "confidence": round(belief.confidence, 4),
                "probabilities": {v.value: round(p, 4) for v, p in belief.probabilities},
                "llm_verdict": llm_belief.verdict.value,
                "llm_probabilities": {v.value: round(p, 4) for v, p in llm_belief.probabilities},
                "posterior": {v.value: round(p, 4) for v, p in posterior.probabilities},
                "calibrated": self._calibrator.is_fitted,
                "decision": reflection.decision.value,
                "settled": case.is_settled(belief, window),
                "unmet": list(case.unmet_conditions(belief, window)),
                "conflicts": [c.question.id for c in case.conflicts_from(window)],
                "independent_publishers": len(case.independent_publishers(window)),
                "evidence_count": len(case.evidence),
                "follow_up_questions": [q.text for q in follow_ups],
                "distrusted_memory_ids": distrusted,
                "critique": reflection.critique,
            },
            reflected,
        )
        return reflection, belief

    async def _challenge(
        self,
        case: CaseFile,
        recollections: tuple[Recollection, ...],
        belief: Belief,
        number: int,
        trace: TraceLog,
    ) -> ResearchAction | None:
        """A red-team pass may buy one more round, once, if it names a check that has not been run."""
        briefing = CaseBriefing(case, self._mode.visible_from(number), recollections)
        challenged = await self._critic.challenge(briefing, belief, self._toolbox.catalogue)
        check = challenged.value.cheap_check
        usable = (
            check is not None
            and self._toolbox.offers(check.tool)
            and case.has_question(check.question_id)
            and case.ledger.repeat_of(check.tool, check.argument) is None
        )
        trace.append_metered(
            TraceEventKind.CRITIQUED,
            number,
            {
                "runner_up_case": challenged.value.runner_up_case,
                "would_flip_it": list(challenged.value.would_flip_it),
                "check": check.model_dump(mode="json") if check else None,
                "check_run": usable,
            },
            challenged,
        )
        return check if usable else None

    async def _report(
        self,
        case: CaseFile,
        recollections: tuple[Recollection, ...],
        tracks: dict[str, TrackRecord],
        trace: TraceLog,
        resolution: Resolution | None,
    ) -> Report:
        belief = case.beliefs[-1]
        last = case.steps[-1].number
        drafted = await self._reporter.write(
            CaseBriefing(case, self._mode.visible_from(last), recollections), belief
        )
        coverage: Coverage = self._toolbox.coverage({inquiry.tool for inquiry in case.inquiries})
        report = drafted.value.report(case, belief, tracks, coverage)
        trace.append_metered(
            TraceEventKind.REPORTED,
            last,
            {
                "verdict": report.verdict.value,
                "confidence": round(report.confidence, 4),
                "findings": len(report.findings),
                "sources_cited": len(report.sources),
                "gaps": len(report.gaps),
                "withdrawn": list(report.withdrawn),
                "manipulation_flags": len(report.manipulation_flags),
            },
            drafted,
        )
        records = drafted.value.memories(case, trace.investigation)
        stored = await self._memory.remember(records)
        outcomes = case.publisher_outcomes(resolution.verdict, resolution.resolved_by) if resolution else []
        self._memory.record_publisher_outcomes(trace.investigation, outcomes)
        trace.append_metered(
            TraceEventKind.MEMORY_WRITTEN,
            last,
            {
                "long_term": self._mode.uses_long_term,
                "stored": stored.value,
                "proposed": [r.text for r in records],
                "publisher_outcomes": len(outcomes),
                "outcomes_resolved_by": resolution.resolved_by.value if resolution else None,
            },
            stored,
        )
        return report


async def scope_subject(
    planner: Planner, text: str, documents: tuple[Document, ...], trace: TraceLog, as_of: date
) -> Subject:
    subject, scoped, problems = await planner.scope(text, documents, as_of)
    trace.append_metered(
        TraceEventKind.SCOPED,
        0,
        {
            "kind": subject.kind.value,
            "statement": subject.statement,
            "entity": subject.entity,
            "disambiguators": list(subject.disambiguators),
            "as_of": as_of.isoformat(),
            "scope_problems": list(problems),
            "documents": [d.name for d in documents],
        },
        scoped,
    )
    return subject


class ClosedBookInvestigator:
    """Answers without investigating, packaged as an Investigation so it is graded exactly like one."""

    def __init__(self, planner: Planner, analyst: ClosedBookAnalyst, toolbox: Toolbox) -> None:
        self._planner = planner
        self._analyst = analyst
        self._toolbox = toolbox

    async def scope(
        self, text: str, documents: tuple[Document, ...], trace: TraceLog, as_of: date
    ) -> Subject:
        return await scope_subject(self._planner, text, documents, trace, as_of)

    async def investigate(
        self, subject: Subject, trace: TraceLog, resolution: Resolution | None = None
    ) -> Investigation:
        started = time.perf_counter()
        case = CaseFile(subject)
        answered = await self._analyst.answer(subject)
        belief = answered.value.belief(subject.kind)
        case.record_step(Step(1, (), belief, belief))
        trace.append_metered(
            TraceEventKind.REFLECTED,
            1,
            {
                "verdict": belief.verdict.value,
                "confidence": round(belief.confidence, 4),
                "critique": answered.value.reasoning,
                "closed_book": True,
            },
            answered,
        )
        report = Report.assemble(
            case,
            belief,
            answered.value.reasoning,
            [],
            [],
            ["Closed book: nothing was searched."],
            {},
            self._toolbox.coverage(set()),
        )
        return Investigation(
            case,
            report,
            MemoryMode.CLOSED_BOOK,
            StopReason.CLOSED_BOOK,
            (),
            frozenset(),
            time.perf_counter() - started,
            trace,
        )

    def forget(self, investigation: str) -> None:
        return None
