import json
import re
from dataclasses import dataclass
from typing import ClassVar

from pydantic import JsonValue

from osint_harness.investigation.case_file import CaseFile
from osint_harness.investigation.evidence import Evidence, Stance, Strength
from osint_harness.investigation.source import Source, TrackRecord
from osint_harness.investigation.subject import Subject
from osint_harness.investigation.verdict import Belief, Verdict


class Estimative:
    """ICD-203 words of estimative probability, so the bottom line reads as an analyst would write it."""

    BANDS: ClassVar[tuple[tuple[float, str], ...]] = (
        (0.95, "almost certain"),
        (0.80, "very likely"),
        (0.55, "likely"),
        (0.45, "roughly even chance"),
        (0.20, "unlikely"),
        (0.05, "very unlikely"),
        (0.0, "almost no chance"),
    )

    @classmethod
    def phrase(cls, probability: float) -> str:
        return next(words for floor, words in cls.BANDS if probability >= floor)


class Credibility:
    """Admiralty information-credibility number (1-6) for one finding, judged apart from the reliability of
    whoever published it: how many independent publishers stand behind it, how directly, and whether the
    question it answers is contested. 5 (improbable) is never assigned by rule."""

    LABELS: ClassVar[dict[int, str]] = {
        1: "confirmed",
        2: "probably true",
        3: "possibly true",
        4: "doubtful",
        5: "improbable",
        6: "cannot be judged",
    }

    @classmethod
    def grade(cls, items: list[Evidence], publishers: set[str], contested: bool) -> int:
        if not items:
            return 6
        direct = any(item.strength is Strength.DIRECT and item.quote_verified for item in items)
        if contested or not direct:
            return 4
        if len(publishers) >= 3:
            return 1
        return 2 if len(publishers) == 2 else 3


class RegistryClaims:
    """Finds sentences that name a registry, list or database. Such a sentence may only stand if a tool that
    covers that record was actually called, or if it says plainly that the record was *not* checked."""

    RECORDS: ClassVar[dict[str, re.Pattern[str]]] = {
        "sanctions": re.compile(
            r"\b(OFAC|SDN|sanctions?[- ](lists?|databases?|registers?|screening)|consolidated (sanctions "
            r")?list|"
            r"OFSI|HM Treasury)\b",
            re.IGNORECASE,
        ),
        "insolvency_register": re.compile(
            r"\b(insolvency (registers?|records?|databases?|notices?)|Insolvenzbekanntmachung\w*|"
            r"bankruptcy (registers?|records?|database))\b",
            re.IGNORECASE,
        ),
        "company_register": re.compile(
            r"\b(Handelsregister|Unternehmensregister|Companies House|OpenCorporates|"
            r"(company|commercial|corporate|business) regist(er|ers|ry|ries))\b",
            re.IGNORECASE,
        ),
        "court_records": re.compile(
            r"\b(PACER|CourtListener|court (records|dockets?|database|filings search))\b", re.IGNORECASE
        ),
        "credit_bureau": re.compile(
            r"\b(Creditreform|Schufa|Dun ?(&|and) ?Bradstreet|Experian|Equifax|credit (bureaus?|reports?))\b",
            re.IGNORECASE,
        ),
        "legal_entity_identifier": re.compile(r"\b(GLEIF|LEI (register|database|lookup))\b", re.IGNORECASE),
        "sec_filings": re.compile(r"\b(EDGAR|SEC filings? (search|database))\b", re.IGNORECASE),
        "pep_lists": re.compile(r"\b(PEP (lists?|database|screening)|politically exposed)\b", re.IGNORECASE),
        "interpol": re.compile(r"\bInterpol\b", re.IGNORECASE),
    }
    ADMITS_NOT_CHECKED: ClassVar[re.Pattern[str]] = re.compile(
        r"\bnot (been )?(checked|queried|searched|consulted|accessed|available|covered|reachable)\b|"
        r"\b(could not|couldn't|cannot|can't|unable "
        r"to)\b[^.]{0,40}\b(check|query|search|access|consult|verify)|"
        r"\bno (access|connector|tool)\b|\b(recommend\w*|should be|next step|would need|outside the scope)\b",
        re.IGNORECASE,
    )

    @classmethod
    def unchecked(cls, sentence: str, checked: frozenset[str]) -> list[str]:
        """The records a sentence claims something about without any tool having looked at them."""
        named = [record for record, pattern in cls.RECORDS.items() if pattern.search(sentence)]
        if not named or cls.ADMITS_NOT_CHECKED.search(sentence):
            return []
        return [record for record in named if record not in checked]

    @staticmethod
    def sentences(text: str) -> list[str]:
        return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


