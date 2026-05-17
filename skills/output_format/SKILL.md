---
name: output-format
description: HTML email and document formatting rules — load before composing any Gmail or Doc output
---

# Output Formatting

## Gmail and Schedule Emails (HTML)
Wrap the entire body in:
```
<div style="font-family:Arial,sans-serif;font-size:14px;line-height:1.6;color:#222;max-width:640px">
```

- Section headers: `<h3 style="margin:24px 0 6px;border-bottom:1px solid #ddd;padding-bottom:4px">`
- Bullet lists: `<ul style="margin:4px 0 12px;padding-left:20px">` with `<li style="margin-bottom:4px">` per item
- One fact or action per bullet. No multi-sentence bullets.
- Job table: `<table style="width:100%;border-collapse:collapse;font-size:13px">` with `<th style="text-align:left;border-bottom:2px solid #ddd;padding:6px">` and `<td style="padding:6px;border-bottom:1px solid #eee">`
- Section spacing: `<div style="height:8px"></div>` between major blocks
- ≤400 words total. Cut rationale first, then condense flags, then trim next actions.
- End with one sentence. No sign-off or closing paragraph.
- Never use markdown, ASCII dividers, or raw newlines — HTML only.

## Sheets
Instruct job_cataloguer with structured field data per its tracking schema.

## Docs
Instruct report_writer to produce a fully formatted document. All long-form analysis belongs in the Doc — never reproduce it in the email summary.
