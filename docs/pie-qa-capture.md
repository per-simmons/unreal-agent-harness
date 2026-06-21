# QA-capturing the ACTUAL play camera of a possessed Cesium DynamicPawn (UE 5.8, via MCP)

> Goal: an agent screenshots what the **possessed chase camera** sees — not the editor flycam —
> so we stop relying on the human's eyes to verify the plane-chase view over the Google 3D Tiles
> scene (`/Game/NYC/NYCFklyover2`). This is the QA companion to `plane-chase-pawn.md`.
>
> Grounded in the LIVE MCP (`describe_toolset`, 2026-06-19) **and** the toolset C++ source:
> `/Users/Shared/Epic Games/UE_5.8/Engine/Plugins/Experimental/Toolsets/EditorToolset/Source/EditorToolset/Private/EditorAppToolset.cpp`.
> Where a claim comes from source it cites `EditorAppToolset.cpp:<line>`.

---

## TL;DR — the two methods, in order of preference

1. **RECOMMENDED — capture the live game viewport during in-viewport PIE.**
   If full PIE survives even one tick, `CaptureViewport` reads the **game framebuffer** (the chase
   cam), because `PlayMode_InViewPort` renders the game *into the same level-viewport widget* that
   `CaptureViewport` screenshots. Use `warmupSeconds: 0` so `StartPIE` returns the instant PIE is
   up — **before** the teardown that produces "PIE ended before warmup completed" — then capture
   immediately. This shows the REAL possessed camera.

2. **FALLBACK — replicate the chase pose in Simulate.**
   If full PIE won't stay alive long enough to capture, run `bSimulate: true` (more stable: input
   isn't possessed, but BeginPlay + ticks run, so `CesiumOriginShiftComponent` still re-anchors the
   pawn near world origin). Read the pawn's TRUE runtime world transform with
   `ActorTools.get_actor_transform`, compute `pawn_world * chase_offset`, and pass that pose
   straight into `CaptureViewport`'s `CaptureTransform`. This is a **reconstruction** of the chase
   view, not the engine's own camera, but it is deterministic and crash-light.

Do Method 1 first. Fall back to Method 2 only if PIE tears down before you can capture.

---

## Why the prior attempts failed (root causes, from source)

### "CaptureViewport in Simulate grabs the EDITOR camera" — confirmed, by design
`CaptureViewport` always uses `GCurrentLevelEditingViewportClient` and reports that client's
`GetViewLocation()/GetViewRotation()` (`EditorAppToolset.cpp:1089`, `1108-1109`, `1166-1168`). In
**Simulate**, the editor flycam IS the active view of that client, so you get the editor camera.
BUT the pixels come from `GetViewportScreenShot(Viewport, Bitmap)` (`:1152`) — the **framebuffer of
that viewport widget**. In **in-viewport PIE** the game renders into that same widget, so the
framebuffer contains the GAME (chase-cam) image even though the returned camera *metadata* is the
editor client's. That single distinction is what makes Method 1 work and is why Simulate alone
can't show the chase cam.

### "PIE ended before warmup completed" — PIE really is tearing down, not a detection bug
The startup watcher (`FPIEStartupWatcher`, `EditorAppToolset.cpp:744-827`) does:
1. subscribe to `FEditorDelegates::PostPIEStarted`; record `PIEStartedTime` when it fires (`:769`).
2. each tick: if `GEditor->PlayWorld` is null *after* PIE started → error
   **"PIE ended before warmup completed"** (`:803-808`).
3. else, once `Now - PIEStartedTime >= WarmupSeconds`, `SetCompleted()` (`:810-816`).

So `PostPIEStarted` DID fire (PIE started), then `PlayWorld` went null inside the warmup window =
**PIE genuinely shut down**, consistent with the log's "runs ~5s then tears down." The tool is
faithfully reporting a real teardown. The 30s figure in the message family is the *timeout* branch
(`:791`), a different error string; ours is the teardown branch.

**The lever:** with `warmupSeconds: 0`, step 3's `Now - PIEStartedTime >= 0` is satisfied on the
**first tick after `PostPIEStarted`** (`:810`). If `PlayWorld` is still alive on that one tick,
`StartPIE` returns success immediately — ahead of the teardown — and you get a window to capture.
(If the teardown is same-tick as start, even warmup 0 returns the teardown error; then use
Method 2.)

