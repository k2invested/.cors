# skills/ — Step Packages (.st files)

**Layer**: 0 (no dependencies)
**Principles**: §8, §14, §16, §17, §18, §19, §20

## Purpose

`.st` files are hash-addressable step scripts. They encode domain knowledge, workflows, identities, monitors, and commitments as sequences of atomic steps the system executes. Loaded at startup, hashed, and registered. The LLM references them by hash or they fire by trigger.

## .st Schema

```json
{
  "name": "skill_name",
  "desc": "what this skill does",
  "trigger": "manual | on_contact:X | on_vocab:X | every_turn | on_mention | scheduled:Xh | command:X",
  "author": "developer | agent",
  "refs": {
    "ref_name": "blob_or_chain_hash"
  },
  "steps": [
    {
      "action": "action_name",
      "desc": "what this step does",
      "vocab": "hash_resolve_needed | pattern_needed | hash_edit_needed | null",
      "post_diff": true,
      "resolve": ["ref_name"],
      "condition": "previous_step.failed",
      "inject": {
        "system": "prompt modification text",
        "temperature": 0.3
      }
    }
  ]
}
```

### Required fields

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| name | str | yes | Skill identifier |
| desc | str | yes | Human-readable description |
| steps | list | no | Step sequence (empty for pure entities — stepless .st files) |
| steps[].action | str | yes (per step) | Action identifier |
| steps[].desc | str | yes (per step) | What this step does |

### Optional fields

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| trigger | str | "manual" | When this skill fires |
| author | str | "developer" | Who created it |
| refs | dict | {} | Named hash references (blobs, chains, commits) |
| steps[].vocab | str | null | Precondition vocab mapping |
| steps[].post_diff | bool | true | Flexible (true) or deterministic (false) |
| steps[].resolve | list | [] | Which refs to resolve before this step |
| steps[].condition | str | null | Conditional execution |
| steps[].inject | dict | null | Scoped prompt modification |
| identity | dict | null | Person identity (name, role, context, etc.) |
| preferences | dict | null | Communication/workflow/architecture preferences |
| constraints | dict | null | Compliance or regulation constraints |
| sources | list | null | Source URLs, APIs, or references |
| scope | str | null | Domain scope definition |

## Trigger Types

| Trigger | Fires when |
|---------|-----------|
| `manual` | Only when explicitly invoked by hash |
| `on_contact:admin` | Message from matching contact_id |
| `on_vocab:research_needed` | Compiler routes a gap with that vocab |
| `every_turn` | Start of every turn |
| `on_mention` | Entity referenced in user message |
| `scheduled:24h` | Every 24 hours |
| `command:X` | Only via /X command. Hidden from LLM registry (not surfaceable through gaps). Bypasses gap routing — executed directly via `run_command()`. |

## post_diff — The Strictness Dial

Per-step configuration that controls execution mode:

| post_diff | Mode | Behavior |
|-----------|------|----------|
| true | Flexible | Execute → LLM reasons → gaps may surface → chain may branch |
| false | Deterministic | Execute → move on → no reasoning, no branching |

A workflow is a .st where most steps are deterministic. An exploration task has post_diff: true on key decision points.

## .st as Manifestation

When a .st file resolves, it manifests a specialized agent for the chain's duration. A .st file can be a workflow (with steps) or a pure entity (stepless — identity/preferences/constraints only). The `inject` field modifies the LLM's context:

```json
{
  "action": "enter_research_mode",
  "inject": {
    "system": "Prioritize source verification. Score every claim.",
    "temperature": 0.3
  },
  "post_diff": false
}
```

Manifestations are scoped to the chain. When the chain closes, the injection expires. Manifestations can nest.

## .st Types

| Type | Written by | Trigger | Example |
|------|-----------|---------|---------|
| Skill | Developer | on_vocab | research.st — research pipeline, hash_edit.st — universal file editing |
| Identity | Developer/Agent | on_contact | admin.st — user preferences |
| Entity | Agent (via reprogramme) | manual / on_mention | pure entities created at runtime (person, concept, domain) |
| Monitor | Developer/Agent | every_turn / scheduled | monitor_api.st |
| Command | Developer | command:X | hidden from LLM, /command only |

All the same format. All hash-addressable. All executable by the same compiler.

### Manifestation fields

The fields present in a .st file determine what the entity IS. st_builder forwards all non-base fields (name, desc, trigger, author, refs, actions) as manifestation config:

| Fields present | Entity type |
|---------------|-------------|
| identity + preferences | Person |
| constraints + sources + scope | Compliance / regulation domain |
| schema + access_rules | Business database |
| principles + boundaries | Domain expertise |

## Existing Skills

| File | Steps | Trigger | Purpose |
|------|-------|---------|---------|
| admin.st | 4 | on_contact:admin | Kenny's identity + preferences (load_identity → load_principles → load_recent → load_commitments) |
| hash_edit.st | 3 | on_vocab:hash_edit_needed | Universal file editing workflow (resolve_target O → compose_edit flexible → execute_edit M). OMO baked into .st structure. |
| research.st | 5 | on_vocab | Research pipeline |

Note: Hashes are computed at load time from file content and change when the .st file is updated. Do not hardcode hashes in documentation.

Skills can also be pure entities (stepless .st files) — e.g. a person, concept, or domain created via reprogramme_needed. The fields present determine what the entity IS.

## Module: loader.py

### Types

| Type | Purpose |
|------|---------|
| SkillStep | One atomic step: action, desc, vocab, post_diff |
| Skill | Complete skill: hash, name, desc, steps[], source, display_name, trigger, is_command |
| SkillRegistry | Hash→Skill, name→Skill, and commands dict. Two visibility tiers: bridge skills (LLM-surfaceable) and command skills (hidden, /command only). |

### Functions

| Function | Purpose |
|----------|---------|
| `load_skill(path) → Skill?` | Load one .st file. Extracts display_name from identity.name. Detects command: trigger prefix → sets is_command. |
| `load_all(skills_dir) → SkillRegistry` | Load all .st files |
| `SkillRegistry.resolve(hash) → Skill?` | Lookup by hash (bridge skills only) |
| `SkillRegistry.resolve_by_name(name) → Skill?` | Lookup by name (bridge skills only) |
| `SkillRegistry.resolve_command(name) → Skill?` | Resolve a /command by name |
| `SkillRegistry.all_commands() → list[Skill]` | List all command skills |
| `SkillRegistry.render_for_prompt() → str` | Render for LLM context (excludes command skills) |
| `SkillRegistry.resolve_name(hash) → str?` | Hash → display name for tree rendering (e.g. "kenny", "research"). Extracted from identity.name or defaults to skill name. |

## Module: tools/st_builder.py

Builds valid .st files from semantic intent. The agent describes what it wants in natural language, the builder handles structure and validation.

### Input (semantic intent)
```json
{
  "name": "task name",
  "desc": "what it does",
  "trigger": "manual",
  "actions": [
    { "do": "read the config", "observe": true },
    { "do": "edit the value", "mutate": true }
  ]
}
```

### Output
Valid .st file with auto-generated action names, inferred vocab, and correct post_diff settings.

### Features
- Vocab inference from action descriptions (regex patterns)
- Auto-generated action slugs
- Schema validation before writing (steps field optional — allows stepless pure entities)
- Handles refs passthrough
- Forwards all non-base fields (identity, preferences, constraints, sources, scope — any manifestation fields) from intent to .st file
- Supports `command:` trigger prefix for hidden /command skills
- Valid triggers: manual, every_turn, on_mention, on_contact:X, on_vocab:X, scheduled:Xh, command:X
