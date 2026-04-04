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


VOCABS: dict[str, VocabSpec] = {
    "hash_resolve_needed": VocabSpec(
        name="hash_resolve_needed",
        category="observe",
        priority=20,
        deterministic=True,
        observation_only=False,
        allows_post_gap_emission=True,
        tool=None,
        desc="Resolve hashes and observe the resulting context.",
    ),
    "pattern_needed": VocabSpec(
        name="pattern_needed",
        category="observe",
        priority=20,
        deterministic=False,
        observation_only=False,
        tool="tools/file_grep.py",
        desc="Search for a deterministic pattern in workspace content.",
    ),
    "email_needed": VocabSpec(
        name="email_needed",
        category="observe",
        priority=20,
        deterministic=False,
        observation_only=False,
        tool="tools/email_check.py",
        desc="Inspect email context or mailbox state.",
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
    "clarify_needed": VocabSpec(
        name="clarify_needed",
        category="observe",
        priority=20,
        deterministic=False,
        observation_only=False,
        desc="Request missing user-only information.",
    ),
    "hash_edit_needed": VocabSpec(
        name="hash_edit_needed",
        category="mutate",
        priority=40,
        tool="tools/hash_manifest.py",
        desc="Patch or rewrite a workspace file.",
    ),
    "stitch_needed": VocabSpec(
        name="stitch_needed",
        category="mutate",
        priority=40,
        tool="tools/stitch_generate.py",
        post_observe="ui_output/",
        desc="Generate stitched UI output artifacts.",
    ),
    "content_needed": VocabSpec(
        name="content_needed",
        category="mutate",
        priority=40,
        tool="tools/file_write.py",
        desc="Write new content into the workspace.",
    ),
    "script_edit_needed": VocabSpec(
        name="script_edit_needed",
        category="mutate",
        priority=40,
        tool="tools/file_edit.py",
        desc="Edit script content in-place.",
    ),
    "command_needed": VocabSpec(
        name="command_needed",
        category="mutate",
        priority=40,
        tool="tools/code_exec.py",
        post_observe="bot.log",
        desc="Execute a shell command to mutate state.",
    ),
    "message_needed": VocabSpec(
        name="message_needed",
        category="mutate",
        priority=40,
        tool="tools/email_send.py",
        desc="Send a message or email.",
    ),
    "json_patch_needed": VocabSpec(
        name="json_patch_needed",
        category="mutate",
        priority=40,
        tool="tools/json_patch.py",
        desc="Apply a structured JSON patch.",
    ),
    "git_revert_needed": VocabSpec(
        name="git_revert_needed",
        category="mutate",
        priority=40,
        tool="tools/git_ops.py",
        desc="Revert git state.",
    ),
    "reason_needed": VocabSpec(
        name="reason_needed",
        category="bridge",
        priority=90,
        desc="Stateful inline judgment and routing.",
    ),
    "await_needed": VocabSpec(
        name="await_needed",
        category="bridge",
        priority=95,
        desc="Pause and rejoin with synchronized background work.",
    ),
    "commit_needed": VocabSpec(
        name="commit_needed",
        category="bridge",
        priority=98,
        desc="Terminal commitment codon.",
    ),
    "reprogramme_needed": VocabSpec(
        name="reprogramme_needed",
        category="bridge",
        priority=99,
        desc="Stateless semantic persistence primitive.",
    ),
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


OBSERVE_VOCAB = {name for name, spec in VOCABS.items() if spec.category == "observe"}
MUTATE_VOCAB = {name for name, spec in VOCABS.items() if spec.category == "mutate"}
BRIDGE_VOCAB = {name for name, spec in VOCABS.items() if spec.category == "bridge"}

DETERMINISTIC_VOCAB = {name for name, spec in VOCABS.items() if spec.deterministic}
OBSERVATION_ONLY_VOCAB = {name for name, spec in VOCABS.items() if spec.observation_only}
TOOL_MAP = {
    name: {k: v for k, v in {"tool": spec.tool, "post_observe": spec.post_observe}.items() if v is not None or k == "tool"}
    for name, spec in VOCABS.items()
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
