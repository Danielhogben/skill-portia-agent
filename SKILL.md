# Portia Agent

Enterprise agent framework with guardrails, approval workflows, structured monitoring, and state rollback.

## What it does

Creates agents with configurable guardrails and approval gates, generates structured plans with verification steps, manages approval workflows for sensitive actions, tracks execution with structured logging, and supports state rollback to previous checkpoints.

## Commands

| Command | Description |
|---------|-------------|
| `create <agent> --guardrails <rules>` | Create an agent with guardrails and approval gates |
| `plan <agent> <objective>` | Generate a structured plan with verification steps |
| `approve <plan_id> [--reject --reason <r>]` | Approve or reject pending agent actions |
| `monitor <agent> [--tail N]` | Track agent execution with structured logging |
| `rollback <agent> --to <checkpoint>` | Revert agent state to a previous checkpoint |

## Examples

```bash
python3 portia_agent.py create deploy-agent --guardrails "no-prod,no-delete,cost-limit-100"
python3 portia_agent.py plan deploy-agent "Deploy v2.3 to staging"
python3 portia_agent.py approve abc123
python3 portia_agent.py monitor deploy-agent --tail 20
python3 portia_agent.py rollback deploy-agent --to checkpoint-2
```

## Guardrails

- **no-prod** — block actions targeting production environments
- **no-delete** — prevent deletion of resources
- **cost-limit-<N>** — reject actions exceeding N dollars
- **require-approval** — all actions need human approval before execution
- **time-window-<start>-<end>** — only allow execution during specified hours

## Approval workflow

1. Agent generates a plan
2. Plan is submitted with PENDING status
3. Human reviews plan steps and risks
4. Approve or reject with reason
5. Approved plans execute with monitoring
6. All actions are logged with timestamps

## Checkpoints

Agents automatically create checkpoints before each plan execution. Rollback restores agent state, memory, and context to any previous checkpoint.
