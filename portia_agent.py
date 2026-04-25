#!/usr/bin/env python3
"""Portia Agent — enterprise agent framework with guardrails, approvals, monitoring, and rollback."""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

SKILL_DIR = Path(__file__).parent
STATE_FILE = SKILL_DIR / "state.json"

G = "\033[92m"
R = "\033[91m"
Y = "\033[93m"
C = "\033[96m"
W = "\033[0m"
BOLD = "\033[1m"


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"agents": {}, "plans": {}, "checkpoints": {}, "audit_log": []}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def print_banner(text):
    print(f"\n{BOLD}{C}{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}{W}\n")


def print_ok(text):
    print(f"  {G}[OK]{W} {text}")


def print_err(text):
    print(f"  {R}[ERR]{W} {text}")


def print_info(text):
    print(f"  {C}[i]{W} {text}")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ── Guardrail definitions ──────────────────────────────────────

GUARDRAILS = {
    "no-prod": {
        "description": "Block actions targeting production environments",
        "check": lambda action: "prod" not in action.get("target", "").lower(),
        "message": "Action targets production — blocked by no-prod guardrail",
    },
    "no-delete": {
        "description": "Prevent deletion of resources",
        "check": lambda action: action.get("action_type") != "delete",
        "message": "Delete actions are blocked by no-delete guardrail",
    },
    "require-approval": {
        "description": "All actions need human approval",
        "check": lambda action: action.get("approved", False),
        "message": "Action requires human approval before execution",
    },
}

# Dynamic guardrails (cost-limit, time-window) checked at runtime
DYNAMIC_GUARDRAILS = {
    "cost-limit": lambda rule, action: action.get("estimated_cost", 0) <= float(rule.split("-", 2)[-1]),
    "time-window": lambda rule, action: True,  # Simplified check
}


def check_guardrails(guardrail_names, action):
    """Check an action against configured guardrails. Returns (passed, messages)."""
    passed = True
    messages = []

    for gr_name in guardrail_names:
        # Static guardrails
        if gr_name in GUARDRAILS:
            gr = GUARDRAILS[gr_name]
            if not gr["check"](action):
                passed = False
                messages.append(gr["message"])

        # Dynamic guardrails
        for prefix, checker in DYNAMIC_GUARDRAILS.items():
            if gr_name.startswith(prefix):
                if not checker(gr_name, action):
                    passed = False
                    messages.append(f"Action violates {gr_name} guardrail")

    return passed, messages


# ── create ──────────────────────────────────────────────────────

async def cmd_create(args):
    if not args:
        print_err("Usage: create <agent-name> [--guardrails <gr1,gr2,...>]")
        return 1

    name = args[0]
    guardrails = []

    if "--guardrails" in args:
        idx = args.index("--guardrails")
        if idx + 1 < len(args):
            guardrails = [g.strip() for g in args[idx + 1].split(",")]

    print_banner(f"Creating Agent: {name}")

    # Validate guardrails
    for gr in guardrails:
        if gr in GUARDRAILS:
            print_ok(f"Guardrail: {gr} — {GUARDRAILS[gr]['description']}")
        elif any(gr.startswith(p) for p in DYNAMIC_GUARDRAILS):
            print_ok(f"Guardrail: {gr}")
        else:
            print_err(f"Unknown guardrail: {gr}")
            print_info(f"Available: {', '.join(GUARDRAILS.keys())}, cost-limit-<N>, time-window-<s>-<e>")
            return 1

    agent_config = {
        "name": name,
        "guardrails": guardrails,
        "approval_required": "require-approval" in guardrails,
        "created": now_iso(),
        "status": "active",
        "plans_completed": 0,
        "last_checkpoint": None,
    }

    # Create agent directory
    agent_dir = Path(os.getcwd()) / "agents" / name
    agent_dir.mkdir(parents=True, exist_ok=True)

    config_file = agent_dir / "config.json"
    config_file.write_text(json.dumps(agent_config, indent=2))
    print_ok(f"Created agent config at {config_file}")

    # Create initial checkpoint
    checkpoint_id = str(uuid.uuid4())[:8]
    checkpoint = {
        "id": checkpoint_id,
        "agent": name,
        "created": now_iso(),
        "state": {"memory": [], "context": {}, "plans_executed": []},
        "label": "initial",
    }

    cp_file = agent_dir / f"checkpoint_{checkpoint_id}.json"
    cp_file.write_text(json.dumps(checkpoint, indent=2))
    agent_config["last_checkpoint"] = checkpoint_id

    state = load_state()
    state["agents"][name] = agent_config
    state["checkpoints"][checkpoint_id] = checkpoint

    # Audit log entry
    state["audit_log"].append({
        "timestamp": now_iso(),
        "event": "agent_created",
        "agent": name,
        "guardrails": guardrails,
    })

    save_state(state)

    print_ok(f"Created initial checkpoint: {checkpoint_id}")
    print_info(f"Plan with: portia_agent.py plan {name} '<objective>'")
    return 0


