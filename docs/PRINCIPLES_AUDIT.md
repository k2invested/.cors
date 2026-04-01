# Principles Audit

This file audits `docs/PRINCIPLES.md` against the current source code. `PRINCIPLES.md` remains the design source of truth. The purpose of this audit is narrower:

- check whether each principle's listed mechanism really exists
- check whether the mechanism actually validates the principle's claim
- check whether important supporting functions are missing from the recorded surface

Status terms:

- `validated` means the mechanism is materially implemented as described
- `partial` means the principle is directionally right but the listed mechanism overstates or omits key runtime behavior
- `drift` means the current mechanism does not yet justify the claim as written

## Section Status

| Principle | Status | Notes |
|---|---|---|
| `§1 The Step Primitive` | `validated` | Core runtime objects and hash layering are real and correctly anchored in `step.py`. |
| `§2 Gap Emission and Manifestation` | `partial` | Emission, admission, dormancy, and passive chains exist, but cross-turn readmission does not preserve original chain placement metadata the way the text claims. |
| `§3 Vocab Determines Manifestation` | `partial` | Runtime vocab sets and policy routing are real, but generic `.st` resolution is context rendering, not generic workflow dispersal, and the deterministic branch still uses the LLM after resolution. |
| `§4 The Formal Gap Configuration` | `partial` | Thresholds and grounding rules are correct, but `CONFIDENCE_THRESHOLD` is documented as active resolution law even though it is not actually used to resolve gaps. |
| `§5 Reprogramme` | `partial` | The persistence path is real, but the described `.st` manifestation model is richer than the loader/runtime currently execute. |
| `§6 Standardised Definitions and Referred Context` | `validated` | Hash citation, referred context, and kernel-computed grounding are materially aligned. |
| `§7 Post-Diff` | `drift` | `post_diff` is present in `.st` files and loaded into `SkillStep`, but the kernel does not currently use it as the execution control law described here. |
| `§8 Compiler Laws and Recursive Fluidity` | `partial` | LIFO, depth-first, OMO, admission, force-close, postcondition, and heartbeat mostly exist; same-priority relevance ordering, score immutability, and generic `.st` embedding do not. |
| `§9 Step Blobs, Chains, and Reasoning Steps` | `validated` | Chains, extraction, lifecycle states, and trajectory storage are accurately represented. |
| `§10 Step Chain Activation` | `partial` | Codons, heartbeat, and passive chains exist, but the planning/extraction story is stronger in the principle text than in the runtime. |
| `§11 Temporal Signatures` | `validated` | Timestamp creation and absolute rendering are accurately implemented. |
| `§12 Supporting Infrastructure` | `partial` | Most lifecycle and resolver plumbing exists, but the `REVERT` description is stronger than the current code. |
| `§13 Step Chain Curation` | `partial` | Curation intent is present in prompts, but the efficiency and relevance-ordering claims are not enforced mechanically. |

## Main Misalignments

### 1. `post_diff` is not the active kernel-side control law yet

`PRINCIPLES.md` describes `post_diff` as the fluidity dial that determines whether execution becomes deterministic or branches back into reasoning. The code does not currently do that generically.

What exists:

- `.st` files store `post_diff`
- `skills/loader.py` preserves `post_diff` on `SkillStep`
- prompts discuss `post_diff`

What is missing:

- `loop.py` does not branch on `SkillStep.post_diff` when dispersing loaded `.st` steps
- codon activation in `loop.py` converts `.st` steps into gaps, but the subsequent execution path is driven by vocab handling, not by `post_diff`
- generic skill execution does not use `post_diff` to decide whether to skip an LLM pass

This is the clearest principle-to-runtime drift in the repo.

### 2. Same-priority relevance ordering is claimed, but not implemented

`PRINCIPLES.md` claims that within the same priority bracket, higher relevance pops first. The compiler does not currently sort that way.

What exists:

- `vocab_priority()` assigns priority by vocab family
- `Ledger.sort_by_priority()` sorts origin gaps by priority only

What is missing:

- no same-priority relevance tiebreak
- no ledger sort on `gap.scores.relevance`

This also weakens later claims that `.st` authors can sequence execution by descending relevance.

