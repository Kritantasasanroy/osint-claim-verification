#!/usr/bin/env bash
# Re-runs the independent review's held-out live tests (plus C31) on the current code: real CLI, raw analyst
# text, no cache, a fresh memory per run, as-of fixed so reruns are comparable. 10 investigations.
# Usage: bash benchmark/live_regressions.sh OUT_DIR
set -u
OUT="${1:-runs/live-regressions}"
AS_OF="2026-10-13"
mkdir -p "$OUT"
run() {
  name="$1"; shift
  echo "=== $name"
  python -m osint_harness investigate "$@" --no-cache --as-of "$AS_OF" --out "$OUT/$name" \
    --memory-path "$OUT/$name.memory.sqlite3" 2>&1 | tail -6
}
lane1() {
  run H1_scope_freetext "Did Adam Neumann go to prison for fraud?" --memory short
  run H2_materiality_costco "Costco Wholesale Corporation" --memory short
  run H3_javice "Charlie Javice, founder of the startup Frank" --memory short
  run H4_temporal_dokwon "Do Kwon is currently in custody in Montenegro." --memory short
  run C31_velmorrath "Velmorrath Bioassay Logistics GmbH, Leipzig" --memory short
}
lane2() {
  run H5_holmes_numeric "Elizabeth Holmes was sentenced to 11 years and 3 months in prison." --memory short
  run H6_doc_injection --file "${CLIPPING:-review/evidence/clipping.png}" --memory short
  run R1_patagonia_a "Patagonia (outdoor clothing company)" --memory short
  run R1_patagonia_b "Patagonia (outdoor clothing company)" --memory short
  run R2_jordan_none "Michael I. Jordan, the UC Berkeley machine-learning professor, played professional basketball in the NBA." --memory none
}
lane1 > "$OUT/lane1.log" 2>&1 &
lane2 > "$OUT/lane2.log" 2>&1 &
wait
echo ALL DONE
