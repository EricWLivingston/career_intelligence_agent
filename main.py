import argparse
import json
import sqlite3
import sys
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import SystemMessage
from lib.tools import (
    get_current_time,
    web_search,
    google_docs_create,
    google_docs_read,
    google_docs_write,
    google_docs_append,
    google_docs_replace_text,
    google_sheets_read,
    google_sheets_column,
    google_sheets_append,
    google_sheets_append_batch,
    google_sheets_update_cell,
    google_sheets_find_row,
    gmail_read,
    gmail_send,
    jsearch_request,
)
from lib.prompts import (
    ORCHESTRATOR_PROMPT,
    JOB_RESEARCHER_PROMPT,
    SCORER_ANALYST_PROMPT,
    REPORT_WRITER_PROMPT,
    INTERVIEW_COACH_PROMPT,
    JOB_CATALOGUER_PROMPT,
    CRITIC_PROMPT,
)

load_dotenv()


def _cached(text: str) -> SystemMessage:
    """Wrap a prompt string so Anthropic caches it on the first call."""
    return SystemMessage(content=[{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}])


SUBAGENTS = [
    {
        "name": "job_researcher",
        "description": "Discovers and structures job listings matching the user's criteria",
        "model": "claude-haiku-4-5-20251001",
        "system_prompt": _cached(JOB_RESEARCHER_PROMPT),
        "tools": [google_sheets_column, jsearch_request],
    },
    {
        "name": "scorer_analyst",
        "description": "Scores job listings against the user's resume, principles, and weighted rubric",
        "model": "claude-sonnet-4-6",
        "system_prompt": _cached(SCORER_ANALYST_PROMPT),
        "tools": [web_search, google_docs_create, google_docs_write, google_docs_append, google_docs_replace_text],
    },
    {
        "name": "report_writer",
        "description": "Produces structured deep-dive reports on roles, companies, or job markets",
        "model": "claude-sonnet-4-6",
        "system_prompt": _cached(REPORT_WRITER_PROMPT),
        "tools": [web_search, google_docs_create, google_docs_write, google_docs_append, google_docs_replace_text],
    },
    {
        "name": "interview_coach",
        "description": "Prepares interview materials, question banks, mock interviews, and learning plans",
        "model": "claude-sonnet-4-6",
        "system_prompt": _cached(INTERVIEW_COACH_PROMPT),
        "tools": [web_search, google_docs_create, google_docs_write, google_docs_append, google_docs_replace_text],
    },
    {
        "name": "job_cataloguer",
        "description": "Logs new jobs, tracks application status, and queries the job catalogue",
        "model": "claude-haiku-4-5-20251001",
        "system_prompt": _cached(JOB_CATALOGUER_PROMPT),
        "tools": [
            get_current_time,
            google_sheets_read,
            google_sheets_append,
            google_sheets_append_batch,
            google_sheets_update_cell,
            google_sheets_find_row,
            google_docs_write,
            google_docs_append,
            gmail_send,
        ],
    },
    {
        "name": "critic_agent",
        "description": "Audits other agents' outputs for factual accuracy, hallucination, and scoring consistency",
        "model": "claude-sonnet-4-6",
        "system_prompt": _cached(CRITIC_PROMPT),
        "tools": [web_search],
    },
]


def build_agents():
    return create_deep_agent(
        name="orchestrator",
        model="claude-haiku-4-5-20251001",
        tools=[get_current_time, google_docs_read, gmail_read, gmail_send],
        system_prompt=_cached(ORCHESTRATOR_PROMPT),
        subagents=SUBAGENTS,
        backend=FilesystemBackend(root_dir=".", virtual_mode=True),
        skills=["./skills/"],
        checkpointer=SqliteSaver(sqlite3.connect("./state/state.db", check_same_thread=False)),
    )


# ---------------------------------------------------------------------------
# Agent singleton — built once, reused across all triggers and future API layers
# ---------------------------------------------------------------------------

_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = build_agents()
    return _agent


def _extract_response(result: dict) -> str:
    messages = result.get("messages", [])
    if not messages:
        return ""
    content = messages[-1].content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    return str(content)


def run_agent(message: str, thread_id: str) -> str:
    """Invoke the agent with a single message and return the response as a string."""
    result = get_agent().invoke(
        {"messages": [{"role": "user", "content": message}]},
        config={"configurable": {"thread_id": thread_id}},
    )
    return _extract_response(result)


# ---------------------------------------------------------------------------
# Chat trigger
# ---------------------------------------------------------------------------

def run_chat(thread_id: str = "chat-main") -> None:
    print(f"Career Intelligence Agent ready (session: {thread_id}). Type 'exit' to quit.")
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() in ("exit", "quit"):
            break
        if not user_input:
            continue
        print(f"\nAgent: {run_agent(user_input, thread_id)}")


# ---------------------------------------------------------------------------
# Gmail trigger
# ---------------------------------------------------------------------------

_PROCESSED_IDS_FILE = Path("tmp/gmail_processed.json")


def _load_processed_ids() -> set:
    if _PROCESSED_IDS_FILE.exists():
        return set(json.loads(_PROCESSED_IDS_FILE.read_text()))
    return set()


def _save_processed_ids(ids: set) -> None:
    _PROCESSED_IDS_FILE.parent.mkdir(exist_ok=True)
    _PROCESSED_IDS_FILE.write_text(json.dumps(list(ids)))


def run_gmail_trigger(query: str = "is:unread subject:[career]", poll_interval: int = 60) -> None:
    """Poll Gmail for new emails and process each as a user request.

    The orchestrator loads the 'triggers' skill on seeing [Gmail trigger] messages
    and handles sub-agent routing and gmail_send replies autonomously.
    """
    processed_ids = _load_processed_ids()
    print(f"Gmail trigger active. Polling every {poll_interval}s for: {query!r}")
    while True:
        try:
            emails = json.loads(gmail_read.invoke({"query": query, "max_results": 10, "full_body": True}))
            for email in emails:
                email_id = email["id"]
                if email_id in processed_ids:
                    continue
                user_message = (
                    f"[Gmail trigger] You received an email.\n"
                    f"From: {email['from']}\n"
                    f"Subject: {email['subject']}\n"
                    f"Date: {email['date']}\n\n"
                    f"{email.get('body') or email.get('snippet', '')}"
                )
                print(f"\n→ Processing: {email['subject']!r} from {email['from']}")
                response = run_agent(user_message, thread_id=f"gmail-{email_id}")
                print(f"  Agent: {response[:200]}")
                processed_ids.add(email_id)
                _save_processed_ids(processed_ids)
        except Exception as exc:
            print(f"[gmail trigger error] {exc}", file=sys.stderr)
        time.sleep(poll_interval)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Career Intelligence Agent")
    parser.add_argument(
        "mode",
        nargs="?",
        default="chat",
        choices=["chat", "gmail"],
        help="Trigger mode: 'chat' (default) or 'gmail'",
    )
    parser.add_argument(
        "--query",
        default="is:unread subject:[career]",
        help="Gmail search query (gmail mode only)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Poll interval in seconds (gmail mode only, default 60)",
    )
    parser.add_argument(
        "--thread",
        default="chat-main",
        help="Thread ID for chat session (default: 'chat-main', persisted across restarts)",
    )
    args = parser.parse_args()

    if args.mode == "gmail":
        run_gmail_trigger(query=args.query, poll_interval=args.interval)
    else:
        run_chat(thread_id=args.thread)
