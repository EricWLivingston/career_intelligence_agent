# Optimization Review — Career Intelligence Agent

> Scope: execution speed, token efficiency, and unused tools across `lib/tools.py`, `lib/prompts.py`, `main.py`.
> Ordered by type, then estimated impact.

---

## Unused Tools

### U1. `google_docs_read` — Assigned to 3 Agents, Mentioned in None of Their Prompts

**File:** `main.py:54, 61, 68`; `lib/prompts.py` (scorer_analyst, report_writer, interview_coach `<tools>` blocks)

`scorer_analyst`, `report_writer`, and `interview_coach` each have `google_docs_read` in their tool list. None of their prompts mention it — the `<tools>` block for each agent lists `web_search`, `google_docs_create`, `google_docs_write`, `google_docs_append`, `google_docs_replace_text`, and nothing about `google_docs_read`. The orchestrator summarizes all docs before delegation (prompts.py:42: "summarize all docs to ≤150 words"), so these agents never need to fetch a doc independently.

**Fix:** Remove `google_docs_read` from the tool lists of `scorer_analyst`, `report_writer`, and `interview_coach` in `main.py`. No prompt changes needed.

**Impact:** Eliminates a ghost tool from 3 agents — reduces tool-list context token overhead and removes any risk of the model attempting unnecessary doc reads.

---

### U2. `gmail_create_draft` — Defined in tools.py, Assigned to No Agent

**File:** `lib/tools.py:319–336`

`gmail_create_draft` is a fully implemented tool not assigned to any agent in `main.py`. (Noted in passdown.md as "available for future use.")

**Fix:** Either assign to `job_cataloguer` for draft follow-up emails, or remove. If keeping for future use, no action needed — it costs nothing unless assigned.

**Impact:** No runtime cost. Cleanup only.

---

### U3. `google_sheets_append_batch` — Missing from job_cataloguer `<tools>` Block

**File:** `lib/prompts.py:388–398` (tools block), `lib/prompts.py:423` (action description), `main.py:80`

`google_sheets_append_batch` is correctly assigned in `main.py` and referenced in the `log_new` action description, but it is **not listed in the `<tools>` block** of `JOB_CATALOGUER_PROMPT`. The model may not recognize it as callable if it doesn't see it in the tool inventory section.

**Fix:** Add to the `<tools>` block (prompts.py ~line 396):
```
- google_sheets_append_batch: append multiple rows at once — use this for log_new with multiple jobs.
```

**Impact:** Ensures Haiku knows the tool is available before reading the action description that calls for it.

---

## Speed Optimizations

### S1. `gmail_read` — N+1 Serial API Calls (High Impact)

**File:** `lib/tools.py:298–316`

`gmail_read` fetches message IDs from the list endpoint, then calls `messages().get(format="full")` once per message in a `for` loop. For `max_results=10`, that is 11 sequential HTTP round-trips (~200–400ms each). Total wait: 2–5 seconds before the orchestrator sees a single email.

```python
# current — serial full fetches
for msg_ref in messages:
    msg = svc.users().messages().get(userId="me", id=msg_ref["id"], format="full").execute()
```

**Fix:** Use `format="metadata"` by default — it returns subject, from, date, and snippet without a second fetch. Add an optional `full_body: bool = False` parameter for cases where body content is required.

**Impact:** Cuts trigger-flow latency by 2–4 seconds on every Gmail read. The orchestrator only needs subject + snippet for intent routing.

---

### S2. `_summarize_job_descriptions` — New `ChatOpenAI` Client on Every Call (Medium Impact)

**File:** `lib/tools.py` (inside `_summarize_job_descriptions`)

A new `ChatOpenAI(model="gpt-4.1-nano")` instance is constructed on every call. This also introduces a second paid API dependency (OpenAI) alongside Claude. The summarizer is called inside `jsearch_request` for every search result set.

**Fix (short term):** Promote to a module-level singleton:
```python
_summarizer_llm: ChatOpenAI | None = None
def _get_summarizer_llm() -> ChatOpenAI:
    global _summarizer_llm
    if _summarizer_llm is None:
        _summarizer_llm = ChatOpenAI(model="gpt-4.1-nano")
    return _summarizer_llm
```

**Fix (better):** Remove `_summarize_job_descriptions` entirely — the downstream Claude agents are capable of summarizing what they need from raw descriptions.

**Impact:** Eliminates a second API dependency and removes per-search GPT latency (~200–500ms). Simplifies the tool.

---

### S3. `jsearch_request` — New `httpx.Client` on Every Call (Medium Impact)

**File:** `lib/tools.py` (inside `jsearch_request`)

`httpx.Client` is constructed and closed inside each `jsearch_request` call, losing connection pooling and keep-alive between calls.

**Fix:** Module-level singleton:
```python
_http_client = httpx.Client(timeout=30, follow_redirects=True)
```

**Impact:** Saves TCP handshake overhead. More noticeable when `job_researcher` runs two searches (initial + broadened fallback) in the same session.

