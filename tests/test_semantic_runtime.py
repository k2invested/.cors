import sys
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loop
import manifest_engine as me
from compile import Compiler
from step import Gap, Step, Trajectory
from skills.loader import Skill, SkillStep, load_all, load_skill


def registry():
    return load_all(str(ROOT / "skills"))


def test_entity_skill_detection_distinguishes_entity_from_action_and_codon():
    reg = registry()
    admin = reg.resolve_by_name("admin")
    hash_edit = reg.resolve_by_name("hash_edit")
    trigger = reg.resolve_by_name("trigger")

    assert admin is not None and loop._is_entity_skill(admin) is True
    assert hash_edit is not None and loop._is_entity_skill(hash_edit) is False
    assert trigger is not None and loop._is_entity_skill(trigger) is False


def test_resolve_hash_injects_entity_but_reads_action_package():
    reg = registry()
    loop._skill_registry = reg
    traj = Trajectory()

    admin = reg.resolve_by_name("admin")
    hash_edit = reg.resolve_by_name("hash_edit")

    assert admin is not None
    assert hash_edit is not None

    admin_rendered = loop.resolve_hash(admin.hash, traj)
    action_rendered = loop.resolve_hash(hash_edit.hash, traj)

    assert admin_rendered is not None and admin_rendered.startswith("semantic_tree:skill_package:")
    assert "package: name=admin" in admin_rendered
    assert action_rendered is not None and action_rendered.startswith("semantic_tree:skill_package:")
    assert "trigger: on_vocab:hash_edit_needed" in action_rendered
    assert "package: name=hash_edit" in action_rendered


def test_render_entity_tree_shows_entity_space():
    reg = registry()
    tree = loop._render_entity_tree(reg)
    assert tree.startswith("entity_tree")
    assert "admin:" in tree
    assert "admin.st" in tree
    assert "clinton.st" in tree


def test_render_step_network_shows_entities_packages_and_commands(tmp_path):
    reg = registry()
    package_hash = me.persist_chain_package(tmp_path, example_stepchain())
    network = me.render_step_network(tmp_path, reg, loop._is_entity_skill, loop._skill_payload)

    assert network.startswith("step_network")
    assert "entities" in network
    assert "executable_packages" in network
    assert "compiled_stepchains" in network
    assert "commands" in network
    assert "admin.st" in network
    assert "trigger.st" in network
    assert package_hash in network


def test_render_step_network_ignores_aggregate_background_json(tmp_path):
    reg = registry()
    package_hash = me.persist_chain_package(tmp_path, example_stepchain())
    (tmp_path / "background_run.chains.json").write_text(json.dumps([{"hash": "abc123"}]))
    (tmp_path / "background_run.trajectory.json").write_text(json.dumps([{"desc": "step"}]))

    network = me.render_step_network(tmp_path, reg, loop._is_entity_skill, loop._skill_payload)

    assert network.startswith("step_network")
    assert package_hash in network
    assert "background_run.chains" not in network
    assert "background_run.trajectory" not in network


def example_stepchain() -> dict:
    return {
        "version": "stepchain.v1",
        "name": "review_flow",
        "desc": "review and verify",
        "trigger": "manual",
        "refs": {"target": "blob:abc123"},
        "root": "phase_reason",
        "phase_order": ["phase_reason", "phase_verify", "phase_done"],
        "nodes": [
            {
                "id": "phase_reason",
                "kind": "reason",
                "goal": "assess",
                "action": "assess_and_route",
                "manifestation": {
                    "kernel_class": "bridge",
                    "dispersal": "mixed",
                    "execution_mode": "curated_step_hash",
                    "activation_ref": "flow:123",
                },
                "generation": {
                    "spawn_mode": "mixed",
                    "spawn_trigger": "conditional",
                    "branch_policy": "depth_first_to_parent",
                    "sibling_policy": "after_descendants",
                    "return_policy": "resume_transition",
                },
                "allowed_vocab": ["reason_needed", "hash_edit_needed"],
                "post_diff": True,
                "gap_template": {
                    "desc": "target must be assessed",
                    "content_refs": ["blob:abc123"],
                    "step_refs": [],
                },
                "activation_key": "flow:123",
                "transitions": {"on_close": "phase_verify"},
            },
            {
                "id": "phase_verify",
                "kind": "verify",
                "goal": "verify",
                "action": "verify_result",
                "manifestation": {
                    "kernel_class": "observe",
                    "dispersal": "mixed",
                    "execution_mode": "runtime_vocab",
                    "runtime_vocab": "hash_resolve_needed",
                },
                "generation": {
                    "spawn_mode": "mixed",
                    "spawn_trigger": "on_post_diff",
                    "branch_policy": "depth_first_to_parent",
                    "sibling_policy": "after_descendants",
                    "return_policy": "resume_transition",
                },
                "allowed_vocab": ["hash_resolve_needed"],
                "post_diff": True,
                "gap_template": {
                    "desc": "result must be observed",
                    "content_refs": ["$commit"],
                    "step_refs": ["$prev"],
                },
                "activation_key": "hash_resolve_needed",
                "transitions": {"on_close": "phase_done"},
            },
            {
                "id": "phase_done",
                "kind": "terminal",
                "goal": "done",
                "action": "close_loop",
                "terminal": True,
            },
        ],
        "closure": {
            "success": {
                "requires_terminal": "phase_done",
                "requires_no_active_gaps": True,
            },
            "failure": {
                "allow_force_close": True,
                "allow_clarify_terminal": True,
            },
            "limits": {
                "max_chain_depth": 8,
                "max_redirects": 2,
            },
        },
    }


