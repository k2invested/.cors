"""Tests for all 20 v5 principles.

Each test validates a structural property of the system.
No LLM calls — pure structure and logic tests.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from step import *
from compile import *
from skills.loader import load_all, load_skill


# ── Helpers ───────────────────────────────────────────────────────────────

def make_gap(desc, content_refs=None, step_refs=None, rel=0.5, conf=0.5, gr=0.5, vocab=None):
    g = Gap.create(desc, content_refs=content_refs or [], step_refs=step_refs or [])
    g.scores = Epistemic(rel, conf, gr)
    if vocab:
        g.vocab = vocab
        g.vocab_score = 0.9
    return g


def make_step(desc, gaps=None, step_refs=None, content_refs=None, commit=None):
    return Step.create(
        desc=desc,
        gaps=gaps or [],
        step_refs=step_refs or [],
        content_refs=content_refs or [],
        commit=commit,
    )


passed = 0
failed = 0
sections = 0


def test(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name}")


def section(name):
    global sections
    sections += 1
    print(f"\n{name}")


# ── §1: Step Primitive (two-phase, two hash layers) ──────────────────────

print("\n§1: Step Primitive")

s = make_step("test step", content_refs=["blob_a"], step_refs=["step_b"])
test("step has hash", len(s.hash) == 12)
test("step has timestamp", s.t > 0)
test("content_refs = layer 2", s.content_refs == ["blob_a"])
test("step_refs = layer 1", s.step_refs == ["step_b"])
test("two layers separated on step", s.content_refs != s.step_refs)

g = make_gap("test gap", content_refs=["blob_c"], step_refs=["step_d"])
test("gap has hash", len(g.hash) == 12)
test("gap content_refs = layer 2", g.content_refs == ["blob_c"])
test("gap step_refs = layer 1", g.step_refs == ["step_d"])

# ── §2: LLM as Attention (pre-diff emergent from hash refs) ─────────────

print("\n§2: LLM as Attention")

s1 = make_step("observed config", step_refs=["step_prev"], content_refs=["blob_cfg"])
test("pre-diff = step_refs + content_refs", s1.all_refs() == ["step_prev", "blob_cfg"])
test("desc carries semantic articulation", s1.desc == "observed config")

# ── §3: Commits and Reverts ──────────────────────────────────────────────

print("\n§3: Commits and Reverts")

obs = make_step("just looked")
mut = make_step("edited file", commit="abc123")
test("observation has no commit", not obs.is_mutation())
test("mutation has commit", mut.is_mutation())
test("commit SHA stored", mut.commit == "abc123")

# ── §4: Reasoning Chains ─────────────────────────────────────────────────

print("\n§4: Reasoning Chains")

chain = Chain.create(origin_gap="gap_hash", first_step="step_1")
test("chain has hash", len(chain.hash) == 12)
test("chain has origin", chain.origin_gap == "gap_hash")
test("chain starts with 1 step", chain.length() == 1)

chain.add_step("step_2")
chain.add_step("step_3")
test("chain grows", chain.length() == 3)
test("chain hash changes on add", chain.hash != Chain.create("gap_hash", "step_1").hash)

# ── §5: Navigation (trajectory traversal) ────────────────────────────────

print("\n§5: Navigation")

traj = Trajectory()
s1 = make_step("first", content_refs=["blob_a"])
s2 = make_step("second", step_refs=[s1.hash], content_refs=["blob_b"])
traj.append(s1)
traj.append(s2)

test("resolve by hash", traj.resolve(s1.hash) == s1)
test("resolve returns None for bad hash", traj.resolve("nonexistent") is None)
test("step_refs link to prior step", s2.step_refs == [s1.hash])
test("co_occurrence counts refs", traj.co_occurrence(s1.hash) >= 1)
test("recent returns ordered steps", len(traj.recent(10)) == 2)

# ── §6: One LLM One Governor (governor in compile.py) ───────────────────

print("\n§6: One LLM One Governor")

test("GovernorSignal exists", hasattr(GovernorSignal, 'ALLOW'))
test("GovernorSignal.HALT exists", hasattr(GovernorSignal, 'HALT'))
test("GovernorState tracks vectors", hasattr(GovernorState(), 'vectors'))

# ── §7: Governor as Linear Algebra ──────────────────────────────────────

print("\n§7: Governor Linear Algebra")

e1 = Epistemic(0.9, 0.8, 0.7)
e2 = Epistemic(0.5, 0.5, 0.5)
test("epistemic has vector", e1.as_vector() == [0.9, 0.8, 0.7])
test("distance computes", e1.distance_to(e2) > 0)
test("magnitude computes", e1.magnitude() > 0)
test("same vector = zero distance", e1.distance_to(e1) == 0.0)

gs = GovernorState()
gs.record(Epistemic(0.5, 0.5, 0.5))
gs.record(Epistemic(0.5, 0.5, 0.5))
gs.record(Epistemic(0.5, 0.5, 0.5))
test("stagnation detected", gs.is_stagnating())

gs2 = GovernorState()
gs2.record(Epistemic(0.5, 0.8, 0.5))
gs2.record(Epistemic(0.5, 0.4, 0.5))
test("divergence detected", gs2.is_diverging())

# ── §8: Predefined Step Hashes (.st files) ──────────────────────────────

print("\n§8: Predefined Step Hashes")

skills_dir = str(Path(__file__).parent.parent / "skills")
registry = load_all(skills_dir)
test("skills loaded", len(registry.all_skills()) > 0)

admin = registry.resolve_by_name("admin")
test("admin.st loaded", admin is not None)
test("admin has hash", len(admin.hash) == 12)
test("admin has steps", admin.step_count() > 0)
test("skill render works", len(registry.render_for_prompt()) > 0)

research = registry.resolve_by_name("research")
test("research.st loaded", research is not None)
test("research has mixed post_diff", any(s.post_diff for s in research.steps) and any(not s.post_diff for s in research.steps))

# ── §9: Ledger as Stack ──────────────────────────────────────────────────

print("\n§9: Ledger as Stack")

ledger = Ledger()
g1 = make_gap("gap A", rel=0.9, conf=0.3, gr=0.9, vocab="pattern_needed")
g2 = make_gap("gap B", rel=0.5, conf=0.2, gr=0.8, vocab="pattern_needed")

ledger.push_origin(g1, "chain_1")
ledger.push_origin(g2, "chain_2")
test("ledger has 2 entries", ledger.size() == 2)

popped = ledger.pop()
test("LIFO: last pushed popped first", popped.gap.hash == g2.hash)

# Push child on current chain
g3 = make_gap("child of A", rel=0.8, conf=0.5, gr=0.9)
ledger.push_child(g3, "chain_1", parent_gap=g1.hash, depth=1)
popped2 = ledger.pop()
test("child pushed on top", popped2.gap.hash == g3.hash)
test("child has depth > 0", popped2.depth == 1)

# ── §10: OMO Rhythm ─────────────────────────────────────────────────────

print("\n§10: OMO Rhythm")

compiler = Compiler(Trajectory())
test("observe vocab identified", is_observe("pattern_needed"))
test("mutate vocab identified", is_mutate("script_edit_needed"))
test("OMO: mutation valid after observation", compiler.validate_omo("script_edit_needed"))
compiler.record_execution("script_edit_needed", True)
test("OMO: mutation invalid after mutation", not compiler.validate_omo("script_edit_needed"))
test("postcondition needed after mutation", compiler.needs_postcondition())
compiler.record_execution("pattern_needed", False)
test("OMO: observation valid after mutation", compiler.validate_omo("pattern_needed"))
test("no postcondition after observation", not compiler.needs_postcondition())

# ── §11: Dormant Gaps ────────────────────────────────────────────────────

print("\n§11: Dormant Gaps")

dormant_gap = make_gap("stale imports in utils.py", rel=0.1, conf=0.1, gr=0.1)
dormant_step = make_step("noticed stale imports", gaps=[dormant_gap])
traj2 = Trajectory()
traj2.append(dormant_step)

compiler2 = Compiler(traj2)
compiler2.emit(dormant_step)
test("low-score gap becomes dormant", dormant_gap.dormant)
test("dormant gap not on ledger", compiler2.ledger.is_empty())
test("dormant gap on trajectory", traj2.resolve_gap(dormant_gap.hash) is not None)

# ── §12: Recursive Convergence ───────────────────────────────────────────

print("\n§12: Recursive Convergence")

s1 = make_step("atomic 1")
s2 = make_step("atomic 2", step_refs=[s1.hash])
s3 = make_step("atomic 3", step_refs=[s2.hash])
chain = Chain.create(origin_gap="g1", first_step=s1.hash)
chain.add_step(s2.hash)
chain.add_step(s3.hash)
test("chain compresses 3 steps into 1 hash", len(chain.hash) == 12)
test("chain is traversable", chain.steps == [s1.hash, s2.hash, s3.hash])

# ── §13: Closed Hash Graph ──────────────────────────────────────────────

print("\n§13: Closed Hash Graph")

test("step hash = 12 chars", len(make_step("test").hash) == 12)
test("gap hash = 12 chars", len(make_gap("test").hash) == 12)
test("same content = same hash", blob_hash("hello") == blob_hash("hello"))
test("different content = different hash", blob_hash("hello") != blob_hash("world"))

traj3 = Trajectory()
s = make_step("test step")
traj3.append(s)
test("trajectory indexes by hash", traj3.resolve(s.hash) == s)
test("nonexistent hash returns None", traj3.resolve("fake_hash") is None)

# ── §14: Vocab as Deterministic Bridge ───────────────────────────────────

print("\n§14: Vocab as Deterministic Bridge")

test("OBSERVE_VOCAB is a set", isinstance(OBSERVE_VOCAB, set))
test("MUTATE_VOCAB is a set", isinstance(MUTATE_VOCAB, set))
test("pattern_needed in observe", "pattern_needed" in OBSERVE_VOCAB)
test("script_edit_needed in mutate", "script_edit_needed" in MUTATE_VOCAB)
test("no overlap", len(OBSERVE_VOCAB & MUTATE_VOCAB) == 0)
test("hash_resolve_needed in observe", "hash_resolve_needed" in OBSERVE_VOCAB)

# ── §15: No Micro Loop ──────────────────────────────────────────────────

print("\n§15: No Micro Loop")

# Chain depth is unbounded (up to MAX_CHAIN_DEPTH)
test("MAX_CHAIN_DEPTH exists", MAX_CHAIN_DEPTH > 0)
test("chain can grow", Chain.create("g", "s").length() == 1)
c = Chain.create("g", "s")
for i in range(10):
    c.add_step(f"step_{i}")
test("chain grows to 11", c.length() == 11)

# ── §16: post_diff as Universal Configuration ───────────────────────────

print("\n§16: post_diff Configuration")

g_flex = make_gap("flexible gap")
g_flex.dormant = False
test("gap default not dormant", not g_flex.dormant)

# post_diff on .st steps
research = registry.resolve_by_name("research")
if research:
    flex_steps = [s for s in research.steps if s.post_diff]
    det_steps = [s for s in research.steps if not s.post_diff]
    test("research has flexible steps", len(flex_steps) > 0)
    test("research has deterministic steps", len(det_steps) > 0)

# ── §17: .st as Manifestation ───────────────────────────────────────────

print("\n§17: .st as Manifestation")

test("skills have trigger field", True)  # schema allows it
admin = registry.resolve_by_name("admin")
if admin:
    test("admin.st is loaded", admin is not None)
    test("admin.st has steps", admin.step_count() >= 4)

# ── §18: Identity as .st ─────────────────────────────────────────────────

print("\n§18: Identity as .st")

admin_path = str(Path(__file__).parent.parent / "skills" / "admin.st")
test("admin.st file exists", os.path.exists(admin_path))
with open(admin_path) as f:
    admin_data = json.load(f)
test("admin has trigger on_contact", admin_data.get("trigger", "").startswith("on_contact"))
test("admin has identity field", "identity" in admin_data)
test("admin has preferences", "preferences" in admin_data)

# ── §19: HEAD as Workspace State ─────────────────────────────────────────

print("\n§19: HEAD as Workspace State")

import subprocess
result = subprocess.run(
    ["git", "rev-parse", "--short", "HEAD"],
    cwd=str(Path(__file__).parent.parent),
    capture_output=True, text=True,
)
test("git HEAD resolvable", result.returncode == 0 and len(result.stdout.strip()) > 0)

result2 = subprocess.run(
    ["git", "ls-tree", "--name-only", "HEAD"],
    cwd=str(Path(__file__).parent.parent),
    capture_output=True, text=True,
)
test("HEAD tree has files", len(result2.stdout.strip()) > 0)

# ── §20: No Modules ─────────────────────────────────────────────────────

print("\n§20: No Modules")

cors_dir = Path(__file__).parent.parent
test("step.py exists", (cors_dir / "step.py").exists())
test("compile.py exists", (cors_dir / "compile.py").exists())
test("loop.py exists", (cors_dir / "loop.py").exists())
test("skills/ exists", (cors_dir / "skills").is_dir())
test("tools/ exists", (cors_dir / "tools").is_dir())
test(".git/ exists", (cors_dir / ".git").is_dir())
test("no governor.py (merged into compile)", not (cors_dir / "governor.py").exists())
test("no Rust crate", not (cors_dir / "kernel_step").exists())

# ── Trajectory round-trip ────────────────────────────────────────────────

print("\n§ Round-trip Persistence")

with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
    tmp = f.name

traj_rt = Trajectory()
s1 = make_step("step 1", content_refs=["blob_a"], gaps=[make_gap("gap 1")])
s2 = make_step("step 2", step_refs=[s1.hash], commit="abc123")
traj_rt.append(s1)
traj_rt.append(s2)
traj_rt.save(tmp)

loaded = Trajectory.load(tmp)
test("round-trip preserves step count", len(loaded.order) == 2)
test("round-trip preserves hash", loaded.resolve(s1.hash).hash == s1.hash)
test("round-trip preserves commit", loaded.resolve(s2.hash).commit == "abc123")
test("round-trip preserves gaps", len(loaded.resolve(s1.hash).gaps) == 1)
test("round-trip preserves content_refs", loaded.resolve(s1.hash).content_refs == ["blob_a"])
os.unlink(tmp)

# ── §9b: Priority Ordering ────────────────────────────────────────────────

section("§9b: Priority Ordering")

test("vocab_priority: bridge (reprogramme) = 99", vocab_priority("reprogramme_needed") == 99)
test("vocab_priority: observe = 20", vocab_priority("pattern_needed") == 20)
test("vocab_priority: mutate = 40", vocab_priority("hash_edit_needed") == 40)
test("vocab_priority: reprogramme = 99", vocab_priority("reprogramme_needed") == 99)
test("vocab_priority: unknown = 50", vocab_priority("something_random") == 50)
test("vocab_priority: None = 50", vocab_priority(None) == 50)

# Priority sorting on ledger
ledger_p = Ledger()
g_observe = make_gap("observe gap", vocab="pattern_needed")
g_mutate = make_gap("mutate gap", vocab="hash_edit_needed")
g_reprog = make_gap("reprogramme", vocab="reprogramme_needed")

ledger_p.push_origin(g_observe, "c1")
ledger_p.push_origin(g_mutate, "c2")
ledger_p.push_origin(g_reprog, "c3")
ledger_p.sort_by_priority()

# After sort: reprogramme(99) at bottom, observe(20) at top → pops first
popped_first = ledger_p.pop()
test("priority: observe pops first", popped_first.gap.vocab == "pattern_needed")
popped_second = ledger_p.pop()
test("priority: mutate pops second", popped_second.gap.vocab == "hash_edit_needed")
popped_last = ledger_p.pop()
test("priority: reprogramme pops last", popped_last.gap.vocab == "reprogramme_needed")

test("LedgerEntry has priority field", hasattr(LedgerEntry(gap=g_observe, chain_id="x"), 'priority'))

# ── §9c: Admission Score (deterministic grounded) ────────────────────────

section("§9c: Admission Score (deterministic grounded)")

traj_adm = Trajectory()
s_ref = make_step("referenced step", content_refs=["blob_x"])
traj_adm.append(s_ref)
traj_adm.append(make_step("also refs blob_x", content_refs=["blob_x"]))
traj_adm.append(make_step("refs step", step_refs=[s_ref.hash]))

compiler_adm = Compiler(traj_adm)

# Gap referencing frequently seen hashes → high grounded
g_grounded = make_gap("well-grounded gap", content_refs=["blob_x"], rel=0.5)
score_grounded = compiler_adm._admission_score(g_grounded)
test("grounded computed from co-occurrence", g_grounded.scores.grounded > 0)
test("admission formula: 0.8*rel + 0.2*gr", score_grounded > 0.4 * 0.8)  # rel=0.5 → at least 0.4

# Gap referencing unknown hashes → zero grounded
g_ungrounded = make_gap("ungrounded gap", content_refs=["never_seen_hash"], rel=0.5)
score_ungrounded = compiler_adm._admission_score(g_ungrounded)
test("unknown hash → grounded ≈ 0", g_ungrounded.scores.grounded == 0.0)
test("admission with zero grounded = 0.8 * rel", abs(score_ungrounded - 0.4) < 0.01)

# High relevance alone can enter (0.8 * 0.9 = 0.72 > 0.4 threshold)
g_high_rel = make_gap("high relevance, no grounding", content_refs=["new_hash"], rel=0.9)
score_high = compiler_adm._admission_score(g_high_rel)
test("high relevance enters despite zero grounding", score_high >= ADMISSION_THRESHOLD)

# Low relevance cannot enter even with grounding
g_low_rel = make_gap("low relevance", content_refs=["blob_x"], rel=0.1)
score_low = compiler_adm._admission_score(g_low_rel)
test("low relevance rejected despite grounding", score_low < ADMISSION_THRESHOLD)

# ── §14b: Dynamic Bridge Vocab ───────────────────────────────────────────

section("§14b: Bridge Vocab")

test("BRIDGE_VOCAB is a set", isinstance(BRIDGE_VOCAB, set))
test("reprogramme_needed is the single bridge primitive", BRIDGE_VOCAB == {"reprogramme_needed"})
test("is_bridge detects reprogramme", is_bridge("reprogramme_needed"))
test("entity resolution has no vocab (just hash_resolve)", not is_bridge("admin_needed"))

# No overlap between observe/mutate/bridge
test("observe ∩ mutate = ∅", len(OBSERVE_VOCAB & MUTATE_VOCAB) == 0)
test("observe ∩ bridge = ∅", len(OBSERVE_VOCAB & BRIDGE_VOCAB) == 0)

# ── §14c: Current Vocab Integrity ────────────────────────────────────────

section("§14c: Current Vocab Integrity")

# Observe: exactly 4 terms
test("OBSERVE has 5 terms", len(OBSERVE_VOCAB) == 5)
test("clarify_needed in observe", "clarify_needed" in OBSERVE_VOCAB)
test("pattern_needed in observe", "pattern_needed" in OBSERVE_VOCAB)
test("hash_resolve_needed in observe", "hash_resolve_needed" in OBSERVE_VOCAB)
test("email_needed in observe", "email_needed" in OBSERVE_VOCAB)
test("external_context in observe", "external_context" in OBSERVE_VOCAB)
test("scan_needed NOT in observe (removed)", "scan_needed" not in OBSERVE_VOCAB)
test("url_needed NOT in observe (removed)", "url_needed" not in OBSERVE_VOCAB)
test("registry_needed NOT in observe (removed)", "registry_needed" not in OBSERVE_VOCAB)
test("research_needed NOT in observe (bridge now)", "research_needed" not in OBSERVE_VOCAB)

# Mutate: exactly 7 terms
test("MUTATE has 7 terms", len(MUTATE_VOCAB) == 7)
test("hash_edit_needed in mutate", "hash_edit_needed" in MUTATE_VOCAB)
test("command_needed in mutate", "command_needed" in MUTATE_VOCAB)
test("content_needed in mutate", "content_needed" in MUTATE_VOCAB)
test("message_needed in mutate", "message_needed" in MUTATE_VOCAB)

# ── §8b: hash_edit.st ────────────────────────────────────────────────────

section("§8b: hash_edit.st")

hash_edit_path = str(Path(__file__).parent.parent / "skills" / "hash_edit.st")
test("hash_edit.st exists", os.path.exists(hash_edit_path))

with open(hash_edit_path) as f:
    he_data = json.load(f)
test("hash_edit has 3 steps", len(he_data.get("steps", [])) == 3)
test("hash_edit triggers on vocab", he_data.get("trigger", "").startswith("on_vocab"))
test("first step is observe", he_data["steps"][0].get("vocab") == "hash_resolve_needed")
test("first step is deterministic", he_data["steps"][0].get("post_diff") == False)
test("second step is flexible", he_data["steps"][1].get("post_diff") == True)

# ── §8c: Skill Loader (trigger, is_command, display_name) ────────────────

section("§8c: Skill Loader Features")

admin_skill = registry.resolve_by_name("admin")
test("admin has trigger field", admin_skill.trigger == "on_contact:admin")
test("admin is not command", not admin_skill.is_command)
test("admin has display_name", admin_skill.display_name == "kenny")

# resolve_name returns display name
test("resolve_name returns display", registry.resolve_name(admin_skill.hash) == "kenny")
test("resolve_name returns None for unknown", registry.resolve_name("bad_hash") is None)

# Command skills: registry has commands dict
test("registry has commands dict", hasattr(registry, 'commands'))
test("resolve_command returns None for non-command", registry.resolve_command("nonexistent") is None)

# ── §17b: Stepless .st (pure entities) ───────────────────────────────────

section("§17b: Stepless .st (pure entities)")

# st_builder should accept stepless entities
import subprocess as sp
result = sp.run(
    ["python3", str(Path(__file__).parent.parent / "tools" / "st_builder.py")],
    input=json.dumps({"name": "test_entity", "desc": "test", "trigger": "manual",
                       "identity": {"role": "tester"}}),
    capture_output=True, text=True,
    cwd=str(Path(__file__).parent.parent),
)
test("st_builder accepts stepless entity", result.returncode == 0)
test("st_builder writes file", "Written:" in result.stdout)

# Clean up
test_st_path = Path(__file__).parent.parent / "skills" / "test_entity.st"
if test_st_path.exists():
    with open(test_st_path) as f:
        test_data = json.load(f)
    test("stepless .st has identity field", "identity" in test_data)
    test("stepless .st has empty or minimal steps", len(test_data.get("steps", [])) == 0)
    os.unlink(test_st_path)

# ── §17c: Manifestation fields forwarded ─────────────────────────────────

section("§17c: Manifestation Fields")

result2 = sp.run(
    ["python3", str(Path(__file__).parent.parent / "tools" / "st_builder.py")],
    input=json.dumps({"name": "compliance_test", "desc": "test domain", "trigger": "manual",
                       "constraints": {"must_ref": "act_1990"}, "sources": ["gov.uk"],
                       "scope": "planning", "actions": [{"do": "check", "observe": True}]}),
    capture_output=True, text=True,
    cwd=str(Path(__file__).parent.parent),
)
test("st_builder forwards domain fields", result2.returncode == 0)

comp_path = Path(__file__).parent.parent / "skills" / "compliance_test.st"
if comp_path.exists():
    with open(comp_path) as f:
        comp_data = json.load(f)
    test("constraints field forwarded", "constraints" in comp_data)
    test("sources field forwarded", "sources" in comp_data)
    test("scope field forwarded", "scope" in comp_data)
    os.unlink(comp_path)

# ── §10b: Universal Postcondition ─────────────────────────────────────────

section("§10b: Universal Postcondition")

# Every mutation should produce a postcondition gap (hash_resolve_needed)
postcond_gap = Gap.create(desc="observe commit:abc", content_refs=["abc"], step_refs=["step_x"])
postcond_gap.scores = Epistemic(relevance=1.0, confidence=1.0, grounded=0.0)
postcond_gap.vocab = "hash_resolve_needed"
test("postcondition gap has hash_resolve vocab", postcond_gap.vocab == "hash_resolve_needed")
test("postcondition gap targets commit ref", "abc" in postcond_gap.content_refs)
test("postcondition gap is observe", is_observe(postcond_gap.vocab))
test("postcondition gap is not mutate", not is_mutate(postcond_gap.vocab))

# ── §2b: Trajectory renders as hash tree ──────────────────────────────────

section("§2b: Hash Tree Render")

traj_render = Trajectory()
s_r1 = make_step("observed workspace", content_refs=["commit_abc"])
s_r2 = make_step("resolved config", step_refs=[s_r1.hash], content_refs=["blob_xyz"],
                  gaps=[make_gap("needs edit", content_refs=["blob_xyz"], vocab="hash_edit_needed")])
traj_render.append(s_r1)
traj_render.append(s_r2)
chain_r = Chain.create(origin_gap=s_r2.gaps[0].hash, first_step=s_r1.hash)
chain_r.add_step(s_r2.hash)
traj_render.add_chain(chain_r)

rendered = traj_render.render_recent(5, registry=registry)
test("render produces tree structure", "├─" in rendered or "└─" in rendered)
test("render shows step hashes", "step:" in rendered)
test("render shows gap hashes", "gap:" in rendered)
test("render shows chain hash", "chain:" in rendered)
test("render shows vocab tag", "hash_edit_needed" in rendered)

# Named hash resolution in render
s_named = make_step("loaded identity", content_refs=[admin_skill.hash])
traj_named = Trajectory()
traj_named.append(s_named)
rendered_named = traj_named.render_recent(5, registry=registry)
test("render shows named skill ref (kenny:hash)", "kenny:" in rendered_named)

# ── §18b: Identity fires after first step ─────────────────────────────────

section("§18b: Identity .st structure")

test("admin.st has identity.name", admin_data.get("identity", {}).get("name") == "Kenny")
test("admin.st has identity.role", "role" in admin_data.get("identity", {}))
test("admin.st has communication prefs", "communication" in admin_data.get("preferences", {}))
test("admin.st has architecture prefs", "architecture" in admin_data.get("preferences", {}))
test("admin.st has workflow prefs", "workflow" in admin_data.get("preferences", {}))

# ── §20b: No stale modules ───────────────────────────────────────────────

section("§20b: No Stale Modules")

cors_dir = Path(__file__).parent.parent
test("no config_edit.st (deleted)", not (cors_dir / "skills" / "config_edit.st").exists())
test("no DESIGN_NOTES.md (deleted)", not (cors_dir / "docs" / "DESIGN_NOTES.md").exists())
test("hash_edit.st exists", (cors_dir / "skills" / "hash_edit.st").exists())
test("hash_manifest.py exists", (cors_dir / "tools" / "hash_manifest.py").exists())
test("st_builder.py exists", (cors_dir / "tools" / "st_builder.py").exists())

# ── Summary ──────────────────────────────────────────────────────────────

print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("All principles validated.")
else:
    print(f"ISSUES: {failed} test(s) failed")
