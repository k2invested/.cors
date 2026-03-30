# Principles v5 — Step Kernel

## 1. The Primitive: Step

A step is meaningful movement. It is the only primitive.

A step is a transition — not a snapshot, not a state, but the movement between states. Every behaviour in the system is expressible as a step. Every mechanism is step operating at a different scale.

### Two-phase transition

A step has two phases:

**Phase 1 — Internal / Premeditation (pre-diff)**

The diff caused by perception. When the system perceives — an input arrives, context is surfaced, a tool returns — internal state changes. This is premeditation: the system's state shifts just from observing. Whether or not anything external changes, a diff is produced. Perception IS mutation.

This is typically an internal state change: new references surfaced, new understanding formed, epistemic scores adjusted. The pre-diff captures what the system now knows or believes that it didn't before.

**Phase 2 — External / Post-verification (post-diff)**

A standard or ideal state is projected onto the current state based on referred/surfaced context. The difference between "what is" and "what should be" produces a gap. This gap is the post-diff — the forward-facing delta that drives action.

Post-verification turns perception into something actionable. Even if no external change occurs, the gap between current and ideal is now a diff that can be reasoned over.

### The two phases together

```
input/event arrives
  → perception shifts internal state           (pre-diff)
  → ideal state projected against current      (post-diff / gap)
  → the pair (pre, post) IS the step
```

Every step, regardless of domain or scale, follows this structure. Observation produces a pre-diff. Assessment produces a post-diff. The step is complete.

### The quadrant simplification

The v4.5 quadrant model (internal/external × &/&mut) collapses. Pre-diff IS internal &mut — it happens every step. There is no separate internal & or internal &mut category. What remains:

