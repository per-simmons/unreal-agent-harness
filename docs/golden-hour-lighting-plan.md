# Golden-Hour Lighting Plan — Cesium P3DT Manhattan (UE 5.8)

Cinematic golden-hour lighting for the `NYCFklyover2` level showing Google Photorealistic
3D Tiles of Manhattan. This is a **prescription only** — an ordered, crash-safe list of
Unreal MCP calls. The editor is LIVE; nothing here was applied. Apply in order, one at a
time, reading the result of each before the next.

Engine: UE 5.8. Ray tracing OFF (`r.RayTracing=0`) and stays off. Cesium gaussian-splat
subsystem patched off. Photoreal tiles are lit by the level DirectionalLight + Sky only.

---

## 0. Ground truth captured from the LIVE scene (read-only)

Level: `/Game/NYC/NYCFklyover2.NYCFklyover2`. Actor refPaths (use verbatim):

| Role | refPath |
|------|---------|
| DirectionalLight (actor) | `/Game/NYC/NYCFklyover2.NYCFklyover2:PersistentLevel.DirectionalLight_UAID_A85E45CFE40401D200_1470382761` |
| → its light component | `…DirectionalLight_UAID_A85E45CFE40401D200_1470382761.LightComponent0` |
| SkyLight component | `…SkyLight_UAID_A85E45CFE40401D200_1470380759.SkyLightComponent0` |
| SkyAtmosphere component | `…SkyAtmosphere_UAID_A85E45CFE40401D200_1470382762.SkyAtmosphereComponent` |
| VolumetricCloud (actor) | `…VolumetricCloud_UAID_A85E45CFE40401D200_1470381760` |
| Cesium3DTileset (actor) | `…Cesium3DTileset_UAID_1C1DD3EDD7A148E602_1701752048` |
| CesiumGeoreference | `…CesiumGeoreference_UAID_1C1DD3EDD7A148E602_1701753049` |

**Current values read from the live actors:**

- DirectionalLight component: `Intensity=6`, `LightColor=(1,1,1)`, `Temperature=6500`,
  `bUseTemperature=true`, `Mobility=Movable`, `DynamicShadowDistanceMovableLight=20000`,
  `DynamicShadowCascades=4`, `LightSourceAngle=0.7357`, `bAtmosphereSunLight=true`,
  `AtmosphereSunLightIndex=0`, `bCastCloudShadows=false`.
  - **Intensity=6 means this light is on the legacy/normalized lighting-units path, NOT
    physical lux** (a physical sun would be ~75,000–120,000 lx). Treat intensity as a
    relative dial in the single digits, not lux. Do not jump to 100000 — that would blow
    the scene to pure white. (See the intensity note in step 2.)
- DirectionalLight actor rotation: `pitch=-16.29, yaw=43.73, roll=112.36`.
  - Roll 112 is just how the OpenWorld template authored the actor's basis; what matters
    for sun height is the **resulting world light DIRECTION**, which we set explicitly with
    a clean rotator below (roll 0).
- SkyLight: `Intensity=1`, `Mobility=Movable`, `SourceType=SLS_CapturedScene`,
  `bRealTimeCapture=true`, `bLowerHemisphereIsBlack=true`, `CastShadows=true`.
  - Real-time capture = the sky light re-captures the SkyAtmosphere automatically, so when
    we drop the sun low the ambient fill warms and dims on its own. Good — leave capture on.

---

## 1. Approach decision — use the PLAIN UE RIG, do NOT add CesiumSunSky

**Recommendation: tune the existing DirectionalLight + SkyAtmosphere + SkyLight. Do NOT add
`ACesiumSunSky`.** Reasons, in order of importance:

1. **CesiumSunSky's sun is driven by UFUNCTIONs we cannot call over MCP.** Confirmed in the
   source: `Source/CesiumRuntime/Public/CesiumSunSky.h` — every time-of-day property
   (`SolarTime`, `Day`, `Month`, `TimeZone`, `NorthOffset`, `Latitude`, …) carries the
   doc comment *"After changing this value from Blueprints or C++, you must call
   UpdateSun."* `UpdateSun()` is a `UFUNCTION` (line 441). The Unreal MCP `ObjectTools`
   surface is **property get/set only — it cannot invoke a UFUNCTION** (verified in
   `programmatic-toolset-capabilities.md`: no registered tool calls a method; the sandbox
   has no `unreal` module). So setting CesiumSunSky's solar time over MCP would change the
   number but never move the sun. Dead end.
