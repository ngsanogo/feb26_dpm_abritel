#!/usr/bin/env bash
# CI locale = même commandes que .github/workflows/ci.yml (sans toucher à .venv du Mac).
# Le venv est dans /tmp du conteneur ; le conteneur est --rm ; l'image est supprimée à la fin.
#
# Usage :
#   ./scripts/ci_docker.sh
#   ./scripts/ci_docker.sh --ollama   # après ruff/pytest, teste Ollama sur le Mac via host.docker.internal
#
# Avec --ollama : Ollama doit tourner sur la machine hôte (ollama serve). Optionnel :
#   ABRITEL_OLLAMA_MODEL=qwen3.5 ./scripts/ci_docker.sh --ollama
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

IMAGE="ghcr.io/astral-sh/uv:bookworm-slim"
WITH_OLLAMA=0
if [[ "${1:-}" == "--ollama" ]]; then
  WITH_OLLAMA=1
fi

cleanup() {
  docker image rm -f "$IMAGE" >/dev/null 2>&1 || true
}
trap cleanup EXIT

DOCKER_ARGS=(--rm)
# Accès au daemon Ollama sur le Mac depuis le conteneur (Linux : host-gateway)
DOCKER_ARGS+=(--add-host=host.docker.internal:host-gateway)
DOCKER_ARGS+=(-e "UV_PROJECT_ENVIRONMENT=/tmp/uv-ci-abritel-docker")
DOCKER_ARGS+=(-v "$ROOT:/app" -w /app)

if [[ "$WITH_OLLAMA" -eq 1 ]]; then
  if ! curl -sf "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
    echo "Ollama ne répond pas sur http://127.0.0.1:11434 — lance « ollama serve » puis réessaie." >&2
    exit 1
  fi
  DOCKER_ARGS+=(-e "ABRITEL_OLLAMA_URL=http://host.docker.internal:11434")
  DOCKER_ARGS+=(-e "ABRITEL_OLLAMA_MODEL=${ABRITEL_OLLAMA_MODEL:-qwen3.5}")
  DOCKER_ARGS+=(-e "ABRITEL_OLLAMA_TIMEOUT=${ABRITEL_OLLAMA_TIMEOUT:-300}")
fi

RUNNER=(bash -lc)
CMD='uv sync --extra dev && uv run ruff check . && uv run ruff format --check . && uv run pytest -m "not slow" -q'
if [[ "$WITH_OLLAMA" -eq 1 ]]; then
  CMD+=" && uv run python scripts/smoke_ollama_docker.py"
fi
RUNNER+=("$CMD")

docker run "${DOCKER_ARGS[@]}" "$IMAGE" "${RUNNER[@]}"

echo "CI Docker : OK (image ${IMAGE} supprimée du moteur local)."
