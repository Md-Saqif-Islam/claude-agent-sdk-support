# Pure logic only.

APPROVAL_THRESHOLD = 500.0
REFUND_AGENT_TYPE = "refunds"
MAX_ATTEMPTS = 3

ORDERS = {"A-100":{"status": "delivered","total":240.0},
        "A-200":{"status": "in_transit","total":900.0}
        }

def error(category: str, retryable: bool, message: str, **extra) -> dict:
    """Structured, categorised error the caller can act on."""
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
    contains the registered agent name when the call comes from a subagent.
    
    State values are read defensively so missing data does not cause the hook to crash."""

    if not tool_name.endswith("process_refund"):
        return None

    if caller!= REFUND_AGENT_TYPE:
        return (f"refunds may only be issued by the {REFUND_AGENT_TYPE} subagent; delegate this with the Task tool")

    if not state.get("verified"):
        return ("identity must be verified before a refund; call verify_identity first")


    over_threshold = tool_input.get("amount", 0)> APPROVAL_THRESHOLD

    if over_threshold and tool_input.get("order_id") not in state.get("approvals", set()):
        return (f"refunds above {APPROVAL_THRESHOLD} require a recorded manager approval for this order; call record_approval first")


    return None


def is_retryable(result: dict) -> bool:
    """True only for a structured error explicitly marked retryable."""
    return (
        result.get("ok") is False
        and result.get("error", {}).get("retryable") is True
    )


def call_with_retry(fn, max_attempts: int = MAX_ATTEMPTS) -> dict:
    """Run fn() and retry while it returns a retryable structured error.

    fn takes no arguments and returns a result dict. Non-retryable errors are
    returned immediately so the agent sees them and can change course.
    """
    result = fn()
    attempts = 1

    for _ in range(max(0, max_attempts - 1)):
        if not is_retryable(result):
            break

        result = fn()
        attempts += 1

    if isinstance(result, dict) and result.get("ok") is False:
        result["error"]["attempts"] = attempts

    return result 


def validate_refund(order_id: str, amount: float, state: dict) -> dict | None:
    """The money rules. A structured error, or None if the refund may proceed.
    These are the tool's own defences, separate from the gate's policy rules. A
    gate that is bypassed, misconfigured or removed must not be the only thing
    standing between a request and the balance.
    """
    if amount <= 0:
        return error("validation", False, "amount must be positive")

    order = ORDERS.get(order_id)

    if order is None:
        return error("validation", False, f"no such order: {order_id}")

    if order_id in state.get("refunded", set()):
        return error("business", False, f"order {order_id} has already been refunded")

    if amount > order["total"]:
        return error(
            "business",
            False,
            f"refund of {amount} exceeds the order total of {order['total']}",
            order_total=order["total"]
        )

    if amount > state["balance"]:
        return error("business", False, "insufficient funds")

    return None


def apply_refund(order_id: str, amount: float, state: dict) -> dict:
    """Validate, then move the money and record what happened.
    The approval is discarded on use, so it authorises one refund rather than
    standing as a permanent flag on the order.
    """
    problem = validate_refund(order_id, amount, state)

    if problem is not None:
        return problem

    state["balance"] -= amount
    state["refunded"].add(order_id)
    state["approvals"].discard(order_id)

    return {"ok": True, "refunded": amount, "balance": state["balance"]}