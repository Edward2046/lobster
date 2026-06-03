#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
LOG_FILE="$LOG_DIR/lobster.log"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
BACKEND_PID_FILE="$ROOT_DIR/.lobster-backend.pid"
FRONTEND_PID_FILE="$ROOT_DIR/.lobster-frontend.pid"
BACKEND_HEALTH_URL="http://127.0.0.1:8765/health"
FRONTEND_URL="http://127.0.0.1:5173"
ACTION="${1:-start}"

mkdir -p "$LOG_DIR"

log() {
  local message="$1"
  local timestamp
  timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
  printf '[%s] %s\n' "$timestamp" "$message" | tee -a "$LOG_FILE"
}

is_pid_running() {
  local pid="$1"
  kill -0 "$pid" 2>/dev/null
}

pid_from_file() {
  local pid_file="$1"
  tr -d '[:space:]' < "$pid_file"
}

write_pid_file() {
  local pid_file="$1"
  local pid="$2"
  printf '%s\n' "$pid" > "$pid_file"
}

remove_stale_pid_file() {
  local pid_file="$1"
  if [ ! -f "$pid_file" ]; then
    return
  fi

  local pid
  pid="$(pid_from_file "$pid_file")"
  if [[ ! "$pid" =~ ^[0-9]+$ ]] || ! is_pid_running "$pid"; then
    rm -f "$pid_file"
  fi
}

backend_is_ready() {
  curl -fsS "$BACKEND_HEALTH_URL" >/dev/null 2>&1
}

frontend_is_ready() {
  curl -fsS "$FRONTEND_URL" >/dev/null 2>&1
}

stop_process() {
  local name="$1"
  local pid_file="$2"

  if [ ! -f "$pid_file" ]; then
    log "$name is not managed by this script right now."
    return
  fi

  local pid
  pid="$(pid_from_file "$pid_file")"
  if [[ ! "$pid" =~ ^[0-9]+$ ]]; then
    rm -f "$pid_file"
    log "$name PID file was invalid and has been removed."
    return
  fi

  if ! is_pid_running "$pid"; then
    rm -f "$pid_file"
    log "$name is already stopped."
    return
  fi

  log "Stopping $name (PID $pid)..."
  kill "$pid"

  for _ in {1..20}; do
    if ! is_pid_running "$pid"; then
      rm -f "$pid_file"
      log "$name stopped."
      return
    fi
    sleep 1
  done

  log "$name did not stop after 20 seconds; sending SIGKILL to PID $pid."
  kill -KILL "$pid"

  for _ in {1..5}; do
    if ! is_pid_running "$pid"; then
      rm -f "$pid_file"
      log "$name stopped."
      return
    fi
    sleep 1
  done

  log "Failed to stop $name."
  exit 1
}

start_backend() {
  remove_stale_pid_file "$BACKEND_PID_FILE"

  if backend_is_ready; then
    log "Backend is already running on :8765."
    return
  fi

  log "Starting backend..."
  (
    cd "$ROOT_DIR"
    nohup python main.py >>"$BACKEND_LOG" 2>&1 &
    backend_pid=$!
    write_pid_file "$BACKEND_PID_FILE" "$backend_pid"
  )

  for _ in {1..30}; do
    if backend_is_ready; then
      local backend_pid
      backend_pid="$(pid_from_file "$BACKEND_PID_FILE")"
      log "Backend started in background with PID $backend_pid."
      return
    fi
    sleep 1
  done

  log "Backend did not become healthy within 30 seconds."
  exit 1
}

start_frontend() {
  remove_stale_pid_file "$FRONTEND_PID_FILE"

  if [ -f "$FRONTEND_PID_FILE" ]; then
    local frontend_pid
    frontend_pid="$(pid_from_file "$FRONTEND_PID_FILE")"
    if is_pid_running "$frontend_pid"; then
      log "Frontend is already running with PID $frontend_pid."
      return
    fi
  fi

  if frontend_is_ready; then
    log "Frontend is already responding on :5173."
    return
  fi

  log "Starting frontend..."
  (
    cd "$ROOT_DIR/web"
    nohup npm run dev -- --host 0.0.0.0 >>"$FRONTEND_LOG" 2>&1 &
    frontend_pid=$!
    write_pid_file "$FRONTEND_PID_FILE" "$frontend_pid"
  )

  for _ in {1..30}; do
    if frontend_is_ready; then
      local frontend_pid
      frontend_pid="$(pid_from_file "$FRONTEND_PID_FILE")"
      log "Frontend started in background with PID $frontend_pid."
      return
    fi
    sleep 1
  done

  log "Frontend did not become ready within 30 seconds."
  exit 1
}

start_all() {
  touch "$LOG_FILE"
  start_backend
  start_frontend
  log "Lobster is running. Logs: lobster.log (script) / backend.log / frontend.log under logs/."
}

stop_all() {
  touch "$LOG_FILE"
  stop_process "Frontend" "$FRONTEND_PID_FILE"
  stop_process "Backend" "$BACKEND_PID_FILE"
}

case "$ACTION" in
  start)
    start_all
    ;;
  stop)
    stop_all
    ;;
  *)
    echo "Usage: $0 [start|stop]" >&2
    exit 1
    ;;
esac
