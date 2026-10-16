"""Score a JSON list of sentences with the running Decider server and save every answer.

Standard library only. Resumable: sentences already in the output file are skipped.
  docker exec decider python /app/score_sentences.py /app/data/all_sentences.json /results/answers.json
The output maps sentence -> {"answers": ..., "wall_ms": ...}. The same file is the replay cache for the demo and benchmark.
"""
import json
import os
import sys
import time

sys.path.insert(0, "/app")
from smoke import post, wait_ready  # noqa: E402

QUESTIONS = json.load(open(os.environ.get("QUESTIONS_JSON", "/app/data/questions.json")))


def main(src, dst):
    health = wait_ready()
    sentences = json.load(open(src))
    done = json.load(open(dst)) if os.path.exists(dst) else {"model": health["model"], "answers": {}}
    assert done["model"] == health["model"], "output file is for another model"
    todo = [s for s in sentences if s not in done["answers"]]
    print("model", health["model"], "device", health["device"], "todo", len(todo), "of", len(sentences), flush=True)
    t0 = time.time()
    for i, s in enumerate(todo):
        out, ms = post({"state": s, "questions": QUESTIONS})
        done["answers"][s] = {"answers": out["answers"], "wall_ms": round(ms, 1)}
        if i % 25 == 24 or i == len(todo) - 1:
            json.dump(done, open(dst, "w"))
            print("  %d/%d  %.0fs" % (i + 1, len(todo), time.time() - t0), flush=True)
    print("done")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