---

### S4. Unbounded Session Context (Medium Impact — Critical Before Production)

**File:** `main.py:111`

`thread_id = "career-session-1"` is hardcoded. Every invocation appends to this single thread indefinitely. After a few daily digest runs, the context overhead per call becomes significant.

**Fix (short term):** Per-session UUID:
```python
import uuid
config = {"configurable": {"thread_id": f"session-{uuid.uuid4().hex[:8]}"}}
```

**Fix (long term):** LangGraph message summarization — after N messages, compact history into a `SystemMessage` and discard older messages.

**Impact:** Prevents token cost creep and latency growth. Must fix before production.

---

### S5. `google_docs_write` — Unnecessary GET for Fresh Docs (Low Impact)

**File:** `lib/tools.py:204–222`

`google_docs_write` always fetches the existing doc to find its end index before clearing and rewriting. For a freshly-created doc (the common case: `google_docs_create` → `google_docs_write`), this GET is a wasted round-trip.

**Fix:** Add optional `is_new: bool = False` parameter — skip the GET when true.

**Impact:** Saves one API round-trip per doc-creation workflow. Small but free.

---

## Token Optimizations

### T1. `gmail_read` — Returns Indented JSON (Medium Impact)

**File:** `lib/tools.py:316`

```python
return json.dumps(output, indent=2)   # ← wastes ~20-30% tokens
```

All other tools already use `separators=(',', ':')`. `gmail_read` was missed.

**Fix:**
```python
return json.dumps(output, separators=(',', ':'))
```

**Impact:** ~20–30% token reduction on every gmail_read response. At 10 messages, saves ~500–1,000 tokens per read.

---

### T2. `jsearch_request` — Still Returns Indented JSON (High Impact)

**File:** `lib/tools.py:466, 476`

The current file state shows both return paths still use `indent=2`:
```python
return json.dumps(data, indent=2)             # line 466
return json.dumps(response.json(), indent=2)  # line 476
```

**Fix:** Change both to `separators=(',', ':')`.

**Impact:** Saves ~2,000–4,000 tokens per job search call. Multiplied across the researcher → scorer chain, meaningful per-run savings.

---

### T3. `critic_agent` — No Upper Bound on `web_search` Calls (Low-Medium Impact)

**File:** `lib/prompts.py:470`

`scorer_analyst` explicitly caps at "4 searches per job". `critic_agent` only says "spot-check at least 3 key facts" with no upper bound. For an audit of 5 scored jobs, the critic could run 15+ searches.

**Fix:** Add an explicit cap to the critic's web_search instruction:
```
Spot-check at least 3 key facts per audit. Cap total searches at 5 per audited output.
```

**Impact:** Prevents runaway search cost on multi-job scoring audits.

---

## Summary Table

| ID | File | Issue | Type | Impact | Status |
|---|---|---|---|---|---|
| U1 | main.py | `google_docs_read` on 3 agents, never used by their prompts | Unused tool | Medium | ✓ Done |
| U2 | tools.py | `gmail_create_draft` not assigned to any agent | Unused tool | Cleanup | ✓ Done |
| U3 | prompts.py | `google_sheets_append_batch` missing from job_cataloguer `<tools>` block | Prompt gap | Medium | ✓ Done |
| S1 | tools.py | `gmail_read` N+1 serial full fetches | Speed | High | ✓ Done |
| S2 | tools.py | New `ChatOpenAI` client per summarize call + GPT dependency | Speed + Cost | Medium | Outstanding |
| S3 | tools.py | New `httpx.Client` per JSearch call | Speed | Medium | Outstanding |
| S4 | main.py | Single unbounded thread context | Speed + Cost | Medium (critical) | Outstanding |
| S5 | tools.py | `google_docs_write` fetches doc for fresh writes | Speed | Low | ✓ Done |
| T1 | tools.py | `gmail_read` returns indented JSON | Tokens | Medium | ✓ Done |
| T2 | tools.py | `jsearch_request` returns indented JSON (lines 466, 476) | Tokens | High | ✓ Done |
| T3 | prompts.py | `critic_agent` web_search has no upper cap | Tokens | Low-Medium | ✓ Done |

---

## Previously Completed

| Item | Description |
|---|---|
| `google_sheets_column` | Dedicated single-column tool added; job_researcher uses it for dedup instead of full sheet read |
| `google_sheets_read` valid JSON | Returns `json.dumps` instead of Python `str(records)` |
| Delegation skill inlined | Orchestrator prompt includes delegation rules directly; no skill-load round-trip per call |
| Prompt caching | All system prompts wrapped with `cache_control: {"type": "ephemeral"}` via `_cached()` |
| `critic_agent` web_search tool | Tool added to agent's tool list in main.py |
| `job_id` dedup key | job_researcher uses `column="job_id"` for duplicate checking |
| `google_sheets_append_batch` | Batch tool added to tools.py and job_cataloguer; log_new action updated to use it |
