# Cooloff

An on-device scam-call gate for family money, built with Strands Decider 2B and Amazon Bedrock.
Work in progress for the AWS Agent Experience Hackathon (Strands Decider).

This commit contains only the test harness for running Decider 2B on a machine, in Docker.
The agent, the `rolling_risk_gate` pattern, the demo page and the benchmark come next.

## Quick start: test Decider on this machine

You need Docker with the Compose plugin and about 25 GB of free disk. No Python install is needed.
The Decider server has no password. It is never published to the network.

```bash
# 1. check the machine and get a recommendation (gpu or cpu)
./scripts/doctor.sh

# 2. start the server (first start downloads the model, about 4.5 GB)
docker compose --profile gpu up -d --build     # NVIDIA GPU
# or
docker compose --profile cpu up -d --build     # CPU only, needs about 8 GB free RAM

# 3. send the four Cooloff questions on five sample sentences
docker compose exec decider python /app/smoke.py

# 4. while step 3 runs (or right after), record memory use
nvidia-smi                       # GPU mode: note "Memory-Usage"
docker stats --no-stream decider # RAM use of the container

# 5. stop
docker compose --profile gpu down    # or --profile cpu
```

Results land in `./results/smoke.json` (ignored by git). Copy it back after a run.

### Windows

Use Docker Desktop with the WSL2 backend and a current NVIDIA driver. Run the commands above in a WSL2 terminal
(Ubuntu), from a clone of this repo inside the WSL2 filesystem (not under `/mnt/c`, which is slow).

### If the GPU run fails

- `docker: could not select device driver "nvidia"`: Docker cannot see the GPU. On Linux install the NVIDIA Container Toolkit.
  On Windows check Docker Desktop settings and update the NVIDIA driver.
- Out of memory: the RTX 3050 has 6 GB, and the model needs about 5 GB plus working space. Close games and browsers
  and try again, or use the `cpu` profile.

## Model

Default: `StrandsAgents/strands-decider-2B-hobson-v19`. Try the newer one with
`DECIDER_MODEL=StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 docker compose --profile gpu up -d --build`.

## License

Apache-2.0. See `LICENSE`.
