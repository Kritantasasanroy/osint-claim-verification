from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from osint_harness.investigation.verdict import Verdict


class Stance(StrEnum):
    SUPPORTS = "supports"
    REFUTES = "refutes"
    CONTEXT = "context"


class Strength(StrEnum):
    DIRECT = "direct"
    INDIRECT = "indirect"
    WEAK = "weak"

    @property
    def factor(self) -> float:
        return {Strength.DIRECT: 1.0, Strength.INDIRECT: 0.6, Strength.WEAK: 0.3}[self]


class Severity(StrEnum):
    """How grave an adverse fact is, most severe first. Only the material ones can make a subject ADVERSE;
    the rest are reported as minor adverse items (docs/materiality.md)."""

    CRIMINAL_CONVICTION = "criminal_conviction"
    CRIMINAL_CHARGE = "criminal_charge"
    SANCTIONS = "sanctions"
    INSOLVENCY = "insolvency"
    REGULATOR_BAN_OR_MAJOR_ENFORCEMENT = "regulator_ban_or_major_enforcement"
    MAJOR_CIVIL_JUDGMENT = "major_civil_judgment"
    ROUTINE_CIVIL_OR_MINOR_FINE = "routine_civil_or_minor_fine"

    @property
    def is_material(self) -> bool:
        return self is not Severity.ROUTINE_CIVIL_OR_MINOR_FINE


@dataclass(frozen=True)
class Evidence:
    """One fact asserted by one source, and how it bears on one question; never edited once recorded.

    `points_to` is the verdict this fact argues for if it is true (None when it only gives context). An
    adverse fact also carries its severity; a minor one never points to ADVERSE, whatever the model said.
    """

    question_id: str
    source_url: str
    domain: str
    statement: str
    quote: str
    stance: Stance
    strength: Strength
    reliability: float
    step: int
    points_to: Verdict | None = None
    severity: Severity | None = None
    published: date | None = None
    quote_verified: bool = True

    @property
    def weight(self) -> float:
        return self.reliability * self.strength.factor

    @property
    def direction(self) -> Verdict | None:
        """The verdict this item may vote for: an immaterial adverse fact votes for nothing."""
        if self.points_to is Verdict.ADVERSE and not (self.severity and self.severity.is_material):
            return None
        return self.points_to

    @property
    def is_minor_adverse(self) -> bool:
        return self.points_to is Verdict.ADVERSE and self.direction is None
