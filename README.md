# Career Intelligence Agent

A multi-agent AI system for job searching, scoring, tracking, and interview prep. Built with Deep Agents (LangGraph) on top of LangChain, with integrations for Google Sheets, Google Docs, Gmail, and the JSearch job API.

---

## Agents

| Agent | Model | Role |
|---|---|---|
| `orchestrator` | Haiku | Routes intent, delegates to subagents, synthesizes results |
| `job_researcher` | Haiku | Searches JSearch API, deduplicates against job catalogue sheet |
| `scorer_analyst` | Sonnet | Scores jobs against resume and criteria, writes analysis to Google Docs |
| `report_writer` | Sonnet | Produces company/role deep-dive reports in Google Docs |
| `interview_coach` | Sonnet | Generates question banks, briefs, and mock interview materials |
| `job_cataloguer` | Haiku | Logs jobs in Google Sheets, tracks application status, sends Gmail confirmations |
| `critic_agent` | Sonnet | Audits other agents' outputs for hallucinations and scoring errors |

---

## How to Run

**Prerequisites:** Python 3.13+, [uv](https://docs.astral.sh/uv/)

```bash
# Install dependencies
uv sync

# Copy and fill in environment variables
cp .env.example .env   # then edit .env with your keys
```

**Terminal chat:**
```bash
uv run python main.py                        # continues "chat-main" thread
uv run python main.py --thread new-topic     # fresh named session
```

**Web UI (Streamlit):**
```bash
uv run streamlit run streamlit_app.py
# opens at http://localhost:8501
```

**HTTP API (FastAPI):**
```bash
uv run uvicorn api.server:app --reload
# POST /chat  (requires X-Api-Key header)
# GET  /health
```

**Gmail trigger (automated email processing):**
```bash
uv run python main.py gmail                                    # polls every 60s
uv run python main.py gmail --query "is:unread label:jobs"    # custom query
uv run python main.py gmail --interval 30                      # faster poll
```

---

## Project Structure

| Path | Purpose |
|---|---|
| `main.py` | Agent definitions, `run_agent()`, CLI entry point |
| `lib/tools.py` | All tool implementations and credential management |
| `lib/prompts.py` | System prompts for each agent |
| `api/server.py` | FastAPI app — `POST /chat` (SSE) and `GET /health` |
| `api/auth.py` | Static API key middleware (`X-Api-Key` header) |
| `streamlit_app.py` | Streamlit web chat UI |
| `.streamlit/config.toml` | Dark theme configuration |
| `skills/` | Skill markdown files loaded by the orchestrator at runtime |
| `state.db` | SQLite conversation checkpoint (auto-created, gitignored) |
| `PRODUCTION_PLAN.md` | Full production deployment plan (phases 1–6) |
| `MAIN_EXPLANATION.md` | Plain-English walkthrough of `main.py` |
| `tools_explanation.txt` | Plain-English walkthrough of `lib/tools.py` |

---

## Environment Variables

| Variable | Source | Required |
|---|---|---|
| `ANTHROPIC_API_KEY` | [Anthropic Console](https://console.anthropic.com) | Yes |
| `OPENAI_API_KEY` | [OpenAI Console](https://platform.openai.com) | Yes |
| `JSEARCH_API_KEY` | OpenWebNinja dashboard | Yes |
| `TAVILY_API_KEY` | [Tavily](https://tavily.com) | Yes |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | GCP → IAM → Service Accounts | Yes |
| `GMAIL_TOKEN_JSON` | Generated locally via OAuth flow | Yes |
| `APP_API_KEY` | Generate with `python -c "import secrets; print(secrets.token_hex(32))"` | For API server |
| `LANGSMITH_API_KEY` | [LangSmith](https://smith.langchain.com) | Optional |
| `LANGCHAIN_TRACING_V2` | Set to `"true"` to enable | Optional |

See `PRODUCTION_PLAN.md` for full deployment instructions including Railway and Streamlit Community Cloud.

---

## Auth Architecture

| Service | Credentials |
|---|---|
| Google Sheets | Service account (`GOOGLE_SERVICE_ACCOUNT_JSON`) |
| Google Docs | OAuth user token (`GMAIL_TOKEN_JSON`) |
| Gmail | OAuth user token (`GMAIL_TOKEN_JSON`) |
| JSearch | `JSEARCH_API_KEY` |
| Claude models | `ANTHROPIC_API_KEY` |
| GPT-4.1-nano | `OPENAI_API_KEY` (job description summarizer only) |
