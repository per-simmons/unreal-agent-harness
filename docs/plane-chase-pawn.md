# Third-person flying PLANE pawn — visible airplane + chase camera (UE 5.8)

> Goal: the user SEES a real airplane body and pilots it third-person (chase cam) flying through
> the Google Photorealistic 3D Tiles Manhattan scene `/Game/NYC/NYCFklyover2`.
> Builds on `flight-pawn-setup.md` (which made the scene pilotable first-person via Cesium
> **DynamicPawn**). This doc adds the **visible plane mesh + a SpringArm + chase Camera**.
>
> The plane is a REALISTIC aircraft Pat brings from Fab (fab.com) — its asset path/scale/axis are
> TBD until it's in-engine. This spec is plane-agnostic: it attaches WHATEVER plane StaticMesh you
> point `<PLANE_SM_REFPATH>` at. (Low-poly CC0 auto-download is dropped — see the asset section.)
>
> Tool/arg names below were verified against the LIVE MCP on 2026-06-19 via
> `describe_toolset` (ActorTools, SceneTools, StaticMeshTools, ObjectTools, EditorAppToolset).
> Anything still uncertain is flagged **VERIFY**. Do NOT touch the live editor without the
> GO/NO-GO checklist at the bottom.

---

## The plane asset — REALISTIC, from Fab (Pat supplies it; path TBD)

Low-poly CC0 (Poly Pizza / Kenney / Quaternius) is **dropped** — it looks cartoonish against the
photoreal Google 3D Tiles. We want a **realistic** aircraft, which in practice means **Fab**
(Epic's marketplace, fab.com). Fab requires Pat's manual clicks (no scriptable API/auth), so the
asset arrives one of two ways — this spec works for both:

- **Path 1 (cleanest): "Add to My Library" in Fab → install to this UE project.** The plane then
  lives as a project asset under `/Game/...` (or a plugin/marketplace mount like
  `/PluginName/...`). No file import needed — **skip Step 1 entirely** and use that content path
  directly as `<PLANE_SM_REFPATH>` in Step 3. Find it with `find_actors`/the content browser, or
  `ObjectTools.search_subclasses` of `/Script/Engine.StaticMesh` filtered by name.
- **Path 2: Pat exports/downloads an FBX (or OBJ) to disk.** Then Step 1 imports it. The on-disk
  path is **TBD** — Pat will drop it somewhere like
  `~/coding/unreal-agent-harness/assets/downloaded/plane/<name>.fbx`. Plug that absolute path into
  Step 1's `source_file`. (FBX preferred; OBJ also accepted by `import_file`. GLB is NOT accepted —
  if Fab gives only GLB, convert GLB→FBX with the harness Blender pattern in `blender_jobs.py`.)

**Whatever the realistic plane is, two things are unknown until it's in-engine — discover them, do
NOT assume:**

1. **Scale.** Realistic Fab planes are usually authored at real-world size, but units vary (some
   come in tiny, some at cm). After import/locate, call `StaticMeshTools.get_bounds` and read the
   real extent. UE is in **cm**, so a believable aircraft is roughly **1000–4000 cm** on its
   longest axis (10–40 m). Set the mesh **component** `RelativeScale3D` (Step 3c) to land in that
   range — `1.0` if it's already ~10–40 m; `100` if it imported in meters-as-units; `0.01` if it's
   absurdly huge. **Decide from the measured bounds, not a guess.**
2. **Forward axis + up axis.** UE pawn "forward" is **+X**, "up" is **+Z**. The plane's nose may
   be modeled along +Y or −X, and FBX from DCC tools often comes in Y-up → needs a roll/pitch fix.
   Set the mesh component `RelativeRotation` (Step 3c) so the **nose points +X and the plane is
   upright**, then CONFIRM visually with a CaptureViewport (Step 7) and adjust. Typical fixes:
   Yaw ±90 (nose was +Y), Yaw 180 (nose was −X), Roll/Pitch ±90 (Y-up source). Use
   `StaticMeshTools.get_bounds` to infer the long axis (nose-tail) vs the wide axis (wingspan)
   before guessing.

