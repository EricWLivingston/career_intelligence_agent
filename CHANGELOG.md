# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.4.0] — 2026-05-18

### Added
- `README.md` — full project overview with agent table, setup instructions, env var reference, and auth architecture
- `CHANGELOG.md` — this file; git tags applied from v0.1.0 forward
- `.streamlit/config.toml` — dark theme (`#0F1117` background, `#4F8EF7` accent)

### Changed
- `streamlit_app.py` — complete UI redesign: hidden Streamlit chrome, centered 760px layout, small header + muted tagline, "New chat" button, rounded inputs, silent spinner
- `MAIN_EXPLANATION.md` — updated imports (`MemorySaver` → `SqliteSaver`, added `sqlite3`), updated `build_agents()` checkpointer explanation, updated `run_chat()` to reflect fixed `chat-main` thread ID, added `run_agent()` section documenting all callers, updated CLI examples to use `uv run`
- `tools_explanation.txt` — updated `_get_creds()` and `_get_gmail_creds()` sections to describe env-var-first credential loading pattern
- `passdown.md` — added Phase 3–5 session notes, updated Current State

---

## [0.3.0] — 2026-05-18

### Added
- `api/server.py` — FastAPI app with `POST /chat` (Server-Sent Events stream) and `GET /health`
- `api/auth.py` — `verify_key` dependency; enforces `X-Api-Key` header against `APP_API_KEY` env var
- `api/models.py` — `ChatRequest` Pydantic model (`message`, `thread_id`)
- `api/__init__.py` — package marker
- `streamlit_app.py` — Streamlit web chat UI; imports `run_agent` directly; session-scoped `web-{uuid}` thread IDs; `st.session_state` for display history
- `APP_API_KEY` — generated and added to `.env`

### Changed
- `pyproject.toml` — added `fastapi>=0.115`, `uvicorn[standard]>=0.32`, `streamlit>=1.45`
- `.gitignore` — added `state.db-shm`, `state.db-wal`

---

## [0.2.0] — 2026-05-18

### Added
- SQLite persistent checkpointer (`state.db`) — conversation history survives process restarts
- `GOOGLE_SERVICE_ACCOUNT_JSON` env var support in `_get_creds()` — falls back to `service_account.json` file for local dev
- `GMAIL_TOKEN_JSON` env var support in `_get_gmail_creds()` — auto-refreshes expired tokens; falls back to browser OAuth flow for local dev
- `--thread` CLI argument — start a named alternate session from the terminal

### Changed
- `pyproject.toml` — added `langgraph-checkpoint-sqlite`
- `main.py` — replaced `MemorySaver()` with `SqliteSaver(sqlite3.connect(...))`, fixed `run_chat()` thread ID from random UUID to `"chat-main"`, added `run_agent()` as shared invocation function, added argparse CLI with `--thread` argument

### Fixed
- Gmail trigger `StructuredTool` not callable — changed `gmail_read(...)` to `gmail_read.invoke({...})`
- Chat sessions not persisting across restarts — was generating a new random thread ID each startup

---

## [0.1.0] — 2026-05-18

### Added
- Initial multi-agent system: orchestrator + 6 subagents (job_researcher, scorer_analyst, report_writer, interview_coach, job_cataloguer, critic_agent)
- Tools: `jsearch_request`, `web_search`, `google_sheets_*`, `google_docs_*`, `gmail_read`, `gmail_send`, `get_current_time`
- Skills: `output-format`, `triggers`, `critic`, `delegation`
- `main.py` with `run_chat()`, `run_gmail_trigger()`, and argparse CLI
- `lib/tools.py` — all tool implementations and Google API credential management
- `lib/prompts.py` — system prompts for each agent
- `dev.ipynb` — interactive testing notebook
- Project on GitHub (private repo)
