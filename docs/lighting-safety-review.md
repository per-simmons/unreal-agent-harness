# Lighting Change Safety Review — UE 5.8 LIVE editor + Cesium Photorealistic 3D Tiles

Scope: adjust scene lighting via Unreal MCP `ObjectTools.set_properties` on a
DirectionalLight / SkyAtmosphere / SkyLight, possibly add a `PostProcessVolume`, in a
LIVE editor we must not crash. Analysis only — nothing touched.

Verdict up front: **GO** for `set_properties` on existing editor-world lights and a
`PostProcessVolume`. **NO-GO** for adding a `CesiumSunSky` actor, and avoid a handful of
specific properties listed below. Rationale and the GO/NO-GO checklist follow.

---

## 1. `set_properties` on lights / PostProcessVolume — crash-safe? YES, with carve-outs

`ObjectTools.set_properties` sets `UPROPERTY`s via reflection, then UE marks the render
state dirty for that component. None of the splat crash paths (a–d in the brief) are
reachable from this:

- The four mitigated crashes live in **`UCesiumGaussianSplatSubsystem::Tick`**,
  `ACesium3DTileset::OnFocusEditorViewportOnThis`/`getRootTile`, the RT geometry path,
  and `bRemoteExecution` boot. Setting `Intensity`/`LightColor`/rotation/exposure on a
  `UDirectionalLightComponent`, `USkyLightComponent`, `USkyAtmosphereComponent`, or
  `APostProcessVolume` does **not** call into the Cesium splat subsystem, into
  `Cesium3DTileset`, or into any tickable Cesium object. They are plain engine actors;
  the tileset keeps streaming independently.
- The splat subsystem ticks unconditionally regardless of what else you do (that's why
  it was patched off). Confirm the patch is still live before this work (see §5) — but a
  lighting edit neither re-enables it nor feeds it stale objects.

**Generally safe to set** (Movable lights, reflection-only marks dirty, no rebuild):
- DirectionalLight: `Intensity`, `LightColor`, `Temperature`, `bUseTemperature`,
  `relative/world Rotation`, `LightSourceAngle`, `bAtmosphereSunLight` (it is the
  atmosphere sun — leave it true).
- SkyLight: `Intensity`, `LightColor`, `SourceType`, cubemap angle. (See the
  `bRealTimeCapture` carve-out below.)
- SkyAtmosphere: `Rayleigh/Mie` scattering, `MultiScatteringFactor`, density — these
  just mark render state dirty.
- PostProcessVolume settings: `ExposureMethod`, `ExposureCompensation`, manual
  `ExposureMinEV100/MaxEV100`, `bUnbound`, `BlendWeight`, color grading (saturation /
  contrast / gain / gamma), bloom, vignette.

**Do NOT set via reflection on the live editor (heavy rebuild / RT / known-hazard):**
- `LightingChannels`, `Mobility` — changing mobility on a live light forces a render-
  resource recreate; leave lights Movable as-is, don't flip Static/Stationary.
- **Anything ray-tracing / Lumen-hardware:** `CastRaytracedShadow`,
  `RayTracingGroupId`, PPV `ReflectionMethod = RayTraced`,
  `GlobalIllumination = RayTraced`, `Lumen*HardwareRayTracing`. RT is forced off and
  must stay off (crash c). Use **screen-space / Lumen-software** reflections + GI only.
- `bRealTimeCapture` on a SkyLight — toggling it kicks a real-time sky capture that
  re-renders the scene each frame against the streaming Cesium tiles; expensive and a
  stutter/hitch risk on a live editor. If you need sky light to match new atmosphere,
  prefer leaving the existing capture mode and adjusting `Intensity`, or do a one-shot
  recapture deliberately rather than enabling continuous capture.
- Reimport/rebuild triggers in general (`RecreatePhysicsState`, texture reimport, etc.)
  — none are needed for lighting; don't touch them.

---

## 2. Adding actors via `add_to_scene_from_class`

### PostProcessVolume — SAFE
`APostProcessVolume` has no tick of concern and spawns no subsystem. It's the
recommended way to drive exposure/tone-mapping. Spawn it, set `bUnbound = true` (or scale
its box to enclose the camera), then `set_properties` for exposure/color. No Cesium
interaction.

### CesiumSunSky — NO-GO (do not add it)
Read `CesiumRuntime/Private/CesiumSunSky.cpp`. It is materially riskier than a plain
light on a live editor streaming Photorealistic 3D Tiles:

- `PrimaryActorTick.bCanEverTick = true` **and** `ShouldTickIfViewportsOnly()` returns
  `true` — so it **ticks in the normal editor**, not just PIE. Every editor frame
  `Tick()` reads/sets SkyAtmosphere height/scattering, and if `UpdateAtmosphereAtRuntime`
  is on, `UpdateAtmosphereRadius()` runs — which calls `getViewLocation()` (grabs the
  active editor viewport / player pawn) and does georeference math against the ellipsoid
  every frame. That is a live per-frame path coupled to the georeference and the
  viewport, exactly the class of "tick coupled to Cesium state + editor world" that the
  splat subsystem crash came from.