Everything else below is plane-agnostic: it attaches **whatever** StaticMesh `<PLANE_SM_REFPATH>`
points at, plus a chase camera, to the flying pawn.

---

## TL;DR recommendation: **Option 1 — attach components to the existing DynamicPawn instance**

`ActorTools.add_component` works on a **live actor instance** (not just a Blueprint) — verified
in the schema: `owner` accepts `/Script/CoreUObject.Object` (an actor or a SceneComponent),
`component_type` is a `Class` ref, returns the new `ActorComponent`. That means we can bolt a
StaticMeshComponent (the plane), a SpringArmComponent, and a CameraComponent straight onto the
DynamicPawn that already flies — **no Blueprint authoring required**, which is good because we
can't author a custom Pawn Blueprint's movement logic over this MCP.

**Why not Option 2 (build a brand-new Pawn):** `SceneTools.add_to_scene_from_class` can spawn an
actor of any class, and we could add the three components to it — but a stock `Pawn`/`DefaultPawn`
gives us no *flight movement we can wire up over MCP* (input bindings + a UFloatingPawnMovement
hookup live in C++/Blueprint graph logic we can't author here — see
`programmatic-toolset-capabilities.md`: no UFUNCTION calls, no graph authoring that compiles new
behavior). DynamicPawn already HAS the globe-aware flight movement + input. So we reuse it and
just make it visible + add a chase cam. **Option 2 is the fallback ONLY if add_component on the
live DynamicPawn instance fails to persist into PIE** (see "If Option 1 fails" at the end).

The component tree we are building on the DynamicPawn:

```
DynamicPawn (root: its existing CollisionComponent / capsule — DO NOT replace)
└─ SpringArm   (new, attached to root)         length ~2000cm back+up, lag on
   └─ ChaseCam (new CameraComponent, attached to SpringArm socket)   ← becomes the view
PlaneMesh (new StaticMeshComponent, attached to root)  ← the visible airplane, offset to center
```

Everything below is the ordered MCP call sequence. Call form (this MCP):
`mcp__unreal__call_tool` with `{ "toolset_name": "<toolset>", "tool_name": "<tool>",
"arguments": { ... } }`. `ObjectTools.set_properties` takes its `values` as a **JSON STRING**,
not an object — that's a schema gotcha, shown literally below.

---

## Pre-flight

```jsonc
// P0. Nothing already playing.
{ "toolset_name": "EditorToolset.EditorAppToolset", "tool_name": "IsPIERunning", "arguments": {} }
// → must be false. If true: STOP, ask the user.

// P1. Confirm the right level is loaded.
{ "toolset_name": "editor_toolset.toolsets.scene.SceneTools",
  "tool_name": "get_current_level", "arguments": {} }
// → expect a path ending in NYCFklyover2. If not, the flight-pawn-setup.md GameMode step may not
//   be in effect — reconcile before proceeding.
```

---

## Step 1 — get the realistic plane to a StaticMesh `<PLANE_SM_REFPATH>`

**If Pat installed the Fab plane to the project (Path 1): SKIP the import.** The mesh already has
a content path. Locate it and set `<PLANE_SM_REFPATH>` to that asset's refPath:
```jsonc
{ "toolset_name": "editor_toolset.toolsets.object.ObjectTools",
  "tool_name": "search_subclasses",
  "arguments": { "base_class": { "refPath": "/Script/Engine.StaticMesh" },
                 "class_name": "<plane-name-substring>" } }
// or browse: EditorAppToolset.SetContentBrowserPath to the Fab folder + GetSelectedAssets.
// Realistic Fab planes are sometimes SKELETAL meshes (rigged gear/flaps). If so, you'll want a
// StaticMesh for a simple chase body — either use the SkeletalMeshComponent path (add a
// /Script/Engine.SkeletalMeshComponent instead in Step 3 and set its SkeletalMeshAsset), or have
// Pat export a static FBX. Most chase-cam needs are fine with whichever renders; flag which it is.
```

