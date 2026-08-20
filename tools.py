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