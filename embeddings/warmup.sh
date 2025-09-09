#!/bin/bash
set -e

echo "Waiting for embeddings service to be healthy..."
timeout=120
until curl -fsS http://localhost:4000/health >/dev/null; do
  ((timeout--))
  if [ $timeout -le 0 ]; then
    echo "ERROR: Embeddings service health check timed out."
    exit 1
  fi
  sleep 1
done

echo "Service is healthy. Sending warmup request..."
curl -fsS -X POST http://localhost:4000/v1/embeddings \
-H 'Content-Type: application/json' \
-d '{"model":"jina-code-v2","input":"warmup"}' >/dev/null

echo "Warmup request sent successfully."