- Its constructor bakes in the things we explicitly avoid: the SkyLight is created with
  **`bRealTimeCapture = true`** and **`CastRaytracedShadow = ECastRayTracedShadow::Enabled`**
  (the RT path we force off, crash c). Spawning CesiumSunSky therefore reintroduces an
  RT-shadow sky light and a continuous real-time capture against the streaming tiles by
  default.
- It spawns sub-actors (`_spawnSkySphere` on mobile; a GlobeAnchor that snaps to Earth
  center) and subscribes to `RootComponent->TransformUpdated`. More spawn/teardown
  surface on a live editor than we want.

If atmospheric look is required, get it from a **plain `SkyAtmosphere` + `DirectionalLight`
+ `SkyLight`** you already have (or add a vanilla `SkyAtmosphere`/`PostProcessVolume`),
adjusted via `set_properties`. Don't add `CesiumSunSky`.

---

## 3. Inside Simulate/PIE vs normal editor — do it in the NORMAL editor

Do the lighting change **outside Simulate, in the normal editor world.** Reasons:

- The mitigated splat crash (`UObjectArray.h:1083`) and the stale-world re-init are
  aggravated specifically by **PIE start/stop and editor↔game world swaps** (per the
  splat-subsystem doc). Staying out of PIE avoids that whole class of teardown.
- `set_properties` on editor-world actors persists into the level and is what you want to
  save. Properties set on PIE-world clones evaporate on Stop.
- The patched splat subsystem is inert either way, but normal editor = fewer world swaps
  = strictly safer.

**Save after:** `AssetTools.save_assets` (saving the dirtied level/lighting) is safe — it
serializes actor properties; it does not invoke the splat subsystem, doesn't touch the
tileset's runtime state, and doesn't trigger RT or FocusOnActors. Save once at the end,
in the normal editor, after edits are verified.

---

## 4. QA without crashing

- QA with **`Viewport.capture_viewport`** (screenshot the current view), never
  `FocusOnActors` / focus-on-this on any actor — focusing a `Cesium3DTileset` hits the
  `getRootTile` null-deref (crash b). If you must reframe, move the camera by setting the
  viewport/camera transform, not by focusing a Cesium actor.
- Don't select the tileset and frame-select (F) it either — same code path.

---

## 5. GO / NO-GO checklist (apply in this order)

GO — do:
1. Confirm the splat-subsystem patch is still live (`GetTickableTickType()` →
   `Never`, no `CesiumGaussianSplatSystemActor` in the level) and `ue_crashlog.sh` is
   clean before starting. Confirm `bRemoteExecution` is still false.
2. Work in the **normal editor**, NOT Simulate/PIE. Do not start PIE during this task.
3. `set_properties` only on existing **editor-world** actors:
   DirectionalLight (rotation, `Intensity`, `LightColor`, `Temperature`,
   `bUseTemperature`), SkyAtmosphere (scattering), SkyLight (`Intensity`/color), and a
   `PostProcessVolume` (exposure method/comp, color grading, bloom, vignette).
4. If you need a PPV, `add_to_scene_from_class` `PostProcessVolume`, set `bUnbound=true`,
   then set its properties. (PPV spawn is safe.)
5. QA via `Viewport.capture_viewport` after each change.
6. Save once at the end with `AssetTools.save_assets`.

NO-GO — never:
- Do **not** add a `CesiumSunSky` actor (ticks in-editor against the georeference +
  defaults to RT shadows + real-time capture). Use plain SkyAtmosphere/SkyLight instead.
- Do **not** set any ray-tracing / hardware-Lumen property (`CastRaytracedShadow`, RT
  reflections/GI). Keep reflections+GI on screen-space / Lumen-software.
- Do **not** toggle a SkyLight's `bRealTimeCapture` on, or change any light's `Mobility`.
- Do **not** `FocusOnActors` / frame-select any Cesium tileset (crash b). QA via capture.
- Do **not** enter PIE/Simulate for this change (avoids the splat/world-swap crash
  class).
- Do **not** re-enable `bRemoteExecution` or anything that forces a reimport/rebuild.

---

## File references
- `cesium-build/cesium-unreal/Source/CesiumRuntime/Private/CesiumSunSky.cpp:46` —
  ctor: `bCanEverTick=true`, SkyLight `bRealTimeCapture=true`,
  `CastRaytracedShadow=Enabled`.
- `…/CesiumSunSky.cpp:257` — `Tick` (per-frame SkyAtmosphere updates).
- `…/CesiumSunSky.cpp:315` — `ShouldTickIfViewportsOnly() return true` (ticks in editor).
- `…/CesiumSunSky.cpp:499` — `UpdateAtmosphereRadius` (per-frame viewport+georeference math).
- `unreal-agent-harness/docs/cesium-splat-subsystem-disable.md` — splat Tick crash +
  patch (must stay live).
