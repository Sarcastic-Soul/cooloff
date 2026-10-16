"""Make Amazon Polly voices for the scripted calls. Voices only: no real people, no brands.
Writes demo/web/audio/<script id>/<line index>.mp3 and demo/web/audio/manifest.json (durations in ms).
Run: uv run python demo/make_audio.py
"""
import json
import subprocess
from pathlib import Path

import boto3

polly = boto3.client("polly", region_name="us-east-1")
VOICES = {  # script id -> (caller voice, parent voice)
    "grandchild_gift_cards": ("Justin", "Ruth"),
    "fake_bank_safe_account": ("Matthew", "Ruth"),
    "real_pharmacy": ("Salli", "Ruth"),
    "real_bank_alert": ("Kendra", "Ruth"),
}


def duration_ms(path: Path) -> int:
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    return round(float(out) * 1000)


def synth(text: str, voice: str, path: Path):
    r = polly.synthesize_speech(Engine="neural", VoiceId=voice, OutputFormat="mp3", Text=text)
    path.write_bytes(r["AudioStream"].read())


def main():
    root = Path("demo/web/audio")
    manifest = {}
    for sid, (caller, parent) in VOICES.items():
        script = json.loads(Path(f"demo/scripts/{sid}.json").read_text())
        (root / sid).mkdir(parents=True, exist_ok=True)
        manifest[sid] = {}
        for i, line in enumerate(script["lines"]):
            p = root / sid / f"{i}.mp3"
            synth(line["text"], caller if line["speaker"] == "caller" else parent, p)
            manifest[sid][i] = duration_ms(p)
    (root / "manifest.json").write_text(json.dumps(manifest))
    print({k: sum(v.values()) // 1000 for k, v in manifest.items()}, "seconds of speech")


if __name__ == "__main__":
    main()
