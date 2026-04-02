"""Skill loader — load `.st` packages, hash them, build a resolvable registry.

The loader is the runtime projection of authored `.st` files. It should not
discard manifestation structure that later layers may need. So it now does two
things at once:
  1. normalizes the core fields the runtime uses directly
  2. preserves the full package payload so nothing structural is lost at load
     time
"""

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SEMANTIC_FIELDS = {
    "identity",
    "preferences",
    "constraints",
    "sources",
    "scope",
    "schema",
    "access_rules",
    "principles",
    "boundaries",
    "domain_knowledge",
    "entity_refs",
}

BASE_SKILL_FIELDS = {
    "name",
    "desc",
    "steps",
    "source",
    "display_name",
    "trigger",
    "author",
    "refs",
    "artifact_kind",
}

BASE_STEP_FIELDS = {
    "action",
    "desc",
    "vocab",
    "post_diff",
    "relevance",
    "resolve",
    "condition",
    "inject",
    "content_refs",
    "step_refs",
    "kind",
    "goal",
    "allowed_vocab",
    "manifestation",
    "generation",
    "transitions",
    "terminal",
    "requires_postcondition",
    "activation_key",
}


@dataclass
class SkillStep:
    """One atomic step within a skill package.

    The loader keeps the fields the current runtime uses directly and preserves
    all additional authored fields in `extra` so no manifestation information is
    lost during loading.
    """
    action: str
    desc: str
    vocab: str | None = None    # precondition vocab mapping (None = internal/deterministic)
    post_diff: bool = True      # True = flexible (LLM reasons), False = deterministic
    relevance: float | None = None
    resolve: list[str] = field(default_factory=list)
    condition: Any = None
    inject: Any = None
    content_refs: list[str] = field(default_factory=list)
    step_refs: list[str] = field(default_factory=list)
    kind: str | None = None
    goal: str | None = None
    allowed_vocab: list[str] = field(default_factory=list)
    manifestation: dict = field(default_factory=dict)
    generation: dict = field(default_factory=dict)
    transitions: dict = field(default_factory=dict)
    terminal: bool = False
    requires_postcondition: bool = False
    activation_key: str | None = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        data = {
            "action": self.action,
            "desc": self.desc,
            "vocab": self.vocab,
            "post_diff": self.post_diff,
        }
        if self.relevance is not None:
            data["relevance"] = self.relevance
        if self.resolve:
            data["resolve"] = self.resolve
        if self.condition is not None:
            data["condition"] = self.condition
        if self.inject is not None:
            data["inject"] = self.inject
        if self.content_refs:
            data["content_refs"] = self.content_refs
        if self.step_refs:
            data["step_refs"] = self.step_refs
        if self.kind is not None:
            data["kind"] = self.kind
        if self.goal is not None:
            data["goal"] = self.goal
        if self.allowed_vocab:
            data["allowed_vocab"] = self.allowed_vocab
        if self.manifestation:
            data["manifestation"] = self.manifestation
        if self.generation:
            data["generation"] = self.generation
        if self.transitions:
            data["transitions"] = self.transitions
        if self.terminal:
            data["terminal"] = True
        if self.requires_postcondition:
            data["requires_postcondition"] = True
        if self.activation_key is not None:
            data["activation_key"] = self.activation_key
        data.update(self.extra)
        return data


@dataclass
class Skill:
    """A predefined step package — hash-addressable and preserved losslessly."""
    hash: str
    name: str
    desc: str
    steps: list[SkillStep]
    source: str                 # file path for debugging
    display_name: str = ""      # from identity.name or skill name — used in tree render
    trigger: str = "manual"     # when this skill fires
    is_command: bool = False     # True = /command only, not surfaceable by LLM
    artifact_kind: str = "action"
    author: str | None = None
    refs: dict = field(default_factory=dict)
    semantics: dict = field(default_factory=dict)
    payload: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)

    def step_count(self) -> int:
        return len(self.steps)

    def deterministic_steps(self) -> list[SkillStep]:
        return [s for s in self.steps if not s.post_diff]

    def flexible_steps(self) -> list[SkillStep]:
        return [s for s in self.steps if s.post_diff]

    def to_dict(self) -> dict:
        if self.payload:
            return dict(self.payload)
        data = {
            "name": self.name,
            "desc": self.desc,
            "trigger": self.trigger,
            "steps": [step.to_dict() for step in self.steps],
        }
        if self.author is not None:
            data["author"] = self.author
        if self.refs:
            data["refs"] = self.refs
        if self.artifact_kind:
            data["artifact_kind"] = self.artifact_kind
        data.update(self.semantics)
        data.update(self.extra)
        return data


