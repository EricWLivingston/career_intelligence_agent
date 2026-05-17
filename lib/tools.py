import base64
import json
import os
from datetime import datetime, timezone
from email.mime.text import MIMEText
from typing import Literal

import httpx
from tavily import TavilyClient

import gspread
from google.oauth2.service_account import Credentials
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

@tool
def get_current_time() -> str:
    """Return the current date and time in ISO 8601 format (UTC) and a human-readable local format.

    Always call this tool when you need today's date, the current timestamp,
    or any relative date reference such as 'today', 'this week', or 'now'.
    """
    now_utc = datetime.now(timezone.utc)
    now_local = datetime.now()
    return json.dumps({
        "utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "local_date": now_local.strftime("%Y-%m-%d"),
        "local_datetime": now_local.strftime("%Y-%m-%d %H:%M:%S"),
        "day_of_week": now_local.strftime("%A"),
    })


_SA_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]
_GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]

_sheets_client: gspread.Client | None = None
_docs_service = None
_gmail_service = None
_tavily_client: TavilyClient | None = None


def _get_creds() -> Credentials:
    creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", "service_account.json")
    return Credentials.from_service_account_file(creds_path, scopes=_SA_SCOPES)


def _get_gmail_creds() -> OAuthCredentials:
    token_path = os.getenv("GMAIL_TOKEN_PATH", "gmail_token.json")
    client_secrets_path = os.getenv("GMAIL_CLIENT_SECRETS_PATH", "gmail_credentials.json")
    creds = None
    if os.path.exists(token_path):
        creds = OAuthCredentials.from_authorized_user_file(token_path, _GMAIL_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, _GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())
    return creds


def _get_gmail_service():
    global _gmail_service
    if _gmail_service is None:
        _gmail_service = build("gmail", "v1", credentials=_get_gmail_creds())
    return _gmail_service


def _get_client() -> gspread.Client:
    global _sheets_client
    if _sheets_client is None:
        _sheets_client = gspread.authorize(_get_creds())  # type: ignore[arg-type]
    return _sheets_client


def _get_docs_service():
    global _docs_service
    if _docs_service is None:
        _docs_service = build("docs", "v1", credentials=_get_gmail_creds())
    return _docs_service


def _get_sheet(spreadsheet_id: str, sheet_name: str) -> gspread.Worksheet:
    return _get_client().open_by_key(spreadsheet_id).worksheet(sheet_name)


def _get_tavily() -> TavilyClient:
    global _tavily_client
    if _tavily_client is None:
        _tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY", ""))
    return _tavily_client


@tool
def google_sheets_read(spreadsheet_id: str, sheet_name: str) -> str:
    """Read all rows from a Google Sheet. Returns all records as a JSON-like string."""
    records = _get_sheet(spreadsheet_id, sheet_name).get_all_records()
    return str(records)


@tool
def google_sheets_append(spreadsheet_id: str, sheet_name: str, row: list) -> str:
    """Append a new row to a Google Sheet. row is a list of values in column order (A, B, C, ...)."""
    _get_sheet(spreadsheet_id, sheet_name).append_row(row, value_input_option="USER_ENTERED")
    return "Row appended successfully."


@tool
def google_sheets_append_batch(spreadsheet_id: str, sheet_name: str, rows: list) -> str:
    """Append multiple rows to a Google Sheet in one call. rows is a list of row lists, each in column order (A, B, C, ...)."""
    _get_sheet(spreadsheet_id, sheet_name).append_rows(rows, value_input_option="USER_ENTERED")
    return f"{len(rows)} rows appended successfully."


@tool
def google_sheets_update_cell(
    spreadsheet_id: str, sheet_name: str, row_index: int, col_index: int, value: str
) -> str:
    """Update a single cell in a Google Sheet. row_index and col_index are 1-based."""
    _get_sheet(spreadsheet_id, sheet_name).update_cell(row_index, col_index, value)
    return f"Cell ({row_index}, {col_index}) updated to '{value}'."


@tool
def google_sheets_find_row(spreadsheet_id: str, sheet_name: str, query: str) -> str:
    """Find the first row containing query in any cell. Returns the row index (1-based) and row values."""
    sheet = _get_sheet(spreadsheet_id, sheet_name)
    cell = sheet.find(query)
    if cell is None:
        return f"No row found containing '{query}'."
    row_values = sheet.row_values(cell.row)
    return str({"row_index": cell.row, "values": row_values})


