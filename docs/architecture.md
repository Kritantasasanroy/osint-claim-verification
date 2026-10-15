# Architecture

![Architecture](architecture.png)

Rendered (PNG and SVG) from the Mermaid source below, `docs/architecture.mmd`. Yellow boxes are rules enforced in
typed code; white boxes are model calls. Every decision that matters to an analyst (when to stop, how confident to
be, what a report may claim) is a yellow box.

```mermaid
flowchart TB
    subgraph INPUT["1 · Input"]
        direction LR
        T["Raw analyst text<br/>company · person · claim · question"]
        F["Files<br/>PDF · image · DOCX · XLSX · PPTX · HTML · EML · TXT"]
    end

    subgraph INTAKE["2 · Intake and scoping"]
        direction LR
        DI["DocumentIntake<br/>text layer, else nemotron-parse OCR"] --> SC["Planner · scope<br/>entity · disambiguators · full assertion · as-of"]
        SC --> SCK["ScopeCheck (code)<br/>names, details, claim-vs-name kept?<br/>retry once, else analyst's words"]
    end

    subgraph LOOP["3 · Investigator loop"]
        direction TB
        PL["Planner · plan<br/>questions with roles<br/>identity · core_fact · verdict_deciding"] --> RS["Researcher<br/>choose tool calls"]
        RS --> QL["QueryLedger (code)<br/>rejects repeated queries, asks once more"]
        QL --> EV["Evaluator<br/>evidence: stance · strength · points_to · severity<br/>full-quote check · dates"]
        EV --> RF["Reflector<br/>model belief + critique<br/>(sees posterior + ACH matrix)"]
        RF --> CONF["Confidence (code)<br/>EvidencePosterior → pool → calibrator<br/>shipped belief, never 100%"]
        CONF --> GATE["Stopping gate (code)<br/>2 independent clusters on verdict questions<br/>weight ≥ 1 · authoritative for ADVERSE/FALSE<br/>materiality · no conflict · window per memory mode"]
        GATE -- "not settled" --> RS
        GATE -- "settled" --> CR["Red-team critic<br/>(judge model)<br/>may buy one extra check"]
        CR -- "new check" --> RS
        CR -- "nothing new / budget spent" --> RP["Reporter<br/>BLUF draft · findings · typed facts"]
        RP --> VAL["Report validators (code)<br/>citations retrieved only · uploads never corroborate<br/>registry claims without a tool withdrawn<br/>searches + coverage from the trace<br/>Admiralty letters · credibility 1-6 · manipulation flags"]
    end

    subgraph SOURCES["External sources (ResearchTool, each declares what it covers)"]
        direction LR
        WS["Tavily web / news<br/>(publication dates)"] ~~~ RD["Tavily extract"] ~~~ WK["Wikipedia"]
        WD["Wikidata<br/>QIDs, dates"] ~~~ GL["GLEIF<br/>LEI records"] ~~~ SEC["SEC EDGAR<br/>filings"]
        CL["CourtListener<br/>opinions"] ~~~ WB["Wayback<br/>archived pages"] ~~~ OS["OpenSanctions<br/>(only with a key)"]
    end

    subgraph MEMORY["Memory"]
        direction LR
        STM["Short-term · CaseFile<br/>questions · sources · publisher clusters<br/>evidence · steps (LLM belief, posterior, shipped)"]
        LTM[("Long-term · SQLite<br/>typed facts (entity, relation, value, valid_from/to)<br/>supersession · namesake gate · usage counters<br/>specific lessons · publisher track records<br/>(dev-split ground truth only, tier ceilings)")]
    end

    subgraph OUT["4 · Outputs"]
        direction LR
        MD["report.md · report.json (schema v2)"] ~~~ TR["trace.jsonl + prompts.jsonl<br/>model id · prompt hashes · raw output"]
    end

    subgraph EVAL["5 · Evaluation (offline, ground truth)"]
        direction LR
        BM["Benchmark v2: 128 cases · 9 slices<br/>dev / test split · BenchmarkAudit"] --> BR["Runner + run_manifest.json<br/>closed_book · none · short · long · long_only<br/>seeds · graded scoping · --pre-scoped"]
        BR --> JG["Judge (other model family)<br/>atomic facts · κ vs human gold"]
        JG --> ST["Stats<br/>bootstrap CIs · McNemar · permutation<br/>stability · ECE/Brier/AURC"]
        ST --> SB["summary.md · charts<br/>baseline first"]
    end

    T --> SC
    F --> DI
    SCK --> PL
    RS <--> SOURCES
    LOOP <--> STM
    LTM -- "recall (re-asked on follow-ups) · reliability" --> PL
    VAL --> MD
    VAL -- "own conclusions only" --> LTM
    LOOP -. "every event" .-> TR
    BR -. "drives" .-> LOOP
    TR -. "graded from" .-> ST

    LLM[["NVIDIA NIM · nemotron-3-super-120b (agents)<br/>z-ai/glm-5.3-flash (judge, red-team critic)<br/>JSON-schema answers · seeded requests"]]
    LOOP -.- LLM

    classDef code fill:#fff4d6,stroke:#b8860b,stroke-width:2px,color:#000
    class SCK,QL,CONF,GATE,VAL code
```

## Responsibilities

| Component | Owns | Never does |
|---|---|---|
| `Planner` + `ScopeCheck` | scoping raw text into entity, disambiguators, full assertion and as-of date; the questions and their roles | dropping a name, a disambiguating detail or the claim itself (code retries once, then falls back to the analyst's words) |
| `Researcher` + `QueryLedger` | choosing tools and arguments for open questions | repeating a query: the ledger rejects it in every memory mode |
| `Evaluator` + `QuoteCheck` | turning sources into `Evidence` with stance, strength, verdict direction, severity, date | trusting a quote it cannot find in full in the source (demoted to weak, marked unverified) |
| `Reflector` | the model's belief, critique, follow-ups, distrusted memories, conclude/continue | setting the shipped confidence or stopping on its own |
| `EvidencePosterior` + `ConfidenceCalibrator` | the shipped belief: verdict from a pool of model and posterior; confidence from the posterior (or a dev-fitted calibrator), never 100% | using the model's verbalised probability as the output |
| `CaseFile.unmet_conditions` (the gate) | when a case may close: independent clusters on verdict questions, weight, authoritative sources, materiality, conflicts, all inside the memory mode's window | counting identity confirmations as corroboration of a verdict |
| `Critic` (judge model) | one red-team pass before closing; may buy one extra check | running more than once per investigation |
| `Reporter` + `Report.assemble` | prose and draft findings; then code adds searches, coverage, Admiralty letters, credibility, manipulation flags, minor adverse items | citing unretrieved sources or the analyst's own upload; claiming a registry was checked when no tool covers it |
| `Investigator` | loop, budget, concurrency, trace | any business decision |
| `LongTermMemory` | typed temporal facts with supersession, namesake gate, usage counters, specific lessons, publisher track records | learning track records from its own conclusions (only from dev-split labels or an analyst), exceeding a tier's ceiling |
| `ClosedBookInvestigator` | the floor: same model and rubric, no tools, graded identically | searching |
| `BenchmarkRunner` + `RunManifest` | modes × seeds × cases, graded scoping, resume within one code version | mixing results from two SHAs in one directory |
| `Scoreboard` + `stats` | CIs, paired tests against the closed-book floor, stability, calibration of three confidence signals | reporting a rate without its interval |
| `Transport` | retries, concurrency cap, separate LLM and search caches | |