**If Pat dropped an FBX/OBJ on disk (Path 2): import it.** Replace `<PLANE_FILE_ON_DISK>` with the
actual absolute path Pat provides (TBD), and `<PlaneName>` with a clean asset name:
```jsonc
{ "toolset_name": "editor_toolset.toolsets.static_mesh.StaticMeshTools",
  "tool_name": "import_file",
  "arguments": {
    "folder_path": "/Game/NYC/Plane",
    "asset_name": "SM_<PlaneName>",
    "source_file": "<PLANE_FILE_ON_DISK>",
    "import_materials": true,
    "import_textures": true,
    "combine_meshes": true
  } }
```
- `combine_meshes:true` → a multi-part plane (fuselage/wings/gear) becomes ONE StaticMesh
  (`returnValue[0]`). Capture that refPath as `<PLANE_SM_REFPATH>`
  (`/Game/NYC/Plane/SM_<PlaneName>.SM_<PlaneName>`).
- `import_materials:true` + `import_textures:true` so a realistic plane keeps its PBR look (the
  whole point vs low-poly). If textures live in a sidecar folder, point Fab/Pat to embed them or
  place them next to the FBX before import.

```jsonc
// 1b. MANDATORY size check (UE = cm). This drives the component scale in Step 3c — do not guess.
{ "toolset_name": "editor_toolset.toolsets.static_mesh.StaticMeshTools",
  "tool_name": "get_bounds",
  "arguments": { "mesh": { "refPath": "<PLANE_SM_REFPATH>" } } }
```
- Read the longest axis (max−min). Target a believable aircraft: **~1000–4000 cm** (10–40 m).
  - already ~1000–4000 cm → component scale **1.0**
  - ~10–40 (imported in meters-as-units) → scale **100**
  - tens of thousands of cm (way too big) → scale **0.01–0.1**
- Note which local axis is longest (nose-tail) vs second (wingspan) — informs the yaw fix in 3c.

```jsonc
// 1c. Recommended: turn OFF collision on the plane mesh asset so the visible body never
//     blocks/encloses the pawn's own collision (it's attached purely as the cosmetic chase body).
{ "toolset_name": "editor_toolset.toolsets.static_mesh.StaticMeshTools",
  "tool_name": "remove_collisions",
  "arguments": { "mesh": { "refPath": "<PLANE_SM_REFPATH>" } } }
```

---

## Step 2 — find the live DynamicPawn instance + its root component

The DynamicPawn is already placed (AutoPossessPlayer=Player0). Get its real refPath — don't
fabricate it.

```jsonc
// 2a. Find by class. DynamicPawn is a Blueprint of GlobeAwareDefaultPawn; search that base.
{ "toolset_name": "editor_toolset.toolsets.object.ObjectTools",
  "tool_name": "search_subclasses",
  "arguments": {
    "base_class": { "refPath": "/Script/CesiumRuntime.GlobeAwareDefaultPawn" },
    "class_name": "DynamicPawn"
  } }
// → gives the DynamicPawn_C class refPath (≈ /CesiumForUnreal/DynamicPawn.DynamicPawn_C).
//   Call it <DYNPAWN_CLASS>.
```

```jsonc
// 2b. Find the placed instance of that class in the level.
{ "toolset_name": "editor_toolset.toolsets.scene.SceneTools",
  "tool_name": "find_actors",
  "arguments": {
    "name": "",
    "tag": "",
    "collision_channels": [],
    "actor_type": { "refPath": "<DYNPAWN_CLASS>" }
  } }
// → returnValue[0].refPath = <DYNPAWN_REFPATH>. (If empty, fall back to actor_type =
//   /Script/CesiumRuntime.GlobeAwareDefaultPawn, or name-search "DynamicPawn".)
//   NOTE: find_actors requires name/tag/collision_channels keys even when empty.
```

```jsonc
// 2c. Get the pawn's root SceneComponent — new components attach to this.
{ "toolset_name": "editor_toolset.toolsets.actor.ActorTools",
  "tool_name": "get_root_component",
  "arguments": { "actor": { "refPath": "<DYNPAWN_REFPATH>" } } }
// → returnValue.refPath = <PAWN_ROOT>. Do NOT replace or reparent the root (it's the pawn's
//   collision/movement anchor).
```

