# Sub-Agent Input Schemas
> All fields accept `null`. `sessionId` is required on every call.

---

## 1. Job Researcher

```json
{
  "type": "object",
  "properties": {
    "criteria": {
      "oneOf": [{ "type": "string" }, { "type": "null" }],
      "description": "Job search keywords extracted from the user's guiding principles (e.g. 'Electrical Engineer', 'Hardware Engineer')"
    },
    "task": {
      "oneOf": [{ "type": "string" }, { "type": "null" }],
      "description": "Specific job searching task parsed from user intent"
    },
    "resume_summary": {
      "oneOf": [{ "type": "string" }, { "type": "null" }],
      "description": "Brief summary of the user's skills and experience level"
    },
    "sessionId": {
      "oneOf": [{ "type": "string" }, { "type": "null" }],
      "description": "Unique session identifier generated for this sub-agent call"
    }
  },
  "required": ["sessionId"]
}
```

---

## 2. Scorer / Analyst

```json
{
  "type": "object",
  "properties": {
    "jobs": {
      "oneOf": [{ "type": "array" }, { "type": "null" }],
      "description": "One or more job listing objects (JSON) to evaluate"
    },
    "resume": {
      "oneOf": [{ "type": "string" }, { "type": "null" }],
      "description": "The user's resume or a structured summary of their experience"
    },
    "principles": {
      "oneOf": [{ "type": "string" }, { "type": "null" }],
      "description": "The user's guiding principles document"
    },
    "scoring_rubric": {
      "oneOf": [{ "type": "string" }, { "type": "object" }, { "type": "null" }],
      "description": "Scoring priority weights: culture_sentiment 0.30, compensation 0.25, skill_alignment 0.20, growth_opportunity 0.15, company_health 0.10"
    },
    "sessionId": {
      "oneOf": [{ "type": "string" }, { "type": "null" }],
      "description": "Unique session identifier generated for this sub-agent call"
    }
  },
  "required": ["sessionId"]
}
```

---

## 3. Report Writer

```json
{
  "type": "object",
  "properties": {
    "subject": {
      "oneOf": [{ "type": "string" }, { "type": "null" }],
      "description": "The role, company, or topic to report on"
    },
    "scored_job": {
      "oneOf": [{ "type": "object" }, { "type": "null" }],
      "description": "Scorer output for this role — null if not available"
    },
    "resume_summary": {
      "oneOf": [{ "type": "string" }, { "type": "null" }],
      "description": "Summary of the user's experience and goals"
    },
    "principles": {
      "oneOf": [{ "type": "string" }, { "type": "null" }],
      "description": "The user's guiding principles"
    },
    "report_type": {
      "oneOf": [
        { "type": "string", "enum": ["role_deep_dive", "company_profile", "market_overview"] },
        { "type": "null" }
      ],
      "description": "One of: role_deep_dive | company_profile | market_overview"
    },
    "sessionId": {
      "oneOf": [{ "type": "string" }, { "type": "null" }],
      "description": "Unique session identifier generated for this sub-agent call"
    }
  },
  "required": ["sessionId"]
}
```

---

## 4. Interview Coach

```json
{
  "type": "object",
  "properties": {
    "role": {
      "oneOf": [{ "type": "string" }, { "type": "null" }],
      "description": "The job title, company, and job description"
    },
    "resume": {
      "oneOf": [{ "type": "string" }, { "type": "null" }],
      "description": "The user's resume or experience summary"
    },
    "report": {
      "oneOf": [{ "type": "string" }, { "type": "object" }, { "type": "null" }],
      "description": "Deep-dive report on this role — null if not available"
    },
    "scored_job": {
      "oneOf": [{ "type": "object" }, { "type": "null" }],
      "description": "Scorer output for this role — null if not available"
    },
    "request_type": {
      "oneOf": [
        { "type": "string", "enum": ["full_prep", "question_bank", "mock_interview", "learning_plan", "company_research_brief"] },
        { "type": "null" }
      ],
      "description": "One of: full_prep | question_bank | mock_interview | learning_plan | company_research_brief"
    },
    "sessionId": {
      "oneOf": [{ "type": "string" }, { "type": "null" }],
      "description": "Unique session identifier generated for this sub-agent call"
    }
  },
  "required": ["sessionId"]
}
```

---

## 5. Application Tracker

```json
{
  "type": "object",
  "properties": {
    "action": {
      "oneOf": [
        { "type": "string", "enum": ["log_new", "update_status", "query", "remind", "summarize_pipeline"] },
        { "type": "null" }
      ],
      "description": "One of: log_new | update_status | query | remind | summarize_pipeline"
    },
    "job_data_single": {
      "oneOf": [{ "type": "object" }, { "type": "null" }],
      "description": "A single job object with fields: title, company, url, date_applied, status, notes"
    },
    "job_data_multi": {
      "oneOf": [{ "type": "array" }, { "type": "null" }],
      "description": "An array of job objects with fields: title, company, url, date_applied, status, notes"
    },
    "sessionId": {
      "oneOf": [{ "type": "string" }, { "type": "null" }],
      "description": "Unique session identifier generated for this sub-agent call"
    }
  },
  "required": ["sessionId"]
}
```

---

## 6. Critic Agent

```json
{
  "type": "object",
  "properties": {
    "agent_output": {
      "oneOf": [{ "type": "string" }, { "type": "object" }, { "type": "array" }, { "type": "null" }],
      "description": "The raw output (JSON or text) produced by the source agent"
    },
    "source_agent": {
      "oneOf": [{ "type": "string" }, { "type": "null" }],
      "description": "Name of the agent that produced the output (e.g. scorer_analyst, report_writer)"
    },
    "original_inputs": {
      "oneOf": [{ "type": "string" }, { "type": "object" }, { "type": "null" }],
      "description": "Compacted summary of the inputs the source agent received"
    },
    "sessionId": {
      "oneOf": [{ "type": "string" }, { "type": "null" }],
      "description": "Unique session identifier generated for this sub-agent call"
    }
  },
  "required": ["sessionId"]
}
```
