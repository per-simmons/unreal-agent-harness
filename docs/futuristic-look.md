# Futuristic Look — Windowed-Glass Skyscrapers + Dusk Lighting (UE 5.8)

Make the 12 procedural tower meshes in `/Game/futuristiccity` read as **lit glass
skyscrapers with window grids** (not gray geometric shapes), and light the scene for a
**Dubai-at-dusk** mood where the emissive windows glow.

This is a **prescription only** — an ordered, paste-ready list of Unreal MCP calls. The
editor is LIVE; nothing here has been applied. Apply in order; read the result of each call
before the next (especially the verification get_properties calls).

Engine: UE 5.8. Lumen + Substrate available, ray tracing OFF — leave it off. The window
look is driven entirely by an **emissive material grid**, so it does not depend on RT.

---

## 0. Hard facts verified against THIS MCP build (read before trusting the brief)

These were confirmed by `describe_toolset` on the live server and by the proven idioms in
`golden-hour-lighting-plan.md` / `programmatic-toolset-capabilities.md`. They override a few
assumptions in the original brief:

1. **There IS a clean material-assignment tool.** Do NOT hand-edit the `StaticMaterials`
   array via `ObjectTools.set_properties`. Use
   `StaticMeshTools.set_material(mesh, slot_name, material)` — it assigns to the asset, so
   **all 49 placed instances update**. Slot names come from
   `StaticMeshTools.get_material_slots(mesh)` (do NOT assume slot 0/1 are literally named
   "0"/"1" — read them first; the brief's "slot 0 / slot 1" are *indices*, the tool wants
   *names*).

2. **Constant values on material expression nodes are set with
   `ObjectTools.set_properties`** on the returned expression node (e.g. a
   `MaterialExpressionConstant` has a float property `R`; a `Constant3Vector` has a
   `Constant` linear-color property). `add_expression` only creates the node at default
   values — you must then set its constant. **Property names vary per node class — confirm
   with `ObjectTools.list_properties(node)` before setting** (do this once per node class,
   then reuse).

3. **`set_properties.values` is a JSON STRING at the raw MCP layer**, but when called
   through `ProgrammaticToolset.execute_tool_script` via `execute_tool(...)` you pass a
   real dict for the input and `properties` is a real object. Both forms appear below.

4. **Light intensity here is almost certainly on the legacy/normalized units path, NOT
   physical lux** (the Manhattan sun in the sibling level read `Intensity=6`). **Do NOT set
   lux magnitudes (50000+)** — it clips the scene to pure white. Treat intensity as a
   single-digit-to-low-tens dial and control final brightness with a **Manual-exposure
   PostProcessVolume** (auto-exposure otherwise washes the dusk mood and the window glow
   right out — there is no cvar-set tool in this build to disable auto-exposure).

5. **Sun pitch is set on the ACTOR via `ActorTools.set_actor_transform`** (rotation lives on
   the actor, not the light component). `ActorTools` was not in the brief's tool list but is
   registered and is the correct path.

6. **`execute_tool_script` is a restricted sandbox**: `run() -> dict`, only
   `json/math/datetime/copy/re/time` importable, no `import unreal`, the only door to the
   engine is `execute_tool("<Toolset>.<Tool>", {...})`. The loop in §3 obeys this.

---

## 1. Material `M_TowerGlass` — emissive window grid over reflective tinted glass

### Technique (why this reads as a skyscraper)

A skyscraper reads as glass-with-windows because of a **tiling rectangular grid of lit cells
separated by dark mullions**, over a **dark, reflective, blue-tinted base**. We build that
grid procedurally:

- A 2D coordinate (UV if reliable, else **WorldPosition** — see the fallback) is multiplied
  by a tiling count: **high vertical** (many floors) × **moderate horizontal** (bays).
- `Frac` of that gives a 0..1 position **within each cell**. A window-vs-mullion **mask** is
  made by thresholding Frac on both axes (window in the centre of the cell, dark mullion
  border) and multiplying the two axis masks.
- `Floor` of the tiled coordinate gives a **per-cell integer id**; a cheap hash of that id
  drives **per-window on/off variation** (not every window lit) and slight color/brightness
  jitter, so it doesn't look like a uniform LED panel.