---

## Call form

All calls: `mcp__unreal__call_tool` with
`{ "toolset_name": "<toolset>", "tool_name": "<tool>", "arguments": { ... } }`.
`EditorAppToolset` tool names are PascalCase (`StartPIE`, `CaptureViewport`, `IsPIERunning`,
`StopPIE`, `SetCameraTransform`). The `editor_toolset.*` toolsets use snake_case
(`get_actor_transform`, `find_actors`, …).

---

## METHOD 1 — capture the live PIE game view (RECOMMENDED)

### M1.0 Pre-flight (read-only)
```jsonc
{ "toolset_name": "EditorToolset.EditorAppToolset", "tool_name": "IsPIERunning", "arguments": {} }
// → must be false. If true: STOP (someone's already playing).
```

### M1.1 Start full PIE with ZERO warmup, in-viewport
```jsonc
{ "toolset_name": "EditorToolset.EditorAppToolset", "tool_name": "StartPIE",
  "arguments": {
    "options": {
      "bSimulate": false,
      "playMode": "PlayMode_InViewPort",
      "warmupSeconds": 0,
      "startTransform": {
        "location": { "x": 0.0, "y": -15000.0, "z": 30000.0 },
        "rotation": { "pitch": -10.0, "yaw": 90.0, "roll": 0.0 },
        "scale":    { "x": 1.0, "y": 1.0, "z": 1.0 }
      }
    }
  } }
```
- `warmupSeconds: 0` → `StartPIE` completes on the first post-start tick the play world is alive
  (`EditorAppToolset.cpp:810`), so control returns to you *before* the teardown.
- `PlayMode_InViewPort` is mandatory: only in-viewport renders the game into the widget that
  `CaptureViewport` reads. Out-of-process modes are downgraded with a warning and break the
  watcher (`:929-941`) — never use them here.
- Two possible returns:
  - **success** → PIE is up; go to M1.2 IMMEDIATELY (don't insert other calls; the teardown clock
    is running).
  - **error "PIE ended before warmup completed"** → PIE tore down same/next tick. Do NOT retry
    blindly. Pull the teardown cause from the log (M1.4), then switch to **Method 2**.

### M1.2 Capture the game framebuffer (the chase cam)
Call this the instant M1.1 succeeds. Pass NO `captureTransform` — you want whatever the game is
actually rendering (the possessed chase camera), not an overridden pose. `bShowUI: false` hides
editor gizmos/selection outline (`:1110-1127`, `:240-246`); the game HUD still renders.
```jsonc
{ "toolset_name": "EditorToolset.EditorAppToolset", "tool_name": "CaptureViewport",
  "arguments": { "bShowUI": false } }
```
Read the returned image:
- **plane visible, camera behind+above it, skyline ahead → SUCCESS (this is the real chase view).**
- inside the plane (first-person) → CalcCamera-override case; see `plane-chase-pawn.md` Step 5d #2.
- plane sideways/belly-first → fix `PlaneMesh.RelativeRotation` in the EDITOR world (PIE stopped),
  then re-run.

> NOTE on returned camera metadata: `Out.CameraLocation/Rotation/FOV` describe the editor client,
> not the game cam (`:1166-1168`). **Trust the pixels, not those numbers.** For ground-truth of the
> game camera pose, read it from the possessed pawn at runtime (Method 2's M2.3 read works during
> full PIE too — just target the PIE-world pawn).

### M1.3 (optional) burst captures if one frame is ambiguous
If PIE survives a few ticks, you may call `CaptureViewport` 2-3 times back to back to catch a
clean, streamed-in frame (3D Tiles pop in over a second or two). Stop the moment a capture
errors — that means `PlayWorld` is gone.