@dataclass(frozen=True)
class Finding:
    statement: str
    citations: tuple[str, ...]
    credibility: int = 6

    @property
    def credibility_label(self) -> str:
        return Credibility.LABELS[self.credibility]


@dataclass(frozen=True)
class CitedSource:
    source: Source
    reliability: float

    @property
    def admiralty(self) -> str:
        return Source.admiralty(self.reliability, self.source.is_upload)


@dataclass(frozen=True)
class Search:
    """One research action as the trace recorded it, not as anyone later described it."""

    tool: str
    query: str
    step: int
    results: int
    failure: str | None
    decisive: bool


@dataclass(frozen=True)
class Coverage:
    """What the toolbox could reach, and what it was actually used to check."""

    reachable: dict[str, frozenset[str]]
    called: frozenset[str]
    EXPECTED: ClassVar[dict[str, str]] = {
        "sanctions": "Sanctions lists (OFAC SDN, EU, UN, UK)",
        "pep_lists": "Politically-exposed-person lists",
        "company_register": "Company registers",
        "insolvency_register": "Insolvency registers",
        "court_records": "Court dockets and judgments",
        "sec_filings": "SEC EDGAR filings",
        "legal_entity_identifier": "GLEIF legal-entity (LEI) records",
        "credit_bureau": "Credit bureaus",
        "interpol": "Interpol notices",
        "archived_pages": "Archived (Wayback) copies of pages",
    }

    @property
    def checked(self) -> frozenset[str]:
        return frozenset(record for tool in self.called for record in self.reachable.get(tool, frozenset()))

    def not_checked(self) -> list[str]:
        reachable = {record for records in self.reachable.values() for record in records}
        lines = []
        for record, label in self.EXPECTED.items():
            if record in self.checked:
                continue
            reason = "a tool exists but was not used" if record in reachable else "no connector"
            lines.append(f"{label}: not checked ({reason})")
        return lines


