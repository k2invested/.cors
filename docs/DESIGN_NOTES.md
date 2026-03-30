# v5 Design Notes — Trajectory Control & Persistent Reasoning

## Core Idea: Turn as Unit of Step

The persistent LLM session lives for one turn, not one session. Each turn IS a step at a higher scale.

### Two levels of step() recursion

1. **Within a turn** — tool steps. The LLM accumulates context naturally via persistent conversation history. No context reconstruction needed — it was there for every step.

2. **Across turns** — turn-level steps. When a turn ends, it compacts into a trajectory atom. The next turn loads a chain of these compacted turn-atoms.

### StepKernel (see step_kernel.rs)

```
StepKernel {
    messages: Vec<Message>,       // persistent within the turn
    atoms: Vec<VerificationAtom>, // produced this turn
}
```

- One Sonnet session per turn
- LLM observes events the kernel feeds it, produces VerificationAtoms
- VerificationAtom is the ONLY interface between LLM and kernel
- Kernel routes based on atoms, LLM doesn't decide tool calls

### What this solves

- **Within-turn coherence**: persistent session means the LLM saw everything. No trajectory injection needed during the turn.
- **Cross-turn coherence**: compacted turn-atoms persist across turns. The next turn starts with the prior reasoning chain — what was the goal, what was observed, what was decided, what's unfinished.
- **Trajectory noise**: the trajectory is a list of turns (compacted), not a list of every tool call and full file dump.

### Open questions

- What does the compacted turn-atom look like? What's the minimal representation that preserves reasoning continuity?
- How many prior turn-atoms can be injected before context limits hit?
- Does the compaction happen in Rust (deterministic) or via LLM (semantic)?

### Tradeoff

One long Sonnet session per turn is more expensive per token than multi-model nano/mini calls. But it eliminates context reconstruction overhead and information loss between steps.

---

## The Diff/Step Distinction

Two layers, not one:

- **Diff** = what changed. Data. Compressible. Reconstructable. The measurable trace of a state transition. This is what Git stores.
- **Step** = how and why it changed. Semantics. The observation + interpretation + decision that produced the diff. This is what the system uniquely preserves.

The system stores BOTH. Diffs for compression and reconstruction (O(change) storage, replay, compose). Steps for reasoning continuity (why was this done, what was the agent thinking).

### Observation is a diff

When the LLM observes a tool result, internal state changes even if no external action happens. Every atom IS a diff — the LLM's presence transforms the state just by perceiving it. Passive reading does not exist in this system; perception is mutation.

### The architecture (from Git analogy)

Git: state + diff (reconstructable history, no semantics)
This system: state + diff + step (reconstructable history WITH semantics)

```
state₀ → step₁ (observe + interpret + mutate) → state₁ → step₂ → state₂ → ...
         diff₁ = state₁ - state₀                        diff₂ = state₂ - state₁
```

Diffs chain. Steps compose. A turn = compose(all step-atoms) → one turn-atom with net diff + compressed semantics.

### Compression model (three tiers)

1. **Delta compression** — store only what changed per step (step.rs Diff struct)
2. **Composition compression** — compose N child diffs into one net diff per turn
3. **Semantic compression** (future) — domain-specific: merge consecutive edits to same key, drop superseded observations, keep only epistemic high-water marks

---

## Associative Recall via Semantic Steps

The LLM doesn't remember. It gets reminded. The quality of recall depends on the quality of the original step descriptions.

### The loop

1. LLM produces semantically rich atom (clear assessment, specific gaps, honest scores)
2. Kernel stores it (content-addressed by hash, indexed by semantic fields)
3. Next turn: user input triggers LLM's initial observation
4. Kernel matches current observation against stored atoms — surfaces relevant history
5. LLM reads surfaced history → naturally connects past to present

### Two concerns, clean boundary

- **LLM's job**: describe well (produce rich assessments, specific gaps)
- **Kernel's job**: recall well (surface relevant history when current context matches)

### Storage model (dual view)

```
turn_atom:
  id:         hash(diff + assessment + t)     // kernel: addressing, dedup, integrity
  diff:       { added: {...}, changed: {...} } // kernel: reconstruction
  assessment: "researched X, found Y"          // LLM: semantic reasoning
  gaps:       "Z unresolved"                   // LLM: continuity
```

Kernel sees hashes. LLM sees meaning. Same data, two views.

### Analogy

Like human memory — present experience evokes subconscious recall of related past states. The deterministic system plays the role of the subconscious: surfacing what's relevant based on semantic similarity between now and then.

### Recall is a step, not a side effect

When the kernel surfaces historical atom IDs, that IS a state transition. The current step's diff records the recall:

```
diff: {
  added: { "_recalled": ["turn_2_hash", "turn_3_hash"] }
}
```

State before: no recalled references. State after: references present. The LLM observes them as part of its context → its next emission is informed by them.

This means:
- Recall uses the same primitive as everything else (step/diff)
- No special recall mechanism needed — it's just an internal & observation
- If the LLM updates something based on recall, that's internal &mut — still a step
- The composed turn-atom captures which history was surfaced: "turn 5 recalled turns 2 and 3"
- Future turns can see the recall chain — the reasoning trace includes its own memory access patterns

---

## v5 Atom: Minimal Universal Primitive

### The 7-field atom

```
atom = {
  pre:        hash(forward_diff),     // the gap — what's needed
  post:       hash(backward_diff),    // the result — what changed
  content:    "semantic description", // LLM: reasoning, recall, continuity
  t:          1711612800.0,           // kernel: ordering, recency
  relevance:  0.9,                    // kernel: filtering threshold
  confidence: 0.8,                    // kernel: trust gating
  grounded:   0.95,                   // kernel: grounding gate
}
```

### Two-part hash identity

