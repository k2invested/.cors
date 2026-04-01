import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loop
from skills.loader import load_all


def registry():
    return load_all(str(ROOT / "skills"))


def test_entity_skill_detection_distinguishes_entity_from_action_and_codon():
    reg = registry()
    admin = reg.resolve_by_name("admin")
    hash_edit = reg.resolve_by_name("hash_edit")
    reason = reg.resolve_by_name("reason")

    assert admin is not None and loop._is_entity_skill(admin) is True
    assert hash_edit is not None and loop._is_entity_skill(hash_edit) is False
    assert reason is not None and loop._is_entity_skill(reason) is False


def test_render_entity_tree_shows_entity_space():
    reg = registry()
    tree = loop._render_entity_tree(reg)
    assert tree.startswith("entity_tree")
    assert "kenny:" in tree
    assert "admin.st" in tree