@dataclass(frozen=True)
class Report:
    subject: Subject
    verdict: Verdict
    confidence: float
    summary: str
    findings: tuple[Finding, ...]
    minor_adverse_items: tuple[str, ...]
    conflicts: tuple[str, ...]
    conflict_notes: tuple[str, ...]
    searches: tuple[Search, ...]
    checked: tuple[str, ...]
    not_checked: tuple[str, ...]
    withdrawn: tuple[str, ...]
    document_assessment: tuple[str, ...]
    document_claims: tuple[str, ...]
    manipulation_flags: tuple[str, ...]
    gaps: tuple[str, ...]
    next_steps: tuple[str, ...]
    sources: tuple[CitedSource, ...]
    SCHEMA_VERSION: ClassVar[str] = "2"

    @classmethod
    def assemble(
        cls,
        case_file: CaseFile,
        belief: Belief,
        summary: str,
        findings: list[Finding],
        conflicts: list[str],
        gaps: list[str],
        tracks: dict[str, TrackRecord],
        coverage: Coverage,
        next_steps: tuple[str, ...] = (),
        document_assessment: tuple[str, ...] = (),
    ) -> "Report":
        """The rules a report must obey whatever the model wrote:
        - a finding cites only sources the investigation retrieved, and never the analyst's own upload,
          which is the thing under test; a finding only the upload supports is reported as its claim;
        - a sentence about a registry or list that no called tool covers is withdrawn;
        - conflicts are the ones the case file computed; the model's prose only explains them;
        - searches, coverage and manipulation flags come from the case file, not from the model."""
        checked = coverage.checked
        withdrawn: list[str] = []

        def admissible(sentence: str) -> bool:
            unchecked = RegistryClaims.unchecked(sentence, checked)
            if unchecked:
                withdrawn.append(f"{sentence} [withdrawn: no tool checked {', '.join(unchecked)}]")
            return not unchecked

        grounded: list[Finding] = []
        unsupported: list[str] = []
        document_claims: list[str] = []
        for finding in findings:
            if not admissible(finding.statement):
                continue
            retrieved = [url for url in finding.citations if url in case_file.sources]
            external = tuple(url for url in retrieved if not case_file.sources[url].is_upload)
            if external:
                grounded.append(cls._graded(case_file, finding.statement, external))
            elif retrieved:
                document_claims.append(finding.statement)
            else:
                unsupported.append(f"Not established (no retrieved source supports it): {finding.statement}")
        cited_urls = dict.fromkeys(url for finding in grounded for url in finding.citations)
        cited = tuple(
            CitedSource(source, source.reliability(tracks.get(source.domain, TrackRecord())))
            for source in (case_file.sources[url] for url in cited_urls)
        )
        # Every piece of model prose is screened before `withdrawn` is frozen into the report.
        kept_summary = " ".join(s for s in RegistryClaims.sentences(summary) if admissible(s))
        kept_notes = tuple(note for note in conflicts if admissible(note))
        kept_gaps = tuple([gap for gap in gaps if admissible(gap)] + unsupported)
        # Next steps are, by definition, about records not yet checked: they are not claims, so not screened.
        kept_steps = tuple(next_steps)
        return cls(
            subject=case_file.subject,
            verdict=belief.verdict,
            confidence=belief.confidence,
            summary=kept_summary,
            findings=tuple(grounded),
            minor_adverse_items=tuple(
                dict.fromkeys(
                    f"{item.statement} ({item.severity.value if item.severity else 'unrated'}; {item.domain})"
                    for item in case_file.minor_adverse_items()
                )
            ),
            conflicts=tuple(
                f"{c.question.text} - supported by {', '.join(sorted(c.balance.supporting))} "
                f"(weight {c.balance.support_weight:.2f}) vs refuted by "
                f"{', '.join(sorted(c.balance.refuting))} (weight {c.balance.refute_weight:.2f})"
                for c in case_file.conflicts
            ),
            conflict_notes=kept_notes,
            searches=tuple(
                Search(
                    inquiry.tool.value,
                    inquiry.argument,
                    inquiry.step,
                    len(inquiry.sources),
                    inquiry.failure,
                    any(source.url in cited_urls for source in inquiry.sources),
                )
                for inquiry in case_file.inquiries
            ),
            checked=tuple(Coverage.EXPECTED.get(record, record) for record in sorted(checked)),
            not_checked=tuple(coverage.not_checked()),
            withdrawn=tuple(withdrawn),
            document_assessment=tuple(document_assessment) if case_file.subject.documents else (),
            document_claims=tuple(document_claims),
            manipulation_flags=tuple(
                f'{source.title or source.url}: "{flag}"'
                for source in case_file.sources.values()
                for flag in source.manipulation_flags
            ),
            gaps=kept_gaps,
            next_steps=kept_steps,
            sources=cited,
        )

    @staticmethod
    def _graded(case_file: CaseFile, statement: str, citations: tuple[str, ...]) -> Finding:
        items = [
            item
            for item in case_file.external_evidence
            if item.source_url in citations and item.stance is not Stance.CONTEXT
        ]
        contested_questions = {c.question.id for c in case_file.conflicts}
        contested = any(item.question_id in contested_questions for item in items)
        publishers = {case_file.publisher(item) for item in items}
        return Finding(statement, citations, Credibility.grade(items, publishers, contested))

    def citation_number(self, url: str) -> int:
        return [cited.source.url for cited in self.sources].index(url) + 1

    def to_markdown(self) -> str:
        subject = self.subject
        lines = [
            f"# Findings report: {subject.statement}",
            "",
            "## Bottom line",
            f"**{self.verdict.value}** — {Estimative.phrase(self.confidence)} ({self.confidence:.0%}), "
            f"as of {subject.as_of.isoformat()}.  ",
            f"**Subject type:** {subject.kind.value}"
            + (f"  \n**Identity:** {subject.identity}" if subject.disambiguators else ""),
            "",
            self.summary,
            "",
            "## Key findings",
        ]
        for finding in self.findings:
            refs = "".join(
                f"[{self.citation_number(url)}{self.sources[self.citation_number(url) - 1].admiralty}]"
                for url in finding.citations
            )
            lines.append(
                f"- {finding.statement} {refs} _(credibility {finding.credibility}: "
                f"{finding.credibility_label})_"
            )
        if not self.findings:
            lines.append("- No finding is supported by an independently retrieved source.")
        lines += ["", "## Minor adverse items (not material to the verdict)"]
        lines += [f"- {item}" for item in self.minor_adverse_items] or ["- None found."]
        lines += ["", "## Conflicting information"]
        lines += [f"- {conflict}" for conflict in self.conflicts] or [
            "- No open conflict between independent sources."
        ]
        lines += [f"  - Assessment: {note}" for note in self.conflict_notes]
        lines += [
            "",
            "## Searches performed",
            "",
            "| Round | Tool | Query | Results | Decisive |",
            "|---|---|---|---|---|",
        ]
        lines += [
            f"| {s.step} | {s.tool} | {s.query.replace('|', '/')} | "
            f"{s.failure or s.results} | {'yes' if s.decisive else ''} |"
            for s in self.searches
        ]
        lines += ["", "## Coverage", "", "Checked with a dedicated tool:"]
        lines += [f"- {record}" for record in self.checked] or [
            "- Only general web, news and encyclopedia search."
        ]
        lines += ["", "Not checked:"]
        lines += [f"- {record}" for record in self.not_checked] or ["- Nothing outstanding."]
        lines += [f"- {statement}" for statement in self.withdrawn]
        if subject.documents or self.manipulation_flags:
            lines += ["", "## Document assessment and manipulation flags"]
            lines += [f"- {note}" for note in self.document_assessment]
            lines += [
                f"- Asserted only by the provided document (not independently corroborated): {claim}"
                for claim in self.document_claims
            ]
            lines += [
                f"- Possible instruction aimed at an AI reader: {flag}" for flag in self.manipulation_flags
            ]
            if not (self.document_assessment or self.document_claims or self.manipulation_flags):
                lines.append("- Nothing to flag.")
        lines += ["", "## Gaps and recommended next steps"]
        lines += [f"- {gap}" for gap in self.gaps] or ["- None recorded."]
        lines += [f"- Next: {step}" for step in self.next_steps]
        lines += [
            "",
            "## Sources",
            "",
            "Letters are Admiralty source-reliability grades (A best, F cannot be judged).",
        ]
        for number, cited in enumerate(self.sources, start=1):
            source = cited.source
            dated = f", published {source.published.isoformat()}" if source.published else ""
            lines.append(
                f"{number}. ({cited.admiralty}) [{source.title or source.url}]({source.url}) — "
                f"{source.tier.value}, reliability {cited.reliability:.2f}{dated}"
            )
        if subject.documents:
            lines += ["", "## Documents provided"]
            lines += [f"- {document.name}" for document in subject.documents]
        return "\n".join(lines) + "\n"

    def to_json(self) -> str:
        subject = self.subject
        record: dict[str, JsonValue] = {
            "schema_version": self.SCHEMA_VERSION,
            "subject": {
                "kind": subject.kind.value,
                "statement": subject.statement,
                "entity": subject.entity,
                "disambiguators": list(subject.disambiguators),
                "as_of": subject.as_of.isoformat(),
            },
            "documents": [document.name for document in subject.documents],
            "verdict": self.verdict.value,
            "confidence": round(self.confidence, 4),
            "estimative": Estimative.phrase(self.confidence),
            "summary": self.summary,
            "findings": [
                {
                    "statement": f.statement,
                    "credibility": f.credibility,
                    "credibility_label": f.credibility_label,
                    "citations": list(f.citations),
                }
                for f in self.findings
            ],
            "minor_adverse_items": list(self.minor_adverse_items),
            "conflicts": list(self.conflicts),
            "conflict_notes": list(self.conflict_notes),
            "searches": [
                {
                    "step": s.step,
                    "tool": s.tool,
                    "query": s.query,
                    "results": s.results,
                    "failure": s.failure,
                    "decisive": s.decisive,
                }
                for s in self.searches
            ],
            "checked": list(self.checked),
            "not_checked": list(self.not_checked),
            "withdrawn_statements": list(self.withdrawn),
            "document_assessment": list(self.document_assessment),
            "document_claims": list(self.document_claims),
            "manipulation_flags": list(self.manipulation_flags),
            "gaps": list(self.gaps),
            "next_steps": list(self.next_steps),
            "sources": [
                {
                    "url": c.source.url,
                    "title": c.source.title,
                    "tier": c.source.tier.value,
                    "admiralty": c.admiralty,
                    "reliability": round(c.reliability, 3),
                    "published": c.source.published.isoformat() if c.source.published else None,
                }
                for c in self.sources
            ],
        }
        return json.dumps(record, indent=2, ensure_ascii=False)
