"""A second use of the rolling_risk_gate pattern, with nothing to do with money: a chat-safety gate for a child's messages.

Same gate, new questions and new signals. A stranger's messages are scored one at a time with Decider. One worrying sign
makes the app warn the child (amber). Two different kinds of signs (for example "keep this secret" and "send me a photo")
make it hold outgoing photos and ask a parent (red).

Run on saved Decider answers:   uv run python -m examples.kids_chat.chat_gate
"""
import json
from pathlib import Path

from patterns.rolling_risk_gate import GateConfig, Signal, StreamingRiskGate

HERE = Path(__file__).parent

QUESTIONS = {
    "secrecy": {"type": "noul", "instructions": "Does the sender ask the child to keep this conversation secret from parents or other adults?"},
    "move_platform": {"type": "noul", "instructions": "Does the sender ask the child to move the chat to another private app or channel?"},
    "personal_ask": {
        "type": "choice",
        "instructions": "What does the sender ask the child to share?",
        "criteria": {
            "none": "nothing personal is requested",
            "name_or_school": "the child's full name, school or age",
            "address_or_schedule": "the child's home address or when they are home alone",
            "photos": "photos or video of the child",
            "gifts_or_money": "gifts, game credits or money",
        },
    },
}


def secrecy(a):
    return a["secrecy"]["noul"], 1.0


def move(a):
    return a["move_platform"]["noul"], 1.0


def personal(a):
    p = a["personal_ask"]["probabilities"]
    return p.get("address_or_schedule", 0) + p.get("photos", 0) + p.get("gifts_or_money", 0) + 0.5 * p.get("name_or_school", 0), 1.0


SIGNALS = [
    Signal("secrecy", "manipulation", secrecy, weight=1.5),
    Signal("move_platform", "isolation", move, weight=1.0),
    Signal("personal_ask", "ask", personal, weight=2.0),
]


def main():
    answers = json.loads((HERE / "answers.json").read_text())["answers"]
    for chat in json.loads((HERE / "sentences.json").read_text()):
        gate = StreamingRiskGate(SIGNALS, GateConfig())
        print(f"\n{chat['title']}")
        for s in chat["messages"]:
            st = gate.update(answers[s]["answers"])
            print(f"  [{st.state:5}] {s}")
        print("  result:", gate.state, "-", gate.snapshot().reason or "no signals")


if __name__ == "__main__":
    main()
