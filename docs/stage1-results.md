# Stage 1: can Decider 2B read scam-call sentences?

Before building anything, we checked whether Decider 2B can answer our four questions on single call sentences,
well enough to feed a risk gate. Both public checkpoints were tested on the same 100 hand-labeled sentences
(`eval/stage1_data.py`, runner `eval/stage1_eval.py`, raw output in `bench/results/stage1/`).

Test box: EC2 `c7i.2xlarge` (8 vCPU, 16 GB RAM), CPU only, Decider server in Docker, GitHub commit
`6039cf8` of `strands-labs/strands-decider`.

## The four questions

| Question | Kind | What it asks |
| --- | --- | --- |
| payment_ask | choice | Does the speaker ask for money, a gift card, a password or remote access? |
| impersonation | choice | Who does the speaker claim to be (bank, government, tech support, relative, prize, romance, nobody)? |
| secrecy | noul | Does the speaker ask the listener to keep this quiet? |
| pressure | score | How much time pressure is the speaker applying (0 to 2)? |

The 100 sentences mix scam sentences with ordinary ones. 28 are harmless on purpose (real bills, a real bank alert,
an honest grandchild asking for a ride, a harmless secret). They are there to measure false alarms.

## Results

| | hobson-v19 | qwen3.5-v1-2610 (chosen) |
| --- | --- | --- |
| payment_ask accuracy | 0.91 | **0.94** |
| payment danger recall (picked option) | 16/24 | **20/24** |
| payment danger on harmless sentences | 0/28 | 0/28 |
| impersonation accuracy | 0.74 | 0.74 |
| secrecy (true / false positives / misses) | 9 / 0 / 4 | 8 / 0 / 5 |
| pressure exact / mean error | 0.34 / 0.556 | 0.40 / 0.585 |
| harmless sentences with any false signal | 2/28 | 2/28 |
| median time per sentence (4 questions, CPU) | 3.69 s | 3.46 s |

## The finding that shaped the design

The picked answer is not the best thing to use. Decider also returns the probability of every option. Taking the
probability mass on the dangerous options of `payment_ask`, with qwen3.5-v1-2610:

| Signal | AUC |
| --- | --- |
| payment danger mass | **1.00** |
| secrecy | 0.98 |
| pressure (2 vs 0) | 0.98 |
| any claimed identity | 0.95 |

At a threshold of 0.3 on payment danger mass, 23 of 24 dangerous sentences are caught and none of the 76 other
sentences is flagged. So Cooloff feeds probabilities, not picked options, into the gate
(`patterns/rolling_risk_gate/questions.py`).

## Caveats

- Impersonation accuracy (0.74) is below the 85% we hoped for. Many of the misses are sentences where the identity is
  only hinted at ("your account has been flagged") and not claimed. The question asks who the speaker *claims* to be,
  so the model is arguably right and our labels are strict. We kept the labels as written. Two harmless sentences that
  start with "Honey" or "Dear" were read as romance. The gate treats impersonation as supporting evidence only.
- Latency on CPU is about 3.5 s per sentence for four questions. That is far from the 300 ms we hoped for, and a GPU
  is needed for that. See the README for the numbers we could measure.
- 100 sentences is a small set, written by us. It is enough to choose a checkpoint, not to claim a production error rate.
  The larger call-level test is in `bench/`.