- The mask × window-color drives **`MP_EmissiveColor`**; the base is a dark blue tint on
  **`MP_BaseColor`**, **`MP_Metallic` ≈ 0.85**, **`MP_Roughness` ≈ 0.12** so the glass is
  reflective and catches the dusk sky/atmosphere.

> **UV reliability decision.** These are procedurally generated/imported towers, so per-tower
> UVs are unpredictable (different scale per mesh → window size would vary wildly, or UVs may
> be 0..1 stretched over the whole face → one giant "window"). **Default to the WorldPosition
> grid** (§1b) — it makes the window grid a consistent real-world size on every tower
> regardless of UVs. Keep the UV path (§1a) only as an alternative if a quick capture shows
> the meshes have clean, tiling, per-face UVs. The node lists are nearly identical; only the
> coordinate **source** differs.

### Expression class refPaths (UE 5.8 — all standard `/Script/Engine.*`)

All verified as standard UE 5.8 `MaterialExpression` class names. Confirm any with
`MaterialTools.list_expression_classes(M_TowerGlass, "<search>")` before adding if unsure —
flagged ones noted.

| Role | expression_class refPath |
|------|--------------------------|
| World position (fallback grid source) | `/Script/Engine.MaterialExpressionWorldPosition` |
| UV source (alt grid source) | `/Script/Engine.MaterialExpressionTextureCoordinate` |
| Mask a channel (XY from WorldPos, or split UV) | `/Script/Engine.MaterialExpressionComponentMask` |
| Scalar constant | `/Script/Engine.MaterialExpressionConstant` |
| 2-vector constant (tiling X,Y) | `/Script/Engine.MaterialExpressionConstant2Vector` |
| RGB constant (colors) | `/Script/Engine.MaterialExpressionConstant3Vector` |
| Multiply | `/Script/Engine.MaterialExpressionMultiply` |
| Add | `/Script/Engine.MaterialExpressionAdd` |
| Frac | `/Script/Engine.MaterialExpressionFrac` |
| Floor | `/Script/Engine.MaterialExpressionFloor` |
| Fractional/threshold step | `/Script/Engine.MaterialExpressionIf`  ⚠️ *(verify; see note)* |
| One minus | `/Script/Engine.MaterialExpressionOneMinus` |
| Linear interpolate | `/Script/Engine.MaterialExpressionLinearInterpolate` |
| Dot product (cell-id hash) | `/Script/Engine.MaterialExpressionDotProduct` |
| Sine (cheap hash) | `/Script/Engine.MaterialExpressionSine` |
| Power (sharpen mask) | `/Script/Engine.MaterialExpressionPower` |
| Min / Max (clamp mask) | `/Script/Engine.MaterialExpressionMax` / `…Min` |

> ⚠️ **Threshold node note.** UE has no single "step(edge,x)" node. Build the window-vs-mullion
> mask **without `MaterialExpressionIf`** (which compares against a scalar and is fiddly over
> MCP) using this robust, all-arithmetic trick instead:
> `mask = saturate( (frac*-something) ... )` — concretely we use
> **`Power`** of a smooth pulse, or simplest: **two `Max`/subtract** ops. The recipe below
> uses the **arithmetic pulse** form so every node is a guaranteed-present math node. If you
> prefer a sharper edge and `MaterialExpressionStep` exists in this build
> (`list_expression_classes(mat,"Step")`), you may swap it in.

### 1a → 1b shared build — the WorldPosition window grid (DEFAULT)

Create the material first:

```
toolset: editor_toolset.toolsets.material.MaterialTools
tool:    create_material
arguments: { "folder_path": "/Game/FuturisticCity/Materials", "name": "M_TowerGlass" }
```
Capture the returned material refPath as `<MG>`. Use it as `material_or_function` everywhere
below. (x/y are graph-layout only; values shown keep the graph readable. Call
`MaterialTools.layout_expressions(<MG>)` at the end if you want it auto-tidied.)

**Node list (add each via `MaterialTools.add_expression`, capture each returned refPath):**

