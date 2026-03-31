"""Skill loader — load .st files, hash them, build a resolvable registry.

Each .st file is a JSON step script. The loader:
1. Reads all .st files from the skills directory
2. Computes a blob hash for each
3. Registers them in a hash→skill map
4. Exposes resolve(hash) and resolve_by_name(name)

The LLM references skills by hash. The kernel resolves them to step sequences.
"""

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SkillStep:
    """One atomic step within a skill script."""
    action: str
    desc: str
    vocab: str | None = None    # precondition vocab mapping (None = internal/deterministic)
    post_diff: bool = True      # True = flexible (LLM reasons), False = deterministic


@dataclass
class Skill:
    """A predefined step script — hash-addressable, executable by the kernel."""
    hash: str
    name: str
    desc: str
    steps: list[SkillStep]
    source: str                 # file path for debugging
    display_name: str = ""      # from identity.name or skill name — used in tree render
    trigger: str = "manual"     # when this skill fires
    is_command: bool = False     # True = /command only, not surfaceable by LLM

    def step_count(self) -> int:
        return len(self.steps)

    def deterministic_steps(self) -> list[SkillStep]:
        return [s for s in self.steps if not s.post_diff]

    def flexible_steps(self) -> list[SkillStep]:
        return [s for s in self.steps if s.post_diff]


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

    def register(self, skill: Skill):
        if skill.is_command:
            # Command skills: not in main registry, only in commands
            cmd_name = skill.trigger.replace("command:", "")
            self.commands[cmd_name] = skill
        else:
            self.by_hash[skill.hash] = skill
            self.by_name[skill.name] = skill

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
        return list(self.by_hash.values())

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


def load_skill(path: str) -> Skill | None:
    """Load a single .st file into a Skill."""
    try:
        raw = open(path).read()
        data = json.loads(raw)

        steps = []
        for s in data.get("steps", []):
            steps.append(SkillStep(
                action=s["action"],
                desc=s.get("desc", ""),
                vocab=s.get("vocab"),
                post_diff=s.get("post_diff", True),
            ))

        skill_hash = compute_skill_hash(raw)

        # Extract display name: identity.name → lowercase, else skill name
        identity = data.get("identity", {})
        display = identity.get("name", data["name"]).lower() if identity else data["name"]

        trigger = data.get("trigger", "manual")
        is_command = trigger.startswith("command:")

        return Skill(
            hash=skill_hash,
            name=data["name"],
            desc=data.get("desc", ""),
            steps=steps,
            source=path,
            display_name=display,
            trigger=trigger,
            is_command=is_command,
        )
    except Exception as e:
        print(f"  [skills] failed to load {path}: {e}")
        return None


def load_all(skills_dir: str = None) -> SkillRegistry:
    """Load all .st files from the skills directory."""
    if skills_dir is None:
        skills_dir = str(Path(__file__).parent)

    registry = SkillRegistry()

    for fname in sorted(os.listdir(skills_dir)):
        if not fname.endswith(".st"):
            continue
        path = os.path.join(skills_dir, fname)
        skill = load_skill(path)
        if skill:
            registry.register(skill)
            print(f"  [skills] loaded {skill.name} [{skill.hash}] ({skill.step_count()} steps)")

    return registry


if __name__ == "__main__":
    reg = load_all()
    print(f"\nLoaded {len(reg.all_skills())} skills")
    print(reg.render_for_prompt())
