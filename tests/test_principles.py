"""Structural principle suite for cors.

This replaces the old print-driven script with a real pytest suite.
The goal is broad coverage of the mechanisms described in PRINCIPLES.md:
hash layers, gap admission, vocab routing, chain lifecycle, codons,
temporal rendering, and supporting infrastructure.
"""

from __future__ import annotations

import json
import re
import sys
import time
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import compile as compile_module
import execution_engine as execution_engine_module
import loop
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
from skills.loader import Skill, SkillRegistry, load_all, load_skill
from step import Chain, Epistemic, Gap, Step, Trajectory, absolute_time, blob_hash, chain_hash, relative_time
from tools import chain_to_st as chain_to_st_module
from tools import st_builder as st_builder_module

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
    ("step_roundtrip_rogue", lambda: (lambda restored: restored.rogue and restored.rogue_kind == "policy_violation")(
        Step.from_dict(Step.create("rogue", rogue=True, rogue_kind="policy_violation", failure_source="tree_policy").to_dict())
    )),
    ("chain_rehashes_on_add", lambda: (lambda c: (c.add_step("b"), c.hash)[1] != chain_hash(["gap", "a"]))(Chain.create("gap", "a"))),
    ("trajectory_resolves_step_and_gap", lambda: (lambda t, s, g: t.resolve(s.hash) == s and t.resolve_gap(g.hash) == g)(
        *(lambda gap: (lambda step, traj: (traj.append(step), traj, step, gap)[1:])(make_step("origin", gaps=[gap]), Trajectory()))(make_gap("g"))
    )),
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


