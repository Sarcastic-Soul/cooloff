"""Smoke test for the Decider server. Standard library only.

Sends the four Cooloff questions in one request for a few sample sentences,
prints answers and latency, and saves everything to /results/smoke.json.
Run inside the container:  docker compose exec decider python /app/smoke.py
"""
import json
import os
import statistics
import sys
import time
import urllib.request

URL = os.environ.get("DECIDER_URL", "http://127.0.0.1:8000")

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

SENTENCES = [
    "Grandma, it's me, I'm in trouble and I need money right now.",
    "Please go to the store and buy five hundred dollars in Apple gift cards.",
    "Don't tell your parents about this, they will only make it worse.",
    "Your pharmacy order is ready for pickup after three o'clock.",
    "This is your electric company, your usual bill of $84 is due on the 15th.",
]


def post(body):
    req = urllib.request.Request(
        URL + "/v1/systemone",
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
    )
    t = time.time()
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.loads(r.read())
    return out, (time.time() - t) * 1000


def wait_ready(limit=900):
    t = time.time()
    while time.time() - t < limit:
        try:
            with urllib.request.urlopen(URL + "/health", timeout=5) as r:
                return json.loads(r.read())
        except Exception:
            time.sleep(3)
    sys.exit("server not ready after %ds (first start downloads about 4.5 GB)" % limit)


def main():
    print("waiting for server (first start downloads the model)...")
    health = wait_ready()
    print("health:", json.dumps(health))
    runs, wall = [], []
    for i, s in enumerate(SENTENCES):
        out, ms = post({"state": s, "questions": QUESTIONS})
        runs.append({"sentence": s, "response": out, "wall_ms": round(ms, 1)})
        wall.append(ms)
        print("\n[%d] %s" % (i + 1, s))
        print("    wall %.0f ms" % ms)
        if i == 0:
            print("    raw response:", json.dumps(out)[:700])
        answers = out.get("answers", {})
        for k in QUESTIONS:
            print("    %-14s %s" % (k, json.dumps(answers.get(k))))
    # the first call is a warm-up; report the rest
    warm = wall[1:] or wall
    summary = {
        "health": health,
        "wall_ms_first": round(wall[0], 1),
        "wall_ms_median_warm": round(statistics.median(warm), 1),
        "wall_ms_max_warm": round(max(warm), 1),
    }
    print("\nsummary:", json.dumps(summary))
    os.makedirs("/results", exist_ok=True)
    with open("/results/smoke.json", "w") as f:
        json.dump({"summary": summary, "runs": runs}, f, indent=1)
    print("saved /results/smoke.json")


if __name__ == "__main__":
    main()
