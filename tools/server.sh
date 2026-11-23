#!/usr/bin/env sh
# Start/stop the SiMonPro API in the background (edge server).
#   tools/server.sh start|stop|restart|status|log
# Settings come from .env in the repo root. PYTHON defaults to the project venv.
set -eu
cd "$(dirname "$0")/.."
RUN_DIR=${SIMONPRO_RUN_DIR:-/mnt/storage/simonpro}
PYTHON=${PYTHON:-${UV_PROJECT_ENVIRONMENT:-$RUN_DIR/venv}/bin/python}
PID_FILE=$RUN_DIR/server.pid
LOG=$RUN_DIR/server.log
export TORCH_HOME=${TORCH_HOME:-$RUN_DIR/torch-hub}

running() { [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; }

case "${1:-status}" in
  start)
    if running; then echo "already running (pid $(cat "$PID_FILE"))"; exit 0; fi
    nohup "$PYTHON" -m uvicorn server.app.main:app --host 0.0.0.0 --port "${PORT:-8000}" >"$LOG" 2>&1 &
    echo $! >"$PID_FILE"
    for _ in $(seq 1 60); do
      if curl -sf "localhost:${PORT:-8000}/api/v1/health"; then echo; exit 0; fi
      running || { echo "server exited, see $LOG"; tail -20 "$LOG"; exit 1; }
      sleep 1
    done
    echo "server did not become healthy in 60 s, see $LOG"; exit 1 ;;
  stop)
    if running; then kill "$(cat "$PID_FILE")"; rm -f "$PID_FILE"; echo stopped; else echo "not running"; fi ;;
  restart) "$0" stop; sleep 1; "$0" start ;;
  status) if running; then echo "running (pid $(cat "$PID_FILE"))"; else echo "not running"; fi ;;
  log) tail -f "$LOG" ;;
  *) echo "usage: $0 start|stop|restart|status|log"; exit 2 ;;
esac
