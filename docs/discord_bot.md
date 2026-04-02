# Discord Bot

`discord_bot.py` is a thin transport over `loop.run_turn()`.

Behavior:
- DMs always respond
- Guild messages respond by default unless `DISCORD_REQUIRE_MENTION=1`
- Discord state is isolated per contact under `state/discord/<contact>/`
- `/wipe` clears only that Discord contact's isolated state

Required env:
- `DISCORD_BOT_TOKEN`
- `OPENAI_API_KEY`

The bot auto-loads env values from:
1. `cors/.env`
2. `../KernelAgent/.env`
3. `../.env`

Run:

```bash
source .venv/bin/activate
python discord_bot.py
```

Optional env:
- `DISCORD_REQUIRE_MENTION=1`
- `DISCORD_ALLOWED_CHANNEL_IDS=123,456`
