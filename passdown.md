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

### Bug Fix — JSONDecodeError in `jsearch_request` (`lib/tools.py`)
`_summarize_job_descriptions` called `json.loads()` on LLM output that sometimes came back wrapped in markdown code fences (` ```json ... ``` `). Fixed by stripping fences with a regex before parsing, with fallback to keep original descriptions if parsing still fails.

### Bug Fix — Research agents using grep/glob instead of `web_search` (`lib/prompts.py`)
Deep Agents' `FilesystemMiddleware` injects `grep`, `glob`, and `read_file` tools into every subagent. Research agents (`scorer_analyst`, `report_writer`, `interview_coach`, `critic_agent`) were using these filesystem tools to look for web search capability rather than calling `web_search` directly. Fixed by prepending a two-sentence explicit warning to each agent's `<tools>` block: "Call all tools listed here directly by name — they are registered and ready. Filesystem tools (grep, glob, read_file) are present for internal state only; never use them for internet or web research."

### Bug Fix — Hardcoded year in search queries (`lib/prompts.py`)
All time-sensitive search query examples in `scorer_analyst`, `report_writer`, `interview_coach`, and `critic_agent` prompts used the hardcoded year "2024". Replaced with `{current_year}` — each agent receives the current date from the orchestrator and uses it to construct fresh queries.

### Restored missing tools to `lib/tools.py`
`web_search`, `google_sheets_column`, and `google_docs_write` were absent from the file (external modification). All three restored:
- `web_search`: Tavily singleton (`_get_tavily()`), returns JSON array of `{title, url, content}`
- `google_sheets_column`: fetches a single column by header name, returns flat JSON array
- `google_docs_write`: deletes all existing doc content then inserts new text via batchUpdate

### Bug Fix — `google_sheets_column` dedup key (`lib/prompts.py`, `dev.ipynb`)
`job_researcher` prompt was instructing `google_sheets_column` to use `column="job_apply_link"`. Changed to `column="job_id"` — the apply link is not a stable unique key; `job_id` is the canonical dedup identifier from JSearch. Also fixed in `dev.ipynb` cell 10.

### Bug Fix — `critic_agent` missing `web_search` tool (`main.py`, `lib/prompts.py`)
`critic_agent` prompt described `web_search` as a tool but it was not in the agent's tool list in `main.py`. Added `web_search` to the critic's tool list so it can independently spot-check facts in audited outputs.

### `dev.ipynb` synced with `main.py`
Notebook was out of sync in several ways — all fixed:
- Cell 2: removed local `_cached` definition, added `from main import _cached, SUBAGENTS, build_agents`
- Cell 4: removed local SUBAGENTS redefinition; `build_subagent()` now reads from the imported `SUBAGENTS` list
- Cell 10: `column="job_apply_link"` → `column="job_id"`
- Cells 30, 31: queries updated from "2024" → "2026"
- Cell 33: `build_orchestrator()` → `build_agents()`

### Rename `app_tracker` → `job_cataloguer` (all files)
The subagent was named `app_tracker`, which the orchestrator didn't associate with logging or cataloguing requests ("log this job", "add to my list"). Renamed to `job_cataloguer` across every file. Additionally expanded the ORCHESTRATOR_PROMPT intent routing from 2 patterns to 6:
- "Log [job/role]" → job_cataloguer
- "Add this to my list / catalogue" → job_cataloguer
- "Save this job / role" → job_cataloguer
- "Mark [role] as applied / shortlisted / rejected" → job_cataloguer
- "What's my pipeline?" → job_cataloguer
- "Any follow-ups due?" → job_cataloguer

Files touched: `lib/prompts.py` (variable rename `APP_TRACKER_PROMPT` → `JOB_CATALOGUER_PROMPT`, ORCHESTRATOR_PROMPT sub-agents list, intent routing, delegation section, role description in the prompt itself), `main.py` (import, subagent name/description/system_prompt), `dev.ipynb` (cells 2, 44, 45, 49), `skills/triggers/SKILL.md`, `skills/delegation/SKILL.md`, `skills/output_format/SKILL.md`.

