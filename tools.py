from claude_agent_sdk import create_sdk_mcp_server, tool
import logic


STATE = logic.new_state()

# Simulated upstream flakiness so the retry path is exercised at run time.
# Each order fails transiently the given number of times, then succeeds.
_FLAKY = {"A-200": 1}


def reset_state() -> None:
    """Clear session state. Call between scenarios if running in one process."""
    global STATE, _FLAKY

    STATE = logic.new_state()
    _FLAKY = {"A-200": 1}


@tool(
    "verify_identity",
    "Verify the account holder's identity using their PIN. "
    "Must be completed before any refund is issued.",
    {"pin": str},
)
async def verify_identity(args):
    if args.get("pin") == STATE["pin"]:
        STATE["verified"] = True
        result = {"ok": True, "verified": True}
    else:
        result = logic.error("validation", False, "incorrect PIN")

    return {"content": [{"type": "text", "text": str(result)}]}

@tool(
    "record_approval",
    "Record a manager's approval for a single order, using the manager code. "
    "Required before refunding more than 500. One approval covers one refund.",
    {"order_id": str, "manager_code": str},
)
async def record_approval(args):
    order_id = args.get("order_id")

    if args.get("manager_code") != STATE["manager_code"]:
        result = logic.error("authorisation", False, "invalid manager code")

    elif order_id not in logic.ORDERS:
        result = logic.error("validation", False, f"no such order: {order_id}")

    else:
        STATE["approvals"].add(order_id)
        result = {"ok": True, "approved": order_id}

    return {"content": [{"type": "text", "text": str(result)}]}


def _upstream_lookup(order_id: str) -> dict:
    """Stand-in for a flaky order service."""
    remaining = _FLAKY.get(order_id, 0)

    if remaining > 0:
        _FLAKY[order_id] = remaining - 1
        return logic.error(
            "transient",
            True,
            "order service timed out",
            attempted=order_id,
        )

    found = logic.ORDERS.get(order_id)

    if found is None:
        return logic.error("validation", False, f"no such order: {order_id}")

    return {"ok": True, **found}


@tool(
    "lookup_order",
    "Look up a single order by its identifier. Read-only. "
    "Returns status and total, or a structured error if not found.",
    {"order_id": str},
)