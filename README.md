# GuardianTG

🛡 Advanced Telegram Group Security Bot

Auto-moderation for Telegram groups: anti-spam, anti-link, anti-flood, anti-raid
lockdowns, CAPTCHA verification gates, anti-bot protection and a live web
dashboard.

## Features

- 🛡 **Anti-Spam** — heuristic spam scoring with configurable actions
- 🔗 **Anti-Link** — domain allow-list / block-list with instant parsing
- 💥 **Anti-Raid** — join-rate detection triggers automatic lockdown
- 🧪 **CAPTCHA gate** — new members verify before they can post
- 🤖 **Anti-Bot** — auto-kick untrusted bot accounts
- 🌊 **Anti-Flood** — per-user rate limiting (warn / delete / mute / kick / ban)
- ⚖️ **Moderation** — warn, mute, ban, kick, purge + event logs
- 📊 **Web dashboard** — live stats, logs and registered groups

## Local setup

```bash
cp .env.example .env   # fill in BOT_TOKEN, MONGO_URI, REDIS_URL, OWNER_ID
python -m venv .venv
.venv/Scripts/activate      # Windows
pip install -r requirements.txt
python -m app.main
```

The web dashboard (optional, `WEB_DASHBOARD_ENABLED=true`) runs on
`http://localhost:8000`. Login with the admin email/password set via
`WEB_ADMIN_EMAIL` and `WEB_ADMIN_PASSWORD` (defaults:
`abhisheekmondal927@gmail.com` / `abhisheek2006`).

## Deploy the web dashboard to Vercel

The dashboard is ready for Vercel. Vercel auto-detects the FastAPI app via the
`fastapi` dependency and loads it from `app.web.main:app`, which is declared in
`pyproject.toml` under `[tool.vercel] entrypoint`. All routes are served by
this single function.

1. Push this repository to GitHub.
2. On Vercel, **Import Project** → select the repo → framework **Python** (auto-detected).
3. Add environment variables in Project Settings → Environment Variables:
   - `WEB_SECRET` (any long random string, used to sign session cookies)
   - `WEB_ADMIN_EMAIL` (defaults to `abhisheekmondal927@gmail.com`)
   - `WEB_ADMIN_PASSWORD` (defaults to `abhisheek2006`)
   - `MONGO_URI` (optional — dashboard shows live data when set)
4. Deploy. The public landing page is at `/`, the admin dashboard at `/dashboard`.

> The Telegram bot itself needs a long-running process (VPS / Railway / Fly.io).
> Vercel hosts the web dashboard, not the bot worker.