# Passdown — Career Intelligence Agent

## Project Overview

A multi-subagent AI system for job searching, scoring, tracking, and interview prep. Built with Deep Agents / LangGraph on top of LangChain. Entry point is `main.py`; all tool definitions live in `lib/tools.py`; system prompts live in `lib/prompts.py`; on-demand skill files live in `skills/`.

### Subagents (`main.py`)

| Name | Model | Role |
|---|---|---|
| orchestrator | `claude-haiku-4-5-20251001` | Routes intent, delegates to sub-agents, synthesizes results |
| `job_researcher` | `claude-haiku-4-5-20251001` | Searches JSearch API, deduplicates against job catalogue sheet |
| `scorer_analyst` | `claude-sonnet-4-6` | Scores jobs against resume, principles, and rubric; writes output to Google Docs |
| `report_writer` | `claude-sonnet-4-6` | Produces company/role deep-dive reports in Google Docs |
| `interview_coach` | `claude-sonnet-4-6` | Generates question banks, briefs, mock interviews; writes to Google Docs |
| `job_cataloguer` | `claude-haiku-4-5-20251001` | Logs new jobs, tracks application status, and queries the job catalogue |
| `critic_agent` | `claude-sonnet-4-6` | Audits other agents' outputs for accuracy and hallucination via web_search spot-checks |

---

## Full Tool Assignment

| Agent | Tools |
|---|---|
| orchestrator | `get_current_time`, `google_docs_read`, `gmail_read`, `gmail_send` |
| job_researcher | `google_sheets_column`, `jsearch_request` |
| scorer_analyst | `web_search`, `google_docs_create`, `google_docs_write`, `google_docs_append`, `google_docs_replace_text` |
| report_writer | `web_search`, `google_docs_create`, `google_docs_write`, `google_docs_append`, `google_docs_replace_text` |
| interview_coach | `web_search`, `google_docs_create`, `google_docs_write`, `google_docs_append`, `google_docs_replace_text` |
| job_cataloguer | `get_current_time`, `google_sheets_read`, `google_sheets_append`, `google_sheets_append_batch`, `google_sheets_update_cell`, `google_sheets_find_row`, `google_docs_write`, `google_docs_append`, `gmail_send` |
| critic_agent | `web_search` |

Tool consistency check (run to verify): `uv run python -c "from langchain_core.tools.base import BaseTool; import lib.tools as t, main; defined={n for n,o in vars(t).items() if isinstance(o,BaseTool)}; referenced={tool.name for a in main.SUBAGENTS for tool in a['tools']}; print('Missing:', referenced-defined or 'none')"`

---

## Changes Made Across All Sessions

### Prior sessions (see git history for full detail)
- All core bug fixes: JSONDecodeError in jsearch, research agents using grep instead of web_search, hardcoded 2024 year, missing tools restored, google_sheets_column dedup key, critic_agent missing web_search, dev.ipynb sync, app_tracker → job_cataloguer rename, job_cataloguer batch logging fix.
- All optimizations from OPTIMIZATION_REVIEW.md: compact JSON, prompt caching, LangSmith tracing, skill spec compliance, gmail_read full_body param, google_docs_write skip prefetch.
- main.py restructured with `get_agent()` singleton, `_extract_response()`, `run_agent()`, `run_chat()`, `run_gmail_trigger()`, argparse CLI.

---

### This session

#### Git setup and first commit
- Added `.ipynb_checkpoints/`, `tmp/`, `.claude/`, and `state.db` to `.gitignore`
- Resolved GitHub push rejection (`git pull origin main --allow-unrelated-histories`) caused by GitHub auto-generating an initial file on repo creation
- First commit pushed to GitHub successfully

#### Created `MAIN_EXPLANATION.md`
Comprehensive code walkthrough of `main.py` — covers every section: imports, `_cached()`, `SUBAGENTS` roster, model selection rationale, `build_agents()`, singleton pattern, response parsing, both trigger modes, and CLI usage.

#### Bug fix — Gmail trigger `StructuredTool` not callable (`main.py`)
`gmail_read(query=..., ...)` failed with `'StructuredTool' object is not callable`. LangChain's `@tool` decorator wraps functions into `StructuredTool` objects that require `.invoke({...})` for direct calls outside an agent.

```python
# before
gmail_read(query=query, max_results=10, full_body=True)

# after
gmail_read.invoke({"query": query, "max_results": 10, "full_body": True})
```

#### Phase 1 — Decouple secrets from filesystem (`lib/tools.py`)
Both credential functions now check for an environment variable first and fall back to file-based auth for local dev:

- **`_get_creds()`**: reads `GOOGLE_SERVICE_ACCOUNT_JSON` env var (full JSON string) → `Credentials.from_service_account_info()`. Falls back to `service_account.json` file.
- **`_get_gmail_creds()`**: reads `GMAIL_TOKEN_JSON` env var → `OAuthCredentials.from_authorized_user_info()`, auto-refreshes if expired. Falls back to file-based OAuth flow (opens browser — local only).

To activate on any server: set `GOOGLE_SERVICE_ACCOUNT_JSON` and `GMAIL_TOKEN_JSON` in the host's environment variables (paste the full JSON contents of each file as a single-quoted string).

#### Phase 2 — SQLite persistent checkpointer (`main.py`, `pyproject.toml`)
Replaced in-RAM `MemorySaver` with `SqliteSaver` so conversation history survives process restarts.

