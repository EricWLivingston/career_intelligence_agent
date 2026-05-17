# main.py — Code Walkthrough

## Overview

`main.py` is the entry point for the Career Intelligence Agent. It wires together a multi-agent AI system and exposes two ways to run it: an interactive terminal chat, or an automated Gmail monitor that processes incoming emails as tasks.

---

## Imports

```python
import argparse, json, sys, time, uuid
from pathlib import Path
from dotenv import load_dotenv
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage
from lib.tools import (...)
from lib.prompts import (...)
```

- **Standard library** (`argparse`, `json`, `sys`, `time`, `uuid`, `Path`) — used for CLI parsing, file I/O, timing, and generating unique session IDs.
- **`dotenv`** — loads API keys from the `.env` file into environment variables so the code never has credentials hardcoded.
- **`deepagents`** — the framework that builds and runs the multi-agent system.
- **`FilesystemBackend`** — gives agents a virtual filesystem to read/write files during a session.
- **`MemorySaver`** — LangGraph's in-memory checkpointer; stores conversation history so the agent remembers what was said earlier in a session.
- **`lib.tools`** — all the external integrations (Gmail, Google Sheets, Google Docs, web search, JSearch job API).
- **`lib.prompts`** — the system prompt strings for each agent.

---

## `_cached()` — Prompt Caching Helper

```python
def _cached(text: str) -> SystemMessage:
    return SystemMessage(content=[{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}])
```

Every agent has a long system prompt. Without caching, Anthropic would re-process (and re-charge for) that prompt on every single message. The `cache_control: ephemeral` flag tells Anthropic's API to cache the prompt for up to 5 minutes, so repeated calls within a session only pay for the new user message tokens, not the full system prompt each time.

---

## `SUBAGENTS` — The Agent Roster

```python
SUBAGENTS = [
    {"name": "job_researcher", ...},
    {"name": "scorer_analyst", ...},
    {"name": "report_writer", ...},
    {"name": "interview_coach", ...},
    {"name": "job_cataloguer", ...},
    {"name": "critic_agent", ...},
]
```

Each dictionary defines one specialist agent. The orchestrator delegates work to these agents based on what the user asks for. Each entry specifies:

| Key | Purpose |
|-----|---------|
| `name` | Identifier the orchestrator uses to route tasks |
| `description` | Tells the orchestrator when to use this agent |
| `model` | Which Claude model to use (Haiku for speed/cost, Sonnet for quality) |
| `system_prompt` | The agent's instructions, wrapped in `_cached()` |
| `tools` | The specific integrations this agent is allowed to call |

### Why different models per agent?

- **Haiku** (`job_researcher`, `job_cataloguer`) — fast, cheap. Used for mechanical tasks like fetching job listings and logging data where reasoning depth doesn't matter.
- **Sonnet** (`scorer_analyst`, `report_writer`, `interview_coach`, `critic_agent`) — more capable. Used where judgment, writing quality, and analytical depth matter.

### Agent responsibilities

- **`job_researcher`** — searches for jobs via JSearch API and reads the Google Sheet to understand existing listings.
- **`scorer_analyst`** — scores jobs against the user's resume and criteria, writes analysis to Google Docs.
- **`report_writer`** — produces deep-dive reports on companies, roles, or markets.
- **`interview_coach`** — builds interview prep materials, question banks, and study plans.
- **`job_cataloguer`** — logs jobs into the Google Sheet tracker, updates application statuses, sends Gmail confirmations.
- **`critic_agent`** — reviews other agents' outputs for hallucinations, factual errors, and scoring inconsistencies. Acts as a quality gate.

---

## `build_agents()` — Assembling the System

```python
def build_agents():
    return create_deep_agent(
        name="orchestrator",
        model="claude-haiku-4-5-20251001",
        tools=[get_current_time, google_docs_read, gmail_read, gmail_send],
        system_prompt=_cached(ORCHESTRATOR_PROMPT),
        subagents=SUBAGENTS,
        backend=FilesystemBackend(root_dir=".", virtual_mode=True),
        skills=["./skills/"],
        checkpointer=MemorySaver(),
    )
```

This creates the top-level orchestrator agent. Key decisions:

- **Orchestrator uses Haiku** — it primarily routes tasks to subagents rather than doing heavy reasoning itself, so the cheaper/faster model is appropriate.
- **`FilesystemBackend(virtual_mode=True)`** — agents can read/write files during a session without actually touching disk (changes are sandboxed). This allows agents to pass data to each other through "files" without side effects.
- **`skills=["./skills/"]`** — loads the skill definitions from the `skills/` directory. Skills are markdown files that give the orchestrator reusable behavioral patterns (e.g., how to handle Gmail triggers, how to delegate, how to format output).
- **`checkpointer=MemorySaver()`** — enables conversation memory within a session. Without this, the agent would forget everything said earlier in the same conversation.