| # | name | expression_class | x,y | constant to set after add |
|---|------|------------------|-----|----------------------------|
| N1 | WorldPos | `…WorldPosition` | -1700,0 | — |
| N2 | MaskXY | `…ComponentMask` | -1500,0 | mask = **R,G only** (X,Y world axes → horizontal+vertical building plane). See note ⚠️UV-axis. |
| N3 | TileVec | `…Constant2Vector` | -1700,200 | window cell size in cm → tiling: set **R = 1/350, G = 1/450** (≈350cm bay width, 450cm floor height; smaller value = larger cell). |
| N4 | GridUV = N2*N3 | `…Multiply` | -1300,0 | — |
| N5 | Frac | `…Frac` | -1100,0 | — |
| N6 | Floor (cell id) | `…Floor` | -1100,200 | — (feeds the hash) |
| N7 | CenterOffset | `…Constant` | -1100,-200 | R = **0.5** |
| N8 | Frac-0.5 | `…Add` (Frac + (−0.5)) or Subtract | -900,0 | use `…Subtract` if present, else Add with a −0.5 constant |
| N9 | Abs of that | `…Abs` (`/Script/Engine.MaterialExpressionAbs`) | -750,0 | — (distance from cell centre, 0..0.5 each axis) |
| N10 | WindowHalf | `…Constant` | -900,-200 | R = **0.38** (window half-width as fraction of cell; >0.38 from centre = mullion) |
| N11 | mask = WindowHalf − Abs | `…Subtract` (`…MaterialExpressionSubtract`) | -550,0 | positive inside window, negative on mullion |
| N12 | Saturate/clamp to 0..1 | `…Max` with 0, then `…Min` with small→ or `…MaterialExpressionSaturate` ⚠️verify | -400,0 | — |
| N13 | sharpen | `…Power` (mask ^ ~6) | -250,0 | exponent const R = **8** → crisp window edges |
| N14 | combine X·Y mask | `…Multiply` (maskX * maskY) | -100,0 | — (this is the per-window mask, see ⚠️ two-axis note) |
| N15 | CellHash | `…DotProduct`(Floor, const2(12.9898,78.233)) → `…Sine` → `…Frac` | -100,300 | classic `frac(sin(dot(id,(12.9898,78.233)))*43758.5)` hash → 0..1 per cell |
| N16 | LitThreshold | `…Constant` | 100,300 | R = **0.55** (≈45% of windows lit). hash > threshold ? lit |
| N17 | litMask = saturate((hash−thr)*big) | `…Subtract`→`…Multiply`(×20)→`Max`0`Min`1 | 250,300 | per-cell on/off |
| N18 | WindowColor | `…Constant3Vector` | 250,500 | **cool white-cyan**: R=0.55, G=0.78, B=1.0 |
| N19 | EmissiveBoost | `…Constant` | 250,650 | R = **6.0** (HDR — must exceed 1 to bloom/glow) |
| N20 | Emissive = mask·litMask·color·boost | chain of `…Multiply` | 500,300 | N14 × N17 × N18 × N19 |
| N21 | BaseColorTint | `…Constant3Vector` | 100,-300 | **dark blue glass**: R=0.012, G=0.02, B=0.045 |
| N22 | Metallic | `…Constant` | 100,-450 | R = **0.85** |
| N23 | Roughness | `…Constant` | 100,-600 | R = **0.12** |

**The two-axis mask (⚠️ important).** N9–N14 as written produce a single-axis distance. To
get a real *rectangular window* you need the centre-distance mask on **both** the X and Y
fractional axes, then multiply. Practical build: after N5 (`Frac` of the 2-vector GridUV),
split it with two `ComponentMask` nodes (one R-only, one G-only), run **each** through the
"abs(frac−0.5) → WindowHalf−abs → saturate → power" chain (N7–N13), then **N14 = maskR ×
maskG**. So N7–N13 are instantiated **twice** (once per axis); reuse the same N7/N10/N13
constants by wiring them into both chains. This yields lit rectangles separated by dark
mullion lines on both axes — the skyscraper read.

**Wiring (via `MaterialTools.connect_expressions(from, from_out, to, to_in)`; use
`get_expression_input_names`/`get_expression_output_names` to confirm pin names — `""` =
default first pin):**

1. `N1 WorldPos` → `N2 MaskXY` (in `""`). Set N2 mask to the two building-plane axes.
   ⚠️**UV-axis note:** towers are vertical, so the **floor** axis must be world **Z**. A
   `ComponentMask` of WorldPosition giving **(X for bays, Z for floors)** is usually right —
   confirm by capturing one tower: if floors run horizontally, you masked the wrong pair.
   Use mask **R+B** (X,Z) if so, not R+G.