### M1.4 Stop PIE / harvest teardown cause
```jsonc
{ "toolset_name": "EditorToolset.EditorAppToolset", "tool_name": "IsPIERunning", "arguments": {} }
// if true:
{ "toolset_name": "EditorToolset.EditorAppToolset", "tool_name": "StopPIE", "arguments": {} }
```
If M1.1 errored, read why PIE died (do NOT relaunch the editor):
```jsonc
{ "toolset_name": "EditorToolset.LogsToolset", "tool_name": "...read output log...",
  "arguments": {} }   // describe_toolset EditorToolset.LogsToolset for exact tool/args
```
or tail the abslog on disk: `~/coding/unreal-agent-harness/logs/ue_*.log` (the harness launches UE
with `-abslog=`; see `ue_launch.sh`). Look around the warmup mark for the BeginPlay-time fault
(Cesium subsystem, georeference rebase, RHI). Cross-check `unreal-stability-gotchas` /
`cesium-splat-subsystem-disable.md` — the splat patch must be live for PIE.

---

## METHOD 2 — reconstruct the chase view in Simulate (FALLBACK)

Use only if Method 1's full PIE won't stay alive to capture. Simulate runs BeginPlay + ticks
(so `CesiumOriginShiftComponent` re-anchors the pawn to near origin, exactly like Play) but does
**not** possess input, which tends to be more stable. The editor flycam stays the active view, so
we read the pawn's true runtime transform and aim the capture at it.

### M2.1 Start Simulate (small warmup so the origin-shift settles)
```jsonc
{ "toolset_name": "EditorToolset.EditorAppToolset", "tool_name": "StartPIE",
  "arguments": { "options": { "bSimulate": true, "playMode": "PlayMode_InViewPort",
                              "warmupSeconds": 1.0 } } }
```
A 1s warmup lets BeginPlay + the first origin-shift tick run so `get_actor_transform` returns the
**re-centered** pose, not the editor placement. If even Simulate reports "ended before warmup,"
drop to `warmupSeconds: 0` and read the transform on the next call regardless.

### M2.2 Find the SIMULATE-world pawn  ⚠ the main gotcha
`find_actors` / `get_actor_transform` resolve against `GEditor->GetEditorWorldContext().World()`
(`EditorAppToolset.cpp:401`, `:1214`) — i.e. the **EDITOR** world, whose DynamicPawn still sits at
its authored placement and was NOT origin-shifted. To get the re-centered runtime pose you must
target the **PIE/Simulate world** pawn. Resolve it and VERIFY which world you got:
```jsonc
// class ref for the pawn:
{ "toolset_name": "editor_toolset.toolsets.object.ObjectTools", "tool_name": "search_subclasses",
  "arguments": { "base_class": { "refPath": "/Script/CesiumRuntime.GlobeAwareDefaultPawn" },
                 "class_name": "DynamicPawn" } }   // → <DYNPAWN_CLASS>

// instances of that class (during Simulate, both editor + PIE instances may appear):
{ "toolset_name": "editor_toolset.toolsets.scene.SceneTools", "tool_name": "find_actors",
  "arguments": { "name": "", "tag": "", "collision_channels": [],
                 "actor_type": { "refPath": "<DYNPAWN_CLASS>" } } }
```
Disambiguate by transform: read `get_actor_transform` on each returned instance. The one whose
location is **near world origin** (CesiumOriginShift recenters the anchored pawn to ~0; the editor
copy stays at its large authored coords) is the runtime pawn → `<PAWN_RUNTIME>`. If only the
editor-world instance is returned (origin-shift recenters in the PIE world only and that instance
isn't enumerated), Method 2 can't read the true runtime pose — fall back to capturing whatever the
single instance reports and note the caveat, or return to Method 1.

### M2.3 Read the pawn's TRUE runtime world transform
```jsonc
{ "toolset_name": "editor_toolset.toolsets.actor.ActorTools", "tool_name": "get_actor_transform",
  "arguments": { "actor": { "refPath": "<PAWN_RUNTIME>" } } }
// → { location:{x,y,z}, rotation:{pitch,yaw,roll}, scale:{...} }  (WORLD space; see :get_actor_transform docstring)
```
Call this `Pw` (location) and `Rw` (rotation).

### M2.4 Compute the chase-camera pose (mirror plane-chase-pawn.md's boom)
The chase rig in `plane-chase-pawn.md` is: SpringArm `TargetArmLength 2000` back, `+Z 600` up,
pitched `-12°`, FOV 95, no collision test. Reproduce that geometry in world space:

Let `f` = pawn forward = `Rw.Vector()` (UE forward is +X). Camera offset in the pawn's frame is
`(-2000 along forward) + (+600 up)`. In world space:
```
cam_location = Pw  +  (-2000) * forward(Rw)  +  600 * up(Rw)
cam_rotation = Rw  +  pitch -12°   (yaw = Rw.yaw, roll = 0)
```
Compute `forward`/`up` from `Rw` (standard UE rotator basis): for a yaw-dominant flight pose,
`forward ≈ (cos(yaw)cos(pitch), sin(yaw)cos(pitch), sin(pitch))`,
`up` from the same rotator's Z axis. Keep it simple if pitch/roll are small: subtract
`2000*forward`, add `600*Z`, and set capture rotation = pawn rotation with pitch −12.

### M2.5 Capture from that computed pose
`CaptureViewport` takes a `captureTransform`; it sets the editor client to that pose, does a
synchronous `Viewport->Draw()` (`:1146-1149`), screenshots, then **restores the editor camera via
ON_SCOPE_EXIT** (`:1129-1142`) — so no separate camera-set/restore is needed and the user's flycam
is left untouched.
```jsonc
{ "toolset_name": "EditorToolset.EditorAppToolset", "tool_name": "CaptureViewport",
  "arguments": {
    "bShowUI": false,
    "captureTransform": {
      "location": { "x": <cam_x>, "y": <cam_y>, "z": <cam_z> },
      "rotation": { "pitch": <Rw.pitch - 12>, "yaw": <Rw.yaw>, "roll": 0.0 },
      "scale":    { "x": 1.0, "y": 1.0, "z": 1.0 }
    }
  } }
```
This frames the plane from the chase position. It is a faithful reconstruction of the rig, not the
engine's own CameraComponent output — note that when reporting QA results. (If you only need to
confirm the plane mesh orientation/scale/visibility, this is sufficient and far more stable than
fighting full-PIE teardown.)

