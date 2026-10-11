import argparse
import asyncio
import re
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path

from osint_harness.evaluation.agreement import GoldFile, measure, template
from osint_harness.evaluation.benchmark import Benchmark, Split
from osint_harness.evaluation.counterfactual import CounterfactualRunner
from osint_harness.evaluation.runner import BenchmarkRunner, RunPlan
from osint_harness.harness import Harness, Intervention
from osint_harness.investigation.case_file import MemoryMode
from osint_harness.investigator import Budget
from osint_harness.settings import Settings
from osint_harness.trace import TraceLog


class CommandLine:
    """`investigate` one subject from text and/or files, or `benchmark` the harness on ground-truth cases."""

    def __init__(self) -> None:
        self._parser = argparse.ArgumentParser(
            prog="osint_harness", description="Agentic OSINT investigations"
        )
        commands = self._parser.add_subparsers(dest="command", required=True)
        investigate = commands.add_parser("investigate", help="Investigate a company, person or claim")
        investigate.add_argument(
            "text", nargs="?", default="", help="The subject, in words (optional with --file)"
        )
        investigate.add_argument("--file", action="append", type=Path, default=[], help="Document to include")
        investigate.add_argument(
            "--memory",
            choices=[m.value for m in MemoryMode if m.investigates],
            default=MemoryMode.LONG.value,
        )
        investigate.add_argument("--memory-path", type=Path, default=Path(".memory/long_term.sqlite3"))
        investigate.add_argument("--out", type=Path, default=Path("runs"))
        investigate.add_argument("--as-of", type=date.fromisoformat, default=date.today(), help="YYYY-MM-DD")
        investigate.add_argument("--max-steps", type=int, default=Budget.max_steps)
        investigate.add_argument("--max-tool-calls", type=int, default=Budget.max_tool_calls)
        investigate.add_argument("--no-cache", action="store_true", help="Always call live services")
        benchmark = commands.add_parser("benchmark", help="Run and grade the benchmark under each mode")
        benchmark.add_argument("--cases-file", type=Path, default=Path("benchmark/cases.json"))
        benchmark.add_argument("--cases", nargs="*", default=[], help="Only these case IDs (default: all)")
        benchmark.add_argument(
            "--modes",
            nargs="+",
            choices=[m.value for m in MemoryMode],
            default=[
                MemoryMode.CLOSED_BOOK.value,
                MemoryMode.NONE.value,
                MemoryMode.SHORT.value,
                MemoryMode.LONG.value,
            ],
        )
        benchmark.add_argument(
            "--seeds", type=int, default=1, help="Seeds per case and mode (3 for a final run)"
        )
        benchmark.add_argument("--split", choices=[s.value for s in Split], default=None)
        benchmark.add_argument(
            "--pre-scoped", action="store_true", help="Ablation: skip scoping and use each case's gold scope"
        )
        benchmark.add_argument(
            "--shuffle-order", action="store_true", help="Seed-specific long-memory case order"
        )
        benchmark.add_argument("--run-dir", type=Path, default=Path("results"))
        benchmark.add_argument("--force-new", action="store_true", help="Overwrite a run dir from other code")
        benchmark.add_argument("--max-steps", type=int, default=Budget.max_steps)
        benchmark.add_argument("--max-tool-calls", type=int, default=Budget.max_tool_calls)
        benchmark.add_argument("--llm-cache", choices=["on", "off"], default="off")
        benchmark.add_argument("--search-cache", choices=["on", "off"], default="on")
        benchmark.add_argument(
            "--estimate-only", action="store_true", help="Print the cost estimate and stop"
        )
        benchmark.add_argument(
            "--concurrency",
            type=int,
            default=4,
            help="none/short investigations at once; each long-memory stream runs alongside as one more",
        )
        gold = commands.add_parser("gold-template", help="Export a blind labelling file from a run (E5, E7)")
        gold.add_argument("run_dir", type=Path)
        gold.add_argument("--out", type=Path, default=Path("benchmark/judge_gold.json"))
        diagnose = commands.add_parser(
            "diagnose", help="Counterfactual diagnosis of a run's wrong episodes (E6)"
        )
        diagnose.add_argument("run_dir", type=Path)
        diagnose.add_argument("--cases-file", type=Path, default=Path("benchmark/cases_v2.json"))
        diagnose.add_argument("--mode", default=MemoryMode.SHORT.value)
        diagnose.add_argument(
            "--only",
            nargs="+",
            choices=[i.value for i in Intervention],
            default=[i.value for i in Intervention],
        )
        agreement = commands.add_parser("agreement", help="Judge-human kappa and reward-rating rho")
        agreement.add_argument("run_dir", type=Path)
        agreement.add_argument("--gold", type=Path, default=Path("benchmark/judge_gold.json"))

    def run(self, argv: list[str] | None = None) -> None:
        arguments = self._parser.parse_args(argv)
        if arguments.command == "benchmark":
            asyncio.run(BenchmarkRequest.from_arguments(arguments).carry_out())
            return
        if arguments.command == "gold-template":
            exported = template(Path(arguments.run_dir))
            Path(arguments.out).write_text(exported.model_dump_json(indent=1), encoding="utf-8")
            print(
                f"{len(exported.items)} items and {len(exported.ratings)} reports to label: {arguments.out}"
            )
            return
        if arguments.command == "diagnose":
            asyncio.run(
                self._diagnose(
                    Path(arguments.cases_file),
                    Path(arguments.run_dir),
                    str(arguments.mode),
                    tuple(Intervention(name) for name in arguments.only),
                )
            )
            return
        if arguments.command == "agreement":
            labels = GoldFile.model_validate_json(Path(arguments.gold).read_text(encoding="utf-8"))
            print(measure(Path(arguments.run_dir), labels).to_markdown())
            return
        request = InvestigationRequest.from_arguments(arguments)
        if not request.text.strip() and not request.files:
            self._parser.error("give the subject as text, or at least one --file to derive it from")
        missing = [str(path) for path in request.files if not path.is_file()]
        if missing:
            self._parser.error(f"file not found: {', '.join(missing)}")
        asyncio.run(request.carry_out())

    @staticmethod
    async def _diagnose(
        cases_file: Path, run_dir: Path, mode: str, interventions: tuple[Intervention, ...]
    ) -> None:
        settings = replace(Settings.from_environment(), llm_cache=False, search_cache=True)
        runner = CounterfactualRunner(
            Harness.connect(settings), Benchmark.load(cases_file), cases_file.parent, run_dir, Budget()
        )
        wrong = runner.wrong_episodes(mode)
        print(
            f"{len(wrong)} wrong episodes x {len(Intervention)} interventions = "
            f"{len(wrong) * len(Intervention)} re-runs"
        )
        print((await runner.diagnose(mode, interventions)).to_markdown())


