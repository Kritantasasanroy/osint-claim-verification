"""Writes each case's closed-book probe (E2) into a cases file from a closed_book run: closed_book_correct is
True if the same model with no tools got the case right on seed 0. Cases the probe gets wrong are where
retrieval has to earn its cost. Usage: python benchmark/record_probe.py benchmark/cases_v2.json RUN_DIR"""

import json
import sys
from pathlib import Path


def main(cases_file: Path, run_dir: Path) -> None:
    benchmark = json.loads(cases_file.read_text(encoding="utf-8"))
    recorded = 0
    for case in benchmark["cases"]:
        result = run_dir / "closed_book" / "seed0" / case["id"] / "result.json"
        if result.exists():
            # Re-scored against the current labels, so a relabelled case never keeps a stale probe.
            verdict = json.loads(result.read_text(encoding="utf-8"))["verdict"]
            case["closed_book_correct"] = verdict in case["acceptable_verdicts"]
            recorded += 1
    cases_file.write_text(json.dumps(benchmark, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"recorded the closed-book probe for {recorded} of {len(benchmark['cases'])} cases")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