```jsonc
// 2d. (Diagnostic) See what's already on the pawn so we don't duplicate a camera.
{ "toolset_name": "editor_toolset.toolsets.actor.ActorTools",
  "tool_name": "get_components",
  "arguments": { "actor": { "refPath": "<DYNPAWN_REFPATH>" } } }
// DynamicPawn ships with a GlobeAwareDefaultPawn camera setup. We're adding our OWN SpringArm
// chase cam and will make IT the active view (Step 6). If there's an existing CameraComponent,
// note its refPath as <DEFAULT_CAM> — we set bAutoActivate/bIsActive false on it in Step 6 so
// our chase cam wins. VERIFY the exact existing-camera property names with list_properties
// before assuming.
```

---

## Step 3 — add the visible PLANE mesh component to the pawn

```jsonc
// 3a. Add a StaticMeshComponent to the pawn root.
{ "toolset_name": "editor_toolset.toolsets.actor.ActorTools",
  "tool_name": "add_component",
  "arguments": {
    "owner": { "refPath": "<DYNPAWN_REFPATH>" },
    "component_type": { "refPath": "/Script/Engine.StaticMeshComponent" },
    "name": "PlaneMesh"
  } }
// → returnValue.refPath = <PLANE_COMP>.
```

```jsonc
// 3b. Make sure it's parented to the pawn root (add_component usually attaches to root already;
//     this is belt-and-suspenders / corrects if it landed unattached).
{ "toolset_name": "editor_toolset.toolsets.actor.ActorTools",
  "tool_name": "set_parent_component",
  "arguments": {
    "component": { "refPath": "<PLANE_COMP>" },
    "parent":    { "refPath": "<PAWN_ROOT>" }
  } }
```

```jsonc
// 3c. Point the component at the imported plane mesh AND orient/scale it.
//     values is a JSON STRING (escaped). StaticMesh is an object property -> nested refPath.
//     RelativeRotation = the nose-to-+X / upright fix you determined from Step 1b's bounds
//     (start Yaw 90 if nose was +Y; flip/adjust after the Step 7 capture). RelativeScale3D = the
//     scale you chose from Step 1b's measured bounds (1.0 / 100 / 0.01 — NOT a fixed value).
{ "toolset_name": "editor_toolset.toolsets.object.ObjectTools",
  "tool_name": "set_properties",
  "arguments": {
    "instance": { "refPath": "<PLANE_COMP>" },
    "values": "{ \"StaticMesh\": { \"refPath\": \"<PLANE_SM_REFPATH>\" }, \"RelativeRotation\": { \"Pitch\": 0.0, \"Yaw\": 90.0, \"Roll\": 0.0 }, \"RelativeScale3D\": { \"X\": 1.0, \"Y\": 1.0, \"Z\": 1.0 }, \"RelativeLocation\": { \"X\": 0.0, \"Y\": 0.0, \"Z\": 0.0 } }"
  } }
// VERIFY first with list_properties on <PLANE_COMP> that the property names are exactly
// "StaticMesh", "RelativeRotation", "RelativeScale3D", "RelativeLocation" (they are on
// UStaticMeshComponent/USceneComponent, but list to be safe). If the nose points the wrong way
// after capture, change Yaw to -90; if it flies belly-forward, add Pitch. RelativeLocation can
// recenter the body on the camera pivot if the mesh pivot is off-center.
```

---

## Step 4 — add the SpringArm (chase boom)

```jsonc
// 4a. Add a SpringArmComponent to the pawn root.
{ "toolset_name": "editor_toolset.toolsets.actor.ActorTools",
  "tool_name": "add_component",
  "arguments": {
    "owner": { "refPath": "<DYNPAWN_REFPATH>" },
    "component_type": { "refPath": "/Script/Engine.SpringArmComponent" },
    "name": "ChaseBoom"
  } }
// → <SPRINGARM_COMP>.
```

```jsonc
// 4b. Parent it to the pawn root (so the boom rotates with the plane).
{ "toolset_name": "editor_toolset.toolsets.actor.ActorTools",
  "tool_name": "set_parent_component",
  "arguments": {
    "component": { "refPath": "<SPRINGARM_COMP>" },
    "parent":    { "refPath": "<PAWN_ROOT>" }
  } }
```

