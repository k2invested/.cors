"""Structural principle suite for cors.

This replaces the old print-driven script with a real pytest suite.
The goal is broad coverage of the mechanisms described in PRINCIPLES.md:
hash layers, gap admission, vocab routing, chain lifecycle, codons,
temporal rendering, and supporting infrastructure.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import compile as compile_module
import discord_bot as discord_bot_module
import execution_engine as execution_engine_module
import loop
import manifest_engine as manifest_engine_module
import action_foundations as action_foundations_module
import step as step_module
import vocab_registry as vocab_registry_module
from compile import (
    ADMISSION_THRESHOLD,
    BRIDGE_VOCAB,
    CHAIN_EXTRACT_LENGTH,
    CONFIDENCE_THRESHOLD,
    CROSS_TURN_THRESHOLD,
    DORMANT_PROMOTE_THRESHOLD,
    DORMANT_THRESHOLD,
    MAX_CHAIN_DEPTH,
    MUTATE_VOCAB,
    OBSERVE_VOCAB,
    SATURATION_THRESHOLD,
    STAGNATION_WINDOW,
    ChainState,
    Compiler,
    GovernorSignal,
    GovernorState,
    Ledger,
    LedgerEntry,
    govern,
    is_bridge,
    is_mutate,
    is_observe,
    vocab_priority,
)
from skills.loader import Skill, SkillRegistry, SkillStep, load_all, load_skill
from step import Chain, Epistemic, Gap, RelationNote, Step, StepNote, Trajectory, absolute_time, blob_hash, chain_hash, relative_time
from system import chain_registry as chain_registry_module
from system import control_surface as control_surface_module
from system import hash_registry as hash_registry_module
from tools import hash_manifest as hash_manifest_module
from tools.hash import office_manifest as office_manifest_module
from tools import st_builder as st_builder_module
from system import tool_builder as tool_builder_module
from system import tool_contract as tool_contract_module
from system import tool_registry as tool_registry_module
from system import vocab_builder as vocab_builder_module

SKILLS_DIR = ROOT / "skills"
TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")


def make_gap(
    desc: str = "gap",
    *,
    content_refs: list[str] | None = None,
    step_refs: list[str] | None = None,
    relevance: float = 0.5,
    confidence: float = 0.5,
    grounded: float = 0.0,
    vocab: str | None = None,
    turn_id: int | None = None,
    resolved: bool = False,
    dormant: bool = False,
) -> Gap:
    gap = Gap.create(desc, content_refs=content_refs or [], step_refs=step_refs or [])
    gap.scores = Epistemic(relevance, confidence, grounded)
    gap.vocab = vocab
    gap.vocab_score = 0.9 if vocab else 0.0
    gap.turn_id = turn_id
    gap.resolved = resolved
    gap.dormant = dormant
    return gap


def make_step(
    desc: str = "step",
    *,
    step_refs: list[str] | None = None,
    content_refs: list[str] | None = None,
    gaps: list[Gap] | None = None,
    commit: str | None = None,
    chain_id: str | None = None,
    parent: str | None = None,
) -> Step:
    return Step.create(
        desc=desc,
        step_refs=step_refs or [],
        content_refs=content_refs or [],
        gaps=gaps or [],
        commit=commit,
        chain_id=chain_id,
        parent=parent,
    )


@lru_cache(maxsize=1)
def registry() -> SkillRegistry:
    return load_all(str(SKILLS_DIR))


@lru_cache(maxsize=1)
def skill_data(name: str) -> dict:
    skill = registry().resolve_by_name(name)
    assert skill is not None, f"missing skill: {name}"
    return json.loads(Path(skill.source).read_text())


def skill(name: str) -> Skill:
    resolved = registry().resolve_by_name(name)
    assert resolved is not None, f"missing skill: {name}"
    return resolved


def bootstrap_identity_skill(contact_id: str = "discord:123", user_message: str = "hi", username: str = "courtney") -> Skill:
    intent = loop._build_init_user_intent(contact_id, user_message, contact_profile={"username": username})
    return Skill(
        hash="boot_hash",
        name=intent["name"],
        desc=intent["desc"],
        steps=[SkillStep(**step) for step in intent["steps"]],
        source=str(SKILLS_DIR / "entities" / f"{intent['name']}.st"),
        display_name=intent["name"],
        trigger=intent["trigger"],
        artifact_kind="entity",
        payload=intent,
    )


def render_bootstrap_identity(contact_id: str = "discord:123", user_message: str = "hi", username: str = "courtney") -> str:
    intent = loop._build_init_user_intent(contact_id, user_message, contact_profile={"username": username})
    with tempfile.NamedTemporaryFile("w", suffix=".st", delete=False) as tmp:
        json.dump(intent, tmp)
        tmp_path = Path(tmp.name)
    try:
        skill_obj = Skill(
            hash="boot_hash",
            name=intent["name"],
            desc=intent["desc"],
            steps=[SkillStep(**step) for step in intent["steps"]],
            source=str(tmp_path),
            display_name=intent["name"],
            trigger=intent["trigger"],
            artifact_kind="entity",
            payload=intent,
        )
        return loop._render_identity(skill_obj)
    finally:
        tmp_path.unlink(missing_ok=True)


def seed_trajectory(*refs: str, count: int = 3) -> Trajectory:
    traj = Trajectory()
    for i in range(count):
        traj.append(make_step(f"seed-{i}", content_refs=list(refs)))
    return traj


def build_origin_context(
    *,
    vocab: str = "pattern_needed",
    relevance: float = 0.8,
    confidence: float = 0.7,
    refs: list[str] | None = None,
    current_turn: int = 0,
    gap_turn_id: int | None = None,
    dormant: bool = False,
    seed_count: int = 3,
) -> SimpleNamespace:
    refs = ["blob_alpha"] if refs is None else refs
    traj = seed_trajectory(*refs, count=seed_count) if refs else Trajectory()
    compiler = Compiler(traj, current_turn=current_turn)
    gap = make_gap(
        "origin gap",
        content_refs=refs,
        relevance=relevance,
        confidence=confidence,
        vocab=vocab,
        turn_id=gap_turn_id,
        dormant=dormant,
    )
    step = make_step("origin step", content_refs=refs, gaps=[gap])
    traj.append(step)
    compiler.emit_origin_gaps(step)
    return SimpleNamespace(traj=traj, compiler=compiler, gap=gap, step=step)


def build_chain_context() -> SimpleNamespace:
    traj = Trajectory()
    origin_gap = make_gap(
        "inspect config",
        content_refs=[skill("admin").hash, "blob_cfg"],
        step_refs=["prior_step"],
        relevance=0.9,
        confidence=0.7,
        vocab="pattern_needed",
    )
    step1 = make_step("observed workspace", content_refs=[skill("admin").hash], gaps=[origin_gap])
    traj.append(step1)
    chain = Chain.create(origin_gap.hash, step1.hash)
    traj.add_chain(chain)
    step2 = make_step(
        "updated config",
        step_refs=[step1.hash],
        content_refs=["blob_cfg"],
        commit="abc123",
    )
    traj.append(step2)
    chain.add_step(step2.hash)
    chain.desc = "resolved config"
    chain.resolved = True
    return SimpleNamespace(traj=traj, chain=chain, step1=step1, step2=step2, gap=origin_gap)


def serialized_chain_files(tmp_path: Path) -> tuple[dict, dict]:
    chain_hash = "chain12345678"
    step_hash = "step12345678"
    chain_doc = {
        "hash": chain_hash,
        "origin_gap": "gap123456789",
        "steps": [step_hash],
        "desc": "curated workflow",
        "resolved": True,
    }
    traj_doc = [
        {
            "hash": step_hash,
            "step_refs": [],
            "content_refs": ["admin_hash"],
            "desc": "observe target file",
            "gaps": [
                {
                    "hash": "gap111111111",
                    "desc": "need to resolve target",
                    "content_refs": ["admin_hash"],
                    "step_refs": [],
                    "scores": {"relevance": 1.0, "confidence": 0.8, "grounded": 0.6},
                    "vocab": "hash_resolve_needed",
                    "vocab_score": 0.9,
                }
            ],
            "t": time.time(),
        }
    ]
    (tmp_path / "chains.json").write_text(json.dumps([chain_doc], indent=2))
    (tmp_path / "trajectory.json").write_text(json.dumps(traj_doc, indent=2))
    return chain_doc, traj_doc[0]


P1_CASES = [
    ("blob_hash_deterministic", lambda: blob_hash("alpha") == blob_hash("alpha")),
    ("blob_hash_changes_with_content", lambda: blob_hash("alpha") != blob_hash("beta")),
    ("chain_hash_deterministic", lambda: chain_hash(["a", "b"]) == chain_hash(["a", "b"])),
    ("chain_hash_order_sensitive", lambda: chain_hash(["a", "b"]) != chain_hash(["b", "a"])),
    ("step_hash_length", lambda: len(make_step("demo").hash) == 12),
    ("gap_hash_length", lambda: len(make_gap("demo").hash) == 12),
    ("step_timestamp_set", lambda: make_step("timed").t > 0),
    ("gap_content_refs_preserved", lambda: make_gap("g", content_refs=["blob_a"]).content_refs == ["blob_a"]),
    ("gap_step_refs_preserved", lambda: make_gap("g", step_refs=["step_a"]).step_refs == ["step_a"]),
    ("step_content_refs_preserved", lambda: make_step("s", content_refs=["blob_a"]).content_refs == ["blob_a"]),
    ("step_step_refs_preserved", lambda: make_step("s", step_refs=["step_a"]).step_refs == ["step_a"]),
    ("observation_detected", lambda: make_step("obs").is_observation()),
    ("mutation_detected", lambda: make_step("mut", commit="abc123").is_mutation()),
    ("active_gaps_exclude_dormant_and_resolved", lambda: len(make_step("x", gaps=[
        make_gap("active"),
        make_gap("dormant", dormant=True),
        make_gap("resolved", resolved=True),
    ]).active_gaps()) == 1),
    ("dormant_gaps_only_dormant", lambda: len(make_step("x", gaps=[
        make_gap("active"),
        make_gap("dormant", dormant=True),
    ]).dormant_gaps()) == 1),
    ("all_refs_include_step_and_content_and_gap_refs", lambda: set(make_step(
        "refs",
        step_refs=["step_parent"],
        content_refs=["blob_parent"],
        gaps=[make_gap("child", step_refs=["step_child"], content_refs=["blob_child"])],
    ).all_refs()) == {"step_parent", "blob_parent", "step_child", "blob_child"}),
    ("step_roundtrip_desc", lambda: Step.from_dict(make_step("roundtrip").to_dict()).desc == "roundtrip"),
    ("step_roundtrip_commit", lambda: Step.from_dict(make_step("roundtrip", commit="abc").to_dict()).commit == "abc"),
    ("step_roundtrip_note_summary", lambda: (
        lambda restored: restored.note is not None and restored.note.summary == "roundtrip"
    )(Step.from_dict(make_step("roundtrip").to_dict()))),
    ("step_preserves_explicit_note_relations", lambda: (
        lambda restored: restored.note is not None and restored.note.relations[0].type == "conflicts"
    )(
        Step.from_dict(
            Step.create(
                "explicit note",
                note=StepNote(
                    summary="compare docs to runtime",
                    relations=[RelationNote(type="conflicts", from_ref="docs", to_ref="runtime", note="priority mismatch")],
                ),
            ).to_dict()
        )
    )),
    ("step_roundtrip_rogue", lambda: (lambda restored: restored.rogue and restored.rogue_kind == "policy_violation")(
        Step.from_dict(Step.create("rogue", rogue=True, rogue_kind="policy_violation", failure_source="tree_policy").to_dict())
    )),
    ("chain_hash_stable_on_add", lambda: (lambda c: (lambda initial: (c.add_step("b"), c.hash == initial)[1])(c.hash))(Chain.create("gap", "a"))),
    ("chain_signature_updates_on_add", lambda: (lambda c: (lambda initial: (c.add_step("b"), c.signature != initial)[1])(c.signature))(Chain.create("gap", "a"))),
    ("trajectory_resolves_step_and_gap", lambda: (lambda t, s, g: t.resolve(s.hash) == s and t.resolve_gap(g.hash) == g)(
        *(lambda gap: (lambda step, traj: (traj.append(step), traj, step, gap)[1:])(make_step("origin", gaps=[gap]), Trajectory()))(make_gap("g"))
    )),
]

P1_CASES += [
    ("step_hash_changes_with_desc", lambda: make_step("alpha").hash != make_step("beta").hash),
    ("step_hash_changes_with_content_refs", lambda: make_step("alpha", content_refs=["blob_a"]).hash != make_step("alpha", content_refs=["blob_b"]).hash),
    ("step_hash_changes_with_step_refs", lambda: make_step("alpha", step_refs=["step_a"]).hash != make_step("alpha", step_refs=["step_b"]).hash),
    ("gap_hash_changes_with_step_refs", lambda: make_gap("alpha", step_refs=["step_a"]).hash != make_gap("alpha", step_refs=["step_b"]).hash),
    ("gap_hash_changes_with_content_ref_order", lambda: make_gap("alpha", content_refs=["a", "b"]).hash != make_gap("alpha", content_refs=["b", "a"]).hash),
    ("chain_initial_length_one", lambda: Chain.create("gap", "step_a").length() == 1),
    ("chain_add_step_increments_length", lambda: (lambda c: (c.add_step("step_b"), c.length())[1] == 2)(Chain.create("gap", "step_a"))),
    ("trajectory_append_preserves_order", lambda: (lambda traj, s1, s2: (traj.append(s1), traj.append(s2), traj.order == [s1.hash, s2.hash])[2])(Trajectory(), make_step("one"), make_step("two"))),
    ("step_roundtrip_assessment", lambda: Step.from_dict(make_step("assessed", commit="abc123", gaps=[], chain_id="c1", parent="p1").to_dict()).chain_id == "c1"),
]


P2_CASES = [
    ("fresh_gap_admitted", lambda: build_origin_context().compiler.gap_count() == 1),
    ("weak_gap_becomes_dormant", lambda: build_origin_context(relevance=0.1, confidence=0.1).gap.dormant),
    ("weak_gap_not_on_ledger", lambda: build_origin_context(relevance=0.1, confidence=0.1).compiler.gap_count() == 0),
    ("cross_turn_gap_needs_higher_bar", lambda: build_origin_context(relevance=0.5, confidence=0.6, current_turn=2, gap_turn_id=1, seed_count=0).compiler.gap_count() == 0),
    ("cross_turn_gap_can_reenter", lambda: build_origin_context(relevance=0.8, confidence=0.6, current_turn=2, gap_turn_id=1).compiler.gap_count() == 1),
    ("dormant_promotion_uses_strongest_threshold", lambda: build_origin_context(relevance=0.6, confidence=0.6, dormant=True, seed_count=0).compiler.gap_count() == 0),
    ("emit_origin_creates_chain", lambda: len(build_origin_context().traj.chains) == 1),
    ("origin_chain_tracks_gap_hash", lambda: next(iter(build_origin_context().traj.chains.values())).origin_gap == build_origin_context().gap.hash),
    ("origin_observe_pops_before_mutate", lambda: (lambda ctx: ctx.compiler.ledger.peek().gap.vocab == "pattern_needed")(
        (lambda traj, comp, step: (traj.append(step), comp.emit_origin_gaps(step), SimpleNamespace(traj=traj, compiler=comp))[2])(
            Trajectory(),
            Compiler(Trajectory()),
            make_step("origin", gaps=[
                make_gap("mutate", vocab="content_needed", content_refs=["blob_a"], relevance=0.8, confidence=0.8),
                make_gap("observe", vocab="pattern_needed", content_refs=["blob_a"], relevance=0.8, confidence=0.8),
            ]),
        )
    )),
    ("reprogramme_sits_at_bottom", lambda: (lambda comp, step: (
        comp.emit_origin_gaps(step),
        comp.ledger.stack[0].gap.vocab == "reprogramme_needed",
    )[1])(
        Compiler(Trajectory()),
        make_step("origin", gaps=[
            make_gap("observe", vocab="pattern_needed", content_refs=["blob_a"], relevance=0.8, confidence=0.8),
            make_gap("persist", vocab="reprogramme_needed", content_refs=["blob_a"], relevance=0.8, confidence=0.8),
        ]),
    )),
    ("child_gap_pushes_depth_first", lambda: (lambda ctx: (
        setattr(ctx.compiler, "active_chain", next(iter(ctx.traj.chains.values()))),
        ctx.compiler.emit(make_step("child step", gaps=[
            make_gap("child", vocab="pattern_needed", content_refs=["blob_alpha"], relevance=0.8, confidence=0.7)
        ])),
        ctx.compiler.ledger.peek().depth == ctx.compiler.active_chain.length(),
    )[2])(build_origin_context())),
    ("child_gap_keeps_chain_id", lambda: (lambda ctx: (
        setattr(ctx.compiler, "active_chain", next(iter(ctx.traj.chains.values()))),
        ctx.compiler.emit(make_step("child step", gaps=[
            make_gap("child", vocab="pattern_needed", content_refs=["blob_alpha"], relevance=0.8, confidence=0.7)
        ])),
        ctx.compiler.ledger.peek().chain_id == ctx.compiler.active_chain.hash,
    )[2])(build_origin_context())),
    ("grounded_uses_cooccurrence", lambda: Compiler(seed_trajectory("blob_a"))._compute_grounded(make_gap("g", content_refs=["blob_a"])) > 0),
    ("grounded_zero_without_refs", lambda: Compiler(Trajectory())._compute_grounded(make_gap("g")) == 0.0),
    ("readmit_cross_turn_returns_zero_when_dropped", lambda: (lambda comp, gap: comp.readmit_cross_turn([gap], "origin") == 0)(
        Compiler(Trajectory(), current_turn=2),
        make_gap("weak", relevance=0.2, confidence=0.2, vocab="pattern_needed", turn_id=1),
    )),
    ("readmit_cross_turn_returns_one_when_admitted", lambda: (lambda comp, gap: comp.readmit_cross_turn([gap], "origin") == 1)(
        Compiler(seed_trajectory("blob_a"), current_turn=2),
        make_gap("strong", relevance=0.9, confidence=0.7, vocab="pattern_needed", content_refs=["blob_a"], turn_id=1),
    )),
    ("ledger_size_tracks_admitted_gap", lambda: build_origin_context().compiler.ledger.size() == 1),
    ("empty_ledger_halts", lambda: Compiler(Trajectory()).next()[1] == GovernorSignal.HALT),
    ("next_pops_entry", lambda: build_origin_context().compiler.next()[0] is not None),
    ("chain_summary_reports_origin", lambda: build_origin_context().compiler.chain_summary()[0]["origin"] == build_origin_context().gap.hash),
]

P2_CASES += [
    ("origin_gap_is_indexed_on_append", lambda: (lambda ctx: ctx.traj.resolve_gap(ctx.gap.hash) == ctx.gap)(build_origin_context())),
    ("dormant_gap_is_still_indexed", lambda: (lambda ctx: ctx.traj.resolve_gap(ctx.gap.hash) == ctx.gap and ctx.gap.dormant)(build_origin_context(relevance=0.1, confidence=0.1))),
    ("emit_child_increases_ledger_size", lambda: (lambda ctx: (
        setattr(ctx.compiler, "active_chain", next(iter(ctx.traj.chains.values()))),
        ctx.compiler.emit(make_step("child", gaps=[make_gap("child", vocab="pattern_needed", content_refs=["blob_alpha"], relevance=0.9, confidence=0.7)])),
        ctx.compiler.ledger.size() == 2,
    )[2])(build_origin_context())),
    ("resolve_current_gap_marks_gap_resolved", lambda: (lambda ctx: (ctx.compiler.resolve_current_gap(ctx.gap.hash), ctx.gap.resolved)[1])(build_origin_context())),
    ("resolve_current_gap_closes_empty_chain", lambda: (lambda ctx: (
        (lambda chain_hash: (ctx.compiler.next(), ctx.compiler.resolve_current_gap(ctx.gap.hash), ctx.compiler.ledger.chain_states[chain_hash] == ChainState.CLOSED)[2])(next(iter(ctx.traj.chains)))
    ))(build_origin_context())),
    ("readmit_cross_turn_preserves_gap_hash", lambda: (lambda comp, gap: (comp.readmit_cross_turn([gap], "origin"), comp.ledger.peek().gap.hash == gap.hash)[1])(Compiler(seed_trajectory("blob_a"), current_turn=2), make_gap("carry", relevance=0.9, confidence=0.7, vocab="pattern_needed", content_refs=["blob_a"], turn_id=1))),
    ("readmit_cross_turn_creates_one_new_entry", lambda: (lambda comp, gap: (comp.readmit_cross_turn([gap], "origin"), comp.ledger.size() == 1)[1])(Compiler(seed_trajectory("blob_a"), current_turn=2), make_gap("carry", relevance=0.9, confidence=0.7, vocab="pattern_needed", content_refs=["blob_a"], turn_id=1))),
    ("emit_origin_multiple_gaps_create_multiple_chains", lambda: (lambda traj, step: (lambda comp: (traj.append(step), comp.emit_origin_gaps(step), len(traj.chains) == 2)[2])(Compiler(traj)))(Trajectory(), make_step("origin", gaps=[make_gap("a", vocab="pattern_needed", content_refs=["blob_a"], relevance=0.8, confidence=0.8), make_gap("b", vocab="mailbox_needed", content_refs=["blob_b"], relevance=0.8, confidence=0.8)]))),
    ("ledger_pop_reduces_stack", lambda: (lambda ctx: (ctx.compiler.ledger.pop(), ctx.compiler.ledger.size() == 0)[1])(build_origin_context())),
    ("same_turn_gap_uses_fresh_threshold", lambda: build_origin_context(relevance=0.5, confidence=0.6, current_turn=2, gap_turn_id=2, refs=[]).compiler.gap_count() == 1),
]


P3_CASES = [
    ("observe_pattern_needed", lambda: is_observe("pattern_needed")),
    ("observe_hash_resolve_needed", lambda: is_observe("hash_resolve_needed")),
    ("observe_mailbox_needed", lambda: is_observe("mailbox_needed")),
    ("observe_external_context", lambda: is_observe("external_context")),
    ("bridge_clarify_needed", lambda: is_bridge("clarify_needed")),
    ("mutate_hash_edit_needed", lambda: is_mutate("hash_edit_needed")),
    ("mutate_stitch_needed", lambda: is_mutate("stitch_needed")),
    ("mutate_content_needed", lambda: is_mutate("content_needed")),
    ("bridge_tool_needed", lambda: is_bridge("tool_needed")),
    ("bridge_vocab_reg_needed", lambda: is_bridge("vocab_reg_needed")),
    ("mutate_bash_needed", lambda: is_mutate("bash_needed")),
    ("mutate_email_needed", lambda: is_mutate("email_needed")),
    ("mutate_json_patch_needed", lambda: is_mutate("json_patch_needed")),
    ("mutate_git_revert_needed", lambda: is_mutate("git_revert_needed")),
    ("step_render_classifies_stitch_as_mutate", lambda: step_module.vocab_class("stitch_needed") == "m"),
    ("step_render_classifies_email_as_mutate", lambda: step_module.vocab_class("email_needed") == "m"),
    ("step_render_unknown_trigger_term_is_unknown", lambda: step_module.vocab_class("research_needed") == "_"),
    ("bridge_reason_needed", lambda: is_bridge("reason_needed")),
    ("bridge_await_needed", lambda: is_bridge("await_needed")),
    ("bridge_reprogramme_needed", lambda: is_bridge("reprogramme_needed")),
    ("deterministic_vocab_is_hash_resolve", lambda: loop.DETERMINISTIC_VOCAB == {"hash_resolve_needed"}),
    ("observation_only_contains_external_context", lambda: "external_context" in loop.OBSERVATION_ONLY_VOCAB),
    ("compile_observe_vocab_matches_registry", lambda: compile_module.OBSERVE_VOCAB == vocab_registry_module.OBSERVE_VOCAB),
    ("compile_mutate_vocab_matches_registry", lambda: compile_module.MUTATE_VOCAB == vocab_registry_module.MUTATE_VOCAB),
    ("compile_bridge_vocab_matches_registry", lambda: compile_module.BRIDGE_VOCAB == vocab_registry_module.BRIDGE_VOCAB),
    ("loop_tool_map_matches_registry", lambda: loop.TOOL_MAP == vocab_registry_module.TOOL_MAP),
    ("loop_observation_only_matches_registry", lambda: loop.OBSERVATION_ONLY_VOCAB == vocab_registry_module.OBSERVATION_ONLY_VOCAB),
    ("loop_deterministic_matches_registry", lambda: loop.DETERMINISTIC_VOCAB == vocab_registry_module.DETERMINISTIC_VOCAB),
    ("tool_map_hash_edit_routes_hash_manifest", lambda: loop.TOOL_MAP["hash_edit_needed"]["tool"] == "tools/hash_manifest.py"),
    ("tool_needed_not_in_mutate_tool_map", lambda: "tool_needed" not in loop.TOOL_MAP),
    ("vocab_reg_needed_not_in_mutate_tool_map", lambda: "vocab_reg_needed" not in loop.TOOL_MAP),
    ("tool_map_stitch_has_post_observe", lambda: loop.TOOL_MAP["stitch_needed"]["post_observe"] == "ui_output/"),
    ("tool_map_bash_has_log_post_observe", lambda: loop.TOOL_MAP["bash_needed"]["post_observe"] == "bot.log"),
    ("priority_observe_before_reason", lambda: vocab_priority("pattern_needed") < vocab_priority("reason_needed")),
    ("priority_reason_before_mutate", lambda: vocab_priority("reason_needed") < vocab_priority("content_needed")),
    ("priority_clarify_before_mutate", lambda: vocab_priority("clarify_needed") < vocab_priority("content_needed")),
    ("priority_reason_before_await", lambda: vocab_priority("reason_needed") < vocab_priority("await_needed")),
    ("priority_tool_before_await", lambda: vocab_priority("tool_needed") < vocab_priority("await_needed")),
    ("priority_vocab_reg_before_await", lambda: vocab_priority("vocab_reg_needed") < vocab_priority("await_needed")),
    ("priority_await_before_reprogramme", lambda: vocab_priority("await_needed") < vocab_priority("reprogramme_needed")),
    ("pre_diff_prompt_centers_semantic_tree_reasoning", lambda: "Think in semantic trees, not flat chat turns." in loop.PRE_DIFF_SYSTEM),
    ("pre_diff_prompt_treats_tree_as_historical_progress", lambda: "Treat the semantic tree as your own historical progress while processing the user's message." in loop.PRE_DIFF_SYSTEM),
    ("pre_diff_prompt_explains_resolved_path_pending_and_child_chains", lambda: "resolved path = what is already known or done" in loop.PRE_DIFF_SYSTEM and "child chains = active delegated or embedded work" in loop.PRE_DIFF_SYSTEM),
    ("pre_diff_prompt_says_environment_is_built_from_semantic_surfaces", lambda: "You are shaping an environment made of semantic and executable surfaces." in loop.PRE_DIFF_SYSTEM),
    ("pre_diff_prompt_treats_tree_policy_as_runtime_enforcement", lambda: "The compiler and tree policy enforce the final route." in loop.PRE_DIFF_SYSTEM),
    ("tree_policy_skills_reroutes_reprogramme", lambda: loop._match_policy("skills/admin.st", loop._load_tree_policy())["on_mutate"] == "reprogramme_needed"),
    ("tree_policy_admin_sets_entity_editor_mode", lambda: loop._match_policy("skills/admin.st", loop._load_tree_policy())["reprogramme_mode"] == "entity_editor"),
    ("tree_policy_entities_reroutes_reprogramme", lambda: loop._match_policy("skills/entities/clinton.st", loop._load_tree_policy())["on_mutate"] == "reprogramme_needed"),
    ("tree_policy_entities_set_entity_editor_mode", lambda: loop._match_policy("skills/entities/clinton.st", loop._load_tree_policy())["reprogramme_mode"] == "entity_editor"),
    ("tree_policy_actions_reroute_to_reason", lambda: loop._match_policy("skills/actions/hash_edit.st", loop._load_tree_policy())["on_mutate"] == "reason_needed"),
    ("tree_policy_actions_set_action_editor_mode", lambda: loop._match_policy("skills/actions/hash_edit.st", loop._load_tree_policy())["reprogramme_mode"] == "action_editor"),
    ("tree_policy_system_is_immutable", lambda: loop._match_policy("system/tool_registry.py", loop._load_tree_policy())["immutable"] is True),
    ("tree_policy_vocab_registry_routes_to_vocab_reg_needed", lambda: loop._match_policy("vocab_registry.py", loop._load_tree_policy())["on_mutate"] == "vocab_reg_needed"),
    ("tree_policy_exact_match_compile_immutable", lambda: loop._match_policy("compile.py", loop._load_tree_policy())["immutable"] is True),
    ("tree_policy_longest_prefix_wins", lambda: loop._match_policy("skills/codons/trigger.st", loop._load_tree_policy())["on_reject"] == "reason_needed"),
    ("tree_policy_vocab_targets_are_valid", lambda: vocab_registry_module.validate_tree_policy_targets(loop._load_tree_policy()) == []),
]


P4_CASES = [
    ("gap_axis_desc", lambda: hasattr(make_gap("x"), "desc")),
    ("gap_axis_content_refs", lambda: hasattr(make_gap("x"), "content_refs")),
    ("gap_axis_step_refs", lambda: hasattr(make_gap("x"), "step_refs")),
    ("gap_axis_vocab", lambda: hasattr(make_gap("x"), "vocab")),
    ("gap_axis_relevance", lambda: hasattr(make_gap("x").scores, "relevance")),
    ("gap_axis_confidence", lambda: hasattr(make_gap("x").scores, "confidence")),
    ("gap_axis_grounded", lambda: hasattr(make_gap("x").scores, "grounded")),
    ("admission_score_overwrites_grounded", lambda: (lambda comp, gap: (comp._admission_score(gap), gap.scores.grounded > 0)[1])(
        Compiler(seed_trajectory("blob_a")), make_gap("g", relevance=0.9, grounded=1.0, content_refs=["blob_a"])
    )),
    ("admission_formula_matches_weights", lambda: (lambda comp, gap: round(comp._admission_score(gap), 2) == round(0.8 * 0.5 + 0.2 * gap.scores.grounded, 2))(
        Compiler(seed_trajectory("blob_a")), make_gap("g", relevance=0.5, content_refs=["blob_a"])
    )),
    ("fresh_threshold_constant", lambda: ADMISSION_THRESHOLD == 0.4),
    ("cross_turn_threshold_constant", lambda: CROSS_TURN_THRESHOLD == 0.6),
    ("dormant_promotion_threshold_constant", lambda: DORMANT_PROMOTE_THRESHOLD == 0.7),
    ("dormant_threshold_constant", lambda: DORMANT_THRESHOLD == 0.2),
    ("confidence_threshold_constant", lambda: CONFIDENCE_THRESHOLD == 0.8),
    ("unsourced_gap_can_admit_if_relevant", lambda: build_origin_context(relevance=0.6, refs=[]).compiler.gap_count() == 1),
    ("unsourced_gap_drops_if_not_relevant_enough", lambda: build_origin_context(relevance=0.4, refs=[]).compiler.gap_count() == 0),
    ("gap_hash_changes_with_desc", lambda: make_gap("a").hash != make_gap("b").hash),
    ("gap_hash_changes_with_refs", lambda: make_gap("a", content_refs=["x"]).hash != make_gap("a", content_refs=["y"]).hash),
    ("gap_to_dict_carries_vocab", lambda: make_gap("a", vocab="pattern_needed").to_dict()["vocab"] == "pattern_needed"),
    ("gap_to_dict_carries_carry_forward", lambda: (lambda g: (setattr(g, "carry_forward", True), g.to_dict()["carry_forward"])[1])(make_gap("a"))),
    ("gap_to_dict_carries_status_flags", lambda: (lambda d: d["resolved"] and d["dormant"])(
        make_gap("a", resolved=True, dormant=True).to_dict()
    )),
    ("step_from_dict_preserves_scores", lambda: (lambda restored: restored.gaps[0].scores.relevance == 0.7 and restored.gaps[0].scores.confidence == 0.6)(
        Step.from_dict(make_step("s", gaps=[make_gap("g", relevance=0.7, confidence=0.6)]).to_dict())
    )),
]

P4_CASES += [
    ("gap_axis_turn_id", lambda: hasattr(make_gap("x"), "turn_id")),
    ("gap_axis_carry_forward", lambda: hasattr(make_gap("x"), "carry_forward")),
    ("gap_axis_route_mode", lambda: hasattr(make_gap("x"), "route_mode")),
    ("gap_to_dict_carries_turn_id", lambda: (lambda g: (setattr(g, "turn_id", 4), g.to_dict()["turn_id"] == 4))(make_gap("a"))),
    ("gap_roundtrip_preserves_turn_id", lambda: (lambda restored: restored.gaps[0].turn_id == 7)(
        Step.from_dict(make_step("s", gaps=[(lambda g: (setattr(g, "turn_id", 7), g)[1])(make_gap("g"))]).to_dict())
    )),
    ("gap_roundtrip_preserves_carry_forward", lambda: (lambda restored: restored.gaps[0].carry_forward is True)(
        Step.from_dict(make_step("s", gaps=[(lambda g: (setattr(g, "carry_forward", True), g)[1])(make_gap("g"))]).to_dict())
    )),
    ("gap_roundtrip_preserves_route_mode", lambda: (lambda restored: restored.gaps[0].route_mode == "entity_editor")(
        Step.from_dict(make_step("s", gaps=[(lambda g: (setattr(g, "route_mode", "entity_editor"), g)[1])(make_gap("g"))]).to_dict())
    )),
    ("gap_roundtrip_preserves_vocab_score", lambda: (lambda restored: restored.gaps[0].vocab_score == 0.9)(
        Step.from_dict(make_step("s", gaps=[make_gap("g", vocab="pattern_needed")]).to_dict())
    )),
]


P5_CASES = [
    ("registry_loads_admin", lambda: registry().resolve_by_name("admin") is not None),
    ("registry_loads_hash_edit", lambda: registry().resolve_by_name("hash_edit") is not None),
    ("registry_treats_chain_spec_as_entity", lambda: skill("commitment_chain_construction_spec").artifact_kind == "entity"),
    ("admin_display_name_is_canonical_admin", lambda: skill("admin").display_name == "admin"),
    ("resolve_by_hash_returns_skill", lambda: registry().resolve(skill("admin").hash) == skill("admin")),
    ("hash_edit_skill_exists", lambda: skill("hash_edit").name == "hash_edit"),
    ("workflow_trigger_terms_not_in_kernel_vocab_registry", lambda: "research_needed" not in vocab_registry_module.VOCABS),
    ("render_for_prompt_has_header", lambda: registry().render_for_prompt().startswith("## Available Skills")),
    ("render_for_prompt_has_trigger_vocab_section", lambda: "## Available Trigger Vocab" in registry().render_for_prompt()),
    ("resolve_vocab_trigger_does_not_find_reason", lambda: all(s.name != "reason" for s in registry().resolve_vocab_trigger("reason_needed"))),
    ("build_st_forwards_identity", lambda: "identity" in st_builder_module.build_st({"name": "person", "desc": "d", "identity": {"name": "Ada"}})),
    ("build_st_allows_empty_actions", lambda: st_builder_module.build_st({"name": "entity", "desc": "d", "actions": []})["steps"] == []),
    ("build_st_entity_adds_context_injection_steps", lambda: st_builder_module.build_st({
        "name": "person",
        "desc": "d",
        "identity": {"name": "Ada"},
        "preferences": {"communication": {"style": "direct"}},
    })["steps"] == [
        {"action": "load_identity", "desc": "surface identity context for person", "resolve": ["identity"], "post_diff": False},
        {"action": "load_preferences", "desc": "surface preferences context for person", "resolve": ["preferences"], "post_diff": False},
    ]),
    ("validate_st_accepts_pure_entity", lambda: st_builder_module.validate_st({"name": "entity", "desc": "d", "steps": []}) == []),
    ("validate_st_rejects_semantic_entity_without_context_steps", lambda: any(
        "context-injection steps" in e
        for e in st_builder_module.validate_st(
            {"name": "entity", "desc": "d", "identity": {"name": "Ada"}, "steps": []}
        )
    )),
    ("validate_st_rejects_invalid_trigger", lambda: any("invalid trigger" in e for e in st_builder_module.validate_st({"name": "x", "desc": "d", "trigger": "bad", "steps": []}))),
    ("builder_preserves_explicit_vocab", lambda: st_builder_module.build_st({"name": "x", "desc": "d", "steps": [{"action": "inspect", "desc": "inspect file", "vocab": "hash_resolve_needed"}]})["steps"][0]["vocab"] == "hash_resolve_needed"),
    ("validate_st_rejects_unknown_runtime_vocab", lambda: any("invalid runtime vocab" in e for e in st_builder_module.validate_st({"name": "x", "desc": "d", "steps": [{"action": "inspect", "desc": "inspect file", "vocab": "research_needed"}]}))),
    ("slugify_trims_to_four_words", lambda: st_builder_module.slugify("Update the very important config file") == "update_the_very_important"),
    ("resolve_entity_renders_known_skill", lambda: skill("admin").hash in loop._resolve_entity([skill("admin").hash], registry(), Trajectory())),
    ("resolve_entity_reads_action_package_when_not_entity", lambda: "semantic_tree:skill_package:" in loop._resolve_entity([skill("hash_edit").hash], registry(), Trajectory()) and "package:hash_edit " in loop._resolve_entity([skill("hash_edit").hash], registry(), Trajectory())),
    ("render_entity_has_identity_block", lambda: "identity:" in loop._render_entity(skill("admin"))),
    ("render_entity_has_steps_summary", lambda: "steps:" in loop._render_entity(skill("admin"))),
    ("find_identity_skill_returns_admin", lambda: loop._find_identity_skill("discord:784778107013431296", registry()) == skill("admin")),
    ("render_identity_has_mutable_preferences_surface", lambda: "## Mutable Preferences Surface" in loop._render_identity(skill("admin"))),
    ("render_identity_excludes_system_control_surface", lambda: "## System Control Surface" not in loop._render_identity(skill("admin"))),
    ("render_system_control_surface_has_available_workflows", lambda: "## Available Workflows" in control_surface_module.render_system_control_surface(registry(), cors_root=ROOT)),
    ("render_system_control_surface_has_vocab_map", lambda: "## Vocab Map" in control_surface_module.render_system_control_surface(registry(), cors_root=ROOT)),
    ("render_identity_has_access_rules_when_present", lambda: "## Access Rules" in loop._render_identity(skill("admin")) if "access_rules" in skill_data("admin") else True),
    ("render_identity_pending_bootstrap_shows_initiation", lambda: "## Initiation" in render_bootstrap_identity()),
    ("reprogramme_skill_trigger_is_vocab", lambda: skill("reprogramme").trigger == "on_vocab:reprogramme_needed"),
    ("reprogramme_skill_all_steps_loaded", lambda: skill("reprogramme").step_count() == 3),
    ("trigger_skill_marks_activation_surface", lambda: "activation codon for workflow starts and background launches" in skill_data("trigger")["desc"].lower()),
    ("reprogramme_skill_says_it_does_not_own_judgment", lambda: "does not own the judgment layer" in skill_data("reprogramme")["desc"].lower()),
    ("pre_diff_prompt_routes_inferred_preferences_to_reason_first", lambda: "Stable first-person preferences, communication norms, workflow preferences, and corrections may need semantic persistence, but reason about that first" in loop.PRE_DIFF_SYSTEM),
    ("pre_diff_prompt_describes_reason_as_structural_judgment", lambda: "`reason_needed` = gap requires structural judgment over semantic trees, entities, workflows, tools, vocab routes, or persistence decisions." in loop.PRE_DIFF_SYSTEM),
    ("pre_diff_prompt_says_tool_vocab_and_clarify_activate_through_reason", lambda: "`tool_needed`, `vocab_reg_needed`, and `clarify_needed` may only be activated through `reason_needed`." in loop.PRE_DIFF_SYSTEM),
    ("pre_diff_prompt_describes_reprogramme_as_profile_maintenance", lambda: "`reprogramme_needed` = gap requires writing semantic state into entity/admin-style profiles after that judgment is already warranted. It edits semantic profile state only, not delete/remove/unlink/move operations." in loop.PRE_DIFF_SYSTEM),
    ("pre_diff_prompt_describes_clarify_as_user_only_after_context", lambda: "`clarify_needed` = gap requires user-only information only after available semantic context is exhausted." in loop.PRE_DIFF_SYSTEM),
    ("pre_diff_prompt_says_profile_defaults_to_entity_record", lambda: "when a user refers to a person's \"profile\", default to the semantic entity record in their .st file" in loop.PRE_DIFF_SYSTEM.lower()),
    ("pre_diff_prompt_enforces_hash_grounding_for_step_and_content", lambda: "always reference both step history and content through hashes or repo paths when they are available" in loop.PRE_DIFF_SYSTEM.lower()),
    ("pre_diff_prompt_says_step_hashes_enable_tree_traversal", lambda: "step hashes are causal memory and let you traverse the reasoning path through the semantic tree" in loop.PRE_DIFF_SYSTEM.lower()),
    ("pre_diff_prompt_says_content_hashes_enable_context_traversal", lambda: "content hashes are evidence and let you traverse the concrete context attached to that tree" in loop.PRE_DIFF_SYSTEM.lower()),
    ("pre_diff_prompt_distinguishes_step_refs_and_content_refs", lambda: "step refs show the reasoning path you followed" in loop.PRE_DIFF_SYSTEM.lower() and "content refs show the evidence or workspace objects you need" in loop.PRE_DIFF_SYSTEM.lower()),
    ("pre_diff_prompt_restores_scoring_section", lambda: "## Scoring" in loop.PRE_DIFF_SYSTEM and "`relevance` = how directly resolving the gap advances the user's goal." in loop.PRE_DIFF_SYSTEM),
    ("pre_diff_prompt_names_builtin_abstractions", lambda: "`hash_resolve_needed` = gap requires resolving hashes, packages, repo paths, or semantic records into context." in loop.PRE_DIFF_SYSTEM and "`hash_edit_needed` = gap requires ordinary in-place workspace file patch/rewrite, not delete/remove/unlink/move." in loop.PRE_DIFF_SYSTEM and "`bash_needed` = gap requires shell-level workspace mutation, including delete/remove/unlink/move/rename." in loop.PRE_DIFF_SYSTEM and "`pattern_needed` = gap requires deterministic workspace search." in loop.PRE_DIFF_SYSTEM),
    ("pre_diff_prompt_says_custom_surfaces_are_runtime_injected", lambda: "Other observe and mutate surfaces may be injected at runtime through vocab-to-tool or vocab-to-chain routing." in loop.PRE_DIFF_SYSTEM),
    ("reason_prompt_treats_tree_as_historical_progress", lambda: "Treat the injected trajectory and active chain as your historical progress while processing the user's message." in execution_engine_module._reason_controller_prompt(make_gap("reason about deletion", vocab="reason_needed"))),
    ("reason_prompt_keeps_bridge_activation_under_reason", lambda: "tool_needed, vocab_reg_needed, and clarify_needed may only be surfaced through reason_needed." in execution_engine_module._reason_controller_prompt(make_gap("reason about deletion", vocab="reason_needed"))),
    ("reason_prompt_excludes_reprogramme_for_deletion", lambda: "reprogramme_needed may only be surfaced when semantic persistence into entity/admin state is already warranted; it edits semantic profile state only and should not be used for delete, remove, unlink, move, or rename operations." in execution_engine_module._reason_controller_prompt(make_gap("reason about deletion", vocab="reason_needed"))),
    ("reason_prompt_excludes_hash_edit_for_deletion", lambda: "hash_edit_needed is for in-place content edits only; do not use it for delete, remove, unlink, move, or rename operations." in execution_engine_module._reason_controller_prompt(make_gap("reason about deletion", vocab="reason_needed"))),
    ("reason_prompt_prefers_bash_for_deletion", lambda: "prefer bash_needed rather than hash_edit_needed or reprogramme_needed" in execution_engine_module._reason_controller_prompt(make_gap("reason about deletion", vocab="reason_needed")).lower()),
    ("admin_truth_model_tracks_trajectory_as_truth", lambda: skill_data("admin")["preferences"]["meta"]["truth_and_causality_model"]["trajectory_is_source_of_truth"] is True),
    ("admin_truth_model_tracks_step_hashes_as_causal_memory", lambda: skill_data("admin")["preferences"]["meta"]["truth_and_causality_model"]["step_hashes_are_causal_memory"] is True),
    ("init_user_intent_uses_on_contact_trigger", lambda: loop._build_init_user_intent("discord:123", "hi")["trigger"] == "on_contact:discord:123"),
    ("init_user_intent_starts_pending", lambda: loop._build_init_user_intent("discord:123", "hi")["init"]["status"] == "pending"),
    ("init_user_intent_prefers_get_to_know_questions", lambda: loop._build_init_user_intent("discord:123", "hi")["preferences"]["onboarding"]["get_to_know_entity"] is True),
    ("init_user_intent_bootstrap_is_only_deterministic_reprogramme", lambda: loop._build_init_user_intent("discord:123", "hi")["preferences"]["onboarding"]["deterministic_reprogramme_mode"] == "bootstrap_only"),
    ("init_user_intent_passive_reprogramme_is_optional", lambda: loop._build_init_user_intent("discord:123", "hi")["preferences"]["onboarding"]["passive_reprogramme_optional"] is True),
    ("init_user_intent_question_strategy_prioritizes_communication_preferences", lambda: "likes to communicate" in loop._build_init_user_intent("discord:123", "hi")["preferences"]["onboarding"]["question_strategy"].lower()),
    ("init_user_intent_question_strategy_redirects_casual_topics_back_to_user", lambda: "steer back" in loop._build_init_user_intent("discord:123", "hi")["preferences"]["onboarding"]["question_strategy"].lower()),
    ("init_user_intent_profile_updates_focus_on_user_experience", lambda: "improve the user experience" in loop._build_init_user_intent("discord:123", "hi")["preferences"]["onboarding"]["profile_update_mode"].lower()),
    ("init_user_intent_has_single_initiation_step", lambda: [step["action"] for step in loop._build_init_user_intent("discord:123", "hi")["steps"]] == ["initiate_entity"]),
    ("init_user_intent_initiation_step_resolves_full_profile", lambda: loop._build_init_user_intent("discord:123", "hi")["steps"][0]["resolve"] == ["identity", "preferences", "access_rules", "init"]),
    ("init_user_intent_uses_discord_username_as_default_name", lambda: loop._build_init_user_intent("discord:123", "hi", contact_profile={"username": "courtney"})["name"] == "courtney"),
    ("init_user_intent_sets_identity_name_from_profile", lambda: loop._build_init_user_intent("discord:123", "hi", contact_profile={"username": "courtney"})["identity"]["name"] == "courtney"),
    ("contact_trigger_filename_uses_username", lambda: st_builder_module.contact_filename_for_st({"trigger": "on_contact:discord:123", "identity": {"username": "courtney"}, "name": "courtney"}) == "courtney.st"),
    ("init_user_intent_sets_discord_id_as_identifier", lambda: loop._build_init_user_intent("discord:123", "hi", contact_profile={"username": "courtney"})["identity"]["discord_user_id"] == "123"),
    ("bound_discord_profile_requires_on_contact_entity", lambda: loop._is_bound_discord_profile("discord:123", bootstrap_identity_skill())),
    ("bound_discord_profile_excludes_admin", lambda: loop._is_bound_discord_profile("discord:784778107013431296", skill("admin")) is False),
    ("discord_profile_update_detector_ignores_greeting_only", lambda: loop._message_warrants_discord_profile_update("Hey", bootstrap_identity_skill()) is False),
    ("discord_profile_update_detector_flags_first_person_identity", lambda: loop._message_warrants_discord_profile_update("Hello I'm Jay. I work as a data analyst and have bad knees", bootstrap_identity_skill(contact_id="discord:456", username="jay")) is True),
    ("discord_profile_update_detector_flags_pending_profile_fragment", lambda: loop._message_warrants_discord_profile_update("Edit assistant for 2 years", bootstrap_identity_skill()) is True),
    ("discord_profile_update_detector_ignores_casual_player_taste", lambda: loop._message_warrants_discord_profile_update("son, cherki, tamale are all cool players who are playing at the moment", bootstrap_identity_skill()) is False),
    ("synth_system_defers_to_contact_guidance", lambda: "if the session injects contact synthesis guidance, follow it." in loop.SYNTH_SYSTEM.lower()),
    ("reprogramme_intent_accepts_semantic_skeleton", lambda: loop._is_reprogramme_intent({
        "version": "semantic_skeleton.v1",
        "artifact": {"kind": "entity"},
        "name": "admin",
        "desc": "admin entity",
        "trigger": "manual",
        "refs": {},
        "semantics": {},
    })),
    ("reprogramme_intent_rejects_action_semantic_skeleton", lambda: loop._is_reprogramme_intent({
        "version": "semantic_skeleton.v1",
        "artifact": {"kind": "action", "protected_kind": "action"},
        "name": "hash_edit",
        "desc": "workflow",
        "trigger": "manual",
        "refs": {},
    }) is False),
]


P6_CASES = [
    ("grounded_zero_without_refs", lambda: Compiler(Trajectory())._compute_grounded(make_gap("g")) == 0.0),
    ("grounded_positive_with_refs", lambda: Compiler(seed_trajectory("blob_a"))._compute_grounded(make_gap("g", content_refs=["blob_a"])) > 0.0),
    ("unsourced_gap_penalty_keeps_low_relevance_out", lambda: build_origin_context(relevance=0.49, refs=[]).compiler.gap_count() == 0),
    ("unsourced_gap_at_threshold_can_enter", lambda: build_origin_context(relevance=0.5, refs=[]).compiler.gap_count() == 1),
    ("tag_ref_prefixes_step_layer", lambda: Trajectory()._tag_ref("abc123", "step") == "step:abc123"),
    ("tag_ref_leaves_content_bare", lambda: Trajectory()._tag_ref("abc123", "content") == "abc123"),
    ("tag_ref_uses_typed_namespace_for_skills", lambda: build_chain_context().traj._tag_ref(skill("admin").hash, "content", registry()).startswith("entity:")),
    ("render_refs_combines_layers", lambda: "step:parent" in Trajectory()._render_refs(["parent"], ["blob"], None) and "blob" in Trajectory()._render_refs(["parent"], ["blob"], None)),
    ("render_recent_names_skill_hashes", lambda: "entity:" in build_chain_context().traj.render_recent(5, registry())),
    ("resolve_hash_renders_step_branch", lambda: (lambda ctx: "semantic_tree:step_branch:" in loop.resolve_hash(ctx.step1.hash, ctx.traj))(build_chain_context())),
    ("resolve_hash_renders_gap_tree", lambda: (lambda ctx: "semantic_tree:gap_branch:" in loop.resolve_hash(ctx.gap.hash, ctx.traj))(build_chain_context())),
    ("resolve_hash_returns_none_for_unknown", lambda: loop.resolve_hash("not_a_real_hash", Trajectory()) is None),
    ("render_gap_tree_active_status", lambda: "status: active" in loop._render_gap_tree(make_gap("g"))),
    ("render_gap_tree_dormant_status", lambda: "status: dormant" in loop._render_gap_tree(make_gap("g", dormant=True))),
    ("render_gap_tree_resolved_status", lambda: "status: resolved" in loop._render_gap_tree(make_gap("g", resolved=True))),
    ("step_refs_and_content_refs_render_separately", lambda: "step:prior_step" in build_chain_context().traj.render_recent(5, registry()) and "blob_cfg" in build_chain_context().traj.render_recent(5, registry())),
    ("gap_hash_encodes_content_citation", lambda: make_gap("g", content_refs=["blob_a"]).hash != make_gap("g", content_refs=["blob_b"]).hash),
    ("gap_hash_encodes_step_citation", lambda: make_gap("g", step_refs=["step_a"]).hash != make_gap("g", step_refs=["step_b"]).hash),
    ("co_occurrence_counts_reference_usage", lambda: seed_trajectory("blob_a", count=2).co_occurrence("blob_a") == 2),
    ("resolve_entity_falls_back_to_trajectory", lambda: (lambda traj, step: "semantic_tree:step_branch:" in loop._resolve_entity([step.hash], registry(), traj))( *(lambda t, s: (t.append(s), (t, s))[1])(Trajectory(), make_step("fallback")) )),
]

P6_CASES += [
    ("entity_source_detects_admin", lambda: loop._is_entity_source("skills/admin.st")),
    ("entity_source_detects_entity_tree", lambda: loop._is_entity_source("skills/entities/clinton.st")),
    ("entity_source_detects_chain_spec", lambda: loop._is_entity_source("skills/codons/commitment_chain_construction_spec.st")),
    ("entity_source_excludes_action_tree", lambda: loop._is_entity_source("skills/actions/hash_edit.st") is False),
    ("resolve_hash_admin_renders_entity_surface", lambda: (lambda reg: (setattr(loop, "_skill_registry", reg), "semantic_tree:skill_package:" in loop.resolve_hash(skill("admin").hash, Trajectory()) and "package:admin " in loop.resolve_hash(skill("admin").hash, Trajectory()))[1])(registry())),
    ("resolve_hash_action_renders_package_tree", lambda: (lambda reg: (setattr(loop, "_skill_registry", reg), "semantic_tree:skill_package:" in loop.resolve_hash(skill("hash_edit").hash, Trajectory()) and "package:hash_edit " in loop.resolve_hash(skill("hash_edit").hash, Trajectory()))[1])(registry())),
    ("resolve_hash_chain_spec_renders_entity_surface", lambda: (lambda reg: (setattr(loop, "_skill_registry", reg), "commitment_chain_construction_spec" in loop.resolve_hash(skill("commitment_chain_construction_spec").hash, Trajectory()))[1])(registry())),
    ("resolve_entity_top_rate_injects_business_context", lambda: "Top Rate Estates LTD" in loop._resolve_entity([skill("Top Rate Estates LTD").hash], registry(), Trajectory())),
    ("resolve_entity_clinton_injects_identity", lambda: "Cyber security developer" in loop._resolve_entity([skill("clinton").hash], registry(), Trajectory())),
    ("render_entity_includes_trigger", lambda: "trigger:" in loop._render_entity(skill("clinton"))),
    ("render_chain_spec_exposes_field_semantics", lambda: "## Field Semantics" in loop._render_identity(skill("commitment_chain_construction_spec"))),
    ("render_chain_spec_mentions_reason_activation", lambda: "activation_owned_by_reason" in loop._render_identity(skill("commitment_chain_construction_spec"))),
    ("render_chain_spec_mentions_tool_writer_split", lambda: "tool_creation_owned_by_tool_needed" in loop._render_identity(skill("commitment_chain_construction_spec"))),
    ("render_chain_spec_mentions_public_trigger_rule", lambda: "final public trigger assignment belongs to the completed top-level workflow" in loop._render_identity(skill("commitment_chain_construction_spec")).lower()),
    ("render_session_context_includes_header", lambda: "## Session Context" in loop._render_session_context(Trajectory(), registry(), "hello")),
    ("pre_diff_prompt_describes_st_files_as_semantic_environment_surfaces", lambda: "`.st` files are semantic environment surfaces." in loop.PRE_DIFF_SYSTEM),
    ("pre_diff_prompt_describes_workspace_files_as_implementation_surfaces", lambda: "Ordinary workspace files are implementation surfaces." in loop.PRE_DIFF_SYSTEM),
    ("pre_diff_prompt_says_reason_shapes_environment", lambda: "Use these as the runtime abstractions for shaping the environment." in loop.PRE_DIFF_SYSTEM),
    ("pre_diff_prompt_keeps_low_level_path_enforcement_out_of_prompt", lambda: "Think in terms of which abstraction the turn requires, not which low-level file path should be enforced." in loop.PRE_DIFF_SYSTEM),
]


def test_p13_rogue_step_signature_and_render():
    traj = Trajectory()
    rogue = Step.create(
        "REVERTED: bad mutation",
        content_refs=["blob_a"],
        rogue=True,
        rogue_kind="policy_violation",
        failure_source="tree_policy",
    )
    traj.append(rogue)

    rendered = traj.render_recent(5, registry())
    assert "{r=" in rendered
    assert "rogues (1)" in rendered
    assert "policy_violation, tree_policy" in rendered


def test_p6_resolve_all_refs_carries_content_refs_from_step_refs():
    setattr(loop, "_skill_registry", registry())
    traj = Trajectory()
    parent = make_step("parent", content_refs=[skill("admin").hash])
    traj.append(parent)

    rendered = loop.resolve_all_refs([parent.hash], [], traj)

    assert f"── resolved {skill('admin').hash} ──" in rendered


def test_p6_resolve_all_refs_dedupes_explicit_and_carried_content_refs():
    setattr(loop, "_skill_registry", registry())
    traj = Trajectory()
    parent = make_step("parent", content_refs=[skill("admin").hash])
    traj.append(parent)

    rendered = loop.resolve_all_refs([parent.hash], [skill("admin").hash], traj)

    assert rendered.count(f"── resolved {skill('admin').hash} ──") == 1


def test_p6_resolve_all_refs_step_ref_expansion_is_shallow():
    setattr(loop, "_skill_registry", registry())
    traj = Trajectory()
    grandparent = make_step("grandparent", content_refs=[skill("admin").hash])
    traj.append(grandparent)
    parent = make_step("parent", step_refs=[grandparent.hash], content_refs=[])
    traj.append(parent)

    rendered = loop.resolve_all_refs([parent.hash], [], traj)

    assert f"── resolved {skill('admin').hash} ──" not in rendered


def test_p6_ground_emitted_gaps_for_admission_carries_step_content_refs():
    setattr(loop, "_skill_registry", registry())
    traj = Trajectory()
    parent = make_step("parent", content_refs=[skill("admin").hash])
    traj.append(parent)
    child_gap = make_gap("child", step_refs=[parent.hash], content_refs=[])

    grounded = loop._ground_emitted_gaps_for_admission([child_gap], traj)

    assert child_gap.content_refs == [skill("admin").hash]
    assert f"── resolved {skill('admin').hash} ──" in grounded[0][1]


def test_p6_render_candidate_gap_grounding_includes_resolved_refs():
    setattr(loop, "_skill_registry", registry())
    traj = Trajectory()
    parent = make_step("parent", content_refs=[skill("admin").hash])
    traj.append(parent)
    child_gap = make_gap("child", step_refs=[parent.hash], content_refs=[])

    rendered = loop._render_candidate_gap_grounding(
        loop._ground_emitted_gaps_for_admission([child_gap], traj)
    )

    assert rendered is not None
    assert "## Candidate Gap Grounding" in rendered
    assert f"### gap:{child_gap.hash}" in rendered
    assert f"── resolved {skill('admin').hash} ──" in rendered


def test_p6_execution_engine_candidate_grounding_mutates_child_refs():
    traj = Trajectory()
    parent = make_step("parent", content_refs=["skills/admin.st"])
    traj.append(parent)
    child_gap = make_gap("child", step_refs=[parent.hash], content_refs=[])

    hooks = SimpleNamespace(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: (
            f"refs:{','.join(step_refs)}|content:{','.join(content_refs)}"
        )
    )

    grounded = execution_engine_module._ground_emitted_gaps_for_admission(
        [child_gap],
        trajectory=traj,
        hooks=hooks,
    )

    assert child_gap.content_refs == ["skills/admin.st"]
    assert grounded[0][1] == f"refs:{parent.hash}|content:skills/admin.st"


def test_p6_execution_engine_injects_candidate_gap_grounding():
    class FakeSession:
        def __init__(self):
            self.injected = []

        def inject(self, content: str, role: str = "user"):
            self.injected.append(content)

    gap = make_gap("child", content_refs=["skills/admin.st"])
    session = FakeSession()

    execution_engine_module._inject_candidate_gap_grounding(
        session,
        [(gap, "resolved admin context")],
    )

    assert session.injected
    assert "## Candidate Gap Grounding" in session.injected[0]
    assert f"### gap:{gap.hash}" in session.injected[0]
    assert "resolved admin context" in session.injected[0]


def test_p13_reprogramme_failure_materializes_rogue_step():
    class FakeSession:
        def __init__(self):
            self.injected = []

        def inject(self, content: str, role: str = "user"):
            self.injected.append(content)

        def call(self, user_content: str = None) -> str:
            return json.dumps({
                "version": "semantic_skeleton.v1",
                "artifact": {"kind": "entity"},
                "name": "admin",
                "desc": "bad update",
                "trigger": "manual",
                "refs": {},
                "existing_ref": "kenny:47824f077e7d",
                "semantics": {},
            })

    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap("persist admin preference", content_refs=[skill("admin").hash], vocab="reprogramme_needed")
    entry = SimpleNamespace(gap=gap, chain_id="chain1")
    session = FakeSession()

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "",
        execute_tool=lambda tool, params: ("Validation errors:\n  - existing_ref not found: kenny:47824f077e7d", 1),
        auto_commit=lambda message, paths=None: ("abc123", None),
        parse_step_output=lambda raw, step_refs, content_refs, chain_id=None: (make_step("noop"), []),
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: None,
        extract_written_path=lambda output: None,
        is_reprogramme_intent=lambda intent: True,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: "semantic_tree:skill_package:hash_edit\nname: hash_edit" if content_refs else None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: ["skills/admin.st [step] +1 -0"],
        step_assessment=lambda before, after, path=None: ["  validator: ok"],
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.step_result is not None
    assert outcome.step_result.rogue is True
    assert outcome.step_result.rogue_kind == "validation_error"
    assert outcome.step_result.failure_source == "st_builder"
    assert len(outcome.step_result.step_refs) == 1
    failure_attempt = traj.resolve(outcome.step_result.step_refs[0])
    assert failure_attempt is not None
    assert failure_attempt.desc == "failed attempt: persist admin preference"
    assert len(outcome.step_result.gaps) == 1
    assert outcome.step_result.gaps[0].vocab == "reason_needed"
    assert outcome.step_result.gaps[0].step_refs == [failure_attempt.hash]
    assert "Diagnose rogue step" in outcome.step_result.gaps[0].desc


def test_p13_render_recent_labels_rogue_handoff_resolution():
    traj = Trajectory()
    gap = make_gap("build workflow", resolved=True)
    gap.resolution_kind = "rogue_handoff"
    traj.append(make_step("author workflow", gaps=[gap]))

    rendered = traj.render_recent(5, registry())
    assert "resolved -> rogue handoff" in rendered


def test_p13_compiler_resolve_current_gap_records_resolution_kind():
    ctx = build_origin_context()
    ctx.compiler.resolve_current_gap(ctx.gap.hash, resolution_kind="rogue_handoff")
    assert ctx.gap.resolved is True
    assert ctx.gap.resolution_kind == "rogue_handoff"


P7_CASES = [
    ("admin_steps_all_deterministic", lambda: all(not s.post_diff for s in skill("admin").steps)),
    ("hash_edit_has_one_flexible_step", lambda: len(skill("hash_edit").flexible_steps()) == 1),
    ("hash_edit_has_flexible_steps_again", lambda: any(s.post_diff for s in skill("hash_edit").steps)),
    ("hash_edit_has_deterministic_steps_again", lambda: any(not s.post_diff for s in skill("hash_edit").steps)),
    ("await_first_two_deterministic", lambda: all(not s.post_diff for s in skill("await").steps[:2])),
    ("await_last_step_flexible", lambda: skill("await").steps[-1].post_diff is True),
    ("commit_later_steps_flexible", lambda: all(s.post_diff for s in skill("commit").steps[1:])),
    ("reprogramme_steps_all_terminal", lambda: all(not s.post_diff for s in skill("reprogramme").steps)),
    ("builder_observe_maps_to_post_diff_true", lambda: st_builder_module.build_st({"name": "x", "desc": "d", "actions": [{"do": "inspect file", "observe": True}]})["steps"][0]["post_diff"] is True),
    ("builder_mutate_maps_to_post_diff_false", lambda: st_builder_module.build_st({"name": "x", "desc": "d", "actions": [{"do": "edit file", "mutate": True}]})["steps"][0]["post_diff"] is False),
    ("action_update_requires_existing_ref", lambda: any("requires 'existing_ref'" in e for e in st_builder_module.validate_st({"name": "x", "desc": "d", "steps": []}, artifact_kind="action_update"))),
    ("render_for_prompt_marks_admin_deterministic", lambda: "(deterministic)" in registry().render_for_prompt()),
    ("render_for_prompt_marks_mixed_skill", lambda: "hash_edit" in registry().render_for_prompt() and "(mixed)" in registry().render_for_prompt()),
    ("admin_deterministic_steps_helper", lambda: all(not s.post_diff for s in skill("admin").steps)),
    ("hash_edit_flexible_steps_helper", lambda: len(skill("hash_edit").flexible_steps()) == 1),
]

P7_CASES += [
    ("clinton_steps_are_all_deterministic", lambda: all(not s.post_diff for s in skill("clinton").steps)),
    ("top_rate_steps_are_all_deterministic", lambda: all(not s.post_diff for s in skill("Top Rate Estates LTD").steps)),
    ("cors_ui_steps_are_all_deterministic", lambda: all(not s.post_diff for s in skill("cors_ui").steps)),
    ("chain_spec_steps_are_all_deterministic", lambda: all(not s.post_diff for s in skill("commitment_chain_construction_spec").steps)),
    ("clinton_loads_identity_first", lambda: skill("clinton").steps[0].action == "load_identity"),
    ("clinton_loads_preferences_second", lambda: skill("clinton").steps[1].action == "load_preferences"),
    ("top_rate_loads_identity_first", lambda: skill("Top Rate Estates LTD").steps[0].action == "load_identity"),
    ("cors_ui_loads_constraints", lambda: skill("cors_ui").steps[0].action == "load_constraints"),
    ("chain_spec_load_order_matches_semantics", lambda: [s.action for s in skill("commitment_chain_construction_spec").steps] == ["load_identity", "load_constraints", "load_scope"]),
]


P8_CASES = [
    ("omo_allows_first_mutation", lambda: Compiler(Trajectory()).validate_omo("content_needed")),
    ("omo_blocks_consecutive_mutation", lambda: (lambda comp: (comp.record_execution("content_needed", True), comp.validate_omo("content_needed"))[1] is False)(Compiler(Trajectory()))),
    ("omo_allows_observation_after_mutation", lambda: (lambda comp: (comp.record_execution("content_needed", True), comp.validate_omo("pattern_needed"))[1])(Compiler(Trajectory()))),
    ("postcondition_needed_after_mutation", lambda: (lambda comp: (comp.record_execution("content_needed", True), comp.needs_postcondition())[1])(Compiler(Trajectory()))),
    ("postcondition_clears_after_observation", lambda: (lambda comp: (comp.record_execution("content_needed", True), comp.record_execution("pattern_needed", False), comp.needs_postcondition())[2] is False)(Compiler(Trajectory()))),
    ("govern_acts_on_grounded_mutation", lambda: govern(LedgerEntry(make_gap("g", vocab="content_needed", confidence=0.7, grounded=0.6), "c"), 1, GovernorState()) == GovernorSignal.ACT),
    ("govern_allows_weak_mutation", lambda: govern(LedgerEntry(make_gap("g", vocab="content_needed", confidence=0.2, grounded=0.1), "c"), 1, GovernorState()) == GovernorSignal.ALLOW),
    ("govern_reverts_on_real_divergence", lambda: (lambda state: (state.record(Epistemic(0.5, 0.8, 0.5)), state.record(Epistemic(0.5, 0.19, 0.5)), govern(LedgerEntry(make_gap("g"), "c"), 1, state))[2] == GovernorSignal.REVERT)(GovernorState())),
    ("govern_does_not_revert_on_moderate_confidence_drop", lambda: (lambda state: (state.record(Epistemic(0.5, 0.8, 0.5)), state.record(Epistemic(0.5, 0.5, 0.5)), govern(LedgerEntry(make_gap("g"), "c"), 1, state))[2] != GovernorSignal.REVERT)(GovernorState())),
    ("govern_redirects_on_oscillation", lambda: (lambda state: (state.record(Epistemic(0.5, 0.80, 0.5)), state.record(Epistemic(0.5, 0.70, 0.5)), state.record(Epistemic(0.5, 0.75, 0.5)), state.record(Epistemic(0.5, 0.68, 0.5)), govern(LedgerEntry(make_gap("g"), "c"), 1, state))[4] == GovernorSignal.REDIRECT)(GovernorState())),
    ("govern_redirects_on_stagnation", lambda: (lambda state: (state.record(Epistemic(0.5, 0.5, 0.5)), state.record(Epistemic(0.5, 0.5, 0.5)), state.record(Epistemic(0.5, 0.5, 0.5)), govern(LedgerEntry(make_gap("g"), "c"), 1, state))[3] == GovernorSignal.REDIRECT)(GovernorState())),
    ("govern_constrains_at_max_depth", lambda: govern(LedgerEntry(make_gap("g"), "c"), MAX_CHAIN_DEPTH + 1, GovernorState()) == GovernorSignal.CONSTRAIN),
    ("ledger_lifo_pop", lambda: (lambda ledger, g1, g2: (ledger.push_origin(g1, "c1"), ledger.push_origin(g2, "c2"), ledger.pop().gap.hash == g2.hash)[2])(Ledger(), make_gap("g1"), make_gap("g2"))),
    ("ledger_child_pops_first", lambda: (lambda ledger, g1, g2: (ledger.push_origin(g1, "c1"), ledger.push_child(g2, "c1", g1.hash, 1), ledger.pop().gap.hash == g2.hash)[2])(Ledger(), make_gap("g1"), make_gap("g2"))),
    ("force_close_marks_chain_resolved", lambda: (lambda ctx: (ctx.compiler.force_close_chain(next(iter(ctx.traj.chains))), next(iter(ctx.traj.chains.values())).resolved)[1])(build_origin_context())),
    ("skip_chain_suspends_chain", lambda: (lambda ctx, chain_id: (ctx.compiler.skip_chain(chain_id), ctx.compiler.ledger.chain_states[chain_id] == ChainState.SUSPENDED)[1])(build_origin_context(), next(iter(build_origin_context().traj.chains)))),
    ("next_on_empty_halts", lambda: Compiler(Trajectory()).next()[1] == GovernorSignal.HALT),
    ("next_sets_active_chain", lambda: build_origin_context().compiler.next()[0] is not None),
    ("resolve_current_gap_closes_chain", lambda: (lambda ctx: (ctx.compiler.next(), ctx.compiler.resolve_current_gap(ctx.gap.hash), next(iter(ctx.traj.chains.values())).resolved)[2])(build_origin_context())),
    ("render_ledger_empty_message", lambda: Compiler(Trajectory()).render_ledger() == "(ledger empty)"),
    ("chain_summary_contains_state", lambda: "state" in build_origin_context().compiler.chain_summary()[0]),
]

P8_CASES += [
    ("govern_allows_observe_gap", lambda: govern(LedgerEntry(make_gap("g", vocab="pattern_needed", confidence=0.7, grounded=0.7), "c"), 1, GovernorState()) == GovernorSignal.ALLOW),
    ("govern_constrains_past_max_depth", lambda: govern(LedgerEntry(make_gap("g"), "c"), MAX_CHAIN_DEPTH + 1, GovernorState()) == GovernorSignal.CONSTRAIN),
    ("needs_postcondition_false_initially", lambda: Compiler(Trajectory()).needs_postcondition() is False),
    ("record_execution_observation_keeps_last_was_mutation_false", lambda: (lambda comp: (comp.record_execution("pattern_needed", False), comp.last_was_mutation is False)[1])(Compiler(Trajectory()))),
    ("record_execution_mutation_sets_last_was_mutation_true", lambda: (lambda comp: (comp.record_execution("content_needed", True), comp.last_was_mutation is True)[1])(Compiler(Trajectory()))),
    ("record_execution_observation_clears_postcondition_need", lambda: (lambda comp: (comp.record_execution("content_needed", True), comp.record_execution("pattern_needed", False), comp.needs_postcondition() is False)[2])(Compiler(Trajectory()))),
    ("governor_state_stagnation_window_constant", lambda: STAGNATION_WINDOW == 3),
    ("governor_state_saturation_threshold_constant", lambda: SATURATION_THRESHOLD == 0.05),
    ("validate_omo_allows_observe_after_observe", lambda: (lambda comp: (comp.record_execution("pattern_needed", False), comp.validate_omo("pattern_needed"))[1])(Compiler(Trajectory()))),
    ("validate_omo_allows_bridge_after_observe", lambda: Compiler(Trajectory()).validate_omo("reason_needed")),
]


P9_CASES = [
    ("chain_starts_at_length_one", lambda: Chain.create("gap", "step").length() == 1),
    ("chain_add_step_increments_length", lambda: (lambda c: (c.add_step("step2"), c.length())[1] == 2)(Chain.create("gap", "step1"))),
    ("chain_roundtrip_preserves_hash", lambda: Chain.from_dict(Chain.create("gap", "step").to_dict()).hash == Chain.create("gap", "step").hash),
    ("chain_roundtrip_preserves_signature", lambda: (lambda c: (c.add_step("step2"), Chain.from_dict(c.to_dict()).signature == c.signature)[1])(Chain.create("gap", "step1"))),
    ("trajectory_add_chain_find_chain", lambda: (lambda traj, c: (traj.add_chain(c), traj.find_chain(c.origin_gap) == c)[1])(Trajectory(), Chain.create("gap", "step"))),
    ("append_to_passive_chain_true_when_open", lambda: (lambda traj, c, s: (traj.add_chain(c), traj.append_to_passive_chain(c.hash, s))[1])(Trajectory(), Chain.create("gap", "step1"), make_step("step2"))),
    ("append_to_passive_chain_false_when_resolved", lambda: (lambda traj, c, s: (setattr(c, "resolved", True), traj.add_chain(c), traj.append_to_passive_chain(c.hash, s))[2] is False)(Trajectory(), Chain.create("gap", "step1"), make_step("step2"))),
    ("find_passive_chains_matches_origin_refs", lambda: (lambda traj, gap, chain: (traj.gap_index.__setitem__(gap.hash, gap), traj.add_chain(chain), len(traj.find_passive_chains("blob_a")) == 1)[2])(Trajectory(), make_gap("origin", content_refs=["blob_a"]), Chain.create(make_gap("origin", content_refs=["blob_a"]).hash, "step1"))),
    ("recent_is_chronological", lambda: (lambda traj, s1, s2: (traj.append(s1), traj.append(s2), [s.desc for s in traj.recent(2)] == ["one", "two"])[2])(Trajectory(), make_step("one"), make_step("two"))),
    ("render_recent_empty_trajectory", lambda: Trajectory().render_recent() == "(empty trajectory)"),
    ("render_recent_flat_when_no_chains", lambda: "step:" in (lambda traj: (traj.append(make_step("loose")), traj.render_recent())[1])(Trajectory())),
    ("render_recent_chain_header", lambda: "chain:" in build_chain_context().traj.render_recent(5, registry())),
    ("render_recent_shows_commit", lambda: "commit:abc123" in build_chain_context().traj.render_recent(5, registry())),
    ("render_recent_shows_resolved_status", lambda: "resolved" in build_chain_context().traj.render_recent(5, registry())),
    ("recent_chains_returns_chain_objects", lambda: isinstance(build_chain_context().traj.recent_chains(1)[0], Chain)),
    ("chain_summary_counts_steps", lambda: build_origin_context().compiler.chain_summary()[0]["steps"] >= 1),
    ("extract_threshold_marks_chain", lambda: (lambda traj, comp, chain, gap: (
        setattr(comp, "active_chain", chain),
        [chain.add_step(f"s{i}") for i in range(CHAIN_EXTRACT_LENGTH - 1)],
        comp.resolve_current_gap(gap.hash),
        chain.extracted,
    )[3])(
        (lambda ctx: ctx.traj)(build_origin_context()),
        (lambda ctx: ctx.compiler)(build_origin_context()),
        next(iter(build_origin_context().traj.chains.values())),
        build_origin_context().gap,
    )),
    ("chain_state_open_on_push_origin", lambda: list(build_origin_context().compiler.ledger.chain_states.values())[0] == ChainState.OPEN),
    ("find_chain_returns_none_when_absent", lambda: Trajectory().find_chain("missing") is None),
    ("co_occurrence_reads_gap_refs_via_all_refs", lambda: (lambda traj, gap, step: (traj.append(step), traj.co_occurrence("blob_gap") == 1)[1])(Trajectory(), make_gap("g", content_refs=["blob_gap"]), make_step("s", gaps=[make_gap("g", content_refs=["blob_gap"])]))),
    ("render_recent_orders_recent_chain_first", lambda: build_chain_context().traj.render_recent(1, registry()).startswith("chain:")),
]

P9_CASES += [
    ("chain_desc_roundtrip", lambda: (lambda c: (setattr(c, "desc", "workflow"), Chain.from_dict(c.to_dict()).desc == "workflow")[1])(Chain.create("gap", "step"))),
    ("chain_resolved_roundtrip", lambda: (lambda c: (setattr(c, "resolved", True), Chain.from_dict(c.to_dict()).resolved is True)[1])(Chain.create("gap", "step"))),
    ("chain_extracted_roundtrip", lambda: (lambda c: (setattr(c, "extracted", True), Chain.from_dict(c.to_dict()).extracted is True)[1])(Chain.create("gap", "step"))),
    ("trajectory_recent_limits_size", lambda: (lambda traj: (traj.append(make_step("one")), traj.append(make_step("two")), len(traj.recent(1)) == 1)[2])(Trajectory())),
    ("trajectory_resolve_missing_step_none", lambda: Trajectory().resolve("missing") is None),
    ("trajectory_resolve_missing_gap_none", lambda: Trajectory().resolve_gap("missing") is None),
    ("append_to_passive_chain_appends_hash", lambda: (lambda traj, chain, step: (traj.add_chain(chain), traj.append_to_passive_chain(chain.hash, step), chain.steps[-1] == step.hash)[2])(Trajectory(), Chain.create("gap", "step1"), make_step("step2"))),
    ("find_passive_chains_excludes_resolved_chain", lambda: (lambda traj, gap, chain: (traj.gap_index.__setitem__(gap.hash, gap), setattr(chain, "resolved", True), traj.add_chain(chain), len(traj.find_passive_chains("blob_a")) == 0)[3])(Trajectory(), make_gap("origin", content_refs=["blob_a"]), Chain.create(make_gap("origin", content_refs=["blob_a"]).hash, "step1"))),
    ("recent_chains_respects_limit", lambda: len(build_chain_context().traj.recent_chains(1)) == 1),
    ("chain_length_matches_step_list", lambda: (lambda c: (c.add_step("s2"), c.add_step("s3"), c.length() == len(c.steps))[2])(Chain.create("gap", "s1"))),
]


P10_CASES = [
    ("trigger_trigger_manual", lambda: skill("trigger").trigger == "manual"),
    ("await_trigger", lambda: skill("await").trigger == "on_vocab:await_needed"),
    ("await_wait_step_observe", lambda: skill("await").steps[0].vocab == "hash_resolve_needed"),
    ("await_last_step_flexible", lambda: skill("await").steps[-1].post_diff is True),
    ("commit_relevance_descends", lambda: [s["relevance"] for s in skill_data("commit")["steps"]] == [1.0, 0.9, 0.8]),
    ("reprogramme_trigger", lambda: skill("reprogramme").trigger == "on_vocab:reprogramme_needed"),
    ("reprogramme_relevance_descends", lambda: [s["relevance"] for s in skill_data("reprogramme")["steps"]] == [1.0, 0.9, 0.8]),
    ("background_trigger_needs_heartbeat", lambda: (lambda comp: (comp.record_background_trigger("c1"), comp.needs_heartbeat())[1])(Compiler(Trajectory()))),
    ("await_suppresses_heartbeat", lambda: (lambda comp: (comp.record_background_trigger("c1"), comp.record_await("c1"), comp.needs_heartbeat())[2] is False)(Compiler(Trajectory()))),
    ("dangling_gaps_find_carry_forward_only", lambda: (lambda traj, gap: (
        setattr(gap, "carry_forward", True),
        traj.append(make_step("s", gaps=[gap])),
        len(loop._find_dangling_gaps(traj)) == 1
    )[2])(Trajectory(), make_gap("active"))),
    ("dangling_gaps_ignore_dormant", lambda: len(loop._find_dangling_gaps((lambda traj: (traj.append(make_step("s", gaps=[make_gap("d", dormant=True)])), traj)[1])(Trajectory()))) == 0),
    ("dangling_gaps_ignore_resolved", lambda: len(loop._find_dangling_gaps((lambda traj: (traj.append(make_step("s", gaps=[make_gap("r", resolved=True)])), traj)[1])(Trajectory()))) == 0),
    ("await_steps_count", lambda: skill("await").step_count() == 3),
]

P10_CASES += [
    ("trigger_skill_is_codon", lambda: skill("trigger").artifact_kind == "codon"),
    ("await_skill_is_codon", lambda: skill("await").artifact_kind == "codon"),
    ("reprogramme_skill_is_codon", lambda: skill("reprogramme").artifact_kind == "codon"),
    ("route_mode_for_admin_source_is_entity_editor", lambda: execution_engine_module._reprogramme_mode_for_source("skills/admin.st") == "entity_editor"),
    ("route_mode_for_entity_source_is_entity_editor", lambda: execution_engine_module._reprogramme_mode_for_source("skills/entities/clinton.st") == "entity_editor"),
    ("entity_surface_matcher_accepts_entities_prefix", lambda: execution_engine_module._is_entity_admin_surface("skills/entities/") is True),
    ("destructive_bash_detected_for_delete_gap", lambda: execution_engine_module._is_destructive_bash_gap(make_gap("Delete skills/entities/clinton.st from the workspace.", vocab="bash_needed")) is True),
    ("destructive_bash_not_detected_for_hash_edit_gap", lambda: execution_engine_module._is_destructive_bash_gap(make_gap("Delete skills/entities/clinton.st from the workspace.", vocab="hash_edit_needed")) is False),
    ("destructive_bash_preserved_on_entity_surface", lambda: execution_engine_module._preserve_destructive_bash_on_entity_surface(make_gap("Delete skills/entities/clinton.st from the workspace.", vocab="bash_needed"), loop._load_tree_policy()) is True),
    ("destructive_bash_preserved_for_resolved_entity_target", lambda: execution_engine_module._preserve_destructive_bash_on_entity_surface(make_gap("Delete clinton.st entity file.", vocab="bash_needed", content_refs=[skill("clinton").hash]), loop._load_tree_policy(), skill("clinton")) is True),
    ("route_mode_for_action_source_is_action_editor", lambda: execution_engine_module._reprogramme_mode_for_source("skills/actions/hash_edit.st") == "action_editor"),
    ("new_action_origination_requires_reason", lambda: execution_engine_module._new_action_origination_requires_reason(make_gap("create research workflow", vocab="content_needed"), route_mode="action_editor", target_entity=None)),
    ("reason_judgment_required_for_public_trigger_assignment", lambda: execution_engine_module._requires_reason_judgment(
        make_gap("Assign on_vocab:research_needed as the public trigger for the highest-order research workflow in skills/actions/research.st.", vocab="content_needed"),
        registry=registry(),
        policy=loop._load_tree_policy(),
        route_mode="action_editor",
        target_entity=None,
    ) is True),
    ("reason_judgment_required_for_hash_embedding", lambda: execution_engine_module._requires_reason_judgment(
        make_gap("Embed the committed research leaf by block_ref into the higher-order orchestration workflow.", vocab="content_needed"),
        registry=registry(),
        policy=loop._load_tree_policy(),
        route_mode=None,
        target_entity=None,
    ) is True),
    ("reason_judgment_not_required_for_ordinary_repo_file_edit", lambda: execution_engine_module._requires_reason_judgment(
        make_gap("Fix a typo in docs/ARCHITECTURE.md.", vocab="hash_edit_needed", content_refs=["docs/ARCHITECTURE.md"]),
        registry=registry(),
        policy=loop._load_tree_policy(),
        route_mode=None,
        target_entity=None,
    ) is False),
    ("reason_target_path_prefers_desc_action_path_over_tool_ref", lambda: execution_engine_module._target_path_from_gap(make_gap("Create a new research workflow in skills/actions/research.st", content_refs=["tools/research_web.py"])) == "skills/actions/research.st"),
    ("entity_editor_coercion_strips_flow_fields", lambda: (lambda frame: ("root" not in frame and "phases" not in frame and "closure" not in frame and frame["artifact"]["kind"] == "entity"))(
        execution_engine_module._coerce_semantic_frame_for_mode(
            {"artifact": {"kind": "hybrid"}, "root": "r", "phases": [], "closure": {}},
            "entity_editor",
        )
    )),
]


P11_CASES = [
    ("absolute_time_format_epoch", lambda: bool(TIMESTAMP_RE.fullmatch(absolute_time(0.1)))),
    ("absolute_time_format_recent", lambda: bool(TIMESTAMP_RE.fullmatch(absolute_time(time.time())))),
    ("absolute_time_format_fixed", lambda: absolute_time(1710000000.0).startswith("2024-")),
    ("step_timestamp_is_absolute_renderable", lambda: bool(TIMESTAMP_RE.fullmatch(absolute_time(make_step("s").t)))),
    ("relative_time_just_now", lambda: relative_time(time.time()) == "just now"),
    ("relative_time_seconds", lambda: relative_time(time.time() - 10).endswith("s ago")),
    ("relative_time_minutes", lambda: relative_time(time.time() - 120).endswith("m ago")),
    ("relative_time_hours", lambda: relative_time(time.time() - 7200).endswith("h ago")),
    ("relative_time_yesterday", lambda: relative_time(time.time() - 86400) == "yesterday"),
    ("relative_time_days", lambda: relative_time(time.time() - (3 * 86400)).endswith("d ago")),
    ("relative_time_months", lambda: relative_time(time.time() - (70 * 86400)).endswith("mo ago")),
    ("render_recent_chain_header_has_absolute_time", lambda: bool(re.search(r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]", build_chain_context().traj.render_recent(5, registry())))),
    ("render_recent_steps_have_absolute_time", lambda: bool(re.search(r"\(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\)", build_chain_context().traj.render_recent(5, registry())))),
    ("flat_tree_has_absolute_time", lambda: bool(re.search(r"\(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\)", (lambda traj: (traj.append(make_step("loose")), traj.render_recent())[1])(Trajectory())))),
    ("render_chain_includes_runtime_legend", lambda: (lambda ctx: "legend: step{kindflowN}" in ctx.traj.render_chain(next(iter(ctx.traj.chains)), registry()) and "gap refs = gap-surfacing provenance" in ctx.traj.render_chain(next(iter(ctx.traj.chains)), registry()))(build_chain_context())),
    ("deep_render_has_absolute_time", lambda: (lambda ctx: bool(re.search(r"\(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\)", loop._render_step_tree(ctx.step2, ctx.traj))))(build_chain_context())),
    ("step_timestamps_increase_over_time", lambda: (lambda s1, s2: s2.t >= s1.t)(make_step("a"), make_step("b"))),
    ("recent_returns_last_step_time", lambda: (lambda ctx: ctx.traj.recent(1)[0].t == ctx.step2.t)(build_chain_context())),
    ("render_recent_preserves_step_order", lambda: (lambda ctx: (lambda rendered: rendered.find(ctx.step1.hash) < rendered.find(ctx.step2.hash))(ctx.traj.render_recent(5, registry())))(build_chain_context())),
    ("relative_time_zero_or_negative_empty", lambda: relative_time(0) == ""),
    ("absolute_time_zero_or_negative_empty", lambda: absolute_time(0) == ""),
]

P11_CASES += [
    ("relative_time_fifty_nine_seconds", lambda: relative_time(time.time() - 59).endswith("s ago")),
    ("relative_time_fifty_nine_minutes", lambda: relative_time(time.time() - (59 * 60)).endswith("m ago")),
    ("relative_time_twenty_three_hours", lambda: relative_time(time.time() - (23 * 3600)).endswith("h ago")),
    ("relative_time_two_days", lambda: relative_time(time.time() - (2 * 86400)).endswith("d ago")),
    ("relative_time_many_months", lambda: relative_time(time.time() - (365 * 86400)).endswith("mo ago")),
    ("absolute_time_nonempty_for_positive", lambda: absolute_time(1.0) != ""),
    ("step_times_are_float_seconds", lambda: isinstance(make_step("timed").t, float)),
    ("render_step_tree_has_absolute_time", lambda: bool(re.search(r"\(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\)", loop._render_step_tree(make_step("timed"), (lambda traj, step: (traj.append(step), traj)[1])(Trajectory(), make_step("timed")))))),
    ("render_recent_has_chain_header_timestamp_brackets", lambda: "[" in build_chain_context().traj.render_recent(5, registry()).splitlines()[0]),
    ("absolute_time_stable_for_same_input", lambda: absolute_time(1710000000.0) == absolute_time(1710000000.0)),
]


P12_CASES = [
    ("parse_step_output_extracts_gap", lambda: (lambda old: (setattr(loop, "_turn_counter", 7), loop._parse_step_output('Saw issue\\n{\"gaps\":[{\"desc\":\"need context\",\"content_refs\":[\"blob_a\"],\"step_refs\":[\"step_a\"],\"vocab\":\"pattern_needed\",\"relevance\":0.8,\"confidence\":0.6}]}', ["step_root"], ["blob_root"])[0:2], setattr(loop, "_turn_counter", old))[1][1][0].desc == "need context")(loop._turn_counter)),
    ("parse_step_output_sets_turn_id", lambda: (lambda old: (setattr(loop, "_turn_counter", 9), loop._parse_step_output('x {\"gaps\":[{\"desc\":\"g\"}]}', [], [])[1][0].turn_id, setattr(loop, "_turn_counter", old))[1] == 9)(loop._turn_counter)),
    ("parse_step_output_zeros_grounded", lambda: loop._parse_step_output('x {"gaps":[{"desc":"g","grounded":1.0}]}', [], [])[1][0].scores.grounded == 0.0),
    ("parse_step_output_uses_prefix_desc", lambda: loop._parse_step_output('observed issue {"gaps":[]}', [], [])[0].desc == "observed issue"),
    ("parse_step_output_persists_top_level_note", lambda: (lambda step: step.note is not None and step.note.summary == "reasoned over chain" and step.note.drift == ["runtime/doc mismatch"])(loop._parse_step_output('reason {"note":{"summary":"reasoned over chain","drift":["runtime/doc mismatch"]},"gaps":[]}', [], [])[0])),
    ("extract_json_parses_block", lambda: loop._extract_json('text {"a": 1}') == {"a": 1}),
    ("extract_json_invalid_returns_none", lambda: loop._extract_json("not json") is None),
    ("extract_command_reads_command_field", lambda: loop._extract_command('{"command": "echo hi"}') == "echo hi"),
    ("extract_command_missing_returns_none", lambda: loop._extract_command('{"reasoning": "x"}') is None),
    ("resolve_all_refs_formats_blocks", lambda: (lambda ctx: "resolved step" in loop.resolve_all_refs([ctx.step1.hash], [], ctx.traj))(build_chain_context())),
    ("load_tree_policy_contains_action_entity_prefixes", lambda: "skills/actions/" in loop._load_tree_policy() and "skills/entities/" in loop._load_tree_policy()),
    ("match_policy_exact_path", lambda: loop._match_policy("loop.py", loop._load_tree_policy())["immutable"] is True),
    ("match_policy_prefix_path", lambda: loop._match_policy("skills/admin.st", loop._load_tree_policy())["on_mutate"] == "reprogramme_needed"),
    ("match_policy_longest_prefix", lambda: loop._match_policy("skills/codons/await.st", loop._load_tree_policy())["on_reject"] == "reason_needed"),
    ("match_policy_tools_prefix_routes_to_tool_writer", lambda: loop._match_policy("tools/research_web.py", loop._load_tree_policy())["on_mutate"] == "tool_needed"),
    ("chain_spec_in_codon_tree_still_resolves_as_entity_source", lambda: loop._is_entity_source("skills/codons/commitment_chain_construction_spec.st")),
    ("execute_tool_missing_file_nonzero", lambda: loop.execute_tool("tools/does_not_exist.py", {})[1] == 1),
    ("find_identity_skill_admin", lambda: loop._find_identity_skill("discord:784778107013431296", registry()) == skill("admin")),
    ("render_identity_has_communication_pref", lambda: "communication:" in loop._render_identity(skill("admin"))),
    ("admin_load_order_matches_split_surfaces", lambda: [s.action for s in skill("admin").steps] == ["load_identity", "load_preferences"]),
    ("validate_st_accepts_command_trigger", lambda: st_builder_module.validate_st({"name": "cmd", "desc": "d", "trigger": "command:demo", "steps": []}) == []),
    ("load_skill_detects_command_flag", lambda: (lambda path: load_skill(str(path)).is_command)(
        (lambda p: (p.write_text(json.dumps({"name": "cmd", "desc": "d", "trigger": "command:test", "steps": []})), p)[1])(Path(ROOT / "tests" / "_tmp_command.st"))
    )),
    ("resolve_hash_unknown_returns_none", lambda: loop.resolve_hash("missing_hash", Trajectory()) is None),
]

P12_CASES += [
    ("collect_clarify_frontier_merges_current_and_active", lambda: (lambda comp, gap1, gap2: (
        comp.ledger.push_origin(gap1, "c1"),
        comp.ledger.push_origin(gap2, "c2"),
        len(execution_engine_module._collect_clarify_frontier(comp, gap1, current_turn=0)) == 2,
    )[2])(Compiler(Trajectory()), make_gap("ask one", vocab="clarify_needed", turn_id=0), make_gap("ask two", vocab="clarify_needed", turn_id=0))),
    ("collect_clarify_frontier_filters_old_turns", lambda: (lambda comp, current_gap, old_gap: (
        comp.ledger.push_origin(old_gap, "c1"),
        len(execution_engine_module._collect_clarify_frontier(comp, current_gap, current_turn=2)) == 1,
    )[1])(Compiler(Trajectory(), current_turn=2), make_gap("current", vocab="clarify_needed", turn_id=2), make_gap("old", vocab="clarify_needed", turn_id=1))),
    ("build_clarify_frontier_step_merges_refs", lambda: (lambda step: ("blob_a" in step.content_refs and "step_a" in step.step_refs))(execution_engine_module._build_clarify_frontier_step(origin_step=make_step("origin"), merged_gaps=[make_gap("q1", content_refs=["blob_a"], step_refs=["step_a"], vocab="clarify_needed")], chain_id="c1"))),
    ("build_clarify_frontier_step_desc_prefix", lambda: execution_engine_module._build_clarify_frontier_step(origin_step=make_step("origin"), merged_gaps=[make_gap("q1", vocab="clarify_needed")], chain_id="c1").desc.startswith("clarify frontier:")),
    ("clone_gap_for_carry_forward_preserves_vocab", lambda: loop._clone_gap_for_carry_forward(make_gap("persist", vocab="reason_needed"), current_turn=5).vocab == "reason_needed"),
    ("clone_gap_for_carry_forward_sets_new_turn", lambda: loop._clone_gap_for_carry_forward(make_gap("persist", vocab="reason_needed"), current_turn=5).turn_id == 5),
    ("forced_synth_frontier_none_when_empty", lambda: loop._persist_forced_synth_frontier(Trajectory(), Compiler(Trajectory()), make_step("origin"), 0) is None),
    ("forced_synth_frontier_marks_gaps_carry_forward", lambda: (lambda ctx: (
        loop._persist_forced_synth_frontier(ctx.traj, ctx.compiler, ctx.step, 3).gaps[0].carry_forward
    ))(build_origin_context())),
    ("dangling_gaps_ignore_clarify_even_if_marked", lambda: (lambda traj, gap: (
        setattr(gap, "carry_forward", True),
        traj.append(make_step("s", gaps=[gap])),
        len(loop._find_dangling_gaps(traj)) == 0,
    )[2])(Trajectory(), make_gap("clarify", vocab="clarify_needed"))),
    ("emit_reason_skill_is_context_only", lambda: len(loop._emit_reason_skill(skill("trigger"), make_gap("reason about this"), make_step("origin"), "c1").gaps) == 0),
    ("activate_chain_reference_background_schedules_without_gaps", lambda: (lambda comp, step: (comp.record_background_trigger("c1"), True)[1] if step.desc.startswith("scheduled background chain:") and not step.gaps else False)(
        Compiler(Trajectory()),
        manifest_engine_module.activate_chain_reference(
            ROOT / "chains",
            skill("trigger").hash,
            "background",
            make_gap("reason about this"),
            make_step("origin"),
            "c1",
            registry(),
            Compiler(Trajectory()),
            Trajectory(),
            0,
        ),
    )),
    ("activate_chain_reference_background_includes_trigger_context", lambda: skill("trigger").hash in manifest_engine_module.activate_chain_reference(
        ROOT / "chains",
        skill("trigger").hash,
        "background",
        make_gap("reason about this"),
        make_step("origin"),
        "c1",
        registry(),
        Compiler(Trajectory()),
        Trajectory(),
        0,
    ).content_refs),
]


def test_p12_compiler_background_refs_split_manual_await_from_async():
    compiler = Compiler(Trajectory())
    compiler.ledger.chain_states["manual"] = ChainState.OPEN
    compiler.ledger.chain_states["async"] = ChainState.OPEN

    compiler.record_background_trigger(
        "manual",
        refs=["child_manual"],
        activation_ref="child_manual",
        await_policy="manual",
    )
    compiler.record_background_trigger(
        "async",
        refs=["child_async"],
        activation_ref="child_async",
        await_policy="none",
    )

    assert compiler.manual_await_refs() == ["child_manual"]
    assert compiler.background_refs() == ["child_async"]
    assert compiler.needs_heartbeat() is True


def test_p12_persist_manual_await_frontier_emits_await_gap():
    traj = Trajectory()
    compiler = Compiler(traj)
    compiler.ledger.chain_states["parent"] = ChainState.OPEN
    origin = make_step("origin")
    traj.append(origin)
    compiler.record_background_trigger(
        "parent",
        refs=["child_chain"],
        activation_ref="child_chain",
        await_policy="manual",
    )

    await_step = loop._persist_manual_await_frontier(traj, compiler, origin, 5)

    assert await_step is not None
    assert await_step.desc.startswith("await frontier:")
    assert await_step.content_refs == ["child_chain"]
    assert len(await_step.gaps) == 1
    assert await_step.gaps[0].vocab == "await_needed"
    assert await_step.gaps[0].carry_forward is True
    assert "parent" in compiler._awaited_chains


def test_p12_load_chain_package_searches_sibling_trajectory_stores(tmp_path):
    command_dir = tmp_path / "command"
    background_dir = tmp_path / "background_agent"
    command_dir.mkdir(parents=True)
    background_dir.mkdir(parents=True)
    doc = {
        "hash": "childflow1234",
        "origin_gap": "gap123",
        "desc": "background flow",
        "steps": [],
    }
    (background_dir / "childflow1234.json").write_text(json.dumps(doc))

    loaded = manifest_engine_module.load_chain_package(command_dir, "childflow1234")

    assert loaded == doc


def test_p12_extract_chains_writes_activation_alias(tmp_path):
    traj = Trajectory()
    step = make_step("child")
    traj.append(step)
    chain = Chain.create("gap123", step.hash)
    chain.resolved = True
    chain.extracted = True
    chain.activation_ref = "workflow_alias"
    traj.add_chain(chain)

    traj.extract_chains(str(tmp_path))

    assert (tmp_path / f"{chain.hash}.json").exists()
    assert (tmp_path / "workflow_alias.json").exists()


def test_p12_run_isolated_workflow_ref_writes_background_store(tmp_path, monkeypatch):
    monkeypatch.setattr(loop, "TRAJECTORY_STORE_DIR", tmp_path / "trajectory_store")
    monkeypatch.setattr(loop, "COMMAND_TRAJECTORY_DIR", loop.TRAJECTORY_STORE_DIR / "command")
    monkeypatch.setattr(loop, "SUBAGENT_TRAJECTORY_DIR", loop.TRAJECTORY_STORE_DIR / "subagent")
    monkeypatch.setattr(loop, "BACKGROUND_AGENT_TRAJECTORY_DIR", loop.TRAJECTORY_STORE_DIR / "background_agent")

    class FakeSession:
        def __init__(self, model=None):
            self.messages = []

        def set_system(self, content: str):
            self.messages = [{"role": "system", "content": content}]

        def inject(self, content: str, role: str = "user"):
            self.messages.append({"role": role, "content": content})

        def call(self, user_content: str = None) -> str:
            if user_content:
                self.inject(user_content)
            return '{"gaps":[]}'

    monkeypatch.setattr(loop, "Session", FakeSession)
    monkeypatch.setattr(loop, "_synthesize", lambda session, user_message, turn_facts=None: "child done")

    def fake_execute_iteration(**kwargs):
        entry = kwargs["entry"]
        trajectory = kwargs["trajectory"]
        compiler = kwargs["compiler"]
        step_result = make_step(f"child executed: {entry.gap.desc}", chain_id=entry.chain_id)
        trajectory.append(step_result)
        compiler.add_step_to_chain(step_result.hash)
        compiler.resolve_current_gap(entry.gap.hash)
        return SimpleNamespace(control="continue", step_result=step_result)

    monkeypatch.setattr(loop, "execute_iteration", fake_execute_iteration)

    ref = skill("hash_edit").hash
    result = loop.run_isolated_workflow_ref(
        ref,
        task_prompt="apply a deterministic child edit flow",
        store_kind="background_agent",
        await_policy="none",
    )

    assert result["status"] == "ok"
    assert Path(str(result["trajectory"])).exists()
    assert Path(str(result["chains_file"])).exists()
    alias_path = Path(str(result["chains_dir"])) / f"{ref}.json"
    assert alias_path.exists()
    alias_doc = json.loads(alias_path.read_text())
    assert alias_doc["activation_ref"] == ref
    assert alias_doc["store_kind"] == "background_agent"


def test_p12_run_isolated_workflow_ref_normalizes_typed_workflow_ref(tmp_path, monkeypatch):
    monkeypatch.setattr(loop, "TRAJECTORY_STORE_DIR", tmp_path / "trajectory_store")
    monkeypatch.setattr(loop, "COMMAND_TRAJECTORY_DIR", loop.TRAJECTORY_STORE_DIR / "command")
    monkeypatch.setattr(loop, "SUBAGENT_TRAJECTORY_DIR", loop.TRAJECTORY_STORE_DIR / "subagent")
    monkeypatch.setattr(loop, "BACKGROUND_AGENT_TRAJECTORY_DIR", loop.TRAJECTORY_STORE_DIR / "background_agent")

    class FakeSession:
        def __init__(self, model=None):
            self.messages = []

        def set_system(self, content: str):
            self.messages = [{"role": "system", "content": content}]

        def inject(self, content: str, role: str = "user"):
            self.messages.append({"role": role, "content": content})

        def call(self, user_content: str = None) -> str:
            if user_content:
                self.inject(user_content)
            return '{"gaps":[]}'

    monkeypatch.setattr(loop, "Session", FakeSession)
    monkeypatch.setattr(loop, "_synthesize", lambda session, user_message, turn_facts=None: "child done")

    def fake_execute_iteration(**kwargs):
        entry = kwargs["entry"]
        trajectory = kwargs["trajectory"]
        compiler = kwargs["compiler"]
        step_result = make_step(f"child executed: {entry.gap.desc}", chain_id=entry.chain_id)
        trajectory.append(step_result)
        compiler.add_step_to_chain(step_result.hash)
        compiler.resolve_current_gap(entry.gap.hash)
        return SimpleNamespace(control="continue", step_result=step_result)

    monkeypatch.setattr(loop, "execute_iteration", fake_execute_iteration)

    ref = f"architect:{skill('architect').hash}"
    result = loop.run_isolated_workflow_ref(
        ref,
        task_prompt="run architect child flow",
        store_kind="background_agent",
        await_policy="manual",
    )

    assert result["status"] == "ok"
    assert result["activation_ref"] == skill("architect").hash
    alias_path = Path(str(result["chains_dir"])) / f"{skill('architect').hash}.json"
    assert alias_path.exists()
    alias_doc = json.loads(alias_path.read_text())
    assert alias_doc["activation_ref"] == skill("architect").hash


P13_CASES = [
    ("max_chain_depth_constant", lambda: MAX_CHAIN_DEPTH == 15),
    ("chain_extract_length_constant", lambda: CHAIN_EXTRACT_LENGTH == 8),
    ("ledger_entry_depth_defaults_zero", lambda: LedgerEntry(make_gap("g"), "c").depth == 0),
    ("push_child_sets_depth", lambda: (lambda ledger: (ledger.push_child(make_gap("g"), "c", "p", 3), ledger.peek().depth == 3)[1])(Ledger())),
    ("await_relevance_descending", lambda: (lambda vals: vals == sorted(vals, reverse=True))([s["relevance"] for s in skill_data("await")["steps"]])),
    ("commit_relevance_descending", lambda: (lambda vals: vals == sorted(vals, reverse=True))([s["relevance"] for s in skill_data("commit")["steps"]])),
    ("reprogramme_relevance_descending", lambda: (lambda vals: vals == sorted(vals, reverse=True))([s["relevance"] for s in skill_data("reprogramme")["steps"]])),
    ("hash_edit_observe_then_flexible_then_mutate", lambda: [s.get("vocab") for s in skill_data("hash_edit")["steps"]] == ["hash_resolve_needed", None, "hash_edit_needed"]),
    ("admin_refs_field_present", lambda: "refs" in skill_data("admin")),
    ("cors_ui_refs_field_present", lambda: "refs" in skill_data("cors_ui")),
    ("builder_preserves_refs", lambda: st_builder_module.build_st({"name": "wf", "desc": "d", "refs": {"admin": "abc"}, "actions": []})["refs"] == {"admin": "abc"}),
    ("find_passive_chains_supports_embedding", lambda: (lambda traj, gap, chain: (traj.gap_index.__setitem__(gap.hash, gap), traj.add_chain(chain), bool(traj.find_passive_chains("entity_hash")))[2])(Trajectory(), make_gap("origin", content_refs=["entity_hash"]), Chain.create(make_gap("origin", content_refs=["entity_hash"]).hash, "step1"))),
    ("force_close_marks_reason", lambda: (lambda ctx: (ctx.compiler.force_close_chain(next(iter(ctx.traj.chains))), "force-closed" in next(iter(ctx.traj.chains.values())).desc)[1])(build_origin_context())),
    ("render_recent_reports_step_count", lambda: build_chain_context().chain.length() == 2),
    ("recent_chains_returns_chain_units", lambda: build_chain_context().traj.recent_chains(1)[0].origin_gap == build_chain_context().chain.origin_gap),
    ("compose_over_construction_keeps_codon_steps_short", lambda: all(skill(name).step_count() <= 4 for name in ("trigger", "await", "commit", "reprogramme"))),
]

P13_CASES += [
    ("root_skills_only_admin", lambda: sorted(path.name for path in SKILLS_DIR.glob("*.st")) == ["admin.st"]),
    ("action_tree_contains_curated_actions", lambda: {"architect.st", "debug.st", "hash_edit.st"}.issubset({path.name for path in (SKILLS_DIR / "actions").glob("*.st")})),
    ("entity_tree_contains_runtime_entities", lambda: {"clinton.st", "cors_ui.st", "top_rate_estates_ltd.st"}.issubset({path.name for path in (SKILLS_DIR / "entities").glob("*.st")})),
    ("codon_tree_contains_bridge_and_spec", lambda: sorted(path.name for path in (SKILLS_DIR / "codons").glob("*.st")) == ["await.st", "commit.st", "commitment_chain_construction_spec.st", "reprogramme.st", "trigger.st"]),
    ("loader_treats_admin_as_entity", lambda: skill("admin").artifact_kind == "entity"),
    ("loader_treats_hash_edit_as_action", lambda: skill("hash_edit").artifact_kind == "action"),
    ("loader_treats_trigger_as_codon", lambda: skill("trigger").artifact_kind == "codon"),
    ("loader_treats_chain_spec_as_entity_even_in_codon_tree", lambda: skill("commitment_chain_construction_spec").artifact_kind == "entity"),
    ("policy_marks_codon_tree_immutable", lambda: loop._match_policy("skills/codons/trigger.st", loop._load_tree_policy())["immutable"] is True),
    ("policy_marks_action_tree_reason_first", lambda: loop._match_policy("skills/actions/debug.st", loop._load_tree_policy())["on_mutate"] == "reason_needed"),
    ("policy_marks_action_tree_action_editor", lambda: loop._match_policy("skills/actions/debug.st", loop._load_tree_policy())["reprogramme_mode"] == "action_editor"),
]


@pytest.mark.parametrize("label,check", P1_CASES, ids=[case[0] for case in P1_CASES])
def test_principle_1_step_primitive(label, check):
    assert check()


@pytest.mark.parametrize("label,check", P2_CASES, ids=[case[0] for case in P2_CASES])
def test_principle_2_gap_emission(label, check):
    assert check()


@pytest.mark.parametrize("label,check", P3_CASES, ids=[case[0] for case in P3_CASES])
def test_principle_3_vocab_manifestation(label, check):
    assert check()


@pytest.mark.parametrize("label,check", P4_CASES, ids=[case[0] for case in P4_CASES])
def test_principle_4_formal_gap_configuration(label, check):
    assert check()


@pytest.mark.parametrize("label,check", P5_CASES, ids=[case[0] for case in P5_CASES])
def test_principle_5_reprogramme_and_registry(label, check):
    assert check()


@pytest.mark.parametrize("label,check", P6_CASES, ids=[case[0] for case in P6_CASES])
def test_principle_6_referred_context(label, check):
    assert check()


@pytest.mark.parametrize("label,check", P7_CASES, ids=[case[0] for case in P7_CASES])
def test_principle_7_post_diff(label, check):
    assert check()


@pytest.mark.parametrize("label,check", P8_CASES, ids=[case[0] for case in P8_CASES])
def test_principle_8_compiler_laws(label, check):
    assert check()


@pytest.mark.parametrize("label,check", P9_CASES, ids=[case[0] for case in P9_CASES])
def test_principle_9_chains_and_steps(label, check):
    assert check()


@pytest.mark.parametrize("label,check", P10_CASES, ids=[case[0] for case in P10_CASES])
def test_principle_10_activation_and_codons(label, check):
    assert check()


@pytest.mark.parametrize("label,check", P11_CASES, ids=[case[0] for case in P11_CASES])
def test_principle_11_temporal_signatures(label, check):
    assert check()


@pytest.mark.parametrize("label,check", P12_CASES, ids=[case[0] for case in P12_CASES])
def test_principle_12_supporting_infrastructure(label, check):
    try:
        assert check()
    finally:
        tmp = ROOT / "tests" / "_tmp_command.st"
        if tmp.exists():
            tmp.unlink()


@pytest.mark.parametrize("label,check", P13_CASES, ids=[case[0] for case in P13_CASES])
def test_principle_13_curation(label, check):
    assert check()


def test_p9_trajectory_save_and_load_roundtrip(tmp_path):
    gap = make_gap("persisted", content_refs=["blob_a"], vocab="pattern_needed")
    step = make_step("saved step", gaps=[gap], commit="abc123")
    traj = Trajectory()
    traj.append(step)

    path = tmp_path / "trajectory.json"
    traj.save(path)
    loaded = Trajectory.load(path)

    assert loaded.resolve(step.hash).desc == "saved step"
    assert loaded.resolve_gap(gap.hash).desc == "persisted"


def test_p9_chains_save_load_and_extract(tmp_path):
    ctx = build_chain_context()
    chains_path = tmp_path / "chains.json"
    chains_dir = tmp_path / "chains"

    ctx.traj.save_chains(chains_path)
    loaded = Trajectory()
    Trajectory.load_chains(chains_path, loaded)
    loaded.steps = ctx.traj.steps
    loaded.chains = ctx.traj.chains
    next(iter(loaded.chains.values())).extracted = True
    next(iter(loaded.chains.values())).resolved = True
    loaded.extract_chains(chains_dir)

    assert chains_path.exists()
    assert any(chains_dir.iterdir())




def test_p12_auto_commit_contract_clean_tree(monkeypatch):
    monkeypatch.setattr(loop, "git", lambda cmd, cwd=None: "")
    assert loop.auto_commit("noop") == (None, None)


def test_p12_auto_commit_contract_success(monkeypatch):
    responses = {
        ("status", "--porcelain"): " M loop.py",
        ("rev-parse", "--short", "HEAD"): "abc123",
        ("add", "-A", "--", "loop.py"): "",
        ("commit", "-m", "ok"): "",
        ("diff", "--numstat", "abc123", "abc123"): "5\t4\tloop.py",
    }

    def fake_git(cmd, cwd=None):
        return responses.get(tuple(cmd), "")

    monkeypatch.setattr(loop, "git", fake_git)
    monkeypatch.setattr(loop, "git_head", lambda: "abc123")
    monkeypatch.setattr(loop, "_check_protected", lambda post, pre: ([], None))

    assert loop.auto_commit("ok") == ("abc123", None)


def test_p12_auto_commit_filters_local_runtime_noise(monkeypatch):
    calls: list[tuple[str, ...]] = []

    def fake_git(cmd, cwd=None):
        calls.append(tuple(cmd))
        if cmd == ["status", "--porcelain"]:
            return "\n".join(
                [
                    " M skills/admin.st",
                    " M background_completions.json",
                    " M trajectory_store/background_agent/hash_edit.json",
                    " M tools/__pycache__/scan_tree.cpython-314.pyc",
                ]
            )
        if cmd[:3] == ["rev-parse", "--short", "HEAD"]:
            return "abc123"
        if cmd == ["diff", "--numstat", "abc123", "abc123"]:
            return "5\t4\tskills/admin.st"
        return ""

    monkeypatch.setattr(loop, "git", fake_git)
    monkeypatch.setattr(loop, "git_head", lambda: "abc123")
    monkeypatch.setattr(loop, "_check_protected", lambda post, pre: ([], None))

    assert loop.auto_commit("ok") == ("abc123", None)
    assert ("add", "-A", "--", "skills/admin.st") in calls
    assert ("add", "-A", "--", "background_completions.json") not in calls


def test_p12_auto_commit_scopes_to_selected_paths(monkeypatch):
    calls: list[tuple[str, ...]] = []

    def fake_git(cmd, cwd=None):
        calls.append(tuple(cmd))
        if cmd == ["status", "--porcelain", "--", "skills/admin.st"]:
            return " M skills/admin.st"
        if cmd[:3] == ["rev-parse", "--short", "HEAD"]:
            return "abc123"
        if cmd == ["diff", "--numstat", "abc123", "abc123"]:
            return "5\t4\tskills/admin.st"
        return ""

    monkeypatch.setattr(loop, "git", fake_git)
    monkeypatch.setattr(loop, "git_head", lambda: "abc123")
    monkeypatch.setattr(loop, "_check_protected", lambda post, pre: ([], None))

    assert loop.auto_commit("ok", paths=["/Users/k2invested/Desktop/cors/skills/admin.st"]) == ("abc123", None)
    assert ("status", "--porcelain", "--", "skills/admin.st") in calls
    assert ("add", "-A", "--", "skills/admin.st") in calls


def test_p12_auto_commit_contract_rejection(monkeypatch):
    calls: list[tuple[str, ...]] = []

    def fake_git(cmd, cwd=None):
        calls.append(tuple(cmd))
        if cmd[:2] == ["status", "--porcelain"]:
            return " M loop.py"
        if cmd[:3] == ["rev-parse", "--short", "HEAD"]:
            return "abc123"
        return ""

    monkeypatch.setattr(loop, "git", fake_git)
    monkeypatch.setattr(loop, "git_head", lambda: "abc123")
    monkeypatch.setattr(loop, "_check_protected", lambda post, pre: (["skills/codons/trigger.st"], "reason_needed"))

    assert loop.auto_commit("bad") == (None, "reason_needed")
    assert ("revert", "--no-commit", "HEAD") in calls


def test_p12_auto_commit_notifications_formats_step_and_regular_files(monkeypatch):
    monkeypatch.setattr(
        loop,
        "git",
        lambda cmd, cwd=None: "5\t4\tloop.py\n8\t2\tskills/admin.st" if cmd == ["diff", "--numstat", "a1", "b2"] else "",
    )
    monkeypatch.setattr(
        loop,
        "git_show",
        lambda ref: json.dumps({
            "name": "admin",
            "trigger": "on_contact:discord:784778107013431296",
            "steps": [{"action": "load_identity", "desc": "load", "resolve": ["identity"], "post_diff": False}],
        }) if ref == "a1:skills/admin.st" else json.dumps({
            "name": "admin",
            "trigger": "on_contact:discord:784778107013431296",
            "steps": [
                {"action": "load_identity", "desc": "load", "resolve": ["identity"], "post_diff": False},
                {"action": "persist_pref", "desc": "persist", "vocab": "reprogramme_needed", "post_diff": False},
            ],
        }),
    )
    lines = loop._auto_commit_notifications("a1", "b2")
    assert lines[0] == "loop.py +5 -4"
    assert lines[1] == "skills/admin.st [step] +8 -2"
    assert "  validator.status: ok" in lines
    assert "  structure.step_count: 1->2" in lines
    assert "  continuity.trigger: preserved" in lines
    assert "  projection.bridge_count: 0->1" in lines
    assert "  policy.drift: false" in lines
    assert "  semantic.drift: true" in lines
    assert "  surface.reprogramme_needed: added (0->1)" in lines
    assert "  step_delta: persist_pref added surface=reprogramme_needed post_diff=false refs=0" in lines


def test_p12_step_assessment_notification_reports_unchanged_gap_config():
    before = {
        "name": "admin",
        "trigger": "manual",
        "steps": [{"action": "load_identity", "desc": "load", "resolve": ["identity"], "post_diff": False}],
    }
    after = {
        "name": "admin",
        "trigger": "manual",
        "steps": [{"action": "load_identity", "desc": "load", "resolve": ["identity"], "post_diff": False}],
        "preferences": {"communication": {"plain_text_only": True}},
    }
    lines = loop._step_assessment_notification("skills/admin.st", before, after)
    assert "  validator.status: ok" in lines
    assert "  structure.artifact_kind: action->hybrid" in lines
    assert "  structure.step_count: 1->1" in lines
    assert "  continuity.trigger: preserved" in lines
    assert "  policy.drift: false" in lines
    assert "  semantic.drift: true" in lines
    assert "  surface.internal: unchanged (1->1)" in lines
    assert not any(line.startswith("  step_delta:") for line in lines)
    assert not any(line.startswith("  continuity.init_scaffold:") for line in lines)


def test_p12_policy_drift_only_tracks_policy_enforcement_failures():
    assessment = {
        "security_violations": [],
        "security_risks": [{"domain": "semantic_integrity", "code": "semantic_desc_vocab_mismatch"}],
    }
    assert loop._policy_drift_flag(assessment) is False


def test_p12_policy_drift_detects_protected_surface_policy_failures():
    assessment = {
        "security_violations": [{"domain": "protected_surfaces", "code": "codon_mutation_attempt"}],
        "security_risks": [],
    }
    assert loop._policy_drift_flag(assessment) is True


def test_p12_commit_assessment_for_commit_uses_parent_diff(monkeypatch):
    monkeypatch.setattr(loop, "git", lambda cmd, cwd=None: "parent123" if cmd == ["rev-parse", "child456^"] else "")
    monkeypatch.setattr(loop, "_auto_commit_notifications", lambda pre, post: [f"{pre}->{post}"])
    assert loop._commit_assessment_for_commit("child456") == ["parent123->child456"]


def test_p12_step_serialization_preserves_assessment():
    step = Step.create("postcondition", assessment=["skills/admin.st [step] +1 -0"])
    restored = Step.from_dict(step.to_dict())
    assert restored.assessment == ["skills/admin.st [step] +1 -0"]


def test_p12_render_recent_shows_step_assessment():
    traj = Trajectory()
    traj.append(Step.create("postcondition", assessment=["skills/admin.st [step] +1 -0"]))
    rendered = traj.render_recent(5, registry())
    assert "assessment: skills/admin.st [step] +1 -0" in rendered


def test_p12_policy_drift_assessment_marks_tree_policy_revert():
    lines = execution_engine_module._policy_drift_assessment("tree_policy", "immutable path violation")
    assert lines == [
        "policy.status: rejected",
        "policy.drift: true",
        "policy.source: tree_policy",
        "policy.detail: immutable path violation",
    ]


def test_p12_reprogramme_intent_rejects_gap_payload():
    assert loop._is_reprogramme_intent({"gaps": [{"desc": "x"}]}) is False


def test_p12_reprogramme_intent_accepts_entity_payload():
    assert loop._is_reprogramme_intent({"name": "admin", "desc": "prefs", "artifact_kind": "entity"}) is True


def test_p12_reprogramme_intent_rejects_action_payload():
    assert loop._is_reprogramme_intent({"name": "hash_edit", "desc": "workflow", "artifact_kind": "action_update"}) is False


def test_p12_contact_synthesis_guidance_pending_redirects_to_user():
    guidance = loop._render_contact_synthesis_guidance(bootstrap_identity_skill())

    assert guidance is not None
    assert "init.status pending" in guidance
    assert "learning about the user directly" in guidance


def test_p12_contact_synthesis_guidance_complete_allows_normal_conversation():
    identity = bootstrap_identity_skill()
    identity.payload["init"]["status"] = "complete"

    guidance = loop._render_contact_synthesis_guidance(identity)

    assert guidance is not None
    assert "init.status complete" in guidance
    assert "Hold normal conversation naturally" in guidance


def test_p12_bootstrap_contact_entity_skips_known_contact(monkeypatch):
    admin = registry().resolve_by_name("admin")
    assert admin is not None
    monkeypatch.setattr(loop, "_find_identity_skill", lambda contact_id, registry_obj: admin)
    assert loop._bootstrap_contact_entity(registry(), "admin", "hi") is None


def test_p12_bootstrap_contact_entity_creates_first_contact_step(monkeypatch):
    monkeypatch.setattr(loop, "_find_identity_skill", lambda contact_id, registry_obj: None)
    monkeypatch.setattr(loop, "execute_tool", lambda tool, intent: ("Written: /Users/k2invested/Desktop/cors/skills/user_discord_123.st", 0))
    monkeypatch.setattr(loop, "auto_commit", lambda message, paths=None: ("abc123", None))

    step = loop._bootstrap_contact_entity(registry(), "discord:123", "hello there")

    assert step is not None
    assert step.commit == "abc123"
    assert step.desc == "reprogrammed bootstrap: user_discord_123"
    assert step.content_refs == ["abc123"]


def test_p12_run_turn_bootstraps_unknown_contact_even_on_no_gap_turn(monkeypatch, tmp_path):
    class FakeSession:
        def set_system(self, content: str):
            pass

        def inject(self, content: str, role: str = "user"):
            pass

        def call(self, user_content: str = None) -> str:
            return "No gaps."

    synth_facts = {}

    monkeypatch.setattr(loop, "Session", lambda model=None: FakeSession())
    monkeypatch.setattr(loop, "load_all", lambda path: registry())
    monkeypatch.setattr(loop, "git_head", lambda: "abc123")
    monkeypatch.setattr(loop, "git_tree", lambda: "head tree")
    monkeypatch.setattr(loop, "_find_dangling_gaps", lambda trajectory: [])
    monkeypatch.setattr(loop, "_parse_step_output", lambda raw, step_refs, content_refs: (make_step("origin"), []))
    monkeypatch.setattr(loop, "_find_identity_skill", lambda contact_id, registry_obj: None)
    monkeypatch.setattr(loop, "_save_turn", lambda trajectory, state=None: None)

    def fake_bootstrap(registry_obj, contact_id, user_message, *, contact_profile=None):
        assert contact_id == "discord:123"
        assert user_message == "Hey"
        return make_step("reprogrammed bootstrap: user_discord_123", commit="boot123", content_refs=["boot123"])

    def fake_synth(session, user_message, turn_facts=None):
        synth_facts.update(turn_facts or {})
        return "hello"

    monkeypatch.setattr(loop, "_bootstrap_contact_entity", fake_bootstrap)
    monkeypatch.setattr(loop, "_synthesize", fake_synth)

    response = loop.run_turn(
        "Hey",
        "discord:123",
        traj_file=tmp_path / "trajectory.json",
        chains_file=tmp_path / "chains.json",
        chains_dir=tmp_path / "chains",
    )

    assert response == "hello"
    assert synth_facts["commits"] == ["boot123"]
    assert synth_facts["successful_mutations"] == ["reprogrammed bootstrap: user_discord_123"]


def test_p12_run_turn_bootstraps_before_identity_lookup(monkeypatch, tmp_path):
    class FakeSession:
        def set_system(self, content: str):
            pass

        def inject(self, content: str, role: str = "user"):
            pass

        def call(self, user_content: str = None) -> str:
            return "No gaps."

    initial_registry = registry()
    bootstrapped_skill = Skill(
        hash="boot_hash",
        name="user_discord_123",
        desc="Bootstrap entity for inbound contact discord:123",
        steps=[SkillStep(action="initiate_entity", desc="initiate", post_diff=False, resolve=["identity", "preferences", "access_rules", "init"])],
        source=str(SKILLS_DIR / "entities" / "user_discord_123.st"),
        display_name="user_discord_123",
        trigger="on_contact:discord:123",
        artifact_kind="entity",
        payload={"identity": {"external_id": "discord:123"}, "init": {"status": "pending"}},
    )
    refreshed_registry = SkillRegistry()
    for s in initial_registry.all_skills():
        refreshed_registry.register(s)
    refreshed_registry.register(bootstrapped_skill)

    loads = {"count": 0}

    def fake_load_all(path: str):
        loads["count"] += 1
        return initial_registry if loads["count"] == 1 else refreshed_registry

    seen_identity = {"value": False}

    def fake_find_identity(contact_id, registry_obj):
        if registry_obj is refreshed_registry:
            seen_identity["value"] = True
            return bootstrapped_skill
        return None

    monkeypatch.setattr(loop, "Session", lambda model=None: FakeSession())
    monkeypatch.setattr(loop, "load_all", fake_load_all)
    monkeypatch.setattr(loop, "git_head", lambda: "abc123")
    monkeypatch.setattr(loop, "git_tree", lambda: "head tree")
    monkeypatch.setattr(loop, "_find_dangling_gaps", lambda trajectory: [])
    monkeypatch.setattr(loop, "_parse_step_output", lambda raw, step_refs, content_refs: (make_step("origin"), []))
    monkeypatch.setattr(loop, "_find_identity_skill", fake_find_identity)
    monkeypatch.setattr(loop, "_render_identity", lambda skill_obj: "## Identity")
    monkeypatch.setattr(loop, "_save_turn", lambda trajectory, state=None: None)
    monkeypatch.setattr(loop, "_synthesize", lambda session, user_message, turn_facts=None: "hello")
    monkeypatch.setattr(loop, "_bootstrap_contact_entity", lambda registry_obj, contact_id, user_message, contact_profile=None: make_step("reprogrammed bootstrap: user_discord_123", commit="boot123"))

    response = loop.run_turn(
        "Hey",
        "discord:123",
        traj_file=tmp_path / "trajectory.json",
        chains_file=tmp_path / "chains.json",
        chains_dir=tmp_path / "chains",
    )

    assert response == "hello"
    assert seen_identity["value"] is True


def test_p12_filter_discord_gaps_keeps_only_observation_and_clarify():
    observe_gap = make_gap("observe", vocab="hash_resolve_needed")
    clarify_gap = make_gap("clarify", vocab="clarify_needed")
    reason_gap = make_gap("reason", vocab="reason_needed")
    mutate_gap = make_gap("mutate", vocab="content_needed")

    kept, pruned = loop._filter_discord_gaps([observe_gap, clarify_gap, reason_gap, mutate_gap])

    assert [gap.hash for gap in kept] == [observe_gap.hash, clarify_gap.hash]
    assert pruned == 2
    assert reason_gap.dormant is True
    assert mutate_gap.dormant is True


def test_p12_run_turn_no_gap_discord_turn_triggers_profile_sync(monkeypatch, tmp_path):
    class FakeSession:
        def set_system(self, content: str):
            pass

        def inject(self, content: str, role: str = "user"):
            pass

        def call(self, user_content: str = None) -> str:
            return "No gaps."

    synth_facts = {}
    identity = bootstrap_identity_skill()

    monkeypatch.setattr(loop, "Session", lambda model=None: FakeSession())
    monkeypatch.setattr(loop, "load_all", lambda path: registry())
    monkeypatch.setattr(loop, "git_head", lambda: "abc123")
    monkeypatch.setattr(loop, "git_tree", lambda: "head tree")
    monkeypatch.setattr(loop, "_find_dangling_gaps", lambda trajectory: [])
    monkeypatch.setattr(loop, "_parse_step_output", lambda raw, step_refs, content_refs: (make_step("origin"), []))
    monkeypatch.setattr(loop, "_find_identity_skill", lambda contact_id, registry_obj: identity)
    monkeypatch.setattr(loop, "_render_identity", lambda skill_obj: "## Identity")
    monkeypatch.setattr(loop, "_save_turn", lambda trajectory, state=None: None)
    monkeypatch.setattr(loop, "_bootstrap_contact_entity", lambda registry_obj, contact_id, user_message, contact_profile=None: None)

    def fake_sync(contact_id, user_message, *, identity_skill, registry, trajectory, origin_step):
        assert contact_id == "discord:123"
        assert user_message == "Hey"
        assert identity_skill == identity
        return make_step("reprogrammed discord profile: courtney", commit="sync123")

    def fake_synth(session, user_message, turn_facts=None):
        synth_facts.update(turn_facts or {})
        return "hello"

    monkeypatch.setattr(loop, "_run_no_gap_discord_profile_sync", fake_sync)
    monkeypatch.setattr(loop, "_synthesize", fake_synth)

    response = loop.run_turn(
        "Hey",
        "discord:123",
        traj_file=tmp_path / "trajectory.json",
        chains_file=tmp_path / "chains.json",
        chains_dir=tmp_path / "chains",
    )

    assert response == "hello"
    assert synth_facts["commits"] == ["sync123"]
    assert synth_facts["successful_mutations"] == [
        "reprogramme_needed: deterministic no-gap discord profile sync for courtney"
    ]


def test_p12_run_turn_hydrates_identity_before_first_prediff(monkeypatch, tmp_path):
    class FakeSession:
        def __init__(self):
            self.injected = []
            self.calls = []
            self.identity_before_first_call = False

        def set_system(self, content: str):
            pass

        def inject(self, content: str, role: str = "user"):
            self.injected.append((role, content))

        def call(self, user_content: str = None) -> str:
            if not self.calls:
                self.identity_before_first_call = any("## Identity" in content for _role, content in self.injected)
            self.calls.append(user_content or "")
            return "No gaps."

    session_holder = {}

    def fake_parse(raw, step_refs, content_refs):
        return make_step("origin"), []

    def fake_synth(session, user_message, turn_facts=None):
        return "hello"

    def make_session(model=None):
        session = FakeSession()
        session_holder["session"] = session
        return session

    monkeypatch.setattr(loop, "Session", make_session)
    monkeypatch.setattr(loop, "load_all", lambda path: registry())
    monkeypatch.setattr(loop, "git_head", lambda: "abc123")
    monkeypatch.setattr(loop, "git_tree", lambda: "head tree")
    monkeypatch.setattr(loop, "_find_dangling_gaps", lambda trajectory: [])
    monkeypatch.setattr(loop, "_parse_step_output", fake_parse)
    monkeypatch.setattr(loop, "_find_identity_skill", lambda contact_id, registry_obj: skill("admin"))
    monkeypatch.setattr(loop, "_render_identity", lambda skill_obj: "## Identity")
    monkeypatch.setattr(loop, "_save_turn", lambda trajectory, state=None: None)
    monkeypatch.setattr(loop, "_synthesize", fake_synth)
    monkeypatch.setattr(loop, "_bootstrap_contact_entity", lambda registry_obj, contact_id, user_message, contact_profile=None: None)

    response = loop.run_turn(
        "Hey",
        "admin",
        traj_file=tmp_path / "trajectory.json",
        chains_file=tmp_path / "chains.json",
        chains_dir=tmp_path / "chains",
    )

    assert response == "hello"
    assert session_holder["session"].identity_before_first_call is True


def test_p12_run_turn_injects_clarify_frontier_into_synthesis(monkeypatch, tmp_path):
    class FakeSession:
        def __init__(self):
            self.injected = []

        def set_system(self, content: str):
            pass

        def inject(self, content: str, role: str = "user"):
            self.injected.append((role, content))

        def call(self, user_content: str = None) -> str:
            return json.dumps({
                "gaps": [
                    {
                        "desc": "Need the target profile name before proceeding.",
                        "vocab": "clarify_needed",
                        "relevance": 0.9,
                        "confidence": 0.9,
                    }
                ]
            })

    seen = {"guidance": None}

    def fake_synth(session, user_message, turn_facts=None):
        for role, content in session.injected:
            if role == "system" and "## Clarify Frontier" in content:
                seen["guidance"] = content
        return "clarify"

    monkeypatch.setattr(loop, "Session", lambda model=None: FakeSession())
    monkeypatch.setattr(loop, "load_all", lambda path: registry())
    monkeypatch.setattr(loop, "git_head", lambda: "abc123")
    monkeypatch.setattr(loop, "git_tree", lambda: "head tree")
    monkeypatch.setattr(loop, "_find_dangling_gaps", lambda trajectory: [])
    monkeypatch.setattr(loop, "_find_identity_skill", lambda contact_id, registry_obj: skill("admin"))
    monkeypatch.setattr(loop, "_render_identity", lambda skill_obj: "## Identity")
    monkeypatch.setattr(loop, "_save_turn", lambda trajectory, state=None: None)
    monkeypatch.setattr(loop, "_synthesize", fake_synth)

    response = loop.run_turn(
        "Tell me about him",
        "admin",
        traj_file=tmp_path / "trajectory.json",
        chains_file=tmp_path / "chains.json",
        chains_dir=tmp_path / "chains",
    )

    assert response == "clarify"
    assert seen["guidance"] is not None
    assert "Need the target profile name before proceeding." in seen["guidance"]
    assert "Do not continue the task" in seen["guidance"]


def test_p12_inline_reprogramme_does_not_trigger_heartbeat():
    class FakeSession:
        def __init__(self):
            self.injected = []

        def inject(self, content: str, role: str = "user"):
            self.injected.append(content)

        def call(self, user_content: str = None) -> str:
            return json.dumps({
                "artifact_kind": "entity",
                "name": "admin",
                "desc": "updated admin preferences",
            })

    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap("persist admin preference", content_refs=[skill("admin").hash], vocab="reprogramme_needed")
    entry = SimpleNamespace(gap=gap, chain_id="chain1")
    session = FakeSession()

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "",
        execute_tool=lambda tool, params: ("Written: /Users/k2invested/Desktop/cors/skills/admin.st", 0),
        auto_commit=lambda message, paths=None: ("abc123", None),
        parse_step_output=lambda raw, step_refs, content_refs, chain_id=None: (make_step("noop"), []),
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: None,
        extract_written_path=lambda output: "/Users/k2invested/Desktop/cors/skills/admin.st",
        is_reprogramme_intent=lambda intent: True,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: "semantic_tree:skill_package:hash_edit\nname: hash_edit" if content_refs else None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: ["  validator: ok"],
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.step_result is not None
    assert outcome.step_result.commit == "abc123"
    assert compiler.needs_heartbeat() is False


def test_p12_inline_reprogramme_emits_postcondition_assessment_before_synth():
    class FakeSession:
        def __init__(self):
            self.injected = []

        def inject(self, content: str, role: str = "user"):
            self.injected.append(content)

        def call(self, user_content: str = None) -> str:
            return json.dumps({
                "artifact_kind": "entity",
                "name": "admin",
                "desc": "updated admin preferences",
            })

    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap("persist admin preference", content_refs=[skill("admin").hash], vocab="reprogramme_needed")
    entry = SimpleNamespace(gap=gap, chain_id="chain1")
    session = FakeSession()

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "",
        execute_tool=lambda tool, params: ("Written: /Users/k2invested/Desktop/cors/skills/admin.st", 0),
        auto_commit=lambda message, paths=None: ("abc123", None),
        parse_step_output=lambda raw, step_refs, content_refs, chain_id=None: (make_step("noop"), []),
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: None,
        extract_written_path=lambda output: "/Users/k2invested/Desktop/cors/skills/admin.st",
        is_reprogramme_intent=lambda intent: True,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: "semantic_tree:skill_package:hash_edit\nname: hash_edit" if content_refs else None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: ["skills/admin.st [step] +1 -0", "  validator.status: ok"],
        step_assessment=lambda before, after, path=None: ["  validator: ok"],
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.step_result is not None
    postconditions = [step for step in traj.steps.values() if step.desc == "postcondition: persist admin preference"]
    assert len(postconditions) == 1
    assert postconditions[0].assessment == ["skills/admin.st [step] +1 -0", "  validator.status: ok"]
    assert len(postconditions[0].gaps) == 1
    assert postconditions[0].gaps[0].vocab == "hash_resolve_needed"


def test_p12_bash_needed_commit_postcondition_resolves_bot_log(monkeypatch):
    class FakeSession:
        def __init__(self):
            self.injected = []

        def inject(self, content: str, role: str = "user"):
            self.injected.append(content)

        def call(self, user_content: str = None) -> str:
            return json.dumps({"command": "pytest -q"})

    class Result:
        stdout = "tests passed"
        stderr = ""
        returncode = 0

    monkeypatch.setattr(execution_engine_module.subprocess, "run", lambda *args, **kwargs: Result())

    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap("run test suite", vocab="bash_needed")
    entry = SimpleNamespace(gap=gap, chain_id="chain1")
    session = FakeSession()

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "resolved activation context",
        execute_tool=lambda tool, params: ("", 0),
        auto_commit=lambda message, paths=None: ("abc123", None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: raw,
        extract_written_path=lambda output: None,
        is_reprogramme_intent=loop._is_reprogramme_intent,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: "semantic_tree:skill_package:hash_edit\nname: hash_edit" if content_refs else None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=loop._emit_reason_skill,
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: ["bot log pending"],
        step_assessment=lambda before, after, path=None: [],
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.step_result is not None
    assert outcome.step_result.commit == "abc123"
    postconditions = [step for step in traj.steps.values() if step.desc == "postcondition: run test suite"]
    assert len(postconditions) == 1
    assert postconditions[0].content_refs == ["bot.log"]
    assert len(postconditions[0].gaps) == 1
    assert postconditions[0].gaps[0].content_refs == ["bot.log"]
    assert postconditions[0].gaps[0].vocab == "hash_resolve_needed"


def test_p12_bash_needed_infers_commit_paths_for_rm(monkeypatch):
    class FakeSession:
        def inject(self, content: str, role: str = "user"):
            pass

        def call(self, user_content: str = None) -> str:
            return json.dumps({"command": "rm skills/entities/clinton.st"})

    captured_paths: list[list[str] | None] = []

    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap("delete clinton file", vocab="bash_needed")
    entry = SimpleNamespace(gap=gap, chain_id="chain1")

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "",
        execute_tool=lambda tool, params: ("[1 step(s) completed, no output]", 0),
        auto_commit=lambda message, paths=None: (captured_paths.append(paths) or True) and ("abc123", None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: raw,
        extract_written_path=lambda output: None,
        is_reprogramme_intent=loop._is_reprogramme_intent,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=loop._emit_reason_skill,
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=FakeSession(),
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert captured_paths == [["skills/entities/clinton.st"]]


def test_p12_bash_needed_without_commit_still_emits_log_postcondition(monkeypatch):
    class FakeSession:
        def __init__(self):
            self.injected = []

        def inject(self, content: str, role: str = "user"):
            self.injected.append(content)

        def call(self, user_content: str = None) -> str:
            return json.dumps({"command": "pytest -q"})

    class Result:
        stdout = "tests passed"
        stderr = ""
        returncode = 0

    monkeypatch.setattr(execution_engine_module.subprocess, "run", lambda *args, **kwargs: Result())

    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap("run test suite", vocab="bash_needed")
    entry = SimpleNamespace(gap=gap, chain_id="chain1")
    session = FakeSession()

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "resolved activation context",
        execute_tool=lambda tool, params: ("", 0),
        auto_commit=lambda message, paths=None: (None, None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: raw,
        extract_written_path=lambda output: None,
        is_reprogramme_intent=loop._is_reprogramme_intent,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: "semantic_tree:stub\nname: foundation" if content_refs else None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=loop._emit_reason_skill,
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.step_result is not None
    assert outcome.step_result.commit is None
    assert outcome.step_result.desc == "executed: run test suite"
    postconditions = [step for step in traj.steps.values() if step.desc == "postcondition: run test suite"]
    assert len(postconditions) == 1
    assert postconditions[0].content_refs == ["bot.log"]
    assert len(postconditions[0].gaps) == 1
    assert postconditions[0].gaps[0].content_refs == ["bot.log"]
    assert postconditions[0].gaps[0].vocab == "hash_resolve_needed"


def test_p12_hash_resolve_runs_in_deterministic_branch_and_can_surface_follow_on_mutation():
    class FakeSession:
        def __init__(self):
            self.prompts = []
            self.injected = []

        def inject(self, content: str, role: str = "user"):
            self.injected.append((role, content))

        def call(self, user_content: str = None) -> str:
            self.prompts.append(user_content or "")
            return (
                'Observed the current entity context.\n'
                '{"gaps":[{"desc":"Update the user profile to note that Clinton is their brother and reference clinton.st.",'
                '"vocab":"reprogramme_needed","relevance":0.95,"confidence":0.9}]}'
            )

    traj = Trajectory()
    prerequisite_gap = make_gap(
        "Need to resolve the user's current entity (.st) file in order to update their profile to note that their brother is Clinton, referencing clinton.st.",
        content_refs=[skill("admin").hash, skill("clinton").hash],
        vocab="hash_resolve_needed",
        relevance=0.95,
        confidence=0.9,
    )
    origin_step = make_step("origin", gaps=[prerequisite_gap])
    traj.append(origin_step)

    compiler = Compiler(traj)
    compiler.emit_origin_gaps(origin_step)
    entry, signal = compiler.next()

    assert entry is not None
    session = FakeSession()

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "## Existing entity data",
        execute_tool=lambda tool, params: ("", 0),
        auto_commit=lambda message, paths=None: (None, None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: None,
        extract_command=lambda raw: None,
        extract_written_path=lambda output: None,
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: "semantic_tree:stub\nname: foundation" if content_refs else None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
        render_session_context=lambda trajectory, registry_obj, user_message, active_chain_id=None, active_gap=None: "## Session Context\nactive session",
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=signal,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.step_result is not None
    assert any("surface the actual next gap now" in prompt for prompt in session.prompts)
    assert compiler.ledger.stack[-1].gap.vocab == "reprogramme_needed"
    assert "clinton" in compiler.ledger.stack[-1].gap.desc.lower()


def test_p12_resolve_current_gap_marks_trajectory_gap_resolved_for_cross_turn_resume():
    traj = Trajectory()
    gap = make_gap("persist alias", vocab="reprogramme_needed", relevance=0.9, confidence=0.9)
    origin = make_step("origin", gaps=[gap])
    traj.append(origin)

    compiler = Compiler(traj)
    compiler.emit_origin_gaps(origin)
    entry, _signal = compiler.next()

    assert entry is not None
    compiler.resolve_current_gap(gap.hash)

    resolved_gap = traj.resolve_gap(gap.hash)
    assert resolved_gap is not None
    assert resolved_gap.resolved is True
    assert loop._find_dangling_gaps(traj) == []


def test_p12_find_dangling_gaps_only_returns_carry_forward_gaps():
    traj = Trajectory()
    carry = make_gap("carry me", vocab="reason_needed")
    carry.carry_forward = True
    plain = make_gap("drop me", vocab="hash_resolve_needed")
    traj.append(make_step("resume", gaps=[carry, plain]))

    dangling = loop._find_dangling_gaps(traj)
    assert [gap.desc for gap in dangling] == ["carry me"]


def test_p12_find_dangling_gaps_ignores_clarify_even_if_marked_carry_forward():
    traj = Trajectory()
    clarify = make_gap("need user detail", vocab="clarify_needed")
    clarify.carry_forward = True
    traj.append(make_step("clarify", gaps=[clarify]))

    assert loop._find_dangling_gaps(traj) == []


def test_p12_find_dangling_gaps_dedupes_by_hash():
    traj = Trajectory()
    gap = make_gap("same persisted gap", vocab="reason_needed")
    gap.carry_forward = True
    clone = Gap(
        hash=gap.hash,
        desc=gap.desc,
        content_refs=list(gap.content_refs),
        step_refs=list(gap.step_refs),
        vocab=gap.vocab,
        vocab_score=gap.vocab_score,
        carry_forward=True,
    )
    traj.append(make_step("one", gaps=[gap]))
    traj.append(make_step("two", gaps=[clone]))

    dangling = loop._find_dangling_gaps(traj)
    assert len(dangling) == 1
    assert dangling[0].hash == gap.hash


def test_p12_collect_clarify_frontier_merges_current_and_active_deduped():
    traj = Trajectory()
    compiler = Compiler(traj)
    current = make_gap("question one", vocab="clarify_needed")
    current.turn_id = 5
    other = make_gap("question two", vocab="clarify_needed")
    other.turn_id = 5
    dup = Gap(
        hash=current.hash,
        desc=current.desc,
        content_refs=list(current.content_refs),
        step_refs=list(current.step_refs),
        vocab="clarify_needed",
        turn_id=5,
    )
    compiler.ledger.stack.append(SimpleNamespace(gap=other))
    compiler.ledger.stack.append(SimpleNamespace(gap=dup))

    merged = execution_engine_module._collect_clarify_frontier(compiler, current, current_turn=5)
    assert [gap.desc for gap in merged] == ["question one", "question two"]


def test_p12_collect_clarify_frontier_is_turn_bounded():
    traj = Trajectory()
    compiler = Compiler(traj)
    current = make_gap("current question", vocab="clarify_needed", turn_id=9)
    same_turn = make_gap("same turn question", vocab="clarify_needed", turn_id=9)
    old_turn = make_gap("old turn question", vocab="clarify_needed", turn_id=8)
    compiler.ledger.stack.append(SimpleNamespace(gap=same_turn))
    compiler.ledger.stack.append(SimpleNamespace(gap=old_turn))

    merged = execution_engine_module._collect_clarify_frontier(compiler, current, current_turn=9)
    assert [gap.desc for gap in merged] == ["current question", "same turn question"]


def test_p12_build_clarify_frontier_step_has_single_canonical_desc_and_refs():
    origin = make_step("origin")
    gap1 = make_gap("question one", content_refs=["a"], step_refs=["s1"], vocab="clarify_needed")
    gap2 = make_gap("question two", content_refs=["b"], step_refs=["s2"], vocab="clarify_needed")

    step = execution_engine_module._build_clarify_frontier_step(
        origin_step=origin,
        merged_gaps=[gap1, gap2],
        chain_id="chain1",
    )

    assert step.desc.startswith("clarify frontier:")
    assert step.step_refs == [origin.hash, "s1", "s2"]
    assert step.content_refs == ["a", "b"]
    assert len(step.gaps) == 2


def test_p12_clarify_iteration_emits_single_merged_step():
    class FakeSession:
        def inject(self, content: str, role: str = "user"):
            pass

        def call(self, user_content: str = None) -> str:
            return ""

    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap("question one", content_refs=["a"], vocab="clarify_needed")
    extra = make_gap("question two", content_refs=["b"], vocab="clarify_needed")
    entry = SimpleNamespace(gap=gap, chain_id="chain1")
    compiler.ledger.stack.append(SimpleNamespace(gap=extra))
    session = FakeSession()

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "resolved activation context",
        execute_tool=lambda tool, params: ("", 0),
        auto_commit=lambda message, paths=None: (None, None),
        parse_step_output=lambda raw, step_refs, content_refs, chain_id=None: (make_step("noop"), []),
        extract_json=lambda raw: None,
        extract_command=lambda raw: None,
        extract_written_path=lambda output: None,
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: "semantic_tree:stub\nname: foundation" if content_refs else None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
        render_session_context=lambda trajectory, registry_obj, user_message, active_chain_id=None, active_gap=None: "## Session Context\nactive session",
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.control == "break"
    assert outcome.step_result is not None
    assert len(outcome.step_result.gaps) == 2
    assert outcome.step_result.desc.startswith("clarify frontier:")
    assert outcome.step_result.content_refs == ["a", "b"]
    assert "question one" in outcome.step_result.desc
    assert "question two" in outcome.step_result.desc


def test_p12_persist_forced_synth_frontier_clones_active_ledger_gaps():
    traj = Trajectory()
    compiler = Compiler(traj, current_turn=3)
    origin_gap = make_gap("pending", vocab="hash_resolve_needed", relevance=0.9, confidence=0.9)
    origin = make_step("origin", gaps=[origin_gap])
    traj.append(origin)
    compiler.emit_origin_gaps(origin)

    forced = loop._persist_forced_synth_frontier(traj, compiler, origin, current_turn=3)

    assert forced is not None
    assert forced.desc == "forced synth: unresolved frontier persisted for next turn"
    assert len(forced.gaps) == 1
    assert forced.gaps[0].carry_forward is True
    assert forced.gaps[0].desc == "pending"
    assert forced.gaps[0].turn_id == 3


def test_p12_reason_needed_runs_inline_and_emits_child_gaps():
    class FakeSession:
        def __init__(self):
            self.calls = 0
            self.injected = []

        def inject(self, content: str, role: str = "user"):
            self.injected.append(content)

        def call(self, user_content: str = None) -> str:
            self.calls += 1
            return (
                "Inline reasoning complete.\n"
                '{"gaps":[{"desc":"create research workflow artifact","vocab":"content_needed","relevance":0.9,"confidence":0.9}]}'
            )

    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap("design the next clean research plan", vocab="reason_needed")
    entry = SimpleNamespace(gap=gap, chain_id="chain1")
    session = FakeSession()

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "resolved activation context",
        execute_tool=lambda tool, params: ("", 0),
        auto_commit=lambda message, paths=None: (None, None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: None,
        extract_command=lambda raw: None,
        extract_written_path=lambda output: None,
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: "semantic_tree:stub\nname: foundation" if content_refs else None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
        render_session_context=lambda trajectory, registry_obj, user_message, active_chain_id=None, active_gap=None: "## Session Context\nactive session",
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.step_result is not None
    assert outcome.step_result.desc.startswith("Inline reasoning complete.")
    assert session.calls == 1
    assert compiler.needs_heartbeat() is False
    assert any("## Session Context" in content for content in session.injected)
    assert not any("Delegation Preferences" in content for content in session.injected)
    assert compiler.ledger.stack[-1].gap.vocab == "content_needed"


def test_p12_reason_needed_prompt_says_collect_foundations_before_new_workflow_write():
    class FakeSession:
        def __init__(self):
            self.calls = 0
            self.injected = []
            self.prompts = []

        def inject(self, content: str, role: str = "user"):
            self.injected.append(content)

        def call(self, user_content: str = None) -> str:
            self.calls += 1
            self.prompts.append(user_content or "")
            return "Inline reasoning complete.\n{}"

    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap(
        "Create a new research workflow in skills/actions/research.st triggered by research_needed.",
        vocab="reason_needed",
    )
    entry = SimpleNamespace(gap=gap, chain_id="chain1")
    session = FakeSession()

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "",
        execute_tool=lambda tool, params: ("", 0),
        auto_commit=lambda message, paths=None: (None, None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: {},
        extract_command=lambda raw: None,
        extract_written_path=lambda output: None,
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: "semantic_tree:stub\nname: foundation" if content_refs else None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
        render_session_context=lambda trajectory, registry_obj, user_message, active_chain_id=None, active_gap=None: "## Session Context\nactive session",
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert session.prompts
    assert any("Use reason_needed for open specifications, competing interpretations, and deciding the next concrete move." in prompt for prompt in session.prompts)


def test_p12_reason_needed_keeps_foundation_judgment_inside_first_iteration():
    class FakeSession:
        def __init__(self):
            self.calls = 0
            self.injected = []

        def inject(self, content: str, role: str = "user"):
            self.injected.append(content)

        def call(self, user_content: str = None) -> str:
            self.calls += 1
            return json.dumps({
                "gaps": [
                    {
                        "desc": "Inspect the committed foundations already present before deciding whether a research workflow or supporting tool should be created.",
                        "vocab": "hash_resolve_needed",
                        "content_refs": ["skills/actions/research.st", skill("hash_edit").hash],
                        "relevance": 0.9,
                        "confidence": 0.8,
                    }
                ]
            })

    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap(
        "Create a new research workflow in skills/actions/research.st triggered by research_needed.",
        vocab="reason_needed",
    )
    entry = SimpleNamespace(gap=gap, chain_id="chain1")
    session = FakeSession()

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "",
        execute_tool=lambda tool, params: ("", 0),
        auto_commit=lambda message, paths=None: ("abc123", None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: None,
        extract_written_path=loop._extract_written_path,
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: f"semantic_tree:skill_package:{skill('hash_edit').hash}\nname: hash_edit" if content_refs else None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
        render_session_context=lambda trajectory, registry_obj, user_message, active_chain_id=None, active_gap=None: "## Session Context\nactive session",
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.step_result is not None
    assert outcome.step_result.gaps
    assert outcome.step_result.gaps[0].vocab == "hash_resolve_needed"
    assert outcome.step_result.commit is None
    assert session.calls == 1


def test_p12_reason_needed_cannot_surface_reprogramme_for_action_tree():
    class FakeSession:
        def __init__(self):
            self.calls = 0
            self.injected = []
            self.prompts = []

        def inject(self, content: str, role: str = "user"):
            self.injected.append(content)

        def call(self, user_content: str = None) -> str:
            self.calls += 1
            self.prompts.append(user_content or "")
            return (
                "Inline reasoning complete.\n"
                '{"gaps":[{"desc":"Author a corrected semantic_skeleton.v1 action package for skills/actions/research.st.",'
                '"vocab":"reprogramme_needed","relevance":0.9,"confidence":0.9}]}'
            )

    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap("repair research workflow", vocab="reason_needed")
    entry = SimpleNamespace(gap=gap, chain_id="chain1")
    session = FakeSession()

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "",
        execute_tool=lambda tool, params: ("", 0),
        auto_commit=lambda message, paths=None: (None, None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: None,
        extract_command=lambda raw: None,
        extract_written_path=lambda output: None,
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=loop._load_tree_policy,
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: "semantic_tree:stub\nname: foundation" if content_refs else None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.step_result is not None
    assert compiler.ledger.stack[-1].gap.vocab == "reason_needed"
    assert "skills/actions/research.st" in compiler.ledger.stack[-1].gap.desc
    assert any("Use reason_needed for open specifications, competing interpretations, and deciding the next concrete move." in content for content in session.prompts)


def test_p12_reprogramme_trigger_assignment_reroutes_to_reason_needed():
    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap(
        "Assign on_vocab:research_needed as the public trigger for the highest-order research workflow in skills/actions/research.st.",
        vocab="reprogramme_needed",
        content_refs=["skills/actions/research.st"],
    )
    entry = SimpleNamespace(gap=gap, chain_id="chain1")

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "",
        execute_tool=lambda tool, params: ("should not run", 1),
        auto_commit=lambda message, paths=None: (None, None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: None,
        extract_command=lambda raw: None,
        extract_written_path=lambda output: None,
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=loop._load_tree_policy,
        match_policy=loop._match_policy,
        resolve_entity=lambda content_refs, registry_obj, trajectory: "semantic_tree:stub\nname: foundation" if content_refs else None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=loop._emit_reason_skill,
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=SimpleNamespace(inject=lambda *args, **kwargs: None, call=lambda *args, **kwargs: ""),
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.control == "continue"
    assert compiler.ledger.stack[-1].gap.vocab == "reason_needed"
    assert compiler.ledger.stack[-1].gap.route_mode is None


def test_p12_st_builder_cli_reports_malformed_skeleton_as_validation_error():
    payload = {
        "version": "semantic_skeleton.v1",
        "artifact": {"kind": "action", "protected_kind": "action"},
        "name": "research",
        "desc": "Malformed research workflow",
        "trigger": "manual",
        "refs": {},
        "root": "phase_root",
        "phases": ["phase_root"],
        "closure": {"success": {}},
    }

    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "st_builder.py")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=ROOT,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 1
    assert "Validation errors:" in output
    assert "phase 0 must be an object" in output
    assert "Traceback" not in output


def test_p12_hash_edit_tool_write_reroutes_to_tool_needed():
    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap(
        "Patch tools/research_web.py to add domain-aware scraping.",
        vocab="hash_edit_needed",
        content_refs=["tools/research_web.py"],
    )
    entry = SimpleNamespace(gap=gap, chain_id="chain1")

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "",
        execute_tool=lambda tool, params: ("should not run", 1),
        auto_commit=lambda message, paths=None: (None, None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: None,
        extract_command=lambda raw: None,
        extract_written_path=lambda output: None,
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=loop._load_tree_policy,
        match_policy=loop._match_policy,
        resolve_entity=lambda content_refs, registry_obj, trajectory: f"semantic_tree:skill_package:{skill('hash_edit').hash}\nname: hash_edit" if content_refs else None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=loop._emit_reason_skill,
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=SimpleNamespace(inject=lambda *args, **kwargs: None, call=lambda *args, **kwargs: ""),
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.control == "continue"
    assert compiler.ledger.stack[-1].gap.vocab == "tool_needed"


def test_p12_content_needed_tool_write_reroutes_to_tool_needed_from_desc():
    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap(
        "Create tools/research_image.py as a foundational workflow tool for image-aware research classification.",
        vocab="content_needed",
    )
    entry = SimpleNamespace(gap=gap, chain_id="chain1")

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "",
        execute_tool=lambda tool, params: ("should not run", 1),
        auto_commit=lambda message, paths=None: (None, None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: None,
        extract_command=lambda raw: None,
        extract_written_path=lambda output: None,
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=loop._load_tree_policy,
        match_policy=loop._match_policy,
        resolve_entity=lambda content_refs, registry_obj, trajectory: None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=loop._emit_reason_skill,
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=SimpleNamespace(inject=lambda *args, **kwargs: None, call=lambda *args, **kwargs: ""),
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.control == "continue"
    assert compiler.ledger.stack[-1].gap.vocab == "tool_needed"


def test_p12_turn_outcome_facts_forbid_future_write_promises_without_success():
    rendered = loop._render_turn_outcome_facts({
        "commits": [],
        "successful_mutations": [],
        "attempted_mutations": [],
        "rogue_failures": [],
    })

    assert "Do not say 'I'll update', 'I will proceed'" in rendered


def test_p12_turn_outcome_facts_forbid_ready_claims_after_failed_authoring():
    rendered = loop._render_turn_outcome_facts({
        "commits": [],
        "successful_mutations": [],
        "attempted_mutations": ["reason_needed: create skills/actions/research.st"],
        "rogue_failures": ["reason actualization failed: create skills/actions/research.st | source=st_builder | kind=validation_error"],
    })

    assert "attempted but not validated or persisted" in rendered
    assert "ready, live, built, or complete" in rendered


def test_p12_turn_outcome_facts_treat_persisted_frontier_as_unresolved():
    rendered = loop._render_turn_outcome_facts({
        "commits": [],
        "successful_mutations": [],
        "attempted_mutations": ["reason_needed: create skills/actions/research.st"],
        "rogue_failures": [],
        "persisted_frontiers": ["forced frontier: create skills/actions/research.st"],
    })

    assert "Persisted unresolved frontiers:" in rendered
    assert "still structurally invalid, unresolved, exhausted, or persisted for a later turn" in rendered
    assert "instead of saying it is ready to be built" in rendered


def test_p12_hash_resolve_is_not_observation_only_auto_close():
    assert "hash_resolve_needed" not in loop.OBSERVATION_ONLY_VOCAB


def test_p12_identity_linkage_clarify_upgrades_to_identity_resolve():
    clarify_gap = make_gap(
        "User asked about their brother, but the identity of their brother is not specified or linked to any known entity. Clarification is needed to proceed.",
        vocab="clarify_needed",
        relevance=0.9,
        confidence=0.8,
    )
    upgraded = loop._upgrade_identity_linkage_clarify_gaps(
        user_message="Tell me about my brother",
        origin_gaps=[clarify_gap],
        identity_skill=skill("admin"),
    )

    assert len(upgraded) == 1
    assert upgraded[0].vocab == "hash_resolve_needed"
    assert upgraded[0].content_refs == [skill("admin").hash]
    assert "Tell me about my brother" in upgraded[0].desc


def test_p12_reason_needed_does_not_actualize_new_action_skeleton_directly():
    class FakeSession:
        def __init__(self):
            self.calls = 0
            self.injected = []

        def inject(self, content: str, role: str = "user"):
            self.injected.append(content)

        def call(self, user_content: str = None) -> str:
            self.calls += 1
            return json.dumps({
                "version": "semantic_skeleton.v1",
                "artifact": {"kind": "action", "protected_kind": "action", "lineage": "research", "version_strategy": "hash_pinned"},
                "name": "research",
                "desc": "Research workflow",
                "trigger": "on_vocab:research_needed",
                "refs": {},
                "root": "phase_root",
                "phases": [
                    {
                        "id": "phase_root",
                        "label": "Observe request",
                        "source_step": {
                            "action": "observe_request",
                            "desc": "Observe the research request and scope it.",
                            "vocab": "hash_resolve_needed",
                            "relevance": 1.0,
                            "post_diff": False,
                        },
                    }
                ],
                "closure": {"success": {}},
            })

    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap(
        "Create a new workflow file at skills/actions/research.st that implements a research workflow triggered by the vocab research_needed.",
        vocab="reason_needed",
        content_refs=["tools/research_web.py"],
    )
    entry = SimpleNamespace(gap=gap, chain_id="chain1")
    session = FakeSession()

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "",
        execute_tool=lambda tool, params: ("Written: /Users/k2invested/Desktop/cors/skills/actions/research.st", 0),
        auto_commit=lambda message, paths=None: ("abc123", None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: None,
        extract_written_path=loop._extract_written_path,
        is_reprogramme_intent=loop._is_reprogramme_intent,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: "semantic_tree:stub\nname: foundation" if content_refs else None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=loop._emit_reason_skill,
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: ["skills/actions/research.st [step] +10 -0"],
        step_assessment=lambda before, after, path=None: [],
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.step_result is not None
    assert outcome.step_result.commit is None
    assert compiler.ledger.is_empty()


def test_p12_validate_semantic_skeleton_intent_rejects_public_trigger_before_top_layer():
    intent = {
        "version": "semantic_skeleton.v1",
        "artifact": {"kind": "action", "protected_kind": "action"},
        "name": "research",
        "trigger": "on_vocab:research_needed",
        "next_layer_desc": "Build the higher-order orchestration layer.",
    }

    errors = st_builder_module.validate_semantic_skeleton_intent(intent)
    assert any("may not claim the final public on_vocab trigger" in e for e in errors)


def test_p12_lower_step_chain_builds_valid_action_spine():
    intent = {
        "version": "step_chain.v1",
        "artifact": {"kind": "action", "protected_kind": "action"},
        "name": "test",
        "desc": "Execute project tests.",
        "trigger": "on_vocab:test_needed",
        "steps": [
            {
                "id": "run_tests",
                "kind": "mutate",
                "goal": "Execute all relevant test scripts.",
                "gap_template": {
                    "desc": "Compose a command that executes all relevant test scripts.",
                    "content_refs": [],
                    "step_refs": [],
                },
                "manifestation": {
                    "execution_mode": "runtime_vocab",
                    "runtime_vocab": "bash_needed",
                },
                "allowed_vocab": ["bash_needed"],
                "relevance": 1.0,
                "post_diff": True,
            }
        ],
    }

    lowered, artifact_kind, existing_ref = st_builder_module.lower_step_chain(intent)

    assert artifact_kind == "action"
    assert existing_ref is None
    assert lowered["root"] == "run_tests"
    assert lowered["closure"]["success"]["requires_terminal"] == "phase_done"
    assert lowered["phases"][0]["transitions"] == {"on_close": "phase_done"}
    assert lowered["phases"][0]["manifestation"]["runtime_vocab"] == "bash_needed"
    assert lowered["steps"][0]["vocab"] == "bash_needed"
    assert st_builder_module.validate_st(lowered, artifact_kind="action") == []


def test_p12_manifest_engine_build_semantic_tree_uses_normalized_path_for_step_chain():
    doc = {
        "version": "step_chain.v1",
        "artifact": {"kind": "action", "protected_kind": "action"},
        "name": "test",
        "desc": "Execute project tests.",
        "trigger": "on_vocab:test_needed",
        "steps": [
            {
                "id": "run_tests",
                "kind": "mutate",
                "goal": "Execute all relevant test scripts.",
                "gap_template": {
                    "desc": "Compose a command that executes all relevant test scripts.",
                    "content_refs": [],
                    "step_refs": [],
                },
                "manifestation": {
                    "execution_mode": "runtime_vocab",
                    "runtime_vocab": "bash_needed",
                },
                "allowed_vocab": ["bash_needed"],
                "relevance": 1.0,
                "post_diff": True,
            }
        ],
    }

    tree = manifest_engine_module.build_semantic_tree(doc, source_type="working_step_chain", source_ref="test")

    assert tree["version"] == "semantic_tree.v1"
    assert tree["package"]["name"] == "test"
    assert tree["package"]["closure"]["success"]["requires_terminal"] == "phase_done"
    assert tree["nodes"][0]["gap"]["runtime_vocab"] == "bash_needed"


def test_p12_validate_step_chain_intent_rejects_public_trigger_before_top_layer():
    intent = {
        "version": "step_chain.v1",
        "artifact": {"kind": "action", "protected_kind": "action"},
        "name": "research",
        "trigger": "on_vocab:research_needed",
        "next_layer_desc": "Build the higher-order orchestration layer.",
        "steps": [
            {
                "id": "observe_request",
                "goal": "Observe request",
                "gap_template": {"desc": "Observe request"},
                "manifestation": {"runtime_vocab": "hash_resolve_needed"},
            }
        ],
    }

    errors = st_builder_module.validate_step_chain_intent(intent)
    assert any("may not claim the final public on_vocab trigger" in e for e in errors)


def test_p12_reason_needed_handles_authoring_like_gap_as_plain_judgment():
    class FakeSession:
        def __init__(self):
            self.prompts = []

        def inject(self, content: str, role: str = "user"):
            self.prompts.append(content)

        def call(self, user_content: str = None) -> str:
            self.prompts.append(user_content or "")
            return json.dumps(
                {
                    "gaps": [
                        {
                            "desc": "Create the workflow file at skills/actions/test.st with a single command execution gap for test execution.",
                            "vocab": "content_needed",
                            "content_refs": ["skills/actions/test.st"],
                            "relevance": 0.95,
                            "confidence": 0.9,
                        }
                    ]
                }
            )

    traj = Trajectory()
    gap = make_gap(
        "Create a new workflow file at skills/actions/test.st that executes all tests via test_needed.",
        vocab="reason_needed",
        content_refs=["skills/actions/test.st"],
    )
    origin_step = make_step("origin", gaps=[gap])
    traj.append(origin_step)
    chain = Chain(hash="chain1", origin_gap=gap.hash, steps=[origin_step.hash])
    traj.add_chain(chain)
    compiler = Compiler(traj)
    compiler.active_chain = chain
    entry = SimpleNamespace(gap=gap, chain_id="chain1")
    session = FakeSession()

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "",
        execute_tool=lambda tool, params: ("", 0),
        auto_commit=lambda message, paths=None: (None, None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: None,
        extract_written_path=loop._extract_written_path,
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
        render_session_context=lambda trajectory, registry_obj, user_message, active_chain_id=None, active_gap=None: "## Session Context\nactive session",
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.step_result is not None
    assert outcome.step_result.gaps
    assert outcome.step_result.gaps[0].vocab == "content_needed"
    assert "Use reason_needed for open specifications" in "\n".join(session.prompts)
    assert not any(prompt.startswith("## Chain Construction Spec") for prompt in session.prompts)


def test_p12_reason_needed_authoring_like_gap_keeps_plain_chain_state():
    class FakeSession:
        def inject(self, content: str, role: str = "user"):
            pass

        def call(self, user_content: str = None) -> str:
            return json.dumps(
                {
                    "gaps": [
                        {
                            "desc": "Inspect the existing workflow/tool foundations needed before creating skills/actions/test.st.",
                            "vocab": "hash_resolve_needed",
                            "content_refs": ["skills/actions/test.st"],
                            "relevance": 0.9,
                            "confidence": 0.8,
                        }
                    ]
                }
            )

    traj = Trajectory()
    gap = make_gap(
        "Need to create a new skills/actions/test.st flow with a single command exec gap.",
        vocab="reason_needed",
        content_refs=["skills/actions/test.st"],
    )
    origin_step = make_step("origin", gaps=[gap])
    traj.append(origin_step)
    chain = Chain(hash="chain1", origin_gap=gap.hash, steps=[origin_step.hash])
    traj.add_chain(chain)
    compiler = Compiler(traj)
    compiler.active_chain = chain
    entry = SimpleNamespace(gap=gap, chain_id="chain1")
    session = FakeSession()

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "",
        execute_tool=lambda tool, params: ("", 0),
        auto_commit=lambda message, paths=None: (None, None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: None,
        extract_written_path=loop._extract_written_path,
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
        render_session_context=lambda trajectory, registry_obj, user_message, active_chain_id=None, active_gap=None: "## Session Context\nactive session",
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.step_result is not None
    assert outcome.step_result.gaps[0].vocab == "hash_resolve_needed"


def test_p12_action_foundations_render_skills_tools_and_default_contracts():
    rendered = action_foundations_module.render_action_foundations(
        registry=registry(),
        chains_dir=ROOT / "chains",
        cors_root=ROOT,
        tool_map=loop.TOOL_MAP,
        git=lambda cmd, cwd=None: "0123456789abcdef0123456789abcdef01234567",
    )

    assert rendered.startswith("## Action Foundations")
    assert f"{skill('hash_edit').hash} kind=action_package surface=semantic_tree" in rendered
    assert "activation=name:hash_edit_needed default_gap=hash_edit_needed" in rendered
    assert "0123456789ab kind=tool_blob surface=described_blob" in rendered


def test_p12_action_foundations_enrich_extracted_chain_contract():
    chains_dir = ROOT / "chains"
    chains_dir.mkdir(exist_ok=True)
    chain_path = chains_dir / "test_chain_contract.json"
    chain_doc = {
        "version": "stepchain.v1",
        "hash": "feedfacecafe",
        "name": "test_chain_contract",
        "desc": "test chain",
        "trigger": "on_vocab:research_needed",
        "root": "phase_root",
        "nodes": [
            {
                "id": "phase_root",
                "action": "observe_request",
                "goal": "Observe request",
                "kind": "observe",
                "gap_template": {"desc": "Observe request", "content_refs": [], "step_refs": []},
                "manifestation": {"runtime_vocab": "hash_resolve_needed"},
                "allowed_vocab": ["hash_resolve_needed"],
            },
            {"id": "phase_done", "kind": "terminal", "terminal": True},
        ],
    }
    chain_path.write_text(json.dumps(chain_doc))
    try:
        spec = action_foundations_module.foundation_from_chain_doc(chain_doc, ref="feedfacecafe", chains_dir=chains_dir)
        assert spec.surface == "semantic_tree"
        assert spec.activation == "name:research_needed"
        assert spec.default_gap == "research_needed"
        assert spec.omo_role == "observe"
    finally:
        chain_path.unlink(missing_ok=True)


def test_p12_action_foundations_ignore_aggregate_background_json_files(tmp_path):
    chain_doc = {
        "version": "stepchain.v1",
        "hash": "feedfacecafe",
        "name": "test_chain_contract",
        "desc": "test chain",
        "trigger": "on_vocab:research_needed",
        "root": "phase_root",
        "nodes": [
            {
                "id": "phase_root",
                "action": "observe_request",
                "goal": "Observe request",
                "kind": "observe",
                "gap_template": {"desc": "Observe request", "content_refs": [], "step_refs": []},
                "manifestation": {"runtime_vocab": "hash_resolve_needed"},
                "allowed_vocab": ["hash_resolve_needed"],
            },
            {"id": "phase_done", "kind": "terminal", "terminal": True},
        ],
    }
    (tmp_path / "feedfacecafe.json").write_text(json.dumps(chain_doc))
    (tmp_path / "background_run.chains.json").write_text(json.dumps([{"hash": "abc123"}]))
    (tmp_path / "background_run.trajectory.json").write_text(json.dumps([{"desc": "step"}]))

    rendered = action_foundations_module.render_action_foundations(
        registry=registry(),
        chains_dir=tmp_path,
        cors_root=ROOT,
        tool_map=loop.TOOL_MAP,
        git=lambda cmd, cwd=None: "0123456789abcdef0123456789abcdef01234567",
    )

    assert "feedfacecafe kind=extracted_chain surface=semantic_tree" in rendered
    assert "background_run" not in rendered


def test_p12_action_foundations_resolve_trigger_owner_prefers_semantic_top_level_block():
    owner = action_foundations_module.resolve_trigger_owner(
        "hash_edit_needed",
        registry=registry(),
        chains_dir=ROOT / "chains",
        cors_root=ROOT,
        tool_map=loop.TOOL_MAP,
        git=lambda cmd, cwd=None: "0123456789abcdef0123456789abcdef01234567",
    )

    assert owner is not None
    assert owner.ref == skill("hash_edit").hash
    assert owner.kind == "action_package"


def test_p12_trigger_owner_ignores_manual_lower_layer_and_resolves_top_layer(tmp_path):
    lower = {
        "version": "stepchain.v1",
        "hash": "feedface1000",
        "name": "research_leaf",
        "desc": "manual lower layer",
        "trigger": "manual",
        "root": "phase_leaf",
        "nodes": [
            {
                "id": "phase_leaf",
                "action": "classify_request",
                "goal": "Classify request",
                "kind": "reason",
                "gap_template": {"desc": "Classify request", "content_refs": [], "step_refs": []},
                "manifestation": {"runtime_vocab": "reason_needed"},
                "allowed_vocab": ["reason_needed"],
            },
            {"id": "phase_done", "kind": "terminal", "terminal": True},
        ],
    }
    upper = {
        "version": "stepchain.v1",
        "hash": "feedface2000",
        "name": "research_top",
        "desc": "top layer owner",
        "trigger": "on_vocab:research_needed",
        "root": "phase_root",
        "nodes": [
            {
                "id": "phase_root",
                "action": "activate_leaf",
                "goal": "Activate committed research leaf",
                "kind": "higher_order",
                "gap_template": {"desc": "Activate research leaf", "content_refs": ["feedface1000"], "step_refs": []},
                "manifestation": {"runtime_vocab": "reason_needed"},
                "allowed_vocab": ["reason_needed"],
            },
            {"id": "phase_done", "kind": "terminal", "terminal": True},
        ],
    }
    (tmp_path / "feedface1000.json").write_text(json.dumps(lower))
    (tmp_path / "feedface2000.json").write_text(json.dumps(upper))

    owner = action_foundations_module.resolve_trigger_owner(
        "research_needed",
        registry=registry(),
        chains_dir=tmp_path,
        cors_root=ROOT,
        tool_map=loop.TOOL_MAP,
        git=lambda cmd, cwd=None: "0123456789abcdef0123456789abcdef01234567",
    )

    assert owner is not None
    assert owner.ref == "feedface2000"
    assert owner.activation == "name:research_needed"


def test_p12_reprogramme_failure_does_not_commit_without_written_path():
    class FakeSession:
        def __init__(self):
            self.injected = []

        def inject(self, content: str, role: str = "user"):
            self.injected.append(content)

        def call(self, user_content: str = None) -> str:
            return json.dumps({
                "version": "semantic_skeleton.v1",
                "artifact": {"kind": "entity"},
                "name": "admin",
                "desc": "bad update",
                "trigger": "manual",
                "refs": {},
                "existing_ref": "kenny:47824f077e7d",
                "semantics": {},
            })

    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap("persist admin preference", content_refs=[skill("admin").hash], vocab="reprogramme_needed")
    entry = SimpleNamespace(gap=gap, chain_id="chain1")
    session = FakeSession()
    commit_calls = []

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "",
        execute_tool=lambda tool, params: ("Validation errors:\n  - existing_ref not found: kenny:47824f077e7d", 1),
        auto_commit=lambda message, paths=None: (commit_calls.append((message, paths)) or ("abc123", None)),
        parse_step_output=lambda raw, step_refs, content_refs, chain_id=None: (make_step("noop"), []),
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: None,
        extract_written_path=lambda output: None,
        is_reprogramme_intent=lambda intent: True,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: ["  validator: ok"],
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.step_result is not None
    assert outcome.step_result.commit is None
    assert commit_calls == []
    assert any("ST BUILDER FAILED" in injected for injected in session.injected)
    assert outcome.step_result.assessment == ["builder-error: existing_ref not found: kenny:47824f077e7d", "  validator: ok"]


def test_p12_entity_tree_reprogramme_mode_coerces_frame_to_entity():
    frame = {
        "version": "semantic_skeleton.v1",
        "artifact": {"kind": "hybrid", "protected_kind": "action"},
        "name": "clinton",
        "root": "phase_root",
        "phases": [{"id": "phase_root"}],
        "closure": {"success": {}},
        "semantics": {"identity": {"role": "developer"}},
    }

    coerced = execution_engine_module._coerce_semantic_frame_for_mode(frame, "entity_editor")

    assert coerced is not None
    assert coerced["artifact"]["kind"] == "entity"
    assert coerced["artifact"]["protected_kind"] == "entity"
    assert "root" not in coerced
    assert "phases" not in coerced
    assert "closure" not in coerced


def test_p12_new_action_gap_ignores_example_action_refs_for_target_resolution():
    gap = make_gap(
        "Compose research.st in skills/actions/ with trigger on_vocab:research_needed, matching architect.st, debug.st, and hash_edit.st.",
        content_refs=[skill("hash_edit").hash],
        vocab="reprogramme_needed",
    )

    target = execution_engine_module._entity_target_for_reprogramme(gap, registry())

    assert target is None


def test_p12_st_builder_normalizes_phases_missing_generation():
    skeleton = {
        "version": "semantic_skeleton.v1",
        "artifact": {"kind": "action", "protected_kind": "action"},
        "name": "research",
        "desc": "research workflow",
        "trigger": "on_vocab:research_needed",
        "root": "phase_clarify_1",
        "phases": [
            {
                "id": "phase_clarify_1",
                "kind": "clarify",
                "goal": "Clarify the research question.",
                "action": "clarify_question",
                "gap_template": {"desc": "Clarify the research question."},
                "manifestation": {
                    "kernel_class": "clarify",
                    "dispersal": "context",
                    "execution_mode": "runtime_vocab",
                    "runtime_vocab": "clarify_needed",
                },
                "post_diff": False,
            }
        ],
        "closure": {"success": {}},
    }

    lowered, artifact_kind, existing_ref = st_builder_module.lower_semantic_skeleton(skeleton)

    assert artifact_kind == "action"
    assert existing_ref is None
    assert lowered["phases"][0]["generation"]["branch_policy"] == "depth_first_to_parent"
    assert lowered["steps"][0]["vocab"] == "clarify_needed"


def test_p12_validate_st_rejects_action_closure_nonterminal_target():
    st = {
        "name": "research",
        "desc": "workflow",
        "trigger": "on_vocab:research_needed",
        "refs": {},
        "artifact": {"kind": "action", "protected_kind": "action"},
        "root": "phase_root",
        "phases": [
            {
                "id": "phase_root",
                "kind": "observe",
                "goal": "root",
                "action": "root",
                "gap_template": {"desc": "root", "content_refs": [], "step_refs": []},
                "manifestation": {"kernel_class": "observe", "dispersal": "context", "execution_mode": "runtime_vocab", "runtime_vocab": "hash_resolve_needed"},
                "generation": {"spawn_mode": "none", "spawn_trigger": "none", "branch_policy": "depth_first_to_parent", "sibling_policy": "after_descendants", "return_policy": "resume_transition"},
                "allowed_vocab": ["hash_resolve_needed"],
                "post_diff": False,
                "transitions": {"on_close": "phase_done"},
            },
            {"id": "phase_done", "kind": "terminal", "goal": "done", "action": "close_loop", "terminal": True},
        ],
        "steps": [{"action": "root", "desc": "root", "vocab": "hash_resolve_needed", "post_diff": False}],
        "closure": {"success": {"requires_terminal": "phase_root", "requires_no_active_gaps": True}},
    }

    errors = st_builder_module.validate_st(st, artifact_kind="action")
    assert any("requires_terminal must reference a real terminal phase" in e for e in errors)


def test_p12_validate_st_rejects_nested_phase_steps_for_authored_action():
    st = {
        "name": "research",
        "desc": "workflow",
        "trigger": "on_vocab:research_needed",
        "refs": {},
        "artifact": {"kind": "action", "protected_kind": "action"},
        "root": "phase_root",
        "phases": [
            {
                "id": "phase_root",
                "kind": "higher_order",
                "goal": "root",
                "action": "root",
                "gap_template": {"desc": "root", "content_refs": [], "step_refs": []},
                "manifestation": {"kernel_class": "bridge", "dispersal": "mixed", "execution_mode": "inline"},
                "generation": {"spawn_mode": "none", "spawn_trigger": "none", "branch_policy": "depth_first_to_parent", "sibling_policy": "after_descendants", "return_policy": "resume_transition"},
                "allowed_vocab": ["reason_needed"],
                "post_diff": False,
                "transitions": {"on_close": "phase_done"},
                "steps": [{"kind": "mutate", "gap": {"vocab": "bash_needed"}}],
            },
            {"id": "phase_done", "kind": "terminal", "goal": "done", "action": "close_loop", "terminal": True},
        ],
        "steps": [{"action": "root", "desc": "root", "post_diff": False}],
        "closure": {"success": {"requires_terminal": "phase_done", "requires_no_active_gaps": True}},
    }

    errors = st_builder_module.validate_st(st, artifact_kind="action")
    assert any("nested steps" in e for e in errors)


def test_p12_validate_st_rejects_descriptive_enrichment_without_runtime_linkage():
    st = {
        "name": "research",
        "desc": "workflow",
        "trigger": "on_vocab:research_needed",
        "refs": {"research_web": "tools/research_web.py"},
        "artifact": {"kind": "action", "protected_kind": "action"},
        "input_schema": {"queries": {"type": "array"}},
        "root": "phase_root",
        "phases": [
            {
                "id": "phase_root",
                "kind": "higher_order",
                "goal": "root",
                "action": "root",
                "gap_template": {"desc": "root", "content_refs": [], "step_refs": []},
                "manifestation": {"kernel_class": "bridge", "dispersal": "mixed", "execution_mode": "inline"},
                "generation": {"spawn_mode": "none", "spawn_trigger": "none", "branch_policy": "depth_first_to_parent", "sibling_policy": "after_descendants", "return_policy": "resume_transition"},
                "allowed_vocab": ["reason_needed"],
                "post_diff": False,
                "transitions": {"on_close": "phase_done"},
            },
            {"id": "phase_done", "kind": "terminal", "goal": "done", "action": "close_loop", "terminal": True},
        ],
        "steps": [{"action": "root", "desc": "root", "post_diff": False}],
        "closure": {"success": {"requires_terminal": "phase_done", "requires_no_active_gaps": True}},
    }

    errors = st_builder_module.validate_st(st, artifact_kind="action")
    assert any("runtime-effective non-bridge phase" in e for e in errors)
    assert any("declared tool or blob refs are not linked" in e for e in errors)


def test_p12_validate_st_rejects_missing_embedded_foundation_ref():
    st = {
        "name": "research",
        "desc": "workflow",
        "trigger": "on_vocab:research_needed",
        "refs": {"missing_tool": "tools/does_not_exist.py"},
        "artifact": {"kind": "action", "protected_kind": "action"},
        "root": "phase_root",
        "phases": [
            {
                "id": "phase_root",
                "kind": "observe",
                "goal": "root",
                "action": "root",
                "gap_template": {"desc": "root", "content_refs": ["@missing_tool"], "step_refs": []},
                "manifestation": {"kernel_class": "observe", "dispersal": "context", "execution_mode": "runtime_vocab", "runtime_vocab": "hash_resolve_needed"},
                "generation": {"spawn_mode": "none", "spawn_trigger": "none", "branch_policy": "depth_first_to_parent", "sibling_policy": "after_descendants", "return_policy": "resume_transition"},
                "allowed_vocab": ["hash_resolve_needed"],
                "post_diff": False,
                "transitions": {"on_close": "phase_done"},
            },
            {"id": "phase_done", "kind": "terminal", "goal": "done", "action": "close_loop", "terminal": True},
        ],
        "steps": [{"action": "root", "desc": "root", "vocab": "hash_resolve_needed", "post_diff": False}],
        "closure": {"success": {"requires_terminal": "phase_done", "requires_no_active_gaps": True}},
    }

    errors = st_builder_module.validate_st(st, artifact_kind="action", output_dir=str(ROOT / "skills"))
    assert any("must already exist before embedding" in e for e in errors)
    assert any("must point to an existing tool path, committed skill hash, or committed blob hash" in e for e in errors)


def test_p12_validate_st_accepts_existing_tool_blob_hash_ref():
    tool_blob = subprocess.check_output(
        ["git", "rev-parse", "HEAD:tools/research_web.py"],
        cwd=ROOT,
        text=True,
    ).strip()

    st = {
        "name": "research",
        "desc": "workflow",
        "trigger": "manual",
        "refs": {"research_tool_blob": tool_blob},
        "artifact": {"kind": "action", "protected_kind": "action"},
        "root": "phase_root",
        "phases": [
            {
                "id": "phase_root",
                "kind": "observe",
                "goal": "inspect research tool foundation",
                "action": "inspect_tool",
                "gap_template": {"desc": "inspect tool", "content_refs": ["@research_tool_blob"], "step_refs": []},
                "manifestation": {"kernel_class": "observe", "dispersal": "context", "execution_mode": "runtime_vocab", "runtime_vocab": "hash_resolve_needed"},
                "generation": {"spawn_mode": "none", "spawn_trigger": "none", "branch_policy": "depth_first_to_parent", "sibling_policy": "after_descendants", "return_policy": "resume_transition"},
                "allowed_vocab": ["hash_resolve_needed"],
                "post_diff": False,
                "transitions": {"on_close": "phase_done"},
            },
            {"id": "phase_done", "kind": "terminal", "goal": "done", "action": "close_loop", "terminal": True},
        ],
        "steps": [{"action": "inspect_tool", "desc": "inspect tool", "vocab": "hash_resolve_needed", "post_diff": False}],
        "closure": {"success": {"requires_terminal": "phase_done", "requires_no_active_gaps": True}},
    }

    errors = st_builder_module.validate_st(st, artifact_kind="action", output_dir=str(ROOT / "skills"))
    assert not any("must already exist before embedding" in e for e in errors)
    assert not any("must point to an existing tool path, committed skill hash, or committed blob hash" in e for e in errors)


def test_p12_validate_st_rejects_internal_hash_handler_tool_path():
    st = {
        "name": "inspect_doc_handler",
        "desc": "workflow",
        "trigger": "manual",
        "refs": {"doc_handler": "tools/hash/doc_read.py"},
        "artifact": {"kind": "action", "protected_kind": "action"},
        "root": "phase_root",
        "phases": [
            {
                "id": "phase_root",
                "kind": "observe",
                "goal": "inspect handler",
                "action": "inspect_handler",
                "gap_template": {"desc": "inspect", "content_refs": ["@doc_handler"], "step_refs": []},
                "manifestation": {"kernel_class": "observe", "dispersal": "context", "execution_mode": "runtime_vocab", "runtime_vocab": "hash_resolve_needed"},
                "generation": {"spawn_mode": "none", "spawn_trigger": "none", "branch_policy": "depth_first_to_parent", "sibling_policy": "after_descendants", "return_policy": "resume_transition"},
                "allowed_vocab": ["hash_resolve_needed"],
                "post_diff": False,
                "transitions": {"on_close": "phase_done"},
            },
            {"id": "phase_done", "kind": "terminal", "goal": "done", "action": "close_loop", "terminal": True},
        ],
        "steps": [{"action": "inspect_handler", "desc": "inspect", "vocab": "hash_resolve_needed", "post_diff": False}],
        "closure": {"success": {"requires_terminal": "phase_done", "requires_no_active_gaps": True}},
    }

    errors = st_builder_module.validate_st(st, artifact_kind="action", output_dir=str(ROOT / "skills"))
    assert any("must already exist before embedding" in e for e in errors)


def test_p12_validate_st_rejects_internal_hash_handler_blob_hash():
    rev_parse = subprocess.run(
        ["git", "rev-parse", "HEAD:tools/hash/doc_read.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if rev_parse.returncode == 0:
        tool_blob = rev_parse.stdout.strip()
    else:
        tool_blob = subprocess.check_output(
            ["git", "hash-object", "tools/hash/doc_read.py"],
            cwd=ROOT,
            text=True,
        ).strip()

    st = {
        "name": "inspect_doc_handler_blob",
        "desc": "workflow",
        "trigger": "manual",
        "refs": {"doc_handler_blob": tool_blob},
        "artifact": {"kind": "action", "protected_kind": "action"},
        "root": "phase_root",
        "phases": [
            {
                "id": "phase_root",
                "kind": "observe",
                "goal": "inspect handler blob",
                "action": "inspect_handler",
                "gap_template": {"desc": "inspect", "content_refs": ["@doc_handler_blob"], "step_refs": []},
                "manifestation": {"kernel_class": "observe", "dispersal": "context", "execution_mode": "runtime_vocab", "runtime_vocab": "hash_resolve_needed"},
                "generation": {"spawn_mode": "none", "spawn_trigger": "none", "branch_policy": "depth_first_to_parent", "sibling_policy": "after_descendants", "return_policy": "resume_transition"},
                "allowed_vocab": ["hash_resolve_needed"],
                "post_diff": False,
                "transitions": {"on_close": "phase_done"},
            },
            {"id": "phase_done", "kind": "terminal", "goal": "done", "action": "close_loop", "terminal": True},
        ],
        "steps": [{"action": "inspect_handler", "desc": "inspect", "vocab": "hash_resolve_needed", "post_diff": False}],
        "closure": {"success": {"requires_terminal": "phase_done", "requires_no_active_gaps": True}},
    }

    errors = st_builder_module.validate_st(st, artifact_kind="action", output_dir=str(ROOT / "skills"))
    assert any("must already exist before embedding" in e for e in errors)


def test_p12_validate_st_rejects_named_default_embedding_with_gap_override():
    st = {
        "name": "research",
        "desc": "workflow",
        "trigger": "manual",
        "refs": {"hash_edit_block": skill("hash_edit").hash},
        "artifact": {"kind": "action", "protected_kind": "action"},
        "root": "phase_root",
        "phases": [
            {
                "id": "phase_root",
                "kind": "higher_order",
                "goal": "embed hash edit by default contract",
                "action": "embed_hash_edit",
                "gap_template": {"desc": "embed hash edit", "content_refs": [], "step_refs": []},
                "manifestation": {"kernel_class": "bridge", "dispersal": "mixed", "execution_mode": "inline"},
                "generation": {"spawn_mode": "none", "spawn_trigger": "none", "branch_policy": "depth_first_to_parent", "sibling_policy": "after_descendants", "return_policy": "resume_transition"},
                "allowed_vocab": ["reason_needed"],
                "post_diff": False,
                "transitions": {"on_close": "phase_done"},
                "embedding": {
                    "block_ref": "@hash_edit_block",
                    "activation_mode": "named_default",
                    "gap_override": {"desc": "specialized override"},
                },
            },
            {"id": "phase_done", "kind": "terminal", "goal": "done", "action": "close_loop", "terminal": True},
        ],
        "steps": [{"action": "embed_hash_edit", "desc": "embed hash edit", "post_diff": False}],
        "closure": {"success": {"requires_terminal": "phase_done", "requires_no_active_gaps": True}},
    }

    errors = st_builder_module.validate_st(st, artifact_kind="action", output_dir=str(ROOT / "skills"))
    assert any("named_default embedding may not override the default gap contract" in e for e in errors)


def test_p12_validate_st_accepts_hash_embedded_explicit_gap_override():
    st = {
        "name": "research",
        "desc": "workflow",
        "trigger": "manual",
        "refs": {"hash_edit_block": skill("hash_edit").hash},
        "artifact": {"kind": "action", "protected_kind": "action"},
        "root": "phase_root",
        "phases": [
            {
                "id": "phase_root",
                "kind": "higher_order",
                "goal": "embed hash edit by hash",
                "action": "embed_hash_edit",
                "gap_template": {"desc": "embed hash edit", "content_refs": [], "step_refs": []},
                "manifestation": {"kernel_class": "bridge", "dispersal": "mixed", "execution_mode": "inline"},
                "generation": {"spawn_mode": "none", "spawn_trigger": "none", "branch_policy": "depth_first_to_parent", "sibling_policy": "after_descendants", "return_policy": "resume_transition"},
                "allowed_vocab": ["reason_needed"],
                "post_diff": False,
                "transitions": {"on_close": "phase_done"},
                "embedding": {
                    "block_ref": "@hash_edit_block",
                    "activation_mode": "hash_embedded",
                    "gap_override": {
                        "desc": "specialized hash-edit use",
                        "content_refs": ["@hash_edit_block"],
                        "allowed_vocab": ["hash_edit_needed"],
                    },
                },
            },
            {"id": "phase_done", "kind": "terminal", "goal": "done", "action": "close_loop", "terminal": True},
        ],
        "steps": [{"action": "embed_hash_edit", "desc": "embed hash edit", "post_diff": False}],
        "closure": {"success": {"requires_terminal": "phase_done", "requires_no_active_gaps": True}},
    }

    errors = st_builder_module.validate_st(st, artifact_kind="action", output_dir=str(ROOT / "skills"))
    assert not any("embedding.block_ref" in e for e in errors)
    assert not any("named_default embedding may not override" in e for e in errors)


def test_p12_semantic_tree_render_shows_foundation_and_embedding_contract():
    doc = {
        "version": "semantic_skeleton.v1",
        "artifact": {"kind": "action", "protected_kind": "action"},
        "name": "research",
        "desc": "workflow",
        "trigger": "manual",
        "refs": {"hash_edit_block": skill("hash_edit").hash},
        "root": "phase_root",
        "phases": [
            {
                "id": "phase_root",
                "kind": "higher_order",
                "goal": "embed hash edit by hash",
                "action": "embed_hash_edit",
                "gap_template": {"desc": "embed hash edit", "content_refs": [], "step_refs": []},
                "manifestation": {"kernel_class": "bridge", "dispersal": "mixed", "execution_mode": "inline"},
                "generation": {"spawn_mode": "none", "spawn_trigger": "none", "branch_policy": "depth_first_to_parent", "sibling_policy": "after_descendants", "return_policy": "resume_transition"},
                "allowed_vocab": ["reason_needed"],
                "post_diff": False,
                "transitions": {"on_close": "phase_done"},
                "embedding": {
                    "block_ref": "@hash_edit_block",
                    "activation_mode": "hash_embedded",
                    "gap_override": {"desc": "specialized hash edit", "allowed_vocab": ["hash_edit_needed"]},
                },
            },
            {"id": "phase_done", "kind": "terminal", "goal": "done", "action": "close_loop", "terminal": True},
        ],
        "closure": {"success": {"requires_terminal": "phase_done", "requires_no_active_gaps": True}},
    }

    tree = manifest_engine_module.build_semantic_tree(doc, source_type="resolved_package", source_ref="research")
    tree["foundation"] = action_foundations_module.foundation_from_skill(skill("hash_edit"), cors_root=ROOT).__dict__
    rendered = manifest_engine_module.render_semantic_tree(tree)

    assert "foundation: ref=" in rendered
    assert "default_gap=" not in rendered
    assert f"@embed:{skill('hash_edit').hash} [hash_embedded]" in rendered
    assert "embed_override:" in rendered
    assert "allowed_vocab=" not in rendered
    assert "manifestation:" not in rendered
    assert "generation:" not in rendered


def test_p13_runtime_semantic_tree_marks_parent_open_while_descendants_unresolved():
    parent_gap = make_gap("inspect canonical action", resolved=True, vocab="hash_resolve_needed")
    child_gap = make_gap("compose test flow", vocab="content_needed")
    step1 = make_step("inspect structure", gaps=[parent_gap])
    step2 = make_step("author test flow", step_refs=[step1.hash], gaps=[child_gap])

    tree = manifest_engine_module.build_runtime_semantic_tree(
        [step1.to_dict(), step2.to_dict()],
        source_type="realized_chain",
        source_ref="chain_state_demo",
        summary_desc="authoring chain",
    )
    rendered_tree = manifest_engine_module.render_semantic_tree(tree)

    assert 'chain:chain_state_demo "authoring chain" (active, 2 steps)' in rendered_tree
    assert f'{{o=}} step:{step1.hash} "inspect structure"' in rendered_tree
    assert f'{{resolved:o}} gap:{parent_gap.hash} [hash_resolve_needed]' in rendered_tree
    assert f'{{m+1}} step:{step2.hash} "author test flow"' in rendered_tree
    assert f'{{active:m}} gap:{child_gap.hash} [content_needed]' in rendered_tree

    traj = Trajectory()
    traj.append(step1)
    traj.append(step2)
    chain = Chain.create(parent_gap.hash, step1.hash)
    traj.add_chain(chain)
    chain.add_step(step2.hash)
    traj.add_chain(chain)
    rendered_chain = traj.render_chain(chain.hash, registry())

    assert f"step:{step1.hash} \"inspect structure\" [open]" in rendered_chain
    assert f"step:{step2.hash} \"author test flow\" [open]" in rendered_chain


def test_p13_runtime_semantic_tree_marks_branch_resolved_after_descendants_close():
    parent_gap = make_gap("inspect canonical action", resolved=True, vocab="hash_resolve_needed")
    step1 = make_step("inspect structure", gaps=[parent_gap])
    step2 = make_step("author test flow", step_refs=[step1.hash], gaps=[])

    tree = manifest_engine_module.build_runtime_semantic_tree(
        [step1.to_dict(), step2.to_dict()],
        source_type="realized_chain",
        source_ref="chain_state_resolved",
        summary_desc="authoring chain",
        resolved=True,
    )
    rendered_tree = manifest_engine_module.render_semantic_tree(tree)

    assert 'chain:chain_state_resolved "authoring chain" (resolved, 2 steps)' in rendered_tree
    assert f'{{o=}} step:{step1.hash} "inspect structure"' in rendered_tree
    assert f'{{resolved:o}} gap:{parent_gap.hash} [hash_resolve_needed]' in rendered_tree
    assert f'{{o=}} step:{step2.hash} "author test flow"' in rendered_tree
    assert f"gap:{step2.hash}.gap -> refs:[step:(none), content:(none)]" in rendered_tree

    traj = Trajectory()
    traj.append(step1)
    traj.append(step2)
    chain = Chain.create(parent_gap.hash, step1.hash)
    traj.add_chain(chain)
    chain.add_step(step2.hash)
    chain.resolved = True
    traj.add_chain(chain)
    rendered_chain = traj.render_chain(chain.hash, registry())

    assert f"step:{step1.hash} \"inspect structure\" [resolved]" in rendered_chain
    assert f"step:{step2.hash} \"author test flow\" [resolved]" in rendered_chain


def test_p12_render_skill_package_surfaces_action_tree_details():
    debug_skill = registry().resolve_by_name("debug")
    assert debug_skill is not None
    rendered = loop._render_skill_package(debug_skill)

    assert rendered.startswith(f"semantic_tree:skill_package:{debug_skill.hash}")
    assert 'package:debug "Reason-activated debug analysis. Resolves principles, attached source, turn tree, and failed output log, then reasons about fixes and may activate hash_edit." (5 steps)' in rendered
    assert "trigger: manual" in rendered
    assert "legend: step{o/m/b/c + frontier}; gap{status + surface + ref-counts}" in rendered
    assert "[hash_resolve_needed]" in rendered
    assert "manifestation:" not in rendered
    assert "generation:" not in rendered
    assert "allowed_vocab=" not in rendered


def test_p12_render_skill_package_uses_refined_semantic_tree_surface():
    debug_skill = registry().resolve_by_name("debug")
    assert debug_skill is not None

    rendered = loop._render_skill_package(debug_skill)

    assert "{o" in rendered
    assert "step:" in rendered
    assert "gap:" in rendered
    assert "-> refs:[" in rendered
    assert "[hash_resolve_needed]" in rendered
    assert "allowed_vocab=" not in rendered
    assert "post_diff=" not in rendered
    assert "manifestation:" not in rendered
    assert "generation:" not in rendered


def test_p12_build_semantic_tree_from_action_skill_exposes_gap_configuration():
    debug_skill = registry().resolve_by_name("debug")
    assert debug_skill is not None

    tree = manifest_engine_module.build_semantic_tree(
        debug_skill.payload,
        source_type="skill_package",
        source_ref=debug_skill.hash,
    )

    assert tree["version"] == "semantic_tree.v1"
    assert tree["root_id"].startswith("phase_")
    first = tree["nodes"][0]
    assert first["gap"]["runtime_vocab"] == "hash_resolve_needed"
    assert first["manifestation"]["kernel_class"] == "observe"
    assert first["generation"]["branch_policy"] == "depth_first_to_parent"


def test_p12_build_semantic_tree_from_realized_chain_preserves_causal_links():
    chain_doc = {
        "hash": "chain123",
        "origin_gap": "gap0",
        "steps": [
            {
                "hash": "step_a",
                "desc": "resolve context",
                "gaps": [
                    {
                        "hash": "gap_a",
                        "desc": "resolve context",
                        "vocab": "hash_resolve_needed",
                        "step_refs": ["seed"],
                        "content_refs": ["blob_a"],
                        "scores": {"relevance": 1.0, "confidence": 0.7, "grounded": 0.2},
                    }
                ],
            },
            {
                "hash": "step_b",
                "desc": "edit file",
                "commit": "abc123",
                "gaps": [
                    {
                        "hash": "gap_b",
                        "desc": "edit file",
                        "vocab": "hash_edit_needed",
                        "step_refs": ["step_a"],
                        "content_refs": ["blob_b"],
                        "scores": {"relevance": 0.8, "confidence": 0.8, "grounded": 0.6},
                    }
                ],
            },
        ],
    }

    tree = manifest_engine_module.build_semantic_tree(chain_doc, source_type="realized_chain", source_ref="chain123")

    assert tree["version"] == "semantic_tree.v1"
    assert tree["nodes"][1]["parent_id"] == "step_a"
    assert tree["nodes"][1]["gap"]["runtime_vocab"] == "hash_edit_needed"
    assert tree["nodes"][1]["gap"]["post_diff"] is True


def test_p12_resolve_hash_renders_action_packages_as_semantic_tree(monkeypatch):
    monkeypatch.setattr(loop, "_skill_registry", registry())
    architect_skill = registry().resolve_by_name("architect")
    assert architect_skill is not None

    rendered = loop.resolve_hash(architect_skill.hash, Trajectory())

    assert rendered is not None
    assert rendered.startswith(f"semantic_tree:skill_package:{architect_skill.hash}")
    assert 'package:architect "' in rendered
    assert 'step:phase_resolve_source_1 "resolve_source"' in rendered
    assert "next: on_close->" in rendered


def test_p12_resolve_hash_renders_log_tail_for_local_log(monkeypatch, tmp_path):
    log_path = tmp_path / "bot.log"
    lines = [f"line {i}" for i in range(150)]
    log_path.write_text("\n".join(lines))

    monkeypatch.setattr(loop, "CORS_ROOT", tmp_path)

    rendered = loop.resolve_hash("bot.log", Trajectory())

    assert rendered is not None
    assert rendered.startswith("log_tail:bot.log")
    assert "showing tail;" in rendered
    assert "line 149" in rendered
    assert "line 0" not in rendered


def test_p12_resolve_hash_routes_docx_through_specialized_reader(monkeypatch, tmp_path):
    doc_path = tmp_path / "sample.docx"
    doc_path.write_text("placeholder")

    calls: list[tuple[str, dict]] = []

    def fake_execute_tool(tool_path: str, params: dict):
        calls.append((tool_path, params))
        return ("1: Hello from DOCX", 0)

    monkeypatch.setattr(loop, "CORS_ROOT", tmp_path)
    monkeypatch.setattr(loop, "execute_tool", fake_execute_tool)

    rendered = loop.resolve_hash("sample.docx", Trajectory())

    assert rendered == "1: Hello from DOCX"
    assert calls == [("tools/hash/doc_read.py", {"path": "sample.docx"})]


def test_p12_resolve_hash_routes_pptx_through_marker_reader(monkeypatch, tmp_path):
    pptx_path = tmp_path / "slides.pptx"
    pptx_path.write_text("placeholder")

    calls: list[tuple[str, dict]] = []

    def fake_execute_tool(tool_path: str, params: dict):
        calls.append((tool_path, params))
        return ("1: Slide 1 title", 0)

    monkeypatch.setattr(loop, "CORS_ROOT", tmp_path)
    monkeypatch.setattr(loop, "execute_tool", fake_execute_tool)

    rendered = loop.resolve_hash("slides.pptx", Trajectory())

    assert rendered == "1: Slide 1 title"
    assert calls == [("tools/hash/document_extract_marker.py", {"path": "slides.pptx"})]


def test_p12_hash_manifest_routes_package_office_formats_through_office_manifest():
    assert hash_manifest_module.TOOL_ROUTES[".pptx"] == "tools/hash/office_manifest.py"
    assert hash_manifest_module.TOOL_ROUTES[".xlsx"] == "tools/hash/office_manifest.py"


def test_p12_hash_registry_captures_core_routes():
    assert hash_registry_module.HASH_CORE_TOOLS == (
        "tools/hash_resolve.py",
        "tools/hash_manifest.py",
    )
    assert hash_registry_module.HASH_MANIFEST_ROUTES[".docx"] == "tools/hash/doc_edit.py"
    assert hash_registry_module.HASH_MANIFEST_ROUTES[".pptx"] == "tools/hash/office_manifest.py"
    assert hash_registry_module.HASH_RESOLVE_ROUTES[".json"] == "tools/hash/json_query.py"
    assert hash_registry_module.HASH_RESOLVE_ROUTES[".pdf"] == "tools/hash/pdf_read.py"
    assert hash_registry_module.HASH_RESOLVE_ROUTES[".png"] == "tools/hash/document_extract_marker.py"


def test_p12_tool_registry_exposes_only_public_hash_tools():
    assert "tools/hash_resolve.py" in tool_registry_module.PUBLIC_TOOL_PATHS
    assert "tools/hash_manifest.py" in tool_registry_module.PUBLIC_TOOL_PATHS
    assert "tools/hash/json_query.py" not in tool_registry_module.PUBLIC_TOOL_PATHS
    assert "tools/hash/doc_read.py" not in tool_registry_module.PUBLIC_TOOL_PATHS
    assert "tools/hash/document_extract_marker.py" not in tool_registry_module.PUBLIC_TOOL_PATHS


def test_p12_chain_registry_exposes_action_chain_paths():
    assert chain_registry_module.PUBLIC_CHAIN_PATHS == (
        "skills/actions/architect.st",
        "skills/actions/debug.st",
        "skills/actions/hash_edit.st",
        "skills/actions/principles.st",
        "skills/actions/principles_edit.st",
        "skills/actions/property_research.st",
    )


def test_p12_chain_registry_derives_hash_edit_contract():
    contracts = {contract.name: contract for contract in chain_registry_module.list_public_chain_contracts(ROOT)}
    contract = contracts["hash_edit"]

    assert contract.source == "skills/actions/hash_edit.st"
    assert contract.trigger == "on_vocab:hash_edit_needed"
    assert contract.activation == "name:hash_edit_needed"
    assert contract.default_gap == "hash_edit_needed"
    assert contract.entry_vocab == "hash_resolve_needed"
    assert contract.step_count == 3
    assert contract.omo_shape == "observe->bridge->mutate"
    assert contract.tool_paths == ("tools/hash_manifest.py",)


def test_p12_chain_registry_derives_principles_edit_contract():
    contracts = {contract.name: contract for contract in chain_registry_module.list_public_chain_contracts(ROOT)}
    contract = contracts["principles_edit"]

    assert contract.source == "skills/actions/principles_edit.st"
    assert contract.trigger == "manual"
    assert contract.activation == "name:hash_resolve_needed"
    assert contract.default_gap == "hash_resolve_needed"
    assert contract.entry_vocab == "hash_resolve_needed"
    assert contract.step_count == 3
    assert contract.omo_shape == "observe->bridge->mutate"
    assert contract.tool_paths == ("tools/hash_manifest.py",)


def test_p12_chain_registry_derives_command_action_tools():
    contracts = {contract.name: contract for contract in chain_registry_module.list_public_chain_contracts(ROOT)}
    architect = contracts["architect"]
    debug = contracts["debug"]
    principles = contracts["principles"]
    property_research = contracts["property_research"]

    assert architect.activation == "name:architect_needed"
    assert architect.trigger == "on_vocab:architect_needed"
    assert architect.default_gap == "architect_needed"
    assert architect.step_count == 5
    assert architect.omo_shape == "observe->bridge"
    assert architect.tool_paths == ()
    assert debug.activation == "name:hash_resolve_needed"
    assert debug.trigger == "manual"
    assert debug.step_count == 5
    assert debug.omo_shape == "observe->bridge"
    assert debug.tool_paths == ()
    assert principles.activation == "name:hash_resolve_needed"
    assert principles.trigger == "manual"
    assert principles.step_count == 3
    assert principles.omo_shape == "observe->bridge"
    assert principles.tool_paths == ()
    assert property_research.activation == "command:property_research"
    assert property_research.step_count == 14
    assert property_research.omo_shape == "observe->mutate"
    assert "tools/postcodes_io.py" in property_research.tool_paths
    assert "tools/land_registry.py" in property_research.tool_paths
    assert "tools/research_web.py" in property_research.tool_paths


def test_p12_architect_needed_routes_to_architect_chain_ref():
    architect_ref = next(
        contract.ref for contract in chain_registry_module.list_public_chain_contracts(ROOT) if contract.name == "architect"
    )
    spec = vocab_registry_module.get_vocab("architect_needed")
    assert spec is not None
    assert spec.target_kind == "chain"
    assert spec.target_ref == architect_ref


def test_p12_render_public_chain_registry_lists_compact_chain_surface():
    rendered = chain_registry_module.render_public_chain_registry(ROOT)

    assert rendered.startswith("## Public Chain Registry")
    assert "skills/actions/hash_edit.st" in rendered
    assert "activation=name:hash_edit_needed" in rendered
    assert "omo=observe->bridge->mutate" in rendered


def test_p12_all_public_tools_express_valid_contract_metadata():
    missing_or_invalid = []
    for rel in tool_registry_module.PUBLIC_TOOL_PATHS:
        path = ROOT / rel
        if tool_contract_module.load_tool_contract(path) is None:
            missing_or_invalid.append((rel, tool_contract_module.validate_tool_file(path)))
    assert missing_or_invalid == []


def test_p12_render_public_tool_registry_lists_public_tools_and_contracts():
    rendered = execution_engine_module._render_public_tool_registry(ROOT)
    tool_refs = tool_registry_module.public_tool_ref_map(ROOT)
    hash_resolve_ref = next(ref for ref, path in tool_refs.items() if path == "tools/hash_resolve.py")
    hash_manifest_ref = next(ref for ref, path in tool_refs.items() if path == "tools/hash_manifest.py")

    assert rendered.startswith("## Public Tool Registry")
    assert f"tools/hash_resolve.py | ref={hash_resolve_ref} | observe/workspace | post_observe=none" in rendered
    assert f"tools/hash_manifest.py | ref={hash_manifest_ref} | mutate/workspace | post_observe=artifacts | artifacts=derived" in rendered
    assert "tools/runway_gen.py | ref=" in rendered
    assert "mutate/external | post_observe=log | artifacts=none" in rendered
    assert "tools/hash/doc_read.py" not in rendered
    assert "tools/hash/document_extract_marker.py" not in rendered


def test_p12_find_vocab_for_tool_ref_prefers_current_hash_manifest_mapping():
    hash_manifest_ref = next(
        ref for ref, path in tool_registry_module.public_tool_ref_map(ROOT).items() if path == "tools/hash_manifest.py"
    )
    assert vocab_registry_module.find_vocab_for_tool_ref(hash_manifest_ref) == "hash_edit_needed"


def test_p12_semantic_skeleton_from_st_supports_direct_tool_ref_steps():
    tool_ref = next(
        ref for ref, path in tool_registry_module.public_tool_ref_map(ROOT).items() if path == "tools/postcodes_io.py"
    )
    lowered = st_builder_module.semantic_skeleton_from_st(
        {
            "name": "postcode_probe",
            "desc": "lookup postcode context",
            "trigger": "manual",
            "steps": [
                {
                    "action": "lookup_postcode",
                    "desc": "use the postcode tool directly",
                    "tool_ref": tool_ref,
                    "post_diff": False,
                }
            ],
        }
    )

    phase = lowered["phases"][0]
    assert phase["manifestation"]["execution_mode"] == "curated_step_hash"
    assert phase["manifestation"]["activation_ref"] == tool_ref
    assert phase["allowed_vocab"] == []
    lowered_st, _, _ = st_builder_module.lower_semantic_skeleton(lowered)
    assert lowered_st["steps"][0]["tool_ref"] == tool_ref


def test_p12_action_foundations_hide_internal_hash_handlers():
    rendered = action_foundations_module.render_action_foundations(
        registry=registry(),
        chains_dir=ROOT / "chains",
        cors_root=ROOT,
        tool_map=loop.TOOL_MAP,
        git=lambda args, _stdin=None: subprocess.check_output(["git", *args], cwd=ROOT, text=True),
    )

    assert "source=tools/hash_resolve.py" in rendered
    assert "source=tools/hash_manifest.py" in rendered
    assert "source=tools/hash/doc_read.py" not in rendered
    assert "source=tools/hash/document_extract_marker.py" not in rendered


def test_p12_office_manifest_patches_minimal_pptx_package(tmp_path):
    pptx_path = tmp_path / "slides.pptx"
    with zipfile.ZipFile(pptx_path, "w") as zf:
        zf.writestr(
            "ppt/slides/slide1.xml",
            '<p:sld xmlns:p="urn:test"><p:txBody>Old Title</p:txBody></p:sld>',
        )
        zf.writestr(
            "ppt/_rels/presentation.xml.rels",
            '<Relationships xmlns="urn:test"></Relationships>',
        )

    message = office_manifest_module.patch_package(str(pptx_path), "Old Title", "New Title")

    assert message.startswith("ok: slides.pptx")
    with zipfile.ZipFile(pptx_path) as zf:
        slide_xml = zf.read("ppt/slides/slide1.xml").decode("utf-8")
    assert "New Title" in slide_xml
    assert "Old Title" not in slide_xml


def test_p12_tool_contract_validates_workspace_mutate_artifact_tool(tmp_path):
    tool_path = tmp_path / "sample_tool.py"
    tool_path.write_text(
        '"""sample_tool — writes a local artifact."""\n'
        'TOOL_DESC = "writes a local artifact"\n'
        'TOOL_MODE = "mutate"\n'
        'TOOL_SCOPE = "workspace"\n'
        'TOOL_POST_OBSERVE = "artifacts"\n'
        'TOOL_DEFAULT_ARTIFACTS = ["outputs/sample.txt"]\n',
        encoding="utf-8",
    )

    assert tool_contract_module.validate_tool_file(tool_path) == []


def test_p12_tool_contract_validates_runtime_artifact_key(tmp_path):
    tool_path = tmp_path / "runtime_artifact_tool.py"
    tool_path.write_text(
        '"""runtime_artifact_tool — writes dynamic artifacts."""\n'
        'TOOL_DESC = "writes dynamic artifacts"\n'
        'TOOL_MODE = "mutate"\n'
        'TOOL_SCOPE = "workspace"\n'
        'TOOL_POST_OBSERVE = "artifacts"\n'
        'TOOL_RUNTIME_ARTIFACT_KEY = "artifacts"\n',
        encoding="utf-8",
    )

    assert tool_contract_module.validate_tool_file(tool_path) == []


def test_p12_tool_contract_rejects_artifact_tool_without_source_fields(tmp_path):
    tool_path = tmp_path / "missing_artifacts.py"
    tool_path.write_text(
        '"""missing_artifacts — claims artifacts but does not express them."""\n'
        'TOOL_DESC = "claims artifacts but does not express them"\n'
        'TOOL_MODE = "mutate"\n'
        'TOOL_SCOPE = "external"\n'
        'TOOL_POST_OBSERVE = "artifacts"\n',
        encoding="utf-8",
    )

    errors = tool_contract_module.validate_tool_file(tool_path)
    assert any("TOOL_DEFAULT_ARTIFACTS, TOOL_ARTIFACT_PARAMS, or TOOL_RUNTIME_ARTIFACT_KEY" in error for error in errors)


def test_p12_tool_contract_rejects_workspace_mutate_log_only(tmp_path):
    tool_path = tmp_path / "bad_tool.py"
    tool_path.write_text(
        '"""bad_tool — mutates workspace but only logs."""\n'
        'TOOL_DESC = "mutates workspace but only logs"\n'
        'TOOL_MODE = "mutate"\n'
        'TOOL_SCOPE = "workspace"\n'
        'TOOL_POST_OBSERVE = "log"\n',
        encoding="utf-8",
    )

    errors = tool_contract_module.validate_tool_file(tool_path)
    assert any("workspace mutate tools" in error for error in errors)


def test_p12_tool_builder_writes_validated_stub(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE", str(tmp_path))
    target = tmp_path / "tools" / "demo_tool.py"
    stdin = json.dumps(
        {
            "path": "tools/demo_tool.py",
            "desc": "produce a local demo artifact",
            "mode": "mutate",
            "scope": "workspace",
            "post_observe": "artifacts",
            "default_artifacts": ["demo/output.txt"],
        }
    )

    old_stdin = sys.stdin
    old_stdout = sys.stdout
    try:
        sys.stdin = SimpleNamespace(read=lambda: stdin)
        buffer = []
        sys.stdout = SimpleNamespace(write=lambda s: buffer.append(s), flush=lambda: None)
        tool_builder_module.main()
    finally:
        sys.stdin = old_stdin
        sys.stdout = old_stdout

    assert target.exists()
    content = target.read_text(encoding="utf-8")
    assert 'TOOL_DESC = "produce a local demo artifact"' in content
    assert "TOOL_DEFAULT_ARTIFACTS = ['demo/output.txt']" in content
    assert tool_contract_module.validate_tool_file(target) == []


def test_p12_tool_builder_writes_param_based_artifact_stub(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE", str(tmp_path))
    target = tmp_path / "tools" / "param_tool.py"
    stdin = json.dumps(
        {
            "path": "tools/param_tool.py",
            "desc": "write artifact paths through params",
            "mode": "mutate",
            "scope": "workspace",
            "post_observe": "artifacts",
            "artifact_params": ["output_path"],
        }
    )

    old_stdin = sys.stdin
    old_stdout = sys.stdout
    try:
        sys.stdin = SimpleNamespace(read=lambda: stdin)
        buffer = []
        sys.stdout = SimpleNamespace(write=lambda s: buffer.append(s), flush=lambda: None)
        tool_builder_module.main()
    finally:
        sys.stdin = old_stdin
        sys.stdout = old_stdout

    content = target.read_text(encoding="utf-8")
    assert 'TOOL_ARTIFACT_PARAMS = [\'output_path\']' in content
    assert tool_contract_module.validate_tool_file(target) == []


def test_p12_vocab_builder_writes_configurable_tool_route(tmp_path):
    registry_copy = tmp_path / "vocab_registry.py"
    registry_copy.write_text((ROOT / "vocab_registry.py").read_text(encoding="utf-8"), encoding="utf-8")
    hash_manifest_ref = next(
        ref for ref, path in tool_registry_module.public_tool_ref_map(ROOT).items() if path == "tools/hash_manifest.py"
    )
    stdin = json.dumps(
        {
            "name": "demo_vocab_needed",
            "classifiable": "mutate",
            "target_kind": "tool",
            "target_ref": hash_manifest_ref,
            "desc": "route demo semantic mutations through hash manifest",
            "prompt_hint": "Use for demo write/edit requests.",
            "registry_path": str(registry_copy),
        }
    )

    old_stdin = sys.stdin
    old_stdout = sys.stdout
    try:
        sys.stdin = SimpleNamespace(read=lambda: stdin)
        buffer = []
        sys.stdout = SimpleNamespace(write=lambda s: buffer.append(s), flush=lambda: None)
        vocab_builder_module.main()
    finally:
        sys.stdin = old_stdin
        sys.stdout = old_stdout

    content = registry_copy.read_text(encoding="utf-8")
    assert '"demo_vocab_needed": VocabSpec(' in content
    assert 'target_kind="tool"' in content
    assert f'target_ref="{hash_manifest_ref}"' in content
    assert 'prompt_hint="Use for demo write/edit requests."' in content


def test_p12_vocab_builder_accepts_vocab_skeleton_version_for_chain_route(tmp_path):
    registry_copy = tmp_path / "vocab_registry.py"
    registry_copy.write_text((ROOT / "vocab_registry.py").read_text(encoding="utf-8"), encoding="utf-8")
    public_chain_ref = next(iter(chain_registry_module.public_chain_ref_map(ROOT)))
    stdin = json.dumps(
        {
            "version": "vocab_skeleton.v1",
            "name": "demo_chain_vocab_needed",
            "classifiable": "mutate",
            "target_kind": "chain",
            "target_ref": public_chain_ref,
            "desc": "route demo semantic maintenance through a public chain",
            "registry_path": str(registry_copy),
        }
    )

    old_stdin = sys.stdin
    old_stdout = sys.stdout
    try:
        sys.stdin = SimpleNamespace(read=lambda: stdin)
        buffer = []
        sys.stdout = SimpleNamespace(write=lambda s: buffer.append(s), flush=lambda: None)
        vocab_builder_module.main()
    finally:
        sys.stdin = old_stdin
        sys.stdout = old_stdout

    content = registry_copy.read_text(encoding="utf-8")
    assert '"demo_chain_vocab_needed": VocabSpec(' in content
    assert 'target_kind="chain"' in content
    assert f'target_ref="{public_chain_ref}"' in content


def test_p12_tool_needed_injects_public_tool_registry_before_compose():
    class FakeSession:
        def __init__(self):
            self.injected = []
            self.calls = 0

        def inject(self, content: str, role: str = "user"):
            self.injected.append(content)

        def call(self, user_content: str = None) -> str:
            self.calls += 1
            return json.dumps(
                {
                    "path": "tools/demo_registry_tool.py",
                    "desc": "inspect registry-aware tool composition",
                    "mode": "observe",
                    "scope": "workspace",
                    "post_observe": "none",
                }
            )

    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap("create a registry-aware tool", vocab="tool_needed")
    entry = SimpleNamespace(gap=gap, chain_id="chain1")
    session = FakeSession()

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "",
        execute_tool=lambda tool, params: ("ok: wrote tools/demo_registry_tool.py", 0),
        auto_commit=lambda message, paths=None: (None, None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: None,
        extract_written_path=lambda output: "tools/demo_registry_tool.py",
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.step_result is not None
    assert any(content.startswith("## Public Tool Registry") for content in session.injected)
    tool_refs = tool_registry_module.public_tool_ref_map(ROOT)
    hash_resolve_ref = next(ref for ref, path in tool_refs.items() if path == "tools/hash_resolve.py")
    hash_manifest_ref = next(ref for ref, path in tool_refs.items() if path == "tools/hash_manifest.py")
    assert any(f"tools/hash_resolve.py | ref={hash_resolve_ref} | observe/workspace | post_observe=none" in content for content in session.injected)
    assert any(f"tools/hash_manifest.py | ref={hash_manifest_ref} | mutate/workspace | post_observe=artifacts | artifacts=derived" in content for content in session.injected)
    assert session.calls == 1


def test_p12_vocab_reg_needed_injects_registries_before_compose():
    class FakeSession:
        def __init__(self):
            self.injected = []
            self.calls = 0

        def inject(self, content: str, role: str = "user"):
            self.injected.append(content)

        def call(self, user_content: str = None) -> str:
            self.calls += 1
            hash_manifest_ref = next(
                ref for ref, path in tool_registry_module.public_tool_ref_map(ROOT).items() if path == "tools/hash_manifest.py"
            )
            return json.dumps(
                {
                    "version": "vocab_skeleton.v1",
                    "name": "demo_vocab_needed",
                    "classifiable": "mutate",
                    "target_kind": "tool",
                    "target_ref": hash_manifest_ref,
                    "desc": "route demo semantic mutations through hash manifest",
                }
            )

    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap("add a vocab route for hash edits", vocab="vocab_reg_needed")
    entry = SimpleNamespace(gap=gap, chain_id="chain1")
    session = FakeSession()

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "",
        execute_tool=lambda tool, params: ("written: vocab_registry.py", 0),
        auto_commit=lambda message, paths=None: (None, None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: None,
        extract_written_path=lambda output: "vocab_registry.py",
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.step_result is not None
    assert any(content.startswith("## Public Tool Registry") for content in session.injected)
    assert any(content.startswith("## Public Chain Registry") for content in session.injected)
    assert any(content.startswith("## Configurable Vocab Registry") for content in session.injected)
    assert session.calls == 1


def test_p12_vocab_reg_needed_stays_on_builder_path_for_vocab_registry_mutation():
    class FakeSession:
        def __init__(self):
            self.injected = []
            self.calls = 0

        def inject(self, content: str, role: str = "user"):
            self.injected.append(content)

        def call(self, user_content: str = None) -> str:
            self.calls += 1
            return json.dumps(
                {
                    "version": "vocab_skeleton.v1",
                    "operation": "upsert",
                    "name": "principles_needed",
                    "classifiable": "mutate",
                    "target_kind": "chain",
                    "target_ref": skill("principles").hash,
                    "desc": "Run the principles workflow.",
                    "prompt_hint": "Use for principles maintenance requests.",
                }
            )

    executed_tools: list[str] = []
    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap(
        "Add principles_needed to vocab_registry.py, mapping it to the principles action package with the correct trigger and target_ref.",
        vocab="vocab_reg_needed",
        content_refs=["vocab_registry.py", skill("principles").hash],
    )
    entry = SimpleNamespace(gap=gap, chain_id="chain1")
    session = FakeSession()

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "resolved vocab registry context",
        execute_tool=lambda tool, params: (executed_tools.append(tool) or "written: vocab_registry.py", 0),
        auto_commit=lambda message, paths=None: ("abc123", None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: None,
        extract_written_path=lambda output: "vocab_registry.py",
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=lambda: {"vocab_registry.py": {"on_mutate": "vocab_reg_needed"}, "skills/actions/": {"on_mutate": "reason_needed"}},
        match_policy=lambda path, policy: policy.get(path),
        resolve_entity=lambda content_refs, registry_obj, trajectory: skill("principles") if skill("principles").hash in content_refs else None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.step_result is not None
    assert executed_tools == ["system/vocab_builder.py"]
    assert gap.vocab == "vocab_reg_needed"
    assert session.calls == 1
    assert any(content.startswith("## Refreshed System Control Surface") for content in session.injected)
    assert any("## Vocab Map" in content for content in session.injected)


def test_p12_system_surface_sections_for_vocab_registry_path():
    assert execution_engine_module._system_surface_sections_for_path("vocab_registry.py") == {"vocab"}


def test_p12_system_surface_sections_for_action_path():
    assert execution_engine_module._system_surface_sections_for_path("skills/actions/principles.st") == {"workflows", "vocab"}


def test_p12_direct_tool_ref_observe_executes_public_tool_by_hash():
    class FakeSession:
        def __init__(self):
            self.injected = []
            self.calls = 0

        def inject(self, content: str, role: str = "user"):
            self.injected.append(content)

        def call(self, user_content: str = None) -> str:
            self.calls += 1
            if self.calls == 1:
                return json.dumps({"postcode": "M1 1AA"})
            return json.dumps({"desc": "observed postcode context", "gaps": []})

    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    tool_ref = next(
        ref for ref, path in tool_registry_module.public_tool_ref_map(ROOT).items() if path == "tools/postcodes_io.py"
    )
    gap = make_gap(
        "lookup postcode context for the target property",
        content_refs=["package_ref", tool_ref],
    )
    gap.route_mode = "tool_ref_direct"
    entry = SimpleNamespace(gap=gap, chain_id="chain1")
    session = FakeSession()
    executed = []

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "resolved property brief with postcode M1 1AA",
        execute_tool=lambda tool, params: (executed.append((tool, params)) or True) and ('{"postcode":"M1 1AA","district":"Manchester"}', 0),
        auto_commit=lambda message, paths=None: (None, None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: None,
        extract_written_path=lambda output: None,
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.step_result is not None
    assert executed == [("tools/postcodes_io.py", {"postcode": "M1 1AA"})]
    assert any(content.startswith("## Tool output (tools/postcodes_io.py)") for content in session.injected)


def test_p12_tool_needed_reintegrates_through_reason_needed_after_write():
    class FakeSession:
        def __init__(self):
            self.injected = []

        def inject(self, content: str, role: str = "user"):
            self.injected.append(content)

        def call(self, user_content: str = None) -> str:
            return json.dumps(
                {
                    "path": "tools/demo_registry_tool.py",
                    "desc": "inspect registry-aware tool composition",
                    "mode": "observe",
                    "scope": "workspace",
                    "post_observe": "none",
                }
            )

    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap("create a registry-aware tool", vocab="tool_needed")
    entry = SimpleNamespace(gap=gap, chain_id="chain1")
    session = FakeSession()

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "",
        execute_tool=lambda tool, params: ("written: tools/demo_registry_tool.py", 0),
        auto_commit=lambda message, paths=None: ("abc123def456", None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: None,
        extract_written_path=lambda output: "tools/demo_registry_tool.py",
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert compiler.ledger.stack[-1].gap.vocab == "reason_needed"
    assert compiler.ledger.stack[-1].gap.content_refs == ["tools/demo_registry_tool.py"]


def test_p12_render_log_resolution_caps_chars():
    rendered = loop._render_log_resolution("x" * (loop.LOG_RESOLVE_MAX_CHARS + 500), source_ref="bot.log")

    assert rendered.startswith("log_tail:bot.log")
    assert len(rendered) < loop.LOG_RESOLVE_MAX_CHARS + 200
    assert "chars<=" in rendered


def test_p12_extract_written_path_reads_json_path_field():
    output = json.dumps({"status": "sent", "path": "outbox/email_123.json"})

    assert loop._extract_written_path(output) == "outbox/email_123.json"


def test_p12_extract_written_path_reads_first_json_artifact():
    output = json.dumps({"status": "ok", "artifacts": ["assets/clip1.mp4", "assets/clip2.mp4"]})

    assert loop._extract_written_path(output) == "assets/clip1.mp4"


def test_p12_email_needed_executes_tool_and_post_observes_written_artifact():
    class FakeSession:
        def inject(self, content: str, role: str = "user"):
            pass

        def call(self, user_content: str = None) -> str:
            return json.dumps(
                {
                    "to": "recipient@example.com",
                    "subject": "Hello",
                    "body": "World",
                }
            )

    executed_tools: list[tuple[str, dict]] = []
    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap("send an email update", vocab="email_needed")
    entry = SimpleNamespace(gap=gap, chain_id="chain1")

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "",
        execute_tool=lambda tool, params: (
            executed_tools.append((tool, params)) or (json.dumps({"status": "sent", "path": "outbox/email_123.json"}), 0)
        ),
        auto_commit=lambda message, paths=None: ("abc123def456", None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: None,
        extract_written_path=loop._extract_written_path,
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=FakeSession(),
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert executed_tools == [("tools/email_send.py", {"to": "recipient@example.com", "subject": "Hello", "body": "World"})]
    assert compiler.ledger.stack[-1].gap.vocab == "hash_resolve_needed"
    assert compiler.ledger.stack[-1].gap.content_refs == ["outbox/email_123.json"]


def test_p12_git_revert_needed_uses_tool_reported_commit_for_post_observe():
    class FakeSession:
        def inject(self, content: str, role: str = "user"):
            pass

        def call(self, user_content: str = None) -> str:
            return json.dumps(
                {
                    "action": "revert",
                    "ref": "deadbeef1234",
                }
            )

    executed_tools: list[tuple[str, dict]] = []
    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap("revert the bad commit", vocab="git_revert_needed")
    entry = SimpleNamespace(gap=gap, chain_id="chain1")

    def fail_auto_commit(message, paths=None):
        raise AssertionError("auto_commit should not run when the tool already returns a commit")

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "",
        execute_tool=lambda tool, params: (
            executed_tools.append((tool, params)) or (json.dumps({"status": "ok", "commit": "feedface5678"}), 0)
        ),
        auto_commit=fail_auto_commit,
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: None,
        extract_written_path=loop._extract_written_path,
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "chains",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=FakeSession(),
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert executed_tools == [("tools/git_ops.py", {"action": "revert", "ref": "deadbeef1234"})]
    assert compiler.ledger.stack[-1].gap.vocab == "hash_resolve_needed"
    assert compiler.ledger.stack[-1].gap.content_refs == ["feedface5678"]


def test_p12_reason_needed_can_activate_inline_workflow_without_await():
    class FakeSession:
        def __init__(self):
            self.injected = []

        def inject(self, content: str, role: str = "user"):
            self.injected.append(content)

        def call(self, user_content: str = None) -> str:
            return json.dumps(
                {
                    "activate_ref": skill("hash_edit").hash,
                    "prompt": "apply child workflow",
                    "await_needed": False,
                }
            )

    activated: list[dict] = []
    traj = Trajectory()
    compiler = Compiler(traj)
    compiler.ledger.chain_states["parent_chain"] = ChainState.OPEN
    origin_step = make_step("origin")
    gap = make_gap("delegate child work", vocab="reason_needed")
    entry = SimpleNamespace(gap=gap, chain_id="parent_chain")

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "",
        execute_tool=lambda tool, params: ("", 0),
        auto_commit=lambda message, paths=None: (None, None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: None,
        extract_written_path=loop._extract_written_path,
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
        run_isolated_workflow=lambda ref, **kwargs: activated.append({"ref": ref, **kwargs}) or {"status": "ok", "activation_ref": ref, "store_kind": "background_agent"},
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "trajectory_store" / "command",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=FakeSession(),
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.step_result is not None
    assert activated == []
    assert outcome.step_result.desc.startswith(f"activated workflow:{skill('hash_edit').hash}")
    assert outcome.step_result.chain_id is not None
    child_chain = traj.chains.get(outcome.step_result.chain_id)
    assert child_chain is not None
    assert child_chain.parent_chain_id == "parent_chain"
    assert child_chain.activation_ref == skill("hash_edit").hash
    assert child_chain.steps[0] == outcome.step_result.hash
    assert any(entry.gap.vocab == "hash_resolve_needed" for entry in compiler.ledger.stack)
    assert all(entry.chain_id == child_chain.hash for entry in compiler.ledger.stack)
    assert compiler.background_refs() == []
    assert compiler.manual_await_refs() == []


def test_p12_reason_needed_can_activate_isolated_workflow_with_manual_await():
    class FakeSession:
        def call(self, user_content: str = None) -> str:
            return json.dumps(
                {
                    "activate_ref": skill("hash_edit").hash,
                    "prompt": "apply child workflow",
                    "await_needed": True,
                }
            )

        def inject(self, content: str, role: str = "user"):
            pass

    traj = Trajectory()
    compiler = Compiler(traj)
    compiler.ledger.chain_states["parent_chain"] = ChainState.OPEN
    origin_step = make_step("origin")
    gap = make_gap("delegate child work", vocab="reason_needed")
    entry = SimpleNamespace(gap=gap, chain_id="parent_chain")

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "",
        execute_tool=lambda tool, params: ("", 0),
        auto_commit=lambda message, paths=None: (None, None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: None,
        extract_written_path=loop._extract_written_path,
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
        run_isolated_workflow=lambda ref, **kwargs: {"status": "ok", "activation_ref": ref, "store_kind": "background_agent"},
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "trajectory_store" / "command",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=FakeSession(),
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert compiler.manual_await_refs() == [skill("hash_edit").hash]
    assert compiler.background_refs() == []


def test_p12_reason_needed_queues_completed_background_child_followup():
    class FakeSession:
        def call(self, user_content: str = None) -> str:
            return json.dumps(
                {
                    "activate_ref": skill("hash_edit").hash,
                    "prompt": "apply child workflow",
                    "await_needed": True,
                }
            )

        def inject(self, content: str, role: str = "user"):
            pass

    queued: list[dict] = []
    traj = Trajectory()
    compiler = Compiler(traj)
    compiler.ledger.chain_states["parent_chain"] = ChainState.OPEN
    origin_step = make_step("origin")
    gap = make_gap("delegate child work", vocab="reason_needed")
    entry = SimpleNamespace(gap=gap, chain_id="parent_chain")

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "",
        execute_tool=lambda tool, params: ("", 0),
        auto_commit=lambda message, paths=None: (None, None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: None,
        extract_written_path=loop._extract_written_path,
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
        run_isolated_workflow=lambda ref, **kwargs: {
            "status": "ok",
            "activation_ref": ref,
            "store_kind": "background_agent",
            "resolved": True,
            "trajectory": "trajectory_store/background_agent/hash_edit.trajectory.json",
            "chains_file": "trajectory_store/background_agent/hash_edit.chains.json",
            "tree_render": "chain:child",
            "response": "child complete",
        },
        queue_background_completion=lambda payload: queued.append(payload),
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "trajectory_store" / "command",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=FakeSession(),
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert queued
    assert queued[0]["activation_ref"] == skill("hash_edit").hash
    assert queued[0]["response"] == "child complete"


def test_p12_reason_needed_missing_isolated_child_surfaces_rogue():
    class FakeSession:
        def __init__(self):
            self.injected = []

        def call(self, user_content: str = None) -> str:
            return json.dumps(
                {
                    "activate_ref": f"architect:{skill('architect').hash}",
                    "prompt": "run architecture flow",
                    "await_needed": True,
                }
            )

        def inject(self, content: str, role: str = "user"):
            self.injected.append(content)

    traj = Trajectory()
    compiler = Compiler(traj)
    compiler.ledger.chain_states["parent_chain"] = ChainState.OPEN
    origin_step = make_step("origin")
    gap = make_gap("delegate architecture audit", vocab="reason_needed")
    entry = SimpleNamespace(gap=gap, chain_id="parent_chain")
    session = FakeSession()

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "",
        execute_tool=lambda tool, params: ("", 0),
        auto_commit=lambda message, paths=None: (None, None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: None,
        extract_written_path=loop._extract_written_path,
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
        run_isolated_workflow=lambda ref, **kwargs: {"status": "missing", "activation_ref": ref, "store_kind": "background_agent"},
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "trajectory_store" / "command",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.step_result is not None
    assert outcome.step_result.rogue is True
    assert outcome.step_result.failure_source == "reason_needed"
    assert "isolated workflow launch failed" in (outcome.step_result.failure_detail or "")


def test_p12_queue_background_completion_dedupes(tmp_path):
    state = loop._state_paths(
        traj_file=tmp_path / "trajectory.json",
        chains_file=tmp_path / "chains.json",
        chains_dir=tmp_path / "trajectory_store" / "command",
    )
    payload = {
        "activation_ref": "hash_edit:abcd",
        "trajectory": "trajectory_store/background_agent/hash_edit.trajectory.json",
        "response": "done",
    }
    loop._queue_background_completion(state, payload)
    loop._queue_background_completion(state, payload)
    data = json.loads(loop._background_completion_file(state).read_text(encoding="utf-8"))
    assert len(data) == 1


def test_p12_discord_pop_background_completion_notifications_formats_and_clears(tmp_path, monkeypatch):
    monkeypatch.setattr(discord_bot_module, "STATE_ROOT", tmp_path)
    paths = discord_bot_module.state_paths_for_contact("discord:123")
    paths["background_completions_file"].parent.mkdir(parents=True, exist_ok=True)
    paths["background_completions_file"].write_text(
        json.dumps(
            [
                {
                    "activation_ref": "principles:f9ba012dfe64",
                    "tree_render": "chain:child",
                    "response": "child synth",
                }
            ]
        ),
        encoding="utf-8",
    )
    messages = discord_bot_module.pop_background_completion_notifications("discord:123")
    assert len(messages) == 1
    assert "Background workflow complete: principles:f9ba012dfe64" in messages[0]
    assert "Semantic Tree:" in messages[0]
    assert "Response:" in messages[0]
    assert not paths["background_completions_file"].exists()


def test_p12_reason_needed_can_activate_inline_workflow_with_attached_refs():
    class FakeSession:
        def call(self, user_content: str = None) -> str:
            return json.dumps(
                {
                    "activate_ref": skill("debug").hash,
                    "prompt": "debug the attached failure",
                    "await_needed": False,
                    "content_refs": ["bot.log", "skills/entities/property_brief.st"],
                    "step_refs": ["deadbeef1234"],
                }
            )

        def inject(self, content: str, role: str = "user"):
            pass

    activated: list[dict] = []
    traj = Trajectory()
    compiler = Compiler(traj)
    compiler.ledger.chain_states["parent_chain"] = ChainState.OPEN
    origin_step = make_step("origin")
    gap = make_gap("delegate child debug work", vocab="reason_needed")
    entry = SimpleNamespace(gap=gap, chain_id="parent_chain")

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "resolved activation context",
        execute_tool=lambda tool, params: ("", 0),
        auto_commit=lambda message, paths=None: (None, None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: None,
        extract_written_path=loop._extract_written_path,
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
        run_isolated_workflow=lambda ref, **kwargs: activated.append({"ref": ref, **kwargs}) or {"status": "ok", "activation_ref": ref, "store_kind": "background_agent"},
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "trajectory_store" / "command",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=FakeSession(),
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.step_result is not None
    assert activated == []
    assert outcome.step_result.desc.startswith(f"activated workflow:{skill('debug').hash}")
    injected_gaps = outcome.step_result.gaps
    assert injected_gaps
    assert any("Activation task: debug the attached failure" in g.desc for g in injected_gaps)
    assert any("Activation content refs:" in g.desc for g in injected_gaps)
    assert any("Activation step refs:" in g.desc for g in injected_gaps)
    assert any("bot.log" in g.content_refs for g in injected_gaps)
    assert any("skills/entities/property_brief.st" in g.content_refs for g in injected_gaps)
    assert any("deadbeef1234" in g.step_refs for g in injected_gaps)
    assert compiler.background_refs() == []


def test_p12_inline_child_chain_close_emits_parent_post_observe_reason():
    traj = Trajectory()
    compiler = Compiler(traj, current_turn=7)

    parent_origin = make_step("parent origin")
    traj.append(parent_origin)
    parent_chain = Chain.create(origin_gap="parent_gap", first_step=parent_origin.hash)
    traj.add_chain(parent_chain)
    compiler.ledger.chain_states[parent_chain.hash] = ChainState.OPEN

    child_gap = make_gap("resolve child branch", vocab="hash_resolve_needed")
    child_step = make_step("child resolve", gaps=[child_gap])
    traj.append(child_step)
    child_chain = Chain.create(origin_gap="child_gap", first_step=child_step.hash)
    child_chain.parent_chain_id = parent_chain.hash
    child_chain.activation_ref = skill("debug").hash
    child_chain.await_policy = "none"
    child_step.chain_id = child_chain.hash
    traj.add_chain(child_chain)
    compiler.ledger.chain_states[child_chain.hash] = ChainState.ACTIVE
    compiler.active_chain = child_chain

    compiler.resolve_current_gap(child_gap.hash)

    assert child_chain.resolved is True
    assert child_chain.post_observe_review_emitted is True
    assert compiler.ledger.stack
    review_entry = compiler.ledger.stack[-1]
    assert review_entry.chain_id == parent_chain.hash
    assert review_entry.gap.vocab == "reason_needed"
    assert "post-observe review" in review_entry.gap.desc
    assert skill("debug").hash in review_entry.gap.content_refs
    assert child_chain.hash in review_entry.gap.content_refs
    assert child_step.hash in review_entry.gap.step_refs

    review_step = traj.steps[parent_chain.steps[-1]]
    assert child_chain.hash in review_step.content_refs
    assert child_step.hash in review_step.step_refs


def test_p12_chain_backed_vocab_injects_workflow_inline():
    class FakeSession:
        def __init__(self):
            self.injected = []

        def inject(self, content: str, role: str = "user"):
            self.injected.append(content)

        def call(self, user_content: str = None) -> str:
            return "{}"

    activated: list[dict] = []
    traj = Trajectory()
    compiler = Compiler(traj)
    compiler.ledger.chain_states["parent_chain"] = ChainState.OPEN
    origin_step = make_step("origin")
    gap = make_gap(
        "Activate the architect workflow to audit docs and sync stale files.",
        vocab="architect_needed",
        content_refs=["docs/ARCHITECTURE.md"],
        step_refs=["deadbeef1234"],
    )
    entry = SimpleNamespace(gap=gap, chain_id="parent_chain")
    session = FakeSession()

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "resolved architect activation context",
        execute_tool=lambda tool, params: ("", 0),
        auto_commit=lambda message, paths=None: (None, None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: None,
        extract_written_path=lambda output: None,
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
        run_isolated_workflow=lambda ref, **kwargs: activated.append({"ref": ref, **kwargs}) or {"status": "ok", "activation_ref": ref, "store_kind": "background_agent"},
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "trajectory_store" / "command",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.step_result is not None
    assert activated == []
    assert outcome.step_result.desc.startswith(f"activated workflow:{skill('architect').hash}")
    assert outcome.step_result.chain_id is not None
    child_chain = traj.chains.get(outcome.step_result.chain_id)
    assert child_chain is not None
    assert child_chain.parent_chain_id == "parent_chain"
    assert child_chain.activation_ref == skill("architect").hash
    assert any(g.vocab == "hash_resolve_needed" for g in outcome.step_result.gaps)
    assert compiler.manual_await_refs() == []
    assert compiler.background_refs() == []
    assert any(entry.gap.vocab == "hash_resolve_needed" and entry.chain_id == child_chain.hash for entry in compiler.ledger.stack)
    assert any("## Chain workflow activation" in content for content in session.injected)


def test_p12_inline_skill_activation_only_admits_root_phase():
    reg = registry()
    architect = skill("architect")
    traj = Trajectory()
    compiler = Compiler(traj)
    parent_origin = make_step("parent origin")
    parent_gap = make_gap("activate architect", vocab="architect_needed")
    parent_chain = Chain.create(origin_gap=parent_gap.hash, first_step=parent_origin.hash)
    traj.add_chain(parent_chain)
    compiler.active_chain = parent_chain

    activation_step = manifest_engine_module.activate_skill_package(
        architect,
        architect.hash,
        parent_gap,
        parent_origin,
        parent_chain.hash,
        0,
        task_prompt="run architect",
        activation_content_refs=[architect.hash],
        registry=reg,
        chains_dir=ROOT / "trajectory_store" / "command",
        cors_root=ROOT,
        tool_map=loop.TOOL_MAP,
    )

    compiler.emit(activation_step)
    traj.append(activation_step)

    assert len(compiler.ledger.stack) == 1
    assert compiler.ledger.stack[-1].gap.phase_id == "phase_resolve_source_1"
    assert compiler.ledger.stack[-1].gap.phase_state == "active"
    planned = [gap for gap in activation_step.gaps if gap.phase_state == "planned"]
    assert planned
    assert {gap.phase_id for gap in planned} >= {
        "phase_resolve_principles_2",
        "phase_resolve_docs_3",
        "phase_resolve_tests_4",
        "phase_analyse_and_handoff_fix_5",
    }


def test_p12_inline_skill_activation_promotes_successor_phase_on_resolution():
    reg = registry()
    architect = skill("architect")
    traj = Trajectory()
    compiler = Compiler(traj)
    parent_origin = make_step("parent origin")
    parent_gap = make_gap("activate architect", vocab="architect_needed")
    parent_chain = Chain.create(origin_gap=parent_gap.hash, first_step=parent_origin.hash)
    traj.add_chain(parent_chain)
    compiler.active_chain = parent_chain

    activation_step = manifest_engine_module.activate_skill_package(
        architect,
        architect.hash,
        parent_gap,
        parent_origin,
        parent_chain.hash,
        0,
        task_prompt="run architect",
        activation_content_refs=[architect.hash],
        registry=reg,
        chains_dir=ROOT / "trajectory_store" / "command",
        cors_root=ROOT,
        tool_map=loop.TOOL_MAP,
    )

    compiler.emit(activation_step)
    traj.append(activation_step)

    entry, signal = compiler.next()
    assert signal == GovernorSignal.ALLOW
    assert entry is not None
    assert entry.gap.phase_id == "phase_resolve_source_1"

    compiler.resolve_current_gap(entry.gap.hash)

    assert len(compiler.ledger.stack) == 1
    assert compiler.ledger.stack[-1].gap.phase_id == "phase_resolve_principles_2"
    assert compiler.ledger.stack[-1].gap.phase_state == "active"


def test_p12_hash_edit_compose_prompt_includes_targeting_rules_and_refs():
    class FakeSession:
        def __init__(self):
            self.prompts = []

        def inject(self, content: str, role: str = "user"):
            pass

        def call(self, user_content: str = None) -> str:
            self.prompts.append(user_content or "")
            return json.dumps({
                "action": "write",
                "path": "docs/ARCHITECTURE.md",
                "content": "updated",
            })

    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap(
        "Update the stale architecture doc using the attached context.",
        vocab="hash_edit_needed",
        content_refs=["docs/ARCHITECTURE.md"],
        step_refs=["deadbeef1234"],
    )
    entry = SimpleNamespace(gap=gap, chain_id="chain1")
    session = FakeSession()

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "resolved architecture context",
        execute_tool=lambda tool, params: ("Written: /Users/k2invested/Desktop/cors/docs/ARCHITECTURE.md", 0),
        auto_commit=lambda message, paths=None: ("abc123", None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: None,
        extract_written_path=loop._extract_written_path,
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "trajectory_store" / "command",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.step_result is not None
    assert session.prompts
    prompt = session.prompts[0]
    assert "Available content refs: ['docs/ARCHITECTURE.md']" in prompt
    assert "Available step refs: ['deadbeef1234']" in prompt
    assert "Prefer concrete non-.st workspace files" in prompt
    assert "Treat workflow/entity .st refs as context only" in prompt


def test_p12_execution_failure_auto_activates_debug(monkeypatch):
    class FakeSession:
        def __init__(self):
            self.injected = []

        def inject(self, content: str, role: str = "user"):
            self.injected.append(content)

        def call(self, user_content: str = None) -> str:
            return json.dumps({"command": "pytest -q"})

    class Result:
        stdout = ""
        stderr = "boom"
        returncode = 1

    monkeypatch.setattr(execution_engine_module.subprocess, "run", lambda *args, **kwargs: Result())

    activated: list[dict] = []
    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap("run failing test suite", vocab="bash_needed")
    entry = SimpleNamespace(gap=gap, chain_id="chain1")
    session = FakeSession()

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "resolved failure context",
        execute_tool=lambda tool, params: ("boom", 1),
        auto_commit=lambda message, paths=None: (None, None),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: json.loads(raw)["command"],
        extract_written_path=lambda output: None,
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
        run_isolated_workflow=lambda ref, **kwargs: activated.append({"ref": ref, **kwargs}) or {"status": "ok", "activation_ref": ref, "store_kind": "background_agent"},
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "trajectory_store" / "command",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.step_result is not None
    assert outcome.step_result.rogue is True
    assert activated
    assert activated[0]["ref"] == skill("debug").hash
    assert activated[0]["await_policy"] == "none"
    assert activated[0]["task_prompt"].startswith("Debug execution failure.")
    assert activated[0]["activation_context"] == "resolved failure context"
    assert compiler.background_refs()[0] == skill("debug").hash
    assert any("## Auto Debug Activation" in content for content in session.injected)


def test_p12_protected_path_violation_auto_activates_debug():
    class FakeSession:
        def __init__(self):
            self.injected = []

        def inject(self, content: str, role: str = "user"):
            self.injected.append(content)

        def call(self, user_content: str = None) -> str:
            return json.dumps({"path": "system/tool_registry.py", "old": "x", "new": "y"})

    activated: list[dict] = []
    traj = Trajectory()
    compiler = Compiler(traj)
    origin_step = make_step("origin")
    gap = make_gap("edit protected file", vocab="hash_edit_needed")
    entry = SimpleNamespace(gap=gap, chain_id="chain1")
    session = FakeSession()

    hooks = execution_engine_module.ExecutionHooks(
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "policy failure context",
        execute_tool=lambda tool, params: ("Written: /Users/k2invested/Desktop/cors/system/tool_registry.py", 0),
        auto_commit=lambda message, paths=None: (None, "reason_needed"),
        parse_step_output=loop._parse_step_output,
        extract_json=lambda raw: json.loads(raw),
        extract_command=lambda raw: None,
        extract_written_path=lambda output: "/Users/k2invested/Desktop/cors/system/tool_registry.py",
        is_reprogramme_intent=lambda intent: False,
        load_tree_policy=lambda: {},
        match_policy=lambda path, policy: None,
        resolve_entity=lambda content_refs, registry_obj, trajectory: None,
        render_step_network=lambda registry_obj: "step_network",
        emit_reason_skill=lambda reason_skill, gap_obj, origin, chain_id: make_step("reason"),
        git=lambda cmd, cwd=None: "auto-revert: protected path violation",
        commit_assessment=lambda commit_sha: [],
        step_assessment=lambda before, after, path=None: [],
        run_isolated_workflow=lambda ref, **kwargs: activated.append({"ref": ref, **kwargs}) or {"status": "ok", "activation_ref": ref, "store_kind": "background_agent"},
    )
    config = execution_engine_module.ExecutionConfig(
        cors_root=ROOT,
        chains_dir=ROOT / "trajectory_store" / "command",
        tool_map=loop.TOOL_MAP,
        deterministic_vocab=loop.DETERMINISTIC_VOCAB,
        observation_only_vocab=loop.OBSERVATION_ONLY_VOCAB,
    )

    outcome = execution_engine_module.execute_iteration(
        entry=entry,
        signal=GovernorSignal.ALLOW,
        session=session,
        origin_step=origin_step,
        trajectory=traj,
        compiler=compiler,
        registry=registry(),
        current_turn=0,
        hooks=hooks,
        config=config,
    )

    assert outcome.step_result is not None
    assert outcome.step_result.rogue is True
    assert activated
    assert activated[0]["ref"] == skill("debug").hash
    assert "immutable path violation" in activated[0]["task_prompt"]


def test_p12_debug_failure_does_not_recursively_activate_debug():
    origin_step = make_step("origin", content_refs=[skill("debug").hash])
    rogue_step = make_step("rogue", content_refs=[skill("debug").hash], step_refs=["attempt"])
    gap = make_gap("run failing debug verification", vocab="bash_needed", content_refs=[skill("debug").hash])

    payload = execution_engine_module._debug_activation_payload(
        registry=registry(),
        origin_step=origin_step,
        rogue_step=rogue_step,
        gap=gap,
        rogue_kind="tool_failure",
        failure_source="tools/code_exec.py",
        failure_detail="boom",
    )

    assert payload is None


def test_p12_run_no_gap_discord_profile_sync_coerces_entity_shape(monkeypatch):
    captured: dict[str, dict] = {}

    class FakeSession:
        def set_system(self, content: str):
            pass

        def inject(self, content: str, role: str = "user"):
            pass

        def call(self, user_content: str = None) -> str:
            return json.dumps({
                "version": "semantic_skeleton.v1",
                "artifact": {"kind": "hybrid", "protected_kind": "action"},
                "name": "courtney",
                "desc": "courtney profile",
                "trigger": "on_contact:discord:123",
                "root": "phase_root",
                "phases": [{"id": "phase_root"}],
                "closure": {"success": {}},
                "semantics": {
                    "identity": {"username": "courtney"},
                    "preferences": {"football": True},
                },
            })

    def fake_execute_tool(tool: str, intent: dict):
        captured["intent"] = intent
        return ("Written: /Users/k2invested/Desktop/cors/skills/entities/courtney.st", 0)

    monkeypatch.setattr(loop, "Session", lambda model=None: FakeSession())
    monkeypatch.setattr(loop, "execute_tool", fake_execute_tool)
    monkeypatch.setattr(loop, "auto_commit", lambda message, paths=None: ("sync123", None))

    step = loop._run_no_gap_discord_profile_sync(
        "discord:123",
        "i like football, my favourite team is tottenham",
        identity_skill=bootstrap_identity_skill(),
        registry=registry(),
        trajectory=Trajectory(),
        origin_step=make_step("origin"),
    )

    assert step is not None
    assert captured["intent"]["artifact"]["kind"] == "entity"
    assert captured["intent"]["artifact"]["protected_kind"] == "entity"
    assert "root" not in captured["intent"]
    assert "phases" not in captured["intent"]
    assert "closure" not in captured["intent"]


def test_p12_st_builder_reuses_existing_contact_trigger_path(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    admin_path = skills_dir / "admin.st"
    admin_path.write_text(json.dumps({
        "name": "admin",
        "desc": "canonical admin",
        "trigger": "on_contact:discord:784778107013431296",
        "steps": [{"action": "load_identity", "desc": "load", "post_diff": False}],
        "identity": {"discord_user_id": "784778107013431296"},
    }))

    path = st_builder_module.write_st(
        {
            "name": "Kenny",
            "desc": "updated",
            "trigger": "on_contact:discord:784778107013431296",
            "steps": [],
            "identity": {"discord_user_id": "784778107013431296"},
        },
        output_dir=str(skills_dir),
    )

    assert path == str(admin_path)
    rewritten = json.loads(admin_path.read_text())
    assert rewritten["name"] == "admin"
    assert rewritten["desc"] == "canonical admin"
    assert rewritten["trigger"] == "on_contact:discord:784778107013431296"
    assert len(rewritten["steps"]) == 1


def test_p12_st_builder_writes_new_actions_into_actions_tree(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    path = st_builder_module.write_st(
        {
            "name": "research",
            "desc": "research workflow",
            "trigger": "manual",
            "artifact": {"kind": "action", "protected_kind": "action"},
            "steps": [{"action": "resolve", "desc": "resolve target", "vocab": "hash_resolve_needed", "post_diff": False}],
        },
        output_dir=str(skills_dir),
    )

    assert path == str(skills_dir / "actions" / "research.st")


def test_p12_resolve_hash_supports_skill_source_path(monkeypatch):
    monkeypatch.setattr(loop, "_skill_registry", registry())
    rendered = loop.resolve_hash("skills/admin.st", Trajectory())
    assert rendered is not None
    assert rendered.startswith("semantic_tree:skill_package:")
    assert 'package:admin "' in rendered


def test_p12_pattern_tool_params_include_path_when_pattern_is_quoted():
    gap = make_gap(
        "Need to find \"mirror_then_extend\" in admin preferences.",
        content_refs=["skills/admin.st"],
        vocab="pattern_needed",
    )
    assert execution_engine_module._pattern_tool_params(gap) == {
        "pattern": "mirror_then_extend",
        "path": "skills/admin.st",
    }


def test_p12_canonicalize_content_ref_maps_skill_source_to_hash(monkeypatch):
    monkeypatch.setattr(loop, "_skill_registry", registry())
    skill = registry().resolve_by_name("admin")
    assert skill is not None
    assert loop._canonicalize_content_ref("skills/admin.st") == skill.hash


def test_p12_canonicalize_content_ref_maps_named_hash_alias_to_hash(monkeypatch):
    monkeypatch.setattr(loop, "_skill_registry", registry())
    skill = registry().resolve_by_name("admin")
    assert skill is not None
    assert loop._canonicalize_content_ref(f"kenny:{skill.hash}") == skill.hash


def test_p12_canonicalize_content_ref_maps_repo_path_to_head_object_hash(monkeypatch):
    monkeypatch.setattr(loop, "_skill_registry", registry())
    expected = loop.git(["rev-parse", "HEAD:docs/ARCHITECTURE.md"]).strip().splitlines()[0]
    assert loop._canonicalize_content_ref("docs/ARCHITECTURE.md") == expected


def test_p12_parse_step_output_canonicalizes_gap_content_refs(monkeypatch):
    monkeypatch.setattr(loop, "_skill_registry", registry())
    raw = json.dumps(
        {
            "gaps": [
                {
                    "desc": "inspect admin",
                    "content_refs": ["skills/admin.st"],
                    "step_refs": [],
                    "vocab": "hash_resolve_needed",
                    "relevance": 0.9,
                    "confidence": 0.8,
                }
            ]
        }
    )
    step, gaps = loop._parse_step_output(raw, step_refs=[], content_refs=["docs/ARCHITECTURE.md"])
    skill = registry().resolve_by_name("admin")
    assert skill is not None
    assert gaps[0].content_refs == [skill.hash]
    assert step.content_refs == [loop.git(["rev-parse", "HEAD:docs/ARCHITECTURE.md"]).strip().splitlines()[0]]


def test_p12_compiler_next_redirects_to_alternative_chain_without_recursive_loop(monkeypatch):
    compiler = Compiler(Trajectory())
    first = make_gap("first", vocab="pattern_needed")
    second = make_gap("second", vocab="pattern_needed")
    compiler.ledger.push_origin(first, "c1")
    compiler.ledger.push_origin(second, "c2")

    def fake_govern(entry, chain_length, state):
        if entry.chain_id == "c2":
            return GovernorSignal.REDIRECT
        return GovernorSignal.ALLOW

    monkeypatch.setattr(compile_module, "govern", fake_govern)

    entry, signal = compiler.next()

    assert entry is not None
    assert entry.chain_id == "c1"
    assert signal == GovernorSignal.ALLOW
    assert len(compiler.governor_state.vectors) == 1


def test_p12_compiler_next_redirect_single_chain_falls_back_without_state_duplication(monkeypatch):
    compiler = Compiler(Trajectory())
    gap = make_gap("only", vocab="pattern_needed")
    compiler.ledger.push_origin(gap, "only-chain")

    monkeypatch.setattr(
        compile_module,
        "govern",
        lambda entry, chain_length, state: GovernorSignal.REDIRECT,
    )

    entry, signal = compiler.next()

    assert entry is not None
    assert entry.chain_id == "only-chain"
    assert signal == GovernorSignal.ALLOW
    assert len(compiler.governor_state.vectors) == 1
