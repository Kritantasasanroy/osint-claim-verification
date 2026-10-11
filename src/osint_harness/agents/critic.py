from typing import ClassVar

from pydantic import BaseModel, Field

from osint_harness.agents.briefing import CaseBriefing
from osint_harness.agents.researcher import ResearchAction
from osint_harness.agents.rubric import UNTRUSTED, VERDICTS
from osint_harness.investigation.verdict import Belief
from osint_harness.nvidia import Metered, NvidiaChat


class Challenge(BaseModel):
    runner_up_case: str = Field(
        min_length=20, description="The strongest honest case for the runner-up verdict"
    )
    would_flip_it: list[str] = Field(
        description="Evidence that, if found, would overturn the leading verdict"
    )
    cheap_check: ResearchAction | None = Field(
        description="One specific tool call not yet made that could find such evidence, or null if the "
        "research already covers it"
    )


class Critic:
    """A red-team pass before the case closes: argue for the runner-up verdict and name the one check that
    could overturn the leading one. Run on another model than the reflector, so it does not grade itself."""

    PROMPT: ClassVar[str] = (
        "You are the red-team reviewer of an OSINT team. {today} The team is about to conclude {verdict}. "
        "Argue the strongest honest case for {runner_up} instead, list the evidence that would overturn "
        "{verdict}, and name at most one specific, cheap tool call not yet made that could find it (or null "
        "if "
        "the research already covers it). " + VERDICTS + " " + UNTRUSTED + "\nTools:\n{catalogue}\n"
        "Reply with JSON only."
    )

    def __init__(self, chat: NvidiaChat) -> None:
        self._chat = chat

    async def challenge(self, briefing: CaseBriefing, belief: Belief, catalogue: str) -> Metered[Challenge]:
        ranked = sorted(belief.probabilities, key=lambda pair: -pair[1])
        runner_up = next(v for v, _ in ranked if v is not belief.verdict)
        user = (
            f"{briefing.subject}\n\nQuestions:\n{briefing.questions}\n\nResearch already done:\n"
            f"{briefing.inquiries}\n\nEvidence (newest first):\n{briefing.evidence}\n\nCompeting "
            f"hypotheses:\n"
            f"{briefing.hypotheses}"
        )
        prompt = self.PROMPT.format(
            today=f"Today is {briefing.case_file.subject.as_of.isoformat()}.",
            verdict=belief.verdict.value,
            runner_up=runner_up.value,
            catalogue=catalogue,
        )
        return await self._chat.ask(prompt, user, Challenge)
