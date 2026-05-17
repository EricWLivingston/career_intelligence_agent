# Production Transition Plan — Career Intelligence Agent

> **Goal:** Move from a local CLI app (`main.py`) to a production system with a mobile-accessible frontend.
>
> **Current stack:** Python + Deep Agents (LangGraph) + Google APIs + JSearch + uv  
> **Current state:** Single-user, local only, in-memory state, no server layer

---

## Table of Contents

1. [What Needs to Change and Why](#1-what-needs-to-change-and-why)
2. [Backend API Layer (required for all options)](#2-backend-api-layer)
3. [Persistence (required for all options)](#3-persistence)
4. [Authentication & Secrets](#4-authentication--secrets)
5. [Frontend Options](#5-frontend-options)
6. [Deployment Options](#6-deployment-options)
7. [Recommended Path](#7-recommended-path)
8. [Step-by-Step Implementation Order](#8-step-by-step-implementation-order)

---
1
## 1. What Needs to Change and Why

The table below maps every current limitation to the production requirement that addresses it.

| Current State | Problem | What's Needed |
|---|---|---|
| `input()` loop in `main.py` | Only works in a terminal | HTTP API server (FastAPI) |
| `MemorySaver` (in-process RAM) | Conversation state is lost on restart | Persistent checkpointer (PostgreSQL) |
| `.env` file on local disk | Can't deploy without copying secrets manually | Secret manager or env vars on host |
| Gmail OAuth runs a local browser window | Breaks in any server environment | Pre-generated refresh token stored as a secret |
| `service_account.json` on local disk | Same as above — can't be on a server safely | Service account JSON stored as a secret |
| No authentication | Anyone who hits the server can use it | At minimum, a static API key or full user auth |
| Single thread ID (`career-session-1`) | No multi-session or multi-user support | Dynamic thread IDs per session |

Nothing about your **agent logic**, **subagents**, **tools**, or **prompts** needs to change. The work is almost entirely infrastructure around them.

---

## 2. Backend API Layer

The CLI loop in `main.py` needs to become an HTTP endpoint so the frontend can talk to it.

### Why FastAPI

- Already Python — no context switch from your existing codebase
- Native `async` support lets you stream agent tokens to the client
- Automatic OpenAPI docs (useful during development)
- Works with `uv` and your existing `pyproject.toml`

### What the API looks like

```
POST /chat
Body: { "message": "Find me hardware jobs in San Diego", "thread_id": "user-abc-session-1" }
Response: Server-Sent Events stream of agent tokens
  → data: {"token": "Looking"}
  → data: {"token": " for"}
  → data: {"done": true, "full_response": "..."}

GET /health
Response: { "status": "ok" }
```

### Minimal server structure

```
career_intelligence_agent/
  api/
    __init__.py
    server.py        ← FastAPI app, /chat and /health endpoints
    auth.py          ← API key middleware
    models.py        ← Pydantic request/response models
  main.py            ← unchanged (still works as CLI)
  lib/               ← unchanged
```

### Core server.py pattern

```python
from fastapi import FastAPI, Depends
from fastapi.responses import StreamingResponse
from main import build_agents
import asyncio, json

app = FastAPI()
agent = build_agents()  # built once at startup

@app.post("/chat")
async def chat(body: ChatRequest):
    config = {"configurable": {"thread_id": body.thread_id}}

    async def token_stream():
        for chunk in agent.stream(
            {"messages": [{"role": "user", "content": body.message}]},
            config=config,
            stream_mode="messages",
        ):
            yield f"data: {json.dumps({'token': chunk})}\n\n"
        yield "data: {\"done\": true}\n\n"

    return StreamingResponse(token_stream(), media_type="text/event-stream")
```

> **Add to `pyproject.toml` dependencies:** `fastapi`, `uvicorn[standard]`

---

## 3. Persistence

`MemorySaver` holds conversation history in RAM. When the server restarts, all context is gone. For production you need a persistent checkpointer.

### Option A — PostgreSQL (recommended)

LangGraph ships a first-party PostgreSQL checkpointer: `langgraph-checkpoint-postgres`.

**How it works:** Every graph state snapshot (messages, subagent outputs, tool results) is written to a Postgres table. On the next invocation with the same `thread_id`, the graph rehydrates from the DB.

```python
# replaces MemorySaver() in main.py / build_agents()
from langgraph.checkpoint.postgres import PostgresSaver

checkpointer = PostgresSaver.from_conn_string(os.environ["DATABASE_URL"])
checkpointer.setup()  # creates tables on first run
```

**Pros:** Battle-tested, queryable, works with any Postgres host (Railway, Supabase, Render, RDS)  
**Cons:** Requires a Postgres instance — adds ~$5–10/month if not already on a platform that includes it

### Option B — SQLite (simpler, single-user only)

```python
from langgraph.checkpoint.sqlite import SqliteSaver

checkpointer = SqliteSaver.from_conn_string("./state.db")
```

**Pros:** Zero infrastructure, just a file  
**Cons:** Does not work if you ever run multiple server processes (e.g., Gunicorn with 2 workers); fine for a single-process deploy on Railway/Render

### Option C — Redis

`langgraph-checkpoint-redis` exists but is less commonly used. Best if you're already using Redis for caching. Not worth adding just for checkpointing.

**Recommendation:** Start with SQLite to ship fast. Migrate to PostgreSQL when you need multi-process or multi-user support.

---

## 4. Authentication & Secrets

### API Authentication (who can call your server)

Since this is a personal tool, full OAuth is overkill. A static API key passed in the `Authorization` header is sufficient.

```python
# api/auth.py
from fastapi import Header, HTTPException
import os

async def verify_key(x_api_key: str = Header(...)):
    if x_api_key != os.environ["APP_API_KEY"]:
        raise HTTPException(status_code=401)
```

Every request from your frontend includes `X-Api-Key: <your_secret>` in the header. The secret lives in your hosting platform's environment variables — never in code.

If you later want proper user accounts (login/signup), the cleanest drop-in is **Clerk** (free tier covers personal projects). It handles mobile OAuth, JWTs, and session management. Your FastAPI server validates the JWT instead of a static key.

### Google Service Account (Sheets + Docs)

Currently `service_account.json` is a file on disk. On a server, store the entire JSON as a single environment variable:

```bash
# In your hosting platform's env var config:
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"..."}
```

```python
# In lib/tools.py, replace _get_creds():
import json, os
from google.oauth2.service_account import Credentials

def _get_creds():
    info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    return Credentials.from_service_account_info(info, scopes=_SA_SCOPES)
```

### Gmail OAuth (the tricky one)

The current flow opens a browser window (`flow.run_local_server()`), which **will not work on a server**. The fix is to pre-generate the token locally and store it as a secret.

**One-time setup:**
1. Run the current flow locally once more to produce a fresh `gmail_token.json`
2. Copy its contents into a `GMAIL_TOKEN_JSON` environment variable on your host
3. Update `_get_gmail_creds()` to read from that env var instead of a file:

```python
def _get_gmail_creds():
    
    token_json = os.environ.get("GMAIL_TOKEN_JSON")
    if token_json:
        creds = OAuthCredentials.from_authorized_user_info(
            json.loads(token_json), _GMAIL_SCOPES
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return creds
    # fallback: file-based (local dev only)
    ...existing file logic...
```

The Gmail refresh token is long-lived (~6 months without use, effectively forever if used regularly). The server auto-refreshes access tokens without any browser interaction.

---

## 5. Frontend Options

All options below are mobile-accessible. They vary in build time, customization, and UX quality.

---

### Option A — Chainlit (fastest to ship, ~1–2 days)

[Chainlit](https://chainlit.io) is a Python library that wraps your agent in a production-ready chat UI. You write ~50 lines of Python and get a chat interface that works on desktop and mobile browsers.

**What you get out of the box:**
- Streaming message display (tokens appear as they're generated)
- Message history with collapsible tool call details
- File upload support
- Mobile-responsive by default
- Built-in user session management

**How it integrates:**

```python
# chainlit_app.py
import chainlit as cl
from main import build_agents

agent = build_agents()

@cl.on_message
async def handle(message: cl.Message):
    thread_id = cl.user_session.get("thread_id")
    config = {"configurable": {"thread_id": thread_id}}

    msg = cl.Message(content="")
    await msg.send()

    async for chunk in agent.astream(
        {"messages": [{"role": "user", "content": message.content}]},
        config=config,
        stream_mode="messages",
    ):
        await msg.stream_token(chunk)
    await msg.update()
```

**Pros:** Fastest path to a working mobile UI, zero JavaScript, integrates directly with LangGraph  
**Cons:** Limited UI customization (it looks like Chainlit, not your own brand); hosted on your domain but not a native app

**Add to dependencies:** `chainlit`

---

### Option B — Progressive Web App with Next.js (2–4 weeks, best long-term)

A PWA is a web app that behaves like a native app on mobile: it can be added to the home screen, works offline (partially), and receives push notifications. This is the production-grade path.

**Architecture:**

```
[Mobile Browser / Home Screen PWA]
        ↓ HTTPS + SSE
[Next.js frontend on Vercel]
        ↓ HTTPS
[FastAPI backend (Railway/Fly.io)]
        ↓
[Deep Agents / LangGraph + Google APIs]
```

**Frontend stack:**
- Next.js 14 (App Router) — React framework with SSR and easy Vercel deploy
- `shadcn/ui` — component library, mobile-responsive out of the box
- `EventSource` API — native browser SSE client for streaming agent responses
- `next-pwa` — adds PWA manifest and service worker in ~5 lines of config

**Key UI components to build:**
1. `ChatThread` — scrollable message list, auto-scrolls to bottom, renders markdown
2. `MessageInput` — sticky bottom input with send button (thumb-friendly)
3. `ThreadSidebar` — list of past conversations (fetched from your `/threads` endpoint)
4. `ToolCallAccordion` — collapsed view of tool calls (e.g., "Searched JSearch for hardware jobs in SD")

**Pros:** Full control over design; native-app feel on mobile; can add push notifications; scales to multi-user  
**Cons:** Requires building a React frontend; most work of any option here

---

### Option C — Streamlit (2–3 days, good middle ground)

Streamlit is a Python-only framework for building data apps. It's less polished than a custom PWA but significantly more customizable than Chainlit and requires no JavaScript.

```python
# app.py
import streamlit as st
from main import build_agents

st.set_page_config(page_title="Career Intelligence Agent", layout="wide")
agent = build_agents()

if "thread_id" not in st.session_state:
    st.session_state.thread_id = "session-" + str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

if prompt := st.chat_input("Ask your career agent..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            result = agent.invoke({"messages": [{"role": "user", "content": prompt}]}, config=config)
            response = result["messages"][-1].content
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.chat_message("assistant").write(response)
```

Deploy on Streamlit Community Cloud (free) or alongside your FastAPI server.

**Pros:** Pure Python, fast to build, Streamlit Community Cloud is free  
**Cons:** No token streaming (response appears all at once); Streamlit's mobile UX is functional but not native-feeling; refresh resets UI state unless you're careful

---

### Option D — Telegram Bot (1 day, no frontend to build)

Skip the frontend entirely. Wrap your agent as a Telegram bot. The Telegram app is already installed on most phones and has an excellent mobile UX.

```python
# telegram_bot.py
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters
from main import build_agents

agent = build_agents()

async def handle_message(update: Update, context):
    thread_id = f"tg-{update.effective_chat.id}"
    config = {"configurable": {"thread_id": thread_id}}
    result = agent.invoke(
        {"messages": [{"role": "user", "content": update.message.text}]},
        config=config,
    )
    await update.message.reply_text(result["messages"][-1].content)

app = ApplicationBuilder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
app.add_handler(MessageHandler(filters.TEXT, handle_message))
app.run_polling()
```

Get a bot token from `@BotFather` on Telegram in ~2 minutes.

**Pros:** Fastest possible path to mobile; no frontend code; Telegram handles auth, push notifications, file sharing; free  
**Cons:** You're locked into Telegram's UX; no custom branding; Telegram must be installed on the user's phone

**Add to dependencies:** `python-telegram-bot`

---

## 6. Deployment Options

Once you have an API server, you need to host it. These are ranked by simplicity.

### Option A — Railway (recommended for most cases)

Railway is a PaaS (like Heroku). You connect your GitHub repo and it builds and deploys automatically on every push.

**What it handles for you:** Build (detects Python/uv), environment variables (secrets UI), PostgreSQL add-on, HTTPS domain, logs.

**Cost:** ~$5/month for a hobby project (includes 512MB RAM, 1 vCPU, and a Postgres database)

**Setup:**
1. Push your repo to GitHub (private repo is fine)
2. Create a new Railway project → "Deploy from GitHub repo"
3. Add your env vars in the Railway dashboard (no `.env` file needed)
4. Set the start command: `uvicorn api.server:app --host 0.0.0.0 --port $PORT`
5. Railway gives you a `*.railway.app` HTTPS URL immediately

### Option B — Render

Nearly identical to Railway. Slightly more generous free tier but cold starts on the free plan (the server sleeps after 15 minutes of inactivity and takes ~30 seconds to wake up). Fine for personal use.

**Cost:** Free tier available; $7/month for always-on

### Option C — Fly.io

Docker-based deploy. More control than Railway, slightly more setup. Great if you want to run your app in a specific region (e.g., close to your Google API data).

**Cost:** Free tier (3 shared-CPU VMs), then ~$3–5/month

```bash
# One-time setup
fly launch         # creates Dockerfile and fly.toml
fly secrets set ANTHROPIC_API_KEY=... JSEARCH_API_KEY=...
fly deploy
```

### Option D — Google Cloud Run (serverless, scales to zero)

Run your container only when requests come in. Costs nearly zero for low-traffic personal apps.

**Pros:** Pay-per-request (effectively free for personal use), scales to thousands of users automatically  
**Cons:** Cold starts (~2–5 seconds if the container hasn't been called recently); more initial setup than Railway

```bash
gcloud run deploy career-agent \
  --source . \
  --set-env-vars ANTHROPIC_API_KEY=... \
  --region us-central1 \
  --allow-unauthenticated
```

---

## 7. Recommended Path

Based on your stack and goals, here are two concrete paths:

### Path 1 — Ship fast (1–3 days total)

Best if you want something working on your phone this week.

| Layer | Choice | Why |
|---|---|---|
| Frontend | Chainlit | Zero JS, integrates with LangGraph natively, mobile-responsive |
| Backend | FastAPI + Chainlit server | Chainlit runs its own server, FastAPI optional |
| Persistence | SQLite (`langgraph-checkpoint-sqlite`) | No infra to set up |
| Deploy | Railway | One command, auto-deploy from GitHub |
| Auth | Static `APP_API_KEY` header | Personal tool, no need for user accounts |

**Total new code:** ~100 lines of Python (Chainlit app + tweaks to `_get_creds()`)

### Path 2 — Production-grade (2–4 weeks)

Best if you want a polished mobile experience or plan to share with others.

| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js PWA | Full control, native-app feel on mobile, offline support |
| Backend | FastAPI with SSE streaming | Python-native, streaming support, clean API design |
| Persistence | PostgreSQL (`langgraph-checkpoint-postgres`) | Durable, queryable, scales to multi-user |
| Deploy | Railway (backend) + Vercel (frontend) | Both have GitHub auto-deploy, free SSL |
| Auth | Clerk (free tier) | Handles login, sessions, JWTs, mobile OAuth |

---

## 8. Step-by-Step Implementation Order

Work in this order regardless of which path you choose. Each step is independently deployable and testable.

### Phase 1 — Decouple secrets from the filesystem (1–2 hours)

These changes are required before any deployment and have no effect on local behavior.

- [ ] **1.1** Add `GOOGLE_SERVICE_ACCOUNT_JSON` env var support to `_get_creds()` in `lib/tools.py`
- [ ] **1.2** Add `GMAIL_TOKEN_JSON` env var support to `_get_gmail_creds()` in `lib/tools.py`
- [ ] **1.3** Generate a fresh `gmail_token.json` locally, copy its contents into `.env` as `GMAIL_TOKEN_JSON`
- [ ] **1.4** Test locally with the env var versions to confirm they work
- [ ] **1.5** Add `service_account.json`, `gmail_token.json`, `gmail_credentials.json`, `.env` to `.gitignore`

### Phase 2 — Add persistent checkpointer (30 minutes)

- [ ] **2.1** Add `langgraph-checkpoint-sqlite` to `pyproject.toml`
- [ ] **2.2** In `main.py`, replace `MemorySaver()` with `SqliteSaver.from_conn_string("./state.db")`
- [ ] **2.3** Test: start the CLI, send a message, restart, send another message — confirm prior context is remembered

### Phase 3 — Build the API server (2–4 hours)

- [ ] **3.1** Add `fastapi` and `uvicorn[standard]` to `pyproject.toml`
- [ ] **3.2** Create `api/server.py` with `POST /chat` (SSE stream) and `GET /health`
- [ ] **3.3** Create `api/auth.py` with static API key middleware
- [ ] **3.4** Test locally: `uvicorn api.server:app --reload`, then `curl -X POST http://localhost:8000/chat ...`

### Phase 4 — Build the frontend (varies by option)

**Path 1 (Chainlit):**
- [ ] **4.1** Add `chainlit` to `pyproject.toml`
- [ ] **4.2** Create `chainlit_app.py` (see Option A code above)
- [ ] **4.3** Run `chainlit run chainlit_app.py` and test on your phone's browser (connect to your laptop's IP on the local network)

**Path 2 (Next.js PWA):**
- [ ] **4.1** `npx create-next-app@latest frontend --typescript --tailwind --app`
- [ ] **4.2** Install `shadcn/ui`: `npx shadcn@latest init`
- [ ] **4.3** Build `ChatThread` and `MessageInput` components
- [ ] **4.4** Implement SSE client to stream from your FastAPI backend
- [ ] **4.5** Add `next-pwa`, configure `manifest.json` with app name and icon
- [ ] **4.6** Test "Add to Home Screen" on iOS/Android

### Phase 5 — Deploy (1–2 hours)

- [ ] **5.1** Create a private GitHub repo, push everything (`.gitignore` must exclude all secrets)
- [ ] **5.2** Create Railway project from the GitHub repo
- [ ] **5.3** Add all environment variables in Railway dashboard:
  - `ANTHROPIC_API_KEY`
  - `OPENAI_API_KEY`
  - `JSEARCH_API_KEY`
  - `GOOGLE_SERVICE_ACCOUNT_JSON`
  - `GMAIL_TOKEN_JSON`
  - `APP_API_KEY` (generate a random secret for frontend auth)
- [ ] **5.4** Set start command: `uvicorn api.server:app --host 0.0.0.0 --port $PORT` (or `chainlit run chainlit_app.py --host 0.0.0.0 --port $PORT`)
- [ ] **5.5** Deploy. Railway gives you a `https://*.railway.app` URL — open it on your phone

### Phase 6 — Harden for production (ongoing)

- [ ] **6.1** Migrate from SQLite to PostgreSQL checkpointer (provision Postgres on Railway, update `DATABASE_URL`)
- [ ] **6.2** Add request rate limiting (FastAPI middleware or Railway's built-in)
- [ ] **6.3** Set up LangSmith tracing (`LANGSMITH_API_KEY` + `LANGCHAIN_TRACING_V2=true`) for debugging production runs
- [ ] **6.4** Add structured logging (`structlog` or Python `logging` to stdout — Railway captures it)
- [ ] **6.5** Set up health check monitoring (UptimeRobot, free tier, pings your `/health` endpoint)

---

## Appendix: Environment Variables Reference

All secrets that need to be set on the deployment platform:

| Variable | Source | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | Anthropic console | For Claude models |
| `OPENAI_API_KEY` | OpenAI console | For `gpt-4.1-nano` in job description summarizer |
| `JSEARCH_API_KEY` | OpenWebNinja dashboard | For JSearch job search |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | GCP console → IAM → Service Accounts | Full JSON content as a single string |
| `GMAIL_TOKEN_JSON` | Generated locally via OAuth flow | Full contents of `gmail_token.json` |
| `GMAIL_CLIENT_SECRETS_JSON` | GCP console → OAuth 2.0 credentials | Optional — only needed if token needs to be re-issued |
| `APP_API_KEY` | You generate this | Random secret for frontend→backend auth |
| `DATABASE_URL` | Railway Postgres add-on | Only needed when using PostgreSQL checkpointer |
| `LANGSMITH_API_KEY` | LangSmith dashboard | Optional — enables LangGraph tracing |