2. `N2` → `N4 Multiply` in A; `N3 TileVec` → `N4` in B.
3. `N4` → `N5 Frac`.
4. `N4` → `N6 Floor` (cell id for the hash). `N6` → `N15` dot-product chain.
5. **Per axis (X then the other):** `N5 Frac` → `ComponentMask R` → N8 `Subtract 0.5` → N9
   `Abs` → N11 `Subtract` (N10 WindowHalf − Abs) → N12 saturate → N13 `Power` (^N? exp). Same
   again with `ComponentMask G/B`.
6. `N13_axisX` → `N14 Multiply` A; `N13_axisY` → `N14 Multiply` B.
7. Hash: `N6 Floor` → `N15 DotProduct` (B = const2 12.9898,78.233) → `Sine` → `Multiply ×
   43758.5` → `Frac` → that 0..1 → N17 `Subtract N16` → `Multiply ×20` → `Max 0`/`Min 1`.
8. Emissive: `N14` → `N20a Multiply` A, `N17` → `N20a` B; `N20a` → `N20b Multiply` A, `N18
   WindowColor` → `N20b` B; `N20b` → `N20c Multiply` A, `N19 EmissiveBoost` → `N20c` B.
9. **Outputs (via `connect_to_output(expr, "", MP_*)`):**
   - `N20c` → `MP_EmissiveColor`
   - `N21 BaseColorTint` → `MP_BaseColor`
   - `N22 Metallic` → `MP_Metallic`
   - `N23 Roughness` → `MP_Roughness`
10. `MaterialTools.recompile(<MG>)`.

**Set every constant after adding its node**, e.g. for the tiling vector:
```
toolset: editor_toolset.toolsets.object.ObjectTools
tool:    set_properties
arguments: { "instance": { "refPath": "<N3>" },
             "values": "{\"R\": 0.00286, \"G\": 0.00222}" }
```
For a `Constant3Vector` the color property is `Constant` (a linear color):
```
arguments: { "instance": { "refPath": "<N18>" },
             "values": "{\"Constant\": {\"r\":0.55,\"g\":0.78,\"b\":1.0,\"a\":1.0}}" }
```
For a `Constant` the float property is `R`:
```
arguments: { "instance": { "refPath": "<N19>" }, "values": "{\"R\": 6.0}" }
```
> Run `ObjectTools.list_properties(<node>)` once per node class to confirm `R` /
> `Constant` / `R,G` spellings before the first set of that class. They are stable across UE
> 5.x but the brief explicitly asked to verify, and a silently-missed property name is the #1
> failure mode here.

### 1b — UV alternative (only if the meshes have clean tiling UVs)

Identical graph, but replace **N1 WorldPos + N2 MaskXY** with a single
`MaterialExpressionTextureCoordinate` (its `UTiling`/`VTiling` properties can even do the
tiling, letting you drop N3/N4). Set `UTiling ≈ 8`, `VTiling ≈ 30` (8 bays, 30 floors) as a
start. Use this only if a capture proves UVs tile per face; otherwise the WorldPosition grid
is more reliable on procedural meshes.

---

## 2. Material `M_TowerFrame` — dark structural metal (brief)

```
toolset: editor_toolset.toolsets.material.MaterialTools
tool:    create_material
arguments: { "folder_path": "/Game/FuturisticCity/Materials", "name": "M_TowerFrame" }
```
Capture as `<MF>`. Add three constants and wire to outputs:

| node | class | value | → output |
|------|-------|-------|----------|
| F1 BaseColor | `…Constant3Vector` | `Constant = (0.015,0.015,0.018,1)` near-black | `MP_BaseColor` |
| F2 Metallic | `…Constant` | `R = 0.9` | `MP_Metallic` |
| F3 Roughness | `…Constant` | `R = 0.35` | `MP_Roughness` |

Then `MaterialTools.recompile(<MF>)`. That's the whole frame material.

---

## 3. Assignment — slot 0 → M_TowerGlass, slot 1 → M_TowerFrame on all 12 towers