def test_chain_package_persist_load_and_render(tmp_path, monkeypatch):
    package = example_stepchain()
    package_hash = me.persist_chain_package(tmp_path, package)
    loaded = me.load_chain_package(tmp_path, package_hash)
    rendered = me.render_chain_package(loaded, package_hash)

    assert loaded["version"] == "stepchain.v1"
    assert package_hash == me.stable_doc_hash(package)
    assert rendered.startswith(f"semantic_tree:stepchain:{package_hash}")
    assert "phase_reason" in rendered
    assert "{bx+h/0:1}" in rendered
    assert "{vx+v/1:1}" in rendered


def test_activate_stepchain_package_creates_runtime_gaps():
    package = example_stepchain()
    origin_step = Step.create(desc="origin")
    gap = Gap.create(desc="activate flow", content_refs=["blob:seed"])
    step = me.activate_stepchain_package(package, "pkg123", gap, origin_step, "chain123", 1)

    assert step.content_refs[0] == "pkg123"
    assert len(step.gaps) == 2
    assert step.gaps[0].desc == "target must be assessed"
    assert step.gaps[0].vocab == "reason_needed"
    assert "flow:123" in step.gaps[0].content_refs
    assert step.gaps[1].vocab == "hash_resolve_needed"


def test_activate_stepchain_package_named_default_embedding_uses_foundation_default_gap():
    reg = registry()
    package = {
        "version": "stepchain.v1",
        "name": "embedded_hash_edit",
        "desc": "embed hash edit",
        "trigger": "manual",
        "refs": {"hash_edit_block": reg.resolve_by_name("hash_edit").hash},
        "root": "phase_embed",
        "phase_order": ["phase_embed", "phase_done"],
        "nodes": [
            {
                "id": "phase_embed",
                "kind": "higher_order",
                "goal": "embed hash edit",
                "action": "embed_hash_edit",
                "manifestation": {
                    "kernel_class": "bridge",
                    "dispersal": "mixed",
                    "execution_mode": "inline",
                },
                "generation": {
                    "spawn_mode": "none",
                    "spawn_trigger": "none",
                    "branch_policy": "depth_first_to_parent",
                    "sibling_policy": "after_descendants",
                    "return_policy": "resume_transition",
                },
                "allowed_vocab": [],
                "post_diff": False,
                "gap_template": {
                    "desc": "embed hash edit foundation",
                    "content_refs": [],
                    "step_refs": [],
                },
                "embedding": {
                    "block_ref": "@hash_edit_block",
                    "activation_mode": "named_default",
                },
                "transitions": {"on_close": "phase_done"},
            },
            {
                "id": "phase_done",
                "kind": "terminal",
                "goal": "done",
                "action": "close_loop",
                "terminal": True,
            },
        ],
        "closure": {
            "success": {"requires_terminal": "phase_done", "requires_no_active_gaps": True}
        },
    }
    origin_step = Step.create(desc="origin")
    gap = Gap.create(desc="activate embedded flow", content_refs=["blob:seed"])

    step = me.activate_stepchain_package(
        package,
        "pkg123",
        gap,
        origin_step,
        "chain123",
        1,
        registry=reg,
    )

    assert len(step.gaps) == 1
    assert step.gaps[0].vocab == "hash_edit_needed"
    assert reg.resolve_by_name("hash_edit").hash in step.gaps[0].content_refs


