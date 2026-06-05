# Telegram onboarding-flow bot

A small, config-driven funnel bot. The logic lives in `bot.py` (you rarely touch it).
Your entire funnel — every message, image, video note, button, and branch — is
defined as plain data in `flow_config.py`.

## Setup

1. **Create the bot:** message [@BotFather](https://t.me/BotFather) → `/newbot` →
   copy the token it gives you.

2. **Install:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Add your token:**
   ```bash
   export TELEGRAM_TOKEN="123456:ABC..."        # macOS/Linux
   setx TELEGRAM_TOKEN "123456:ABC..."          # Windows (new shell after)
   ```

4. **Add media:** create a `media/` folder next to `bot.py` and drop in the files
   your flow references (e.g. `intro.mp4`, `rundown.png`). Missing files won't
   crash the bot — it sends a placeholder and logs a warning, so you can wire
   media in later.

5. **Run:**
   ```bash
   python bot.py
   ```
   Open your bot in Telegram and send `/start`.

## Editing the funnel

Everything is in `flow_config.py`. Each step is a dict with a unique `id`.

| type         | fields                                   | what it does                       |
|--------------|------------------------------------------|------------------------------------|
| `message`    | `text`, `delay?`                         | auto-sends text                    |
| `photo`      | `file`, `caption?`, `delay?`             | sends an image from `media/`       |
| `video_note` | `file`, `delay?`                         | sends a round video from `media/`  |
| `input`      | `prompt`, `save_as`, `validate?`, `delay?` | stops and captures a typed reply |
| `buttons`    | `text`, `options:[{label, goto}]`        | inline menu that branches          |
| `goto`       | `target`                                 | jumps to another step `id`         |

- Use `{placeholders}` in any text to insert captured values, e.g. `{full_name}`.
- `validate` currently supports `"email"`.
- Branches rejoin by pointing a `goto` at a shared step `id` (see how the sample
  flow loops "How does it work?" back to the menu, and sends both experience
  branches to `wrap_up`).

## Where leads go

Captured name/email (and which buttons were tapped) are written to `leads.db`
(SQLite) after each input. Inspect them with any SQLite browser or:

```bash
sqlite3 leads.db "SELECT username, data, updated_at FROM leads;"
```

## Scaling notes

- For low traffic, `run_polling()` on a cheap always-on box (Railway, Fly.io, a
  small VPS) is the easiest path.
- For serverless, switch to webhooks — the flow engine stays identical, only the
  entry point in `bot.py` changes.
- Per-user state currently lives in memory (`context.user_data`), so a restart
  resets anyone mid-flow. For production, back it with PTB's `PicklePersistence`
  or move state into the database.
