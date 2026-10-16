from agent.mock_bank import MockBank


def test_spend_and_reject():
    b = MockBank(balance=100)
    assert "Done" in b.pay_bill("Riverside Electric", 84) and round(b.balance) == 16
    assert "Rejected" in b.send_money("X", 500) and round(b.balance) == 16
    assert b.is_known_payee("Riverside Electric") and not b.is_known_payee("Safe Holding Account")
    assert len(b.history()) == 1