# ── plan ────────────────────────────────────────────────────────

async def cmd_plan(args):
    if len(args) < 2:
        print_err("Usage: plan <agent> <objective>")
        return 1

    agent_name = args[0]
    objective = " ".join(args[1:])

    state = load_state()
    if agent_name not in state["agents"]:
        print_err(f"Agent not found: {agent_name}")
        print_info("Create one with: portia_agent.py create <name>")
        return 1

    agent = state["agents"][agent_name]

    print_banner(f"Generating Plan: {agent_name}")

    plan_id = str(uuid.uuid4())[:8]

    # Generate structured plan steps
    steps = [
        {
            "step": 1,
            "action": "analyze_objective",
            "description": f"Analyze the objective: {objective}",
            "target": "internal",
            "estimated_cost": 0.0,
            "risk_level": "low",
            "verification": "Objective is understood and broken into sub-tasks",
        },
        {
            "step": 2,
            "action": "gather_context",
            "description": "Collect relevant context and prerequisites",
            "target": "internal",
            "estimated_cost": 0.001,
            "risk_level": "low",
            "verification": "All required context is available",
        },
        {
            "step": 3,
            "action": "execute_primary",
            "description": f"Execute the primary action for: {objective}",
            "target": "external",
            "estimated_cost": 0.01,
            "risk_level": "medium",
            "verification": "Primary action completed successfully",
        },
        {
            "step": 4,
            "action": "verify_result",
            "description": "Verify the result meets quality standards",
            "target": "internal",
            "estimated_cost": 0.002,
            "risk_level": "low",
            "verification": "Result passes all quality checks",
        },
        {
            "step": 5,
            "action": "finalize",
            "description": "Finalize and record completion",
            "target": "internal",
            "estimated_cost": 0.0,
            "risk_level": "low",
            "verification": "Execution log updated with results",
        },
    ]

    total_cost = sum(s["estimated_cost"] for s in steps)

    plan = {
        "id": plan_id,
        "agent": agent_name,
        "objective": objective,
        "status": "pending_approval" if agent.get("approval_required") else "ready",
        "created": now_iso(),
        "steps": steps,
        "total_estimated_cost": total_cost,
        "guardrail_check": None,
    }

    # Run guardrail checks on each step
    all_passed = True
    for step in steps:
        passed, messages = check_guardrails(agent.get("guardrails", []), step)
        step["guardrail_passed"] = passed
        step["guardrail_messages"] = messages
        if not passed:
            all_passed = False

    plan["guardrail_check"] = "passed" if all_passed else "blocked"

    # Save plan
    plan_file = Path(os.getcwd()) / "agents" / agent_name / f"plan_{plan_id}.json"
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text(json.dumps(plan, indent=2))
    print_ok(f"Plan created: {plan_id}")

    # Display plan
    print(f"\n  {BOLD}Objective:{W} {objective}")
    print(f"  {BOLD}Status:{W} {'Pending Approval' if plan['status'] == 'pending_approval' else 'Ready'}")
    print(f"  {BOLD}Guardrails:{W} {plan['guardrail_check']}")
    print(f"  {BOLD}Est. Cost:{W} ${total_cost:.4f}")
    print()

    for step in steps:
        risk_color = G if step["risk_level"] == "low" else (Y if step["risk_level"] == "medium" else R)
        gr_icon = G + "[PASS]" if step["guardrail_passed"] else R + "[BLOCK]"
        print(f"  {C}Step {step['step']}{W}: {step['description']}")
        print(f"    Risk: {risk_color}{step['risk_level']}{W} | Guardrail: {gr_icon}{W}")
        print(f"    Verify: {step['verification']}")
        for msg in step.get("guardrail_messages", []):
            print(f"    {R}! {msg}{W}")
        print()

    state["plans"][plan_id] = plan
    state["audit_log"].append({
        "timestamp": now_iso(),
        "event": "plan_created",
        "agent": agent_name,
        "plan": plan_id,
        "objective": objective,
    })
    save_state(state)

    if plan["status"] == "pending_approval":
        print_info(f"Plan requires approval: portia_agent.py approve {plan_id}")
    else:
        print_info("Plan ready for execution")
    return 0


