"""Serves the demo page and the recorded sessions.  Run: uv run uvicorn demo.server:app --port 8765
Binds to localhost only. There is no login here, so do not expose it to a network."""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).parent
app = FastAPI(title="Cooloff demo")


@app.get("/api/sessions")
def sessions():
    out = []
    for p in sorted((ROOT / "sessions").glob("*.json")):
        s = json.loads(p.read_text())
        out.append({"id": s["script"]["id"], "title": s["script"]["title"], "kind": s["script"]["kind"], "summary": s["script"]["summary"]})
    order = ["grandchild_gift_cards", "fake_bank_safe_account", "real_pharmacy", "real_bank_alert"]
    return sorted(out, key=lambda x: order.index(x["id"]) if x["id"] in order else 99)


@app.get("/api/session/{sid}")
def session(sid: str):
    p = ROOT / "sessions" / f"{Path(sid).name}.json"
    if not p.exists():
        raise HTTPException(404)
    return json.loads(p.read_text())


app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
