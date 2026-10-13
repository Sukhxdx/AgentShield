#!/bin/sh
# Start Ollama, pull qwen3:4b, then keep the server in the foreground.
set -eu

ollama serve &
pid=$!

ready=0
i=0
while [ "$i" -lt 90 ]; do
  if ollama list >/dev/null 2>&1; then
    ready=1
    break
  fi
  i=$((i + 1))
  sleep 1
done

if [ "$ready" -ne 1 ]; then
  echo "Ollama did not become ready" >&2
  exit 1
fi

ollama pull "${OLLAMA_MODEL:-qwen3:4b}"
wait "$pid"
