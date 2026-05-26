#!/usr/bin/env bash
set -euo pipefail

trap 'echo "ERROR: command failed at line $LINENO"; exit 1' ERR

cd "$(dirname "$0")"

pretty_json() {
  if command -v jq >/dev/null 2>&1; then
    jq .
  else
    cat
  fi
}

wait_for_url() {
  local url="$1"
  local attempts="${2:-30}"
  local delay="${3:-2}"
  local try

  for ((try = 1; try <= attempts; try++)); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
  done

  echo "Timed out waiting for $url"
  return 1
}

wait_for_kafka_health() {
  local attempts="${1:-20}"
  local delay="${2:-1}"
  local try
  local body

  for ((try = 1; try <= attempts; try++)); do
    body="$(curl -fsS http://localhost:8000/kafka-health || true)"
    if printf '%s' "$body" | grep -q '"status":"healthy"'; then
      return 0
    fi
    sleep "$delay"
  done

  echo "Timed out waiting for Kafka health"
  return 1
}

wait_for_prometheus_target() {
  local attempts="${1:-20}"
  local delay="${2:-1}"
  local try
  local body

  for ((try = 1; try <= attempts; try++)); do
    body="$(curl -fsS 'http://localhost:9090/api/v1/query?query=up%7Bjob%3D%22signal-engine%22%7D' || true)"
    if printf '%s' "$body" | grep -q '"job":"signal-engine"'; then
      return 0
    fi
    sleep "$delay"
  done

  echo "Timed out waiting for Prometheus to scrape the app"
  return 1
}

docker compose up -d --build

echo "Waiting for Meilisearch..."
wait_for_url "http://localhost:7701/health" 30 2

echo "Waiting for Jaeger..."
wait_for_url "http://localhost:16686" 30 2

echo "Waiting for Prometheus..."
wait_for_url "http://localhost:9090/-/ready" 30 2

echo "Waiting for Grafana..."
wait_for_url "http://localhost:3001/api/health" 30 2

docker ps | grep -E 'zookeeper|kafka|meilisearch|signal-engine|prometheus|grafana|jaeger' || {
  echo "Core observability containers are not running"
  exit 1
}

echo "Waiting for FastAPI..."
wait_for_url "http://localhost:8000/health" 30 1

echo "Waiting for Kafka health..."
wait_for_kafka_health 20 1

echo "Waiting for Prometheus scrape..."
wait_for_prometheus_target 20 1

echo
echo "FastAPI health:"
curl -s http://localhost:8000/health | pretty_json

echo
echo "Kafka health:"
curl -s http://localhost:8000/kafka-health | pretty_json

echo
echo "Grafana health:"
curl -s http://localhost:3001/api/health | pretty_json

echo
echo "Prometheus target status:"
curl -s "http://localhost:9090/api/v1/query?query=up%7Bjob%3D%22signal-engine%22%7D" | pretty_json

echo
echo "Available Meilisearch indexes:"
curl -s http://localhost:7701/indexes | pretty_json

export MEILISEARCH_INDEX=books

if ! curl -fsS http://localhost:7701/indexes/books >/dev/null 2>&1; then
  curl -s \
    -X POST \
    http://localhost:7701/indexes \
    -H 'Content-Type: application/json' \
    --data '{"uid":"books","primaryKey":"id"}' | pretty_json
fi

wait_for_url "http://localhost:7701/indexes/books" 20 1

curl -s \
  -X POST \
  http://localhost:7701/indexes/books/documents \
  -H 'Content-Type: application/json' \
  --data '[{"id":1,"title":"Python Crash Course"},{"id":2,"title":"Learning Python"},{"id":3,"title":"Kafka in Action"}]' | pretty_json

sleep 2

echo
echo "Search query 'python' ->"
curl -s "http://localhost:8000/search?query=python" | pretty_json

sleep 2

echo
echo "Metrics preview:"
curl -s http://localhost:8000/metrics | grep -E 'signal_engine_http_requests_total|signal_engine_http_request_duration_seconds|signal_engine_signals_total|signal_engine_active_signals' || true

echo
echo "Jaeger services:"
curl -s http://localhost:16686/api/services | pretty_json

echo
echo "Recent signals:"
curl -s http://localhost:8000/signals | pretty_json

echo
echo "Adding a test signal..."
curl -s http://localhost:8000/add-test-signal >/dev/null
echo "Updated signals:"
curl -s http://localhost:8000/signals | pretty_json

echo
echo "Monitoring stack is running."
echo "FastAPI:    http://localhost:8000"
echo "Prometheus: http://localhost:9090"
echo "Grafana:    http://localhost:3001 (admin/admin)"
echo "Jaeger:     http://localhost:16686"
