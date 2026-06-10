# New Bot Setup Guide

Clone this repo and follow these steps to spin up a second independent instance.

---

## 1. Clone & open

```bash
git clone https://github.com/JayBonham/TRADEVAULT.git <your-new-folder-name>
cd <your-new-folder-name>
```

Then open that folder in VS Code.

---

## 2. Create a new GitHub repo

Push the cloned code to a new repo so Vercel treats it as a separate project:

```bash
git remote set-url origin https://github.com/<your-username>/<new-repo-name>.git
git push -u origin main
```

---

## 3. Create a new Telegram bot

1. Open Telegram and message **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the **bot token** it gives you — you'll need it below

---

## 4. Set up a Neon database

1. Go to [neon.tech](https://neon.tech) and create a free project
2. Copy the **connection string** (starts with `postgresql://...`)
3. Run the schema once to create the tables:

```bash
pip install psycopg2-binary
python -c "
import psycopg2, os
conn = psycopg2.connect('<YOUR_DATABASE_URL>')
cur = conn.cursor()
cur.execute('''
  CREATE TABLE IF NOT EXISTS leads (
    chat_id BIGINT PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    email TEXT,
    choices JSONB DEFAULT '[]',
    state JSONB DEFAULT '{}',
    done BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
  );
  CREATE TABLE IF NOT EXISTS flow_config (
    id INT PRIMARY KEY DEFAULT 1,
    flow JSONB NOT NULL DEFAULT '[]'
  );
  INSERT INTO flow_config (id, flow) VALUES (1, '[]') ON CONFLICT DO NOTHING;
''')
conn.commit()
conn.close()
print('Done')
"
```

---

## 5. Deploy to Vercel

1. Go to [vercel.com](https://vercel.com) → **Add New Project** → import your new GitHub repo
2. Under **Environment Variables**, add all four of these:

| Variable | Value |
|---|---|
| `TELEGRAM_TOKEN` | Token from BotFather (step 3) |
| `DATABASE_URL` | Neon connection string (step 4) |
| `DASHBOARD_TOKEN` | Any password you choose for the /dashboard page |
| `WEBHOOK_SECRET` | Any random string (e.g. `openssl rand -hex 16`) |

3. Deploy. Copy your **Vercel domain** (e.g. `your-project.vercel.app`)

---

## 6. Register the Telegram webhook

Run this once after deploying — replace the values with yours:

```bash
curl "https://api.telegram.org/bot<TELEGRAM_TOKEN>/setWebhook?url=https://<your-vercel-domain>/api/telegram&secret_token=<WEBHOOK_SECRET>"
```

You should get `{"ok":true,"result":true}` back.

---

## 7. Customise the landing page

In `public/app.js`, update the `CONFIG` block at the top:

```js
const CONFIG = {
  ctaUrl: 'https://t.me/+YOUR_NEW_TELEGRAM_GROUP_LINK',  // ← swap this
  stats: [
    [1200, '+'],   // signals sent — replace with real number
    [84,   '%'],   // win rate — replace with real number or remove
    [5000, '+'],   // telegram members — replace with real number
    [4,    '']     // markets covered
  ],
};
```

---

## 8. Access the dashboard

Go to `https://<your-vercel-domain>/dashboard` and enter your `DASHBOARD_TOKEN` password.

---

## Summary of what's unique per instance

| Thing | Where to change |
|---|---|
| Telegram bot token | Vercel env var `TELEGRAM_TOKEN` |
| Database | Vercel env var `DATABASE_URL` |
| Dashboard password | Vercel env var `DASHBOARD_TOKEN` |
| Webhook secret | Vercel env var `WEBHOOK_SECRET` + curl command in step 6 |
| CTA / Telegram group link | `public/app.js` → `CONFIG.ctaUrl` |
| Landing page stats | `public/app.js` → `CONFIG.stats` |
| Bot flow/messages | Dashboard → Flow Builder (no code needed) |