The atom's identity is pre + post. Two hashes, two directions:

- **pre** = hash of the forward diff (gap). What's missing. What the system intends to resolve.
- **post** = hash of the backward diff (result). What actually changed. The outcome.

### Quadrant enforcement from structure

The &/&mut distinction is no longer metadata — it's derivable from the hash pair:

| State | pre | post | Meaning |
|-------|-----|------|---------|
| Open gap | set | empty | & (observe) — saw something missing, hasn't acted |
| Resolved step | set | set, differs from pre | &mut (mutate) — gap resolved, result recorded |
| Pure observation | set | set, equals pre | & (no mutation) — observed, nothing changed |

No borrow/ownership tags needed. The structure tells you.

### Gap and diff unify

A gap is a forward diff. A result is a backward diff. Same primitive, different temporal direction:

- **Forward diff (gap)**: state_current → state_desired (what's missing)
- **Backward diff (result)**: state_before → state_after (what changed)

Lifecycle:
```
gap created  → pre hash set, post empty     (forward diff: what's needed)
step executes → kernel resolves the gap
step recorded → post hash set                (backward diff: what happened)
```

A gap is a diff that hasn't been applied yet. When resolved, it gains a post hash.

### Cross-atom relationships from hash equality

- Same **pre** across atoms = same gap attempted multiple times (retries, reclassify)
- Same **post** across atoms = same result produced (dedup, convergence)
- Atom A's **post** = Atom B's **pre** = A's output is B's input (causal chain)
- **pre → post** mapping = reusable knowledge ("this is how this gap gets resolved")

### Consumer split

| Field | Consumer | Purpose |
|-------|----------|---------|
| pre | kernel | gap identity, dedup, causal linking, tree membership |
| post | kernel | result identity, dedup, resolution tracking |
| content | LLM | semantic reasoning, recall, continuity |
| t | kernel | ordering, recency weighting, decay |
| relevance | kernel | filtering — which atoms to surface |
| confidence | kernel | trust gating — whether to rely on a recalled atom |
| grounded | kernel | grounding gate — is this anchored in evidence |

---

## Refined v5 Atom (final shape)

### Struct

```rust
struct PreDiff {
    refs:       Vec<Hash>,      // hashes surfaced from perception/recall
    relevance:  f64,            // how relevant is what we observed
    confidence: f64,            // how sure are we about the observation
    grounded:   f64,            // is this anchored in evidence
}

struct PostDiff {
    gaps:       Vec<Gap>,       // gaps driving compiler decisions
    relevance:  f64,            // how relevant are these gaps
    confidence: f64,            // how sure are we about what needs doing
    grounded:   f64,            // is the action plan anchored in evidence
}

struct Atom {
    pre:     PreDiff,           // perception — what was observed/recalled
    post:    Option<PostDiff>,  // intention — what needs to happen. None = pure observation.
    content: String,            // semantic description for LLM
    t:       f64,               // timestamp
}
```

### Pre = perception, Post = intention

- **pre.refs**: hashes of atoms surfaced by structural recall. What the system perceived.
- **pre.epistemic**: quality of that perception. Was the observation relevant, confident, grounded?
- **post.gaps**: gaps that map onto actions. What needs to happen next. Drives the compiler.
- **post.epistemic**: quality of the intention. Is the action plan relevant, confident, grounded?
- **post = None**: pure observation. No action needed. The step only perceived.

### Dual epistemic scores enable compound routing

| Pre confidence | Post confidence | Kernel action |
|---------------|----------------|---------------|
| high | high | Clear observation, clear action → execute |
| high | low | Saw clearly, unsure what to do → need analysis |
| low | high | Shaky evidence, clear plan → need better observation first |
| low | low | Uncertain all around → surface more context |

### Verification splits naturally

- **Verify-pre**: was the observation grounded? Are the recalled refs relevant?
- **Verify-post**: is the gap assessment sound? Does the action plan follow from the evidence?

Two measurements, not one. The kernel can gate independently on each.

### Gap is no longer a separate concept

A gap is an atom where post is Some (gaps exist) but those gaps haven't been resolved yet. Resolution = a new atom whose pre.refs includes the gap's hash, with post showing the outcome.

### Atom lifecycle

```
1. Perception  → Atom { pre: { refs: [surfaced hashes] }, post: None }
2. Assessment  → Atom { pre: { refs: [...] }, post: Some({ gaps: [...] }) }
3. Execution   → new Atom whose pre.refs includes step 2's hash
4. Resolution  → post.gaps from step 2 are matched by step 3's results
5. Composition → compose(atoms 1-4) → single turn-atom with net pre/post
```

### Atom states (from hash structure)

| pre.refs | post | Meaning |
|----------|------|---------|
| populated | None | Pure observation — perceived, no action needed |
| populated | Some(gaps) | Assessment — observed and identified what's needed |
| populated | Some(empty gaps) | Verified — checked, everything resolved |

---

## Step as Vector

A step is a vector in epistemic space. Pre = origin, Post = destination.

```
step_vector = [pre.relevance, pre.confidence, pre.grounded, post.relevance, post.confidence, post.grounded]
```

### Vector operations as kernel judgments

| Operation | Meaning |
|-----------|---------|
| `post - pre` | Direction of change — what this step accomplishes |
| `magnitude(post - pre)` | Size of transition — how much change |
| `dot(step_a, step_b)` | Alignment — are two steps working toward the same goal |
| `step_a + step_b` | Composition — net movement of two steps combined |
| `distance(current, goal)` | How far from done |
| `cosine(step, goal_vector)` | Is this step converging or diverging |

### Deterministic diagnostics from vector math

- **Stagnation**: step vectors with near-zero magnitude (not moving)
- **Divergence**: step vectors pointing away from goal (getting worse)
- **Convergence**: step vectors aligned with goal direction (on track)
- **Oscillation**: step vectors alternating direction (stuck in a loop)

All deterministic. All from the numbers. No LLM needed for these judgments.

---

## Compiler Goal: Confidence Convergence

The goal is not categorically defined. It is universal:

```
goal = for all atoms: post.gaps.confidence >= threshold
```

The compiler finds the path of steps that raises every gap's confidence above threshold. A gap isn't "resolved" by type or scope — it's resolved when the system is confident enough in the outcome.

- Simple question → low confidence needed → resolves fast
- File write → higher confidence needed → more observation first
- Risky action → very high confidence → extensive verification

The ceiling from v4.5 emerges naturally from the confidence landscape. High-confidence observations widen what actions the compiler attempts. Low confidence constrains. Continuous, not discrete levels.

```
compiler loop:
  1. find atoms where post.gaps.confidence < threshold
  2. select step that maximally raises confidence on the weakest gap
  3. execute → new atom with updated scores
  4. repeat until all gaps above threshold or no progress
  done = all post.gaps.confidence >= threshold
```

---

## Git as Semantic Environment

The AI's state lives in a Git repository. Git primitives map directly to kernel concepts.

### Why Git works here

| Kernel concept | Git primitive |
|---------------|--------------|
| Current state | Working tree |
| Step mutation | Commit |
| Trajectory | Git log |
| Step diff | Commit diff |
| Atom hash | Commit SHA |
| Parallel tasks | Branches |
| Merging results | Git merge |
| Cross-turn persistence | History |
| Dedup | Content-addressed blobs |
| Integrity | Hash verification |
| Causal chain | Parent commit chain |

### Commit-per-mutation-step

Only mutation steps produce commits. Observations are ephemeral (live in the persistent LLM session only).

```
observation (post = None)      → no commit
mutation (post != pre)         → git commit → SHA becomes atom's post hash
verification (post == pre)     → no commit
```

Scalability: ~5-15 commits per turn, ~150-450/day at active use, ~55-165K/year. Git handles millions.

### Commit SHA as structural identifier

A mutation step is identifiable by containing a commit hash in post. The presence of a SHA IS the proof of mutation. No metadata flag needed.

```
Step 1: observe  → pre: [],            post: None
Step 2: mutate   → pre: [],            post: Some("a3f8b2c")
Step 3: observe  → pre: ["a3f8b2c"],   post: None
Step 4: mutate   → pre: ["a3f8b2c"],   post: Some("d4e5f6a")
```

The &/&mut distinction from v4.5 is now: `post.is_some()`. Derived from structure.

### Quadrant emerges from execution

```
precondition vocab → tool → executes → state changed?
                                         ├─ yes → git commit → post = Some(sha)  (&mut)
                                         └─ no  → no commit  → post = None       (&)
```

| v4.5 Quadrant | Examples | Produces commit? |
|---------------|----------|-----------------|
| External & (observe) | scan, pattern, domain, url | No |
| Internal & (recall) | self_recall, recall_needed | No |
| External &mut (produce) | content_needed, command_needed, message_needed | Yes |
| Internal &mut (update) | commitment_needed, profile_needed | Yes |

No upfront classification needed. The quadrant is discovered after execution.

---

## Causal Lineage via Gap Origin

Every mutation traces back to the gap that drove it, the observation that produced that gap, and the commit that preceded it.

```
Step 1: observe input     → gap: "need to scan config"        (no commit)
Step 2: scan config       → gap: "config has wrong value"     (no commit)
Step 3: write fix         → commit a3f8b2c                    (mutation)
```

The atom carries its lineage:

```
Atom {
  pre: {
    refs: ["a3f8b2c"],
    origin_gap: hash(gap),       // the gap that drove this step
    origin_step: step_2_id,      // which step produced that gap
  },
  post: Some("d4e5f6a"),
  content: "fixed config value",
}
```

### Queryable causal graph

| Question | How |
|----------|-----|
| Why did this commit happen? | Follow origin_gap → find the step that created it |
| What did this observation lead to? | Find all atoms whose origin_step points here |
| Full causal chain? | Walk origin_step links backward |
| Observations that never led to mutations? | Steps with no downstream commits |
| Which gaps produced the most mutations? | Count commits per origin_gap |

The trajectory is not just a sequence — it's a directed graph of causation. Structural, deterministic, from hashes.

---

## Salience-Gated Recall

Not everything perceived is worth surfacing. Pre.refs needs filtering.

### Salience function

```
salience(stored_atom, current_context) = f(
    stored_atom.relevance,                               // original relevance
    stored_atom.confidence,                              // original confidence
    recency(stored_atom.t, now),                         // time decay
    semantic_match(stored_atom.content, current_input),  // topic overlap
    causal_proximity(stored_atom, active_gaps),           // connection to open gaps
)
```

### Computation cost tiers

| Method | Cost | Deterministic? |
|--------|------|---------------|
| Keyword overlap | Cheapest | Yes |
| Embedding similarity | Cheap | Near-deterministic |
| 5.4-mini judgment | Expensive | No — last resort |

### Surfacing pipeline

```
1. all stored atoms
2. filter: recency decay (drop old / low relevance)
3. rank: salience score against current input
4. top-K → pre.refs
5. LLM sees only the salient subset
```

Salience filtering IS a step — it observes the current input, scans the store, and produces a pre diff containing only what's worth recalling. Same primitive, applied to recall selection.

### Priority tiers (structural before semantic)

Short/ambiguous inputs like "yes" have zero semantic content — keyword and embedding matching fail. Salience needs structural rules that fire before semantic matching:

```
salience priority:
  1. open gaps from prior turn          (structural — always surface)
  2. most recent turn atom              (recency — always surface)
  3. semantic match on input content     (only useful for rich inputs)
  4. causal proximity to active gaps     (graph traversal)
```

- "yes" → tiers 1+2 fire. LLM gets prior turn's context and open gaps. Understands reference.
- "revisit the trajectory compression" → tier 3 fires, surfaces older atoms by topic.
- "continue what you were doing" → tiers 1+2 fire, open gaps from prior turn resume.

Structural surfacing (tiers 1-2) guarantees conversational coherence. Semantic surfacing (tiers 3-4) enables long-range recall. Both are deterministic.

---

## Pre-Diff Mechanism: Full Steps with Embedded Hashes

### What the LLM sees

Surfaced steps are injected in full, with hashes inline. The LLM reads content for meaning and hash co-occurrence for structure.

```
Surfaced context:

Step [a3f8b2c]: researched trajectory persistence, found compose() enables compression
  pre: [d1e2f3a, b4c5d6e]
  post: [gap: "assessment field at composition time"]

Step [f7g8h9i]: user confirmed cross-turn coherence goal
  pre: [a3f8b2c, d1e2f3a]
  post: [gap: "design compaction format"]

Step [k2l3m4n]: designed salience-gated recall
  pre: [a3f8b2c, f7g8h9i]
  post: []
```

### Hash co-occurrence as implicit knowledge graph

- `a3f8b2c` appears in three steps → central node, high connectivity
- `d1e2f3a` appears in two steps → shared context
- `f7g8h9i` feeds into `k2l3m4n` → causal chain visible

The LLM doesn't decode hashes. It tracks patterns:
- "this hash keeps appearing → whatever it represents is important"
- Content tells it WHAT. Hash patterns tell it HOW things connect.

No explicit knowledge graph needed. The graph IS the hash co-occurrence across surfaced steps. The LLM discovers the topology by reading.

### Recent hash exploration trail

Like git commits visible in the v4.5 render, the system maintains a "most recent hashes explored" list — the last N hashes the LLM decided to explore fully down the causal chain.

```
Recent exploration trail:
  [a3f8b2c] → [d1e2f3a] → [b4c5d6e]    (explored 2 steps ago)
  [f7g8h9i] → [a3f8b2c]                  (explored last step)
```

This gives the LLM:
- **Working memory**: which threads it has already pulled on
- **Exploration state**: where it stopped, what it hasn't followed yet
- **Continuity**: if interrupted or across turns, it sees where it left off
- **Depth control**: the kernel can limit how deep the LLM follows a causal chain (max N hops)

The trail is part of the render — always visible, updated after each step. The LLM can choose to follow an unexplored branch or continue deepening a thread it already started.

---

## Pre-Diff as Exploration System (not search)

### The shift: keyword search → navigation through transition state space

Search asks "what matches this query?" — flat, disconnected results.
Navigation asks "where does this lead?" — connected, directional traversal.

The LLM doesn't search. It navigates. It follows hashes through the state space like following paths through a landscape. Each hash is a waypoint. Each step is a path between waypoints. The causal chain is the route.

### Trajectory = post-diffs only (the trunk)

The stored trajectory is lean — only post-diffs. Gaps, actions, results. Sequential. Reads like a conversation:

```
[abc123] user asked about trajectory control
  gaps: ["need to understand diff compression"]

[def456] researched diffs, found compose() enables turn-level compression
  gaps: ["assessment field at composition time"]

[789fed] user said "yes"
  gaps: []
```

The LLM reads this naturally. "Yes" makes sense because it follows the flow.

### Roots = on-demand exploration

When the LLM sees a hash in the trajectory and wants to go deeper, it follows it. The kernel resolves the hash, surfaces the full step with its own hashes, which can be followed further. Roots are not preloaded — they're explored when the LLM decides a thread is worth pulling.

### Navigation primitives

From any position (current step), the LLM can:
- **Look at trajectory**: the path taken to get here (post-diffs, sequential)
- **Follow roots downward**: where did this come from? (pre-diff convergence)
- **Follow branches forward**: what did this lead to? (post-diff divergence)
- **Jump to co-occurring hash**: what else connects to this entity? (graph traversal)

### Every step has a pre-commit

Every step commits its observation to get a hash. No holes in the chain. Every link exists. The chain is fully traversable in both directions.

```rust
struct Atom {
    pre:            Hash,               // always exists — every step commits
    post:           Option<Hash>,       // Some = mutation occurred
    content:        String,             // semantic description
    t:              f64,                // timestamp
    pre_epistemic:  Epistemic,          // quality of observation
    post_epistemic: Option<Epistemic>,  // quality of action (if any)
}
```

### Structure: roots, not trees

Pre-diff surfacing is convergent (many sources → one present). Post-diff action is divergent (one action → many consequences). The step sits at the junction:

```
many → one (convergence at perception / pre-diff)
one → many (divergence at action / post-diff)
```

### The trajectory is alive

- **Readable**: semantic content tells the story
- **Navigable**: hashes are doors into deeper context
- **Lean**: only post-diffs stored, roots resolved on demand
- **Alive**: every hash is a potential exploration, the LLM decides which threads to pull

---

## Single Persistent 5.4 Architecture

### One LLM, one session, governor controls

No separate mini. One persistent 5.4 session per turn. The LLM does all semantic work — perception AND assessment in one continuous stream. The governor is the only external control.

```
5.4 (persistent session):
  → reads trajectory + commit
  → emits reasoned intent: "config.json exists [aaa], need to see contents"   (pre-diff)
  → kernel resolves aaa → feeds back into session
  → emits reasoned intent: "model_id is gpt-4o [aaa], user wants claude-sonnet" (pre-diff)
  → governor: perception saturated → ACT
  → emits reasoned intent: python3 -c "..." (command)
  → kernel executes → commits → feeds result back
  → emits reasoned intent: "verified, config updated [bbb]"
  → governor: no gaps → HALT → synth from session content
```

### Reasoned intent (single field, all phases)

The `content` field is "reasoned intent" — grounded in referred content, not gap metadata. It doubles as:

| Phase | Content is | Kernel does |
|-------|-----------|-------------|
| Perception | reasoning + hash refs | resolve hashes, feed back |
| Action | command | verify, execute, commit |
| Synthesis | response to user | deliver |

Comments are grounded in specific referred entities/artifacts/content/context. Never in gap progress or system state:

```
❌ "gap sharper now, confidence high"
✅ "config.json has model_id set to gpt-4o-2024-08-06 [aaa]. User wants claude-sonnet-4-6."
```

### Articulated chains

Each chain link is hash + description — forced articulation. The LLM must describe what it found at each hash. The chain is a narrated exploration:

```
chain A:
  [aaa]: "workspace commit — config.json, main.py, utils.py present"
  [bbb]: "config.json contains model_id set to gpt-4o-2024-08-06"

chain B:
  [aaa]: "workspace commit"
  [ccc]: "main.py has no model references — unrelated to task"

chain C:
  [ddd]: "prior turn's pipeline commit"
  [bbb]: "model_id was set to gpt-4o during this pipeline work"
```

Multiple chains per step — one per line of reasoning. Each chain is a complete causal path through the hash space.

### One gap per articulated chain

The post-diff creates one gap per chain. The gap is an analysis/assessment of the entire chain:

```
gap A: { analysis: "config model_id needs updating to claude-sonnet-4-6",
         chain_id: 0, refs: [aaa, bbb],
         signal: { relevance: 0.95, confidence: 0.9, grounded: 1.0 } }

gap B: { analysis: "main.py is unrelated to model_id change",
         chain_id: 1, refs: [aaa, ccc],
         signal: { relevance: 0.1, confidence: 0.95, grounded: 1.0 } }

gap C: { analysis: "model_id was changed during pipeline work, confirms root cause",
         chain_id: 2, refs: [ddd, bbb],
         signal: { relevance: 0.9, confidence: 0.85, grounded: 1.0 } }
```

Governor sees a vector per gap. Gap B is irrelevant — drops out. Gap C enriches Gap A. Gap A is the action target. Recurring chain patterns across turns become entities (trees).

### The perception loop builds the pre-diff

The loop IS the pre-diff being constructed. Working state is mutable (chains grow, content accumulates in session). When the loop ends, the step is frozen as an immutable blob.

```
loop iterations build chains:
  chain A grows: [aaa] → [aaa, bbb]
  chain B grows: [aaa] → [aaa, ccc]
  chain C grows: [ddd] → [ddd, bbb]
governor: perception saturated (information gain < threshold)

→ Step created (immutable):
    pre:     frozen chains [A, B, C]
    post:    one gap per chain with signals
    content: accumulated reasoned intent
```

Same pattern as Git: mutable working tree → immutable commit.

---

## Governor: Deterministic Linear Algebra

The governor is a deterministic convergence monitor operating on chain structure vectors. Pure linear algebra. No LLM judgment.

### Two-phase governance

**Phase 1 — Perception governance (information gain)**

Each chain link has structural properties — a vector:

```
link_vector = [
    co_occurrence,     // how many other steps reference this hash
    commit_distance,   // hops to nearest commit
    tree_membership,   // how many trees contain this hash
    recency,           // how recent is this hash
]
```

The chain is a matrix (one row per link). The governor computes information gain per iteration:

```
state_vector = mean(all link vectors)
delta        = state_vector - prev_state_vector
gain         = magnitude(delta)
```

When gain drops below threshold → perception saturated → exit loop. The system learned nothing new from the last hash resolution.

```rust
fn govern_perception(chain_matrix: &[Vec<f64>]) -> Signal {
    if chain_matrix.len() < 2 { return Signal::Allow; }

    let prev = mean(&chain_matrix[..chain_matrix.len()-1]);
    let curr = mean(chain_matrix);
    let delta: Vec<f64> = curr.iter().zip(prev.iter()).map(|(c,p)| c - p).collect();
    let gain = delta.iter().map(|d| d * d).sum::<f64>().sqrt();

    if gain < SATURATION_THRESHOLD {
        Signal::Halt  // nothing new learned, exit perception
    } else if chain_matrix.len() > MAX_DEPTH {
        Signal::Constrain
    } else {
        Signal::Allow
    }
}
```

**Phase 2 — Action governance (epistemic vector alignment)**

After perception, post-diff exists. Full vector computation:
- Pre vs post epistemic distance
- Convergence toward confidence threshold
- Divergence / stagnation / oscillation detection

### Governor signals

| Signal | Trigger | Effect |
|--------|---------|--------|
| Allow | information gain above threshold | let 5.4 continue exploring |
| Constrain | chain too deep | cap exploration depth |
| Redirect | stagnation (no movement in N steps) | force different gap |
| Revert | divergence (confidence dropped) | undo last mutation |
| Act | perception saturated, gaps remain | enter action mode |
| Halt | all gaps closed OR pathological | end turn |

### The governor mirrors the LLM

The governor computes attention over epistemic vectors the same way a transformer computes attention over token embeddings. Same pattern, different substrate:

```
LLM:      attention over token embeddings  → semantic output
Governor: attention over epistemic vectors → control signal
```

Step all the way down — the governor is step() operating on numbers.

---

## Refined v5 Architecture: Hash-Native Kernel

### Two hash layers (clean separation)

**Layer 1 — Step hashes**: reasoning trajectory. What the system thought, decided, concluded. Semantic descriptions + epistemic scores + references to other steps. Only reasoning steps reference other reasoning steps.

**Layer 2 — Content hashes**: blobs, trees, commits. What exists in the environment. Actual data, reconstructable from git. Gaps and assessments reference content hashes. The kernel resolves them on demand.

### Atom content is hash data, not raw data

```
v4.5: atom.content = { added: { content: "entire 222KB file dump" } }
v5:   atom.content = { refs: [blob_f1a2b3], desc: "config.json model_id=gpt-4o" }
```

Raw data never touches the trajectory. Only hash references and semantic descriptions. Data is resolvable via `resolve(hash)`. Causal chain is traceable via `trace(hash)`.

### No external contamination

The trajectory is a closed hash graph. Nothing enters without being stepped. Raw data → kernel hashes it → blob → step references the blob hash. Hallucinated hashes don't resolve. Errors are isolated in blobs. The reasoning graph is self-verifying.

### Entities identified by hash, not path

```
v4.5: "read config.json"        → file path
v5:   "resolve blob_f1a2b3"     → content hash
```

Files are identified by blob hash. Path is secondary. Different versions are different hashes. Unchanged files share the same hash across commits. Change detection is structural.

### Render collapses to reasoning steps

No directory tree. No git log. No raw content in prompts. Just recent reasoning steps with their hashes. Everything else is resolvable on demand.

```
Render:
  [step_abc] "config model_id needs updating" refs: [blob_f1a2b3, commit_789]
  [step_def] "user confirmed change" refs: [step_abc]
```

### Three abstraction levels (all steps)

```
Level 0: atomic step       — one observation, references content hashes
Level 1: reasoning step    — traces causal chain across atomic steps, references step hashes
Level 2: higher reasoning  — traces patterns across reasoning steps
Level N: still just a step — refs + desc + scores
```

---

## The Turn Loop (Finalized)

### Persistent 5.4 iterating pre→post→pre→post

```
1. INPUT
   5.4 receives user message within cached trajectory (hash map of prior steps)

2. PRE-DIFF (5.4 produces)
   Multiple assessments, each IS a gap articulation:
   - Builds step chains from trajectory hashes
   - Articulates each chain's relationship to referred context
   - References blobs/trees/commits that need resolving
   - Each assessment encodes an ideal state that vocab maps onto

3. POST-DIFF SKELETON (5.4 scores)
   For each gap: direct vocab mapping + score

4. GOVERNOR (deterministic)
   - Computes gap width: distance between pre-articulation and action mapping
   - Selects widest gap
   - Determines: observe or mutate
   - Routes to selected vocab/tool

5. NEXT ITERATION
   Kernel resolves ALL hashes referenced in selected gap
   → injects resolved data into 5.4 session
   → 5.4 produces new pre-diff (deeper perception, sharper gaps)
   → if gap has vocab/tool mapping from prior step:
     → 5.4 composes command
     → kernel executes → commits
   → postcondition fires: deterministic observation via blob hash

6. REPEAT from step 2 until governor HALT → synthesize from session
```

### Observe/mutate enforced by vocab

Internal &/&mut is redundant — the trajectory IS internal state. Every step mutates the hash map. What remains:
- **Observe vocab**: scan_needed, pattern_needed, hash_resolve_needed, etc. → resolve hashes
- **Mutate vocab**: content_needed, script_edit_needed, command_needed, etc. → execute + commit

### Precondition observation reads via blob hash

scan_needed doesn't read by file path — it resolves a blob hash. All observation is hash resolution.

### Postconditions fire via blob hash

After a mutation commits, the postcondition is deterministic: resolve the new commit hash. No separate tool needed — just blob resolution.

---

## Predefined Step Hashes (Domain Knowledge as Code)

### Concept

Predefined hashes resolve to step scripts — sequences of atomic steps the LLM must follow. They encode domain knowledge, workflows, and reusable patterns as hash-addressable entities.

```
hash_CONFIG_EDIT  → step script: read blob → identify key → compose edit → commit
hash_RESEARCH     → step script: decompose → search → verify → extract → store
hash_LAND_REGISTRY → step script: resolve blob → query API → store result
```

The LLM references predefined hashes like any other hash. The kernel resolves them to executable step sequences. Domain knowledge is encoded as hash entities, not system prompt text.

### Per-step configuration

Each atomic step within a predefined script is configurable:

```
hash_LAND_REGISTRY:
  steps:
    - { action: "resolve_blob", post_diff: false }   # deterministic, no discovery
    - { action: "query_api", post_diff: false }       # deterministic
    - { action: "store_result", post_diff: true }     # flexible — LLM reasons about result

hash_RESEARCH:
  steps:
    - { action: "decompose", post_diff: true }        # flexible — LLM decides subtopics
    - { action: "search", post_diff: true }           # flexible — LLM evaluates sources
    - { action: "extract", post_diff: false }         # deterministic — store findings
```

### post_diff flag controls execution mode

| post_diff | Mode | Behavior |
|-----------|------|----------|
| false | Deterministic | Execute and move on. No gaps, no discovery. Workflow. |
| true | Flexible | Execute, then LLM reasons. Gaps may surface. Exploration. |

### Four injection patterns

```
1. Information injection:     resolve blob → inject into context (no execution)
2. Execute + inject:          run command → inject result as blob hash
3. Execute + create + inject: run command → commit → inject commit hash
4. Pure execution:            run command → no injection (fire and forget)
```

### Workflows are just predefined scripts with post_diff: false

A workflow = a predefined step script where most steps are deterministic. A flexible agent task = same script with post_diff: true on key steps. Same structure, different config.

### Discovery → crystallization → reuse

```
Discovery:    atomic steps unfold naturally → pattern emerges across turns
Crystallize:  recurring pattern encoded as predefined step hash
Reuse:        LLM references the hash instead of rediscovering
Improve:      post_diff: true on key steps lets the pattern evolve over time
```

Predefined steps replace workflows. They are hash-addressable, composable, configurable per atomic step, and self-improving through trajectory observation.

---

## Ledger as Stack (Depth-First Chain Resolution)

### Back to front — LIFO

The ledger is a stack. Origin gaps from the pre-diff enter first. Child gaps push on top. The compiler always pops from the top — deepest child first.

```
Origin gaps:     [gap_A, gap_B, gap_C]
gap_A chains:    [gap_A, gap_B, gap_C, gap_D, gap_E]
                                              ↑ pop this first
Resolve gap_E → [gap_A, gap_B, gap_C, gap_D]
Resolve gap_D → [gap_A, gap_B, gap_C]
gap_A complete → [gap_B, gap_C]
```

The compiler's job: **pop top of stack, route by vocab.** No backward search. No planning. Just pop and route. The chain resolves itself depth-first.

### One chain at a time

The compiler never interleaves chains. Follow gap_A's chain all the way down before touching gap_B. Each chain is a unit of work. The boundary between chains is: the point where all children of an origin gap are resolved and the next origin gap gets its turn.

### Chains ARE reasoning steps

A chain that branches (origin gap → child steps → deeper children) is a reasoning step. It's stored as a unit with its own hash. A gap that resolves in one step is just an atom — not a chain.

```
[chain_abc] "config investigation" (4 steps, origin: gap_A)
  gap_A → step_1 → step_2 → step_3 → resolved

[atom_def] "main.py check" (1 step, origin: gap_B)
  gap_B → step_4 → resolved
```

Render shows chains as units. The trajectory stores both the chain hash and the individual atom hashes within it.

---

## OMO Rhythm (Observe-Mutate-Observe)

Every chain self-organises as OMOMOMO. The rhythm is enforced by vocab mapping + automatic postconditions:

```
O: vocab = scan_needed / hash_resolve_needed → resolve hash (observe)
M: vocab = script_edit_needed / content_needed → execute + commit (mutate)
O: postcondition auto-fires → resolve new commit blob (observe)
```

O M O is the atomic unit. You can never mutate without observing first (pre-observation resolves hash data). You can never leave a mutation unverified (postcondition fires as observation). The pattern writes itself — the compiler doesn't plan the sequence, it emerges from the structure.

---

## Dormant Gaps (Peripheral Vision)

Every gap the LLM articulates gets hashed and stored on the trajectory, whether acted on or not. Unresolved gaps below threshold are dormant — blobs that never reached the ledger.

```
Step [abc123]:
  gap 1: [hash_111] "config model_id wrong" — acted on
  gap 2: [hash_222] "utils.py stale imports" — dormant (below threshold)
  gap 3: [hash_333] "naming inconsistency" — dormant (too low relevance)
```

Dormant gaps are:
- Addressable: any future step can reference hash_222
- Trackable: recurring dormant gaps across turns = structurally significant
- Promotable: if hash_222 keeps appearing, system can raise its priority

The trajectory captures everything the LLM noticed, not just what it did. Dormant gaps are the system's peripheral vision — roads not taken, but mapped.

---

## Chain Extraction and Crystallization

### Long chains extract to separate files

Chains exceeding a threshold length are extracted from the inline trajectory to their own `.json` file:

```
trajectory.json: [..., chain_ref: "chains/chain_abc123.json", ...]
chains/chain_abc123.json: [step_1, step_2, ..., step_15]
```

### Recurring patterns promote to .st

When extracted chains show recurring vocab sequences and resolution patterns, they crystallize into predefined `.st` files:

```
chains/chain_abc.json: [scan → scan → edit → scan]   ← extracted
chains/chain_def.json: [scan → scan → edit → scan]   ← same pattern
→ crystallize: skills/file_edit_pattern.st            ← promoted
```

### Chain analysis

A future module can analyze extracted chains:
- Length vs gap width (how deep did the system go?)
- Branch factor (how many sub-gaps per step?)
- Backtrack count (how many direction changes?)
- Vocab sequence (which tools in what order?)
- Convergence trajectory (how did confidence evolve?)

---

## Recursive Convergence

Chain hashes compress arbitrarily complex history into one addressable reference. A project with 500 steps across 30 turns is one chain hash. The agent references it the same way it references a single atom.

```
[project_hash] "property research platform"
  → [chain_1] "land registry integration" (12 steps)
  → [chain_2] "EPC lookup" (8 steps)
  → [chain_3] "flood risk check" (15 steps)
    → [atom_45] "discovered API rate limit"
      → [blob_xyz] actual API response
```

One hash at the top. Unfoldable downward to any depth. Buildable upward to any abstraction. The agent holds one reference and has access to everything — nothing in the context window until resolved on demand.

Forward: resolve(hash) → what IS it
Backward: trace(hash) → how did it get here

Every blob has a birth story. Every chain has a resolution path. The graph is bidirectional and complete.

---

## Closed Hash Graph (No Contamination)

The trajectory is a closed hash graph. Nothing enters without being stepped:

```
External data → kernel hashes it → blob → step references blob hash
```

Raw data never touches the trajectory. Only hash references and semantic descriptions. Contamination vectors — all blocked:
- Raw file dump → only blob hash + description
- LLM hallucination → fabricated hash won't resolve
- Tool errors → isolated in blob, step describes the error
- Stale data → new commit = new hash, old hash = old version

The reasoning graph is self-verifying.

---

## Module Collapse (v5 Architecture)

No Rust crate. Pure Python + JSON + .st + git.

```
cors/
  step.py              ← step primitive, gap, chain, trajectory
  compile.py           ← compiler: ledger stack, governor, admission, OMO, chains
  loop.py              ← turn loop: persistent 5.4, pre/post, synthesis

  skills/
    loader.py          ← loads .st files, hashes, registers
    *.st               ← predefined step packages (skills, identities, commitments)

  tools/
    hash_resolve.py    ← resolve blob/tree/commit/step hashes
    st_builder.py      ← build .st files from semantic intent
    code_exec.py       ← shell execution
    ...                ← observation + mutation tools

  docs/                ← module specs, architecture, principles
  tests/               ← principle validation tests

  trajectory.json      ← reasoning trajectory (step hashes, append-only)
  chains/              ← extracted long chains
  .git/                ← content storage (blobs, trees, commits)
```

| v4.5 (~8200 lines Rust) | v5 |
|--------------------------|-----|
| delta.rs | step.py |
| quadrant.rs | gone (internal/external collapsed) |
| ledger.rs | compile.py (stack-based ledger) |
| compile.rs | compile.py (pop + route + governor) |
| render.rs | loop.py (render recent chain hashes) |
| memory.rs | trajectory.json + git |
| kernel.rs | loop.py |

---

## Vocab as Deterministic Bridge

The LLM maps gaps to vocab. The kernel maps vocab to tools or `.st` files. Clean separation:

```
LLM:    "this gap is research_needed"  (semantic judgment)
Kernel: research_needed → research.st  (deterministic lookup)
```

Vocab routing table:

```
Observe vocab → tools:
  scan_needed         → tools/scan_tree.py
  pattern_needed      → tools/file_grep.py
  hash_resolve_needed → tools/hash_resolve.py
  research_needed     → skills/research.st (expands into child gaps)
  email_needed        → tools/email_check.py
  url_needed          → tools/url_fetch.py

Mutate vocab → tools:
  script_edit_needed  → tools/file_edit.py
  content_needed      → tools/file_write.py
  command_needed      → tools/code_exec.py
  message_needed      → tools/email_send.py
  git_revert_needed   → tools/git_ops.py
```

Some vocab maps to a single tool (one step). Some maps to a `.st` file (expands into child gaps on the ledger). The compiler doesn't distinguish — it pops the stack and routes.

### .st file resolution as ledger intervention

When the compiler pops a gap whose vocab maps to a `.st` file:

```
Compiler pops: { vocab: "research_needed" }
  → kernel: research_needed maps to research.st
  → research.st resolves → its steps inject as child gaps on the ledger
  → compiler now addresses those child gaps depth-first
  → each child gap has its own vocab, post_diff, and hash refs
```

The `.st` file replaces direct execution with a structured sequence.

---

## No Micro Loop

The chain IS the micro loop. The chain length self-adjusts to model intelligence. Same compiler, same stack, same OMO — different depths depending on how efficiently the model resolves gaps.

---

## post_diff as Universal Configuration

Every gap on the ledger carries `post_diff`. The compiler reads it when popping:

```
pop → post_diff: true  → execute → LLM reasons → may branch
pop → post_diff: false → execute → move on → no reasoning
```

A single turn mixes strict and exploratory steps on the same ledger. Configurable per `.st` step, per injected gap, per origin gap. The strictness dial — from pure workflow to full autonomy.

---

## .st as Manifestation

A `.st` file manifests a specialized agent from the base model for the duration of a chain. It can carry an `inject` field for scoped prompt control:

```json
{
  "action": "enter_research_mode",
  "inject": {
    "system": "Prioritize source verification. Score every claim against evidence.",
    "temperature": 0.3
  },
  "post_diff": false
}
```

The kernel reads `inject` and modifies the LLM's context. When the chain closes, the injection expires. Manifestations can nest — a research agent can invoke a code reviewer within its chain, which dissolves when done.

Manifestation types:

| .st type | Trigger | Example |
|----------|---------|---------|
| Skill | on_vocab:X | research.st — deep research pipeline |
| Identity | on_contact:X | admin.st — user preferences + context |
| Monitor | every_turn / scheduled | monitor_api.st — health checks |
| Commitment | manual / on_mention | london_councils.st — tracked task |

All the same format. All hash-addressable. All executable by the same compiler.

---

## Identity as .st

Users are `.st` files. `admin.st` fires on contact match, injecting identity as deterministic steps. The user's hash appears on every step they trigger. Identity evolves — agent updates the `.st` file, git commits, hash changes, future turns use the latest version.

---

## HEAD Always Injected

Every turn: `git rev-parse HEAD` → commit tree injected as hash data. Top-level trees and blobs visible. Deeper content resolved on demand. One hash = entire workspace state. No pre-commit ceremony. Commits only on mutation.

```
[commit_abc123] HEAD
  [tree_aaa] skills/
  [tree_bbb] tools/
  [blob_f1a] config.json
  [blob_c4d] main.py
```

---

## The Complete Architecture

```
cors/
  step.py              ← step primitive, gap, chain, trajectory, hash computation
  compile.py           ← compiler: ledger stack, admission/placement, OMO, chain lifecycle
  loop.py              ← turn loop: persistent 5.4, pre/post iteration, synthesis

  skills/
    loader.py          ← loads .st files, hashes, registers
    admin.st           ← identity: Kenny (evolves)
    research.st        ← skill: research pipeline
    config_edit.st     ← skill: config editing
    *.st               ← commitments, monitors, domain skills

  tools/
    hash_resolve.py    ← resolve blob/tree/commit/step hashes
    st_builder.py      ← build .st files from semantic intent
    code_exec.py       ← shell execution
    file_edit.py       ← file editing
    web_search.py      ← web research
    ...

  trajectory.json      ← reasoning trajectory (step hashes, append-only)
  chains/              ← extracted long chains (.json)
  .git/                ← content storage (blobs, trees, commits)
  docs/                ← module specs, architecture, principles, design notes
  tests/               ← principle validation (95 tests, all structural, no LLM)
```

Three Python files. One skill format. One trajectory file. Git as the database. Everything else is tools and skills — hot-swappable, hash-addressed, structurally composable.
