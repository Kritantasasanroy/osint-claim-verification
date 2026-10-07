from dataclasses import dataclass
from enum import StrEnum


class QuestionStatus(StrEnum):
    OPEN = "open"
    ANSWERED = "answered"
    DROPPED = "dropped"


class QuestionRole(StrEnum):
    """What a question's answer is for. Identity questions settle *which* entity; only verdict-deciding
    evidence may settle the verdict, so confirming a CEO's name can never corroborate a fraud finding."""

    IDENTITY = "identity"
    CORE_FACT = "core_fact"
    VERDICT_DECIDING = "verdict_deciding"


@dataclass
class Question:
    id: str
    text: str
    status: QuestionStatus = QuestionStatus.OPEN
    role: QuestionRole = QuestionRole.VERDICT_DECIDING

    @property
    def is_open(self) -> bool:
        return self.status is QuestionStatus.OPEN

    def answer(self) -> None:
        if self.is_open:
            self.status = QuestionStatus.ANSWERED

    def drop(self) -> None:
        if self.is_open:
            self.status = QuestionStatus.DROPPED
