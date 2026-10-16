"""Stage 1 go/no-go: score the hand-labeled sentences with Decider and print accuracy.

Standard library only. Run inside the Decider container:
  docker cp eval decider:/app/eval && docker exec decider python /app/eval/stage1_eval.py
Writes /results/stage1_<model>.json (every raw answer, so results can be re-scored or replayed).
"""
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, "/app")
import stage1_data  # noqa: E402
from smoke import QUESTIONS, post, wait_ready  # noqa: E402

DANGER_PAY = {"gift_cards_crypto_or_wire", "remote_access_request", "password_or_code_request"}


def main():
    health = wait_ready()
    model = health["model"]
    print("model:", model, "device:", health["device"])
    rows = []
    for i, (s, pay, imp, sec, pres) in enumerate(stage1_data.ROWS):
        out, ms = post({"state": s, "questions": QUESTIONS})
        a = out["answers"]
        rows.append({
            "sentence": s, "truth": {"payment_ask": pay, "impersonation": imp, "secrecy": sec, "pressure": pres},
            "pred": {
                "payment_ask": a["payment_ask"]["choice"], "payment_ask_p": a["payment_ask"]["probabilities"],
                "impersonation": a["impersonation"]["choice"], "impersonation_p": a["impersonation"]["probabilities"],
                "secrecy": a["secrecy"]["noul"], "pressure": a["pressure"]["score"],
            },
            "wall_ms": round(ms, 1),
        })
        if i % 10 == 9:
            print("  scored %d/%d" % (i + 1, len(stage1_data.ROWS)), flush=True)

    def acc(key):
        ok = sum(r["pred"][key] == r["truth"][key] for r in rows)
        return ok / len(rows)

    def per_class(key):
        out = {}
        for c in sorted({r["truth"][key] for r in rows}):
            sub = [r for r in rows if r["truth"][key] == c]
            out[c] = "%d/%d" % (sum(r["pred"][key] == c for r in sub), len(sub))
        return out

    sec_tp = sum(r["pred"]["secrecy"] > 0.5 and r["truth"]["secrecy"] for r in rows)
    sec_fp = sum(r["pred"]["secrecy"] > 0.5 and not r["truth"]["secrecy"] for r in rows)
    sec_fn = sum(r["pred"]["secrecy"] <= 0.5 and r["truth"]["secrecy"] for r in rows)
    pres_exact = sum(round(r["pred"]["pressure"]) == r["truth"]["pressure"] for r in rows) / len(rows)
    pres_mae = statistics.mean(abs(r["pred"]["pressure"] - r["truth"]["pressure"]) for r in rows)

    danger = [r for r in rows if r["truth"]["payment_ask"] in DANGER_PAY]
    danger_hit = sum(r["pred"]["payment_ask"] in DANGER_PAY for r in danger)
    benign = [r for r in rows if r["truth"]["payment_ask"] not in DANGER_PAY and r["truth"]["impersonation"] == "none" and not r["truth"]["secrecy"]]
    benign_pay_fp = sum(r["pred"]["payment_ask"] in DANGER_PAY for r in benign)
    benign_any_fp = sum(r["pred"]["payment_ask"] in DANGER_PAY or r["pred"]["impersonation"] != "none" or r["pred"]["secrecy"] > 0.5 for r in benign)

    wall = [r["wall_ms"] for r in rows[1:]]
    summary = {
        "model": model, "device": health["device"], "n": len(rows),
        "payment_ask_acc": round(acc("payment_ask"), 3), "payment_ask_per_class": per_class("payment_ask"),
        "impersonation_acc": round(acc("impersonation"), 3), "impersonation_per_class": per_class("impersonation"),
        "secrecy_tp_fp_fn": [sec_tp, sec_fp, sec_fn],
        "pressure_exact": round(pres_exact, 3), "pressure_mae": round(pres_mae, 3),
        "danger_payment_recall": "%d/%d" % (danger_hit, len(danger)),
        "benign_n": len(benign), "benign_false_payment_danger": benign_pay_fp, "benign_any_false_signal": benign_any_fp,
        "wall_ms_median": round(statistics.median(wall), 1), "wall_ms_p95": round(sorted(wall)[int(len(wall) * 0.95)], 1),
    }
    print(json.dumps(summary, indent=1))
    os.makedirs("/results", exist_ok=True)
    safe = model.replace("/", "_")
    with open("/results/stage1_%s.json" % safe, "w") as f:
        json.dump({"summary": summary, "rows": rows}, f, indent=1)
    print("saved /results/stage1_%s.json" % safe)


if __name__ == "__main__":
    main()
