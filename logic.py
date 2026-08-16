# Pure logic only.

APPROVAL_THRESHOLD = 500.0
REFUND_AGENT_TYPE = "refunds"
MAX_ATTEMPTS = 3

ORDERS = {"A-100":{"status": "delivered","total":240.0},
        "A-200":{"status": "in_transit","total":900.0}
        }

def error(category: str, retryable: bool, message: str, **extra) -> dict:
    """Structured, categorised error the called can act on."""
    out = {"ok": False, "error": {"category": category,
                                  "retryable": retryable,
                                  "message": message}}
    out["error"].update(extra)
    return out


def new_state() -> dict:
    return {"balance" : 5000.0, 
            "verified": False, 
            "pin": "1234",
            "manager_code": "9999",
            "approvals": set(),
            "refunded" : set()
            }


def gate_decision(tool_name: str, tool_input: dict, state: dict, caller: str | None):
    """Return None if the tool call is allowed, otherwise return a reason for denying it.
    
    The caller tells us which agent made the request. It is None on the main thread and
    containts the registered agent name when the call comes from a subagent.
    
    State values are read defensively so missing data does not cause the hook to crash."""

    if not tool_name.endswith("process_refund"):
        return None

    if caller!= REFUND_AGENT_TYPE:
        return (f"refunds may only be issued by the {REFUND_AGENT_TYPE} subagent; delegate this with the Task tool")

    if not state.get("verified"):
        return ("identity must be verified before a refund; call verify_identity first")


    over_threshold = tool_input.get("amount", 0)> APPROVAL_THRESHOLD

    if over_threshold and tool_input.get("order_id") not in state.get("approvals", set()):
        return (f"refund above {APPROVAL_THRESHOLD} require a recorded manager approval for this order; call record_approval first")


    return None