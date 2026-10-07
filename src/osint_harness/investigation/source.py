import csv
import re
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlparse


class SourceTier(StrEnum):
    OFFICIAL = "official"
    MAJOR_NEWS = "major_news"
    REFERENCE = "reference"
    NEWS = "news"
    USER_PROVIDED = "user_provided"
    UNVETTED = "unvetted"
    USER_GENERATED = "user_generated"

    @property
    def prior_reliability(self) -> float:
        return {
            SourceTier.OFFICIAL: 0.95,
            SourceTier.MAJOR_NEWS: 0.85,
            SourceTier.REFERENCE: 0.75,
            SourceTier.NEWS: 0.65,
            SourceTier.USER_PROVIDED: 0.5,
            SourceTier.UNVETTED: 0.4,
            SourceTier.USER_GENERATED: 0.3,
        }[self]

    @property
    def ceiling(self) -> float:
        """The most a track record can lift a publisher of this tier. Agreement is cheap: a video site that
        is often right is still a video site, and only an analyst may vouch for it beyond this."""
        return {
            SourceTier.OFFICIAL: 0.99,
            SourceTier.MAJOR_NEWS: 0.95,
            SourceTier.REFERENCE: 0.9,
            SourceTier.NEWS: 0.8,
            SourceTier.USER_PROVIDED: 0.5,
            SourceTier.UNVETTED: 0.6,
            SourceTier.USER_GENERATED: 0.5,
        }[self]

    @property
    def is_authoritative(self) -> bool:
        """Good enough, on its own, to anchor an adverse finding or a refutation of a factual record."""
        return self in (SourceTier.OFFICIAL, SourceTier.MAJOR_NEWS, SourceTier.REFERENCE)


