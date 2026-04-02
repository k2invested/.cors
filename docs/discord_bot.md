# discord_bot.py

[discord_bot.py](/Users/k2invested/Desktop/cors/discord_bot.py) is the Discord transport for the local step kernel.

It does not implement a second agent. It forwards Discord messages into [loop.py](/Users/k2invested/Desktop/cors/loop.py) by calling `run_turn(message, contact_id)`.

## Contact Identity

Each Discord author is mapped to a stable contact id:

- `discord:<user_id>`

That means the existing `on_contact:<id>` bootstrap and identity machinery works unchanged.

## Default Behavior

- DMs always receive a response.
- Guild messages receive a response by default.
- Turns are serialized through one async lock so the kernel does not race on `trajectory.json` or `chains.json`.

## Environment

- `.env`
  Optional. Both [discord_bot.py](/Users/k2invested/Desktop/cors/discord_bot.py) and [loop.py](/Users/k2invested/Desktop/cors/loop.py) now auto-load `/Users/k2invested/Desktop/cors/.env` if it exists.
  Existing shell env vars still win.

- `DISCORD_BOT_TOKEN`
  Required. The Discord bot token.

- `DISCORD_REQUIRE_MENTION`
  Optional. Defaults to false.
  Set to `1`, `true`, or `yes` to require a direct mention in guild channels.

- `DISCORD_ALLOWED_CHANNEL_IDS`
  Optional comma-separated allowlist for guild channels.
  Example: `12345,67890`

- `OPENAI_API_KEY`
  Required by the kernel itself.

## Run

```bash
python3 discord_bot.py
```

If you are using `.env`, put entries like this in `/Users/k2invested/Desktop/cors/.env`:

```bash
OPENAI_API_KEY=...
DISCORD_BOT_TOKEN=...
STITCH_API_KEY=...
EMAIL_SENDER=...
EMAIL_PASSWORD=...
EMAIL_RECIPIENT=...
```

## Intents

The bot enables:

- guilds
- messages
- message content

So the Discord application must also have the Message Content intent enabled in the developer portal.
