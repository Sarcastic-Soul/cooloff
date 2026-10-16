"""Generate fraud-awareness training call transcripts (caller side only) with Bedrock, for benchmarking the gate.

Scam calls are written the way scam-awareness courses for older adults describe them. Normal calls include hard
negatives (a real bank alert, an honest grandchild asking for a small loan, a real utility bill, a pharmacy).
Writes bench/data/calls.json. Run: uv run python bench/gen_calls.py
"""
import concurrent.futures as cf
import json
import re
from pathlib import Path

import boto3

MODEL = "qwen.qwen3-next-80b-a3b"
client = boto3.client("bedrock-runtime", region_name="us-east-1")

SCAM_TYPES = {
    "grandparent_gift_cards": "a caller pretending to be a grandchild in trouble who asks for gift cards and says not to tell the parents",
    "grandparent_wire_bail": "a caller pretending to be a grandchild or a lawyer, asking for a wire transfer for bail, asking to keep it secret",
    "bank_fraud_safe_account": "a caller pretending to be a bank fraud department asking the person to move money to a safe account by wire and not to tell the tellers",
    "bank_code_request": "a caller pretending to be a bank asking for the one-time code and the card PIN",
    "tax_government_gift_cards": "a caller pretending to be a tax or social security agency threatening arrest unless the person pays with gift cards or crypto",
    "tech_support_remote": "a caller pretending to be tech support asking the person to install a remote access tool and then pay a fee by gift card",
    "romance_money": "an online romantic partner who has never met the person asking for money by wire or crypto and asking to keep the relationship secret from the family",
    "prize_fee": "a caller saying the person won a prize and must pay a fee in crypto or gift cards to claim it",
}
NORMAL_TYPES = {
    "pharmacy_pickup": "a pharmacy telling a customer their prescription is ready",
    "utility_bill_reminder": "a real utility company reminding a customer of a usual bill amount and due date, asking for no special payment method",
    "real_bank_alert": "a real bank sending an alert about a small unusual charge and telling the customer to call the number on the back of their card, never asking for codes or PINs",
    "honest_grandchild": "a real grandchild calling a grandparent to chat, and asking to borrow twenty dollars until Friday for lunch",
    "doctor_appointment": "a doctor's office confirming and moving an appointment, mentioning a small copay at the visit",
    "delivery_driver": "a delivery driver asking where to leave a package",
    "family_chat": "a daughter chatting with her mother about the weekend and a surprise party for dad that must stay between them",
    "insurance_premium": "an insurance agent confirming the usual monthly premium that is already on autopay",
}
PER_TYPE = 5
PROMPT = """You are helping build a fraud-awareness training set for older adults. Write one realistic phone call transcript, CALLER SIDE ONLY (the person who phones), as a list of {n} short spoken sentences in order. The call is: {desc}.
Rules: one sentence per list item, plain spoken English, no stage directions, no brand names, no real people. Make it different from a typical template (vary names of places, amounts, wording). Output ONLY a JSON array of strings."""


def gen(kind, tname, desc, i):
    n = 9 + (i * 2) % 6
    resp = client.converse(modelId=MODEL, messages=[{"role": "user", "content": [{"text": PROMPT.format(n=n, desc=desc)}]}],
                           inferenceConfig={"maxTokens": 900, "temperature": 0.9})
    text = resp["output"]["message"]["content"][0]["text"]
    m = re.search(r"\[.*\]", text, re.S)
    sents = [s.strip() for s in json.loads(m.group(0)) if isinstance(s, str) and s.strip()]
    return {"id": f"{tname}_{i}", "kind": kind, "type": tname, "split": "dev" if i < 2 else "test", "sentences": sents}


def main():
    jobs = [("scam", t, d, i) for t, d in SCAM_TYPES.items() for i in range(PER_TYPE)] + \
           [("normal", t, d, i) for t, d in NORMAL_TYPES.items() for i in range(PER_TYPE)]
    calls = []
    with cf.ThreadPoolExecutor(8) as ex:
        futs = [ex.submit(gen, *j) for j in jobs]
        for f, j in zip(futs, jobs):
            try:
                calls.append(f.result())
            except Exception as e:
                print("failed", j[1], j[3], e)
    Path("bench/data").mkdir(parents=True, exist_ok=True)
    Path("bench/data/calls.json").write_text(json.dumps(calls, indent=1))
    print(len(calls), "calls,", sum(len(c["sentences"]) for c in calls), "sentences")


if __name__ == "__main__":
    main()
