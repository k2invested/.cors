# Semantic Tree Example — Multi-Layer Chain Construction & Extraction

> A concrete walkthrough of a complex task decomposed into three layers via consecutive reason_needed passes, with every gap axis, every embedding type, and the full deterministic extraction round-trip.

---

## The Task

> "Research all London borough councils, compile property data for each, generate a comparative report, and build a dashboard"

This requires three layers, multiple new .st files, embeddings of existing ones, background triggers with await checkpoints, and full gap configuration on every step.

---

## Pass 1: reason_needed (build leaf chains — Layer 0)

The agent's first reason pass constructs the lowest-level chains. These must exist before anything can embed them.

```
chain:a1b2c3  "leaf chain construction" (active)
  origin: "complex task requires multi-layer decomposition"

  ── NEW .st: council_scrape ──────────────────────────────────────
  │
  ├─ step:f001  "resolve target council website"
  │   gap config:
  │     desc:         "fetch council planning portal URL and structure"
  │     content_refs: [HEAD]
  │     step_refs:    [step:f001]
  │     vocab:        hash_resolve_needed
  │     relevance:    1.0
  │     confidence:   0.9
  │     grounded:     0.0 (kernel computes)
  │     post_diff:    false
  │
  ├─ step:f002  "scrape council data via command"
  │   gap config:
  │     desc:         "execute scraper against resolved council URL"
  │     content_refs: [step:f001]          ← refs the resolve step
  │     step_refs:    [step:f001]
  │     vocab:        command_needed
  │     relevance:    0.9
  │     confidence:   0.8
  │     grounded:     0.0
  │     post_diff:    true                 ← may fail, needs branching
  │
  └─ step:f003  "verify scraped data integrity"
      gap config:
        desc:         "validate scraped JSON against expected council schema"
        content_refs: [step:f002]          ← refs the scrape output
        step_refs:    [step:f001, step:f002]
        vocab:        hash_resolve_needed
        relevance:    0.8
        confidence:   0.9
        grounded:     0.0
        post_diff:    false                ← deterministic check

  ── NEW .st: property_lookup ─────────────────────────────────────
  │
  ├─ step:f010  "resolve land registry API endpoint"
  │   gap config:
  │     desc:         "fetch land registry API config from workspace"
  │     content_refs: [HEAD]
  │     step_refs:    []
  │     vocab:        hash_resolve_needed
  │     relevance:    1.0
  │     confidence:   0.9
  │     grounded:     0.0
  │     post_diff:    false
  │
  ├─ step:f011  "query land registry for borough properties"
  │   gap config:
  │     desc:         "execute land registry API query with borough code"
  │     content_refs: [step:f010]
  │     step_refs:    [step:f010]
  │     vocab:        command_needed
  │     relevance:    0.9
  │     confidence:   0.7
  │     grounded:     0.0
  │     post_diff:    true                 ← API may rate-limit
  │
  ├─ step:f012  "query EPC ratings for matched properties"
  │   gap config:
  │     desc:         "cross-reference EPC database with land registry results"
  │     content_refs: [step:f011]
  │     step_refs:    [step:f010, step:f011]
  │     vocab:        command_needed
  │     relevance:    0.8
  │     confidence:   0.7
  │     grounded:     0.0
  │     post_diff:    true
  │
  └─ step:f013  "merge and store property dataset"
      gap config:
        desc:         "combine land registry + EPC into unified JSON"
        content_refs: [step:f011, step:f012]
        step_refs:    [step:f010, step:f011, step:f012]
        vocab:        content_needed
        relevance:    0.7
        confidence:   0.8
        grounded:     0.0
        post_diff:    false                ← deterministic write

  ── NEW .st: demographics_fetch ──────────────────────────────────
  │
  ├─ step:f020  "resolve ONS API for borough demographics"
  │   gap config:
  │     desc:         "fetch ONS demographics endpoint config"
  │     content_refs: [HEAD]
  │     step_refs:    []
  │     vocab:        hash_resolve_needed
  │     relevance:    1.0
  │     confidence:   0.9
  │     grounded:     0.0
  │     post_diff:    false
  │
  ├─ step:f021  "query population, income, crime data"
  │   gap config:
  │     desc:         "execute ONS queries for borough-level statistics"
  │     content_refs: [step:f020]
  │     step_refs:    [step:f020]
  │     vocab:        command_needed
  │     relevance:    0.9
  │     confidence:   0.8
  │     grounded:     0.0
  │     post_diff:    true
  │
  └─ step:f022  "store demographics dataset"
      gap config:
        desc:         "write demographics JSON to workspace"
        content_refs: [step:f021]
        step_refs:    [step:f020, step:f021]
        vocab:        content_needed
        relevance:    0.8
        confidence:   0.9
        grounded:     0.0
        post_diff:    false
```