@dataclass(frozen=True)
class InvestigationRequest:
    text: str
    files: tuple[Path, ...]
    mode: MemoryMode
    memory_path: Path
    out: Path
    as_of: date
    budget: Budget
    use_cache: bool

    @classmethod
    def from_arguments(cls, arguments: argparse.Namespace) -> "InvestigationRequest":
        return cls(
            text=str(arguments.text),
            files=tuple(Path(path) for path in arguments.file),
            mode=MemoryMode(arguments.memory),
            memory_path=Path(arguments.memory_path),
            out=Path(arguments.out),
            as_of=arguments.as_of,
            budget=Budget(max_steps=int(arguments.max_steps), max_tool_calls=int(arguments.max_tool_calls)),
            use_cache=not bool(arguments.no_cache),
        )

    async def carry_out(self) -> None:
        settings = replace(Settings.from_environment(), llm_cache=self.use_cache, search_cache=self.use_cache)
        harness = Harness.connect(settings)
        documents = tuple([await harness.intake.read(path) for path in self.files])
        for document in documents:
            methods = ", ".join(sorted(m.value for m in document.methods))
            print(f"Read {document.name}: {len(document.text)} characters ({methods})")
        label = re.sub(r"[^a-z0-9]+", "-", (self.text or documents[0].name).lower()).strip("-")[:40]
        folder = self.out / f"{datetime.now():%Y%m%d-%H%M%S}-{label}"
        trace = TraceLog(folder / "trace.jsonl", folder.name)
        investigator = harness.investigator(self.mode, self.memory_path, self.budget)
        subject = await investigator.scope(self.text, documents, trace, self.as_of)
        print(f"Investigating {subject.kind.value}: {subject.statement} (as of {subject.as_of.isoformat()})")
        investigation = await investigator.investigate(subject, trace)
        report = investigation.report
        (folder / "report.md").write_text(report.to_markdown(), encoding="utf-8")
        (folder / "report.json").write_text(report.to_json(), encoding="utf-8")
        print(
            f"Verdict {report.verdict.value} at {report.confidence:.0%} "
            f"after {len(investigation.case_file.steps)} steps, "
            f"{investigation.tool_calls} tool calls, {investigation.usage.total} tokens "
            f"(stopped: {investigation.stop_reason.value})"
        )
        print(f"Report: {folder / 'report.md'}")
        print(f"Trace:  {folder / 'trace.jsonl'}")