class DomainCatalogue:
    """Publisher tiers by domain, in layers: an analyst's rating file, then the hand-curated lists, then the
    shape of the domain (government, court, academic, social platform); anything else is unvetted."""

    OFFICIAL_SUFFIXES: ClassVar[tuple[str, ...]] = (
        ".gov",
        ".gov.uk",
        ".gouv.fr",
        ".europa.eu",
        ".mil",
        ".int",
        ".gc.ca",
        ".gov.au",
        ".gov.in",
        ".nic.in",
        ".bund.de",
        ".admin.ch",
        ".govt.nz",
        ".uscourts.gov",
    )
    OFFICIAL_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"(^|\.)gov\.[a-z]{2}$|(^|\.)gob\.[a-z]{2}$")
    REFERENCE_SUFFIXES: ClassVar[tuple[str, ...]] = (".edu", ".ac.uk", ".ac.in", ".edu.au")
    OFFICIAL: ClassVar[frozenset[str]] = frozenset(
        {
            "courtlistener.com",
            "bafin.de",
            "fca.org.uk",
            "un.org",
            "bundesanzeiger.de",
            "handelsregister.de",
            "unternehmensregister.de",
            "opencorporates.com",
            "gleif.org",
            "sec.gov",
            "justice.gov",
            "finra.org",
            "companieshouse.gov.uk",
            "insolvenzbekanntmachungen.de",
            "pacer.uscourts.gov",
        }
    )
    MAJOR_NEWS: ClassVar[frozenset[str]] = frozenset(
        {
            "reuters.com",
            "apnews.com",
            "bbc.com",
            "bbc.co.uk",
            "ft.com",
            "wsj.com",
            "nytimes.com",
            "bloomberg.com",
            "theguardian.com",
            "washingtonpost.com",
            "economist.com",
            "npr.org",
            "cnbc.com",
            "aljazeera.com",
            "dw.com",
            "lemonde.fr",
            "spiegel.de",
            "handelsblatt.com",
            "faz.net",
            "sueddeutsche.de",
            "elpais.com",
            "thehindu.com",
            "nikkei.com",
            "afp.com",
        }
    )
    REFERENCE: ClassVar[frozenset[str]] = frozenset(
        {
            "wikipedia.org",
            "wikidata.org",
            "britannica.com",
            "nature.com",
            "science.org",
            "cochranelibrary.com",
            "snopes.com",
            "factcheck.org",
            "politifact.com",
            "fullfact.org",
            "harvard.edu",
            "stanford.edu",
            "berkeley.edu",
            "mit.edu",
            "ox.ac.uk",
            "cam.ac.uk",
            "opensanctions.org",
            "web.archive.org",
        }
    )
    NEWS: ClassVar[frozenset[str]] = frozenset(
        {
            "cnn.com",
            "forbes.com",
            "fortune.com",
            "techcrunch.com",
            "theverge.com",
            "businessinsider.com",
            "axios.com",
            "politico.com",
            "time.com",
            "newsweek.com",
            "independent.co.uk",
            "latimes.com",
            "usatoday.com",
            "abcnews.go.com",
            "cbsnews.com",
            "nbcnews.com",
            "theatlantic.com",
            "wired.com",
            "abc.net.au",
            "finance.yahoo.com",
            "boersen-zeitung.de",
            "coindesk.com",
            "law360.com",
            "courthousenews.com",
        }
    )
    USER_GENERATED: ClassVar[frozenset[str]] = frozenset(
        {
            "youtube.com",
            "youtu.be",
            "facebook.com",
            "instagram.com",
            "x.com",
            "twitter.com",
            "tiktok.com",
            "reddit.com",
            "linkedin.com",
            "quora.com",
            "medium.com",
            "substack.com",
            "pinterest.com",
            "threads.net",
            "tumblr.com",
            "fandom.com",
        }
    )
    # Filled from an analyst's rating file (domain,tier rows); a manual input, never learned.
    RATED: ClassVar[dict[str, SourceTier]] = {}

    @classmethod
    def load_ratings(cls, path: Path) -> int:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = [row for row in csv.DictReader(handle) if row.get("domain") and row.get("tier")]
        cls.RATED.update({row["domain"].strip().lower(): SourceTier(row["tier"].strip()) for row in rows})
        return len(rows)

    @classmethod
    def tier_of(cls, domain: str) -> SourceTier:
        rated = next((tier for known, tier in cls.RATED.items() if cls._matches(domain, known)), None)
        if rated is not None:
            return rated
        if cls._listed(domain, cls.USER_GENERATED):
            return SourceTier.USER_GENERATED
        if (
            domain.endswith(cls.OFFICIAL_SUFFIXES)
            or cls.OFFICIAL_PATTERN.search(domain)
            or cls._listed(domain, cls.OFFICIAL)
        ):
            return SourceTier.OFFICIAL
        if cls._listed(domain, cls.MAJOR_NEWS):
            return SourceTier.MAJOR_NEWS
        if cls._listed(domain, cls.REFERENCE) or domain.endswith(cls.REFERENCE_SUFFIXES):
            return SourceTier.REFERENCE
        if cls._listed(domain, cls.NEWS):
            return SourceTier.NEWS
        return SourceTier.UNVETTED

    @classmethod
    def _listed(cls, domain: str, catalogue: frozenset[str]) -> bool:
        return any(cls._matches(domain, known) for known in catalogue)

    @staticmethod
    def _matches(domain: str, known: str) -> bool:
        return domain == known or domain.endswith("." + known)


class ResolvedBy(StrEnum):
    BENCHMARK_LABEL = "benchmark_label"
    ANALYST = "analyst"


@dataclass(frozen=True)
class PublisherOutcome:
    """Whether one publisher's evidence pointed at the verdict that ground truth (a benchmark label or an
    analyst) later confirmed. Never derived from the agent's own conclusion, which would teach it to trust
    whoever agrees with it."""

    domain: str
    agreed: bool
    resolved_by: ResolvedBy


@dataclass(frozen=True)
class TrackRecord:
    """How often a publisher's evidence agreed or disagreed with confirmed outcomes."""

    corroborated: int = 0
    contradicted: int = 0
    PRIOR_STRENGTH: ClassVar[float] = 4.0

    def reliability(self, prior: float, ceiling: float = 1.0) -> float:
        k = self.PRIOR_STRENGTH
        learned = (prior * k + self.corroborated) / (k + self.corroborated + self.contradicted)
        return min(ceiling, learned)