After Pass 1, `chain_to_st` extracts three .st files. The leaf chains now exist on the trajectory with known hashes.

---

## Pass 2: reason_needed (build mid-level chains — Layer 1)

The agent's second reason pass builds chains that **embed** the leaf chains by hash.

```
chain:d4e5f6  "mid-level chain construction" (active)
  origin: "leaf chains ready, build aggregation layer"

  ── NEW .st: borough_analysis ────────────────────────────────────
  │  refs: {admin: 72b1d5ffc964, council_scrape: a1b2..., property_lookup: b3c4..., demographics_fetch: c5d6...}
  │
  ├─ step:m001  "load borough context"
  │   gap config:
  │     desc:         "resolve admin identity + borough-specific config"
  │     content_refs: [admin:72b1d5ffc964]    ← EXISTING .st embedding
  │     step_refs:    []
  │     vocab:        hash_resolve_needed
  │     relevance:    1.0
  │     confidence:   0.9
  │     grounded:     0.0
  │     post_diff:    false
  │
  ├─ step:m002  "scrape council data"
  │   gap config:
  │     desc:         "execute council scraping pipeline for this borough"
  │     content_refs: [council_scrape:a1b2...]  ← LAYER 0 .st EMBEDDING
  │     step_refs:    [step:m001]                  compiler disperses council_scrape.st
  │     vocab:        hash_resolve_needed          gaps depth-first: f001→f002→f003
  │     relevance:    0.9                          then returns to m003
  │     confidence:   0.8
  │     grounded:     0.0
  │     post_diff:    false                    ← the .st handles its own branching
  │
  ├─ step:m003  "fetch property data"
  │   gap config:
  │     desc:         "execute property lookup pipeline for this borough"
  │     content_refs: [property_lookup:b3c4...]  ← LAYER 0 .st EMBEDDING
  │     step_refs:    [step:m001, step:m002]
  │     vocab:        hash_resolve_needed
  │     relevance:    0.8
  │     confidence:   0.8
  │     grounded:     0.0
  │     post_diff:    false
  │
  ├─ step:m004  "fetch demographics"
  │   gap config:
  │     desc:         "execute demographics pipeline for this borough"
  │     content_refs: [demographics_fetch:c5d6...]  ← LAYER 0 .st EMBEDDING
  │     step_refs:    [step:m001, step:m002, step:m003]
  │     vocab:        hash_resolve_needed
  │     relevance:    0.7
  │     confidence:   0.8
  │     grounded:     0.0
  │     post_diff:    false
  │
  └─ step:m005  "synthesize borough findings"
      gap config:
        desc:         "combine council + property + demographics into borough analysis"
        content_refs: [step:m002, step:m003, step:m004]
        step_refs:    [step:m001, step:m002, step:m003, step:m004]
        vocab:        content_needed
        relevance:    0.6
        confidence:   0.8
        grounded:     0.0
        post_diff:    true                 ← may surface data quality issues

  ── EXISTING .st embedding: research.st ──────────────────────────
  │  (not a new .st — drawn in as embedding for validation step)
  │
  ── NEW .st: data_validation ─────────────────────────────────────
  │
  ├─ step:m010  "load all borough analyses"
  │   gap config:
  │     desc:         "resolve all completed borough analysis outputs"
  │     content_refs: [borough_analysis:e7f8...]  ← LAYER 1 self-reference
  │     step_refs:    []
  │     vocab:        hash_resolve_needed
  │     relevance:    1.0
  │     confidence:   0.9
  │     grounded:     0.0
  │     post_diff:    false
  │
  ├─ step:m011  "cross-validate data sources"
  │   gap config:
  │     desc:         "verify consistency across boroughs — detect outliers"
  │     content_refs: [research:a72c3c4dec0c]  ← EXISTING .st embedding
  │     step_refs:    [step:m010]                  research.st disperses its 5
  │     vocab:        hash_resolve_needed          steps for verification methodology
  │     relevance:    0.9
  │     confidence:   0.7
  │     grounded:     0.0
  │     post_diff:    true                     ← research may surface issues
  │
  └─ step:m012  "flag and correct anomalies"
      gap config:
        desc:         "patch any data inconsistencies found in validation"
        content_refs: [step:m011]
        step_refs:    [step:m010, step:m011]
        vocab:        hash_edit_needed
        relevance:    0.8
        confidence:   0.7
        grounded:     0.0
        post_diff:    true                     ← corrections may cascade
```

