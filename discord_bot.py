#!/usr/bin/env python3
"""Discord bridge for the cors step kernel."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any

from env_loader import load_env
from loop import run_turn


ROOT = Path(__file__).resolve().parent
BOT_LOG = ROOT / "bot.log"
MAX_DISCORD_MESSAGE = 1900
STATE_ROOT = ROOT / "state" / "discord"

load_env()


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _env_id_set(name: str) -> set[int]:
    raw = os.environ.get(name, "")
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            continue
    return ids


def contact_id_for_message(message: Any) -> str:
    return f"discord:{message.author.id}"


def _slug_contact_id(contact_id: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", contact_id.lower()).strip("_")
    return slug or "contact"


def state_paths_for_contact(contact_id: str) -> dict[str, Path]:
    base = STATE_ROOT / _slug_contact_id(contact_id)
    return {
        "traj_file": base / "trajectory.json",
        "chains_file": base / "chains.json",
        "chains_dir": base / "chains",
    }


def should_respond(message: Any, client_user: Any, require_mention: bool, allowed_channel_ids: set[int]) -> bool:
    if client_user is None or message.author.bot:
        return False
    if message.author.id == client_user.id:
        return False
    if getattr(message.guild, "id", None) is None:
        return True
    if allowed_channel_ids and message.channel.id not in allowed_channel_ids:
        return False
    if not require_mention:
        return True
    return any(getattr(user, "id", None) == client_user.id for user in getattr(message, "mentions", []))


def strip_invocation(content: str, bot_user_id: int | None) -> str:
    text = content.strip()
    if bot_user_id is not None:
        text = re.sub(rf"<@!?{bot_user_id}>", "", text).strip()
    return text


def split_discord_message(text: str, limit: int = MAX_DISCORD_MESSAGE) -> list[str]:
    text = text.strip()
    if not text:
        return [""]
    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit)
        if split_at <= 0:
            split_at = remaining.rfind(" ", 0, limit)
        if split_at <= 0:
            split_at = limit
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


def configure_logging() -> None:
    BOT_LOG.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(BOT_LOG), logging.StreamHandler()],
    )


def wipe_state_for_contact(contact_id: str) -> None:
    paths = state_paths_for_contact(contact_id)
    for key in ("traj_file", "chains_file"):
        path = paths[key]
        if path.exists():
            path.unlink()
    chains_dir = paths["chains_dir"]
    if chains_dir.exists():
        shutil.rmtree(chains_dir)


def handle_transport_command(prompt: str, contact_id: str) -> str | None:
    command = prompt.strip().lower()
    if command == "/wipe":
        wipe_state_for_contact(contact_id)
        return "trajectory wiped"
    return None


def build_client():
    import discord

    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.messages = True
    intents.guild_messages = True
    intents.dm_messages = True

    require_mention = _env_flag("DISCORD_REQUIRE_MENTION", False)
    allowed_channel_ids = _env_id_set("DISCORD_ALLOWED_CHANNEL_IDS")

    class CorsDiscordClient(discord.Client):
        def __init__(self):
            super().__init__(intents=intents)
            self.turn_lock = asyncio.Lock()
            self.require_mention = require_mention
            self.allowed_channel_ids = allowed_channel_ids

        async def on_ready(self):
            logging.info("Discord bot logged in as %s (%s)", self.user, getattr(self.user, "id", "?"))
            logging.info(
                "Discord bot config require_mention=%s allowed_channel_ids=%s",
                self.require_mention,
                sorted(self.allowed_channel_ids),
            )

        async def on_message(self, message):
            mentioned = any(getattr(user, "id", None) == getattr(self.user, "id", None) for user in getattr(message, "mentions", []))
            logging.info(
                "discord inbound author=%s bot=%s guild=%s channel=%s mentioned=%s content_len=%s",
                getattr(message.author, "id", None),
                getattr(message.author, "bot", None),
                getattr(message.guild, "id", None) if getattr(message, "guild", None) else None,
                getattr(message.channel, "id", None),
                mentioned,
                len(message.content or ""),
            )

            if not should_respond(message, self.user, self.require_mention, self.allowed_channel_ids):
                logging.info(
                    "discord inbound ignored author=%s guild=%s channel=%s mentioned=%s require_mention=%s allowed_channel_ids=%s",
                    getattr(message.author, "id", None),
                    getattr(message.guild, "id", None) if getattr(message, "guild", None) else None,
                    getattr(message.channel, "id", None),
                    mentioned,
                    self.require_mention,
                    sorted(self.allowed_channel_ids),
                )
                return

            prompt = strip_invocation(message.content or "", getattr(self.user, "id", None))
            if not prompt:
                logging.info("discord inbound ignored empty prompt after mention stripping")
                return

            contact_id = contact_id_for_message(message)
            command_response = handle_transport_command(prompt, contact_id)
            if command_response is not None:
                logging.info("discord transport command command=%r", prompt)
                await message.channel.send(command_response)
                return

            logging.info(
                "discord turn start user=%s channel=%s guild=%s content=%r",
                contact_id,
                getattr(message.channel, "id", None),
                getattr(message.guild, "id", None),
                prompt[:200],
            )

            try:
                async with self.turn_lock:
                    async with message.channel.typing():
                        response = await asyncio.to_thread(
                            run_turn,
                            prompt,
                            contact_id,
                            **state_paths_for_contact(contact_id),
                        )
            except Exception:
                logging.exception("discord turn failed for %s", contact_id)
                await message.channel.send("The turn failed. Check bot.log.")
                return

            for chunk in split_discord_message(response):
                await message.channel.send(chunk)

    return CorsDiscordClient()


def main() -> None:
    configure_logging()
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        raise SystemExit("Missing DISCORD_BOT_TOKEN")
    client = build_client()
    client.run(token)


if __name__ == "__main__":
    main()
