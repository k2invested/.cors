# Discord Bot

[discord_bot.py](/Users/k2invested/Desktop/cors/discord_bot.py) is the Discord transport over `loop.run_turn()`.

## Core Behavior

- DMs always respond.
- Guild messages respond unless `DISCORD_REQUIRE_MENTION=1`.
- `DISCORD_ALLOWED_CHANNEL_IDS` can restrict which guild channels are serviced.
- state is isolated per Discord contact under `state/discord/<contact>/`
- `/wipe` clears only that contact’s isolated trajectory/chains state

## Turn Flow

For each inbound message the bot:

1. checks channel / mention policy
2. strips invocation markup
3. captures prior trajectory step count
4. runs `loop.run_turn(...)`
5. sends the synthesized response back to the source channel
6. scans newly added trajectory steps for assessment-bearing postconditions
7. forwards diff notifications to production destinations

## Diff Routing

The bot now forwards postcondition assessments to a production surface.

Current behavior:

- any new step with `assessment` lines becomes a diff notification candidate
- destination channels/threads are selected by:
  - channel/thread name `production`
  - or IDs in `DISCORD_DIFF_CHANNEL_IDS`
- the payload format starts with:

```text
diff notification for <contact_id>
```

This is how `.st` persistence assessments now surface into Discord.

## Required Environment

- `DISCORD_BOT_TOKEN`
- `OPENAI_API_KEY`

The bot auto-loads env values from:

1. `cors/.env`
2. `../KernelAgent/.env`
3. `../.env`

## Optional Environment

- `DISCORD_REQUIRE_MENTION=1`
- `DISCORD_ALLOWED_CHANNEL_IDS=123,456`
- `DISCORD_DIFF_CHANNEL_IDS=123,456`

## Run

```bash
source .venv/bin/activate
python discord_bot.py
```