> Alternative to the hand math: `ActorTools.look_at` can aim an actor at a world point, but it
> rotates an ACTOR, not the editor camera. There is no MCP call to invoke the engine's `CalcCamera`
> or `SetViewTarget`, so for the editor-camera capture the offset math above is the path.

### M2.6 Stop Simulate
```jsonc
{ "toolset_name": "EditorToolset.EditorAppToolset", "tool_name": "StopPIE", "arguments": {} }
```

---

## A third option if both fail: Slate screenshot of the running PIE viewport
`SlateInspectorToolset` (registered, see `list_toolsets`) exposes Playwright-style snapshot +
screenshot of the editor's Slate UI. During in-viewport PIE the play viewport is a Slate widget, so
its screenshot is another route to the live game pixels (Observe the level-viewport window, then
screenshot it). Heavier to drive than `CaptureViewport`; treat as a backstop if M1's framebuffer
read ever returns empty while PIE is genuinely up. `EditorAppToolset.CaptureEditorImage` likewise
composites all visible Slate windows (`EditorAppToolset.cpp:644`) and would include the PIE viewport,
but at editor-window scale, not a clean game frame.

---

## Crash-safety (unchanged from plane-chase-pawn.md)
- Gaussian-splat subsystem patch must stay live (PIE re-runs BeginPlay) — `cesium-splat-subsystem-disable.md`.
- Do NOT call `FocusOnActors` during PIE — it errors by design (`EditorAppToolset.cpp:384-388`).
- Don't touch `r.RayTracing*`, georeference Origin*, GameMode, or lighting actors to "fix" PIE
  teardown — diagnose from the log first.
- Never use out-of-process play modes (`PlayMode_InNewProcess`/VR/etc.) — they break the watcher
  and don't render to the capturable viewport.
- Build all pawn components in the EDITOR world with PIE stopped; PIE clones them. Components added
  during PIE die on StopPIE.

## One-line recipe
Method 1: `IsPIERunning`(false) → `StartPIE`(bSimulate=false, InViewPort, warmupSeconds=0) →
on success, `CaptureViewport`(bShowUI=false) immediately → read pixels → `StopPIE`.
On "ended before warmup": log-diagnose, then Method 2: `StartPIE`(bSimulate=true, warmup 1s) →
find PIE-world DynamicPawn (near-origin instance) → `get_actor_transform` → compute
`Pw − 2000·forward + 600·up`, pitch −12 → `CaptureViewport`(captureTransform=that) → `StopPIE`.
