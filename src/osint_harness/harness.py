from enum import StrEnum
from pathlib import Path

import httpx

from osint_harness.agents.closed_book import ClosedBookAnalyst
from osint_harness.agents.critic import Critic
from osint_harness.agents.evaluator import Evaluator
from osint_harness.agents.planner import Planner
from osint_harness.agents.reflector import Reflector
from osint_harness.agents.reporter import Reporter
from osint_harness.agents.researcher import Researcher
from osint_harness.intake.documents import DocumentIntake
from osint_harness.intake.ocr import NemotronParseOcr
from osint_harness.investigation.case_file import MemoryMode
from osint_harness.investigation.confidence import ConfidenceCalibrator
from osint_harness.investigator import Budget, ClosedBookInvestigator, Investigates, Investigator
from osint_harness.memory import LongTermMemory, MemoryStore, NoLongTermMemory
from osint_harness.nvidia import NvidiaChat, NvidiaEmbedder
from osint_harness.settings import Settings
from osint_harness.tools import Toolbox
from osint_harness.transport import ResponseCache, Transport


class Intervention(StrEnum):
    """One change at a time, for counterfactual diagnosis of a wrong episode (E6)."""

    CONTINUE = "continue"
    NO_MEMORY = "no_memory"
    GOLD_SOURCE = "gold_source"
    PRE_SCOPED = "pre_scoped"
    STRONG_REASONER = "strong_reasoner"
    REPEAT = (
        "repeat"  # the control: no change at all, so a "fix" by any other intervention can be told from noise
    )


class Harness:
    """Composition root: wires settings, services and agents together, once per process."""

    CALIBRATOR: Path = Path("benchmark/calibration/confidence.json")

    def __init__(
        self, settings: Settings, transport: Transport, calibrator: ConfidenceCalibrator | None = None
    ) -> None:
        self.settings = settings
        self.calibrator = calibrator if calibrator is not None else ConfidenceCalibrator.load(self.CALIBRATOR)
        self.chat = NvidiaChat(transport, settings)
        self._embedder = NvidiaEmbedder(transport, settings)
        self.intake = DocumentIntake(NemotronParseOcr(transport, settings))
        self._toolbox = Toolbox.standard(transport, settings)

    @classmethod
    def connect(cls, settings: Settings) -> "Harness":
        """The LLM and search caches are switched separately: a benchmark replays the same evidence across
        modes and seeds (search cache on) while still sampling the model afresh (LLM cache off)."""
        cached = settings.llm_cache or settings.search_cache
        cache = ResponseCache(settings.cache_path) if cached else ResponseCache.disabled()
        client = httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=30.0))
        transport = Transport(
            client, cache, settings.max_concurrent_requests, cache_by_default=settings.search_cache
        )
        return cls(settings, transport)

    @property
    def judge_chat(self) -> NvidiaChat:
        return self.chat.for_model(self.settings.judge_model)

    def investigator(
        self,
        mode: MemoryMode,
        memory_path: Path,
        budget: Budget,
        seed: int | None = None,
        intervention: "Intervention | None" = None,
        seed_urls: tuple[str, ...] = (),
    ) -> Investigates:
        """`intervention` builds the one-change variant a counterfactual replay needs; None is the real "
        "agent."""
        chat = self.chat.with_seed(seed)
        min_rounds = 1
        if intervention is Intervention.CONTINUE:
            budget = Budget(budget.max_steps + 2, budget.max_tool_calls + 6, budget.actions_per_step)
            min_rounds = budget.max_steps
        if intervention is Intervention.NO_MEMORY:
            mode = MemoryMode.NONE
        if not mode.investigates:
            return ClosedBookInvestigator(Planner(chat), ClosedBookAnalyst(chat), self._toolbox)
        memory: MemoryStore = (
            LongTermMemory(memory_path, self._embedder) if mode.uses_long_term else NoLongTermMemory()
        )
        return Investigator(
            Planner(chat),
            Researcher(chat),
            Evaluator(chat),
            Reflector(
                self.judge_chat.with_seed(seed) if intervention is Intervention.STRONG_REASONER else chat
            ),
            Reporter(chat),
            Critic(self.judge_chat.with_seed(seed)),
            self._toolbox,
            memory,
            mode,
            budget,
            self.calibrator,
            min_rounds,
            seed_urls if intervention is Intervention.GOLD_SOURCE else (),
        )
