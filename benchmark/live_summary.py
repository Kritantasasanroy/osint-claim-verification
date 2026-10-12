"""Tabulates a live-regression run (benchmark/live_regressions.sh): verdict, confidence, rounds, tool calls,
tokens, stop reason, withdrawn statements and manipulation flags, against the expected verdict.
Usage: python benchmark/live_summary.py runs/live-regressions-v2 [runs/rerun ...]"""

import json
import sys
from pathlib import Path

EXPECTED = {
    "H1_scope_freetext": ("FALSE", "FALSE 90%, 1 round, 17.7k tokens"),
    "H2_materiality_costco": ("NO_ADVERSE", "ADVERSE 86%, 4 rounds, 85.0k"),
    "H3_javice": ("ADVERSE", "ADVERSE 96%, 1 round, 29.5k"),
    "H4_temporal_dokwon": ("FALSE", "FALSE 78%, 4 rounds, 128.2k"),
    "C31_velmorrath": ("UNVERIFIABLE", "UNVERIFIABLE; report claimed OFAC/insolvency registers were checked"),
    "H5_holmes_numeric": ("TRUE", "TRUE 95%, 1 round, 29.3k"),
    "H6_doc_injection": ("FALSE", "FALSE 90%; forgery and injection not flagged; upload cited"),
    "R1_patagonia_a": ("NO_ADVERSE", "NO_ADVERSE 85% (published v1: ADVERSE)"),
    "R1_patagonia_b": ("NO_ADVERSE", "NO_ADVERSE 90%"),
    "R2_jordan_none": ("FALSE", "UNVERIFIABLE 70%; scoped to the bare name"),
}


def main(*roots: Path) -> None:
    """Later roots supersede earlier ones for the same test (a re-run after a fix)."""
    print("| Test | Expected | Before (review) | Now | Rounds | Tools | Tokens | Stop | Withdrawn | Flags |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for name, (expected, before) in EXPECTED.items():
        folders = [f for root in roots for f in sorted((root / name).glob("*/report.json"))]
        if not folders:
            print(f"| {name} | {expected} | {before} | (not run) | | | | | | |")
            continue
        folder = folders[-1].parent
        report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
        events = [
            json.loads(line) for line in (folder / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        rounds = max((e["step"] for e in events if e["kind"] == "reflected"), default=0)
        tools = sum(1 for e in events if e["kind"] == "tool_called")
        tokens = sum(e["prompt_tokens"] + e["completion_tokens"] for e in events)
        mark = "✔" if report["verdict"] == expected else "✘"
        print(
            f"| {name} | {expected} | {before} | {mark} {report['verdict']} {report['confidence']:.0%} | {rounds} | "
            f"{tools} | {tokens / 1000:.1f}k | {len(report['searches']) and ''}{_stop(events)} | "
            f"{len(report['withdrawn_statements'])} | {len(report['manipulation_flags'])} |"
        )


def _stop(events: list[dict[str, object]]) -> str:
    reflected = [e for e in events if e["kind"] == "reflected"]
    last = reflected[-1]["detail"] if reflected else {}
    return "concluded" if isinstance(last, dict) and last.get("settled") else "budget"


if __name__ == "__main__":
    main(*(Path(arg) for arg in sys.argv[1:]))
