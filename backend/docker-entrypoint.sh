#!/bin/sh
set -eu

mkdir -p /app/backend/data/chroma
chown -R appuser:appuser /app/backend/data/chroma

if [ ! -f /app/backend/data/chroma/chroma.sqlite3 ]; then
    gosu appuser python -m app.scripts.ingest_corpus
fi

exec gosu appuser "$@"
