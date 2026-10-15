# Phase 3: memory (MEM1–MEM4)

| ID | Status | Notes |
|---|---|---|
| MEM1 | **Done** | Typed facts `(entity_id, entity_label, relation, value, valid_from, valid_to, observed_at, source_urls)`. A new value for the same entity and relation supersedes the old one (sets `valid_to`). Recall shows current facts only; `history()` returns superseded ones. `recalled`/`distrusted` counters demote often-distrusted memories. Test: the Milton sentence → pardon supersession. |
| MEM2 | **Partial** | Lessons must name a tool, publisher domain or record type (`LessonCheck`), otherwise they are not stored, and they are stored at confidence 0.5, not 1.0. Not done: expiring lessons by measured effect on dev, which needs repeated dev runs. |
| MEM3 | **Partial** | `long_only` mode and seed-specific shuffled case orders (`--shuffle-order`) exist. Not done: the longitudinal T0/T1 slice with changed facts. The v2 temporal-state slice tests changed facts but not the same entity twice across a simulated gap. |
| MEM4 | **Done** | Every controller computation (gate, conflicts, posterior, supporters, screening) takes the memory mode's visible window. Test: `test_the_none_mode_gate_sees_only_its_own_window`. The question list (the plan) remains visible in `none`, and this is documented. |