---

## Pass 3: reason_needed (build orchestration — Layer 2)

The top-level chain embeds the mid-level chains, triggers background work, and sets await checkpoints.

```
chain:g9h0i1  "orchestration chain construction" (active)
  origin: "mid-level chains ready, build top-level pipeline"

  ── NEW .st: london_research ─────────────────────────────────────
  │  refs: {admin: 72b1d5ffc964, borough_analysis: e7f8..., data_validation: j2k3..., cors_ui: 58bda1f3fe63}
  │
  ├─ step:t001  "load project context and identity"
  │   gap config:
  │     desc:         "resolve admin identity + project workspace state"
  │     content_refs: [admin:72b1d5ffc964, HEAD]
  │     step_refs:    []
  │     vocab:        hash_resolve_needed
  │     relevance:    1.0
  │     confidence:   0.9
  │     grounded:     0.0
  │     post_diff:    false
  │
  ├─ step:t002  "trigger borough analysis (background)"
  │   gap config:
  │     desc:         "launch borough_analysis as background workflow for all 33 boroughs"
  │     content_refs: [borough_analysis:e7f8...]  ← LAYER 1 .st EMBEDDING
  │     step_refs:    [step:t001]                    triggers as background via reprogramme
  │     vocab:        reprogramme_needed              fire-and-forget, no post_diff
  │     relevance:    0.9
  │     confidence:   0.8
  │     grounded:     0.0
  │     post_diff:    false                       ← PERSIST codon, no branching
  │
  ├─ step:t003  "AWAIT borough analysis results"        ← PAUSE CODON
  │   gap config:
  │     desc:         "checkpoint: wait for borough analysis sub-agent to complete"
  │     content_refs: [borough_analysis:e7f8...]
  │     step_refs:    [step:t001, step:t002]
  │     vocab:        await_needed                    ← manual checkpoint
  │     relevance:    0.85
  │     confidence:   0.9
  │     grounded:     0.0
  │     post_diff:    true                            ← inspect sub-agent tree
  │         await.st disperses:
  │           suspend_and_wait → render_subagent_tree → inspect_and_route
  │           if sub-agent done: semantic tree injection → accept/correct/reactivate
  │           if still running: persist as dangling → heartbeat next turn
  │
  ├─ step:t004  "validate aggregated data"
  │   gap config:
  │     desc:         "run data validation pipeline on all borough results"
  │     content_refs: [data_validation:j2k3...]   ← LAYER 1 .st EMBEDDING
  │     step_refs:    [step:t001, step:t003]        data_validation.st disperses:
  │     vocab:        hash_resolve_needed             m010→m011(+research.st)→m012
  │     relevance:    0.8
  │     confidence:   0.8
  │     grounded:     0.0
  │     post_diff:    false
  │
  ├─ step:t005  "compile comparative report"
  │   gap config:
  │     desc:         "generate markdown report comparing all 33 boroughs"
  │     content_refs: [step:t003, step:t004]      ← refs validation + analysis outputs
  │     step_refs:    [step:t001, step:t003, step:t004]
  │     vocab:        content_needed
  │     relevance:    0.7
  │     confidence:   0.8
  │     grounded:     0.0
  │     post_diff:    true                         ← report quality check
  │
  └─ step:t006  "build dashboard via stitch"
      gap config:
        desc:         "generate interactive HTML dashboard from report data"
        content_refs: [cors_ui:58bda1f3fe63, step:t005]  ← EXISTING .st embedding
        step_refs:    [step:t001, step:t005]
        vocab:        stitch_needed
        relevance:    0.6
        confidence:   0.8
        grounded:     0.0
        post_diff:    true                         ← screenshot verification
```

