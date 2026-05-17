---
name: critic
description: Critic agent integration protocol — load before invoking critic_agent to audit any sub-agent output
---

# Critic Integration

- Always ask the user for approval before sending any sub-agent output to the critic.
- Pass `agent_output`, `source_agent`, and a compacted summary of `original_inputs`.
- If the critic returns flags, include an "⚠ Critic flagged:" note in the response. Never suppress flags.
- A "critical" flag means a claim could lead to a bad decision — surface it prominently.
- Do not re-score or alter the original agent output based on critic feedback; only annotate.
