"""TransactionHold: puts the gate in the agent's path as a Strands InterventionHandler.

Before any held tool runs (for example a payment), it looks at the gate:
  green                     Proceed
  amber and payee known     Proceed (the parent was already warned on screen)
  amber and payee unknown   Confirm (a human approves first)
  red                       Confirm (a human approves first, the agent pauses until they answer)

Confirm without a preset response makes the Strands agent stop with stop_reason "interrupt".
The caller asks the family, then resumes the agent with the answer ("yes" lets the tool run).
"""
from __future__ import annotations

from typing import Any, Callable

from strands.interventions import Confirm, InterventionHandler, Proceed

from .gate import AMBER, RED, StreamingRiskGate


class TransactionHold(InterventionHandler):
    name = "transaction-hold"

    def __init__(
        self,
        gate: StreamingRiskGate,
        held_tools: set[str],
        payee_known: Callable[[dict[str, Any]], bool] = lambda tool_input: False,
        on_hold: Callable[[str, dict[str, Any], str], None] | None = None,
    ):
        self.gate = gate
        self.held_tools = set(held_tools)
        self.payee_known = payee_known
        self.on_hold = on_hold  # called as on_hold(tool_name, tool_input, gate_state) when a call is held
        self.decisions: list[dict[str, Any]] = []  # an audit trail the demo page can show

    def before_tool_call(self, event, **kwargs):
        tool = event.tool_use["name"]
        tool_input = event.tool_use.get("input", {}) or {}
        if tool not in self.held_tools:
            return Proceed()

        state = self.gate.state
        known = bool(self.payee_known(tool_input))
        hold = state == RED or (state == AMBER and not known)
        self.decisions.append({"tool": tool, "input": tool_input, "gate": state, "payee_known": known,
                               "action": "confirm" if hold else "proceed"})
        if not hold:
            return Proceed(reason=f"gate {state}")
        if self.on_hold:
            self.on_hold(tool, tool_input, state)
        return Confirm(
            prompt=f"Held: {tool} {tool_input}. The call looks risky (gate {state}). Approve?",
            reason=f"gate {state}, payee_known={known}",
        )