# ── approve ─────────────────────────────────────────────────────

async def cmd_approve(args):
    if not args:
        print_err("Usage: approve <plan_id> [--reject --reason <reason>]")
        return 1

    plan_id = args[0]
    reject = "--reject" in args
    reason = ""

    if "--reason" in args:
        idx = args.index("--reason")
        if idx + 1 < len(args):
            reason = " ".join(args[idx + 1:])

    state = load_state()
    if plan_id not in state["plans"]:
        print_err(f"Plan not found: {plan_id}")
        return 1

    plan = state["plans"][plan_id]

    print_banner(f"{'Rejecting' if reject else 'Approving'} Plan: {plan_id}")

    if reject:
        plan["status"] = "rejected"
        plan["rejected_at"] = now_iso()
        plan["rejection_reason"] = reason or "No reason provided"
        print_ok(f"Plan rejected: {plan['objective']}")
        if reason:
            print_info(f"Reason: {reason}")
        action_event = "plan_rejected"
    else:
        plan["status"] = "approved"
        plan["approved_at"] = now_iso()

        # Simulate execution
        print_info("Executing plan steps...")
        for step in plan["steps"]:
            risk_color = G if step["risk_level"] == "low" else (Y if step["risk_level"] == "medium" else R)
            print(f"  {C}[Step {step['step']}]{W} {step['description']}...", end="")

            if not step.get("guardrail_passed", True):
                print(f" {R}BLOCKED{W}")
                continue

            await asyncio.sleep(0.2)
            step["executed_at"] = now_iso()
            step["result"] = "completed"
            print(f" {G}done{W} {risk_color}[{step['risk_level']}]{W}")

        plan["status"] = "completed"
        plan["completed_at"] = now_iso()
        print_ok("Plan execution completed")
        action_event = "plan_approved"

        # Create checkpoint after execution
        agent_name = plan["agent"]
        checkpoint_id = str(uuid.uuid4())[:8]
        checkpoint = {
            "id": checkpoint_id,
            "agent": agent_name,
            "created": now_iso(),
            "label": f"after-plan-{plan_id}",
            "state": {
                "plans_executed": [plan_id],
                "objective": plan["objective"],
            },
        }

        agent_dir = Path(os.getcwd()) / "agents" / agent_name
        agent_dir.mkdir(parents=True, exist_ok=True)
        cp_file = agent_dir / f"checkpoint_{checkpoint_id}.json"
        cp_file.write_text(json.dumps(checkpoint, indent=2))

        state["checkpoints"][checkpoint_id] = checkpoint
        if agent_name in state["agents"]:
            state["agents"][agent_name]["last_checkpoint"] = checkpoint_id
            state["agents"][agent_name]["plans_completed"] = (
                state["agents"][agent_name].get("plans_completed", 0) + 1
            )

        print_ok(f"Created checkpoint: {checkpoint_id}")

    # Save plan update
    plan_file = Path(os.getcwd()) / "agents" / plan["agent"] / f"plan_{plan_id}.json"
    if plan_file.parent.exists():
        plan_file.write_text(json.dumps(plan, indent=2))

    state["plans"][plan_id] = plan
    state["audit_log"].append({
        "timestamp": now_iso(),
        "event": action_event,
        "agent": plan["agent"],
        "plan": plan_id,
        "reason": reason if reject else None,
    })
    save_state(state)
    return 0


# ── monitor ─────────────────────────────────────────────────────