- **Pre-diff** = internal (always, every step — the LLM's perception)
- **Post-diff** = external (only when the environment is mutated)

| v4.5 | v5 |
|------|-----|
| Internal & (observe own state) | Pre-diff (every step) |
| Internal &mut (mutate own state) | Pre-diff (every step) |
| External & (observe environment) | Tool executes, result enters pre-diff (no commit) |
| External &mut (mutate environment) | Post-diff → command → commit |

## 2. The LLM as Attention Mechanism

The LLM is an attention mechanism that produces qualitative semantic judgment over structured transition states and commit hashes. It does not control, execute, or route. It attends to structure and produces meaning.

```
Kernel: structure, execution, deterministic routing
LLM:    attention, semantics, qualitative judgment
```

The LLM reads structure → produces meaning.
The kernel reads meaning → produces structure.

### Two-model architecture

**5.4-mini (stateless)**: reads the compressed trajectory, produces post-diffs (gaps with scores and hash refs). Surface-level perception. Can run 2-3 calls per step for richer signal via matrix scoring. Coherence comes from the structure of the trajectory, not from session memory.

**5.4 (stateless, per-precond)**: composes commands for external execution. One model, different system messages per precondition. Used for all external paths — both observation and mutation.

```
precond: scan_needed    → 5.4 + "compose a scan command"      (external &, no commit)
precond: content_needed → 5.4 + "compose a write command"     (external &mut, commit)
precond: command_needed → 5.4 + "compose a shell command"     (external &mut, commit)
precond: domain_needed  → 5.4 + "compose a search query"     (external &, no commit)
```

No persistent LLM session needed. Coherence lives in the trajectory structure.

### Pre-diff is emergent

The pre-diff is emergent from the LLM's attention. The trajectory is shown to the LLM with hashes embedded. Whichever hashes the LLM references in its output ARE the pre-diff — the act of selecting which hashes to mention IS the perception.

```
Atom {
    pre:  [abc123, def456],     // hashes LLM attended to from trajectory
    post: Option<Hash>,          // commit SHA if mutation occurred
    content: "...",              // semantic output of attention
}
```

Two layers of control:
- **Kernel** decides what the LLM sees (salience gates the trajectory)
- **LLM** decides what it attends to (semantic selection from what was shown)

## 3. Commits and Reverts

### Commits are deterministic

Every external &mut command automatically produces a commit. This is not an LLM decision — it is a deterministic kernel operation that fires after every mutation.

```
5.4 composes command → kernel executes → state changes → auto-commit → SHA recorded as post hash
```

The commit is the kernel's record that the environment changed. The SHA becomes the atom's post hash. No manual commit step needed.

### Reverts as mistake recovery

When the system detects a mistake (via mini verification, confidence drop, or explicit error), it reverts to a prior commit state. A revert is itself an external &mut — a mutation that restores a previous state.

```
step N: command executes → commit abc123
step N+1: mini verifies → confidence drops → mistake detected
step N+2: git revert abc123 → commit def456 (the revert is itself a commit)
```

The revert vocabulary:
- Revert last commit (one step back)
- Revert to pre-step commit (before the current step's mutations)
- Revert multiple commits (roll back N steps within a turn)

Reverts are traceable — they produce their own commits. The trajectory shows: "committed, detected mistake, reverted." The system can reason about the revert count:
- 0 reverts → clean execution
- 1 revert → corrected course
- Multiple reverts → struggling, may need to reclassify or escalate

The number of commits and reverts within a step is a signal the meta layer can reason about. High revert count on a gap suggests the approach is wrong, not just the execution.

## 4. Steps that Surface Steps: The Meta Layer

Steps that surface other steps containing commits can be reasoned over as a higher order of steps. This is the meta layer — and it replaces the v4.5 compiler.

When the system recalls prior commits during a step, those commits enter the pre-diff as surfaced references. The current step now operates not just on raw input, but on the history of prior transitions. This is recursive — the return value of prior step() calls becoming the input to the current step() call.

The meta layer does not replace the atomic layer. It operates in parallel, in tandem — two interconnected recursive layers:

**Atomic layer**: step() operates on state. Observe, assess, act. Produces diffs and commits.

**Meta layer**: step() operates on the trajectory of the atomic layer. Goal evaluation, strategic planning, knowledge integration, policy adjustment. Consumes trajectory diffs, produces higher-order assessments that influence how the atomic layer responds.

```
Atomic:  step(state, input)        → (state', diff, commit?)
Meta:    step(trajectory, diffs)   → (assessment, goal_adjustment, policy)
                ↑                              ↓
                └──────── influences ──────────┘
```

### The meta layer as compiler

In v4.5, a deterministic backward-search compiler planned tool paths. In v5, the meta layer subsumes this function. The LLM reads the trajectory (compressed, hash-rich), reasons about which gaps to address next, and produces structured post-diffs that the kernel routes.

What remains in the kernel is pure routing — precond → tool → execute → commit. The planning intelligence lives in the meta layer's reasoning over the trajectory. Deterministic safety checks (stagnation detection, divergence, oscillation) remain in the kernel as vector math over epistemic scores.

## 5. Navigation, Not Search

The pre-diff mechanism is an exploration system, not a retrieval system.

Search asks "what matches this query?" — flat, disconnected results. Navigation asks "where does this lead?" — connected, directional traversal through a transition state space.

The LLM navigates. It follows hashes through the state space like following paths through a landscape. Each hash is a waypoint. Each step is a path between waypoints. The causal chain is the route.

From any position (the current step), the LLM can:
- **Read the trajectory**: the path taken to get here (post-diffs, sequential)
- **Follow roots downward**: where did this come from? (pre-diff convergence, many → one)
- **Follow branches forward**: what did this lead to? (post-diff divergence, one → many)
- **Jump to co-occurring hashes**: what else connects to this entity? (graph traversal)

Roots are not preloaded. They are explored on demand — when the LLM decides a thread is worth pulling, the kernel resolves the hash, surfaces the full step with its own hashes, and the LLM can follow further. Depth is controlled by the kernel (max N hops). Breadth is controlled by salience (which hashes to surface initially).

### Structure: roots, not trees

Pre-diff surfacing is convergent — like roots, not trees. Many sources feed into one present moment. The current step draws context from multiple prior steps, each of which drew from their own sources. The deeper you follow, the more the roots branch and intertwine.

Post-diff action is divergent — one action can lead to many consequences, branching forward.

The step sits at the junction:

```
many → one (convergence at perception / pre-diff)
one → many (divergence at action / post-diff)
```

### The trajectory is alive

- **Readable**: semantic content tells the story
- **Navigable**: hashes are doors into deeper context
- **Lean**: only post-diffs stored, roots resolved on demand
- **Alive**: every hash is a potential exploration, the LLM decides which threads to pull

## 6. One LLM, One Governor

One persistent 5.4 session per turn. No separate mini. The LLM does all semantic work — perception and assessment in one continuous stream. The governor is the only external control.

The LLM's output is "reasoned intent" — always grounded in referred content (specific files, values, commits, entities), never in system state (gaps, confidence, convergence). The same field serves all phases: during perception it's reasoning with hash refs, during action it's a command, during synthesis it's the user response.

The perception loop builds the pre-diff. Working state is mutable (chains grow, session accumulates). When the governor halts the loop, the step is frozen as an immutable blob — same pattern as Git's mutable working tree → immutable commit.

### Articulated chains

The LLM must articulate each hash it explores — not just point at it, but describe what it found. Each chain link carries a description. The chain is a narrated exploration:

```
chain A:
  [aaa]: "workspace commit — config.json, main.py present"
  [bbb]: "config.json contains model_id set to gpt-4o-2024-08-06"

chain B:
  [aaa]: "workspace commit"
  [ccc]: "main.py has no model references — unrelated"
```

Forced articulation ensures:
- The LLM can't lazily hop between hashes — it has to say what it found
- Each description is a signal the governor can measure
- The chain is self-documenting for future turns

### One gap per chain

The post-diff creates one gap per articulated chain. The gap is an analysis of the entire chain — what it means, what action it implies. Each gap carries its own epistemic signal:

```
gap A: "config model_id needs updating" — signal: {rel: 0.95, conf: 0.9, gr: 1.0}
gap B: "main.py is unrelated"           — signal: {rel: 0.1, conf: 0.95, gr: 1.0}
```

The governor computes on gap signals. Irrelevant gaps drop out. Action targets the widest remaining gap. Chains that recur across turns become entities (trees).

## 7. The Governor: Deterministic Linear Algebra

The governor is a convergence monitor that operates on chain structure vectors. Pure linear algebra. No LLM judgment. It is a deterministic mirror of the LLM — computing attention over epistemic vectors the same way a transformer computes attention over token embeddings.

### Perception governance (information gain)

Each resolved hash contributes a structural vector:

```
link_vector = [co_occurrence, commit_distance, tree_membership, recency]
```

The chain is a matrix. The governor computes information gain per iteration:

```
state_vector = mean(all link vectors)
delta        = state_vector - prev_state_vector
gain         = magnitude(delta)

gain > threshold  → ALLOW (still learning)
gain < threshold  → perception saturated (nothing new)
depth > max       → CONSTRAIN (too deep)
```

When the state vector stops moving, the system has learned everything it can from existing hashes. Perception is complete.

### Action governance (epistemic alignment)

After perception, post-diff exists. The governor measures:
- Pre vs post epistemic distance (how wide are the gaps)
- Convergence toward confidence threshold
- Divergence, stagnation, oscillation detection

### Governor signals

| Signal | Trigger |
|--------|---------|
| Allow | information gain above threshold |
| Constrain | chain depth exceeded |
| Redirect | stagnation — no movement in N steps |
| Revert | divergence — confidence dropped after action |
| Act | perception saturated, gaps remain |
| Halt | all gaps closed or pathological |

### Confidence convergence

The system's universal goal: address all gaps with sufficient confidence. No categorical goal definition. No discrete ceiling levels.

```
goal = all gaps above confidence threshold
```

The governor measures distance to this goal. The LLM navigates toward it. The governor decides when to allow, constrain, or halt.

## 8. Two Hash Layers

Clean separation between reasoning and data:

**Step hashes** (Layer 1): the reasoning trajectory. What the system thought, decided, concluded. Semantic descriptions + epistemic scores. Only reasoning steps reference other reasoning steps.

**Content hashes** (Layer 2): blobs, trees, commits. What exists in the environment. Actual data, reconstructable from git. Gaps and assessments reference content hashes. The kernel resolves them on demand.

The trajectory is a closed hash graph. Raw data never touches it — only hash references and semantic descriptions. No external contamination. Hallucinated hashes don't resolve. The reasoning graph is self-verifying.

Entities are identified by hash, not path. Different versions are different hashes. Unchanged content shares the same hash. Change detection is structural.

## 9. Predefined Step Hashes

Domain knowledge encoded as hash-addressable step scripts. A predefined hash resolves to a sequence of atomic steps the system must follow.

```
hash_CONFIG_EDIT   → read blob → identify key → compose edit → commit
hash_RESEARCH      → decompose → search → verify → extract → store
hash_LAND_REGISTRY → resolve blob → query API → store result
```

Each atomic step within a script is configurable via `post_diff`:

- **post_diff: false** → deterministic. Execute and move on. No gaps, no discovery. This is workflow mode.
- **post_diff: true** → flexible. Execute, then LLM reasons. Gaps may surface. This is exploration mode.

Workflows are predefined scripts where most steps are deterministic. Flexible tasks are the same scripts with post_diff: true on key steps. Same structure, different config.

Predefined steps are composable (scripts reference other scripts), reusable (any step can reference the hash), and self-improving (naturally discovered patterns crystallize into predefined hashes over time).

Discovery hardens into knowledge: atomic steps unfold → pattern recurs → crystallize as predefined hash → LLM references instead of rediscovering → post_diff: true on key steps lets the pattern evolve.

## 10. Ledger as Stack

The ledger is a stack. Origin gaps enter first. Child gaps push on top. The compiler pops from the top — deepest child first. Back to front. LIFO. Depth-first per origin gap.

The compiler's only job: pop top of stack, route by vocab. No backward search. No planning. One chain at a time — follow gap_A all the way down before touching gap_B.

## 11. OMO Rhythm

Observe-Mutate-Observe is the heartbeat. Every chain self-organises as OMOMOMO. Enforced by vocab mapping + automatic postconditions:

- Observe: vocab routes to hash resolution (scan_needed, hash_resolve_needed)
- Mutate: vocab routes to execution (script_edit_needed, content_needed) → auto-commit
- Observe: postcondition auto-fires → resolve new commit blob → verify result

O M O is the atomic unit. The compiler doesn't plan the sequence — it emerges from the structure.

## 12. Dormant Gaps

Every gap articulation gets hashed and stored, whether acted on or not. Gaps below threshold are dormant blobs — the system's peripheral vision. Addressable by hash, trackable across turns, promotable if recurring.

## 13. Recursive Convergence

Chain hashes compress arbitrarily complex history into one reference. A 500-step project is one hash. Unfoldable downward. Buildable upward. Forward: resolve(hash) → what is it. Backward: trace(hash) → how did it get here. The graph is bidirectional, complete, and self-verifying.

## 14. Closed Hash Graph

The trajectory is a closed system. Raw data never touches it — only hash references and semantic descriptions. External data enters only through the kernel's hash-and-step pipeline. Hallucinated hashes don't resolve. The reasoning graph cannot be contaminated.

## 15. No Modules

No Rust crate. Pure Python + JSON + .st + git. Three scripts (loop.py, governor.py, step.py), a skills directory of .st files, trajectory.json for reasoning, and git for content storage. ~8200 lines of Rust collapses into the simplicity of the hash primitive.
