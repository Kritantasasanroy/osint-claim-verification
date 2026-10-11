from typing import ClassVar

from pydantic import BaseModel, Field

from osint_harness.agents.briefing import CaseBriefing
from osint_harness.agents.rubric import UNTRUSTED
from osint_harness.investigation.independence import Repeat
from osint_harness.investigation.inquiry import ToolName
from osint_harness.nvidia import Metered, NvidiaChat


class ResearchAction(BaseModel):
    tool: ToolName
    argument: str = Field(min_length=1, description="Search query, entity name, or exact URL, per the tool")
    question_id: str = Field(description="The open question this action serves, e.g. Q2")


class ResearchAgenda(BaseModel):
    actions: list[ResearchAction] = Field(min_length=1, max_length=4)


class Researcher:
    """Chooses which tools to call next, and with what, to close the open questions."""

    PROMPT: ClassVar[str] = (
        "You are the research specialist of an OSINT team. {today} Choose up to {limit} tool calls that best "
        "close the open questions, starting with the verdict-deciding ones. Prefer primary records "
        "(registers, "
        "filings, court records, sanctions lists) where a tool reaches them, then major news, then reference "
        "works. Use different publishers to corroborate. For anything that may have changed, search news for "
        "the most recent report. When evidence conflicts, look for the primary record or the most recent "
        "authoritative report that resolves it. Include the subject's disambiguating details in queries "
        "about "
        "a common name. Never repeat or rephrase a query already made: repeats are rejected. Use read_page "
        "only on a URL listed under 'Readable URLs'. "
        + UNTRUSTED
        + "\nTools:\n{catalogue}\nReply with JSON only."
    )

    def __init__(self, chat: NvidiaChat) -> None:
        self._chat = chat

    async def choose(
        self, briefing: CaseBriefing, catalogue: str, limit: int, rejected: tuple[Repeat, ...] = ()
    ) -> Metered[ResearchAgenda]:
        user = (
            f"{briefing.subject}\n\nQuestions:\n{briefing.questions}\n\n"
            f"Research already done:\n{briefing.inquiries}\n\n"
            f"Evidence so far:\n{briefing.evidence}\n\nConflicts:\n{briefing.conflicts}\n\n"
            f"Readable URLs:\n{briefing.readable_urls}\n\nRecalled long-term memories:\n{briefing.memories}"
        )
        if rejected:
            user += "\n\nRejected as repeats of earlier queries (choose genuinely new ones):\n" + "\n".join(
                f"- {r.tool.value}('{r.argument}') repeats '{r.earlier}'" for r in rejected
            )
        prompt = self.PROMPT.format(
            today=f"Today is {briefing.case_file.subject.as_of.isoformat()}.",
            limit=limit,
            catalogue=catalogue,
        )
        return await self._chat.ask(prompt, user, ResearchAgenda)