---

## How the compiler sees it (flattened ledger)

When `london_research.st` fires, the compiler sees a flat stream of gaps. Embeddings disperse depth-first:

```
Ledger (top → bottom, popped from top):

→ t001  hash_resolve_needed  d=0  pri=20   "load project context"
  t002  reprogramme_needed   d=0  pri=99   "trigger borough analysis"
  t003  await_needed         d=0  pri=95   "checkpoint: wait for sub-agent"
  t004  hash_resolve_needed  d=0  pri=20   "validate aggregated data"
  t005  content_needed       d=0  pri=40   "compile report"
  t006  stitch_needed        d=0  pri=40   "build dashboard"
```

After priority sort: `t001(20) → t004(20) → t005(40) → t006(40) → t003(95) → t002(99)`

But wait — t004 embeds `data_validation.st` which embeds `research.st`. When t004 resolves, its child gaps push on top:

```
→ m010  hash_resolve_needed  d=1  pri=20   "load all borough analyses"
  m011  hash_resolve_needed  d=1  pri=20   "cross-validate" (embeds research.st)
  m012  hash_edit_needed     d=1  pri=40   "flag anomalies"
  ... (remaining origin gaps below)
```

When m011 resolves and research.st disperses, THOSE gaps push on top too:

```
→ decompose     hash_resolve_needed  d=2  pri=20
  search        research_needed      d=2  pri=40
  verify_sources (null vocab)        d=2  pri=50
  extract       (null vocab)         d=2  pri=50
  store         content_needed       d=2  pri=40
  m012  hash_edit_needed             d=1  pri=40
  ... (remaining)
```

**Depth-first, LIFO.** The deepest embedded chain resolves completely before the parent resumes. The compiler doesn't know about layers — it just pops the stack.

---

## Deterministic extraction via `chain_to_st`

After the commitment chain resolves, the agent calls `chain_to_st` on each layer. Here's how the extraction maps every gap axis:

### Input: resolved chain on trajectory

```python
chain_data = {
    "hash": "a1b2c3...",
    "origin_gap": "complex task decomposition",
    "desc": "council scraping pipeline",
    "resolved_steps": [
        {
            "hash": "f001",
            "desc": "resolve target council website",
            "content_refs": ["HEAD"],
            "step_refs": [],
            "gaps": [{
                "hash": "...",
                "desc": "fetch council planning portal URL",
                "vocab": "hash_resolve_needed",
                "scores": {"relevance": 1.0, "confidence": 0.9, "grounded": 0.3},
                "content_refs": ["HEAD"],
                "step_refs": ["f001"]
            }],
            "commit": null,
            "t": 1711892036.5
        }
    ]
}
```

### Extraction mapping (every axis preserved)

```
Chain step field          →  .st step field         →  Round-trip guarantee
─────────────────────────────────────────────────────────────────────────────
step.desc                 →  st_step.desc           ✓  verbatim
gap.vocab                 →  st_step.vocab          ✓  verbatim (or null)
gap.scores.relevance      →  st_step.relevance      ✓  float, rounded to 0.01
gap.content_refs          →  st_step.content_refs   ✓  hash list preserved
gap.step_refs             →  st_step.step_refs      ✓  hash list preserved
branching structure       →  st_step.post_diff      ✓  inferred: children exist = true
step.desc → snake_case    →  st_step.action         ✓  derived: first 4 words
```