@tool
def google_sheets_column(spreadsheet_id: str, sheet_name: str, column: str) -> str:
    """Fetch all values from a single named column in a Google Sheet.

    Returns a flat JSON array of values — much cheaper than google_sheets_read
    when only one column is needed (e.g. duplicate-checking job_apply_link).

    Args:
        spreadsheet_id: The Google Sheets spreadsheet ID.
        sheet_name: The name of the worksheet tab.
        column: The header name of the column to fetch (e.g. 'job_apply_link').
    """
    sheet = _get_sheet(spreadsheet_id, sheet_name)
    records = sheet.get_all_records()
    values = [row.get(column) for row in records]
    return json.dumps(values, separators=(',', ':'))


def _extract_doc_text(doc: dict) -> str:
    """Flatten a Docs API document body into plain text."""
    chunks = []
    for element in doc.get("body", {}).get("content", []):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        for pe in paragraph.get("elements", []):
            text = pe.get("textRun", {}).get("content", "")
            chunks.append(text)
    return "".join(chunks)


@tool
def google_docs_create(title: str) -> str:
    """Create a new Google Doc with the given title.

    Args:
        title: The title for the new document.

    Returns a JSON string with document_id and doc_url.
    """
    doc = _get_docs_service().documents().create(body={"title": title}).execute()
    doc_id = doc["documentId"]
    return json.dumps({
        "document_id": doc_id,
        "doc_url": f"https://docs.google.com/document/d/{doc_id}/edit",
    })


@tool
def google_docs_read(document_id: str) -> str:
    """Read the full plain-text content of a Google Doc."""
    doc = _get_docs_service().documents().get(documentId=document_id).execute()
    return _extract_doc_text(doc)


@tool
def google_docs_write(document_id: str, text: str, is_new: bool = False) -> str:
    """Replace the entire content of a Google Doc with the given text.

    Always prefer this over multiple google_docs_append calls when writing
    the full body of a document.

    Args:
        document_id: The document ID returned by google_docs_create.
        text: The full content to write (replaces all existing content).
        is_new: Set True when writing to a freshly created doc to skip the prefetch.
    """
    service = _get_docs_service()
    requests = []
    if not is_new:
        doc = service.documents().get(documentId=document_id).execute()
        end_index = doc["body"]["content"][-1]["endIndex"] - 1
        if end_index > 1:
            requests.append({"deleteContentRange": {"range": {"startIndex": 1, "endIndex": end_index}}})
    requests.append({"insertText": {"location": {"index": 1}, "text": text}})
    service.documents().batchUpdate(documentId=document_id, body={"requests": requests}).execute()
    return "Document written successfully."


@tool
def google_docs_append(document_id: str, text: str) -> str:
    """Append text to the end of a Google Doc."""
    doc = _get_docs_service().documents().get(documentId=document_id).execute()
    end_index = doc["body"]["content"][-1]["endIndex"] - 1
    requests = [{"insertText": {"location": {"index": end_index}, "text": text}}]
    _get_docs_service().documents().batchUpdate(
        documentId=document_id, body={"requests": requests}
    ).execute()
    return "Text appended successfully."


@tool
def google_docs_replace_text(document_id: str, find: str, replacement: str) -> str:
    """Replace all occurrences of a string in a Google Doc."""
    requests = [
        {
            "replaceAllText": {
                "containsText": {"text": find, "matchCase": True},
                "replaceText": replacement,
            }
        }
    ]
    result = (
        _get_docs_service()
        .documents()
        .batchUpdate(documentId=document_id, body={"requests": requests})
        .execute()
    )
    count = (
        result.get("replies", [{}])[0]
        .get("replaceAllText", {})
        .get("occurrencesChanged", 0)
    )
    return f"Replaced {count} occurrence(s) of '{find}'."


def _decode_message_body(payload: dict) -> str:
    """Recursively extract plain-text body from a Gmail message payload."""
    mime_type = payload.get("mimeType", "")
    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        text = _decode_message_body(part)
        if text:
            return text
    return ""


def _get_header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


@tool
def gmail_read(query: str = "", max_results: int = 10, full_body: bool = False) -> str:
    """Read emails from Gmail.

    Args:
        query: Gmail search query (e.g. 'from:alice@example.com', 'subject:offer', 'is:unread').
               Leave empty to fetch the most recent emails.
        max_results: Maximum number of messages to return (default 10).
        full_body: If True, fetch the full message body. Default False returns only
                   id, subject, from, to, date, and snippet (faster — avoids N serial fetches).

    Returns a JSON string with a list of messages.
    """
    svc = _get_gmail_service()
    result = svc.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    messages = result.get("messages", [])
    if not messages:
        return json.dumps([])

    output = []
    for msg_ref in messages:
        fmt = "full" if full_body else "metadata"
        msg = svc.users().messages().get(userId="me", id=msg_ref["id"], format=fmt).execute()
        headers = msg.get("payload", {}).get("headers", [])
        entry: dict = {
            "id": msg["id"],
            "subject": _get_header(headers, "Subject"),
            "from": _get_header(headers, "From"),
            "to": _get_header(headers, "To"),
            "date": _get_header(headers, "Date"),
            "snippet": msg.get("snippet", ""),
        }
        if full_body:
            entry["body"] = _decode_message_body(msg.get("payload", {}))
        output.append(entry)
    return json.dumps(output, separators=(',', ':'))