class ManipulationScan:
    """Text addressed to an AI reader rather than a human one: an instruction smuggled into a page or upload.
    A cheap pattern check; it flags, it does not decide, and a flagged source is trusted less."""

    PATTERNS: ClassVar[tuple[re.Pattern[str], ...]] = tuple(
        re.compile(pattern, re.IGNORECASE)
        for pattern in (
            r"\b(ignore|disregard|forget|override)\b[^.\n]{0,40}\b(previous|prior|above|earlier|all|any)\b"
            r"[^.\n]{0,20}\b(instructions?|prompts?|rules|guidance)\b",
            r"\b(note|message|instructions?|attention)\b[^.\n]{0,15}\b(for|to)\b[^.\n]{0,25}"
            r"\b(ai|a\.i\.|llm|language models?|assistants?|chatbots?|automated|bots?|agents?)\b",
            r"\b(report|mark|classify|rate|label|treat)\b[^.\n]{0,40}\bas\s+(true|false|accurate|verified|"
            r"no_adverse|no adverse|clean|legitimate)\b",
            r"\b(system prompt|you are now|new instructions|developer mode|jailbreak)\b",
            r"\b(do not|don't|never)\b[^.\n]{0,20}\b(cite|mention|report|disclose|flag)\b",
        )
    )

    @classmethod
    def flags(cls, text: str) -> tuple[str, ...]:
        found: list[str] = []
        for pattern in cls.PATTERNS:
            for match in pattern.finditer(text):
                start, end = max(0, match.start() - 40), min(len(text), match.end() + 40)
                found.append(" ".join(text[start:end].split()))
        return tuple(dict.fromkeys(found))


@dataclass(frozen=True)
class Source:
    """A publication as the agents read it: its content is the window every agent and the judge see."""

    READ_WINDOW: ClassVar[int] = 4000
    MANIPULATION_PENALTY: ClassVar[float] = 0.5
    url: str
    title: str
    content: str
    tier: SourceTier
    published: date | None = None
    manipulation_flags: tuple[str, ...] = field(default=(), compare=False)

    @classmethod
    def from_web(
        cls, url: str, title: str, content: str, published: date | None = None, tier: SourceTier | None = None
    ) -> "Source":
        window = content[: cls.READ_WINDOW]
        return cls(
            url,
            title,
            window,
            tier or DomainCatalogue.tier_of(cls.domain_of(url)),
            published,
            ManipulationScan.flags(window),
        )

    @classmethod
    def from_upload(cls, document: str, location: str, content: str) -> "Source":
        """One readable piece of an analyst's document; its domain is the document's name."""
        window = content[: cls.READ_WINDOW]
        return cls(
            f"upload://{document}/{location}",
            f"{document} ({location})",
            window,
            SourceTier.USER_PROVIDED,
            None,
            ManipulationScan.flags(window),
        )

    @property
    def is_upload(self) -> bool:
        return self.tier is SourceTier.USER_PROVIDED

    @property
    def domain(self) -> str:
        return self.domain_of(self.url)

    @staticmethod
    def domain_of(url: str) -> str:
        host = urlparse(url).netloc.lower() or url
        return host.removeprefix("www.")

    def reliability(self, track: TrackRecord) -> float:
        learned = track.reliability(self.tier.prior_reliability, self.tier.ceiling)
        return learned * (self.MANIPULATION_PENALTY if self.manipulation_flags else 1.0)

    @staticmethod
    def admiralty(reliability: float, is_upload: bool = False) -> str:
        """Admiralty source-reliability letter from the reliability number: the tier prior moved by the track
        record, but never past the tier's ceiling, so an unvetted site can at best reach C. An analyst's own
        upload is F, "cannot be judged": it is the thing under test."""
        if is_upload:
            return "F"
        for letter, floor in (("A", 0.9), ("B", 0.75), ("C", 0.6), ("D", 0.4)):
            if reliability >= floor:
                return letter
        return "E"
