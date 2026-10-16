# Cooloff

An agent that looks after an older parent's money during a phone call, built with Strands Decider 2B and Amazon Bedrock.
Made for the AWS Agent Experience Hackathon (Strands Decider). Tags: `#strands-decider-2b` `#policy`.

**This is a simulation.** The bank is a mock (SQLite), the callers are scripts, and the voices are text-to-speech.
Cooloff does not listen to real phone calls and does not touch real accounts. The numbers below come from our own
generated test calls and are a sketch, not a production error rate.

## The idea

Scam calls work because they push an older person to act before anyone else can say "wait". Cooloff sits beside the
call. A small local model, Strands Decider 2B, reads each sentence the caller says and answers four typed questions:

| Question | What it asks |
| --- | --- |
| `payment_ask` | Is the caller asking for a gift card, crypto, a wire, remote access, or a password or code? |
| `impersonation` | Who does the caller claim to be (relative in trouble, bank, government, tech support, romance, prize)? |
| `secrecy` | Is the caller asking the parent to keep this from family or bank staff? |
| `pressure` | How hard is the caller pushing the parent to act now (0 to 2)? |

A plain-code gate, `rolling_risk_gate`, keeps a moving level for each signal. **Red needs two different kinds of signal**,
so one odd sentence never locks anyone out. On red, the Strands agent's payment tools are held with a Strands
`InterventionHandler` (`TransactionHold`), and only then does Amazon Bedrock (Qwen3-Next, not a Claude model) write three
short texts: a calm message for the parent, a text for the family with two exact quotes from the call, and an incident summary.

Decider decides. Bedrock only talks, and only after red. Before red, no word of the call leaves the device.

## What we measured

Test set: 76 generated calls (about 10 sentences each, 924 sentences). 46 are in the test half: 23 scam calls and
23 normal calls (real pharmacy, real bank alert, honest grandchild, insurance premium and others). Gate numbers were
tuned on the other half. Everything here is from `bench/results/summary.json` and can be re-run with `bench/analyze.py`.

| Method | Scam calls caught | Normal calls frozen by mistake | Speed per sentence (median) | Cost |
| --- | --- | --- | --- | --- |
| Decider 2B + gate, on GPU (g6.xlarge) | 23/23 | 5/23 | 144 ms | $0.032 per 1,000 sentences on a rented GPU |
| Decider 2B + gate, on CPU (c7i.2xlarge) | 23/23 | 5/23 | 3,473 ms | $0.344 per 1,000 sentences on a rented CPU |
| Decider 2B + gate, on a device the family owns | 23/23 | 5/23 | as above | $0 |
| Same, but one signal is enough for red | 23/23 | 19/23 | | |
| Qwen3-Next 80B per sentence + same gate (Bedrock) | 23/23 | 2/23 | 936 ms | $0.085 per 1,000 sentences |
| Qwen3-Next 80B on the whole call so far (Bedrock) | 23/23 | 4/23 | 486 ms | $0.00038 per call |
| gpt-oss-120b per sentence + same gate (Bedrock) | 14/23 | 1/23 | 1,398 ms | $0.181 per 1,000 sentences |
| gpt-oss-120b on the whole call so far (Bedrock) | 23/23 | 4/23 | 844 ms | $0.0011 per call |

What this says, in plain words:

- Decider with the two-signal gate caught every scam call, a median of 3 sentences in (27% of the call heard).
- It froze 5 of 23 normal calls by mistake. The best Bedrock LLM setup froze 2 of 23. Most mistakes came from the real bank
  alert, which says things like "we will never ask for your PIN" (a password mention plus a bank claim). With only 23 normal
  calls, treat the gap as a rough size, not a precise rate.
- The two-signal rule matters: with one signal the false freezes go from 5 to 19 of 23.
- A GPU makes Decider about 24 times faster than a CPU (144 ms against 3.5 s for all four questions) and faster than the
  Bedrock calls we measured. On a CPU it is slower than Bedrock.
- Where Decider wins is privacy and cost, not accuracy. The LLM setups send every sentence to the cloud. Decider sends
  nothing before red. It also gives calibrated probabilities (AUC 1.00 on payment danger, 0.98 on secrecy and pressure on
  our 100 hand-labeled sentences), which the gate uses. See `docs/stage1-results.md`.
- GPU (bf16) and CPU (fp32) gave the same decisions for all but one of 924 sentences at the 0.3 payment-danger line.
- Bedrock prices are from third-party price lists. Check AWS before quoting them.

Charts: `bench/results/detection_vs_false_freeze.png`, `time_to_freeze.png`, `confidence_vs_accuracy.png`.

