#!/usr/bin/env bash
# ue_launch.sh — launch UE 5.8 + MyProject with full logging + stability flags.
#
# WHY: bare `open MyProject.uproject` gives no log file and runs at max
# scalability, which makes heavy Cesium / Gaussian-splat scenes crash the Metal
# RHI before you can see why. This wrapper:
#   - writes a full, timestamped log to logs/ue_<stamp>.log (-abslog)
#   - drops scalability so a heavy first load doesn't OOM the GPU
#   - leaves ray tracing OFF (also enforced in DefaultEngine.ini [SystemSettings])
#   - frees the MCP port 8123 if a stale CrashReporter ("CrashRepo") is squatting
#
# Scripts can't read the clock for a filename arg the way the harness wants, so
# pass the timestamp explicitly:  ./ue_launch.sh "$(date +%Y%m%d-%H%M%S)"
# If you omit it, the script generates one with `date` directly.
#
# USAGE:
#   ./ue_launch.sh [STAMP] [--game] [--norhithread] [extra UE args...]
#     STAMP         optional log stamp (default: date +%Y%m%d-%H%M%S)
#     --game        launch -game (standalone) instead of the editor
#     --norhithread add -norhithread (ONLY if advised; serializes the RHI —
#                   slower but rules out RHI-thread races when chasing a crash)
#
set -euo pipefail

HARNESS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UE="/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor"
PROJECT="/Users/patsimmons/Documents/Unreal Projects/MyProject/MyProject.uproject"
LOGDIR="$HARNESS/logs"
MCP_PORT=8123

mkdir -p "$LOGDIR"

# ---- arg parse ----
STAMP=""
GAME=0
NORHITHREAD=0
EXTRA=()
for a in "$@"; do
  case "$a" in
    --game)        GAME=1 ;;
    --norhithread) NORHITHREAD=1 ;;
    --*)           EXTRA+=("$a") ;;
    *)             if [[ -z "$STAMP" ]]; then STAMP="$a"; else EXTRA+=("$a"); fi ;;
  esac
done
[[ -z "$STAMP" ]] && STAMP="$(date +%Y%m%d-%H%M%S)"
LOGFILE="$LOGDIR/ue_${STAMP}.log"

# ---- sanity ----
[[ -x "$UE" ]]      || { echo "[ue_launch] editor not found: $UE" >&2; exit 1; }
[[ -f "$PROJECT" ]] || { echo "[ue_launch] project not found: $PROJECT" >&2; exit 1; }

# ---- free the MCP port if a stale CrashReporter is squatting it ----
# After a crash, Unreal's CrashReportClient ("CrashRepo") can hold port 8123,
# which blocks the MCP plugin from binding it on the next launch.
STALE_PID="$(lsof -ti tcp:${MCP_PORT} 2>/dev/null || true)"
if [[ -n "$STALE_PID" ]]; then
  for pid in $STALE_PID; do
    NAME="$(ps -p "$pid" -o comm= 2>/dev/null || true)"
    echo "[ue_launch] port ${MCP_PORT} held by pid $pid ($NAME) — killing to free MCP"
    kill -9 "$pid" 2>/dev/null || true
  done
  sleep 1
fi

# ---- stability flags ----
# sg.*Quality 2 = "Medium" scalability bucket. Heavy Cesium tilesets + splats
# at Epic/Cinematic can exhaust GPU memory on first stream-in and crash Metal.
SCALABILITY="sg.ViewDistanceQuality 2, sg.AntiAliasingQuality 1, sg.ShadowQuality 1, sg.GlobalIlluminationQuality 1, sg.ReflectionQuality 1, sg.PostProcessQuality 2, sg.TextureQuality 2, sg.EffectsQuality 2, sg.FoliageQuality 2, sg.ShadingQuality 2, r.RayTracing 0, r.Lumen.HardwareRayTracing 0"

ARGS=(
  "$PROJECT"
  -log
  -abslog="$LOGFILE"
  -ExecCmds="$SCALABILITY"
  -stdout
  -FullStdOutLogOutput
)
[[ "$GAME" == "1" ]]        && ARGS+=(-game -windowed -ResX=1600 -ResY=900)
[[ "$NORHITHREAD" == "1" ]] && ARGS+=(-norhithread)
ARGS+=( ${EXTRA[@]+"${EXTRA[@]}"} )

echo "[ue_launch] editor : $UE"
echo "[ue_launch] project: $PROJECT"
echo "[ue_launch] log    : $LOGFILE"
echo "[ue_launch] flags  : ${ARGS[*]:1}"
echo "[ue_launch] (tail the log:  tail -f \"$LOGFILE\" )"

exec "$UE" "${ARGS[@]}"