**First read the real slot names** (do NOT assume "0"/"1"):
```
toolset: editor_toolset.toolsets.static_mesh.StaticMeshTools
tool:    get_material_slots
arguments: { "mesh": { "refPath": "/Game/FuturisticCity/Towers/Tower_01.Tower_01" } }
```
Returns an ordered list, e.g. `["glass","frame"]` or `["MaterialSlot_0","MaterialSlot_1"]`.
**Slot index 0 = first element = glass; index 1 = second = frame.** Use those exact strings
as `slot_name`. Assume the 12 towers share the same slot scheme (verify on Tower_01; if any
differs the loop below logs it).

Assigning on the **StaticMesh asset** propagates to all 49 placed StaticMeshActor instances
automatically (instances only diverge if they carry per-component overrides, which these
grid-placed actors should not).

### Single-tower form (manual / spot check)
```
toolset: editor_toolset.toolsets.static_mesh.StaticMeshTools
tool:    set_material
arguments: {
  "mesh": { "refPath": "/Game/FuturisticCity/Towers/Tower_01.Tower_01" },
  "slot_name": "<first slot name from get_material_slots>",
  "material": { "refPath": "<MG>" }
}
```
…and again with the second slot name and `<MF>`.

### Loop all 12 — `ProgrammaticToolset.execute_tool_script`

