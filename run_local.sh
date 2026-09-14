#!/usr/bin/env bash
# Runs Sentinel without Docker, using a user-space micromamba environment.
# This is the exact path used to build and test this project tonight
# (the dev machine had no Docker/root access) and is kept here as a
# verified fallback for judges' machines that also lack Docker.
#
# For a normal machine with Docker, prefer: docker compose up --build
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$ROOT_DIR/.tools"
MAMBA_BIN="$TOOLS_DIR/bin/micromamba"
export MAMBA_ROOT_PREFIX="$TOOLS_DIR/mamba"

if [ ! -f "$MAMBA_BIN" ]; then
  echo "Bootstrapping micromamba (user-space, no root needed)..."
  mkdir -p "$TOOLS_DIR/bin"
  curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj -C "$TOOLS_DIR" bin/micromamba
fi

if ! "$MAMBA_BIN" env list | grep -q sentinel; then
  echo "Creating sentinel environment (postgresql, ffmpeg, python 3.11)..."
  "$MAMBA_BIN" create -y -n sentinel -c conda-forge postgresql ffmpeg python=3.11
fi

echo "Installing Python dependencies..."
"$MAMBA_BIN" run -n sentinel python3 -m pip install --quiet -r "$ROOT_DIR/backend/requirements.txt"

PGDATA_DIR="$TOOLS_DIR/pgdata"
PGRUN_DIR="$TOOLS_DIR/pgrun"
mkdir -p "$PGRUN_DIR" "$TOOLS_DIR/pglog"

if [ ! -d "$PGDATA_DIR" ]; then
  echo "Initializing Postgres data directory..."
  "$MAMBA_BIN" run -n sentinel initdb -D "$PGDATA_DIR" -U postgres --auth=trust
fi

if ! "$MAMBA_BIN" run -n sentinel pg_isready -h "$PGRUN_DIR" -p 5432 >/dev/null 2>&1; then
  echo "Starting Postgres..."
  "$MAMBA_BIN" run -n sentinel pg_ctl -D "$PGDATA_DIR" -l "$TOOLS_DIR/pglog/pg.log" -o "-p 5432 -k $PGRUN_DIR" start
  sleep 2
fi

"$MAMBA_BIN" run -n sentinel psql -h "$PGRUN_DIR" -p 5432 -U postgres -d postgres -c \
  "SELECT 1 FROM pg_roles WHERE rolname='sentinel'" | grep -q 1 || \
  "$MAMBA_BIN" run -n sentinel psql -h "$PGRUN_DIR" -p 5432 -U postgres -d postgres -c \
  "CREATE ROLE sentinel WITH LOGIN PASSWORD 'sentinel' SUPERUSER;"

"$MAMBA_BIN" run -n sentinel psql -h "$PGRUN_DIR" -p 5432 -U postgres -d postgres -c \
  "SELECT 1 FROM pg_database WHERE datname='sentinel'" | grep -q 1 || \
  "$MAMBA_BIN" run -n sentinel psql -h "$PGRUN_DIR" -p 5432 -U postgres -d postgres -c \
  "CREATE DATABASE sentinel OWNER sentinel;"

export DATABASE_URL="postgresql+psycopg2://sentinel:sentinel@localhost:5432/sentinel"

echo "Initializing tables and seed data..."
cd "$ROOT_DIR/backend"
"$MAMBA_BIN" run -n sentinel python3 scripts/init_db.py
"$MAMBA_BIN" run -n sentinel python3 scripts/seed_data.py
"$MAMBA_BIN" run -n sentinel python3 scripts/seed_static_cameras.py

echo "Starting backend API on http://127.0.0.1:8010 ..."
"$MAMBA_BIN" run -n sentinel uvicorn app.main:app --host 127.0.0.1 --port 8010 &
BACKEND_PID=$!

echo "Installing frontend dependencies..."
cd "$ROOT_DIR/frontend"
npm install --silent

echo "Starting frontend dev server on http://127.0.0.1:5173 ..."
npm run dev -- --host 127.0.0.1 --port 5173 &
FRONTEND_PID=$!

echo ""
echo "Sentinel is starting up:"
echo "  Frontend:  http://127.0.0.1:5173"
echo "  Backend:   http://127.0.0.1:8010/api/health"
echo ""
echo "Press Ctrl+C to stop both servers."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
