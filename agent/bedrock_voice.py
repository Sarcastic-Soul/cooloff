"""The only place Cooloff talks to the cloud: Amazon Bedrock writes the words after the gate goes red.

Three short texts: a calm message for the parent, a text for the family (with two exact quotes from the call),
and an incident summary. Each prompt gets a redacted snippet. Every request is logged with its size, so the demo
can show that nothing was sent before red.

Model: qwen.qwen3-next-80b-a3b through the Bedrock Converse API (a non-Claude model, picked after a 25-model test).
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

import boto3

MODEL_ID = "qwen.qwen3-next-80b-a3b"


def redact(text: str, names: dict[str, str] | None = None) -> str:
    """Hide names, phone numbers, long numbers and emails. Dollar amounts stay (the family needs them)."""
    for real, placeholder in (names or {}).items():
        text = re.sub(re.escape(real), placeholder, text, flags=re.I)
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[email]", text)
    text = re.sub(r"(?<![$\d])\d[\d\s().-]{6,}\d", "[number]", text)
    return text


@dataclass
class BedrockVoice:
    region: str = "us-east-1"
    model_id: str = MODEL_ID
    names: dict[str, str] = field(default_factory=lambda: {"Margaret Hale": "[PARENT]", "Margaret": "[PARENT]"})
    log: list[dict] = field(default_factory=list)  # what was sent, how big, how long it took

    def __post_init__(self):
        self._client = boto3.client("bedrock-runtime", region_name=self.region)

    @property
    def bytes_sent(self) -> int:
        return sum(e["bytes"] for e in self.log)

    def _ask(self, purpose: str, system: str, user: str, max_tokens: int = 350) -> str:
        user = redact(user, self.names)
        t = time.time()
        resp = self._client.converse(
            modelId=self.model_id,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": 0.3},
        )
        text = resp["output"]["message"]["content"][0]["text"].strip()
        self.log.append({"purpose": purpose, "bytes": len((system + user).encode()), "sent": user,
                         "ms": round((time.time() - t) * 1000), "model": self.model_id,
                         "tokens": resp.get("usage", {})})
        return text

    def parent_message(self, snippets: list[str]) -> str:
        return self._ask(
            "parent_message",
            "You write a short, calm message that appears on an older person's screen while they are on a phone call "
            "that looks like a scam. Two or three plain sentences, warm and clear, no jargon, no blame, no alarming words. "
            "Say what looks wrong, tell them to pause any payment, and say a text has been sent to their family. Do not say anyone is coming or on their way. Output only the message.",
            "Sentences the caller said:\n" + "\n".join(f"- {s}" for s in snippets),
        )

    def family_text(self, quotes: list[str], held_action: str) -> str:
        """Returns a text for the family. The two quotes are put in by us, word for word, never by the model."""
        draft = self._ask(
            "family_text",
            "You write a short text message from a family-safety app to the grown children of an older parent. "
            "Plain words, calm but clear, under 70 words. Say the app paused a payment during a call that looks like a scam, "
            "name what was held, include the placeholders {Q1} and {Q2} each on its own line (they will be replaced by exact "
            "quotes from the call), and ask them to call their parent and reply KEEP or RELEASE. Output only the text.",
            f"Held action: {held_action}\nThe call has two worrying moments, shown as {{Q1}} and {{Q2}}.",
        )
        q1, q2 = (quotes + ["", ""])[:2]
        if "{Q1}" not in draft or "{Q2}" not in draft:  # the model forgot: add them ourselves
            draft = draft.rstrip() + "\n{Q1}\n{Q2}"
        return draft.replace("{Q1}", f"“{q1}”").replace("{Q2}", f"“{q2}”")

    def incident_summary(self, timeline: list[str]) -> str:
        return self._ask(
            "incident_summary",
            "You write a short incident summary for a family record. Four to six plain sentences: what happened, in what order, "
            "which signals the safety check saw, what was paused, and what the family decided or still needs to decide. "
            "No speculation. Output only the summary.",
            "Timeline:\n" + "\n".join(f"- {t}" for t in timeline),
            max_tokens=400,
        )
