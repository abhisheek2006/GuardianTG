from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import uvicorn
from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from motor.core import AgnosticDatabase

from app.core.config import get_settings
from app.database import session as db_session

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI(title="GuardianTG Dashboard", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=TEMPLATES_DIR)

COOKIE_NAME = "guardiantg_session"
SESSION_TTL = 86400  # 1 day


# ── Auth ─────────────────────────────────────────────────────────────
def _sign(payload: str) -> str:
    secret = get_settings().web_secret.encode()
    return hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()


def create_session_token(user_id: int) -> str:
    body = f"{user_id}.{int(time.time()) + SESSION_TTL}"
    return f"{body}.{_sign(body)}"


def verify_session_token(token: str) -> bool:
    try:
        body, sig = token.rsplit(".", 1)
        if not hmac.compare_digest(_sign(body), sig):
            return False
        _, expires = body.split(".")
        return int(expires) > time.time()
    except Exception:
        return False


def is_authenticated(token: Optional[str]) -> bool:
    return bool(token) and verify_session_token(token)


async def _try_db() -> Optional[AgnosticDatabase]:
    """Return a connected database or None when unavailable (serverless-safe)."""
    try:
        return db_session.get_db()
    except RuntimeError:
        pass
    try:
        return await db_session.connect()
    except Exception:
        return None


_EMPTY_STATS = {
    "messages_scanned": 0,
    "spam_blocked": 0,
    "links_blocked": 0,
    "users_muted": 0,
    "users_banned": 0,
    "captchas_passed": 0,
    "raids_prevented": 0,
    "users": 0,
    "chats": 0,
}


async def _global_stats() -> dict:
    db = await _try_db()
    if db is None:
        return dict(_EMPTY_STATS)

    from app.database.repositories import actions as action_repo
    from app.database.repositories import logs as log_repo
    from app.database.repositories import users as user_repo

    since = datetime.now(timezone.utc) - timedelta(days=7)
    try:
        events = await log_repo.global_event_counts(db, since)
        actions = await action_repo.total_action_counts(db)
        return {
            "messages_scanned": await log_repo.count_logs(db),
            "spam_blocked": events.get("spam_detected", 0),
            "links_blocked": events.get("link_blocked", 0),
            "users_muted": actions.get("mute", 0),
            "users_banned": actions.get("ban", 0) + actions.get("kick", 0),
            "captchas_passed": events.get("captcha_passed", 0),
            "raids_prevented": events.get("raid_detected", 0),
            "users": await user_repo.count_users(db),
            "chats": await log_repo.count_chats(db),
        }
    except Exception:
        return dict(_EMPTY_STATS)


# ── Auth dependency helpers ──────────────────────────────────────────
async def _check(request: Request) -> Optional[Response]:
    token = request.cookies.get(COOKIE_NAME)
    if not is_authenticated(token):
        return RedirectResponse("/login", status_code=303)
    return None


# ── Public landing page ──────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return templates.TemplateResponse(
        "landing.html",
        {
            "request": request,
            "name": get_settings().bot_name,
            "tagline": get_settings().bot_tagline,
            "authed": is_authenticated(request.cookies.get(COOKIE_NAME)),
        },
    )


# ── Auth ─────────────────────────────────────────────────────────────
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
async def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    settings = get_settings()
    if (
        email.strip().lower() != settings.web_admin_email.strip().lower()
        or not hmac.compare_digest(password, settings.web_admin_password)
    ):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Wrong email or password."},
        )

    response = RedirectResponse("/dashboard", status_code=303)
    token = create_session_token(0)
    response.set_cookie(
        COOKIE_NAME, token, max_age=SESSION_TTL, httponly=True, samesite="lax"
    )
    return response


@app.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


# ── Dashboard pages ──────────────────────────────────────────────────
@app.get("/dashboard", response_class=HTMLResponse)
async def overview(request: Request):
    denied = await _check(request)
    if denied:
        return denied
    stats = await _global_stats()
    return templates.TemplateResponse("index.html", {"request": request, "stats": stats})


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request, limit: int = 100):
    denied = await _check(request)
    if denied:
        return denied
    db = await _try_db()
    entries = []
    if db is not None:
        cursor = db.logs.find({}).sort("created_at", -1).limit(min(limit, 500))
        entries = await cursor.to_list(length=min(limit, 500))
    return templates.TemplateResponse("logs.html", {"request": request, "entries": entries})


@app.get("/chats", response_class=HTMLResponse)
async def chats_page(request: Request):
    denied = await _check(request)
    if denied:
        return denied
    db = await _try_db()
    chats = []
    if db is not None:
        cursor = db.chats.find({}).sort("created_at", -1).limit(500)
        chats = await cursor.to_list(length=500)
    return templates.TemplateResponse("chats.html", {"request": request, "chats": chats})


@app.get("/healthz")
async def healthz():
    return {
        "ok": True,
        "web": "online",
        "database": (await _try_db()) is not None,
    }


async def start_web() -> None:
    settings = get_settings()
    config = uvicorn.Config(
        app,
        host=settings.web_host,
        port=settings.web_port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    await server.serve()