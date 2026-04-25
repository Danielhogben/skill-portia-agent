# Portia Agent

Build approval-gated AI agents with plan creation, approval workflows, monitoring, and rollback capabilities.

**Category:** AI Agents

**Language:** Python

## Quick Start

```bash
python3 portia_agent.py help
```

## Commands

| Command | Description |
|---------|-------------|
| `---------` | ------------- |
| `create <agent> --guardrails <rules>` | Create an agent with guardrails and approval gates |
| `plan <agent> <objective>` | Generate a structured plan with verification steps |
| `approve <plan_id> [--reject --reason <r>]` | Approve or reject pending agent actions |
| `monitor <agent> [--tail N]` | Track agent execution with structured logging |
| `rollback <agent> --to <checkpoint>` | Revert agent state to a previous checkpoint |

## Files

- `SKILL.md` (1KB)
- `portia_agent.py` (18KB)

---

*Part of [Hermes Skills](https://github.com/Danielhogben/hermes-skills) — the world's largest open-source AI agent skill collection.*
