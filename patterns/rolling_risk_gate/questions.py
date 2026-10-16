"""The typed Decider questions for the Cooloff scam-call policy, and how each answer becomes a gate signal.

Why these shapes: the answers are used as continuous numbers (the probability that the answer is a
dangerous choice), not as a single picked option. On our 100 hand-labeled sentences the probability
separates scam from normal sentences far better than the picked option does (see docs/stage1-results.md).
"""
from __future__ import annotations

from .gate import Signal

QUESTIONS = {
    "pressure": {
        "type": "score",
        "instructions": "How much pressure or urgency does the speaker put on the listener?",
        "criteria": ["No pressure", "Some urgency", "Strong threats or demands to act now"],
    },
    "payment_ask": {
        "type": "choice",
        "instructions": "What kind of payment or sensitive access is the speaker asking for?",
        "criteria": {
            "none": "no payment or access is requested",
            "known_bill_known_payee": "an ordinary bill from a known company",
            "gift_cards_crypto_or_wire": "gift cards, cryptocurrency or a wire transfer",
            "remote_access_request": "installing software or sharing the screen",
            "password_or_code_request": "a password, PIN or one-time code",
        },
    },
    "impersonation": {
        "type": "choice",
        "instructions": "Who does the speaker claim to be?",
        "criteria": {
            "none": "no special identity is claimed",
            "relative_in_trouble": "a relative who is in trouble",
            "bank_or_fraud_dept": "a bank or fraud department",
            "government": "a government agency",
            "tech_support": "tech support",
            "romance": "a romantic partner",
            "prize": "a prize or lottery",
        },
    },
    "secrecy": {
        "type": "noul",
        "instructions": "Does the speaker ask the listener to hide this from family or bank staff?",
    },
}

DANGEROUS_PAYMENT = ("gift_cards_crypto_or_wire", "remote_access_request", "password_or_code_request")


def _mass(answer: dict, options) -> float:
    p = answer.get("probabilities", {})
    return sum(p.get(o, 0.0) for o in options)


def payment_signal(a):
    ans = a["payment_ask"]
    return _mass(ans, DANGEROUS_PAYMENT), 1.0  # the mass itself already shrinks when Decider is unsure


def impersonation_signal(a):
    ans = a["impersonation"]
    p = ans.get("probabilities", {})
    # romance alone is common in normal family talk, so it counts for less
    mass = 1.0 - p.get("none", 1.0) - 0.7 * p.get("romance", 0.0)
    return max(mass, 0.0), 1.0


def secrecy_signal(a):
    p = a["secrecy"]["noul"]
    return p, abs(p - 0.5) * 2 if p < 0.5 else 1.0  # a "no" answer is only weak evidence either way


def pressure_signal(a):
    ans = a["pressure"]
    return ans["score"] / 2.0, ans.get("confidence", 0.5) * 2 if ans.get("confidence", 0) < 0.5 else 1.0


# groups: what is asked (money/access), who is asking (identity), how it is pushed (manipulation)
SIGNALS = [
    Signal("payment_ask", "ask", payment_signal, weight=2.0),
    Signal("impersonation", "identity", impersonation_signal, weight=1.0),
    Signal("secrecy", "manipulation", secrecy_signal, weight=1.5),
    Signal("pressure", "manipulation", pressure_signal, weight=0.5),
]