- Added `langgraph-checkpoint-sqlite` to `pyproject.toml`
- Added `import sqlite3` to `main.py`
- `build_agents()` now uses:
  ```python
  checkpointer=SqliteSaver(sqlite3.connect("./state.db", check_same_thread=False))
  ```
- `state.db` added to `.gitignore`

**Note:** `SqliteSaver.from_conn_string()` returns a context manager (`_GeneratorContextManager`), not a `BaseCheckpointSaver` — passing it directly to `create_deep_agent` raises a `TypeError`. Fix is to pass a raw `sqlite3.connect()` call instead.

#### Bug fix — Chat sessions not persisting context between restarts (`main.py`)
`run_chat()` was generating a new random UUID thread ID on every startup (`chat-{uuid4().hex[:8]}`). SQLite was persisting state correctly but each new session used a different key, so old context was never found.

Fixed by defaulting to a fixed thread ID:
```python
def run_chat(thread_id: str = "chat-main") -> None:
```

Added `--thread` CLI argument so the user can start a named alternate session:
```bash
uv run python main.py                        # continues "chat-main" thread
uv run python main.py --thread new-topic     # fresh named session
```

---

## Current State

- **Project is on GitHub** (private repo). All credential files gitignored; `.env` gitignored.
- **Phase 1 complete** — credential functions support env var injection. Manual step remaining: add `GOOGLE_SERVICE_ACCOUNT_JSON` and `GMAIL_TOKEN_JSON` to `.env` (paste JSON file contents) and test with files renamed/removed.
- **Phase 2 complete** — SQLite checkpointer active. `state.db` is created automatically on first run.
- **Chat persistence working** — `chat-main` thread ID is consistent across restarts.
- **Phase 3 complete** — FastAPI server live at `api/server.py`. Start with `APP_API_KEY=<secret> uvicorn api.server:app --reload`. `POST /chat` (SSE, requires `X-Api-Key` header) and `GET /health` are implemented.
- **Next production step:** PRODUCTION_PLAN.md Phase 4 — frontend (Chainlit recommended for fastest path) or Phase 5 — deploy to Railway.

---

## Key Files

| File | Purpose |
|---|---|
| `main.py` | Agent definitions, trigger functions (`run_chat`, `run_gmail_trigger`), and CLI entry point |
| `lib/tools.py` | All tool implementations, credential management |
| `lib/prompts.py` | System prompts for each sub-agent |
| `skills/output_format/SKILL.md` | HTML email/doc formatting rules (name: `output-format`) |
| `skills/triggers/SKILL.md` | Gmail and schedule trigger handling |
| `skills/critic/SKILL.md` | Critic agent integration protocol |
| `skills/delegation/SKILL.md` | Legacy — content inlined into orchestrator prompt; no longer loaded at runtime |
| `api/server.py` | FastAPI app — `POST /chat` (SSE) and `GET /health` |
| `api/auth.py` | `verify_key` dependency — checks `X-Api-Key` header against `APP_API_KEY` env var |
| `api/models.py` | `ChatRequest` Pydantic model (`message`, `thread_id`) |
| `dev.ipynb` | Interactive testing notebook |
| `MAIN_EXPLANATION.md` | Plain-English walkthrough of every section of `main.py` |
| `PRODUCTION_PLAN.md` | Full production transition plan with phased steps |
| `OPTIMIZATION_REVIEW.md` | Speed/token optimization findings with current status |
| `state.db` | SQLite checkpoint database — auto-created, gitignored |
| `tmp/gmail_processed.json` | Persisted set of processed Gmail message IDs (auto-created by gmail trigger) |
| `.env` | All API keys + `LANGCHAIN_TRACING_V2=true` + `LANGCHAIN_PROJECT` + `GOOGLE_SERVICE_ACCOUNT_JSON` + `GMAIL_TOKEN_JSON` (once Phase 1 manual step is done) |
| `service_account.json` | Google service account key — Sheets only (gitignored) |
| `gmail_credentials.json` | OAuth2 Desktop client secrets — Gmail + Docs (gitignored) |
| `gmail_token.json` | Saved Gmail+Docs OAuth token, auto-refreshed (gitignored) |

---

## Auth Architecture

| What | Credentials | Reason |
|---|---|---|
| Google Sheets | Service account (`service_account.json` or `GOOGLE_SERVICE_ACCOUNT_JSON` env var) | Sheets shared with SA; no file creation needed |
| Google Docs | OAuth user (`gmail_token.json` or `GMAIL_TOKEN_JSON` env var) | Must create files in user's Drive; SA has no Drive on personal accounts |
| Gmail | OAuth user (`gmail_token.json` or `GMAIL_TOKEN_JSON` env var) | Must act as the user to send/read their email |
| JSearch API | `JSEARCH_API_KEY` env var | `x-api-key` header; OpenWebNinja API |
| Tavily | `TAVILY_API_KEY` env var | Tavily Python client singleton |
| Claude models | `ANTHROPIC_API_KEY` env var | All agents via Deep Agents |
| GPT-4.1-nano | `OPENAI_API_KEY` env var | Job description summarizer inside `jsearch_request` only |
| LangSmith | `LANGSMITH_API_KEY` + `LANGCHAIN_TRACING_V2=true` | Automatic run tracing; no code changes needed |

---

## CLI Reference

```bash
uv run python main.py                                           # chat (continues chat-main thread)
uv run python main.py --thread my-session                      # chat with named thread
uv run python main.py gmail                                     # Gmail trigger (default query, 60s poll)
uv run python main.py gmail --query "is:unread label:jobs"     # custom Gmail query
uv run python main.py gmail --interval 30                      # poll every 30s
```
