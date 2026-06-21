# Flying-pawn Play mode for the Cesium Manhattan flyover (UE 5.8)

> Goal: make `/Game/NYC/NYCFklyover2` pilotable in FULL PIE — the user flies a free-flying
> pawn through Google Photorealistic 3D Tiles with WASD + mouse, no gravity, like a flight sim.
> Must NOT crash the live editor.
>
> Status of inputs verified on disk (2026-06-19), not assumed. See "Install verification" below.

---

## TL;DR — the recommendation

1. **Pawn:** use Cesium's **`DynamicPawn`** Blueprint — it ships in THIS install
   (`Plugins/CesiumForUnreal/Content/DynamicPawn.uasset`) and is a Blueprint based on the
   compiled C++ class **`GlobeAwareDefaultPawn`**. It flies by default (no gravity), WASD +
   mouse look + E/Q up/down, and it is *globe-aware* so altitude/curvature behave correctly
   over the georeferenced tiles. This is strictly better here than the stock
   `/Script/Engine.DefaultPawn` (which also flies, but is not globe-aware). DefaultPawn is the
   fallback if anything about DynamicPawn misbehaves.

2. **GameMode:** do NOT create a Blueprint. Cesium also ships **`FloatingGameMode`**
   (`Plugins/CesiumForUnreal/Content/FloatingGameMode.uasset`) whose `DefaultPawnClass` is
   already `DynamicPawn`. Set the level's WorldSettings `GameModeOverride` to it via
   `ObjectTools.set_properties`. One property write, no asset authoring.

3. **Spawn placement:** do NOT move PlayerStart and do NOT rely on it. The MCP `StartPIE`
   tool takes a `startTransform` override that spawns + possesses the pawn at an exact pose.
   Spawn a few hundred meters above scene origin, pitched down ~20°, looking north up the
   skyline. (Optional: also nudge the existing PlayerStart to match, as a non-MCP-Play
   fallback — covered below.)

4. **Crash-safety:** FULL PIE (`bSimulate=false`, `PlayMode_InViewPort`) is expected safe now
   — splat subsystem patched off, ray tracing off. The one real Cesium+PIE hazard is the
   georeference rebase on BeginPlay; we don't touch it (origin already lat 40.758 / lon
   -73.9855 / h 150). Hard rules unchanged: never `FocusOnActors` the tileset, no RT, no
   CesiumSunSky.

---

## Install verification (done, not assumed)

```
Plugins/CesiumForUnreal/Content/DynamicPawn.uasset        ✅ present
Plugins/CesiumForUnreal/Content/FloatingGameMode.uasset   ✅ present
Source/CesiumRuntime/.../GlobeAwareDefaultPawn.{h,cpp}     ✅ compiled in this build
Source/CesiumRuntime/.../CesiumFlyToComponent.{h,cpp}      ✅ present (NOT needed for free-flight)
```

So we do NOT need the Cesium Samples project (not installed). Everything required is in the
installed plugin. This is the difference from a vanilla Cesium install where you'd fall back to
`DefaultPawn`.

### Why DynamicPawn over DefaultPawn here
- Both fly by default (no gravity, WASD, mouse look). `DefaultPawn`/`SpectatorPawn` use
  `UFloatingPawnMovement`; DynamicPawn uses the Cesium globe-aware movement on top of a
  `CesiumGlobeAnchorComponent`, so "up" tracks the ellipsoid and speed scales with altitude.
- Over a single Manhattan tile at our origin the difference is small, but DynamicPawn is the
  intended pawn for flying P3DT and avoids the "up drifts as you travel" feel. No extra cost.
- `CesiumFlyToComponent` is for *scripted* camera fly-to animations (point A → B), NOT
  free-flight. Ignore it for this task.

---

## The exact MCP call sequence (ordered, ready to apply)

All tools are under the `mcp__unreal` server. Call form: `mcp__unreal__call_tool` with
`{ "tool": "<Toolset.Tool>", "arguments": { ... } }` (or however the harness wraps it — the
toolset.tool name + the JSON args below are the load-bearing part).

> Pre-flight: confirm nothing is already playing.
> `EditorToolset.EditorAppToolset.IsPIERunning {}`  → must be `false`. If `true`, STOP and ask.

