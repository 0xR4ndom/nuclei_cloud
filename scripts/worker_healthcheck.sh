#!/usr/bin/env bash
# Worker healthcheck for worker-scans container.
# Exits 0 (healthy) or 1 (unhealthy).
#
# Checks:
#   1. Celery worker process is running
#   2. Redis is reachable
#   3. No tasks have been stuck in RUNNING state for > 2 hours
set -euo pipefail

REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

# ── 1. Celery worker process ──────────────────────────────────────────────────
if ! pgrep -x celery > /dev/null 2>&1; then
    echo "UNHEALTHY: celery process not found"
    exit 1
fi

# ── 2. Redis connectivity ─────────────────────────────────────────────────────
# Extract host and port from REDIS_URL (format: redis://host:port/db)
REDIS_HOST=$(echo "$REDIS_URL" | sed -E 's|redis://([^:/]+).*|\1|')
REDIS_PORT=$(echo "$REDIS_URL" | sed -E 's|redis://[^:]+:([0-9]+).*|\1|')
REDIS_PORT="${REDIS_PORT:-6379}"

if ! redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping > /dev/null 2>&1; then
    echo "UNHEALTHY: cannot reach Redis at $REDIS_HOST:$REDIS_PORT"
    exit 1
fi

# ── 3. Check for active tasks (soft check — failure here is non-fatal) ────────
# Use Celery inspect to detect tasks that have been active for an unusually long
# time.  We do this on a best-effort basis: if the inspect call itself fails
# (e.g. worker just started), we don't fail the healthcheck.
ACTIVE_JSON=$(celery -A app.workers.celery_app inspect active \
    --destination "celery@${HOSTNAME}" \
    --timeout 5 \
    --json 2>/dev/null || echo "{}")

# Count tasks that have been running for more than 7200 seconds (2 hours)
# The JSON format is: {"celery@host": [{"time_start": <epoch>, ...}, ...]}
STUCK_COUNT=$(python3 - <<'PYEOF'
import json, sys, time

raw = sys.stdin.read()
try:
    data = json.loads(raw)
except Exception:
    print(0)
    sys.exit(0)

now = time.time()
MAX_AGE = 7200  # 2 hours in seconds
stuck = 0

for worker, tasks in data.items():
    if not isinstance(tasks, list):
        continue
    for task in tasks:
        started = task.get("time_start")
        if started and (now - started) > MAX_AGE:
            stuck += 1

print(stuck)
PYEOF
<<< "$ACTIVE_JSON")

if [ "${STUCK_COUNT:-0}" -gt 0 ]; then
    echo "UNHEALTHY: ${STUCK_COUNT} task(s) stuck for over 2 hours"
    exit 1
fi

echo "HEALTHY: celery running, Redis OK, no stuck tasks"
exit 0
