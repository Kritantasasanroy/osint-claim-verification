import re
from datetime import date
from typing import ClassVar

from pydantic import BaseModel, Field

from osint_harness.agents.briefing import CaseBriefing
from osint_harness.agents.rubric import VERDICTS
from osint_harness.intake.documents import Document
from osint_harness.investigation.case_file import CaseFile
from osint_harness.investigation.question import Question, QuestionRole
from osint_harness.investigation.subject import Subject
from osint_harness.investigation.verdict import SubjectKind
from osint_harness.nvidia import Metered, NvidiaChat


class Scope(BaseModel):
    kind: SubjectKind = Field(
        description="claim if the input asserts or asks anything about an entity (a predicate: did, is, was, "
        "played, owns, was convicted...); company or person only for a bare name to screen"
    )
    entity_name: str = Field(description="The main company or person the input is about, as named in it")
    disambiguators: list[str] = Field(
        description="Every detail in the input that tells this entity apart from namesakes: role, employer, "
        "location, dates, descriptions in parentheses or after a comma. Copy them, do not invent any."
    )
    assertion: str | None = Field(
        description="For a claim: the full assertion as one self-contained, checkable sentence that keeps "
        "every detail of the input (a question becomes the statement it asks about). null otherwise."
    )
    statement: str = Field(
        description="For a claim, the same as assertion. For a company or person, the full name plus its "
        "disambiguators, e.g. 'Patagonia (outdoor clothing company)'."
    )

    def subject(self, documents: tuple[Document, ...], as_of: date) -> Subject:
        statement = self.assertion if self.kind is SubjectKind.CLAIM and self.assertion else self.statement
        return Subject(
            kind=self.kind,
            statement=statement.strip(),
            documents=documents,
            as_of=as_of,
            entity=self.entity_name.strip(),
            disambiguators=tuple(d.strip() for d in self.disambiguators if d.strip()),
        )


class ScopeCheck:
    """What scoping may not lose: every name the analyst wrote, every descriptive detail, and the fact that
    a sentence with a predicate is a claim to check rather than a name to screen."""

    PREDICATE: ClassVar[re.Pattern[str]] = re.compile(
        r"\b(is|are|was|were|has|have|had|did|does|do|will|went|played|plays|owns|owned|founded|filed|won|"
        r"lost|served|serves|sentenced|convicted|acquitted|arrested|pardoned|charged|sued|paid|received|"
        r"became|left|joined|bought|sold|acquired|launched|claimed|denied|admitted|resigned|died|can|could|"
        r"would|may|might|must|should|ran|runs|made|makes|got|gets|holds|held|works|worked|headquartered)\b",
        re.IGNORECASE,
    )
    QUESTION_WORDS: ClassVar[frozenset[str]] = frozenset(
        {
            "is",
            "are",
            "was",
            "were",
            "did",
            "does",
            "do",
            "has",
            "have",
            "had",
            "can",
            "will",
            "who",
            "what",
            "when",
            "where",
            "why",
            "how",
            "the",
            "a",
            "an",
            "it",
            "its",
            "this",
            "that",
            "please",
            "check",
        }
    )
    STOP: ClassVar[frozenset[str]] = frozenset(
        {"the", "a", "an", "of", "for", "and", "in", "at", "on", "to", "with", "by", "from", "former", "its"}
    )

    @classmethod
    def problems(cls, text: str, scope: Scope) -> list[str]:
        if not text.strip():
            return []
        kept = cls._words(
            " ".join([scope.statement, scope.assertion or "", scope.entity_name, *scope.disambiguators])
        )
        problems: list[str] = []
        missing = [name for name in cls.names(text) if not cls._words(name) <= kept]
        if missing:
            problems.append(f"these names from the input were dropped: {', '.join(missing)}")
        for detail in cls.details(text):
            content = cls._words(detail) - cls.STOP
            if content and len(content & kept) / len(content) < 0.6:
                problems.append(f"this disambiguating detail was dropped: '{detail}'")
        if scope.kind is not SubjectKind.CLAIM and cls.PREDICATE.search(text):
            problems.append("the input asserts or asks something about the entity, so kind must be claim")
        return problems

    @classmethod
    def names(cls, text: str) -> list[str]:
        """Runs of capitalised words, minus a sentence-initial question word."""
        found = re.findall(r"\b[A-Z][\w&.'-]*(?:\s+(?:[A-Z][\w&.'-]*|(?:of|de|von|van|der|la|&)\b))*", text)
        names = []
        for run in found:
            words = [w for w in run.split() if w.lower().strip(".") not in cls.QUESTION_WORDS]
            if words and any(len(w.strip(".")) > 1 for w in words):
                names.append(" ".join(words))
        return list(dict.fromkeys(names))

    @staticmethod
    def details(text: str) -> list[str]:
        """Parentheticals, and short comma-delimited appositives (after the name) that carry no verb."""
        parentheses = re.findall(r"\(([^)]{2,80})\)", text)
        segments = [s.strip(" .?!") for s in re.split(r"[,;]", re.sub(r"\([^)]*\)", "", text))[1:]]
        appositives = [s for s in segments if 0 < len(s.split()) <= 8 and not ScopeCheck.PREDICATE.search(s)]
        return parentheses + appositives

    @staticmethod
    def _words(text: str) -> set[str]:
        return {w for w in re.sub(r"[^a-z0-9]+", " ", text.lower()).split() if len(w) > 1}

    @classmethod
    def verbatim(cls, text: str, as_of: date, documents: tuple[Document, ...]) -> Subject:
        """The last resort: the analyst's own words, as a claim if they assert anything."""
        kind = SubjectKind.CLAIM if cls.PREDICATE.search(text) else SubjectKind.PERSON
        names = cls.names(text)
        return Subject(
            kind, text.strip(), documents, as_of, names[0] if names else "", tuple(cls.details(text))
        )


