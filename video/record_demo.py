"""Records one demo scenario as an mp4 with call audio and narration.

Run with the demo-video-pipeline venv (it has playwright and the Kokoro voice):
  PIPELINE=/home/anish-kumar/Code/Hackathons/demo-video-pipeline
  uv run --project $PIPELINE python video/record_demo.py grandchild_gift_cards video/out
The demo server must be running on localhost:8765. The page adds silent pauses (video mode) and the narrator
speaks in them, so the narration never talks over the caller.
"""
import base64
import json
import subprocess
import sys
import time
from pathlib import Path

PIPELINE = Path("/home/anish-kumar/Code/Hackathons/demo-video-pipeline")
sys.path.insert(0, str(PIPELINE))
from common import tts  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
KEYS = ["start", "amber", "red", "held", "messages", "end"]


def main(sid, out_dir):
    out = Path(out_dir) / sid
    out.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((ROOT / "video/narration.json").read_text())[sid]
    gaps, wavs = {}, {}
    for k in KEYS:
        if k in cfg:
            w = out / f"nar_{k}.wav"
            dur = tts.synthesize(cfg[k], str(w), voice="af_heart", speed=1.0)
            gaps[k], wavs[k] = int(dur * 1000 + 800), w
    qs = "&".join(f"gap_{k}={v}" for k, v in gaps.items()) + ("&trim_after=agent_reply" if cfg.get("trim_after") else "")
    frames = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        pg.goto(f"http://localhost:8765/?id={sid}&video=1&{qs}")
        pg.wait_for_selector(".scenarios button")
        pg.wait_for_timeout(800)
        cdp = pg.context.new_cdp_session(pg)

        def on_frame(ev):
            frames.append((ev["metadata"]["timestamp"], ev["data"]))
            cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})

        cdp.on("Page.screencastFrame", on_frame)
        cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": 1920, "maxHeight": 1080, "everyNthFrame": 1})
        pg.wait_for_timeout(500)
        pg.evaluate("document.getElementById('play').click()")
        info = pg.evaluate("({start: window.cooloffStartEpoch, dur: window.cooloffDuration, marks: window.cooloffMarks, tl: window.cooloffTimeline})")
        t_end = info["start"] / 1000 + info["dur"] / 1000 + 1.5
        while time.time() < t_end:
            pg.wait_for_timeout(250)
        cdp.send("Page.stopScreencast")
        b.close()

    t0 = info["start"] / 1000 - 0.2
    fdir = out / "frames"
    fdir.mkdir(exist_ok=True)
    for old in fdir.glob("*.jpg"):
        old.unlink()
    # keep the last frame before t0 as the first frame
    before = [i for i, (ts, _) in enumerate(frames) if ts <= t0]
    frames = frames[before[-1]:] if before else frames
    lines, ts_list = [], [max(ts, t0) for ts, _ in frames]
    for i, (_, data) in enumerate(frames):
        (fdir / f"{i:05d}.jpg").write_bytes(base64.b64decode(data))
        nxt = ts_list[i + 1] if i + 1 < len(frames) else t_end
        lines.append(f"file '{fdir}/{i:05d}.jpg'\nduration {max(nxt - ts_list[i], 0.001):.4f}")
    lines.append(f"file '{fdir}/{len(frames) - 1:05d}.jpg'")
    (out / "frames.txt").write_text("\n".join(lines))
    total = t_end - t0
    silent = out / "silent.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(out / "frames.txt"), "-vf", "fps=30,format=yuv420p",
                    "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-t", f"{total:.3f}", str(silent)], check=True)

    # audio: call lines + narration at their offsets (page time starts 0.2 s into the clip)
    inputs, filters, labels = [], [], []
    offset = 0.2
    for item in info["tl"]:
        mp3 = ROOT / "demo/web" / item["audio"]
        inputs += ["-i", str(mp3)]
        n = len(labels)
        filters.append(f"[{n}:a]aresample=48000,volume=0.9,adelay={int(item['at'] + offset * 1000)}:all=1[a{n}]")
        labels.append(f"[a{n}]")
    for m in info["marks"]:
        inputs += ["-i", str(wavs[m["key"]])]
        n = len(labels)
        filters.append(f"[{n}:a]aresample=48000,volume=1.15,adelay={int(m['at'] + 150 + offset * 1000)}:all=1[a{n}]")
        labels.append(f"[a{n}]")
    filters.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:dropout_transition=0,apad=whole_dur={total:.3f}[mix]")
    audio = out / "audio.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filters), "-map", "[mix]", "-t", f"{total:.3f}", str(audio)], check=True)
    final = out / f"{sid}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(audio), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(final)], check=True)
    print(sid, "->", final, f"{total:.1f}s", "marks", [(m['key'], m['at'], m['dur']) for m in info['marks']])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