### Bug Fix — `job_cataloguer` only logging 3 of 5 jobs (`lib/tools.py`, `main.py`, `lib/prompts.py`)
Root cause: `google_sheets_append` takes one row at a time, requiring N sequential tool calls to log N jobs. Claude Haiku stops making repetitive tool calls early (~3), and the `log_new` prompt description said "Write new row" (singular) with no loop instruction. Fixed three ways:
- Added `google_sheets_append_batch` tool to `lib/tools.py` using gspread's `append_rows` — writes all N rows in a single API call
- Added `google_sheets_append_batch` to job_cataloguer's tool list in `main.py`
- Updated `log_new` in `JOB_CATALOGUER_PROMPT` to: collect ALL jobs into a row list, call `google_sheets_append_batch` ONCE, never loop on `google_sheets_append`
- Added `google_sheets_append_batch` to the `<tools>` block in `JOB_CATALOGUER_PROMPT` so Haiku sees it before reading the action description

### Optimizations applied (from OPTIMIZATION_REVIEW.md)
All prior sessions:
- **Compact JSON** — `jsearch_request` uses `separators=(',', ':')`. Saves ~2–4K tokens per search call.
- **`critic_agent` web_search tool** — added to agent's tool list.
- **`google_sheets_column`** — dedicated single-column tool; job_researcher uses it for dedup instead of full sheet read (100 jobs: ~3KB vs ~50KB).
- **Delegation skill inlined** — ORCHESTRATOR_PROMPT includes delegation rules directly; eliminates one skill-load round-trip per sub-agent call.
- **`google_sheets_read` valid JSON** — returns `json.dumps` instead of Python `str(records)`.
- **Prompt caching** — `_cached()` helper wraps all system prompts in `cache_control: {"type": "ephemeral"}`.
- **LangSmith tracing** — `LANGCHAIN_TRACING_V2=true` + `LANGCHAIN_PROJECT=career-intelligence-agent` in `.env`.
- **Skill spec compliance** — `skills/output_format/SKILL.md` name changed to `output-format`.

This session:
- **U1 — Removed `google_docs_read` from 3 agents** (`main.py`): scorer_analyst, report_writer, interview_coach had it assigned but never used it in their prompts. Orchestrator summarizes docs before delegation so these agents never need direct doc reads.
- **U2 — Removed `gmail_create_draft`** (`lib/tools.py`): tool was defined but not assigned to any agent. Removed entirely.
- **U3 — Added `google_sheets_append_batch` to job_cataloguer `<tools>` block** (`lib/prompts.py`): was in main.py and the action description but missing from the `<tools>` inventory — Haiku needs to see it there to know it's callable.
- **S1/T1 — `gmail_read` rewrite** (`lib/tools.py`): added `full_body: bool = False` parameter; uses `format="metadata"` by default (faster, smaller payloads); body only included when `full_body=True`; output now compact JSON.
- **T2 — `jsearch_request` compact JSON** (`lib/tools.py` lines 466, 476): both return paths now use `separators=(',', ':')`.
- **S5 — `google_docs_write` skip prefetch** (`lib/tools.py`): added `is_new: bool = False` parameter; skips the GET round-trip when writing to a freshly created doc.
- **T3 — `critic_agent` web_search cap** (`lib/prompts.py`): added "cap total searches at 5 per audited output" alongside the existing "spot-check at least 3 key facts" instruction.

### Production prep — `main.py` restructured
`main()` was replaced by a proper trigger architecture:
- **`get_agent()`** — module-level singleton; builds the agent once and caches it. FastAPI/Chainlit import this directly rather than calling `build_agents()` per request.
- **`_extract_response(result)`** — handles both plain-string and multi-block list content from Claude responses.
- **`run_agent(message, thread_id)`** — single invocation point shared by all triggers. Future FastAPI server calls this (or `get_agent().astream()` for SSE streaming).
- **`run_chat()`** — interactive chat trigger with per-session UUID thread IDs (`chat-{8 hex chars}`). Fixes the hardcoded `"career-session-1"` thread ID.
- **`run_gmail_trigger(query, poll_interval)`** — polls Gmail every N seconds for emails matching `query`. Reads with `full_body=True`. Each email gets its own thread (`gmail-{email_id}`). The `[Gmail trigger]` prefix causes the orchestrator to load the `triggers` skill, which routes sub-agents and calls `gmail_send` to reply. Processed IDs persisted across restarts in `tmp/gmail_processed.json`.
- **CLI dispatch via `argparse`**:
  - `uv run python main.py` → chat trigger
  - `uv run python main.py gmail` → Gmail trigger (default: `is:unread subject:[career]`, 60s interval)
  - `uv run python main.py gmail --query "is:unread label:career-agent" --interval 120`

