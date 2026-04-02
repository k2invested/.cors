from types import SimpleNamespace
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import discord_bot


def fake_message(
    *,
    author_id=1,
    author_bot=False,
    guild_id=None,
    channel_id=10,
    mentions=None,
    content="hi",
):
    return SimpleNamespace(
        author=SimpleNamespace(id=author_id, bot=author_bot),
        guild=SimpleNamespace(id=guild_id) if guild_id is not None else None,
        channel=SimpleNamespace(id=channel_id),
        mentions=mentions or [],
        content=content,
    )


def test_contact_id_for_message():
    message = fake_message(author_id=42)
    assert discord_bot.contact_id_for_message(message) == "discord:42"


def test_state_paths_for_contact_are_isolated_per_user():
    paths = discord_bot.state_paths_for_contact("discord:42")
    assert str(paths["traj_file"]).endswith("state/discord/discord_42/trajectory.json")
    assert str(paths["chains_file"]).endswith("state/discord/discord_42/chains.json")
    assert str(paths["chains_dir"]).endswith("state/discord/discord_42/chains")


def test_handle_transport_command_wipes_contact_state(tmp_path, monkeypatch):
    monkeypatch.setattr(discord_bot, "STATE_ROOT", tmp_path / "state")
    contact_id = "discord:42"
    paths = discord_bot.state_paths_for_contact(contact_id)
    paths["traj_file"].parent.mkdir(parents=True, exist_ok=True)
    paths["traj_file"].write_text("[]")
    paths["chains_file"].write_text("{}")
    paths["chains_dir"].mkdir(parents=True, exist_ok=True)
    (paths["chains_dir"] / "abc.json").write_text("{}")

    assert discord_bot.handle_transport_command("/wipe", contact_id) == "trajectory wiped"
    assert not paths["traj_file"].exists()
    assert not paths["chains_file"].exists()
    assert not paths["chains_dir"].exists()


def test_should_respond_in_dm():
    message = fake_message(guild_id=None)
    client_user = SimpleNamespace(id=999)
    assert discord_bot.should_respond(message, client_user, True, set()) is True


def test_should_respond_requires_mention_in_guild():
    client_user = SimpleNamespace(id=999)
    message = fake_message(
        guild_id=123,
        mentions=[SimpleNamespace(id=999)],
    )
    assert discord_bot.should_respond(message, client_user, True, set()) is True


def test_should_not_respond_without_mention_when_required():
    client_user = SimpleNamespace(id=999)
    message = fake_message(guild_id=123, mentions=[])
    assert discord_bot.should_respond(message, client_user, True, set()) is False


def test_should_not_respond_outside_allowed_channel():
    client_user = SimpleNamespace(id=999)
    message = fake_message(guild_id=123, channel_id=55, mentions=[SimpleNamespace(id=999)])
    assert discord_bot.should_respond(message, client_user, True, {99}) is False


def test_strip_invocation_removes_bot_mention():
    assert discord_bot.strip_invocation("<@123> hello there", 123) == "hello there"
    assert discord_bot.strip_invocation("<@!123> hello there", 123) == "hello there"


def test_split_discord_message_prefers_boundaries():
    chunks = discord_bot.split_discord_message("a " * 1200, limit=100)
    assert len(chunks) > 1
    assert all(len(chunk) <= 100 for chunk in chunks)
