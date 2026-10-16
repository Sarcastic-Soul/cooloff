"""LLM baselines for the benchmark, run on Bedrock with non-Claude models.

  per-sentence  the LLM answers the same four questions for each sentence (JSON), then the same gate runs on top.
                This is the fair swap: only the scorer changes.
  windowed      the LLM reads the whole call so far after every sentence and says SCAM or OK. The first SCAM is the alarm.
                This is the common "ask an LLM about the transcript" design. Its cost grows with every sentence.

Writes bench/results/llm_<model>.json. Usage: uv run python bench/llm_baselines.py qwen.qwen3-next-80b-a3b [openai.gpt-oss-120b-1:0]
"""
import concurrent.futures as cf
import json
import re
import statistics
import sys
import time
from pathlib import Path

import boto3

from patterns.rolling_risk_gate import QUESTIONS

client = boto3.client("bedrock-runtime", region_name="us-east-1")

SENTENCE_PROMPT = """Read one sentence from a phone call and answer four questions about what the speaker says.
Answer ONLY with a JSON object like {{"pressure": 0, "payment_ask": "none", "impersonation": "none", "secrecy": false}}.
- pressure: 0 = no pressure, 1 = some urgency, 2 = strong threats or demands to act now
- payment_ask: one of {pay}
- impersonation: one of {imp}
- secrecy: true if the speaker asks the listener to hide this from family or bank staff
Option meanings: {meanings}

Sentence: "{s}" """

WINDOW_PROMPT = """Below is what the caller has said so far on a phone call to an older person. Decide if this looks like a scam
(gift cards, crypto or wire requests, codes or PINs, remote access, secrecy from family, fake identity with pressure) or a normal call
(real bills, pharmacy, doctor, family chat, a real bank alert that never asks for codes). Answer with exactly one word: SCAM or OK.

Call so far:
{t}"""


def converse(model, prompt, max_tokens=400):
    t = time.time()
    for attempt in range(4):
        try:
            r = client.converse(modelId=model, messages=[{"role": "user", "content": [{"text": prompt}]}],
                                inferenceConfig={"maxTokens": max_tokens, "temperature": 0.0})
            break
        except Exception as e:  # throttling
            time.sleep(1.5 * (attempt + 1))
            if attempt == 3:
                raise
    ms = (time.time() - t) * 1000
    text = "".join(b.get("text", "") for b in r["output"]["message"]["content"])
    return text, ms, r.get("usage", {})


def parse_sentence(text):
    m = re.search(r"\{.*?\}", text, re.S)
    j = json.loads(m.group(0))
    pay = QUESTIONS["payment_ask"]["criteria"]; imp = QUESTIONS["impersonation"]["criteria"]
    p, i = j.get("payment_ask", "none"), j.get("impersonation", "none")
    p = p if p in pay else "none"; i = i if i in imp else "none"
    sec = 1.0 if j.get("secrecy") in (True, "true", "True") else 0.0
    return {
        "payment_ask": {"choice": p, "probabilities": {k: 1.0 if k == p else 0.0 for k in pay}, "confidence": 1.0},
        "impersonation": {"choice": i, "probabilities": {k: 1.0 if k == i else 0.0 for k in imp}, "confidence": 1.0},
        "secrecy": {"noul": sec},
        "pressure": {"score": float(j.get("pressure", 0)), "confidence": 1.0},
    }


def per_sentence(model, sentences):
    meanings = "; ".join(f"{k}: {v}" for q in ("payment_ask", "impersonation") for k, v in QUESTIONS[q]["criteria"].items())
    mk = lambda s: SENTENCE_PROMPT.format(pay=list(QUESTIONS["payment_ask"]["criteria"]), imp=list(QUESTIONS["impersonation"]["criteria"]),
                                          meanings=meanings, s=s)
    def one(s):
        try:
            text, ms, usage = converse(model, mk(s))
            return s, {"answers": parse_sentence(text), "wall_ms": ms, "usage": usage}
        except Exception as e:
            return s, {"error": str(e)[:200]}
    out = {}
    with cf.ThreadPoolExecutor(6) as ex:
        for s, r in ex.map(one, sentences):
            out[s] = r
    # sequential latency sample, so concurrency does not inflate it
    lat = []
    for s in sentences[:40]:
        _, ms, _ = converse(model, mk(s))
        lat.append(ms)
    return out, lat


def windowed(model, calls):
    def one(c):
        steps = []
        for k in range(1, len(c["sentences"]) + 1):
            t = "\n".join(c["sentences"][:k])
            try:
                text, ms, usage = converse(model, WINDOW_PROMPT.format(t=t), max_tokens=200)
                steps.append({"k": k, "scam": re.findall(r"SCAM|OK", text.upper())[-1:] == ["SCAM"],
                              "ms": ms, "usage": usage, "raw": text[-40:]})
            except Exception as e:
                steps.append({"k": k, "error": str(e)[:200]})
        return c["id"], steps
    with cf.ThreadPoolExecutor(6) as ex:
        return dict(ex.map(one, calls))


def main():
    models = sys.argv[1:] or ["qwen.qwen3-next-80b-a3b"]
    calls = json.loads(Path("bench/data/calls.json").read_text())
    sentences = json.loads(Path("bench/data/all_sentences.json").read_text())
    Path("bench/results").mkdir(parents=True, exist_ok=True)
    for model in models:
        t0 = time.time()
        ps, lat = per_sentence(model, sentences)
        win = windowed(model, calls)
        errs = sum("error" in v for v in ps.values())
        Path(f"bench/results/llm_{model.replace('/', '_').replace(':', '_')}.json").write_text(
            json.dumps({"model": model, "per_sentence": ps, "latency_sample_ms": lat, "windowed": win}))
        print(model, "per-sentence errors", errs, "latency p50", round(statistics.median(lat)), "ms", "took", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