def test_activate_skill_package_single_step_can_inherit_foundation_default_gap():
    reg = registry()
    synthetic = Skill(
        hash="abc123skill0",
        name="synthetic_review",
        desc="one-step synthetic review action",
        steps=[SkillStep(action="activate", desc="activate review block", vocab=None, post_diff=False)],
        source=str(ROOT / "skills" / "actions" / "synthetic_review.st"),
        trigger="on_vocab:hash_edit_needed",
        artifact_kind="action",
    )
    reg.register(synthetic)

    origin_step = Step.create(desc="origin")
    gap = Gap.create(desc="activate synthetic", content_refs=[synthetic.hash])
    step = me.activate_skill_package(
        synthetic,
        synthetic.hash,
        gap,
        origin_step,
        "chain123",
        1,
        registry=reg,
    )

    assert len(step.gaps) == 1
    assert step.gaps[0].vocab == "hash_edit_needed"
    assert synthetic.hash in step.gaps[0].content_refs


def test_activate_skill_package_preserves_explicit_step_vocab_over_foundation_default():
    reg = registry()
    hash_edit = reg.resolve_by_name("hash_edit")
    assert hash_edit is not None

    origin_step = Step.create(desc="origin")
    gap = Gap.create(desc="activate hash edit", content_refs=[hash_edit.hash])
    step = me.activate_skill_package(
        hash_edit,
        hash_edit.hash,
        gap,
        origin_step,
        "chain123",
        1,
        registry=reg,
    )

    assert [g.vocab for g in step.gaps] == ["hash_resolve_needed", None, "hash_edit_needed"]


def test_resolve_hash_renders_persisted_stepchain_package(tmp_path, monkeypatch):
    monkeypatch.setattr(loop, "CHAINS_DIR", tmp_path)
    traj = Trajectory()
    package_hash = me.persist_chain_package(tmp_path, example_stepchain())
    rendered = loop.resolve_hash(package_hash, traj)
    assert rendered is not None
    assert rendered.startswith(f"semantic_tree:stepchain:{package_hash}")


def test_background_trigger_refs_round_trip():
    compiler = Compiler(Trajectory())
    compiler.record_background_trigger("chain_a", refs=["abc123", "def456"])
    compiler.record_background_trigger("chain_b", refs=["abc123"])
    assert compiler.needs_heartbeat() is True
    assert compiler.background_refs() == ["abc123", "def456"]


def test_loader_preserves_rich_step_manifestation_fields(tmp_path):
    path = tmp_path / "rich_entity.st"
    path.write_text(json.dumps({
        "name": "rich_entity",
        "desc": "entity with rich structure",
        "trigger": "manual",
        "refs": {"admin": "72b1d5ffc964"},
        "identity": {"name": "Ada"},
        "steps": [
            {
                "action": "load_context",
                "desc": "load context",
                "vocab": "hash_resolve_needed",
                "relevance": 0.95,
                "post_diff": False,
                "resolve": ["admin"],
                "condition": {"if": "known"},
                "inject": {"system": "use this context"},
                "content_refs": ["blob:abc123"],
                "step_refs": ["$prev"],
                "manifestation": {"kernel_class": "observe"},
                "generation": {"spawn_mode": "none"},
                "transitions": {"on_done": "next"},
                "custom_field": "preserved"
            }
        ]
    }, indent=2))

    skill = load_skill(str(path))
    assert skill is not None
    assert skill.artifact_kind == "hybrid"
    assert skill.refs == {"admin": "72b1d5ffc964"}
    assert "identity" in skill.semantics
    assert skill.payload["name"] == "rich_entity"

    step = skill.steps[0]
    assert step.relevance == 0.95
    assert step.resolve == ["admin"]
    assert step.condition == {"if": "known"}
    assert step.inject == {"system": "use this context"}
    assert step.content_refs == ["blob:abc123"]
    assert step.step_refs == ["$prev"]
    assert step.manifestation == {"kernel_class": "observe"}
    assert step.generation == {"spawn_mode": "none"}
    assert step.transitions == {"on_done": "next"}
    assert step.extra["custom_field"] == "preserved"


def test_loader_resolves_command_hashes_through_main_registry():
    reg = registry()
    command = reg.resolve_command("architect")
    assert command is not None
    assert reg.resolve(command.hash) == command


