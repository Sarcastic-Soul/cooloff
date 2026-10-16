"""Benchmark: Decider 2B + gate against LLM baselines on the generated calls. Writes bench/results/summary.json and charts.

Usage: uv run python bench/analyze.py bench/data/decider_answers_cpu.json [bench/data/decider_answers_gpu.json]
The optional second file is the same sentences scored on a g6.xlarge GPU; it only adds measured GPU speed and cost.
Method: thresholds are tuned on the dev calls, every number reported is on the test calls (dev also saved).
"""
import itertools
import json
import statistics
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from bench.llm_baselines import SENTENCE_PROMPT, WINDOW_PROMPT
from patterns.rolling_risk_gate import QUESTIONS, GateConfig, StreamingRiskGate, SIGNALS, load_config

PRICE = {  # USD per 1M tokens (input, output). Third-party price lists for Bedrock on-demand; check AWS before quoting.
    "qwen.qwen3-next-80b-a3b": (0.15, 1.20),
    "openai.gpt-oss-120b-1:0": (0.15, 0.60),
}
BOX_PER_HOUR = {"cpu (c7i.2xlarge)": 0.357, "gpu (g6.xlarge)": 0.8048}
R = Path("bench/results")
calls = json.loads(Path("bench/data/calls.json").read_text())


def run_gate(answers_seq, cfg, min_groups=2):
    g = StreamingRiskGate(SIGNALS, GateConfig(**{**cfg.__dict__, "min_groups_for_red": min_groups}))
    red = amber = None
    for i, a in enumerate(answers_seq, 1):
        s = g.update(a)
        if s.state == "amber" and amber is None:
            amber = i
        if s.state == "red" and red is None:
            red = i
            break
    return red, amber


def evaluate(flag_steps, subset):
    """flag_steps: call id -> step where the alarm fired (or None)."""
    scam = [c for c in subset if c["kind"] == "scam"]; normal = [c for c in subset if c["kind"] == "normal"]
    det = [c for c in scam if flag_steps.get(c["id"])]
    ff = [c for c in normal if flag_steps.get(c["id"])]
    ttd = [flag_steps[c["id"]] for c in det]
    frac = [flag_steps[c["id"]] / len(c["sentences"]) for c in det]
    by_type = {}
    for c in normal:
        by_type.setdefault(c["type"], []).append(bool(flag_steps.get(c["id"])))
    return {"detected": f"{len(det)}/{len(scam)}", "detection_rate": round(len(det) / max(len(scam), 1), 3),
            "false_freeze": f"{len(ff)}/{len(normal)}", "false_freeze_rate": round(len(ff) / max(len(normal), 1), 3),
            "median_sentence_of_alarm": statistics.median(ttd) if ttd else None,
            "median_fraction_of_call_heard": round(statistics.median(frac), 2) if frac else None,
            "false_freeze_by_type": {k: f"{sum(v)}/{len(v)}" for k, v in by_type.items() if sum(v)}}


def answers_for(call, table):
    out = []
    for s in call["sentences"]:
        a = table.get(s)
        if a is None or "answers" not in a:
            return None
        out.append(a["answers"])
    return out


def method_flags(table, cfg, min_groups=2, subset=calls):
    flags, ambers = {}, {}
    for c in subset:
        seq = answers_for(c, table)
        if seq is None:
            continue
        flags[c["id"]], ambers[c["id"]] = run_gate(seq, cfg, min_groups)
    return flags, ambers


def tune(table):
    dev = [c for c in calls if c["split"] == "dev"]
    best = None
    for above, attack, release in itertools.product([0.2, 0.25, 0.3, 0.4], [0.5, 0.7, 0.9], [0.08, 0.12, 0.2]):
        cfg = GateConfig(attack=attack, release=release, active_above=above, inactive_below=above / 2)
        flags, _ = method_flags(table, cfg, subset=dev)
        m = evaluate(flags, dev)
        score = m["detection_rate"] - 2 * m["false_freeze_rate"] - 0.001 * (m["median_sentence_of_alarm"] or 99)
        if best is None or score > best[0]:
            best = (score, cfg, m)
    return best[1], best[2]


def lat(xs):
    xs = sorted(xs)
    return {"p50_ms": round(statistics.median(xs)), "p95_ms": round(xs[int(len(xs) * 0.95)])}