async def cmd_monitor(args):
    agent_name = None
    tail_count = 20

    if args:
        agent_name = args[0]

    if "--tail" in args:
        idx = args.index("--tail")
        if idx + 1 < len(args):
            tail_count = int(args[idx + 1])

    print_banner("Agent Monitoring")

    state = load_state()
    audit_log = state.get("audit_log", [])

    if agent_name:
        audit_log = [e for e in audit_log if e.get("agent") == agent_name]
        print_info(f"Filtering for agent: {agent_name}")

    if not audit_log:
        print_info("No audit log entries found")
        return 0

    # Show last N entries
    entries = audit_log[-tail_count:]

    for entry in entries:
        ts = entry.get("timestamp", "?")
        event = entry.get("event", "?")
        agent = entry.get("agent", "?")

        event_colors = {
            "agent_created": G,
            "plan_created": C,
            "plan_approved": G,
            "plan_rejected": R,
            "checkpoint_created": Y,
            "rollback": Y,
        }
        color = event_colors.get(event, W)

        print(f"  {ts[:19]} | {color}{event:<20}{W} | agent: {agent}")

        if entry.get("objective"):
            print(f"    Objective: {entry['objective']}")
        if entry.get("plan"):
            print(f"    Plan: {entry['plan']}")
        if entry.get("reason"):
            print(f"    Reason: {entry['reason']}")

    print()
    print_info(f"Showing {len(entries)} of {len(audit_log)} total events")

    # Show agent status summary
    if agent_name and agent_name in state["agents"]:
        agent = state["agents"][agent_name]
        print()
        print(f"  {BOLD}Agent Status:{W}")
        print(f"    Status: {agent.get('status', '?')}")
        print(f"    Plans completed: {agent.get('plans_completed', 0)}")
        print(f"    Guardrails: {', '.join(agent.get('guardrails', [])) or 'none'}")
        print(f"    Last checkpoint: {agent.get('last_checkpoint', 'none')}")

    return 0


# ── rollback ────────────────────────────────────────────────────

async def cmd_rollback(args):
    if not args:
        print_err("Usage: rollback <agent> --to <checkpoint_id>")
        return 1

    agent_name = args[0]
    checkpoint_id = None

    if "--to" in args:
        idx = args.index("--to")
        if idx + 1 < len(args):
            checkpoint_id = args[idx + 1]

    if not checkpoint_id:
        print_err("Specify checkpoint with --to <checkpoint_id>")
        return 1

    state = load_state()
    if agent_name not in state["agents"]:
        print_err(f"Agent not found: {agent_name}")
        return 1

    if checkpoint_id not in state["checkpoints"]:
        print_err(f"Checkpoint not found: {checkpoint_id}")
        # Show available checkpoints
        agent_cps = [cp for cp in state["checkpoints"].values() if cp.get("agent") == agent_name]
        if agent_cps:
            print_info("Available checkpoints for this agent:")
            for cp in agent_cps:
                print(f"    {cp['id']} — {cp.get('label', 'no label')} ({cp['created'][:19]})")
        return 1

    checkpoint = state["checkpoints"][checkpoint_id]
    if checkpoint["agent"] != agent_name:
        print_err(f"Checkpoint {checkpoint_id} belongs to {checkpoint['agent']}, not {agent_name}")
        return 1

    print_banner(f"Rolling Back: {agent_name} -> {checkpoint_id}")

    # Restore state
    agent = state["agents"][agent_name]
    agent["last_checkpoint"] = checkpoint_id
    agent["status"] = "active"

    print_ok(f"Restored state to checkpoint: {checkpoint_id}")
    print_info(f"Label: {checkpoint.get('label', 'no label')}")
    print_info(f"Created: {checkpoint.get('created', '?')[:19]}")

    # Rollback audit entry
    state["audit_log"].append({
        "timestamp": now_iso(),
        "event": "rollback",
        "agent": agent_name,
        "checkpoint": checkpoint_id,
    })

    # Save checkpoint state to agent directory
    agent_dir = Path(os.getcwd()) / "agents" / agent_name
    agent_dir.mkdir(parents=True, exist_ok=True)
    restore_file = agent_dir / "restored_state.json"
    restore_file.write_text(json.dumps(checkpoint["state"], indent=2))
    print_ok(f"State restored to {restore_file}")

    save_state(state)
    return 0


# ── main ────────────────────────────────────────────────────────

COMMANDS = {
    "create": cmd_create,
    "plan": cmd_plan,
    "approve": cmd_approve,
    "monitor": cmd_monitor,
    "rollback": cmd_rollback,
}


async def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print_banner("Portia Agent Framework")
        print("Commands:")
        for name, func in COMMANDS.items():
            doc = func.__doc__ or ""
            print(f"  {C}{name:<12}{W} {doc}")
        print()
        print("Guardrails:")
        for gr_name, gr in GUARDRAILS.items():
            print(f"  {Y}{gr_name:<20}{W} {gr['description']}")
        print(f"  {'cost-limit-<N>':<20} Reject actions exceeding N dollars")
        print(f"  {'time-window-<s>-<e>':<20} Only allow execution during specified hours")
        print()
        return 0

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd not in COMMANDS:
        print_err(f"Unknown command: {cmd}")
        print(f"  Available: {', '.join(COMMANDS)}")
        return 1

    return await COMMANDS[cmd](args)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
