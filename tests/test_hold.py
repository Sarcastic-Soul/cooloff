from types import SimpleNamespace

from strands.interventions import Confirm, Proceed

from patterns.rolling_risk_gate import make_gate
from patterns.rolling_risk_gate.hold import TransactionHold
from tests.test_gate import ans


def event(tool, **inp):
    return SimpleNamespace(tool_use={"name": tool, "input": inp})


def test_green_proceeds_red_confirms_and_notifies():
    g = make_gate()
    held = []
    hold = TransactionHold(g, {"send_money"}, payee_known=lambda i: i.get("payee") == "Water Co",
                           on_hold=lambda tool, inp, state: held.append((tool, state)))
    assert isinstance(hold.before_tool_call(event("send_money", payee="X", amount=5)), Proceed)
    g.update(ans(sec=0.95)); g.update(ans(pay=0.95))
    assert isinstance(hold.before_tool_call(event("send_money", payee="Water Co", amount=84)), Confirm)
    assert held == [("send_money", "red")]
    assert isinstance(hold.before_tool_call(event("get_balance")), Proceed)  # not a held tool


def test_amber_only_holds_unknown_payee():
    g = make_gate()
    hold = TransactionHold(g, {"send_money"}, payee_known=lambda i: i.get("payee") == "Water Co")
    g.update(ans(pay=0.95))
    assert g.state == "amber"
    assert isinstance(hold.before_tool_call(event("send_money", payee="Water Co")), Proceed)
    assert isinstance(hold.before_tool_call(event("send_money", payee="Stranger")), Confirm)