### Step 0 — find the WorldSettings + PlayerStart actor refPaths
The level is loaded. Get actors so we have real `refPath`s (don't hand-fabricate them).

```json
// 0a. List the level's actors (SceneTools), or use GetVisibleActors as a quick path.
{ "tool": "editor_toolset.toolsets.scene.SceneTools.get_all_level_actors", "arguments": {} }
```
From the result, capture:
- the `WorldSettings` actor refPath (class `/Script/Engine.WorldSettings`),
- the `PlayerStart` actor refPath (class `/Script/Engine.PlayerStart`), if present,
- (sanity) the `Cesium3DTileset` and `CesiumGeoreference` refPaths — do not modify them.

> If `SceneTools` has no "get all actors" tool in this build, use
> `EditorToolset.EditorAppToolset.GetVisibleActors {}` and/or
> `EditorToolset.EditorAppToolset.GetSelectedActors {}` after selecting, OR open the World
> Settings panel — but the actor-list path is cleanest. The point is: obtain the real
> WorldSettings refPath; everything below pastes it in.

### Step 1 — point the level's GameMode at FloatingGameMode (DefaultPawn = DynamicPawn)
First confirm the exact property name on WorldSettings (do NOT guess — list then set):

```json
// 1a. Discover the property name (it's GameModeOverride, but verify).
{ "tool": "editor_toolset.toolsets.object.ObjectTools.list_properties",
  "arguments": { "object": { "refPath": "<WORLDSETTINGS_REFPATH>" } } }
```

```json
// 1b. Set GameModeOverride to the FloatingGameMode class.
//     Note: this is a CLASS-valued property -> pass the GeneratedClass (…_C) refPath.
{ "tool": "editor_toolset.toolsets.object.ObjectTools.set_properties",
  "arguments": {
    "object": { "refPath": "<WORLDSETTINGS_REFPATH>" },
    "properties": {
      "GameModeOverride": { "refPath": "/CesiumForUnreal/FloatingGameMode.FloatingGameMode_C" }
    }
  } }
```

> Verify the class refPath resolves before relying on it:
> `editor_toolset.toolsets.object.ObjectTools.find_class` (or `ObjectTools.get_class`) with
> name `FloatingGameMode_C`, OR `AssetTools` load of `/CesiumForUnreal/FloatingGameMode`. The
> package path for a plugin asset is `/CesiumForUnreal/…` (the plugin's mount point), NOT
> `/Game/…`. The runtime class is the asset name + `_C`.
>
> **Fallback if FloatingGameMode won't resolve as a class:** set GameModeOverride to
> `/Script/Engine.GameModeBase` is NOT enough (its DefaultPawnClass is `DefaultPawn`, which
> flies but isn't globe-aware) — that's actually an acceptable free-flight result. So the
> tiered fallback is:
>   1. `/CesiumForUnreal/FloatingGameMode.FloatingGameMode_C`  (best: DynamicPawn)
>   2. leave GameModeOverride empty + set the **project** default pawn — skip, too global.
>   3. Use `startTransform` + accept whatever the level's current GameMode spawns; if that's a
>      character with gravity you'll fall — so prefer (1). If (1) fails, the cleanest stock
>      option is to set GameModeOverride to a GameMode whose DefaultPawnClass you can set, but
>      DefaultPawnClass lives on the GameMode CDO, not WorldSettings, and editing a CDO over
>      MCP is fiddly. Net: **make option 1 work** — FloatingGameMode is right there.

### Step 2 — (optional) align the existing PlayerStart, for non-MCP Play
This is belt-and-suspenders so that if the user just presses the Play button (instead of MCP
`StartPIE`), they still spawn above the city. `startTransform` in Step 3 makes this optional.

```json
{ "tool": "editor_toolset.toolsets.actor.ActorTools.set_actor_transform",
  "arguments": {
    "actor": { "refPath": "<PLAYERSTART_REFPATH>" },
    "xform": {
      "location": { "x": 0.0, "y": -15000.0, "z": 30000.0 },
      "rotation": { "pitch": -20.0, "yaw": 90.0, "roll": 0.0 }
    },
    "worldspace": true
  } }
```

Coords rationale (scene origin = Manhattan ground at lat 40.758 / lon -73.9855 / h 150):
- `z = 30000` cm = **300 m** above origin — comfortably above street level, below the tile's
  far-LOD pop, good skyline framing.
- `y = -15000` cm = **150 m** back so the origin block is in front, not under you.
- `pitch = -20` look slightly down at the streets; `yaw = 90` face +Y. Tune yaw after the
  first CaptureViewport so you're looking up the avenue toward the tall buildings.

### Step 3 — START FULL PIE with a spawn-pose override
This single call spawns + possesses the DynamicPawn at the exact pose, no PlayerStart needed.

```json
{ "tool": "EditorToolset.EditorAppToolset.StartPIE",
  "arguments": {
    "options": {
      "bSimulate": false,
      "playMode": "PlayMode_InViewPort",
      "startTransform": {
        "location": { "x": 0.0, "y": -15000.0, "z": 30000.0 },
        "rotation": { "pitch": -20.0, "yaw": 90.0, "roll": 0.0 },
        "scale":    { "x": 1.0, "y": 1.0, "z": 1.0 }
      },
      "warmupSeconds": 4.0
    }
  } }
```

- `bSimulate:false` + `PlayMode_InViewPort` = **FULL PIE**, pawn possessed, input active.
- `warmupSeconds: 4` lets BeginPlay run the georeference rebase + first tile fetch settle
  before you inspect/screenshot. The Google P3DT tiles stream in over a few seconds — expect
  low-res → sharpen.

### Step 4 — verify it's flying (no input simulation needed for the human)
```json
{ "tool": "EditorToolset.EditorAppToolset.IsPIERunning", "arguments": {} }   // expect true
```
Then capture to confirm the skyline is in frame and tiles are loading:
```json
{ "tool": "EditorToolset.EditorAppToolset.CaptureViewport", "arguments": { "bShowUI": true } }
```
(`bShowUI:true` so you see the PIE viewport as the user sees it. Do NOT pass annotations/grid
over the tileset — pointless and clutters.) If the skyline isn't framed, `StopPIE`, adjust
`yaw`/`y` in Step 3, `StartPIE` again.

### Step 5 — hand control to the user
PIE is now live in the viewport. Tell the user: **click once inside the play viewport to give
it keyboard focus**, then fly. Controls below.

### Step 6 — exit
```json
{ "tool": "EditorToolset.EditorAppToolset.StopPIE", "arguments": {} }
```

---

## Controls the user will have (DynamicPawn / GlobeAwareDefaultPawn defaults)

| Input | Action |
|-------|--------|
| **W / S** | fly forward / backward (along view direction) |
| **A / D** | strafe left / right |
| **E / Q** (or Space / C) | ascend / descend |
| **Mouse move** | look / aim (free-look while focused) |
| **Mouse wheel / Shift** | speed up movement (Cesium scales speed with altitude) |

Entering/exiting:
- **Enter Play:** we drive it via MCP `StartPIE` (Step 3). The user can also press the editor
  **Play** button — with FloatingGameMode set + PlayerStart aligned (Step 2) that also works.
- **Focus:** the user MUST left-click inside the play viewport once or WASD won't register
  (mouse/keyboard focus goes to the play world only after a click).
- **Eject (fly the editor camera without possessing):** **F8** toggles eject/possess.
- **Exit Play:** **Esc** in the viewport, or MCP `StopPIE`.

---

## GO / NO-GO safety checklist

GO only if ALL are true:

- [ ] `IsPIERunning` returns **false** before starting (no session already up).
- [ ] Ray tracing is **OFF** and stays off (do not touch `r.RayTracing*`).
- [ ] Cesium **gaussian-splat subsystem patch** is in place (the source early-out) — that's the
      crash we already fixed; FULL PIE re-runs BeginPlay so the patch must be live.
- [ ] We are **NOT** calling `FocusOnActors` on the Cesium3DTileset (or any tileset) — known to
      thrash bounds on a streaming tileset. (`FocusOnActors` also errors during PIE anyway.)
- [ ] No **CesiumSunSky** added/toggled; lighting actors (DirectionalLight / SkyAtmosphere /
      SkyLight / VolumetricCloud) are left as-is.
- [ ] The **CesiumGeoreference origin is unchanged** (lat 40.758 / lon -73.9855 / h 150). We do
      NOT write any Origin* property — setting those re-triggers a full rebase (see
      cesium-rebase-solution.md). Leave them alone; BeginPlay rebases on its own.
- [ ] We only modify: WorldSettings.GameModeOverride (Step 1) and optionally the PlayerStart
      transform (Step 2). We do **not** modify the tileset, georeference, or any material.
- [ ] `StartPIE` uses `PlayMode_InViewPort` (in-process) — NOT NewProcess/QuickLaunch (those
      get downgraded anyway, but be explicit).

NO-GO / abort to Simulate if:
- The editor is mid-cook/mid-build, or another agent is editing the level.
- `GameModeOverride` set fails to resolve `FloatingGameMode_C` AND `DefaultPawn` fallback isn't
  acceptable (you'd spawn a falling Character). Fix the class path first.
- First `CaptureViewport` after `StartPIE` shows a black/empty frame that doesn't recover within
  a couple seconds → `StopPIE`, check the log (LogsToolset) for Cesium tile errors before retry.

---

## Why FULL PIE is safe now (the reasoning, briefly)

We already proved Simulate (`bSimulate:true`) runs the BeginPlay rebase + streams tiles without
crashing. FULL PIE differs only by (a) spawning + possessing a pawn and (b) routing input —
neither touches the rendering/tile path that caused the earlier Metal RHI splat crash. That
crash is patched out at the subsystem `Tick` (see cesium-splat-subsystem-disable.md), and that
patch is in the plugin copy the project actually loads, so it applies in PIE too. Ray tracing
is off, so no RT-scene rebuild on possess. The georeference origin is untouched, so no surprise
rebase beyond the normal BeginPlay one we've already seen succeed.

The residual risk is purely "does the chosen pawn spawn cleanly" — which is why we use a stock
shipped pawn (DynamicPawn) + shipped GameMode (FloatingGameMode) rather than anything custom.