@dataclass(frozen=True)
class CostEstimate:
    """A rough upper bound printed before any benchmark spends money (prices are the configured ones)."""

    investigations: int
    tokens: int
    search_calls: int
    usd: float
    # Median of the 9 completed live regression runs (65k-171k) on the post-review code.
    TOKENS_PER_INVESTIGATION = 85_000
    TOKENS_CLOSED_BOOK = 1_500
    SEARCH_CALLS_PER_INVESTIGATION = 12

    @classmethod
    def of(cls, cases: int, modes: tuple[MemoryMode, ...], seeds: int, settings: Settings) -> "CostEstimate":
        investigating = sum(1 for m in modes if m.investigates) * cases * seeds
        closed = sum(1 for m in modes if not m.investigates) * cases * seeds
        tokens = investigating * cls.TOKENS_PER_INVESTIGATION + closed * cls.TOKENS_CLOSED_BOOK
        price = (settings.price.input_per_mtok * 0.85 + settings.price.output_per_mtok * 0.15) / 1_000_000
        return cls(
            investigating + closed, tokens, investigating * cls.SEARCH_CALLS_PER_INVESTIGATION, tokens * price
        )

    def __str__(self) -> str:
        return (
            f"Estimate: {self.investigations} episodes, up to ~{self.tokens / 1e6:.1f}M tokens "
            f"(~${self.usd:.2f} at configured prices), up to ~{self.search_calls} search/tool calls "
            "(fewer with the search cache warm)."
        )


@dataclass(frozen=True)
class BenchmarkRequest:
    cases_file: Path
    case_ids: tuple[str, ...]
    plan: RunPlan
    run_dir: Path
    budget: Budget
    concurrency: int
    llm_cache: bool
    search_cache: bool
    estimate_only: bool

    @classmethod
    def from_arguments(cls, arguments: argparse.Namespace) -> "BenchmarkRequest":
        return cls(
            cases_file=Path(arguments.cases_file),
            case_ids=tuple(str(case_id) for case_id in arguments.cases),
            plan=RunPlan(
                modes=tuple(MemoryMode(mode) for mode in arguments.modes),
                seeds=tuple(range(int(arguments.seeds))),
                split=Split(arguments.split) if arguments.split else None,
                pre_scoped=bool(arguments.pre_scoped),
                shuffle_long_order=bool(arguments.shuffle_order),
                force_new=bool(arguments.force_new),
            ),
            run_dir=Path(arguments.run_dir),
            budget=Budget(max_steps=int(arguments.max_steps), max_tool_calls=int(arguments.max_tool_calls)),
            concurrency=int(arguments.concurrency),
            llm_cache=arguments.llm_cache == "on",
            search_cache=arguments.search_cache == "on",
            estimate_only=bool(arguments.estimate_only),
        )

    async def carry_out(self) -> None:
        benchmark = Benchmark.load(self.cases_file).split(self.plan.split)
        benchmark = benchmark.only(list(self.case_ids)) if self.case_ids else benchmark
        settings = replace(
            Settings.from_environment(), llm_cache=self.llm_cache, search_cache=self.search_cache
        )
        estimate = CostEstimate.of(len(benchmark.cases), self.plan.modes, len(self.plan.seeds), settings)
        print(estimate)
        if self.estimate_only:
            return
        harness = Harness.connect(settings)
        print(
            f"Running {len(benchmark.cases)} cases x {len(self.plan.modes)} modes x {len(self.plan.seeds)} "
            f"seeds "
            f"into {self.run_dir}"
        )
        runner = BenchmarkRunner(
            harness, benchmark, self.cases_file, self.run_dir, self.budget, self.concurrency
        )
        summary = await runner.run(self.plan)
        print(summary.to_markdown())
        print(f"Summary: {self.run_dir / 'summary.json'}  Charts: {self.run_dir / 'charts'}")