class SkillRegistry:
    """Registry of all loaded skills, resolvable by hash or name.

    Two visibility tiers:
      - Bridge skills: in the LLM's awareness, surfaceable through gaps
      - Command skills: hidden from LLM, triggered only via /commands
    """

    def __init__(self):
        self.by_hash: dict[str, Skill] = {}
        self.by_name: dict[str, Skill] = {}
        self.commands: dict[str, Skill] = {}  # command name → Skill
        self._surfaceable_hashes: set[str] = set()

    def register(self, skill: Skill):
        self.by_hash[skill.hash] = skill
        if skill.is_command:
            cmd_name = skill.trigger.replace("command:", "")
            self.commands[cmd_name] = skill
        else:
            self.by_name[skill.name] = skill
            self._surfaceable_hashes.add(skill.hash)

    def resolve(self, hash: str) -> Skill | None:
        return self.by_hash.get(hash)

    def resolve_name(self, hash: str) -> str | None:
        """Hash → display name, or None if not a known skill.

        Returns the identity-derived display name (e.g. 'kenny')
        so the tree renders as kenny:72b1d5ffc964 instead of admin:72b1d5ffc964.
        """
        skill = self.by_hash.get(hash)
        return skill.display_name if skill else None

    def resolve_by_name(self, name: str) -> Skill | None:
        return self.by_name.get(name)

    def resolve_command(self, name: str) -> Skill | None:
        """Resolve a /command by name."""
        return self.commands.get(name)

    def all_skills(self) -> list[Skill]:
        return [self.by_hash[h] for h in self._surfaceable_hashes if h in self.by_hash]

    def all_commands(self) -> list[Skill]:
        return list(self.commands.values())

    def render_for_prompt(self) -> str:
        """Render all skills as context for LLM prompt injection."""
        if not self.by_hash:
            return ""
        lines = ["## Available Skills"]
        for skill in self.by_hash.values():
            steps_desc = " → ".join(s.action for s in skill.steps)
            mode = "mixed"
            if all(not s.post_diff for s in skill.steps):
                mode = "deterministic"
            elif all(s.post_diff for s in skill.steps):
                mode = "flexible"
            lines.append(f"[{skill.hash}] {skill.name}: {skill.desc}")
            lines.append(f"  steps: {steps_desc} ({mode})")
        return "\n".join(lines)


def compute_skill_hash(content: str) -> str:
    """Content-addressed hash for a skill script."""
    return hashlib.sha256(content.encode()).hexdigest()[:12]


def infer_artifact_kind(data: dict, path: str, is_command: bool) -> str:
    explicit = data.get("artifact_kind")
    if isinstance(explicit, str) and explicit:
        return explicit
    if "codons" in Path(path).parts:
        return "codon"
    if "entities" in Path(path).parts or Path(path).name == "admin.st":
        return "entity"
    if "actions" in Path(path).parts:
        return "action"
    has_semantics = any(field in data for field in SEMANTIC_FIELDS)
    has_steps = bool(data.get("steps"))
    if has_semantics and has_steps:
        return "hybrid"
    if has_semantics or not has_steps:
        return "entity"
    if is_command:
        return "action"
    return "action"


def _normalize_step(data: dict) -> SkillStep:
    extra = {k: v for k, v in data.items() if k not in BASE_STEP_FIELDS}
    return SkillStep(
        action=data["action"],
        desc=data.get("desc", ""),
        vocab=data.get("vocab"),
        post_diff=data.get("post_diff", True),
        relevance=data.get("relevance"),
        resolve=list(data.get("resolve", []) or []),
        condition=data.get("condition"),
        inject=data.get("inject"),
        content_refs=list(data.get("content_refs", []) or []),
        step_refs=list(data.get("step_refs", []) or []),
        kind=data.get("kind"),
        goal=data.get("goal"),
        allowed_vocab=list(data.get("allowed_vocab", []) or []),
        manifestation=dict(data.get("manifestation", {}) or {}),
        generation=dict(data.get("generation", {}) or {}),
        transitions=dict(data.get("transitions", {}) or {}),
        terminal=bool(data.get("terminal", False)),
        requires_postcondition=bool(data.get("requires_postcondition", False)),
        activation_key=data.get("activation_key"),
        extra=extra,
    )


def load_skill(path: str) -> Skill | None:
    """Load a single .st file into a Skill."""
    try:
        with open(path) as f:
            raw = f.read()
        data = json.loads(raw)

        steps = [_normalize_step(step) for step in data.get("steps", [])]

        skill_hash = compute_skill_hash(raw)

        identity = data.get("identity", {})
        if Path(path).name == "admin.st" or data["name"] == "admin":
            display = "admin"
        else:
            display = identity.get("name", data["name"]).lower() if identity else data["name"]

        trigger = data.get("trigger", "manual")
        is_command = trigger.startswith("command:")
        artifact_kind = infer_artifact_kind(data, path, is_command)
        semantics = {field: data[field] for field in SEMANTIC_FIELDS if field in data}
        extra = {k: v for k, v in data.items() if k not in BASE_SKILL_FIELDS and k not in SEMANTIC_FIELDS}

        return Skill(
            hash=skill_hash,
            name=data["name"],
            desc=data.get("desc", ""),
            steps=steps,
            source=path,
            display_name=display,
            trigger=trigger,
            is_command=is_command,
            artifact_kind=artifact_kind,
            author=data.get("author"),
            refs=dict(data.get("refs", {}) or {}),
            semantics=semantics,
            payload=data,
            extra=extra,
        )
    except Exception as e:
        print(f"  [skills] failed to load {path}: {e}")
        return None


def load_all(skills_dir: str = None) -> SkillRegistry:
    """Load all .st files from the skills directory and subdirectories.

    Scans skills/ and skills/codons/ — codons are loaded with the same
    mechanism but have immutable tree_policy protection.
    """
    if skills_dir is None:
        skills_dir = str(Path(__file__).parent)

    registry = SkillRegistry()

    # Walk directory tree to find all .st files (includes codons/)
    for root, _dirs, files in os.walk(skills_dir):
        for fname in sorted(files):
            if not fname.endswith(".st"):
                continue
            path = os.path.join(root, fname)
            skill = load_skill(path)
            if skill:
                registry.register(skill)
                # Tag codons for display
                is_codon = "codons" in root
                tag = " [codon]" if is_codon else ""
                print(f"  [skills] loaded {skill.name} [{skill.hash}] ({skill.step_count()} steps){tag}")

    return registry


if __name__ == "__main__":
    reg = load_all()
    print(f"\nLoaded {len(reg.all_skills())} skills")
    print(reg.render_for_prompt())