---

## Current State

- **No commits have been made** — entire working tree is untracked/unstaged. Stage files explicitly (not `git add .`) to avoid committing credential files outside `.gitignore`.
- **Tool consistency check: PASS** — 16 tools referenced, 0 missing.
- **`dev.ipynb` is the primary testing surface.** Run cells top-to-bottom; cells 2 and 4 must execute before any agent or tool test cells. Note: `dev.ipynb` imports `build_agents` from `main` — the new `get_agent()` / `run_agent()` functions are also importable from `main`.
- **OPTIMIZATION_REVIEW.md outstanding items:** S2 (`ChatOpenAI` singleton + remove GPT dependency in `_summarize_job_descriptions`), S3 (`httpx.Client` singleton in `jsearch_request`), S4 (thread ID now fixed in chat trigger; `MemorySaver` → `SqliteSaver` is next for persistence across restarts — PRODUCTION_PLAN.md Phase 2).
- **Next production step:** PRODUCTION_PLAN.md Phase 1 — decouple secrets from filesystem (`GOOGLE_SERVICE_ACCOUNT_JSON` and `GMAIL_TOKEN_JSON` env vars in `lib/tools.py`).

---

## Key Files

| File | Purpose |
|---|---|
| `main.py` | Agent definitions, trigger functions (`run_chat`, `run_gmail_trigger`), and CLI entry point |
| `lib/tools.py` | All tool implementations |
| `lib/prompts.py` | System prompts for each sub-agent |
| `skills/output_format/SKILL.md` | HTML email/doc formatting rules (name: `output-format`) |
| `skills/triggers/SKILL.md` | Gmail and schedule trigger handling |
| `skills/critic/SKILL.md` | Critic agent integration protocol |
| `skills/delegation/SKILL.md` | Legacy — content inlined into orchestrator prompt; no longer loaded at runtime |
| `dev.ipynb` | Interactive testing notebook |
| `PRODUCTION_PLAN.md` | Full production transition plan |
| `OPTIMIZATION_REVIEW.md` | Speed/token optimization findings with current status |
| `tmp/gmail_processed.json` | Persisted set of processed Gmail message IDs (auto-created by gmail trigger) |
| `.env` | All API keys + `LANGCHAIN_TRACING_V2=true` + `LANGCHAIN_PROJECT` |
| `service_account.json` | Google service account key — Sheets only (gitignored) |
| `gmail_credentials.json` | OAuth2 Desktop client secrets — Gmail + Docs (gitignored) |
| `gmail_token.json` | Saved Gmail+Docs OAuth token, auto-refreshed (gitignored) |

---

## Auth Architecture

| What | Credentials | Reason |
|---|---|---|
| Google Sheets | Service account (`service_account.json`) | Sheets shared with SA; no file creation needed |
| Google Docs | OAuth user (`gmail_token.json`) | Must create files in user's Drive; SA has no Drive on personal accounts |
| Gmail | OAuth user (`gmail_token.json`) | Must act as the user to send/read their email |
| JSearch API | `JSEARCH_API_KEY` env var | `x-api-key` header; OpenWebNinja API |
| Tavily | `TAVILY_API_KEY` env var | Tavily Python client singleton |
| Claude models | `ANTHROPIC_API_KEY` env var | All agents via Deep Agents |
| GPT-4.1-nano | `OPENAI_API_KEY` env var | Job description summarizer inside `jsearch_request` only |
| LangSmith | `LANGSMITH_API_KEY` + `LANGCHAIN_TRACING_V2=true` | Automatic run tracing; no code changes needed |
