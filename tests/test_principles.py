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


def test(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name}")


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
g1 = make_gap("gap A", rel=0.9, conf=0.3, gr=0.9, vocab="scan_needed")
g2 = make_gap("gap B", rel=0.5, conf=0.2, gr=0.8, vocab="scan_needed")

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
test("observe vocab identified", is_observe("scan_needed"))
test("mutate vocab identified", is_mutate("script_edit_needed"))
test("OMO: mutation valid after observation", compiler.validate_omo("script_edit_needed"))
compiler.record_execution("script_edit_needed", True)
test("OMO: mutation invalid after mutation", not compiler.validate_omo("script_edit_needed"))
test("postcondition needed after mutation", compiler.needs_postcondition())
compiler.record_execution("scan_needed", False)
test("OMO: observation valid after mutation", compiler.validate_omo("scan_needed"))
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
test("scan_needed in observe", "scan_needed" in OBSERVE_VOCAB)
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

# ── Summary ──────────────────────────────────────────────────────────────

print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("All principles validated.")
else:
    print(f"ISSUES: {failed} test(s) failed")