### 3. `.st` relevance values are largely not live runtime inputs

Several sections assume `.st` steps carry executable `relevance` that affects runtime behavior. The current loader drops it.

What exists:

- many `.st` files contain `relevance`
- prompts instruct the model to write `relevance`
- `loop.py` tries to read `st_step.__dict__.get("relevance", 0.8)` when expanding codons

What actually happens:

- `SkillStep` has no `relevance` field
- `skills/loader.py` does not preserve `relevance`
- codon child gaps therefore fall back to the default value rather than the file’s authored value

So the principle is right as a design target, but the current mechanism does not validate it.

### 4. Generic `.st` workflow embedding is not implemented the way the principles describe

The principles repeatedly describe a model where existing `.st` files can be embedded by hash and their gaps disperse depth-first when resolved. That is not generally how the runtime works today.

What exists:

- `resolve_hash()` checks the skill registry first
- when a skill hash resolves, the loop renders the `.st` data as entity context via `_render_entity()`
- specific codons and `/command` flows manually expand known `.st` files into gaps

What is missing:

- no generic mechanism that takes an arbitrary skill hash in `content_refs` and disperses its `steps[]` onto the ledger
- no generic “workflow `.st` resolution becomes gap mutation” runtime path

So `.st` resolution is currently generic for context injection, but not generic for workflow activation.

### 5. `chain_to_st` is deterministic in shape, but not lossless

The principles describe deterministic extraction of semantic trees into `.st` files and say that nothing is lost in the round-trip. The current implementation is more limited.

What exists:

- `tools/chain_to_st.py` loads chains and extracts `.st`-compatible steps without using an LLM

What it still does heuristically:

- derives actions from descriptions
- infers `post_diff` from child-gap/commit shape
- derives relevance from gap scores or fallback position

This is deterministic, but not fully faithful to all authored planning semantics.

### 6. Cross-turn readmission is real, but its mechanism is overstated

`Compiler.readmit_cross_turn()` exists and does re-score dangling gaps against the higher threshold. But the principle text says it preserves original chain metadata. It does not.

Current behavior:

- a new chain is created from the dangling gap and current step hash
- the gap is reinserted as a new origin

So the principle should describe re-admission and re-scoring, not preservation of prior chain placement metadata.

### 7. `CONFIDENCE_THRESHOLD` is recorded as active law, but is not actually used for resolution

The constant exists in `compile.py`, but the current code does not resolve gaps by checking `confidence > CONFIDENCE_THRESHOLD`.

Actual resolution mostly happens when:

- no child gaps were emitted
- the loop explicitly calls `compiler.resolve_current_gap()`
- chains are force-closed or completed structurally

The constant belongs in the file map, but the principle text overstates its current runtime role.

### 8. “Scores never modified” is not true for grounded

The principles say scores are set at emission and never modified. That is not strictly true.

What exists:

- relevance and confidence come from the model at emission

What changes:

- grounded is overwritten at admission by `_compute_grounded()`

So if the intended law is “LLM-authored relevance/confidence are immutable,” the text should say that more precisely.

### 9. The supporting infrastructure section overstates `REVERT`

`§12` says `REVERT` means “git revert last commit.” The current `run_turn()` behavior for `GovernorSignal.REVERT` is softer.

Current behavior:

- print divergence warning
- resolve the current gap
- continue

The actual git revert path lives in mutation protection and explicit git tools, not in the governor’s `REVERT` branch.

## Principle-by-Principle Notes

### `§1 The Step Primitive`

This is one of the strongest sections. `Gap`, `Step`, `Epistemic`, `blob_hash()`, and `chain_hash()` are all correctly named and materially aligned.

One nuance: `Step.create()` includes a timestamp in the hash input, so step hashes are event-addressed rather than purely content-addressed. The principle language is still close enough, but that detail matters.

### `§2 Gap Emission and Manifestation`

Emission, admission, dormancy, and passive chain building are real. The only meaningful correction is the readmission story noted above.

### `§3 Vocab Determines Manifestation`

The core vocab tiers are correct, and the tree policy routing is real. The main correction is that `.st` resolution is not a generic dual-mode “inject or disperse” runtime path today. Generic resolution injects entity-style renderings; only special paths disperse steps.

