#!/usr/bin/env bash
set -euo pipefail

# Start all services for the dj-tools web client:
#   Elasticsearch (Docker), API (FastAPI), Client (Vite)
#
# Usage:
#   bash src/scripts/start_web.sh             Start everything
#   bash src/scripts/start_web.sh --reindex   Force re-index tracks into Elasticsearch

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

REINDEX=false
if [[ "${1:-}" == "--reindex" ]]; then
  REINDEX=true
fi

ES_CONTAINER="dj-tools-es"
ES_IMAGE="docker.elastic.co/elasticsearch/elasticsearch:8.17.0"
ES_URL="http://127.0.0.1:9200"
API_PORT=8000
CLIENT_PORT=5173
STARTED_ES=false

cleanup() {
  echo ""
  echo "Shutting down..."
  [[ -n "${CLIENT_PID:-}" ]] && kill "$CLIENT_PID" 2>/dev/null && echo "  Stopped client (PID $CLIENT_PID)"
  [[ -n "${API_PID:-}" ]] && kill "$API_PID" 2>/dev/null && echo "  Stopped API (PID $API_PID)"
  if [[ "$STARTED_ES" == true ]]; then
    docker stop "$ES_CONTAINER" >/dev/null 2>&1 && echo "  Stopped Elasticsearch container"
  fi
  echo "Done."
}
trap cleanup EXIT

# -- Activate venv --
if [[ -d ".venv" ]]; then
  source .venv/bin/activate
fi

# -- Elasticsearch --
echo "==> Elasticsearch"

ES_PORT_PID=$(lsof -ti:9200 2>/dev/null || true)
if [[ -n "$ES_PORT_PID" ]]; then
  ES_PORT_PROC=$(ps -p "$ES_PORT_PID" -o comm= 2>/dev/null || echo "unknown")
  if docker info >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${ES_CONTAINER}$"; then
    echo "  Container '$ES_CONTAINER' already running on port 9200"
  else
    echo "  WARNING: Port 9200 already in use by '$ES_PORT_PROC' (PID $ES_PORT_PID)"
    echo "  Proceeding — Elasticsearch may already be available"
  fi
else
  if ! docker info >/dev/null 2>&1; then
    echo "  Docker is not running. Starting Docker Desktop..."
    open -a Docker
    for i in {1..30}; do
      docker info >/dev/null 2>&1 && break
      sleep 2
    done
    docker info >/dev/null 2>&1 || { echo "  ERROR: Docker failed to start"; exit 1; }
  fi

  if docker ps --format '{{.Names}}' | grep -q "^${ES_CONTAINER}$"; then
    echo "  Container '$ES_CONTAINER' already running"
  elif docker ps -a --format '{{.Names}}' | grep -q "^${ES_CONTAINER}$"; then
    echo "  Starting existing container '$ES_CONTAINER'..."
    docker start "$ES_CONTAINER" >/dev/null
    STARTED_ES=true
  else
    echo "  Creating container '$ES_CONTAINER'..."
    docker run -d --name "$ES_CONTAINER" -p 9200:9200 \
      -e "discovery.type=single-node" \
      -e "xpack.security.enabled=false" \
      -e "xpack.security.enrollment.enabled=false" \
      -e "ES_JAVA_OPTS=-Xms512m -Xmx512m" \
      "$ES_IMAGE" >/dev/null
    STARTED_ES=true
  fi
fi

echo "  Waiting for Elasticsearch..."
for i in {1..30}; do
  curl -sf "$ES_URL" >/dev/null 2>&1 && break
  sleep 2
done
curl -sf "$ES_URL" >/dev/null 2>&1 || { echo "  ERROR: Elasticsearch failed to respond at $ES_URL"; exit 1; }
echo "  Elasticsearch ready at $ES_URL"

# -- Index tracks --
INDEX_EXISTS=$(curl -sf -o /dev/null -w "%{http_code}" "$ES_URL/dj_tracks" 2>/dev/null || echo "000")
if [[ "$REINDEX" == true ]] || [[ "$INDEX_EXISTS" != "200" ]]; then
  echo ""
  echo "==> Indexing tracks"
  python -m src.scripts.index_tracks
fi

# -- API server --
echo ""
echo "==> API server"
python -m src.scripts.run_api &
API_PID=$!
sleep 3
echo "  API running at http://127.0.0.1:$API_PORT (PID $API_PID)"

# -- Client dev server --
echo ""
echo "==> Client dev server"
if [[ ! -d "client/node_modules" ]]; then
  echo "  Installing client dependencies..."
  npm --prefix client install --silent
fi
npm --prefix client run dev &
CLIENT_PID=$!
sleep 2
echo "  Client running at http://localhost:$CLIENT_PORT (PID $CLIENT_PID)"

echo ""
echo "==> All services started"
echo "    Elasticsearch: $ES_URL"
echo "    API:           http://127.0.0.1:$API_PORT"
echo "    Client:        http://localhost:$CLIENT_PORT"
echo ""
echo "Press Ctrl+C to stop all services."

wait