class PlannedQuestion(BaseModel):
    text: str
    role: QuestionRole = Field(
        description="identity: which exact entity this is; core_fact: background (founding, roles, place); "
        "verdict_deciding: an answer that decides the verdict (the claim itself and its key components, or "
        "an "
        "adverse signal such as fraud, sanctions, insolvency, convictions, major enforcement)"
    )


class Plan(BaseModel):
    questions: list[PlannedQuestion] = Field(min_length=1, max_length=6)

    def raise_on(self, case_file: CaseFile) -> list[Question]:
        return [case_file.raise_question(q.text, q.role) for q in self.questions if q.text.strip()]


class Planner:
    """Frames the subject and decides which questions the investigation must answer."""

    SCOPE_PROMPT: ClassVar[str] = (
        "You are the intake analyst of an OSINT team. Decide what is being investigated. If the input "
        "asserts "
        "or asks anything about a company or person, it is a claim: keep the whole assertion, with every "
        "detail (who, which one, what, when, numbers); a question becomes the statement it asks about. Only "
        "a "
        "bare name (with descriptors) is a company or person to screen. Copy every disambiguating detail "
        "(role, employer, place, dates, parentheticals) into disambiguators. If documents are attached and "
        "the "
        "text is empty or vague, derive the most important checkable claim from the documents. Never invent "
        "facts: restate only what the input says. Reply with JSON only."
    )
    PLAN_PROMPT: ClassVar[str] = (
        "You are the lead investigator of an OSINT team. {today} Write 3 to 6 concrete, independently "
        "checkable questions whose answers decide the verdict, and give each its role. For a company or "
        "person, "
        "cover identity disambiguation (role identity), core facts (core_fact), and the adverse signals that "
        "would make it ADVERSE (verdict_deciding). For a claim, cover the exact assertion and its key "
        "components "
        "(verdict_deciding) and the primary record that would settle it. " + VERDICTS + " Long-term memories "
        "may help, but they can be outdated or about a namesake: turn them into questions to verify, never "
        "into "
        "assumptions. Reply with JSON only."
    )

    def __init__(self, chat: NvidiaChat) -> None:
        self._chat = chat

    async def scope(
        self, text: str, documents: tuple[Document, ...], as_of: date
    ) -> tuple[Subject, Metered[Scope], list[str]]:
        """The model scopes; code checks nothing was lost, asks once more naming what was, and otherwise
        falls back to the analyst's own words. Returns the subject, the last reply and the problems seen."""
        excerpts = "\n\n".join(f"--- {d.name} ---\n{d.text[:6000]}" for d in documents)
        user = f"Analyst input:\n{text or '(none)'}\n\nAttached documents:\n{excerpts or '(none)'}"
        scoped = await self._chat.ask(self.SCOPE_PROMPT, user, Scope)
        problems = ScopeCheck.problems(text, scoped.value)
        if not problems:
            return scoped.value.subject(documents, as_of), scoped, []
        retry = f"{user}\n\nYour previous scope lost information: {'; '.join(problems)}. Fix it."
        rescoped = await self._chat.ask(self.SCOPE_PROMPT, retry, Scope)
        merged = Metered(
            rescoped.value,
            scoped.usage + rescoped.usage,
            scoped.latency_s + rescoped.latency_s,
            rescoped.cached,
            scoped.calls + rescoped.calls,
        )
        still = ScopeCheck.problems(text, rescoped.value)
        if not still:
            return rescoped.value.subject(documents, as_of), merged, problems
        return ScopeCheck.verbatim(text, as_of, documents), merged, problems + still

    async def plan(self, briefing: CaseBriefing) -> Metered[Plan]:
        user = (
            f"{briefing.subject}\n\nRecalled long-term memories:\n{briefing.memories}\n\n"
            "Write the investigation questions."
        )
        prompt = self.PLAN_PROMPT.format(today=f"Today is {briefing.case_file.subject.as_of.isoformat()}.")
        return await self._chat.ask(prompt, user, Plan)
