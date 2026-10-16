"""Plays a scripted call through the whole Cooloff stack and records every step as events (for the demo page).

For each caller sentence: Decider scores it, the gate updates. When the parent asks the agent to move money, the agent
(Strands + Bedrock) tries the tool and the TransactionHold decides. On the first red, Bedrock writes the parent message,
the family text and the incident summary. The family answers KEEP and the held action is cancelled.

Run:  uv run python -m agent.session demo/scripts/grandchild_gift_cards.json --replay bench/data/decider_answers_cpu.json --out demo/sessions
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from patterns.rolling_risk_gate import AMBER, RED, make_gate

from . import netmon
from .bedrock_voice import BedrockVoice
from .cooloff_agent import build_agent, resume, run_request
from .decider_client import DeciderClient
from .mock_bank import MockBank

AMBER_TEXT = "Something on this call sounds unusual. Take your time, and do not buy cards, share codes or send money yet."


def brief(answers: dict) -> dict:
    return {
        "payment_ask": answers["payment_ask"]["choice"], "payment_p": answers["payment_ask"]["probabilities"],
        "impersonation": answers["impersonation"]["choice"], "impersonation_p": answers["impersonation"]["probabilities"],
        "secrecy": answers["secrecy"]["noul"], "pressure": answers["pressure"]["score"],
    }


def run_script(script: dict, decider: DeciderClient, voice: BedrockVoice | None = None, use_agent: bool = True) -> dict:
    netmon.install()
    netmon.reset()
    voice = voice or BedrockVoice()
    bank = MockBank()
    gate = make_gate()
    events: list[dict] = []
    ev = lambda type_, **kw: events.append({"type": type_, "t_net_voice": netmon.total("voice"), "t_net_agent": netmon.total("agent"),
                                             "net_total": netmon.total(), **kw})
    held_info: dict = {}

    def on_hold(tool, inp, state):
        held_info.update(tool=tool, input=inp, gate=state)

    agent, hold = build_agent(bank, gate, on_hold=on_hold) if use_agent else (None, None)
    ev("start", script=script["id"], title=script["title"], kind=script["kind"], summary=script["summary"],
       decider_mode=decider.mode, decider_model=decider.model, balance=bank.balance)

    best: dict[str, tuple[float, str]] = {}  # per signal: strongest value so far and the sentence that caused it
    pending = None
    red_voice_done = False
    amber_shown = False
    pa = script.get("payment_attempt")

    for idx, line in enumerate(script["lines"]):
        if line["speaker"] == "caller":
            answers, ms = decider.score(line["text"])
            snap = gate.update(answers)
            for s in gate.signals:
                v, _ = s.extract(answers)
                if v > best.get(s.name, (0, ""))[0]:
                    best[s.name] = (v, line["text"])
            ev("sentence", idx=idx, speaker="caller", text=line["text"], decider_ms=ms, answers=brief(answers),
               gate=snap.__dict__)
            if snap.state == AMBER and not amber_shown:
                amber_shown = True
                ev("amber", text=AMBER_TEXT, note="local message, nothing sent to the cloud")
            if snap.state == RED and snap.changed:
                ev("red", step=snap.step, reason=snap.reason, active=snap.active)
        else:
            ev("sentence", idx=idx, speaker="parent", text=line["text"])

        if pa and idx == pa["after_line"] and agent:
            ev("parent_request", text=pa["request"], gate_state=gate.state)
            with netmon.tag("agent"):
                result = run_request(agent, pa["request"])
            if result["status"] == "held":
                ev("held", tool=held_info.get("tool"), input=held_info.get("input"), gate=held_info.get("gate"),
                   balance=bank.balance, note="the agent paused and is waiting for the family")
                pending = result
                # Bedrock writes the words, but only now that the gate is red
                active_sigs = [n for n in gate.snapshot().active] or list(best)
                ranked = sorted(((best[n][0], n, best[n][1]) for n in active_sigs if n in best), reverse=True)
                quotes, seen = [], set()
                for _, _, text in ranked:
                    if text not in seen:
                        quotes.append(text)
                        seen.add(text)
                    if len(quotes) == 2:
                        break
                action = f"{held_info['tool']} {held_info['input']}"
                with netmon.tag("voice"):
                    pm = voice.parent_message(quotes)
                    ev("parent_message", text=pm, bytes_sent=voice.log[-1]["bytes"], sent=voice.log[-1]["sent"], ms=voice.log[-1]["ms"])
                    ft = voice.family_text(quotes, action)
                    ev("family_text", text=ft, bytes_sent=voice.log[-1]["bytes"], sent=voice.log[-1]["sent"], ms=voice.log[-1]["ms"])
                    timeline = [f"Step {e['gate']['step']}: caller said “{e['text']}” (gate {e['gate']['state']})"
                                for e in events if e["type"] == "sentence" and e["speaker"] == "caller" and e["gate"]["state"] != "green"]
                    release = script.get("family_decision") == "release"
                    timeline += [f"Held: {action}. Balance unchanged at ${bank.balance:,.2f}."]
                    timeline += ["The family replied RELEASE after calling their parent." if release
                                 else "The family replied KEEP and the payment stays cancelled."]
                    summ = voice.incident_summary(timeline)
                    ev("incident_summary", text=summ, bytes_sent=voice.log[-1]["bytes"], sent=voice.log[-1]["sent"], ms=voice.log[-1]["ms"])
                ev("family_reply", text="RELEASE" if release else "KEEP",
                   note="the family called, it was a real call, and they released the payment" if release
                   else "the family chose to keep the payment frozen")
                with netmon.tag("agent"):
                    out = resume(agent, pending["interrupts"], "yes" if release else "no")
                ev("agent_reply", text=out["text"], balance=bank.balance)
            else:
                ev("agent_reply", text=result["text"], balance=bank.balance, gate_state=gate.state, paid=True)

    ev("end", balance=bank.balance, final_state=gate.state, history=bank.history(),
       net={"voice_bytes": netmon.total("voice"), "agent_bytes": netmon.total("agent"), "total_bytes": netmon.total()},
       net_requests=[{**r, "t": round(r["t"], 3)} for r in netmon.records])
    return {"script": script, "events": events}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script", nargs="+")
    ap.add_argument("--replay", help="answers.json from scripts/score_sentences.py")
    ap.add_argument("--url", help="live Decider server URL")
    ap.add_argument("--out", default="demo/sessions")
    a = ap.parse_args()
    decider = DeciderClient(url=a.url, replay_file=a.replay)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    for p in a.script:
        script = json.loads(Path(p).read_text())
        t = time.time()
        session = run_script(script, decider)
        session["recorded"] = {"decider_mode": decider.mode, "decider_model": decider.model, "seconds": round(time.time() - t, 1)}
        Path(a.out, script["id"] + ".json").write_text(json.dumps(session, indent=1))
        end = session["events"][-1]
        print(script["id"], "final gate:", end["final_state"], "balance:", end["balance"], "net:", end["net"])


if __name__ == "__main__":
    main()
