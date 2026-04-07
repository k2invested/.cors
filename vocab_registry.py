from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VocabSpec:
    name: str
    category: str  # observe | mutate | bridge
    priority: int
    deterministic: bool = False
    observation_only: bool = False
    allows_post_gap_emission: bool = True
    tool: str | None = None
    post_observe: str | None = None
    desc: str = ""
    target_kind: str | None = None
    target_ref: str | None = None
    prompt_hint: str = ""

# BEGIN CONFIGURABLE_VOCABS
CONFIGURABLE_VOCABS: dict[str, VocabSpec] = {
    "hash_resolve_needed": VocabSpec(
        name="hash_resolve_needed",
        category="observe",
        priority=20,
        deterministic=True,
        observation_only=False,
        allows_post_gap_emission=True,
        tool=None,
        desc="Resolve hashes and observe the resulting context.",
        target_kind="tool",
        target_ref="f4f6e4bf8d15",
    ),
    "pattern_needed": VocabSpec(
        name="pattern_needed",
        category="observe",
        priority=20,
        deterministic=False,
        observation_only=False,
        tool="tools/file_grep.py",
        desc="Search for a deterministic pattern in workspace content.",
        target_kind="tool",
        target_ref="d5b8c72f9e8c",
    ),
    "email_needed": VocabSpec(
        name="email_needed",
        category="observe",
        priority=20,
        deterministic=False,
        observation_only=False,
        tool="tools/email_check.py",
        desc="Inspect email context or mailbox state.",
        target_kind="tool",
        target_ref="d58156396f0a",
    ),
    "external_context": VocabSpec(
        name="external_context",
        category="observe",
        priority=20,
        deterministic=False,
        observation_only=True,
        allows_post_gap_emission=False,
        tool=None,
        desc="Inject external context as passive observation only.",
    ),
    "architect_needed": VocabSpec(
        name="architect_needed",
        category="mutate",
        priority=40,
        desc="Run the architect workflow to analyse source/doc/test drift and hand off exact edits if syncing is warranted.",
        target_kind="chain",
        target_ref="bbd5a3bf44ef",
    ),
    "hash_edit_needed": VocabSpec(
        name="hash_edit_needed",
        category="mutate",
        priority=40,
        tool="tools/hash_manifest.py",
        desc="Patch or rewrite a workspace file.",
        target_kind="tool",
        target_ref="20c7462db20c",
    ),
    "stitch_needed": VocabSpec(
        name="stitch_needed",
        category="mutate",
        priority=40,
        tool="tools/stitch_generate.py",
        post_observe="ui_output/",
        desc="Generate stitched UI output artifacts.",
        target_kind="tool",
        target_ref="533639db50a2",
    ),
    "content_needed": VocabSpec(
        name="content_needed",
        category="mutate",
        priority=40,
        tool="tools/hash_manifest.py",
        desc="Write new content into the workspace through the hash manifest primitive.",
        target_kind="tool",
        target_ref="20c7462db20c",
    ),
    "command_needed": VocabSpec(
        name="command_needed",
        category="mutate",
        priority=40,
        tool="tools/code_exec.py",
        post_observe="bot.log",
        desc="Execute a shell command to mutate state.",
        target_kind="tool",
        target_ref="52f151625add",
    ),
    "message_needed": VocabSpec(
        name="message_needed",
        category="mutate",
        priority=40,
        tool="tools/email_send.py",
        desc="Send a message or email.",
        target_kind="tool",
        target_ref="0aa81af568e8",
    ),
    "json_patch_needed": VocabSpec(
        name="json_patch_needed",
        category="mutate",
        priority=40,
        tool="tools/hash_manifest.py",
        desc="Apply a structured JSON patch through the hash manifest primitive.",
        target_kind="tool",
        target_ref="20c7462db20c",
    ),
    "git_revert_needed": VocabSpec(
        name="git_revert_needed",
        category="mutate",
        priority=40,
        tool="tools/git_ops.py",
        desc="Revert git state.",
        target_kind="tool",
        target_ref="7320bac4d41b",
    ),
}
# END CONFIGURABLE_VOCABS

