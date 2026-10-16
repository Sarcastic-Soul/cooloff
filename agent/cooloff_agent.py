"""The Cooloff steward agent: a Strands agent that handles a parent's money tasks on a mock bank.

The gate sits in the agent's path as a TransactionHold InterventionHandler. When the gate is red (or amber with an
unknown payee), a money tool call does not run. The agent pauses with stop_reason "interrupt" until the family answers.
"""
from __future__ import annotations

from typing import Any

from strands import Agent, tool
from strands.models import BedrockModel

from patterns.rolling_risk_gate import StreamingRiskGate
from patterns.rolling_risk_gate.hold import TransactionHold

from .mock_bank import MockBank

MODEL_ID = "qwen.qwen3-next-80b-a3b"
HELD_TOOLS = {"pay_bill", "send_money", "buy_gift_card"}

SYSTEM_PROMPT = (
    "You are Cooloff, a careful assistant that does money tasks for Margaret Hale on her own device. "
    "Use the tools to do exactly what she asks, one tool call per request. After the tool result, reply in one short sentence. "
    "If a tool call is held for family approval, say so plainly and do not try another way to move the money."
)


def build_agent(bank: MockBank, gate: StreamingRiskGate, on_hold=None, region: str = "us-east-1") -> tuple[Agent, TransactionHold]:
    @tool
    def get_balance() -> str:
        """Read the current account balance."""
        return f"Balance ${bank.balance:,.2f}"

    @tool
    def pay_bill(payee: str, amount: float) -> str:
        """Pay a bill to a payee.

        Args:
            payee: Name of the company being paid.
            amount: Dollar amount.
        """
        return bank.pay_bill(payee, amount)

    @tool
    def send_money(payee: str, amount: float) -> str:
        """Send money (bank transfer or wire) to a payee.

        Args:
            payee: Name of the person or account receiving the money.
            amount: Dollar amount.
        """
        return bank.send_money(payee, amount)

    @tool
    def buy_gift_card(brand: str, amount: float) -> str:
        """Buy a gift card.

        Args:
            brand: Brand of the gift card.
            amount: Dollar amount.
        """
        return bank.buy_gift_card(brand, amount)

    hold = TransactionHold(
        gate, HELD_TOOLS,
        payee_known=lambda i: bank.is_known_payee(str(i.get("payee", ""))),
        on_hold=on_hold,
    )
    agent = Agent(
        model=BedrockModel(model_id=MODEL_ID, region_name=region, temperature=0.0, max_tokens=300),
        tools=[get_balance, pay_bill, send_money, buy_gift_card],
        system_prompt=SYSTEM_PROMPT,
        interventions=[hold],
        callback_handler=None,
    )
    return agent, hold


def run_request(agent: Agent, text: str) -> dict[str, Any]:
    """Run one parent request. Returns {"status": "done"|"held", "text": ..., "interrupts": [...]}"""
    result = agent(text)
    if result.stop_reason == "interrupt":
        return {"status": "held", "text": "", "interrupts": [{"id": i.id, "prompt": getattr(i, "reason", None)} for i in result.interrupts]}
    return {"status": "done", "text": str(result).strip(), "interrupts": []}


def resume(agent: Agent, interrupts: list[dict], answer: str) -> dict[str, Any]:
    """The family answered. 'yes' lets the held tool run, anything else cancels it."""
    result = agent([{"interruptResponse": {"interruptId": i["id"], "response": answer}} for i in interrupts])
    return {"status": "held" if result.stop_reason == "interrupt" else "done", "text": str(result).strip()}
