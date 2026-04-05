"""test_law9.py — Law 9 compliance tests for validate_chain.

Tests exercise all four outcomes the validator can emit:
  CLEAN      — no background triggers
  CLOSED     — background trigger + downstream await_needed
  HEARTBEAT  — background trigger, no await (heartbeat path)
  ORPHAN     — await_needed with no upstream background trigger
  MISORDERED — await_needed before its background trigger

Also tests:
  - Current reason-needed activations
  - Legacy reprogramme_needed compatibility
  - Mixed chains (some CLOSED, some HEARTBEAT in same skill)
  - Recursive embedded skill validation
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

# Reach the tools module
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
from validate_chain import (
    check_steps,
    Finding,
    validate_file,
    ValidationResult,
    LEGACY_BACKGROUND_VOCAB,
    REASON_VOCAB,
    AWAIT_VOCAB,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def step(vocab: str | None = None, action: str = "do_thing", **extra) -> dict:
    s = {"action": action, "desc": action.replace("_", " "), "post_diff": True}
    if vocab is not None:
        s["vocab"] = vocab
    s.update(extra)
    return s


def skill_json(steps: list[dict], name: str = "test_skill") -> str:
    return json.dumps({"name": name, "desc": "test", "trigger": "manual", "steps": steps})


# ── check_steps unit tests ────────────────────────────────────────────────────

class TestCheckSteps:

    def test_clean_no_background(self):
        """No background or await vocab — returns empty findings."""
        steps = [step("hash_resolve_needed"), step("command_needed"), step(None)]
        findings = check_steps(steps)
        assert findings == []

    def test_closed_explicit_await_for_reason_activation(self):
        """reason_needed + activate_ref followed by await_needed → CLOSED."""
        steps = [
            step("hash_resolve_needed"),
            step(REASON_VOCAB, activate_ref="flow123"),  # index 1
            step("content_needed"),
            step(AWAIT_VOCAB),            # index 3
        ]
        findings = check_steps(steps)
        assert len(findings) == 1
        assert findings[0].kind == "CLOSED"
        assert findings[0].trigger_idx == 1
        assert findings[0].await_idx == 3

    def test_heartbeat_no_await_for_reason_activation(self):
        """reason_needed + activate_ref with no downstream await → HEARTBEAT."""
        steps = [
            step("hash_resolve_needed"),
            step(REASON_VOCAB, activation_ref="flow123"),  # index 1
            step("content_needed"),
        ]
        findings = check_steps(steps)
        assert len(findings) == 1
        assert findings[0].kind == "HEARTBEAT"
        assert findings[0].trigger_idx == 1
        assert findings[0].await_idx == -1

    def test_orphan_await_no_trigger(self):
        """await_needed with no upstream background trigger → ORPHAN."""
        steps = [
            step("hash_resolve_needed"),
            step(AWAIT_VOCAB),            # index 1 — no trigger above it
        ]
        findings = check_steps(steps)
        assert len(findings) == 1
        assert findings[0].kind == "ORPHAN"
        assert findings[0].trigger_idx == -1
        assert findings[0].await_idx == 1

    def test_misordered_await_before_trigger(self):
        """await_needed before its background trigger → MISORDERED."""
        steps = [
            step("hash_resolve_needed"),
            step(AWAIT_VOCAB),            # index 1 — before trigger
            step("content_needed"),
            step(REASON_VOCAB, activate_ref="flow123"),  # index 3 — comes after await
        ]
        findings = check_steps(steps)
        # The await is orphaned/misordered. The activation has no downstream await → HEARTBEAT.
        kinds = {f.kind for f in findings}
        assert "MISORDERED" in kinds
        assert "HEARTBEAT" in kinds

    def test_multiple_triggers_mixed(self):
        """Two background triggers: first has await (CLOSED), second does not (HEARTBEAT)."""
        steps = [
            step(REASON_VOCAB, activate_ref="flow123"),  # index 0
            step("content_needed"),
            step(AWAIT_VOCAB),            # index 2 — closes trigger 0
            step("hash_resolve_needed"),
            step(LEGACY_BACKGROUND_VOCAB),  # index 4 — no await downstream
        ]
        findings = check_steps(steps)
        kinds = [f.kind for f in findings]
        assert "CLOSED" in kinds
        assert "HEARTBEAT" in kinds
        closed = next(f for f in findings if f.kind == "CLOSED")
        assert closed.trigger_idx == 0
        assert closed.await_idx == 2
        heartbeat = next(f for f in findings if f.kind == "HEARTBEAT")
        assert heartbeat.trigger_idx == 4

    def test_multiple_triggers_all_closed(self):
        """Two background triggers, each followed by its own await_needed → all CLOSED."""
        steps = [
            step(REASON_VOCAB, activate_ref="flow123"),  # index 0
            step(AWAIT_VOCAB),            # index 1
            step("content_needed"),
            step(LEGACY_BACKGROUND_VOCAB),  # index 3
            step(AWAIT_VOCAB),            # index 4
        ]
        findings = check_steps(steps)
        kinds = [f.kind for f in findings]
        assert all(k == "CLOSED" for k in kinds)
        assert len(findings) == 2

    def test_adjacent_trigger_and_await(self):
        """background trigger immediately followed by await_needed → CLOSED."""
        steps = [
            step(REASON_VOCAB, activation_ref="flow123"),  # index 0
            step(AWAIT_VOCAB),            # index 1
        ]
        findings = check_steps(steps)
        assert len(findings) == 1
        assert findings[0].kind == "CLOSED"

    def test_plain_reason_step_is_not_background_trigger(self):
        """Ordinary reason_needed without activation metadata is ignored."""
        steps = [
            step(REASON_VOCAB),
            step("hash_resolve_needed"),
        ]
        findings = check_steps(steps)
        assert findings == []

    def test_legacy_reprogramme_trigger_still_validates(self):
        """Legacy reprogramme_needed still counts as a background trigger."""
        steps = [step(LEGACY_BACKGROUND_VOCAB), step(AWAIT_VOCAB)]
        findings = check_steps(steps)
        assert len(findings) == 1
        assert findings[0].kind == "CLOSED"


# ── validate_file tests ────────────────────────────────────────────────────────

class TestValidateFile:

    def _write_st(self, tmp_path: Path, steps: list[dict], name: str = "test") -> Path:
        data = {"name": name, "desc": "test", "trigger": "manual", "steps": steps}
        p = tmp_path / f"{name}.st"
        p.write_text(json.dumps(data))
        return p

    def test_clean_file(self, tmp_path):
        p = self._write_st(tmp_path, [step("hash_resolve_needed"), step("content_needed")])
        result = validate_file(p, registry={})
        assert result.law9_status == "PASS"
        assert not result.findings  # no findings = CLEAN

    def test_heartbeat_file_is_warn(self, tmp_path):
        p = self._write_st(tmp_path, [step(REASON_VOCAB, activate_ref="flow123")])
        result = validate_file(p, registry={})
        assert result.law9_status == "WARN"
        assert result.findings[0].kind == "HEARTBEAT"
        assert not result.has_violations

    def test_closed_file_is_pass(self, tmp_path):
        p = self._write_st(tmp_path, [step(REASON_VOCAB, activate_ref="flow123"), step(AWAIT_VOCAB)])
        result = validate_file(p, registry={})
        assert result.law9_status == "PASS"
        assert result.findings[0].kind == "CLOSED"

    def test_orphan_file_is_fail(self, tmp_path):
        p = self._write_st(tmp_path, [step(AWAIT_VOCAB)])
        result = validate_file(p, registry={})
        assert result.law9_status == "FAIL"
        assert result.has_violations

    def test_misordered_file_is_fail(self, tmp_path):
        p = self._write_st(tmp_path, [step(AWAIT_VOCAB), step(REASON_VOCAB, activate_ref="flow123")])
        result = validate_file(p, registry={})
        assert result.law9_status == "FAIL"
        assert result.has_violations

    def test_invalid_json_is_error(self, tmp_path):
        p = tmp_path / "bad.st"
        p.write_text("{not valid json")
        result = validate_file(p, registry={})
        assert result.law9_status == "ERROR"
        assert result.error is not None

    def test_recursive_embedded_skill(self, tmp_path):
        """Parent skill is CLEAN but embeds a child skill with a violation."""
        import hashlib

        # Write child .st with a violation
        child_steps = [step(AWAIT_VOCAB)]  # orphan
        child_data = {"name": "child", "desc": "child", "trigger": "manual", "steps": child_steps}
        child_raw = json.dumps(child_data)
        child_hash = hashlib.sha256(child_raw.encode()).hexdigest()[:12]
        child_path = tmp_path / "child.st"
        child_path.write_text(child_raw)

        # Write parent .st that references child by hash in content_refs
        parent_steps = [
            {"action": "use_child", "desc": "embed child", "vocab": "hash_resolve_needed",
             "post_diff": False, "content_refs": [child_hash]},
        ]
        parent_data = {"name": "parent", "desc": "parent", "trigger": "manual", "steps": parent_steps}
        parent_path = tmp_path / "parent.st"
        parent_path.write_text(json.dumps(parent_data))

        # Registry maps child hash → path
        registry = {child_hash: child_path}
        result = validate_file(parent_path, registry=registry)

        # Parent itself is CLEAN, but embedded child has violation
        assert len(result.embedded) == 1
        assert result.embedded[0].has_violations
        assert result.has_violations  # propagates up
        assert result.law9_status == "FAIL"

    def test_cycle_detection(self, tmp_path):
        """Self-referencing skill does not infinite-loop."""
        import hashlib

        # Write a skill that references itself
        steps = [{"action": "self_ref", "desc": "self", "vocab": None,
                  "post_diff": False, "content_refs": ["placeholder"]}]
        data = {"name": "cyclic", "desc": "cyclic", "trigger": "manual", "steps": steps}
        raw = json.dumps(data)
        skill_hash = hashlib.sha256(raw.encode()).hexdigest()[:12]

        # Now rewrite with real hash in content_refs
        steps[0]["content_refs"] = [skill_hash]
        raw = json.dumps(data)  # hash won't match exactly but close enough to test
        path = tmp_path / "cyclic.st"
        path.write_text(raw)

        registry = {skill_hash: path}
        # Should not raise RecursionError
        result = validate_file(path, registry=registry)
        assert result is not None


# ── Integration: existing skills are all CLEAN ────────────────────────────────

class TestExistingSkills:
    """Smoke-test the live skills directory — must all pass Law 9."""

    def test_all_existing_skills_pass(self):
        """All skills in skills/ must be Law 9 compliant (PASS or WARN, no FAIL)."""
        import os
        import hashlib
        from validate_chain import validate_all, load_skill_registry

        registry = load_skill_registry()
        results = validate_all(registry)

        assert results, "No .st files found — something is wrong"

        failures = [r for r in results if r.has_violations]
        assert not failures, (
            f"Law 9 violations in existing skills:\n"
            + "\n".join(f"  {r.file}: {[f.message for f in r.findings if f.is_violation]}"
                        for r in failures)
        )

    def test_codon_files_are_clean(self):
        """Codons (primitive building blocks) must not contain background triggers in their steps.

        Codons define the vocabulary — they don't compose it. They RESPOND to
        reprogramme_needed / await_needed as triggers, but their own step bodies
        should not emit further background triggers (that would create implicit chains).
        """
        from validate_chain import validate_file, load_skill_registry

        registry = load_skill_registry()
        codon_dir = Path(__file__).parent.parent / "skills" / "codons"

        for p in sorted(codon_dir.glob("*.st")):
            result = validate_file(p, registry)
            assert not result.has_violations, (
                f"Codon {p.name} has Law 9 violations: "
                f"{[f.message for f in result.findings if f.is_violation]}"
            )