def test_render_active_chain_highlights_current_gap():
    traj = Trajectory()
    origin_gap = Gap.create(desc="review target", content_refs=["blob:abc123"])
    origin_gap.vocab = "reason_needed"

    origin_step = Step.create(desc="origin", gaps=[origin_gap])
    traj.append(origin_step)
    chain = traj.find_chain(origin_gap.hash)
    if chain is None:
        from step import Chain
        chain = Chain.create(origin_gap=origin_gap.hash, first_step=origin_step.hash)
        traj.add_chain(chain)

    work_gap = Gap.create(desc="apply review", content_refs=["blob:abc123"])
    work_gap.vocab = "hash_edit_needed"
    work_step = Step.create(desc="reason activated", step_refs=[origin_step.hash], gaps=[work_gap])
    traj.append(work_step)
    old_hash = chain.hash
    chain.add_step(work_step.hash)
    del traj.chains[old_hash]
    traj.chains[chain.hash] = chain

    rendered = traj.render_chain(chain.hash, highlight_gap=work_gap.hash)
    assert rendered.startswith(f"chain:{chain.hash}")
    assert "apply review" in rendered
    assert f"gap:{work_gap.hash}" in rendered
    assert "[focus]" in rendered


def test_render_active_chain_includes_compact_tree_signatures():
    traj = Trajectory()
    origin_gap = Gap.create(desc="review target", content_refs=["blob:abc123"])
    origin_gap.vocab = "reason_needed"
    origin_gap.scores.relevance = 0.9
    origin_gap.scores.confidence = 0.8
    origin_gap.scores.grounded = 0.2

    origin_step = Step.create(desc="origin", gaps=[origin_gap])
    traj.append(origin_step)
    rendered = traj.render_recent(5)

    assert "{o+1}" in rendered
    assert "{?b872/0:1}" in rendered


def test_render_chain_collapsed_mode_summarizes_history():
    traj = Trajectory()
    origin_gap = Gap.create(desc="review target", content_refs=["blob:abc123"])
    origin_gap.vocab = "reason_needed"
    origin_step = Step.create(desc="origin", gaps=[origin_gap])
    traj.append(origin_step)
    from step import Chain
    chain = Chain.create(origin_gap=origin_gap.hash, first_step=origin_step.hash)
    traj.add_chain(chain)

    prev = origin_step
    old_hash = chain.hash
    for idx in range(1, 7):
        gap = Gap.create(desc=f"close branch {idx}: inspect shard {idx}", content_refs=[f"blob:{idx}"], step_refs=[prev.hash])
        gap.vocab = "hash_resolve_needed"
        if idx < 6:
            gap.resolved = True
        step = Step.create(desc=f"inspect shard {idx}", step_refs=[prev.hash], gaps=[gap])
        traj.append(step)
        chain.add_step(step.hash)
        prev = step
    del traj.chains[old_hash]
    traj.chains[chain.hash] = chain

    rendered = traj.render_chain(chain.hash, mode="collapsed")
    assert "history:" in rendered
    assert "earlier resolved step(s) collapsed" in rendered


def test_render_chain_keeps_refs_on_resolved_gap_lines():
    traj = Trajectory()
    origin_gap = Gap.create(desc="review target", content_refs=["blob:abc123"], step_refs=["seed123"])
    origin_gap.vocab = "reason_needed"
    origin_gap.resolved = True
    origin_step = Step.create(desc="review target", gaps=[origin_gap])
    traj.append(origin_step)
    from step import Chain
    chain = Chain.create(origin_gap=origin_gap.hash, first_step=origin_step.hash)
    traj.add_chain(chain)

    rendered = traj.render_chain(chain.hash)
    assert f"gap:{origin_gap.hash}" in rendered
    assert "step:seed123" in rendered
    assert "blob:abc123" in rendered


def test_render_chain_shows_compact_effective_contract_tags_for_foundation_backed_gap():
    reg = registry()
    hash_edit = reg.resolve_by_name("hash_edit")
    assert hash_edit is not None

    traj = Trajectory()
    origin_gap = Gap.create(desc="review target", content_refs=[hash_edit.hash])
    origin_gap.vocab = "reason_needed"
    origin_step = Step.create(desc="origin", gaps=[origin_gap])
    traj.append(origin_step)

    from step import Chain
    chain = Chain.create(origin_gap=origin_gap.hash, first_step=origin_step.hash)
    traj.add_chain(chain)

    work_gap = Gap.create(desc="activate hash edit", content_refs=[hash_edit.hash])
    work_gap.vocab = "hash_edit_needed"
    work_step = Step.create(desc="activate foundation", step_refs=[origin_step.hash], gaps=[work_gap])
    traj.append(work_step)
    old_hash = chain.hash
    chain.add_step(work_step.hash)
    del traj.chains[old_hash]
    traj.chains[chain.hash] = chain

    rendered = traj.render_chain(chain.hash, registry=reg)
    assert "gap=hash_edit_needed" in rendered
    assert "embed=named_default" in rendered


