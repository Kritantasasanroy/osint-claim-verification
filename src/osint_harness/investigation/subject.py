import re
from dataclasses import dataclass, field
from datetime import date
from typing import ClassVar

from osint_harness.intake.documents import Document
from osint_harness.investigation.verdict import SubjectKind


@dataclass(frozen=True)
class Subject:
    """What is being investigated, in words, plus any documents the analyst handed over with it.

    `as_of` is the date the verdict is about: "currently" in a claim means on that day. `entity` and
    `disambiguators` (role, employer, place, dates) say which of several namesakes is meant, so evidence
    about another person or company with the same name can be told apart and rejected.
    """

    kind: SubjectKind
    statement: str
    documents: tuple[Document, ...] = ()
    as_of: date = field(default_factory=date.today)
    entity: str = ""
    disambiguators: tuple[str, ...] = ()

    STATE_MARKERS: ClassVar[re.Pattern[str]] = re.compile(
        r"\b(currently|still|now|today|at present|presently|remains?|is (the )?(ceo|chair|president|head|"
        r"owner|in (custody|prison|jail))|is serving|is being held|incumbent)\b",
        re.IGNORECASE,
    )

    @property
    def is_state_claim(self) -> bool:
        """A claim about how things stand now ("currently", "still", "is CEO"): newer evidence wins."""
        return self.kind is SubjectKind.CLAIM and bool(self.STATE_MARKERS.search(self.statement))

    @property
    def identity(self) -> str:
        """The entity and what tells it apart from namesakes, as one line for prompts and memory keys."""
        name = self.entity or self.statement
        return f"{name} ({'; '.join(self.disambiguators)})" if self.disambiguators else name
