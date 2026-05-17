---
name: delegation
description: Per-agent input specs and delegation rules — load before calling any sub-agent
---

# Delegation Rules

## General Rules
- Always pass the current date to each sub-agent.
- Summarize any document passed to a sub-agent in 150 words or less.
- All inputs to sub-agents must be JSON.
- Chain multi-step flows sequentially: researcher → scorer → critic → output.
- On any sub-agent error: abort and report. Never retry.
- Send each agent only the context listed below — nothing more.

## Per-Agent Input Specs

### job_researcher
Pass: `criteria` (keywords: "Electrical Engineer" OR "Hardware Engineer" only), `task`, `resume_summary`, `spreadsheet_id` (1wlXCsRVph7DKB_Jv0MaYlji9p_aUIUlC3QYfspJQMCc), `sheet_name` (job_catalogue)
Omit: full_resume, principles_document, scored_jobs, report, action

### scorer_analyst
Pass: `jobs` (JSON), `resume`, `principles`, `scoring_rubric` (culture_sentiment 0.30, compensation 0.25, skill_alignment 0.20, growth_opportunity 0.15, company_health 0.10)
Omit: criteria, report, request_type, action

### report_writer
Pass: `subject`, `scored_job` (if available), `resume_summary`, `principles`, `report_type` (role_deep_dive | company_profile | market_overview)
Omit: criteria, jobs, action, request_type

### interview_coach
Pass: `role`, `resume`, `report` (if available), `scored_job` (if available), `request_type` (full_prep | question_bank | mock_interview | learning_plan | company_research_brief)
Omit: criteria, principles, jobs, action

### job_cataloguer
Pass: `action` (log_new | update_status | query | remind | summarize_pipeline), `job_data` (title, company, URL, date, status, notes only), `spreadsheet_id` (1wlXCsRVph7DKB_Jv0MaYlji9p_aUIUlC3QYfspJQMCc), `sheet_name` (job_catalogue)
Omit: resume, principles, scored_job, criteria, report, request_type

### critic_agent
Pass: `agent_output`, `source_agent`, `original_inputs` (compacted summary)
Omit: criteria, principles, action, request_type, report_type