```jsonc
// 4c. Configure the boom: ~2000 cm behind & ~600 up, no collision test (tiles would yank the
//     camera), camera lag for a smooth chase feel. TargetArmLength is along the arm's -X, so the
//     boom is mounted facing forward and pitched slightly down to look over the plane.
{ "toolset_name": "editor_toolset.toolsets.object.ObjectTools",
  "tool_name": "set_properties",
  "arguments": {
    "instance": { "refPath": "<SPRINGARM_COMP>" },
    "values": "{ \"TargetArmLength\": 2000.0, \"bDoCollisionTest\": false, \"bEnableCameraLag\": true, \"CameraLagSpeed\": 5.0, \"bEnableCameraRotationLag\": true, \"CameraRotationLagSpeed\": 6.0, \"bUsePawnControlRotation\": false, \"RelativeLocation\": { \"X\": 0.0, \"Y\": 0.0, \"Z\": 600.0 }, \"RelativeRotation\": { \"Pitch\": -12.0, \"Yaw\": 0.0, \"Roll\": 0.0 } }"
  } }
// VERIFY names via list_properties on <SPRINGARM_COMP>. Canonical USpringArmComponent props:
// TargetArmLength, bDoCollisionTest, bEnableCameraLag, CameraLagSpeed, bEnableCameraRotationLag,
// CameraRotationLagSpeed, bUsePawnControlRotation, SocketOffset, TargetOffset.
// CRITICAL: bDoCollisionTest = false. With it true, the SpringArm probes the world and the
// Google 3D Tiles will constantly collide the boom, snapping the camera into the plane. Off = a
// clean fixed chase distance. (This is also crash-neutral: it's a component prop, not a tileset op.)
// Tuning: TargetArmLength 1500 (tight) … 3000 (cinematic). Z 600 looks over the fuselage.
// bUsePawnControlRotation:false → the boom follows the plane's body orientation (true chase).
// Set true ONLY if you want mouse to orbit the camera independently of the plane.
```

---

## Step 5 — add the chase Camera on the SpringArm and make it the view

```jsonc
// 5a. Add a CameraComponent attached to the SPRINGARM (not the root).
{ "toolset_name": "editor_toolset.toolsets.actor.ActorTools",
  "tool_name": "add_component",
  "arguments": {
    "owner": { "refPath": "<SPRINGARM_COMP>" },
    "component_type": { "refPath": "/Script/Engine.CameraComponent" },
    "name": "ChaseCam"
  } }
// → <CHASECAM_COMP>. owner = the spring arm so the camera rides the arm's far end.
```

```jsonc
// 5b. Belt-and-suspenders parent to the spring arm + activate it.
{ "toolset_name": "editor_toolset.toolsets.actor.ActorTools",
  "tool_name": "set_parent_component",
  "arguments": {
    "component": { "refPath": "<CHASECAM_COMP>" },
    "parent":    { "refPath": "<SPRINGARM_COMP>" }
  } }
```

```jsonc
// 5c. Camera props: a slightly wide FOV reads better for flight; auto-activate so it becomes the
//     view. bUsePawnControlRotation:false → camera inherits the boom (which follows the plane).
{ "toolset_name": "editor_toolset.toolsets.object.ObjectTools",
  "tool_name": "set_properties",
  "arguments": {
    "instance": { "refPath": "<CHASECAM_COMP>" },
    "values": "{ \"FieldOfView\": 95.0, \"bAutoActivate\": true, \"bUsePawnControlRotation\": false, \"RelativeLocation\": { \"X\": 0.0, \"Y\": 0.0, \"Z\": 0.0 }, \"RelativeRotation\": { \"Pitch\": 0.0, \"Yaw\": 0.0, \"Roll\": 0.0 } }"
  } }
// VERIFY: list_properties on <CHASECAM_COMP> for FieldOfView, bAutoActivate, bUsePawnControlRotation.
```