This obeys the sandbox: `run()` returns a dict, only `execute_tool(...)` reaches the engine,
inputs/outputs are dicts (the `{"refPath": "..."}` wrapping is preserved). **Paste `<MG>` and
`<MF>` refPaths into the two constants** before running. It reads each mesh's real slot names
(so it's robust to "0"/"1" vs "glass"/"frame"), assigns slot index 0→glass, 1→frame, and
reports per-tower status.

```python
def run():
    GLASS = {"refPath": "<MG>"}   # paste M_TowerGlass refPath
    FRAME = {"refPath": "<MF>"}   # paste M_TowerFrame refPath
    SM = "editor_toolset.toolsets.static_mesh.StaticMeshTools"
    results = {}
    for i in range(1, 13):
        mesh = {"refPath": "/Game/FuturisticCity/Towers/Tower_%02d.Tower_%02d" % (i, i)}
        try:
            slots = execute_tool(SM + ".get_material_slots", {"mesh": mesh})["returnValue"]
            rec = {"slots": slots}
            if len(slots) >= 1:
                execute_tool(SM + ".set_material",
                             {"mesh": mesh, "slot_name": slots[0], "material": GLASS})
                rec["slot0"] = slots[0] + " <- glass"
            if len(slots) >= 2:
                execute_tool(SM + ".set_material",
                             {"mesh": mesh, "slot_name": slots[1], "material": FRAME})
                rec["slot1"] = slots[1] + " <- frame"
            results["Tower_%02d" % i] = rec
        except Exception as e:
            results["Tower_%02d" % i] = {"error": str(e)}
    return results
```
Read the returned dict: every tower should show both slots assigned. Any `"error"` or
single-slot tower flags a mesh that needs manual handling. (Call
`ProgrammaticToolset.get_execution_environment` once first if you haven't this session — the
plugin requires it before `execute_tool_script`.)

---

## 4. Dusk lighting — Dubai-at-dusk so the windows glow

Order matters: **set exposure Manual FIRST** (else auto-exposure rebalances and the emissive
windows won't read as "glowing" — they'll just look mid-grey). Then aim/warm the sun, then
fog.

### 4a. Find the existing lights (read-only)
```
toolset: editor_toolset.toolsets.scene.SceneTools
tool:    find_actors
arguments: { "name": "", "tag": "",
             "actor_type": { "refPath": "/Script/Engine.DirectionalLight" },
             "collision_channels": [] }
```
Repeat with `/Script/Engine.SkyLight` and `/Script/Engine.SkyAtmosphere`. Capture the actor
refPaths. The light **component** is the actor refPath + `.LightComponent0` (directional) /
`.SkyLightComponent0` (sky) — confirm by `ObjectTools.list_properties` on the actor to find
the exact component subobject name (the sibling level used `LightComponent0` /
`SkyLightComponent0`).

### 4b. Manual-exposure PostProcessVolume (make-or-break for the glow)
```
toolset: editor_toolset.toolsets.scene.SceneTools
tool:    add_to_scene_from_class
arguments: { "actor_type": { "refPath": "/Script/Engine.PostProcessVolume" },
             "name": "PP_Dusk", "xform": { "location": { "x":0,"y":0,"z":0 } } }
```
Capture as `<PP>`, then (note `values` is a JSON **string** at the raw layer; struct nesting
allowed):
```
toolset: editor_toolset.toolsets.object.ObjectTools
tool:    set_properties
arguments: {
  "instance": { "refPath": "<PP>" },
  "values": "{\"bUnbound\": true, \"Priority\": 1000000.0, \"Settings\": {\"bOverride_AutoExposureMethod\": true, \"AutoExposureMethod\": \"AEM_Manual\", \"bOverride_AutoExposureBias\": true, \"AutoExposureBias\": 10.0, \"bOverride_AutoExposureApplyPhysicalCameraExposure\": true, \"AutoExposureApplyPhysicalCameraExposure\": false, \"bOverride_BloomIntensity\": true, \"BloomIntensity\": 1.0, \"bOverride_BloomThreshold\": true, \"BloomThreshold\": 1.0}}"
}
```
- `AEM_Manual` + `AutoExposureBias 10.0` = fixed exposure; **this is the brightness dial** —
  raise to 11–12 if too dark, drop to 8–9 if blown. Bloom threshold 1.0 means only the HDR
  window emissive (boost 6.0 > 1) blooms → the glow.
- ⚠️ Verify struct field spellings with `list_properties(<PP>)` / on its `Settings` first;
  stable across 5.x but confirm. If a nested-struct set is rejected, fall back to driving
  brightness via light intensities and accept auto-exposure (worse mood).

### 4c. Aim + warm the sun (DirectionalLight) — actor rotation, component color
Dusk sun just at/below the horizon. Pitch ~**-4°** (lower than golden hour's -8 → deeper,
redder), warm via temperature.
```
toolset: editor_toolset.toolsets.actor.ActorTools
tool:    set_actor_transform
arguments: { "actor": { "refPath": "<DirectionalLight actor>" },
             "xform": { "rotation": { "pitch": -4.0, "yaw": -60.0, "roll": 0.0 } },
             "worldspace": true }
```
Then on the **component** (legacy units — NOT lux):
```
toolset: editor_toolset.toolsets.object.ObjectTools
tool:    set_properties
arguments: {
  "instance": { "refPath": "<DirectionalLight actor>.LightComponent0" },
  "values": "{\"bUseTemperature\": true, \"Temperature\": 3200.0, \"LightColor\": {\"r\":1.0,\"g\":0.70,\"b\":0.42,\"a\":1.0}, \"Intensity\": 4.0, \"bAtmosphereSunLight\": true, \"DynamicShadowDistanceMovableLight\": 50000.0}"
}
```
- `Temperature 3200` + a warm `LightColor` (#FFB36A ≈ rgb 1.0,0.70,0.42 as requested) → deep
  amber dusk. **Intensity 4.0** (dimmer than midday, so windows out-glow the sky). Keep
  `bAtmosphereSunLight=true` so SkyAtmosphere reddens the horizon automatically.

### 4d. SkyLight — dim cool fill + recapture
At dusk the ambient is dim and cool (sky blue), which makes the warm windows pop.
```
toolset: editor_toolset.toolsets.object.ObjectTools
tool:    set_properties
arguments: {
  "instance": { "refPath": "<SkyLight actor>.SkyLightComponent0" },
  "values": "{\"Intensity\": 0.6, \"bRealTimeCapture\": true, \"bLowerHemisphereIsBlack\": true}"
}
```
- `bRealTimeCapture=true` **auto-recaptures** the warmed sky — no manual recapture UFUNCTION
  needed (which we couldn't call anyway). Intensity 0.6 keeps shadows deep so windows read as
  the brightest thing. If shadows go pure black, raise to 0.9.

### 4e. ExponentialHeightFog — subtle atmospheric haze (YES, add it)
A thin warm fog sells the Dubai-dusk depth and makes distant towers' window grids fade into
glow.
```
toolset: editor_toolset.toolsets.scene.SceneTools
tool:    add_to_scene_from_class
arguments: { "actor_type": { "refPath": "/Script/Engine.ExponentialHeightFog" },
             "name": "Fog_Dusk", "xform": { "location": { "x":0,"y":0,"z":0 } } }
```
Capture as `<FOG>`, set on its component (`.Component0`, confirm name via list_properties):
```
toolset: editor_toolset.toolsets.object.ObjectTools
tool:    set_properties
arguments: {
  "instance": { "refPath": "<FOG>.Component0" },
  "values": "{\"FogDensity\": 0.012, \"FogHeightFalloff\": 0.0008, \"FogInscatteringColor\": {\"r\":0.42,\"g\":0.28,\"b\":0.22,\"a\":1.0}, \"StartDistance\": 2000.0, \"bEnableVolumetricFog\": false}"
}
```
- Low `FogDensity 0.012` + tiny `FogHeightFalloff` (city spans ±42,000 cm horizontally and up
  to 80,000 cm tall, so falloff must be small or upper floors clear out). Warm brown-amber
  inscatter. **Keep `bEnableVolumetricFog=false`** — volumetric fog is a heavier, ticking-ish
  feature; the cheap height fog gives the haze without that risk. Tune density 0.008–0.02.

### 4f. SkyAtmosphere (if present) — leave default, optionally thicken Mie
With `bAtmosphereSunLight=true` and a low sun, the atmosphere reddens the horizon on its own.
Only if a capture wants a thicker glow band:
```
toolset: editor_toolset.toolsets.object.ObjectTools
tool:    set_properties
arguments: { "instance": { "refPath": "<SkyAtmosphere actor>.SkyAtmosphereComponent" },
             "values": "{\"MieScatteringScale\": 0.005, \"AerialPerspectiveViewDistanceScale\": 1.4}" }
```
Verify names via `list_properties` first (Mie field names vary by version).

### Apply order
1. 4b (PP_Dusk Manual exposure) → capture.
2. 4c (sun aim + warm) → capture, tune `AutoExposureBias` for brightness, `Temperature`/pitch
   for warmth.
3. 4d (SkyLight dim) → 4e (fog) → 4f (optional Mie) → capture between each.

---

## 5. QA capture pose

City spans ~±42,000 cm in X/Y around origin, towers up to ~80,000 cm tall. To frame the
skyline as a hero dusk shot, stand back and outside the grid, low to the ground, looking
across and slightly up at the towers (so lit window grids fill the frame against the dusk
sky). Set the editor camera explicitly (**never `FocusOnActors`** — explicit transform is the
safe path):

```
toolset: EditorToolset.EditorAppToolset
tool:    SetCameraTransform
arguments: {
  "transform": {
    "location": { "x": -75000.0, "y": -75000.0, "z": 22000.0 },
    "rotation": { "pitch": 8.0, "yaw": 45.0, "roll": 0.0 }
  }
}
```
- Camera ~75 km out on the −X/−Y diagonal, 220 m up, **yaw 45°** looking back toward origin
  along the diagonal (sees the deepest run of towers), **pitch +8°** angled slightly up so
  tower tops + window grids dominate over ground. The warm sun (yaw −60) rakes across from
  screen-right.

Then capture (NO annotations — read-only render, annotations clutter a beauty shot):
```
toolset: EditorToolset.EditorAppToolset
tool:    CaptureViewport
arguments: { "bShowUI": false }
```
Pull back further (location ×1.3) if towers clip the frame edges; raise `z` and `pitch` for a
more elevated establishing shot. Re-capture after each lighting tune rather than guessing.

---

## 6. Build order summary

1. §1 create `M_TowerGlass` → add nodes → set constants → wire → `recompile`. **Assign to ONE
   tower (§3 single form) and `CaptureAssetImage`/viewport-capture that one tower first** to
   confirm the window grid reads (axis right, cell size right) BEFORE looping all 12.
2. §2 create `M_TowerFrame` → recompile.
3. §3 loop assign all 12 (after the single-tower grid is confirmed).
4. §4 lighting in the stated order, exposure first.
5. §5 camera + capture; iterate the exposure/temperature/density dials.

**Top risk to watch:** the window-grid **axis** (floors must run on world Z) and **cell size**
(tiling constants) — both only show up in a capture. Confirm on one tower before committing
to all 12; everything else is cheap to re-set.
