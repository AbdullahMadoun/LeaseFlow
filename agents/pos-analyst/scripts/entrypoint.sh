#!/usr/bin/env sh
# Container entrypoint.
#
# 1. Ensure the work dir exists.
# 2. If the sandbox image is not present locally, build it from the bundled
#    Dockerfile.sandbox (idempotent — `docker build` is a no-op if cached).
# 3. Hand off to uvicorn. The api_server lifespan hook calls worker.resume_all()
#    before serving the first request.
set -eu

: "${POS_WORK_DIR:=/var/pos-analyst}"
: "${POS_SANDBOX_IMAGE:=pos-analyst-sandbox:latest}"
: "${POS_BIND_HOST:=0.0.0.0}"
: "${POS_BIND_PORT:=8080}"

mkdir -p "${POS_WORK_DIR}/jobs"

if [ -S /var/run/docker.sock ]; then
    if ! docker image inspect "${POS_SANDBOX_IMAGE}" >/dev/null 2>&1; then
        echo "[entrypoint] building sandbox image ${POS_SANDBOX_IMAGE}..."
        docker build -f /app/Dockerfile.sandbox -t "${POS_SANDBOX_IMAGE}" /app >&2 || {
            echo "[entrypoint] sandbox image build failed; jobs will fail at preflight" >&2
        }
    else
        echo "[entrypoint] sandbox image ${POS_SANDBOX_IMAGE} present"
    fi
else
    echo "[entrypoint] WARNING: /var/run/docker.sock is not mounted — code execution will fail" >&2
fi

exec uvicorn api_server:app \
    --host "${POS_BIND_HOST}" \
    --port "${POS_BIND_PORT}" \
    --workers 1 \
    --loop asyncio \
    --no-access-log