## Quick start

You need [uv](https://docs.astral.sh/uv/) and Python 3.11 or newer. Node is not needed.

```bash
uv sync
uv run pytest                                          # 11 tests for the gate, the hold and the mock bank

# the reusable pattern on a different job (no money): a child's chat
uv run python -m examples.kids_chat.chat_gate

# the demo page: four recorded calls (each was recorded through the real agent and gate)
uv run uvicorn demo.server:app --port 8765             # then open http://localhost:8765
```

The demo server has no login and binds to localhost only. Do not expose it to a network.

The four calls are: a fake grandchild asking for gift cards, a fake bank "fraud team", a real pharmacy call that stays
green, and a real bank alert that freezes by mistake (shown as a false alarm that the family releases).

### Run the full stack yourself

Recording a session needs AWS credentials with Bedrock access (model `qwen.qwen3-next-80b-a3b` in `us-east-1`) and either
saved Decider answers (replay) or a Decider server.

```bash
# replay saved Decider answers, live Bedrock for the words
uv run python -m agent.session demo/scripts/grandchild_gift_cards.json \
  --replay bench/data/decider_answers_cpu.json --out demo/sessions

# re-run the benchmark (needs the baseline result files in bench/results/)
uv run python bench/analyze.py bench/data/decider_answers_cpu.json bench/data/decider_answers_gpu.json
```

## Run Decider 2B itself

You need Docker with the Compose plugin and about 25 GB of free disk (160 GB root disk on the GPU image, see below).
The Decider server has no password. It is never published to the network; other containers share its network.

```bash
docker compose --profile gpu up -d --build     # NVIDIA GPU
# or
docker compose --profile cpu up -d --build     # CPU only, needs about 8 GB free RAM

docker compose exec decider python /app/smoke.py                                  # five sample sentences
docker compose exec decider python /app/score_sentences.py /app/data/all_sentences.json /results/answers.json
docker compose --profile gpu down
```

First start downloads the model (about 4.5 GB). Default model is `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610`. Set
`DECIDER_MODEL=StrandsAgents/strands-decider-2B-hobson-v19` to use the older one. On the GPU, Decider used about 4.6 GB of
GPU memory.

`scripts/doctor.sh` checks the machine and recommends `gpu` or `cpu`.

### EC2

`g6.xlarge` (NVIDIA L4) is the fast option and `c7i.2xlarge` is the CPU option. Both are reached through SSM only, with
no open ports.

```bash
COOLOFF_SG=<no-inbound sg> COOLOFF_SUBNET=<subnet> scripts/aws/launch.sh gpu   # or cpu
scripts/aws/teardown.sh                                                        # terminates every box tagged project=cooloff
```

Notes from our runs: the GPU Deep Learning AMI alone uses about 55 GB, so the script asks for a 160 GB root disk on `gpu`.
`g6.xlarge` had no free capacity in some Availability Zones, so you may need to try other subnets. A new account needs a
quota increase for G-family vCPUs. The Docker image installs `gcc` because Triton compiles a small kernel on the GPU.

## What is in the repo

| Path | What |
| --- | --- |
| `patterns/rolling_risk_gate/` | **The reusable Decider decision pattern** (`policy`): questions, gate, `TransactionHold`, thresholds, and a short `USAGE.md` |
| `examples/kids_chat/` | Same gate, different job: warn a child about a stranger's messages |
| `agent/` | The Strands agent, mock bank, Decider client, Bedrock voice, and the session recorder |
| `demo/` | The demo page and four recorded sessions |
| `bench/` | Generated calls, the benchmark, the baselines, saved Decider answers, charts |
| `eval/`, `docs/stage1-results.md` | The 100-sentence test used to pick a checkpoint |
| `scripts/`, `Dockerfile.decider`, `compose.yaml` | Running Decider in Docker, locally or on EC2 |
| `video/` | Scripts used to record the demo clips |

## Limits

- Simulation only. Mock bank, scripted callers, text-to-speech voices.
- Calls are generated, normal calls are only 23 in the test half, and the sentence text comes from us and from a model.
- 5 of 23 normal calls were frozen by mistake. A real product would need a quick "this is fine" path for the family, which
  the demo shows but does not tune.
- Impersonation accuracy was 0.74, below the 85% we hoped for. The gate uses it as supporting evidence only.
- On a CPU, scoring one sentence takes about 3.5 s. That is too slow for a live call without a GPU.
- There is no speech-to-text. The demo starts from sentences, not audio.

## License

Apache-2.0. See `LICENSE`.