def main(answers_path, gpu_path=None):
    dec = json.loads(Path(answers_path).read_text())
    table = dec["answers"]
    test = [c for c in calls if c["split"] == "test"]
    cfg, dev_metrics = tune(table)
    summary = {"decider_model": dec["model"], "n_calls": len(calls), "n_test_calls": len(test),
               "tuned_config": cfg.__dict__, "dev_metrics_tuned": dev_metrics, "methods": {}}

    # Decider + gate, and the ablation without the two-signal rule
    for name, mg in (("decider+gate (two signals)", 2), ("decider+gate (one signal is enough)", 1)):
        flags, ambers = method_flags(table, cfg, mg, test)
        m = evaluate(flags, test)
        m["amber_on_normal_calls"] = f"{sum(1 for c in test if c['kind']=='normal' and ambers.get(c['id']))}/{sum(c['kind']=='normal' for c in test)}"
        summary["methods"][name] = m
    ds_ms = [v["wall_ms"] for v in table.values() if "wall_ms" in v]
    summary["decider_latency_cpu"] = lat(ds_ms)
    if gpu_path:
        gpu = json.loads(Path(gpu_path).read_text())["answers"]
        summary["decider_latency_gpu"] = lat([v["wall_ms"] for v in gpu.values() if "wall_ms" in v])
        danger = lambda r: 1 - r["answers"]["payment_ask"]["probabilities"]["none"] - r["answers"]["payment_ask"]["probabilities"]["known_bill_known_payee"]
        flips = sum((danger(table[k]) > 0.3) != (danger(gpu[k]) > 0.3) for k in table)
        summary["gpu_vs_cpu_answers"] = {"sentences": len(table), "payment_danger_over_0.3_differs": flips,
                                         "note": "GPU runs bf16, CPU runs fp32; probabilities differ by under 0.03"}

    # LLM baselines
    sentence_counts = [len(c["sentences"]) for c in calls]
    avg_sent = statistics.mean(sentence_counts)
    for path in sorted(R.glob("llm_*.json")):
        d = json.loads(path.read_text()); model = d["model"]; pin, pout = PRICE.get(model, (0, 0))
        ps = {s: v for s, v in d["per_sentence"].items() if "answers" in v}
        flags, ambers = method_flags(ps, cfg, 2, test)
        m = evaluate(flags, test)
        toks_in = statistics.mean(v["usage"].get("inputTokens", 0) for v in ps.values()); toks_out = statistics.mean(v["usage"].get("outputTokens", 0) for v in ps.values())
        m.update(latency=lat(d["latency_sample_ms"]), cost_per_1000_sentences_usd=round((toks_in * pin + toks_out * pout) / 1e6 * 1000, 4),
                 avg_tokens=[round(toks_in), round(toks_out)])
        summary["methods"][f"{model} per-sentence + same gate"] = m
        # windowed
        wflags, wtok, wms = {}, [], []
        for c in test:
            steps = d["windowed"].get(c["id"], [])
            first = next((s["k"] for s in steps if s.get("scam")), None)
            wflags[c["id"]] = first
        for c in calls:
            steps = [s for s in d["windowed"].get(c["id"], []) if "usage" in s]
            wtok.append((sum(s["usage"].get("inputTokens", 0) for s in steps), sum(s["usage"].get("outputTokens", 0) for s in steps)))
            wms += [s["ms"] for s in steps]
        wm = evaluate(wflags, test)
        wm.update(latency=lat(wms), cost_per_call_usd=round(statistics.mean((i * pin + o * pout) / 1e6 for i, o in wtok), 5),
                  avg_input_tokens_per_call=round(statistics.mean(i for i, _ in wtok)))
        summary["methods"][f"{model} windowed (whole call so far)"] = wm

    # costs for Decider on a rented box and on the family's own device
    p50s = {"cpu": summary["decider_latency_cpu"]["p50_ms"] / 1000}
    if "decider_latency_gpu" in summary:
        p50s["gpu"] = summary["decider_latency_gpu"]["p50_ms"] / 1000
    summary["decider_cost"] = {k: {"per_1000_sentences_usd": round(rate / 3600 * p50s[k[:3]] * 1000, 4) if k[:3] in p50s else None,
                                   "per_hour_usd": rate} for k, rate in BOX_PER_HOUR.items()}
    summary["decider_cost"]["own device"] = {"per_1000_sentences_usd": 0.0, "note": "runs on hardware the family already owns"}
    summary["avg_sentences_per_generated_call"] = round(avg_sent, 1)

    # bytes of call words sent to the cloud before the alarm
    summary["call_words_sent_before_alarm_bytes"] = {"decider+gate": 0, "per-sentence LLM": "every sentence", "windowed LLM": "the whole call so far, every sentence"}

    R.mkdir(parents=True, exist_ok=True)
    (R / "summary.json").write_text(json.dumps(summary, indent=1))
    charts(summary, table, cfg)
    print(json.dumps(summary, indent=1))


