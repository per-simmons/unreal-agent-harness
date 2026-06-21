#!/usr/bin/env bash
# ue_crashlog.sh — find + print the NEWEST UE 5.8 crash, agent-readable.
#
# Prints: the crash dir, the assert/exception message, the LogCesium errors,
# the "Critical error" block, and the top of the callstack — without dumping
# the whole multi-MB report into context.
#
# USAGE:
#   ./ue_crashlog.sh            # newest crash
#   ./ue_crashlog.sh -n 3       # list the 3 newest crash dirs, detail the newest
#   ./ue_crashlog.sh DIR        # detail a specific crash dir
#   ./ue_crashlog.sh --port     # just check/kill the CrashReporter squatting 8123
#
set -euo pipefail

CRASHROOT="$HOME/Library/Application Support/Epic/UnrealEngine/5.8/Saved/Crashes"
# The project also keeps its own crash dir; check both.
PROJ_CRASHROOT="$HOME/Documents/Unreal Projects/MyProject/Saved/Crashes"
MCP_PORT=8123

free_port() {
  local pids
  pids="$(lsof -ti tcp:${MCP_PORT} 2>/dev/null || true)"
  if [[ -z "$pids" ]]; then
    echo "[ue_crashlog] port ${MCP_PORT} is free."
    return 0
  fi
  for pid in $pids; do
    local name; name="$(ps -p "$pid" -o comm= 2>/dev/null || true)"
    echo "[ue_crashlog] port ${MCP_PORT} held by pid $pid ($name) — killing"
    kill -9 "$pid" 2>/dev/null || true
  done
}

if [[ "${1:-}" == "--port" ]]; then
  free_port
  exit 0
fi

# Collect candidate crash dirs from both roots, newest first.
# (macOS ships bash 3.2 with no `mapfile`, so build the array portably.)
DIRS=()
while IFS= read -r d; do
  [[ -n "$d" ]] && DIRS+=("$d")
done < <(
  { find "$CRASHROOT" -mindepth 1 -maxdepth 1 -type d 2>/dev/null;
    find "$PROJ_CRASHROOT" -mindepth 1 -maxdepth 1 -type d 2>/dev/null; } \
  | while read -r d; do printf '%s\t%s\n' "$(stat -f %m "$d" 2>/dev/null || echo 0)" "$d"; done \
  | sort -rn | cut -f2-
)

if [[ "${1:-}" == "-n" ]]; then
  N="${2:-3}"
  echo "[ue_crashlog] $N newest crash dirs:"
  for i in $(seq 0 $((N-1))); do
    [[ -n "${DIRS[$i]:-}" ]] && echo "  ${DIRS[$i]}"
  done
  TARGET="${DIRS[0]:-}"
elif [[ -n "${1:-}" && -d "${1:-}" ]]; then
  TARGET="$1"
else
  TARGET="${DIRS[0]:-}"
fi

if [[ -z "${TARGET:-}" ]]; then
  echo "[ue_crashlog] no crash dirs found under:"
  echo "  $CRASHROOT"
  echo "  $PROJ_CRASHROOT"
  exit 0
fi

echo "=================================================================="
echo "[ue_crashlog] newest crash: $TARGET"
echo "  ($(date -r "$(stat -f %m "$TARGET")" 2>/dev/null || echo unknown))"
echo "=================================================================="

# 1) The high-level message (CrashContext.runtime-xml / CrashReportClient text)
CTX="$TARGET/CrashContext.runtime-xml"
if [[ -f "$CTX" ]]; then
  echo "---- error message ----"
  # Pull the <ErrorMessage> ... </ErrorMessage> payload.
  perl -0777 -ne 'print "$1\n" if /<ErrorMessage>(.*?)<\/ErrorMessage>/s' "$CTX" \
    | sed 's/^[[:space:]]*//' | head -20
  echo
fi

# 2) The most useful log = the editor/runtime log in the crash dir.
LOG="$(find "$TARGET" -maxdepth 1 -name '*.log' 2>/dev/null | head -1)"
if [[ -z "$LOG" ]]; then
  # fall back to the global editor log
  LOG="$(find "$HOME/Documents/Unreal Projects/MyProject/Saved/Logs" -name '*.log' 2>/dev/null \
        | while read -r l; do printf '%s\t%s\n' "$(stat -f %m "$l")" "$l"; done \
        | sort -rn | head -1 | cut -f2-)"
fi

if [[ -n "$LOG" && -f "$LOG" ]]; then
  echo "---- LogCesium errors/warnings ($LOG) ----"
  grep -nE 'LogCesium' "$LOG" 2>/dev/null | grep -iE 'error|warning|invalid|status' | tail -25 || echo "(none)"
  echo
  echo "---- Critical error / assertion / fatal ----"
  grep -nE 'Critical error|Fatal error|Assertion failed|=== Critical|LowLevelFatalError|signal|EXCEPTION' "$LOG" 2>/dev/null | tail -20 || echo "(none)"
  echo
  echo "---- callstack (lines around the crash) ----"
  # Print from the first "Critical error" to ~60 lines after.
  awk '/Critical error|Fatal error|=== Critical/{f=1} f{print; n++} n>60{exit}' "$LOG" | head -70 || true
else
  echo "[ue_crashlog] no .log found in the crash dir; files present:"
  ls -la "$TARGET"
fi

echo
echo "---- port ${MCP_PORT} status (MCP) ----"
if lsof -i tcp:${MCP_PORT} 2>/dev/null | grep -q LISTEN; then
  lsof -i tcp:${MCP_PORT} 2>/dev/null | grep LISTEN
  echo "[ue_crashlog] NOTE: ${MCP_PORT} is held. If this is 'CrashRepo'/CrashReportClient,"
  echo "             free it with:  ./ue_crashlog.sh --port"
else
  echo "[ue_crashlog] port ${MCP_PORT} is free."
fi