### Output: extracted .st file

```json
{
  "name": "council_scrape",
  "desc": "council scraping pipeline",
  "trigger": "manual",
  "author": "chain_extract",
  "source_chain": "a1b2c3...",
  "steps": [
    {
      "action": "resolve_target_council_website",
      "desc": "resolve target council website",
      "vocab": "hash_resolve_needed",
      "relevance": 1.0,
      "post_diff": false,
      "content_refs": ["HEAD"]
    },
    {
      "action": "scrape_council_data_via",
      "desc": "scrape council data via command",
      "vocab": "command_needed",
      "relevance": 0.9,
      "post_diff": true,
      "content_refs": ["f001"]
    },
    {
      "action": "verify_scraped_data_integrity",
      "desc": "verify scraped data integrity",
      "vocab": "hash_resolve_needed",
      "relevance": 0.8,
      "post_diff": false,
      "content_refs": ["f002"]
    }
  ]
}
```

### The round-trip

```
reason_needed (pass 1)
  → agent writes chain as semantic tree with full gap config
  → chain plays out on ledger (execution validates the design)
  → chain resolves successfully

chain_to_st(chain_hash="a1b2c3", name="council_scrape")
  → load_chain_data: reads trajectory + chains index
  → extract_st_steps: maps each step's gap config to .st schema
    ├─ desc → action (snake_case) + desc (verbatim)
    ├─ gap.vocab → vocab
    ├─ gap.scores.relevance → relevance (or position-derived 1.0→0.9→0.8)
    ├─ gap.content_refs → content_refs (embedding hashes preserved)
    ├─ branching detection → post_diff
    └─ gap.step_refs → (available but not in .st schema — causal chain is runtime-only)
  → writes skills/council_scrape.st

Future invocation:
  → loader.py reads council_scrape.st → SkillRegistry
  → LLM references council_scrape:hash in content_refs
  → kernel resolves → gaps disperse onto ledger
  → SAME execution shape as the original chain
```

---

## Configuration coverage matrix

Every possible gap configuration the system can express:

| Configuration | Example in tree | Where it appears |
|--------------|----------------|------------------|
| **Observe, deterministic** | `f001` — hash_resolve, post_diff=false | Leaf data fetch |
| **Observe, flexible** | `m011` — research.st embedding, post_diff=true | Validation with branching |
| **Mutate, deterministic** | `f013` — content_needed, post_diff=false | Write result, no review |
| **Mutate, flexible** | `f002` — command_needed, post_diff=true | Scraper may fail |
| **Existing .st embedding** | `m002` — content_refs=[council_scrape:hash] | Leaf chain reuse |
| **New .st inline** | `f001-f003` as council_scrape | Written during reason pass |
| **Nested .st embedding** | `m011` embeds research.st at depth 2 | Validation uses research |
| **Background trigger** | `t002` — reprogramme_needed, post_diff=false | Fire-and-forget launch |
| **Await checkpoint** | `t003` — await_needed, post_diff=true | Sync barrier |
| **Entity ref (soft nudge)** | `t001` — content_refs=[admin:hash] | Identity context |
| **UI generation** | `t006` — stitch_needed, refs cors_ui | Dashboard via Stitch |
| **Cross-layer embedding** | `t004` embeds data_validation which embeds research | 3 layers deep |
| **Null vocab (flex)** | research.st step 3 — verify_sources | LLM reasons freely |
| **High relevance (critical)** | Every step 1 at 1.0 | Fires first in chain |
| **Low relevance (last)** | `t006` at 0.6 | Fires after all else |
| **Confidence gating** | `f011` at 0.7 — API uncertain | Governor may hold for more evidence |
| **Empty step_refs** | `f020` — first step, no causal ancestor | Origin step |
| **Rich step_refs** | `m005` — refs 4 prior steps | Full causal chain |

Every axis of the 7-axis gap configuration appears in this tree. Every extraction maps cleanly to .st schema. The round-trip loses nothing except runtime-only metadata (timestamps, grounded scores, chain_id) which are recomputed when the .st is re-instantiated.
