import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import env_loader
from env_loader import default_env_paths, load_env


def test_load_env_reads_simple_key_values(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "OPENAI_API_KEY=test-key\n"
        "DISCORD_BOT_TOKEN='discord-token'\n"
        "# comment\n"
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)

    load_env(env_path)

    assert os.environ["OPENAI_API_KEY"] == "test-key"
    assert os.environ["DISCORD_BOT_TOKEN"] == "discord-token"


def test_load_env_does_not_override_existing_values_by_default(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=file-value\n")
    monkeypatch.setenv("OPENAI_API_KEY", "existing-value")

    load_env(env_path)

    assert os.environ["OPENAI_API_KEY"] == "existing-value"


def test_default_env_paths_prefers_local_then_kernelagent():
    paths = default_env_paths("/Users/k2invested/Desktop/cors")
    assert paths[0] == Path("/Users/k2invested/Desktop/cors/.env")
    assert paths[1] == Path("/Users/k2invested/Desktop/KernelAgent/.env")


def test_load_env_uses_first_available_path(tmp_path, monkeypatch):
    root = tmp_path / "cors"
    sibling = tmp_path / "KernelAgent"
    root.mkdir()
    sibling.mkdir()
    (sibling / ".env").write_text("DISCORD_BOT_TOKEN=from-kernelagent\n")
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.setattr(env_loader, "default_env_paths", lambda base_dir=None: default_env_paths(root))

    load_env()

    assert os.environ["DISCORD_BOT_TOKEN"] == "from-kernelagent"
