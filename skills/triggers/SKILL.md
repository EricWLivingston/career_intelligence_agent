---
name: triggers
description: Gmail and schedule trigger handling — load when invoked via email or cron schedule
---

# Trigger Handling

## Gmail Trigger
- Read the incoming email with `gmail_read`.
- Parse the email body as the user's intent.
- Execute the appropriate sub-agent flow.
- Reply via `gmail_send` using HTML formatting (load the output_format skill).
- Be thorough — treat the email body as a full task brief.

## Schedule Trigger (Daily Digest)
1. Read resume and principles docs with `google_docs_read`.
2. Delegate to `job_researcher` for today's listings.
3. Delegate to `scorer_analyst` for scores.
4. Compile digest: top-scored jobs, pipeline reminders (via `job_cataloguer`), any flagged actions.
5. Send to user's Gmail as an HTML digest email (load the output_format skill).
6. Write digest to the `daily_digest` doc (ID: 1StcOa52XsCSrN3SyPEJPX4J1_iuzZA-0wKLIbVWzd7o).
