#!/bin/bash
URL=$1
MAX_RETRIES=5
RETRY_DELAY=10

echo "Running smoke test against $URL"

for i in $(seq 1 $MAX_RETRIES); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" $URL/health)
  echo "Attempt $i — got status $STATUS"

  if [ "$STATUS" == "200" ]; then
    echo "Smoke test passed — $URL is healthy"
    exit 0
  fi

  echo "Not ready yet, retrying in ${RETRY_DELAY}s..."
  sleep $RETRY_DELAY
done

echo "Smoke test FAILED after $MAX_RETRIES attempts"
exit 1
