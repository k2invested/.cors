"""Authoritative runtime vocab registry.

This module is the single source of truth for kernel-visible vocab:
family, routing helpers, and a small amount of derivable operational
metadata used by renderers, compilers, and security tooling.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VocabSpec:
    name: str
    family: str
    target_surface: str
    scope_profile: str
    topology_prior: str
    ref_posture: str
    postcondition_mode: str
    protection_mode: str
    class_code: str


VOCAB_SPECS: dict[str, VocabSpec] = {
    "hash_resolve_needed": VocabSpec(
        name="hash_resolve_needed",
        family="observe",
        target_surface="addressed_content",
        scope_profile="micro",
        topology_prior="linear",
        ref_posture="strict_hash",
        postcondition_mode="none",
        protection_mode="low",
        class_code="o",
    ),
    "pattern_needed": VocabSpec(
        name="pattern_needed",
        family="observe",
        target_surface="content_pattern",
        scope_profile="micro",
        topology_prior="linear",
        ref_posture="strict_hash",
        postcondition_mode="followup_optional",
        protection_mode="low",
        class_code="o",
    ),
    "mailbox_needed": VocabSpec(
        name="mailbox_needed",
        family="observe",
        target_surface="mailbox",
        scope_profile="bounded",
        topology_prior="bounded_branch",
        ref_posture="implicit_or_step_ref",
        postcondition_mode="followup_optional",
        protection_mode="medium",
        class_code="o",
    ),
    "external_context": VocabSpec(
        name="external_context",
        family="observe",
        target_surface="transient_context",
        scope_profile="micro",
        topology_prior="blob",
        ref_posture="optional",
        postcondition_mode="none",
        protection_mode="low",
        class_code="o",
    ),
    "research_needed": VocabSpec(
        name="research_needed",
        family="observe",
        target_surface="discovery",
        scope_profile="open",
        topology_prior="recursive_discovery",
        ref_posture="entity_or_hash_seed",
        postcondition_mode="workflow_defined",
        protection_mode="package_scoped",
        class_code="o",
    ),
    "hash_edit_needed": VocabSpec(
        name="hash_edit_needed",
        family="mutate",
        target_surface="blob",
        scope_profile="micro",
        topology_prior="linear",
        ref_posture="strict_hash",
        postcondition_mode="hash_resolve",
        protection_mode="protected_reroute",
        class_code="m",
    ),
    "stitch_needed": VocabSpec(
        name="stitch_needed",
        family="mutate",
        target_surface="generated_artifact",
        scope_profile="bounded",
        topology_prior="bounded_branch",
        ref_posture="optional",
        postcondition_mode="artifact_preview",
        protection_mode="medium",
        class_code="m",
    ),
    "content_needed": VocabSpec(
        name="content_needed",
        family="mutate",
        target_surface="content",
        scope_profile="bounded",
        topology_prior="bounded_branch",
        ref_posture="optional",
        postcondition_mode="hash_resolve",
        protection_mode="medium",
        class_code="m",
    ),
    "script_edit_needed": VocabSpec(
        name="script_edit_needed",
        family="mutate",
        target_surface="script",
        scope_profile="micro",
        topology_prior="linear",
        ref_posture="strict_hash",
        postcondition_mode="hash_resolve",
        protection_mode="protected_reroute",
        class_code="m",
    ),
    "command_needed": VocabSpec(
        name="command_needed",
        family="mutate",
        target_surface="workspace",
        scope_profile="open",
        topology_prior="open_branch",
        ref_posture="optional",
        postcondition_mode="workspace_commit_observe",
        protection_mode="protected_reroute",
        class_code="m",
    ),
    "email_needed": VocabSpec(
        name="email_needed",
        family="mutate",
        target_surface="outbound_mail",
        scope_profile="bounded",
        topology_prior="linear",
        ref_posture="optional",
        postcondition_mode="mailbox_observe",
        protection_mode="medium",
        class_code="m",
    ),
    "json_patch_needed": VocabSpec(
        name="json_patch_needed",
        family="mutate",
        target_surface="structured_blob",
        scope_profile="micro",
        topology_prior="linear",
        ref_posture="strict_hash",
        postcondition_mode="hash_resolve",
        protection_mode="protected_reroute",
        class_code="m",
    ),
    "git_revert_needed": VocabSpec(
        name="git_revert_needed",
        family="mutate",
        target_surface="commit",
        scope_profile="micro",
        topology_prior="terminal_linear",
        ref_posture="strict_commit_hash",
        postcondition_mode="none",
        protection_mode="high",
        class_code="m",
    ),
    "reason_needed": VocabSpec(
        name="reason_needed",
        family="bridge",
        target_surface="semantic_trees",
        scope_profile="open",
        topology_prior="open_structure",
        ref_posture="optional",
        postcondition_mode="structural_activation",
        protection_mode="structural",
        class_code="b",
    ),
    "await_needed": VocabSpec(
        name="await_needed",
        family="bridge",
        target_surface="parent_child_sync",
        scope_profile="bounded",
        topology_prior="checkpoint",
        ref_posture="background_refs",
        postcondition_mode="review_reintegration",
        protection_mode="structural",
        class_code="b",
    ),
    "commit_needed": VocabSpec(
        name="commit_needed",
        family="bridge",
        target_surface="child_trajectory",
        scope_profile="bounded",
        topology_prior="terminal_closure",
        ref_posture="implicit_chain",
        postcondition_mode="semantic_reintegration",
        protection_mode="structural",
        class_code="b",
    ),
    "reprogramme_needed": VocabSpec(
        name="reprogramme_needed",
        family="bridge",
        target_surface="semantic_state",
        scope_profile="bounded",
        topology_prior="semantic_maintenance",
        ref_posture="optional",
        postcondition_mode="persistence_outcome",
        protection_mode="semantic",
        class_code="b",
    ),
    "clarify_needed": VocabSpec(
        name="clarify_needed",
        family="bridge",
        target_surface="user_boundary",
        scope_profile="cross_turn_open",
        topology_prior="suspend_resume",
        ref_posture="optional",
        postcondition_mode="user_reply",
        protection_mode="temporal",
        class_code="c",
    ),
}


OBSERVE_VOCAB = {name for name, spec in VOCAB_SPECS.items() if spec.family == "observe"}
MUTATE_VOCAB = {name for name, spec in VOCAB_SPECS.items() if spec.family == "mutate"}
BRIDGE_VOCAB = {name for name, spec in VOCAB_SPECS.items() if spec.family == "bridge"}
RUNTIME_VOCAB = set(VOCAB_SPECS)


def is_observe(vocab: str | None) -> bool:
    return vocab in OBSERVE_VOCAB


def is_mutate(vocab: str | None) -> bool:
    return vocab in MUTATE_VOCAB


def is_bridge(vocab: str | None) -> bool:
    return vocab in BRIDGE_VOCAB


def vocab_family(vocab: str | None) -> str:
    if vocab is None:
        return "unknown"
    spec = VOCAB_SPECS.get(vocab)
    return spec.family if spec else "unknown"


def vocab_class_code(vocab: str | None) -> str:
    if not vocab:
        return "_"
    spec = VOCAB_SPECS.get(vocab)
    return spec.class_code if spec else "_"


def pre_diff_vocab_guide() -> str:
    """Prompt-facing runtime vocab guide for the main agent."""
    return """Each gap maps to a vocab term that tells the kernel HOW to resolve it:

OBSERVE (kernel resolves, you receive data):
  pattern_needed — search file contents by pattern
  hash_resolve_needed — resolve step/gap/blob hashes from trajectory
  mailbox_needed — check mailbox/inbox state
  external_context — surface from current context
  research_needed — activate the controlled research workflow
  (workspace files visible via HEAD commit tree. URL fetch/search remain package-scoped workflow vocab, not standalone kernel vocab.)

MUTATE (you compose a command, kernel executes):
  hash_edit_needed — edit any file (universal: read by hash → compose edit → execute via hash_manifest)
  stitch_needed — generate UI via Google Stitch (prompt → HTML + Tailwind CSS)
  content_needed — write a new file
  script_edit_needed — edit an existing file
  command_needed — execute a shell command
  email_needed — send an email/message
  json_patch_needed — surgical JSON edit
  git_revert_needed — git revert/checkout

CLARIFY BRIDGE:
  clarify_needed — cross-turn clarification bridge. Use this when:
    - The user's intent is ambiguous and you'd be guessing
    - Multiple interpretations exist and the wrong one wastes effort
    - You need a specific piece of information only the user has
    The desc field becomes your question. This halts the iteration loop.
    The gap persists on the trajectory and resumes when the user replies.
"""