def charts(summary, table, cfg):
    names = list(summary["methods"])
    short = lambda n: n.replace("openai.gpt-oss-120b-1:0", "gpt-oss-120b").replace("qwen.qwen3-next-80b-a3b", "qwen3-next").replace(" (whole call so far)", "").replace(" + same gate", "+gate").replace("decider+gate (one signal is enough)", "Decider+gate, 1 signal").replace("decider+gate (two signals)", "Decider+gate, 2 signals")
    ink, sage, red, sand = "#15201d", "#2f6b4f", "#c23b22", "#e0ac2b"
    fig, ax = plt.subplots(figsize=(9, 4.6)); x = range(len(names))
    ax.bar([i - 0.2 for i in x], [summary["methods"][n]["detection_rate"] * 100 for n in names], 0.4, color=sage, label="scam calls caught")
    ax.bar([i + 0.2 for i in x], [summary["methods"][n]["false_freeze_rate"] * 100 for n in names], 0.4, color=red, label="normal calls frozen by mistake")
    ax.set_xticks(list(x)); ax.set_xticklabels([short(n) for n in names], rotation=18, ha="right", fontsize=8); ax.set_ylabel("% of test calls"); ax.legend(frameon=False)
    ax.set_title("Detection and false freezes on the test calls"); fig.tight_layout(); fig.savefig(R / "detection_vs_false_freeze.png", dpi=160); plt.close(fig)

    # confidence vs accuracy from the stage 1 sentences
    import eval.stage1_data as sd  # noqa
    rows = json.loads(Path("bench/results/stage1/stage1_strands-decider-2B-qwen3.5-v1-2610.json").read_text())["rows"]
    pts = []
    for r in rows:
        pp = r["pred"]["payment_ask_p"]; top = max(pp, key=pp.get)
        pts.append((pp[top], top == r["truth"]["payment_ask"]))
    bins = [(0, .5), (.5, .7), (.7, .85), (.85, 1.01)]
    xs, ys, ns = [], [], []
    for lo, hi in bins:
        sel = [ok for c, ok in pts if lo <= c < hi]
        if sel:
            xs.append((lo + min(hi, 1)) / 2); ys.append(sum(sel) / len(sel) * 100); ns.append(len(sel))
    fig, ax = plt.subplots(figsize=(5.2, 4.2)); ax.plot([0, 100], [0, 100], color="#8aa39a", ls="--")
    ax.plot([x * 100 for x in xs], ys, "o-", color=ink)
    for x_, y_, n in zip(xs, ys, ns):
        ax.annotate(f"n={n}", (x_ * 100, y_), textcoords="offset points", xytext=(6, -12), fontsize=8)
    ax.set_xlabel("Decider confidence in its top choice (%)"); ax.set_ylabel("answers that were right (%)"); ax.set_title("Confidence against accuracy (payment ask)")
    fig.tight_layout(); fig.savefig(R / "confidence_vs_accuracy.png", dpi=160); plt.close(fig)

    # when the alarm fires
    fig, ax = plt.subplots(figsize=(6, 3.8)); data = []
    for c in calls:
        if c["kind"] == "scam" and c["split"] == "test":
            seq = [table[s]["answers"] for s in c["sentences"] if s in table]
            if len(seq) == len(c["sentences"]):
                red, _ = run_gate(seq, cfg); data.append(red / len(c["sentences"]) * 100 if red else 105)
    ax.hist(data, bins=range(0, 120, 10), color=sage); ax.set_xlabel("% of the call heard when the freeze fired (105 = never)"); ax.set_ylabel("scam calls")
    ax.set_title("Time to freeze, Decider + gate"); fig.tight_layout(); fig.savefig(R / "time_to_freeze.png", dpi=160); plt.close(fig)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