P3_CASES = [
    ("observe_pattern_needed", lambda: is_observe("pattern_needed")),
    ("observe_hash_resolve_needed", lambda: is_observe("hash_resolve_needed")),
    ("observe_email_needed", lambda: is_observe("email_needed")),
    ("observe_external_context", lambda: is_observe("external_context")),
    ("observe_clarify_needed", lambda: is_observe("clarify_needed")),
    ("mutate_hash_edit_needed", lambda: is_mutate("hash_edit_needed")),
    ("mutate_stitch_needed", lambda: is_mutate("stitch_needed")),
    ("mutate_content_needed", lambda: is_mutate("content_needed")),
    ("mutate_script_edit_needed", lambda: is_mutate("script_edit_needed")),
    ("mutate_command_needed", lambda: is_mutate("command_needed")),
    ("mutate_message_needed", lambda: is_mutate("message_needed")),
    ("mutate_json_patch_needed", lambda: is_mutate("json_patch_needed")),
    ("mutate_git_revert_needed", lambda: is_mutate("git_revert_needed")),
    ("bridge_reason_needed", lambda: is_bridge("reason_needed")),
    ("bridge_await_needed", lambda: is_bridge("await_needed")),
    ("bridge_commit_needed", lambda: is_bridge("commit_needed")),
    ("bridge_reprogramme_needed", lambda: is_bridge("reprogramme_needed")),
    ("deterministic_vocab_is_hash_resolve", lambda: loop.DETERMINISTIC_VOCAB == {"hash_resolve_needed"}),
    ("observation_only_contains_external_context", lambda: "external_context" in loop.OBSERVATION_ONLY_VOCAB),
    ("tool_map_hash_edit_routes_hash_manifest", lambda: loop.TOOL_MAP["hash_edit_needed"]["tool"] == "tools/hash_manifest.py"),
    ("tool_map_stitch_has_post_observe", lambda: loop.TOOL_MAP["stitch_needed"]["post_observe"] == "ui_output/"),
    ("priority_observe_before_mutate", lambda: vocab_priority("pattern_needed") < vocab_priority("content_needed")),
    ("priority_mutate_before_reason", lambda: vocab_priority("content_needed") < vocab_priority("reason_needed")),
    ("priority_reason_before_await", lambda: vocab_priority("reason_needed") < vocab_priority("await_needed")),
    ("priority_await_before_commit", lambda: vocab_priority("await_needed") < vocab_priority("commit_needed")),
    ("priority_commit_before_reprogramme", lambda: vocab_priority("commit_needed") < vocab_priority("reprogramme_needed")),
    ("tree_policy_skills_reroutes_reprogramme", lambda: loop._match_policy("skills/admin.st", loop._load_tree_policy())["on_mutate"] == "reprogramme_needed"),
    ("tree_policy_admin_sets_entity_editor_mode", lambda: loop._match_policy("skills/admin.st", loop._load_tree_policy())["reprogramme_mode"] == "entity_editor"),
    ("tree_policy_entities_reroutes_reprogramme", lambda: loop._match_policy("skills/entities/clinton.st", loop._load_tree_policy())["on_mutate"] == "reprogramme_needed"),
    ("tree_policy_entities_set_entity_editor_mode", lambda: loop._match_policy("skills/entities/clinton.st", loop._load_tree_policy())["reprogramme_mode"] == "entity_editor"),
    ("tree_policy_actions_set_action_editor_mode", lambda: loop._match_policy("skills/actions/hash_edit.st", loop._load_tree_policy())["reprogramme_mode"] == "action_editor"),
    ("tree_policy_exact_match_compile_immutable", lambda: loop._match_policy("compile.py", loop._load_tree_policy())["immutable"] is True),
    ("tree_policy_longest_prefix_wins", lambda: loop._match_policy("skills/codons/reason.st", loop._load_tree_policy())["on_reject"] == "reason_needed"),
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


P5_CASES = [
    ("registry_loads_admin", lambda: registry().resolve_by_name("admin") is not None),
    ("registry_loads_hash_edit", lambda: registry().resolve_by_name("hash_edit") is not None),
    ("registry_treats_chain_spec_as_entity", lambda: skill("commitment_chain_construction_spec").artifact_kind == "entity"),
    ("admin_display_name_is_canonical_admin", lambda: skill("admin").display_name == "admin"),
    ("resolve_by_hash_returns_skill", lambda: registry().resolve(skill("admin").hash) == skill("admin")),
    ("hash_edit_skill_exists", lambda: skill("hash_edit").name == "hash_edit"),
    ("render_for_prompt_has_header", lambda: registry().render_for_prompt().startswith("## Available Skills")),
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
    ("resolve_entity_reads_action_package_when_not_entity", lambda: '"name": "hash_edit"' in loop._resolve_entity([skill("hash_edit").hash], registry(), Trajectory())),
    ("render_entity_has_identity_block", lambda: "identity:" in loop._render_entity(skill("admin"))),
    ("render_entity_has_steps_summary", lambda: "steps:" in loop._render_entity(skill("admin"))),
    ("find_identity_skill_returns_admin", lambda: loop._find_identity_skill("discord:784778107013431296", registry()) == skill("admin")),
    ("render_identity_has_preferences", lambda: "## Preferences" in loop._render_identity(skill("admin"))),
    ("render_identity_has_access_rules_when_present", lambda: "## Access Rules" in loop._render_identity(skill("admin")) if "access_rules" in skill_data("admin") else True),
    ("reprogramme_skill_trigger_is_vocab", lambda: skill("reprogramme").trigger == "on_vocab:reprogramme_needed"),
    ("reprogramme_skill_all_steps_loaded", lambda: skill("reprogramme").step_count() == 3),
    ("reason_skill_mentions_persistence_judgment", lambda: "persistence" in skill_data("reason")["desc"].lower()),
    ("reprogramme_skill_says_it_does_not_own_judgment", lambda: "does not own the judgment layer" in skill_data("reprogramme")["desc"].lower()),
    ("pre_diff_prompt_routes_inferred_preferences_to_reason_first", lambda: "use reason_needed first to judge whether it should become semantic state" in loop.PRE_DIFF_SYSTEM.lower()),
    ("pre_diff_prompt_says_stable_preferences_are_not_no_gap", lambda: "stable user-model updates are not no-gap" in loop.PRE_DIFF_SYSTEM.lower()),
    ("pre_diff_prompt_says_stable_preference_statements_count_as_action", lambda: "stable first-person preference statements about future interaction count as action" in loop.PRE_DIFF_SYSTEM.lower()),
    ("pre_diff_prompt_says_bridge_codons_are_primitives", lambda: "treat the bridge codons as primitives" in loop.PRE_DIFF_SYSTEM.lower()),
    ("pre_diff_prompt_says_reason_is_stateful_judgment_primitive", lambda: "reason_needed is the primitive for stateful judgment" in loop.PRE_DIFF_SYSTEM.lower()),
    ("pre_diff_prompt_says_reason_before_clarify", lambda: "do not use clarify_needed as the first response to uncertainty" in loop.PRE_DIFF_SYSTEM.lower()),
    ("pre_diff_prompt_says_reprogramme_is_semantic_persistence_primitive", lambda: "reprogramme_needed is the primitive for stateless semantic persistence" in loop.PRE_DIFF_SYSTEM.lower()),
    ("init_user_intent_uses_on_contact_trigger", lambda: loop._build_init_user_intent("discord:123", "hi")["trigger"] == "on_contact:discord:123"),
    ("init_user_intent_starts_pending", lambda: loop._build_init_user_intent("discord:123", "hi")["init"]["status"] == "pending"),
    ("init_user_intent_prefers_get_to_know_questions", lambda: loop._build_init_user_intent("discord:123", "hi")["preferences"]["onboarding"]["get_to_know_entity"] is True),
    ("init_user_intent_bootstrap_is_only_deterministic_reprogramme", lambda: loop._build_init_user_intent("discord:123", "hi")["preferences"]["onboarding"]["deterministic_reprogramme_mode"] == "bootstrap_only"),
    ("init_user_intent_passive_reprogramme_is_optional", lambda: loop._build_init_user_intent("discord:123", "hi")["preferences"]["onboarding"]["passive_reprogramme_optional"] is True),
    ("init_user_intent_loads_onboarding_preferences", lambda: any(step["action"] == "load_onboarding_preferences" for step in loop._build_init_user_intent("discord:123", "hi")["steps"])),
    ("reprogramme_intent_accepts_semantic_skeleton", lambda: loop._is_reprogramme_intent({
        "version": "semantic_skeleton.v1",
        "artifact": {"kind": "entity"},
        "name": "admin",
        "desc": "admin entity",
        "trigger": "manual",
        "refs": {},
        "semantics": {},
    })),
]


P6_CASES = [
    ("grounded_zero_without_refs", lambda: Compiler(Trajectory())._compute_grounded(make_gap("g")) == 0.0),
    ("grounded_positive_with_refs", lambda: Compiler(seed_trajectory("blob_a"))._compute_grounded(make_gap("g", content_refs=["blob_a"])) > 0.0),
    ("unsourced_gap_penalty_keeps_low_relevance_out", lambda: build_origin_context(relevance=0.49, refs=[]).compiler.gap_count() == 0),
    ("unsourced_gap_at_threshold_can_enter", lambda: build_origin_context(relevance=0.5, refs=[]).compiler.gap_count() == 1),
    ("tag_ref_prefixes_step_layer", lambda: Trajectory()._tag_ref("abc123", "step") == "step:abc123"),
    ("tag_ref_leaves_content_bare", lambda: Trajectory()._tag_ref("abc123", "content") == "abc123"),
    ("tag_ref_uses_registry_name", lambda: build_chain_context().traj._tag_ref(skill("admin").hash, "content", registry()).startswith("admin:")),
    ("render_refs_combines_layers", lambda: "step:parent" in Trajectory()._render_refs(["parent"], ["blob"], None) and "blob" in Trajectory()._render_refs(["parent"], ["blob"], None)),
    ("render_recent_names_skill_hashes", lambda: "admin:" in build_chain_context().traj.render_recent(5, registry())),
    ("resolve_hash_renders_step_branch", lambda: (lambda ctx: "step:" in loop.resolve_hash(ctx.step1.hash, ctx.traj))(build_chain_context())),
    ("resolve_hash_renders_gap_tree", lambda: (lambda ctx: "gap:" in loop.resolve_hash(ctx.gap.hash, ctx.traj))(build_chain_context())),
    ("resolve_hash_returns_none_for_unknown", lambda: loop.resolve_hash("not_a_real_hash", Trajectory()) is None),
    ("render_gap_tree_active_status", lambda: "status: active" in loop._render_gap_tree(make_gap("g"))),
    ("render_gap_tree_dormant_status", lambda: "status: dormant" in loop._render_gap_tree(make_gap("g", dormant=True))),
    ("render_gap_tree_resolved_status", lambda: "status: resolved" in loop._render_gap_tree(make_gap("g", resolved=True))),
    ("step_refs_and_content_refs_render_separately", lambda: "step:prior_step" in build_chain_context().traj.render_recent(5, registry()) and "blob_cfg" in build_chain_context().traj.render_recent(5, registry())),
    ("gap_hash_encodes_content_citation", lambda: make_gap("g", content_refs=["blob_a"]).hash != make_gap("g", content_refs=["blob_b"]).hash),
    ("gap_hash_encodes_step_citation", lambda: make_gap("g", step_refs=["step_a"]).hash != make_gap("g", step_refs=["step_b"]).hash),
    ("co_occurrence_counts_reference_usage", lambda: seed_trajectory("blob_a", count=2).co_occurrence("blob_a") == 2),
    ("resolve_entity_falls_back_to_trajectory", lambda: (lambda traj, step: "step:" in loop._resolve_entity([step.hash], registry(), traj))( *(lambda t, s: (t.append(s), (t, s))[1])(Trajectory(), make_step("fallback")) )),
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
        resolve_entity=lambda content_refs, registry_obj, trajectory: None,
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
    assert len(outcome.step_result.gaps) == 1
    assert outcome.step_result.gaps[0].vocab == "reason_needed"
    assert "Diagnose rogue step" in outcome.step_result.gaps[0].desc


P7_CASES = [
    ("admin_steps_all_deterministic", lambda: all(not s.post_diff for s in skill("admin").steps)),
    ("hash_edit_has_one_flexible_step", lambda: len(skill("hash_edit").flexible_steps()) == 1),
    ("hash_edit_has_flexible_steps_again", lambda: any(s.post_diff for s in skill("hash_edit").steps)),
    ("hash_edit_has_deterministic_steps_again", lambda: any(not s.post_diff for s in skill("hash_edit").steps)),
    ("reason_first_step_deterministic", lambda: skill("reason").steps[0].post_diff is False),
    ("reason_later_steps_flexible", lambda: all(s.post_diff for s in skill("reason").steps[1:])),
    ("await_first_two_deterministic", lambda: all(not s.post_diff for s in skill("await").steps[:2])),
    ("await_last_step_flexible", lambda: skill("await").steps[-1].post_diff is True),
    ("commit_first_step_deterministic", lambda: skill("commit").steps[0].post_diff is False),
    ("commit_later_steps_flexible", lambda: all(s.post_diff for s in skill("commit").steps[1:])),
    ("reprogramme_steps_all_terminal", lambda: all(not s.post_diff for s in skill("reprogramme").steps)),
    ("builder_observe_maps_to_post_diff_true", lambda: st_builder_module.build_st({"name": "x", "desc": "d", "actions": [{"do": "inspect file", "observe": True}]})["steps"][0]["post_diff"] is True),
    ("builder_mutate_maps_to_post_diff_false", lambda: st_builder_module.build_st({"name": "x", "desc": "d", "actions": [{"do": "edit file", "mutate": True}]})["steps"][0]["post_diff"] is False),
    ("action_update_requires_existing_ref", lambda: any("requires 'existing_ref'" in e for e in st_builder_module.validate_st({"name": "x", "desc": "d", "steps": []}, artifact_kind="action_update"))),
    ("render_for_prompt_marks_admin_deterministic", lambda: "(deterministic)" in registry().render_for_prompt()),
    ("render_for_prompt_marks_mixed_skill", lambda: "hash_edit" in registry().render_for_prompt() and "(mixed)" in registry().render_for_prompt()),
    ("extract_st_steps_blob_is_terminal", lambda: chain_to_st_module.extract_st_steps({"resolved_steps": [{"desc": "observe target", "content_refs": ["blob_a"], "gaps": []}]})[0]["post_diff"] is False),
    ("extract_st_steps_gap_branch_is_flexible", lambda: chain_to_st_module.extract_st_steps({"resolved_steps": [{"desc": "branch", "gaps": [{"content_refs": ["blob_a"], "step_refs": ["step_a"], "scores": {"relevance": 0.8}, "vocab": "pattern_needed"}]}]})[0]["post_diff"] is True),
    ("extract_st_steps_commit_implies_post_diff", lambda: chain_to_st_module.extract_st_steps({"resolved_steps": [{"desc": "mutate", "commit": "abc", "gaps": [{"content_refs": [], "step_refs": [], "scores": {"relevance": 0.8}, "vocab": "content_needed"}]}]})[0]["post_diff"] is True),
    ("admin_deterministic_steps_helper", lambda: all(not s.post_diff for s in skill("admin").steps)),
    ("hash_edit_flexible_steps_helper", lambda: len(skill("hash_edit").flexible_steps()) == 1),
]


P8_CASES = [
    ("omo_allows_first_mutation", lambda: Compiler(Trajectory()).validate_omo("content_needed")),
    ("omo_blocks_consecutive_mutation", lambda: (lambda comp: (comp.record_execution("content_needed", True), comp.validate_omo("content_needed"))[1] is False)(Compiler(Trajectory()))),
    ("omo_allows_observation_after_mutation", lambda: (lambda comp: (comp.record_execution("content_needed", True), comp.validate_omo("pattern_needed"))[1])(Compiler(Trajectory()))),
    ("postcondition_needed_after_mutation", lambda: (lambda comp: (comp.record_execution("content_needed", True), comp.needs_postcondition())[1])(Compiler(Trajectory()))),
    ("postcondition_clears_after_observation", lambda: (lambda comp: (comp.record_execution("content_needed", True), comp.record_execution("pattern_needed", False), comp.needs_postcondition())[2] is False)(Compiler(Trajectory()))),
    ("govern_acts_on_grounded_mutation", lambda: govern(LedgerEntry(make_gap("g", vocab="content_needed", confidence=0.7, grounded=0.6), "c"), 1, GovernorState()) == GovernorSignal.ACT),
    ("govern_allows_weak_mutation", lambda: govern(LedgerEntry(make_gap("g", vocab="content_needed", confidence=0.2, grounded=0.1), "c"), 1, GovernorState()) == GovernorSignal.ALLOW),
    ("govern_reverts_on_divergence", lambda: (lambda state: (state.record(Epistemic(0.5, 0.8, 0.5)), state.record(Epistemic(0.5, 0.5, 0.5)), govern(LedgerEntry(make_gap("g"), "c"), 1, state))[2] == GovernorSignal.REVERT)(GovernorState())),
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


P9_CASES = [
    ("chain_starts_at_length_one", lambda: Chain.create("gap", "step").length() == 1),
    ("chain_add_step_increments_length", lambda: (lambda c: (c.add_step("step2"), c.length())[1] == 2)(Chain.create("gap", "step1"))),
    ("chain_roundtrip_preserves_hash", lambda: Chain.from_dict(Chain.create("gap", "step").to_dict()).hash == Chain.create("gap", "step").hash),
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


P10_CASES = [
    ("reason_trigger", lambda: skill("reason").trigger == "on_vocab:reason_needed"),
    ("reason_step1_observe", lambda: skill("reason").steps[0].vocab == "hash_resolve_needed"),
    ("reason_step2_flexible", lambda: skill("reason").steps[1].post_diff is True),
    ("reason_relevance_descends", lambda: [s["relevance"] for s in skill_data("reason")["steps"]] == [1.0, 0.9, 0.8, 0.7]),
    ("await_trigger", lambda: skill("await").trigger == "on_vocab:await_needed"),
    ("await_wait_step_observe", lambda: skill("await").steps[0].vocab == "hash_resolve_needed"),
    ("await_last_step_flexible", lambda: skill("await").steps[-1].post_diff is True),
    ("commit_trigger", lambda: skill("commit").trigger == "on_vocab:commit_needed"),
    ("commit_first_step_observe", lambda: skill("commit").steps[0].vocab == "hash_resolve_needed"),
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
    ("reason_steps_count", lambda: skill("reason").step_count() == 4),
    ("await_steps_count", lambda: skill("await").step_count() == 3),
    ("commit_steps_count", lambda: skill("commit").step_count() == 3),
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
    ("deep_render_has_absolute_time", lambda: (lambda ctx: bool(re.search(r"\(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\)", loop._render_step_tree(ctx.step2, ctx.traj))))(build_chain_context())),
    ("step_timestamps_increase_over_time", lambda: (lambda s1, s2: s2.t >= s1.t)(make_step("a"), make_step("b"))),
    ("recent_returns_last_step_time", lambda: (lambda ctx: ctx.traj.recent(1)[0].t == ctx.step2.t)(build_chain_context())),
    ("render_recent_preserves_step_order", lambda: (lambda ctx: (lambda rendered: rendered.find(ctx.step1.hash) < rendered.find(ctx.step2.hash))(ctx.traj.render_recent(5, registry())))(build_chain_context())),
    ("relative_time_zero_or_negative_empty", lambda: relative_time(0) == ""),
    ("absolute_time_zero_or_negative_empty", lambda: absolute_time(0) == ""),
]


P12_CASES = [
    ("parse_step_output_extracts_gap", lambda: (lambda old: (setattr(loop, "_turn_counter", 7), loop._parse_step_output('Saw issue\\n{\"gaps\":[{\"desc\":\"need context\",\"content_refs\":[\"blob_a\"],\"step_refs\":[\"step_a\"],\"vocab\":\"pattern_needed\",\"relevance\":0.8,\"confidence\":0.6}]}', ["step_root"], ["blob_root"])[0:2], setattr(loop, "_turn_counter", old))[1][1][0].desc == "need context")(loop._turn_counter)),
    ("parse_step_output_sets_turn_id", lambda: (lambda old: (setattr(loop, "_turn_counter", 9), loop._parse_step_output('x {\"gaps\":[{\"desc\":\"g\"}]}', [], [])[1][0].turn_id, setattr(loop, "_turn_counter", old))[1] == 9)(loop._turn_counter)),
    ("parse_step_output_zeros_grounded", lambda: loop._parse_step_output('x {"gaps":[{"desc":"g","grounded":1.0}]}', [], [])[1][0].scores.grounded == 0.0),
    ("parse_step_output_uses_prefix_desc", lambda: loop._parse_step_output('observed issue {"gaps":[]}', [], [])[0].desc == "observed issue"),
    ("extract_json_parses_block", lambda: loop._extract_json('text {"a": 1}') == {"a": 1}),
    ("extract_json_invalid_returns_none", lambda: loop._extract_json("not json") is None),
    ("extract_command_reads_command_field", lambda: loop._extract_command('{"command": "echo hi"}') == "echo hi"),
    ("extract_command_missing_returns_none", lambda: loop._extract_command('{"reasoning": "x"}') is None),
    ("resolve_all_refs_formats_blocks", lambda: (lambda ctx: "resolved step" in loop.resolve_all_refs([ctx.step1.hash], [], ctx.traj))(build_chain_context())),
    ("load_tree_policy_contains_action_entity_prefixes", lambda: "skills/actions/" in loop._load_tree_policy() and "skills/entities/" in loop._load_tree_policy()),
    ("match_policy_exact_path", lambda: loop._match_policy("loop.py", loop._load_tree_policy())["immutable"] is True),
    ("match_policy_prefix_path", lambda: loop._match_policy("skills/admin.st", loop._load_tree_policy())["on_mutate"] == "reprogramme_needed"),
    ("match_policy_longest_prefix", lambda: loop._match_policy("skills/codons/await.st", loop._load_tree_policy())["on_reject"] == "reason_needed"),
    ("chain_spec_in_codon_tree_still_resolves_as_entity_source", lambda: loop._is_entity_source("skills/codons/commitment_chain_construction_spec.st")),
    ("execute_tool_missing_file_nonzero", lambda: loop.execute_tool("tools/does_not_exist.py", {})[1] == 1),
    ("find_identity_skill_admin", lambda: loop._find_identity_skill("discord:784778107013431296", registry()) == skill("admin")),
    ("render_identity_has_username", lambda: "username:" in loop._render_identity(skill("admin"))),
    ("render_identity_has_communication_pref", lambda: "communication:" in loop._render_identity(skill("admin"))),
    ("validate_st_accepts_command_trigger", lambda: st_builder_module.validate_st({"name": "cmd", "desc": "d", "trigger": "command:demo", "steps": []}) == []),
    ("load_skill_detects_command_flag", lambda: (lambda path: load_skill(str(path)).is_command)(
        (lambda p: (p.write_text(json.dumps({"name": "cmd", "desc": "d", "trigger": "command:test", "steps": []})), p)[1])(Path(ROOT / "tests" / "_tmp_command.st"))
    )),
    ("resolve_hash_unknown_returns_none", lambda: loop.resolve_hash("missing_hash", Trajectory()) is None),
]


P13_CASES = [
    ("max_chain_depth_constant", lambda: MAX_CHAIN_DEPTH == 15),
    ("chain_extract_length_constant", lambda: CHAIN_EXTRACT_LENGTH == 8),
    ("ledger_entry_depth_defaults_zero", lambda: LedgerEntry(make_gap("g"), "c").depth == 0),
    ("push_child_sets_depth", lambda: (lambda ledger: (ledger.push_child(make_gap("g"), "c", "p", 3), ledger.peek().depth == 3)[1])(Ledger())),
    ("reason_relevance_descending", lambda: (lambda vals: vals == sorted(vals, reverse=True))([s["relevance"] for s in skill_data("reason")["steps"]])),
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
    ("extract_st_steps_preserves_content_refs", lambda: chain_to_st_module.extract_st_steps({"resolved_steps": [{"desc": "observe target", "gaps": [{"content_refs": ["entity_hash"], "step_refs": [], "scores": {"relevance": 0.9}, "vocab": "hash_resolve_needed"}]}]})[0]["content_refs"] == ["entity_hash"]),
    ("extract_st_steps_derives_relevance_when_missing", lambda: chain_to_st_module.extract_st_steps({"resolved_steps": [{"desc": "observe", "gaps": [{}]}]})[0]["relevance"] == 1.0),
    ("extract_st_steps_slugifies_action", lambda: chain_to_st_module.extract_st_steps({"resolved_steps": [{"desc": "Observe target file", "gaps": []}]})[0]["action"] == "observe_target_file"),
    ("compose_over_construction_keeps_codon_steps_short", lambda: all(skill(name).step_count() <= 4 for name in ("reason", "await", "commit", "reprogramme"))),
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


def test_p10_chain_to_st_roundtrip_writes_file(tmp_path, monkeypatch):
    chain_doc, _step_doc = serialized_chain_files(tmp_path)
    monkeypatch.setattr(chain_to_st_module, "CORS_ROOT", tmp_path)
    monkeypatch.setattr(chain_to_st_module, "TRAJ_FILE", tmp_path / "trajectory.json")
    monkeypatch.setattr(chain_to_st_module, "CHAINS_FILE", tmp_path / "chains.json")

    output_path = tmp_path / "skills" / "curated.st"
    result = chain_to_st_module.chain_to_st(
        chain_hash=chain_doc["hash"],
        name="curated",
        desc="curated workflow",
        refs={"admin": "admin_hash"},
        output_path=str(output_path),
    )

    assert result["status"] == "ok"
    assert result["st"]["source_chain"] == chain_doc["hash"]
    assert result["st"]["refs"] == {"admin": "admin_hash"}
    assert output_path.exists()


def test_p12_auto_commit_contract_clean_tree(monkeypatch):
    monkeypatch.setattr(loop, "git", lambda cmd, cwd=None: "")
    assert loop.auto_commit("noop") == (None, None)


def test_p12_auto_commit_contract_success(monkeypatch):
    responses = {
        ("status", "--porcelain"): " M loop.py",
        ("rev-parse", "--short", "HEAD"): "abc123",
        ("add", "-A"): "",
        ("commit", "-m", "ok"): "",
        ("diff", "--numstat", "abc123", "abc123"): "5\t4\tloop.py",
    }

    def fake_git(cmd, cwd=None):
        return responses.get(tuple(cmd), "")

    monkeypatch.setattr(loop, "git", fake_git)
    monkeypatch.setattr(loop, "git_head", lambda: "abc123")
    monkeypatch.setattr(loop, "_check_protected", lambda post, pre: ([], None))

    assert loop.auto_commit("ok") == ("abc123", None)


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
    monkeypatch.setattr(loop, "_check_protected", lambda post, pre: (["skills/codons/reason.st"], "reason_needed"))

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
        resolve_entity=lambda content_refs, registry_obj, trajectory: None,
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
        resolve_all_refs=lambda step_refs, content_refs, trajectory: "",
        execute_tool=lambda tool, params: ("", 0),
        auto_commit=lambda message, paths=None: (None, None),
        parse_step_output=lambda raw, step_refs, content_refs, chain_id=None: (make_step("noop"), []),
        extract_json=lambda raw: None,
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


def test_p12_action_tree_reprogramme_mode_preserves_flow_fields():
    frame = {
        "version": "semantic_skeleton.v1",
        "artifact": {"kind": "hybrid", "protected_kind": "action"},
        "name": "workflow",
        "root": "phase_root",
        "phases": [{"id": "phase_root"}],
        "closure": {"success": {}},
    }

    preserved = execution_engine_module._coerce_semantic_frame_for_mode(frame, "action_editor")

    assert preserved is not None
    assert preserved["artifact"]["kind"] == "hybrid"
    assert preserved["artifact"]["protected_kind"] == "action"
    assert preserved["root"] == "phase_root"
    assert preserved["phases"] == [{"id": "phase_root"}]
    assert preserved["closure"] == {"success": {}}


def test_p12_new_action_origination_requires_reason():
    gap = make_gap("build research workflow", vocab="reprogramme_needed")
    gap.route_mode = "action_editor"
    assert execution_engine_module._new_action_origination_requires_reason(
        gap,
        route_mode="action_editor",
        target_entity=None,
    ) is True


def test_p12_existing_action_update_does_not_require_reason():
    gap = make_gap("update hash_edit", vocab="reprogramme_needed")
    gap.route_mode = "action_editor"
    assert execution_engine_module._new_action_origination_requires_reason(
        gap,
        route_mode="action_editor",
        target_entity=skill("hash_edit"),
    ) is False


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
    assert "## Entity: admin:" in rendered


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