### Making the chase cam the ACTIVE view in PIE — the real gotcha (VERIFY)
UE picks a pawn's view camera by: (1) if the pawn implements `CalcCamera`/has an active
`UCameraComponent`, that camera is used; a possessed pawn with a `UCameraComponent` flagged
`bAutoActivate`/active will be the view via `APawn::CalcCamera` → `UCameraComponent::GetCameraView`.
DynamicPawn (GlobeAwareDefaultPawn) may already provide its own camera/view. Two ways to ensure
OURS wins, in order of preference:

1. **Deactivate the pawn's existing camera** (from Step 2d `<DEFAULT_CAM>`), so ours is the only
   active CameraComponent:
   ```jsonc
   { "toolset_name": "editor_toolset.toolsets.object.ObjectTools",
     "tool_name": "set_properties",
     "arguments": { "instance": { "refPath": "<DEFAULT_CAM>" },
       "values": "{ \"bAutoActivate\": false, \"bIsActive\": false }" } }
   ```
   (VERIFY the active-flag property name with list_properties on `<DEFAULT_CAM>` — it's commonly
   `bIsActive` with setter Activate/Deactivate; we can only set the bool over MCP, which is
   usually enough at BeginPlay since bAutoActivate drives initial state.)

2. If GlobeAwareDefaultPawn overrides `CalcCamera` in C++ (ignores CameraComponents entirely),
   a component camera can't override it via property-set alone — there is **no MCP call to invoke
   `CalcCamera`/SetViewTarget**. In that case the chase view must come from a Blueprint child of
   DynamicPawn (set its View Target / use a CameraComponent the BP exposes) — which is asset
   authoring we generally avoid. **Mitigation that needs no Blueprint:** the plane mesh is still
   attached and visible; you'd be flying first-person *inside* a visible plane rather than true
   chase. That's the degraded-but-working state. **Flag this and test #1 first** — most pawns,
   including the default flying pawns, honor an active CameraComponent.

> Bottom line: **do Step 2d + 5d-#1, then verify with a CaptureViewport during PIE (Step 7).**
> If the view is third-person behind the plane → success. If it's still first-person → you've hit
> the CalcCamera-override case; report it and fall back (visible-plane first-person, or Option 2
> with a Blueprint pawn the user authors once).

---

## Step 6 — (do NOT change GameMode/origin) confirm flight setup from flight-pawn-setup.md

The GameMode = FloatingGameMode (DefaultPawn = DynamicPawn) and georeference origin are already
handled in `flight-pawn-setup.md`. **Do not re-set GameModeOverride or any Origin* property here**
(origin re-set triggers a Cesium rebase — see cesium-rebase-solution.md). We only added components.

---

## Step 7 — START PIE and verify the chase view

```jsonc
{ "toolset_name": "EditorToolset.EditorAppToolset", "tool_name": "StartPIE",
  "arguments": {
    "options": {
      "bSimulate": false,
      "playMode": "PlayMode_InViewPort",
      "startTransform": {
        "location": { "x": 0.0, "y": -15000.0, "z": 30000.0 },
        "rotation": { "pitch": -10.0, "yaw": 90.0, "roll": 0.0 },
        "scale":    { "x": 1.0, "y": 1.0, "z": 1.0 }
      },
      "warmupSeconds": 4.0
    }
  } }
```
Then:
```jsonc
{ "toolset_name": "EditorToolset.EditorAppToolset", "tool_name": "IsPIERunning", "arguments": {} } // true
{ "toolset_name": "EditorToolset.EditorAppToolset", "tool_name": "CaptureViewport",
  "arguments": { "bShowUI": true } }
```
Read the capture:
- **Plane visible, camera behind+above it, skyline ahead → SUCCESS.** Hand control to the user.
- **Plane visible but you're inside it (first-person) →** CalcCamera-override case (Step 5d #2).
- **Plane flying sideways/belly-first →** fix `PlaneMesh.RelativeRotation` Yaw/Pitch (Step 3c),
  `StopPIE`, re-Start. (Component edits made during PIE may not persist — prefer editing in the
  editor world, then StartPIE again.)
- **No plane at all →** `StaticMesh` didn't bind: re-check `<PLANE_SM_REFPATH>` and that Step 3c
  returned true; confirm the import produced an asset (CaptureAssetImage on `<PLANE_SM_REFPATH>`).

