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
  "trigger": "manual | on_contact:X | on_vocab:X | every_turn | on_mention | scheduled:Xh",
  "author": "developer | agent",
  "refs": {
    "ref_name": "blob_or_chain_hash"
  },
  "steps": [
    {
      "action": "action_name",
      "desc": "what this step does",
      "vocab": "scan_needed | null",
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
| steps | list | yes | At least one step |
| steps[].action | str | yes | Action identifier |
| steps[].desc | str | yes | What this step does |

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

## Trigger Types

| Trigger | Fires when |
|---------|-----------|
| `manual` | Only when explicitly invoked by hash |
| `on_contact:admin` | Message from matching contact_id |
| `on_vocab:research_needed` | Compiler routes a gap with that vocab |
| `every_turn` | Start of every turn |
| `on_mention` | Entity referenced in user message |
| `scheduled:24h` | Every 24 hours |

## post_diff — The Strictness Dial

Per-step configuration that controls execution mode:

| post_diff | Mode | Behavior |
|-----------|------|----------|
| true | Flexible | Execute → LLM reasons → gaps may surface → chain may branch |
| false | Deterministic | Execute → move on → no reasoning, no branching |

A workflow is a .st where most steps are deterministic. An exploration task has post_diff: true on key decision points.

## .st as Manifestation

When a .st file resolves, it manifests a specialized agent for the chain's duration. The `inject` field modifies the LLM's context:

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
| Skill | Developer | on_vocab | research.st — research pipeline |
| Identity | Developer/Agent | on_contact | admin.st — user preferences |
| Monitor | Developer/Agent | every_turn / scheduled | monitor_api.st |
| Commitment | Agent | manual / on_mention | london_councils.st |

All the same format. All hash-addressable. All executable by the same compiler.

## Existing Skills

| File | Hash | Steps | Trigger | Purpose |
|------|------|-------|---------|---------|
| admin.st | 72b1d5ffc964 | 4 | on_contact:admin | Kenny's identity + preferences |
| research.st | a72c3c4dec0c | 5 | on_vocab | Research pipeline |
| config_edit.st | 843651734922 | 3 | on_vocab | Config file editing |
| complete_london_councils.st | 8144b1a8b318 | 4 | manual | Tracked commitment |

## Module: loader.py

### Types

| Type | Purpose |
|------|---------|
| SkillStep | One atomic step: action, desc, vocab, post_diff |
| Skill | Complete skill: hash, name, desc, steps[], source |
| SkillRegistry | Hash→Skill and name→Skill maps |

### Functions

| Function | Purpose |
|----------|---------|
| `load_skill(path) → Skill?` | Load one .st file |
| `load_all(skills_dir) → SkillRegistry` | Load all .st files |
| `SkillRegistry.resolve(hash) → Skill?` | Lookup by hash |
| `SkillRegistry.resolve_by_name(name) → Skill?` | Lookup by name |
| `SkillRegistry.render_for_prompt() → str` | Render for LLM context |

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
- Schema validation before writing
- Handles refs passthrough
