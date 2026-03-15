#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

WITH_SERVICES=0
PYTEST_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --with-services)
            WITH_SERVICES=1
            shift
            ;;
        --)
            shift
            while [[ $# -gt 0 ]]; do
                PYTEST_ARGS+=("$1")
                shift
            done
            ;;
        *)
            PYTEST_ARGS+=("$1")
            shift
            ;;
    esac
done

wait_for_health() {
    local name="$1"
    local url="$2"
    local retries=60
    local sleep_seconds=1

    for _ in $(seq 1 "$retries"); do
        if curl -fsS "$url" >/dev/null 2>&1; then
            echo "$name is healthy at $url"
            return 0
        fi
        sleep "$sleep_seconds"
    done

    echo "Timed out waiting for $name at $url" >&2
    return 1
}

SERVICE_PIDS=()
cleanup_services() {
    if [[ ${#SERVICE_PIDS[@]} -gt 0 ]]; then
        kill "${SERVICE_PIDS[@]}" >/dev/null 2>&1 || true
        wait "${SERVICE_PIDS[@]}" 2>/dev/null || true
    fi
}

if [[ "$WITH_SERVICES" -eq 1 ]]; then
    trap cleanup_services EXIT

    uv run python -m uvicorn ai_router.node_manager_server:app --host 127.0.0.1 --port 9000 >/tmp/raphael-node-manager.log 2>&1 &
    SERVICE_PIDS+=("$!")

    uv run python -m uvicorn ai_router.embedding_server:app --host 127.0.0.1 --port 9100 >/tmp/raphael-embedding.log 2>&1 &
    SERVICE_PIDS+=("$!")

    uv run python -m uvicorn ai_router.code_embedding_server:app --host 127.0.0.1 --port 9200 >/tmp/raphael-code-embedding.log 2>&1 &
    SERVICE_PIDS+=("$!")

    wait_for_health "Node manager" "http://127.0.0.1:9000/health"
    wait_for_health "Embedding server" "http://127.0.0.1:9100/health"
    wait_for_health "Code embedding server" "http://127.0.0.1:9200/health"
fi

if [[ ${#PYTEST_ARGS[@]} -eq 0 ]]; then
    uv run pytest
else
    uv run pytest "${PYTEST_ARGS[@]}"
fi