---

## `get_agent()` — Singleton Pattern

```python
_agent = None

def get_agent():
    global _agent
    if _agent is None:
        _agent = build_agents()
    return _agent
```

Building the agent system (loading models, skills, backends) takes time. This pattern ensures it only happens once — the first time `get_agent()` is called — and every subsequent call reuses the same instance. This matters especially in the Gmail polling loop, which calls `run_agent()` repeatedly.

---

## `_extract_response()` — Parsing Agent Output

```python
def _extract_response(result: dict) -> str:
    messages = result.get("messages", [])
    if not messages:
        return ""
    content = messages[-1].content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    return str(content)
```

LangGraph returns agent results as a dictionary containing a list of messages. The final message is the agent's response, but its `content` field can be either a plain string or a list of content blocks (which happens when the model uses tool calls or cache markers). This function normalizes both cases into a single plain string.

---

## `run_agent()` — Single Invocation

```python
def run_agent(message: str, thread_id: str) -> str:
    result = get_agent().invoke(
        {"messages": [{"role": "user", "content": message}]},
        config={"configurable": {"thread_id": thread_id}},
    )
    return _extract_response(result)
```

Sends one message to the agent system and returns the response. The `thread_id` is how LangGraph isolates conversation history — two different thread IDs mean two independent conversations with no shared memory. The same thread ID means the agent remembers all prior messages in that thread.

---

## `run_chat()` — Interactive Terminal Mode

```python
def run_chat() -> None:
    thread_id = f"chat-{uuid.uuid4().hex[:8]}"
    print(f"Career Intelligence Agent ready (session: {thread_id}). Type 'exit' to quit.")
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() in ("exit", "quit"):
            break
        if not user_input:
            continue
        print(f"\nAgent: {run_agent(user_input, thread_id)}")
```

Starts a conversation loop in the terminal. A random `thread_id` is generated at the start so each chat session gets its own isolated memory. The loop reads input, skips blank lines, and prints the agent response until the user types `exit` or `quit`.

---

## Gmail Trigger — Automated Email Processing

### Persistence: tracking processed emails

```python
_PROCESSED_IDS_FILE = Path("tmp/gmail_processed.json")

def _load_processed_ids() -> set:
    ...

def _save_processed_ids(ids: set) -> None:
    ...
```

To avoid processing the same email twice across restarts, the system stores a set of already-handled Gmail message IDs in a JSON file. On startup it loads this file; after processing each email it saves the updated set.

### The polling loop

```python
def run_gmail_trigger(query: str = "is:unread subject:[career]", poll_interval: int = 60) -> None:
    processed_ids = _load_processed_ids()
    while True:
        try:
            emails = json.loads(gmail_read(query=query, max_results=10, full_body=True))
            for email in emails:
                if email["id"] in processed_ids:
                    continue
                user_message = (
                    f"[Gmail trigger] You received an email.\n"
                    f"From: {email['from']}\nSubject: {email['subject']}\n..."
                )
                response = run_agent(user_message, thread_id=f"gmail-{email['id']}")
                processed_ids.add(email["id"])
                _save_processed_ids(processed_ids)
        except Exception as exc:
            print(f"[gmail trigger error] {exc}", file=sys.stderr)
        time.sleep(poll_interval)
```

Every `poll_interval` seconds (default: 60), it queries Gmail for unread emails matching the search query (default: emails with `[career]` in the subject). For each new email:

1. Formats the email as a natural-language message prefixed with `[Gmail trigger]` — this prefix signals the orchestrator to load the `triggers` skill, which tells it how to handle email-sourced requests.
2. Passes it to `run_agent()` with a thread ID tied to the email's Gmail ID, so if the same email somehow triggers again, the agent has context from the prior run.
3. Marks the email as processed and saves the ID to disk.

Errors are caught and printed to stderr so a network blip or API failure doesn't crash the whole polling loop.

---

## CLI Entry Point

```python
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Career Intelligence Agent")
    parser.add_argument("mode", nargs="?", default="chat", choices=["chat", "gmail"])
    parser.add_argument("--query", default="is:unread subject:[career]")
    parser.add_argument("--interval", type=int, default=60)
    args = parser.parse_args()

    if args.mode == "gmail":
        run_gmail_trigger(query=args.query, poll_interval=args.interval)
    else:
        run_chat()
```

The `if __name__ == "__main__"` guard ensures this block only runs when the file is executed directly (not when imported as a module by other code).

**Usage examples:**

```bash
# Interactive chat (default)
python main.py

# Gmail polling with defaults
python main.py gmail

# Gmail polling with custom query and interval
python main.py gmail --query "is:unread subject:[job]" --interval 30
```
