"""Dashboard web server for Hot Helper bot."""

import os
import json
import httpx
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from database import Database

# ── Config ────────────────────────────────────────────────────────────────────

CLIENT_ID     = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
SECRET_KEY    = os.getenv("DASHBOARD_SECRET_KEY", "fallback-change-this")
OWNER_ID      = int(os.getenv("OWNER_ID", "0"))
BASE_URL      = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000")
REDIRECT_URI  = f"{BASE_URL}/auth/callback"

DISCORD_API   = "https://discord.com/api/v10"
OAUTH_URL     = (
    f"https://discord.com/oauth2/authorize"
    f"?client_id={CLIENT_ID}"
    f"&redirect_uri={REDIRECT_URI}"
    f"&response_type=code"
    f"&scope=identify"
)

db         = Database()
serializer = URLSafeTimedSerializer(SECRET_KEY)
app        = FastAPI(docs_url=None, redoc_url=None)
templates  = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# ── Auth helpers ──────────────────────────────────────────────────────────────

def make_session(user_id: int) -> str:
    return serializer.dumps(str(user_id))

def read_session(token: str) -> int | None:
    try:
        uid = serializer.loads(token, max_age=86400)  # 24h
        return int(uid)
    except (BadSignature, SignatureExpired):
        return None

def get_current_user(request: Request) -> int | None:
    token = request.cookies.get("session")
    if not token:
        return None
    return read_session(token)

def require_owner(request: Request) -> int:
    uid = get_current_user(request)
    if uid != OWNER_ID:
        raise HTTPException(status_code=403, detail="Forbidden")
    return uid

# ── Auth routes ───────────────────────────────────────────────────────────────

@app.get("/login")
async def login():
    return RedirectResponse(OAUTH_URL)

@app.get("/auth/callback")
async def auth_callback(code: str = None, error: str = None):
    if error or not code:
        return RedirectResponse("/login?error=1")

    async with httpx.AsyncClient() as client:
        # Exchange code for token
        token_resp = await client.post(
            f"{DISCORD_API}/oauth2/token",
            data={
                "client_id":     CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type":    "authorization_code",
                "code":          code,
                "redirect_uri":  REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_resp.status_code != 200:
            return RedirectResponse("/login?error=1")

        access_token = token_resp.json().get("access_token")

        # Get user info
        user_resp = await client.get(
            f"{DISCORD_API}/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if user_resp.status_code != 200:
            return RedirectResponse("/login?error=1")

        user = user_resp.json()
        user_id = int(user["id"])

    if user_id != OWNER_ID:
        return HTMLResponse("<h2>Access denied. This dashboard is owner-only.</h2>", status_code=403)

    response = RedirectResponse("/dashboard")
    response.set_cookie("session", make_session(user_id), httponly=True, max_age=86400)
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse("/login")
    response.delete_cookie("session")
    return response

# ── Pages ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    uid = get_current_user(request)
    if uid == OWNER_ID:
        return RedirectResponse("/dashboard")
    return RedirectResponse("/login")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    return templates.TemplateResponse("login.html", {"request": request, "error": error})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, _=Depends(require_owner)):
    return templates.TemplateResponse("dashboard.html", {"request": request})

# ── API — Guild config ────────────────────────────────────────────────────────

@app.get("/api/guilds")
async def get_guilds(_=Depends(require_owner)):
    """List all configured guilds."""
    from config import DB_PATH
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT guild_id FROM config")
    rows = cursor.fetchall()
    conn.close()
    return [{"guild_id": r["guild_id"]} for r in rows]

@app.get("/api/guild/{guild_id}/config")
async def get_config(guild_id: int, _=Depends(require_owner)):
    config = db.get_guild_config(guild_id)
    if not config:
        raise HTTPException(status_code=404, detail="Guild not configured")
    return config

# ── API — Moderation ──────────────────────────────────────────────────────────

@app.get("/api/guild/{guild_id}/warnings/{user_id}")
async def get_warnings(guild_id: int, user_id: int, _=Depends(require_owner)):
    return db.get_warnings(user_id, guild_id)

@app.get("/api/guild/{guild_id}/modlogs/{user_id}")
async def get_modlogs(guild_id: int, user_id: int, _=Depends(require_owner)):
    return db.get_mod_logs(user_id, guild_id)

@app.get("/api/guild/{guild_id}/pending-mutes")
async def get_pending_mutes(guild_id: int, _=Depends(require_owner)):
    return db.get_pending_approvals(guild_id)

# ── API — XP & Leaderboard ────────────────────────────────────────────────────

@app.get("/api/guild/{guild_id}/leaderboard")
async def get_leaderboard(guild_id: int, page: int = 1, _=Depends(require_owner)):
    limit  = 10
    offset = (page - 1) * limit
    return db.get_leaderboard(guild_id, limit=limit, offset=offset)

@app.get("/api/guild/{guild_id}/xp/{user_id}")
async def get_user_xp(guild_id: int, user_id: int, _=Depends(require_owner)):
    data = db.get_user_xp(user_id, guild_id)
    if not data:
        raise HTTPException(status_code=404, detail="No XP data")
    return data

@app.post("/api/guild/{guild_id}/xp/{user_id}/reset")
async def reset_user_xp(guild_id: int, user_id: int, _=Depends(require_owner)):
    db.reset_xp(user_id, guild_id)
    return {"ok": True}

# ── API — QOTD ────────────────────────────────────────────────────────────────

@app.get("/api/qotd")
async def list_qotd(_=Depends(require_owner)):
    from config import DB_PATH
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM qotd ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/qotd")
async def add_qotd(request: Request, _=Depends(require_owner)):
    body = await request.json()
    question = body.get("question", "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question required")
    db.add_qotd(question)
    return {"ok": True}

@app.post("/api/qotd/reset")
async def reset_qotd(_=Depends(require_owner)):
    db.reset_qotd()
    return {"ok": True}

# ── API — Stats ───────────────────────────────────────────────────────────────

@app.get("/api/guild/{guild_id}/stats/{user_id}")
async def get_stats(guild_id: int, user_id: int, _=Depends(require_owner)):
    data = db.get_user_stats(user_id, guild_id)
    if not data:
        raise HTTPException(status_code=404, detail="No stats")
    return data

@app.get("/api/guild/{guild_id}/roles")
async def get_roles(guild_id: int, _=Depends(require_owner)):
    return db.get_custom_roles(guild_id)