### `§4 The Formal Gap Configuration`

The seven-axis framing is still a useful design description, but not all seven axes are carried as first-class runtime fields everywhere. The threshold logic is accurate; the `CONFIDENCE_THRESHOLD` claim is the main drift.

### `§5 Reprogramme`

The section captures the intent of reprogramme well, and the iteration-branch plus `_reprogramme_pass()` are real. The caution is that the `.st` ecosystem described there is richer than what the loader currently executes as first-class behavior.

### `§6 Standardised Definitions and Referred Context`

This section is mostly accurate. The hash-citation discipline, grounding rules, and resolver order all line up well with the runtime.

One minor recording issue: the `Gap.create()` hash formula in the principle text shortens the actual implementation and omits `step_refs` in one place.

### `§7 Post-Diff`

This is the least validated section. It is conceptually central, but the runtime has not caught up. The current mechanism stores `post_diff` but does not enforce the described kernel-side behavior generically.

### `§8 Compiler Laws and Recursive Fluidity`

The compiler laws section is strong in spirit and mostly real at the ledger/governor level. The main corrections are:

- same-priority relevance ordering is not implemented
- score immutability is overstated
- recursive `.st` embedding is not generic

### `§9 Step Blobs, Chains, and Reasoning Steps`

Accurate and well-backed by `step.py`.

### `§10 Step Chain Activation`

The codon architecture is real. `reason`, `await`, `commit`, and `reprogramme` all exist as `.st` codons and runtime branches. The drift is mostly in the stronger planning claims:

- full 7-axis chain authoring is not runtime-validated
- generic `.st` embedding is not runtime-generic
- extraction is deterministic but not lossless

### `§11 Temporal Signatures`

Accurate.

### `§12 Supporting Infrastructure`

Mostly accurate, but `REVERT` needs correction and `run_command()` is summarized more generally than the actual signature/behavior.

### `§13 Step Chain Curation`

The design intent is clear and good, and the prompts do nudge toward reuse. But efficiency, depth planning, and relevance-based sequencing are not yet enforced by code beyond generic chain depth limits.

## Important Functions Not Fully Recorded

The principles record most major mechanisms, but not every principle-relevant function surface. The most notable omissions are:

`step.py`

- `Step.to_dict()` / `Step.from_dict()`
- `Chain.to_dict()` / `Chain.from_dict()`
- `Trajectory.load()`
- `Trajectory.save()`
- `Trajectory.resolve()` / `Trajectory.resolve_gap()`
- `Trajectory._render_refs()` and `_render_steps_as_tree()`

`compile.py`

- `Compiler.has_unresolved_background()`
- `Compiler.record_background_trigger()`
- `Compiler.record_await()`
- `Compiler.needs_heartbeat()`
- `Compiler.render_ledger()`
- `Compiler.chain_summary()`

`loop.py`

- `_load_tree_policy()`
- `_match_policy()`
- `_check_protected()`
- `resolve_all_refs()`
- `execute_tool()`
- `_extract_json()` / `_extract_command()`
- `_find_identity_skill()`
- `_synthesize()`
- `_save_turn()`
- `run_command()`

`skills/loader.py`

- `SkillRegistry.all_commands()`
- `SkillRegistry.render_for_prompt()`
- `Skill.deterministic_steps()` / `Skill.flexible_steps()`

These are not all principle-defining, but several are principle-supporting and should be recorded if the goal is full mechanism traceability.

## Bottom Line

`PRINCIPLES.md` is directionally strong and still the right design anchor. The biggest issue is not that the principles are wrong. It is that a few sections describe the system you are building toward, while the code is still in an intermediate state.

The most important places where mechanism should be tightened or the principle text should be clarified are:

1. make `post_diff` a real runtime law, or narrow the wording
2. preserve and use `.st` step `relevance`, or stop claiming same-priority relevance sequencing
3. decide whether generic `.st` workflow embedding is truly a runtime feature, then implement or narrow
4. narrow the chain extraction claim from “lossless” to “deterministic but currently heuristic”
5. correct the `REVERT` and cross-turn readmission descriptions