# BEGIN FOUNDATIONAL_BRIDGES
FOUNDATIONAL_BRIDGES: dict[str, VocabSpec] = {
    "clarify_needed": VocabSpec(
        name="clarify_needed",
        category="bridge",
        priority=20,
        deterministic=False,
        observation_only=False,
        desc="Request missing user-only information after reason has exhausted available context.",
    ),
    "reason_needed": VocabSpec(
        name="reason_needed",
        category="bridge",
        priority=90,
        desc="Stateful inline judgment and routing.",
    ),
    "tool_needed": VocabSpec(
        name="tool_needed",
        category="bridge",
        priority=92,
        tool="system/tool_builder.py",
        desc="Reason-routed tool authoring branch with validated runtime contract metadata.",
    ),
    "vocab_reg_needed": VocabSpec(
        name="vocab_reg_needed",
        category="bridge",
        priority=93,
        tool="system/vocab_builder.py",
        desc="Reason-routed semantic vocab routing branch for configurable observe/mutate paths.",
    ),
    "await_needed": VocabSpec(
        name="await_needed",
        category="bridge",
        priority=95,
        desc="Pause and rejoin with synchronized background work.",
    ),
    "reprogramme_needed": VocabSpec(
        name="reprogramme_needed",
        category="bridge",
        priority=99,
        desc="Stateless semantic persistence primitive.",
    ),
}
# END FOUNDATIONAL_BRIDGES


VOCABS: dict[str, VocabSpec] = {**CONFIGURABLE_VOCABS, **FOUNDATIONAL_BRIDGES}
FOUNDATIONAL_BRIDGE_POST_OBSERVE = {
    "tool_needed": "reason_needed",
    "vocab_reg_needed": "reason_needed",
}


def get_vocab(name: str | None) -> VocabSpec | None:
    if not name:
        return None
    return VOCABS.get(name)


def has_vocab(name: str | None) -> bool:
    return get_vocab(name) is not None


def is_observe(name: str | None) -> bool:
    spec = get_vocab(name)
    return bool(spec and spec.category == "observe")


def is_mutate(name: str | None) -> bool:
    spec = get_vocab(name)
    return bool(spec and spec.category == "mutate")


def is_bridge(name: str | None) -> bool:
    spec = get_vocab(name)
    return bool(spec and spec.category == "bridge")


def vocab_priority(name: str | None) -> int:
    spec = get_vocab(name)
    return spec.priority if spec is not None else 50


OBSERVE_VOCAB = {name for name, spec in CONFIGURABLE_VOCABS.items() if spec.category == "observe"}
MUTATE_VOCAB = {name for name, spec in CONFIGURABLE_VOCABS.items() if spec.category == "mutate"}
BRIDGE_VOCAB = set(FOUNDATIONAL_BRIDGES)

DETERMINISTIC_VOCAB = {name for name, spec in VOCABS.items() if spec.deterministic}
OBSERVATION_ONLY_VOCAB = {name for name, spec in VOCABS.items() if spec.observation_only}
TOOL_MAP = {
    name: {k: v for k, v in {"tool": spec.tool, "post_observe": spec.post_observe}.items() if v is not None or k == "tool"}
    for name, spec in CONFIGURABLE_VOCABS.items()
    if spec.category in {"observe", "mutate"}
}


def validate_tree_policy_targets(policy: dict) -> list[str]:
    invalid: list[str] = []
    for path, rule in policy.items():
        if not isinstance(rule, dict):
            continue
        for key in ("on_mutate", "on_reject"):
            target = rule.get(key)
            if target and not has_vocab(str(target)):
                invalid.append(f"{path}:{key}:{target}")
    return invalid


def render_configurable_vocab_registry() -> str:
    lines = ["## Configurable Vocab Registry"]
    for name, spec in CONFIGURABLE_VOCABS.items():
        target = spec.target_ref or "internal"
        lines.append(
            f"- {name} | classifiable={spec.category} | target_kind={spec.target_kind or 'none'} | target_ref={target} | {spec.desc}"
        )
    return "\n".join(lines)


def find_vocab_for_tool_ref(tool_ref: str | None) -> str | None:
    if not isinstance(tool_ref, str) or not tool_ref:
        return None
    best_name: str | None = None
    best_priority: int | None = None
    for name, spec in CONFIGURABLE_VOCABS.items():
        if spec.target_kind != "tool" or spec.target_ref != tool_ref:
            continue
        if best_priority is None or spec.priority < best_priority:
            best_name = name
            best_priority = spec.priority
    return best_name