2. **Two atmospheres fight.** CesiumSunSky spawns/【drives its own SkyAtmosphere + sky sphere;
   with the template's existing `SkyAtmosphere` present you get double atmosphere / double
   sun unless you reconcile them — exactly the kind of fiddly state that risks the live
   editor.
3. **Simplicity + safety.** The plain rig reaches golden hour with **pure property sets and
   one transform set** — all of which take effect immediately with no UFUNCTION, no tick,
   no new ticking subsystem. The whole reason the scene is stable right now is that we
   stripped ticking/■crashy actors; adding CesiumSunSky reintroduces an actor that wants to
   re-run sun/atmosphere updates.

**Net:** aim the existing DirectionalLight to a low golden-hour angle, warm it via color
temperature, and pin exposure with a PostProcessVolume. CesiumSunSky buys nothing here and
costs controllability + stability.

---

## 2. DirectionalLight — angle, warmth, intensity, shadows

Golden hour = sun **~6°–10° above the horizon**. In UE a directional light's **pitch is the
downward angle of the light direction**; a sun 8° above the horizon casts light angled 8°
DOWNWARD, i.e. **pitch ≈ -8°** (negative = pointing down toward the ground). We set a clean
world rotator (roll 0) and choose yaw so the warm light rakes across the Manhattan avenues.

### 2a. Aim the sun (low golden-hour angle) — via ActorTools.set_actor_transform

Rotation is on the **actor**, not the component. Use `ActorTools.set_actor_transform` with
`worldspace:true` and ONLY the rotation field (location/scale omitted = "don't change").

```
toolset: editor_toolset.toolsets.actor.ActorTools
tool:    set_actor_transform
arguments:
{
  "actor": { "refPath": "/Game/NYC/NYCFklyover2.NYCFklyover2:PersistentLevel.DirectionalLight_UAID_A85E45CFE40401D200_1470382761" },
  "xform": { "rotation": { "pitch": -8.0, "yaw": -55.0, "roll": 0.0 } },
  "worldspace": true
}
```

- `pitch=-8.0` → sun ~8° above horizon (golden hour). Tune in the **-6 to -12** band: -6 is
  a deeper, redder near-sunset; -12 is brighter "late afternoon gold." -8 is the safe hero.
- `yaw=-55.0` → light comes from roughly the SW/W, raking long shadows down the avenues
  toward the camera. Adjust yaw to taste after you see the first capture; yaw is purely
  aesthetic and costs nothing to re-set.
- `roll=0.0` → clears the template's odd 112° roll so pitch/yaw mean what they say.

### 2b. Warm the sun color (temperature) — via ObjectTools.set_properties on the COMPONENT

`bUseTemperature` is already true. Golden hour ≈ **3600–4300 K**. Lower = more orange.

```
toolset: editor_toolset.toolsets.object.ObjectTools
tool:    set_properties
arguments:
{
  "instance": { "refPath": "/Game/NYC/NYCFklyover2.NYCFklyover2:PersistentLevel.DirectionalLight_UAID_A85E45CFE40401D200_1470382761.LightComponent0" },
  "properties": {
    "Temperature": 4000,
    "bUseTemperature": true,
    "LightColor": { "r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0 }
  }
}
```

