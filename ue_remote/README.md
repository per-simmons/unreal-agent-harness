# UE Python Remote Execution (call live UE/Cesium FUNCTIONS, no clicks)

Drive a **running** Unreal Editor from outside the process — run arbitrary
Python in the editor's own runtime, which means we can call real UE/Cesium
**functions** (BlueprintCallable / BlueprintSetter), not just set raw
UPROPERTYs.

## Why this exists (the Cesium blocker)

The MCP property-set path writes raw UPROPERTYs and **bypasses the Cesium
BlueprintSetters**. So Cesium tiles stay at ECEF (earth-centered) coordinates
and never rebase to the local origin — they render in the wrong place/scale.

The rebase only fires through real **function** calls:
`CesiumGeoreference.set_origin_longitude_latitude_height(unreal.Vector(lon, lat, height))`
and `Cesium3DTileset.refresh_tileset()`. Remote-exec is how we call them.

## Files

| File | What it is |
|------|------------|
| `remote_execution.py` | UE's **official** client (copied verbatim from `UE_5.8/.../PythonScriptPlugin/Content/Python/`). Implements the UDP multicast discovery + TCP command protocol. Do not edit. |
| `ue_exec.py` | CLI. Connects to the running editor and runs a Python string / file, prints UE stdout. |
| `cesium_rebase.py` | Snippet to send via `ue_exec.py`. Finds all `CesiumGeoreference` + `Cesium3DTileset` actors and rebases them to a lon/lat/height origin. |

## One-time setup (already done)

`~/Documents/Unreal Projects/MyProject/Config/DefaultEngine.ini`:

```ini
[/Script/PythonScriptPlugin.PythonScriptPluginSettings]
bRemoteExecution=True
RemoteExecutionMulticastGroupEndpoint=239.0.0.1:6766
RemoteExecutionMulticastBindAddress=0.0.0.0
RemoteExecutionSendBufferSizeBytes=2097152
RemoteExecutionReceiveBufferSizeBytes=2097152
RemoteExecutionMulticastTtl=0
```

(Setting names verified against the UE 5.8 engine source:
`PythonScriptPluginSettings.h/.cpp`.) `PythonScriptPlugin` is enabled in
`MyProject.uproject`.

> **One editor restart is required** for `bRemoteExecution=True` to take effect.
> The setting is read at editor startup; you cannot toggle it on a session that
> was already running.

## Workflow (no clicks)

1. **Launch the editor** (remote-exec is now enabled). Nothing else to click.
2. From a terminal **outside** the editor:

```bash
cd ~/coding/unreal-agent-harness/ue_remote

# sanity check — should print the engine version
python3 ue_exec.py "import unreal; print(unreal.SystemLibrary.get_engine_version())"

# rebase Cesium tiles to NYC (Times Square) and refresh all tilesets
python3 ue_exec.py --file cesium_rebase.py

# rebase to any origin
LON=-73.9857 LAT=40.7484 HEIGHT=0 python3 ue_exec.py --file cesium_rebase.py

# evaluate a single expression and get its value back
python3 ue_exec.py --mode eval "len(unreal.EditorActorSubsystem().get_all_level_actors())"

# pipe a script in
cat some_script.py | python3 ue_exec.py -
```

### Exit codes (so an agent can branch on them)

| Code | Meaning |
|------|---------|
| `0` | Command ran; UE stdout is on stdout. |
| `2` | No editor discovered within the timeout (editor not running, or not restarted after enabling remote-exec). |
| `3` | UE reported the command failed (traceback is in the output). |
| `1` | Client/usage error. |

## Networking notes

- Editor binds the multicast socket to `0.0.0.0` (all adapters); the client
  defaults to the loopback command endpoint `127.0.0.1:6776`. Same-host, so
  loopback is reachable. Both sides share group `239.0.0.1:6766`.
- Override from the client via env vars if needed:
  `UE_REMOTE_MULTICAST=239.0.0.1:6766`, `UE_REMOTE_BIND_ADDRESS=127.0.0.1`.
- `RemoteExecutionMulticastTtl=0` keeps discovery on the local host only — fine
  for editor + client on the same Mac, and avoids leaking onto the LAN.
