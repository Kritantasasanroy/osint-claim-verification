from dataclasses import dataclass
from datetime import date

from osint_harness.agents.rubric import dated
from osint_harness.investigation.case_file import CaseFile
from osint_harness.investigation.evidence import Evidence
from osint_harness.memory import Recollection


@dataclass(frozen=True)
class CaseBriefing:
    """The case file as an agent is allowed to see it: what the memory mode keeps visible, in prose."""

    case_file: CaseFile
    visible_from_step: int
    recollections: tuple[Recollection, ...] = ()

    @property
    def subject(self) -> str:
        subject = self.case_file.subject
        allowed = ", ".join(verdict.value for verdict in subject.kind.allowed_verdicts)
        lines = [
            dated(subject),
            f"Subject ({subject.kind.value}): {subject.statement}",
            f"Allowed verdicts: {allowed}",
        ]
        if subject.disambiguators:
            lines.append(
                f"Which entity: {subject.identity}. Evidence about a namesake that does not fit this is not "
                "evidence about the subject."
            )
        if subject.documents:
            lines.append(
                "Documents provided by the analyst (under test, never proof of themselves): "
                + ", ".join(d.name for d in subject.documents)
            )
        return "\n".join(lines)

    @property
    def questions(self) -> str:
        return (
            "\n".join(f"{q.id} [{q.status.value}, {q.role.value}] {q.text}" for q in self.case_file.questions)
            or "(none yet)"
        )

    @property
    def visible_evidence(self) -> list[Evidence]:
        """Newest dated evidence first, so the present state of affairs is read before older reports."""
        visible = self.case_file.evidence_from_step(self.visible_from_step)
        return sorted(visible, key=lambda item: item.published or date.min, reverse=True)

    @property
    def evidence(self) -> str:
        visible = self.visible_evidence
        if not visible:
            return "(no evidence yet)"
        return "\n".join(
            f"- {item.question_id} | {item.stance.value} | {item.strength.value} | weight {item.weight:.2f} "
            f"| "
            f"points to {item.direction.value if item.direction else '-'}"
            + (f" ({item.severity.value})" if item.severity else "")
            + f" | {item.domain} | published {item.published.isoformat() if item.published else 'undated'}"
            + (" STALE" if self.case_file.is_stale(item) else "")
            + (" | quote NOT verified" if not item.quote_verified else "")
            + f" | {item.statement} | quote: <untrusted_source>{item.quote[:200]}</untrusted_source> | "
            f"{item.source_url}"
            for item in visible
        )

    @property
    def conflicts(self) -> str:
        found = self.case_file.conflicts_from(self.visible_from_step)
        if not found:
            return "(no conflicts detected)"
        return "\n".join(
            f"- {c.question.id} {c.question.text}: supporting {sorted(c.balance.supporting)} "
            f"(weight {c.balance.support_weight:.2f}) vs refuting {sorted(c.balance.refuting)} "
            f"(weight {c.balance.refute_weight:.2f})"
            for c in found
        )

    @property
    def posterior(self) -> str:
        posterior = self.case_file.posterior(self.visible_from_step)
        return ", ".join(
            f"{verdict.value} {p:.0%} ({posterior.independent_supporters(verdict)} independent publishers)"
            for verdict, p in posterior.probabilities
        )

    @property
    def hypotheses(self) -> str:
        """A compact analysis-of-competing-hypotheses matrix: each decisive item against each verdict."""
        allowed = self.case_file.subject.kind.allowed_verdicts
        rows = [
            f"- {item.domain}: {item.statement[:90]} | "
            + " ".join(f"{v.value}:{'+' if item.direction is v else '-'}" for v in allowed)
            for item in self.visible_evidence
            if item.direction is not None
        ]
        return "\n".join(rows[:15]) or "(no decisive evidence yet)"

    @property
    def belief_history(self) -> str:
        steps = [step for step in self.case_file.steps if step.number >= self.visible_from_step]
        return (
            "\n".join(f"step {s.number}: {s.belief.verdict.value} ({s.belief.confidence:.0%})" for s in steps)
            or "(no belief yet)"
        )

    @property
    def inquiries(self) -> str:
        done = self.case_file.inquiries_from_step(self.visible_from_step)
        return (
            "\n".join(
                f"- step {i.step}: {i.tool.value}('{i.argument}') -> {i.outcome.value}, "
                f"{len(i.sources)} sources" + (f" ({i.failure})" if i.failure else "")
                for i in done
            )
            or "(none yet)"
        )

    @property
    def readable_urls(self) -> str:
        urls = [
            f"- {source.url} ({source.title[:80]})"
            for inquiry in self.case_file.inquiries_from_step(self.visible_from_step)
            for source in inquiry.sources
        ]
        return "\n".join(urls[-25:]) or "(none)"

    @property
    def memories(self) -> str:
        if not self.recollections:
            return "(no long-term memories recalled)"
        return "\n".join(f"- {r.label} {r.describe()}" for r in self.recollections)

    def excerpt(self, number: int, url: str) -> str:
        source = self.case_file.sources[url]
        published = f" | published {source.published.isoformat()}" if source.published else ""
        return (
            f"[SOURCE {number}] {source.title} | {source.url} | tier {source.tier.value}{published}\n"
            f"<untrusted_source id={number}>\n{source.content}\n</untrusted_source>"
        )