def test_render_chain_marks_unresolved_sibling_gap_as_pending():
    traj = Trajectory()
    resolved_gap = Gap.create(desc="resolved branch", content_refs=["blob:resolved"])
    resolved_gap.vocab = "hash_resolve_needed"
    resolved_gap.resolved = True
    pending_gap = Gap.create(desc="pending branch", content_refs=["blob:pending"])
    pending_gap.vocab = "hash_edit_needed"

    origin_step = Step.create(desc="origin", gaps=[resolved_gap, pending_gap])
    traj.append(origin_step)
    from step import Chain
    chain = Chain.create(origin_gap=resolved_gap.hash, first_step=origin_step.hash)
    traj.add_chain(chain)

    rendered = traj.render_chain(chain.hash)
    assert f"gap:{pending_gap.hash}" in rendered
    assert "(pending)" in rendered


def test_render_chain_marks_gap_open_and_shows_child_chain():
    traj = Trajectory()
    parent_gap = Gap.create(desc="spawn child review", content_refs=["blob:parent"])
    parent_gap.vocab = "reason_needed"
    parent_step = Step.create(desc="parent origin", gaps=[parent_gap])
    traj.append(parent_step)

    from step import Chain
    parent_chain = Chain.create(origin_gap=parent_gap.hash, first_step=parent_step.hash)
    traj.add_chain(parent_chain)

    child_origin_step = Step.create(desc="child activated")
    traj.append(child_origin_step)
    child_chain = Chain.create(origin_gap=parent_gap.hash, first_step=child_origin_step.hash)
    child_chain.desc = "child review in progress"
    traj.add_chain(child_chain)

    rendered = traj.render_chain(parent_chain.hash)
    assert f"gap:{parent_gap.hash}" in rendered
    assert "(open, child chain active)" in rendered
    assert f'chain:{child_chain.hash}  "child review in progress" (active, 1 steps)' in rendered


def test_render_chain_appends_remote_frontier_footer_for_other_unresolved_chains():
    traj = Trajectory()

    current_gap = Gap.create(desc="current branch", content_refs=["blob:current"])
    current_gap.vocab = "hash_resolve_needed"
    current_step = Step.create(desc="current origin", gaps=[current_gap])
    traj.append(current_step)

    from step import Chain
    current_chain = Chain.create(origin_gap=current_gap.hash, first_step=current_step.hash)
    traj.add_chain(current_chain)

    remote_gap = Gap.create(desc="remote branch", content_refs=["blob:remote"])
    remote_gap.vocab = "hash_edit_needed"
    remote_step = Step.create(desc="remote origin", gaps=[remote_gap])
    traj.append(remote_step)
    remote_chain = Chain.create(origin_gap=remote_gap.hash, first_step=remote_step.hash)
    traj.add_chain(remote_chain)

    rendered = traj.render_chain(current_chain.hash)
    assert "\n  frontier\n" in rendered
    assert f'gap:{remote_gap.hash} "remote branch"' in rendered
    assert f"via chain:{remote_chain.hash}" in rendered


def test_render_gap_tree_includes_signature_and_ref_counts():
    traj = Trajectory()
    gap = Gap.create(desc="inspect config", content_refs=["blob:abc123"], step_refs=["prev123"])
    gap.vocab = "hash_resolve_needed"
    gap.scores.relevance = 0.8
    gap.scores.confidence = 0.6
    gap.scores.grounded = 0.4

    rendered = loop._render_gap_tree(gap, traj)
    assert "{?o754/1:1}" in rendered
    assert "content_refs[1]" in rendered
    assert "step_refs[1]" in rendered


def test_build_runtime_semantic_tree_attaches_effective_contract_for_foundation_gap():
    reg = registry()
    hash_edit = reg.resolve_by_name("hash_edit")
    assert hash_edit is not None

    step = Step.create(
        desc="activate foundation",
        content_refs=[hash_edit.hash],
        gaps=[Gap.create(desc="activate hash edit", content_refs=[hash_edit.hash])],
    )
    step.gaps[0].vocab = "hash_edit_needed"

    tree = me.build_runtime_semantic_tree(
        [step.to_dict()],
        source_type="trajectory_recent",
        source_ref="recent",
        registry=reg,
    )

    node = tree["nodes"][0]
    assert node["effective_contract"]["ref"] == hash_edit.hash
    assert node["effective_contract"]["default_gap"] == "hash_edit_needed"
    assert node["effective_contract"]["effective_gap"] == "hash_edit_needed"