- Keep `LightColor` white (1,1,1) and let **Temperature** do the warming — that's the clean,
  physically meaningful knob. (If you want extra punch later, you can tint LightColor toward
  warm, but don't double-warm hard or P3DT albedo goes sickly orange.)
- 4000 K is the hero. Push to 3700 for a redder, deeper-sunset read; 4300 for subtler gold.

### 2c. Intensity — nudge, don't blast

Current `Intensity=6` on the legacy units path. At a low sun angle the atmosphere already
reddens/dims the disk, so you usually want to **hold or slightly raise** the raw intensity
and control final brightness with exposure (step 4), NOT by cranking the light.

```
toolset: editor_toolset.toolsets.object.ObjectTools
tool:    set_properties
arguments:
{
  "instance": { "refPath": "/Game/NYC/NYCFklyover2.NYCFklyover2:PersistentLevel.DirectionalLight_UAID_A85E45CFE40401D200_1470382761.LightComponent0" },
  "properties": { "Intensity": 8.0 }
}
```

- Start at **8.0** (a small bump from 6). If the lit faces of buildings read flat, go to 10.
- **Do NOT set lux-scale values (50000+) here** — this light is not on the physical-lux path
  (proven by the existing value of 6). A huge number will clip everything to white.
- If after step 4 the scene is still too dark/too bright, prefer changing **exposure
  compensation** (step 4) over chasing intensity — exposure is the single global dial.

### 2d. Shadows (optional polish, safe)

Long low-angle shadows are the signature of golden hour. The movable-light cascade settings
are already reasonable (`DynamicShadowDistanceMovableLight=20000`, `DynamicShadowCascades=4`).
For a city flyover you can extend shadow distance so distant blocks still cast:

```
toolset: editor_toolset.toolsets.object.ObjectTools
tool:    set_properties
arguments:
{
  "instance": { "refPath": "/Game/NYC/NYCFklyover2.NYCFklyover2:PersistentLevel.DirectionalLight_UAID_A85E45CFE40401D200_1470382761.LightComponent0" },
  "properties": {
    "DynamicShadowDistanceMovableLight": 50000.0,
    "DynamicShadowCascades": 4,
    "bAtmosphereSunLight": true
  }
}
```

- `bAtmosphereSunLight=true` (already set) is what makes THIS light drive the SkyAtmosphere
  disk/scatter — keep it true so the atmosphere reddens with the low sun automatically.
- This step is optional; skip if you want fewer changes. Larger shadow distance = a little
  more GPU but no stability risk.

---

## 3. Sky / atmosphere + clouds

### 3a. SkyAtmosphere — leave at defaults, let the sun angle do the work

**Recommended: do NOT touch SkyAtmosphere scatter values.** With `bAtmosphereSunLight=true`
on the directional light and a low sun pitch, the SkyAtmosphere physically reddens the
horizon and warms the disk on its own — that's the correct, robust way to get the warm
horizon. Hand-tuning Rayleigh/Mie is unnecessary and easy to overcook.

If (and only if) you want a stronger haze/glow band on the horizon after seeing a capture,
the safe single knob is Mie (aerosol) scattering — a property set on the component:

```
toolset: editor_toolset.toolsets.object.ObjectTools
tool:    set_properties
arguments:
{
  "instance": { "refPath": "/Game/NYC/NYCFklyover2.NYCFklyover2:PersistentLevel.SkyAtmosphere_UAID_A85E45CFE40401D200_1470382762.SkyAtmosphereComponent" },
  "properties": { "MieScatteringScale": 0.004, "AerialPerspectiveViewDistanceScale": 1.5 }
}
```

- Default `MieScatteringScale` is ~0.003; nudging to 0.004 thickens the warm horizon haze.
- `AerialPerspectiveViewDistanceScale` 1.5 adds distance haze over the far skyline (very
  golden-hour). Optional. **Verify exact property names with `ObjectTools.list_properties`
  on the component before setting** — Mie/Rayleigh field names vary by version.

### 3b. SkyLight — keep real-time capture ON

No change needed. `bRealTimeCapture=true` means the SkyLight re-captures the warmed sky and
provides warm ambient fill automatically. Leaving `Intensity=1` is correct. (If shadows read
too black/blue, raise SkyLight `Intensity` to 1.5 for a touch more fill — optional.)

### 3c. VolumetricCloud — KEEP it (it sells golden hour), but it's optional

**Keep the VolumetricCloud.** Low sun under-lighting cloud bottoms with warm light is one of
the most convincing golden-hour cues, and the cloud is a static scene actor — it does not
introduce the ticking/■crash class we removed. No property change required.

- If you want the sun to actually warm the clouds, set `bCastCloudShadows`/cloud interaction
  on the directional light later, but the default cloud already catches the warm sun color.
- Only drop the cloud if you specifically want a clean clear-sky skyline; if so, delete via
  `SceneTools.remove_from_scene` on the VolumetricCloud actor (safe — it's an ordinary
  actor, not the tileset). Prefer keeping it.

---

## 4. Exposure — pin it MANUAL with a PostProcessVolume (this is the make-or-break step)

The viewport's **auto-exposure (eye adaptation) will wash golden hour out** — it brightens
the dim low-sun scene back toward mid-grey, killing the mood. There is **no "set console
variable" tool** in this MCP build (`EditorAppToolset` only has `SearchCVars`, read-only),
so we cannot `r.DefaultFeature.AutoExposure 0` from here. The correct, fully-MCP-doable fix
is an **unbound PostProcessVolume with Manual exposure**.

### 4a. Add a PostProcessVolume actor

```
toolset: editor_toolset.toolsets.scene.SceneTools
tool:    add_to_scene_from_class
arguments:
{
  "actor_type": { "refPath": "/Script/Engine.PostProcessVolume" },
  "name": "PP_GoldenHour",
  "xform": { "location": { "x": 0, "y": 0, "z": 0 } }
}
```

- Capture the returned actor refPath (call it `<PP>` below). Location is irrelevant once we
  set it unbound.

### 4b. Make it global (unbound) and set manual exposure

Exposure lives in the volume's nested `Settings` (FPostProcessSettings) struct. Each setting
has a `bOverride_*` boolean that must be true for the value to apply. Set on the **actor**:

```
toolset: editor_toolset.toolsets.object.ObjectTools
tool:    set_properties
arguments:
{
  "instance": { "refPath": "<PP>" },
  "properties": {
    "bUnbound": true,
    "Priority": 1000000.0,
    "Settings": {
      "bOverride_AutoExposureMethod": true,
      "AutoExposureMethod": "AEM_Manual",
      "bOverride_AutoExposureBias": true,
      "AutoExposureBias": 11.0,
      "bOverride_AutoExposureApplyPhysicalCameraExposure": true,
      "AutoExposureApplyPhysicalCameraExposure": false
    }
  }
}
```

- `bUnbound=true` + very high `Priority` → this volume affects the whole level regardless of
  camera position (essential for a flyover).
- `AutoExposureMethod=AEM_Manual` kills eye-adaptation. With Manual, brightness is driven by
  `AutoExposureBias` (which Manual treats as the **fixed EV100 / exposure compensation**).
- `AutoExposureBias=11.0` is the starting EV for an outdoor daylight-ish scene on the legacy
  intensity path. **This is the dial you tune for overall brightness** — raise it (12–13) if
  the scene is too dark, lower it (9–10) if blown out. Adjust this BEFORE touching light
  intensity.
- `AutoExposureApplyPhysicalCameraExposure=false` so a camera's physical exposure doesn't
  re-darken it.

> **IMPORTANT — verify field names first.** Before 4b, run
> `ObjectTools.list_properties` on `<PP>` and on its `Settings` struct to confirm the exact
> spellings (`AutoExposureMethod`, `AutoExposureBias`, the `bOverride_*` flags). They are
> stable across 5.x but confirm rather than assume. `AEM_Manual` is the enum value for the
> method.

### 4c. (Alternative, if a struct-valued set_properties is rejected)

If the nested-struct `Settings` payload doesn't take, fall back to driving brightness purely
through **SkyLight + DirectionalLight intensities** (steps 2c/3b) and accept auto-exposure —
but Manual exposure via the PPV is strongly preferred for a consistent cinematic look across
the flyover. Do not try to disable auto-exposure via console (no cvar-set tool exists here).

---

## 5. Recommended apply ORDER (one at a time, capture between)

1. **2a** — aim the sun (`set_actor_transform`, pitch -8 / yaw -55 / roll 0).
2. **2b** — warm the sun (`Temperature 4000`).
3. **4a + 4b** — add `PP_GoldenHour`, set `bUnbound`, `AEM_Manual`, `AutoExposureBias 11`.
   *(Do exposure early — without it, captures lie because auto-exposure rebalances.)*
4. Capture the viewport (`EditorAppToolset.CaptureViewport`, default args, NO annotations)
   and look. Tune **`AutoExposureBias`** first for overall brightness.
5. **2c** — bump `Intensity` to 8 only if lit faces read flat after exposure is right.
6. **2d / 3a / 3b / 3c** — optional polish (shadow distance, Mie haze, sky fill, clouds),
   each followed by a capture.

After each change, prefer a fresh `CaptureViewport` over guessing.

---

## 6. CRASH-SAFETY — explicit do / don't

**SAFE (property/transform sets — take effect immediately, no UFUNCTION, no tick):**
- `ActorTools.set_actor_transform` on the **DirectionalLight** to rotate the sun. ✅
- `ObjectTools.set_properties` on the **DirectionalLightComponent** (Temperature, Intensity,
  LightColor, shadow distance/cascades, bAtmosphereSunLight). ✅
- `ObjectTools.set_properties` on the **SkyLightComponent** (Intensity). ✅
- `ObjectTools.set_properties` on the **SkyAtmosphereComponent** (Mie/aerial scale) — after
  confirming names with `list_properties`. ✅
- `SceneTools.add_to_scene_from_class` of a **PostProcessVolume** + `set_properties` for
  Manual exposure. ✅ (PPV is an ordinary, non-ticking actor.)
- `EditorAppToolset.CaptureViewport` to review. ✅ (NOTE: pass NO/■minimal annotations; it's
  read-only rendering.)

**DO NOT:**
- ❌ **Never `EditorAppToolset.FocusOnActors` on the Cesium3DTileset** (or any Cesium actor).
  Focusing frames the actor's bounds; a streaming P3DT tileset's bounds/■focus path has been
  the crash trigger. If you must move the camera, use `SetCameraTransform` with explicit
  coordinates, never FocusOnActors on the tileset.
- ❌ **Do not re-enable ray tracing** (no `r.RayTracing 1`, no Lumen/RT reflection toggles).
  There is no cvar-set tool here anyway, but do not author any RT-on change.
- ❌ **Do not add `ACesiumSunSky`** (re-introduces a sun/atmosphere updater + second
  atmosphere; and its sun can't be driven over MCP — see §1).
- ❌ **Do not add anything that ticks** — no Niagara/■splat actors, no
  `CesiumGaussianSplatSystemActor`. The splat subsystem is patched off; don't spawn anything
  that would re-touch it.
- ❌ **Do not call any UFUNCTION-style operation** (there's no MCP path to it, and on Cesium
  actors the rebase/■refresh UFUNCTIONs are the risky ones). Stick to property + transform.
- ❌ **Do not set DirectionalLight Intensity to physical-lux magnitudes** (50000+). This
  light is on the legacy units path (current value 6); a huge value clips to white. Control
  brightness with `AutoExposureBias`.
- ❌ **Do not `FocusOnActors` / select-then-focus** as a convenience — same tileset risk.

**If anything looks wrong after a set:** re-`get_properties` to confirm the value landed,
re-`CaptureViewport`, and adjust the single relevant dial. Never batch many speculative
changes before looking.

---

## 7. One-glance dial summary

| Want | Change | On |
|------|--------|----|
| Lower / redder sun | `pitch` -6 (deeper) … -12 (higher) | DirectionalLight actor rotation |
| Warmer light | `Temperature` 3700 (warm) … 4300 (subtle) | DirectionalLightComponent |
| Overall brightness | `AutoExposureBias` 9 (darker) … 13 (brighter) | PP_GoldenHour Settings |
| Punchier lit faces | `Intensity` 6 → 8 → 10 | DirectionalLightComponent |
| Thicker horizon haze | `MieScatteringScale` ~0.004, `AerialPerspectiveViewDistanceScale` 1.5 | SkyAtmosphereComponent |
| More shadow fill | SkyLight `Intensity` 1 → 1.5 | SkyLightComponent |
| Longer shadows reach | `DynamicShadowDistanceMovableLight` 20000 → 50000 | DirectionalLightComponent |

Hero starting point: **pitch -8, yaw -55, roll 0; Temperature 4000; Intensity 8;
AutoExposureBias 11 (Manual); keep cloud + real-time SkyLight.**
