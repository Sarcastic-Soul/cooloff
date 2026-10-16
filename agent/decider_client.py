"""Calls Decider for one sentence. Two modes:

  live    POST to a running `strands-decider serve` (default http://127.0.0.1:8000)
  replay  look the sentence up in a saved answers file (made by scripts/score_sentences.py)

Replay makes the demo and the benchmark repeatable and lets anyone run the repo without a model or a GPU.
Replay answers are real Decider answers recorded earlier. The session log says which mode produced them.
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

from patterns.rolling_risk_gate import QUESTIONS


class DeciderClient:
    def __init__(self, url: str | None = None, replay_file: str | Path | None = None, timeout: float = 120.0):
        assert url or replay_file, "give a url (live) or a replay_file (replay)"
        self.url = url.rstrip("/") if url else None
        self.timeout = timeout
        self.cache: dict[str, dict] = {}
        self.model = None
        if replay_file:
            data = json.loads(Path(replay_file).read_text())
            self.cache, self.model = data["answers"], data.get("model")
        self.mode = "live" if (url and not replay_file) else "replay"

    def score(self, sentence: str) -> tuple[dict, float]:
        """Returns (answers, milliseconds). In replay mode the milliseconds are the recorded ones."""
        if self.mode == "replay":
            hit = self.cache[sentence]  # KeyError on purpose: a missing sentence must not be faked
            return hit["answers"], hit["wall_ms"]
        body = json.dumps({"state": sentence, "questions": QUESTIONS}).encode()
        req = urllib.request.Request(self.url + "/v1/systemone", data=body, headers={"content-type": "application/json"})
        t = time.time()
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            out = json.loads(r.read())
        return out["answers"], (time.time() - t) * 1000