@tool
def gmail_send(to: str, subject: str, body: str) -> str:
    """Send an email via Gmail.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Plain-text email body.

    Returns a confirmation with the sent message ID.
    """
    svc = _get_gmail_service()
    mime = MIMEText(body)
    mime["to"] = to
    mime["subject"] = subject
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
    sent = svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    return f"Email sent. Message id: {sent['id']}"



def _jsearch_headers() -> dict:
    api_key = os.getenv("JSEARCH_API_KEY", "")
    return {"x-api-key": api_key}


_JSEARCH_BASE = "https://api.openwebninja.com/jsearch"


def _summarize_job_descriptions(data: dict) -> dict:
    jobs = data.get("data", [])
    if not jobs:
        return data
    descriptions = [job.get("job_description", "") for job in jobs]
    prompt = (
        "Summarize each job description below in 50 words or less. "
        "Return only a JSON array of strings (one summary per description, same order). "
        "No other text.\n\n"
        + "\n\n---\n\n".join(f"Job {i + 1}:\n{d}" for i, d in enumerate(descriptions))
    )
    llm = ChatOpenAI(model="gpt-4.1-nano")
    response = llm.invoke([HumanMessage(content=prompt)])
    summaries = json.loads(response.content)
    for job, summary in zip(jobs, summaries):
        job["job_description"] = summary
    return data


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for current information.

    Use for: company culture (Glassdoor, Blind, Reddit reviews), salary and compensation
    benchmarks, funding rounds and financial health, recent company news, layoffs,
    interview experiences, and job market trends.

    Args:
        query: Search query, e.g. 'Anduril Industries Glassdoor reviews 2026'.
        max_results: Number of results to return (default 5, max 10).

    Returns a JSON array of {title, url, content} results.
    """
    results = _get_tavily().search(query=query, max_results=max_results)
    output = [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", "")[:500],
        }
        for r in results.get("results", [])
    ]
    return json.dumps(output, separators=(',', ':'))


@tool
def jsearch_request(
    endpoint: Literal["search", "job-details"],
    query: str | None = None,
    page: int = 1,
    num_pages: int = 1,
    date_posted: str = "all",
    remote_jobs_only: bool = False,
    employment_types: str | None = None,
    job_requirements: str | None = None,
    country: str = "us",
    job_id: str | None = None,
    extended_publisher_details: bool = False,
) -> str:
    """Make a single request to the JSearch API and return the result.

    Reads JSEARCH_API_KEY from the environment.

    Args:
        endpoint: Which JSearch endpoint to call — 'search' or 'job-details'.
        query: (search only) Free-text job search query, e.g. 'software engineer in Austin'.
        page: (search only) Result page number (default 1).
        num_pages: (search only) Number of pages to return (default 1, max 20).
        date_posted: (search only) Filter by posting age — 'all', 'today', '3days', 'week', 'month'.
        remote_jobs_only: (search only) If True, return only remote positions.
        employment_types: (search only) Comma-separated types, e.g. 'FULLTIME,CONTRACTOR'.
        job_requirements: (search only) Comma-separated requirements, e.g. 'under_3_years_experience'.
        country: (search only) Two-letter country code for the job market (default 'us').
        job_id: (job-details only) Job ID returned by a prior search (field: job_id).
        extended_publisher_details: (job-details only) If True, include additional publisher metadata.

    For 'search' results, each job's description is replaced with a concise 50-100 word summary.
    Returns a JSON string with the API response data.
    """
    request_headers = {"Accept": "application/json", **_jsearch_headers()}

    if endpoint == "search":
        params: dict = {
            "query": query,
            "page": page,
            "num_pages": num_pages,
            "date_posted": date_posted,
            "remote_jobs_only": str(remote_jobs_only).lower(),
            "country": country,
        }
        if employment_types:
            params["employment_types"] = employment_types
        if job_requirements:
            params["job_requirements"] = job_requirements
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            response = client.get(f"{_JSEARCH_BASE}/search", params=params, headers=request_headers)
        response.raise_for_status()
        data = _summarize_job_descriptions(response.json())
        return json.dumps(data, separators=(',', ':'))

    # endpoint == "job-details"
    params = {
        "job_id": job_id,
        "extended_publisher_details": str(extended_publisher_details).lower(),
    }
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        response = client.get(f"{_JSEARCH_BASE}/job-details", params=params, headers=request_headers)
    response.raise_for_status()
    return json.dumps(response.json(), separators=(',', ':'))