> IMPORTANT: component changes via `add_component`/`set_properties` should be made to the **editor
> (non-PIE) world actor**, BEFORE StartPIE, so PIE clones them into the play world. If you add
> components while PIE is running, they live only on the PIE actor and vanish on StopPIE. Build
> everything in Steps 1–5 with PIE stopped; only Step 7 starts play.

Exit:
```jsonc
{ "toolset_name": "EditorToolset.EditorAppToolset", "tool_name": "StopPIE", "arguments": {} }
```

---

## Controls the user gets (unchanged from DynamicPawn / GlobeAwareDefaultPawn)
W/S forward-back · A/D strafe · E/Q (or Space/C) up-down · mouse look · scroll/Shift speed.
Click once inside the play viewport to grab focus. F8 ejects. Esc exits. The only difference vs
`flight-pawn-setup.md` is the user now sees the plane body and a chase camera frames it.

---

## Crash-safety — REAFFIRMED (same hard rules as flight-pawn-setup.md)
- [ ] Gaussian-splat subsystem **patch stays in place** (the crash we already fixed; PIE re-runs
      BeginPlay so the patch must be live). See `cesium-splat-subsystem-disable.md`.
- [ ] **Ray tracing OFF** — do not touch `r.RayTracing*`. Adding mesh/camera components does not
      enable RT.
- [ ] **No `FocusOnActors`** on the Cesium3DTileset (or any actor during PIE — it errors in PIE
      anyway). We use `CaptureViewport` to inspect, never FocusOnActors.
- [ ] **No CesiumSunSky**, no lighting-actor changes.
- [ ] **CesiumGeoreference origin untouched** (lat 40.758 / lon -73.9855 / h 150) — we set NO
      Origin* property. BeginPlay rebases on its own.
- [ ] **SpringArm `bDoCollisionTest:false`** — prevents the camera boom probing the streaming
      tiles. (Also just looks better.)
- [ ] We only touch: the new PlaneMesh / SpringArm / ChaseCam components on the DynamicPawn, and
      the import of one StaticMesh asset. We do NOT modify the tileset, georeference, GameMode,
      materials, or any lighting actor.
- [ ] `StartPIE` uses `PlayMode_InViewPort` (in-process) with `bSimulate:false` (full PIE).

NO-GO: editor mid-cook/build, another agent editing the level, or `IsPIERunning` already true.

---

## If Option 1 fails (add_component doesn't persist to PIE, or CalcCamera override blocks the view)

**Option 2 — new Pawn actor, components added, but NO custom movement over MCP.** You can:
`SceneTools.add_to_scene_from_class` with `actor_type` = `/Script/Engine.DefaultPawn`
(`search_subclasses` of `/Script/Engine.Pawn` to get the exact class refPath), then run Steps 3–5
against THAT actor's root, set `AutoPossessPlayer` via `ObjectTools.set_properties`
(`"{ \"AutoPossessPlayer\": \"Player0\" }"` — VERIFY the enum string with list_properties), and
disable the level's DynamicPawn auto-possess so only one pawn possesses Player0.
- `DefaultPawn` flies (UFloatingPawnMovement, no gravity) and accepts a CameraComponent as its
  view, so the **chase cam works**. The trade-off vs Option 1: DefaultPawn is **not globe-aware**
  (no Cesium altitude/curvature scaling) — fine over a single Manhattan tile, slightly worse feel
  on long traverses. This is the cleanest all-MCP path to a *true third-person flying plane* if
  DynamicPawn's camera can't be overridden.
- A truly custom Pawn (bespoke flight feel + guaranteed chase view) needs a **Blueprint asset** —
  which `programmatic-toolset-capabilities.md` shows we **cannot author/compile over this MCP**
  (no graph-compile, no UFUNCTION calls). If the user wants that, they author a `BP_PlanePawn`
  (Pawn → add StaticMesh+SpringArm+Camera in the BP editor, FloatingPawnMovement, set Default
  Pawn Class) ONCE in the editor; after that we just place/possess it via MCP. Recommend Option 1
  first, Option 2 (DefaultPawn) as the no-Blueprint fallback, BP only if they want a bespoke pawn.
```
