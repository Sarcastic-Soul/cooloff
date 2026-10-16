#!/usr/bin/env bash
# Checks this machine and recommends a mode (gpu or cpu). Run: ./scripts/doctor.sh
# Works on Linux, macOS, and Windows through WSL2 or Git Bash.
set -u

ok()   { printf '  [ok]   %s\n' "$*"; }
warn() { printf '  [warn] %s\n' "$*"; }
bad()  { printf '  [FAIL] %s\n' "$*"; }

echo "== system"
uname -a
if [ -r /proc/meminfo ]; then
  total_kb=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
  avail_kb=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
  echo "  RAM total $((total_kb/1024)) MB, available $((avail_kb/1024)) MB"
  [ "$avail_kb" -ge 9000000 ] && ok "enough free RAM for cpu mode (needs about 8 GB)" || warn "less than 9 GB free RAM; close other apps before cpu mode"
fi
echo "  disk free here: $(df -h . | awk 'NR==2 {print $4}') (need about 25 GB for images and model)"

echo "== docker"
if command -v docker >/dev/null 2>&1; then
  ok "$(docker --version)"
  docker compose version >/dev/null 2>&1 && ok "$(docker compose version | head -1)" || bad "docker compose plugin missing"
  docker info >/dev/null 2>&1 && ok "docker daemon reachable" || bad "docker daemon not reachable (start Docker Desktop, or add your user to the docker group)"
else
  bad "docker not installed"
fi

echo "== gpu"
mode=cpu
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,memory.total,memory.used,driver_version --format=csv,noheader
  free_mb=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
  echo "  free VRAM: ${free_mb} MB"
  if docker info 2>/dev/null | grep -qi nvidia || docker run --rm --gpus all python:3.12-slim true >/dev/null 2>&1; then
    ok "docker can use the GPU"
    if [ "${free_mb:-0}" -ge 5500 ]; then
      ok "enough VRAM for gpu mode"; mode=gpu
    else
      warn "under 5.5 GB VRAM free; gpu mode may run out of memory. Close games, browsers, and other GPU apps, then re-run this check."
      mode=gpu-tight
    fi
  else
    warn "docker cannot use the GPU. Linux: install NVIDIA Container Toolkit. Windows: Docker Desktop with WSL2 backend and a current NVIDIA driver."
  fi
else
  warn "nvidia-smi not found (no NVIDIA driver, or running outside WSL2 on Windows)"
fi

echo
echo "== recommendation"
case "$mode" in
  gpu)       echo "  docker compose --profile gpu up -d --build" ;;
  gpu-tight) echo "  try:      docker compose --profile gpu up -d --build"
             echo "  fallback: docker compose --profile cpu up -d --build" ;;
  *)         echo "  docker compose --profile cpu up -d --build" ;;
esac
echo "  then:     docker compose exec decider python /app/smoke.py"
