# Troubleshooting — the gotchas you'll actually hit

Hard-won during the build. Ctrl-F your symptom.

## Connection / MCP
- **`"Unable to connect"` when calling a tool.** The MCP server isn't running in the *currently open* project. Causes + fixes:
  - Plugin not enabled in this project → see [UNREAL-MCP-ENABLE.md](UNREAL-MCP-ENABLE.md). A fresh/sample project does NOT have it on by default.
  - `bAutoStartServer` is false (default) → set it True in `DefaultEngine.ini`; enabling the plugin alone never starts the server.
  - Editor wasn't *fully* restarted after the config change.
  - You switched projects — **only one editor can bind port 8123**; the previous project's server died. Reconnect (`/mcp`) to whichever project is now open.
- **Only `AgentSkillToolset` shows in `list_toolsets`.** You didn't enable **`AllToolsets`** (the aggregator) in the `.uproject`. The ~28 building toolsets ship as disabled-by-default plugins.
- **Port 8000 already in use.** Something else owns it (e.g. WhisperFlow dictation). Use **8123** (`ServerPortNumber=8123`).
- **`get_current_level` returns the wrong project.** You're connected to a different/stale editor instance — quit the stray one.

## Editor boot / crashes
- **Editor hangs on boot, ~500 MB, no log.** `bRemoteExecution=True` starts a multicast listener that hangs macOS boot → set **`bRemoteExecution=False`** in `DefaultEngine.ini`.
- **Recurring tick crash in a Cesium gaussian-splat subsystem** (`UCesiumGaussianSplatSubsystem::Tick`, `UObjectArray.h`). No cvar disables it → patch `GetTickableTickType()`→`Never` + rebuild the CesiumRuntime dylib. See [cesium-splat-subsystem-disable.md](cesium-splat-subsystem-disable.md).
- **Metal RHI crash in `RHILockBuffer`.** A malformed POSITION accessor in a custom splat tile (status 4 = BufferViewTooSmall). Rebuild the tile with self-validating uncompressed accessors. See [khr-gaussian-splatting.md](khr-gaussian-splatting.md).
- **Port 8123 dead after a crash.** The CrashReporter ("CrashRepo") squats it — `kill -9` it, then relaunch.
- **Launching the raw binary hangs.** Use `open MyProject.uproject` (or `ue_launch.sh`), not the bare editor binary.
- **Pull crash logs:** `./ue_crashlog.sh`.

## Viewport / camera (the big time-sink)
- **`CaptureViewport` / `SetCameraTransform` stops affecting the view** — captures look stale/stuck on one object, identical regardless of where you set the camera. The MCP camera can desync from the *active* viewport (especially after the user moves it, or in PIE). Workarounds:
  - QA in the **plain editor** (no PIE): set the editor camera to `pawn + chase offset`, then capture. (`SetCameraTransform` then `CaptureViewport`.)
  - **`CaptureViewport` during PIE grabs the EDITOR viewport, not the possessed game camera** — useless for QA-ing a gameplay cam. See [pie-qa-capture.md](pie-qa-capture.md).
  - When the user is lost in the viewport, the reliable reset is **double-click an actor in the Outliner** (frames it). Editor nav requires the mouse to be **over the 3D viewport**, and **hold Right-Mouse + WASD** (WASD alone does nothing); raise camera speed via RMB+scroll for big scenes.
- **"Shadow but no plane" / can't see a mesh you placed.** Usually: the mesh imported at the **wrong scale** (e.g. 100× — a 60 m plane came in at 6 km, so the camera sits *inside* it) — always `StaticMeshTools.get_bounds` an import and sanity-check m vs cm; OR `bOwnerNoSee=true` (the pawn's own camera hides it but it still casts a shadow); OR the camera is inside the near-clip. See [chase-cam-correct.md](chase-cam-correct.md).
- **Blown-out white viewport.** Manual-exposure `AutoExposureBias` set way too high (e.g. 10 = +10 EV ≈ 1024×). Drop toward 0–2. See [lighting-safety-review.md](lighting-safety-review.md).
- **Sky doesn't cover the screen / black gaps.** Incomplete sky setup — needs a SkyAtmosphere (+ SkyLight) actually present and a directional light with `bAtmosphereSunLight=true`.

## Assets / import
- **`import_file` rejects glTF/GLB.** It takes **FBX/OBJ only** → convert GLB→FBX with headless Blender (`blender_jobs.py`).
- **Image-to-3D imports tiny + rotated.** Comes in ~1.4 m (scale ~10×) and axis-rotated (Y-up→Z-up) — fix scale + rotation on import.
- **City Sample Buildings won't "Add to Project."** That pack is **5.0–5.4 only**; on 5.8 it says "no compatible project." The full **City Sample** *Complete Project* is **5.0–5.8 + Mac** — use that. (Confirm "Supported Engine Versions" on the Fab listing.)

## Materials (MaterialTools)
- **Property names vary per node — always `ObjectTools.list_properties` first.** e.g. a `Constant` uses `r` (lowercase); a `Constant3Vector` uses `constant` (a LinearColor `{r,g,b,a}`).
- **`set_properties` can't grow an empty array by N at once** ("insertion points ambiguous") — append one entry per call (loop it).

## PCG
- **No native Voronoi node.** Use `Cluster` (KMeans) for districts — visually the same patchwork.
- **Grid's own `bCullPointsOutsideVolume` returns ZERO points on first execute** (volume bounds at gen-start don't cover the world grid). Leave it false; clip to shape with a real surface + `Difference` / `Cull Points Outside Actor Bounds`.
- **Execution state is shared at the graph-asset level** → run `ExecuteGraphInstance` / `GetNodeDataView` **one volume at a time**; concurrent calls freeze the editor.
- Static Mesh Spawner palette is NOT a node param — it's on the spawner settings' `meshSelectorParameters` selector subobject; static-mesh refPaths need the `.AssetName` suffix (`…/Tower_01.Tower_01`).

## Performance (heavy scenes / City Sample on Mac)
- Use **Small_City_LVL**, never **Big_City_LVL**, for a smooth demo.
- Confirm **SM6 renderer + Nanite** on (Project Settings → Platforms → Mac → Metal Shader Standard / SM6; needs M2+).
- Biggest single FPS win: **screen percentage 60–70%**. Then Scalability **Medium**, crowd Data Layer **off**, `t.MaxFPS 30` for steady capture. Install on a fast SSD. Let shaders fully compile before judging FPS.

## Concurrency (multi-agent)
- **One editor, one game thread.** Serialize ALL scene mutations — never two builders mutating at once. Read-only inspection can overlap, but not two `ExecuteGraphInstance`/edits.
