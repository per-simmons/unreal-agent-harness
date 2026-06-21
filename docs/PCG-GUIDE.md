# PCG City — How We Build It (living guide)

> **Purpose.** A living reference for building a procedural city in UE 5.8 via the Unreal MCP,
> following the *same steps* as Epic's "PCG procedural city" demo — **not a replica**, our own
> city. Update this file as we learn. Companion to the detailed node-by-node recipe in
> [`pcg-city-plan.md`](./pcg-city-plan.md) and the research in
> [`pcg-city-research.md`](./pcg-city-research.md).

## What we're doing (and what we're NOT)
- **Goal:** an audience-facing LIVE build where a city generates itself in stages:
  city shape → colored **districts** → **blocks** → **buildings rise** → **highway splines** →
  **photoreal swap**.
- **Following the demo's STEPS, making our OWN city** — different shape, our own building
  palette, our own districts. Not copying their exact city.
- **Photoreal is the target finish** (decided 2026-06-20). We will use **City Sample** building
  assets (Epic login + download — a manual user gate, see below). Our 12 custom towers
  (`/Game/FuturisticCity/Towers/Tower_01..12`) are the v1 / fallback palette.

## The MCP PCG surface (verified 2026-06-20, read-only)
`PCGToolset.PCGToolset` is a **real graph-authoring API** (not a thin wrapper):
- `CreateGraph(name, path)` · `ListNativeNodes` · `GetNativeNodeSchema(node)` ·
  `AddNode(graph, nativeNodeType, nodeName, jsonParams, …)` ·
  `ConnectNodePins(from, fromPin, to, toPin)` (auto-inserts converters) · `UpdateNode` ·
  `SetGraphParams` (expose per-instance overridable params) ·
  `SpawnGraphInstance(graph, name, transform)` · `SetGraphInstanceParams` ·
  **`ExecuteGraphInstance(volume)`** (regenerate = the visible "beat") ·
  `GetNodeDataView` / `GetGraphStructure` / `GetNodeInfo` · `DrawSpline` (hands viewport to
  presenter for the live "draw the shape" beat) · `AddCommentBox`.
- `PCGSpatialToolset.RunPCGInstantGraph(graph, params)` — fire-and-forget execute.
- **⚠️ Concurrency:** execution state is shared at the graph-asset level. Call
  `ExecuteGraphInstance` / `GetNodeDataView` on **one volume at a time**, fully returning
  before the next — concurrent calls freeze the editor. (We use ONE graph + ONE volume.)

## The pipeline (one graph `/Game/PCG/PCG_LiveCity`, built node-by-node on camera)
Each stage = AddNode(s) → Connect → `ExecuteGraphInstance` so the viewport gains a layer.

| Stage | What | MCP feasibility | Key nodes |
|---|---|---|---|
| A | City shape (draw / build outline → surface) | ✅ Feasible | `DrawSpline`, `Get Spline Data`, `Create Surface From Spline` |
| B | Districts (colored regions) | ⚠️ Partial — **no Voronoi node**; use `Cluster` (KMeans, looks the same) | `Surface Sampler`, `Cluster`, `Attribute Partition`, `Visualize Attribute` |
| C | Blocks (grid per district + street gaps) | ✅ Feasible | `Create Points Grid` (cellSize > footprint = streets) |
| D | Buildings rise (height-varied, color-coded Small/Med/Large) | ✅ Feasible | `Add Attribute` (sizeClass), `Transform Points` (extrude), `Static Mesh Spawner` |
| E | Highway splines (carve road through) | ✅ Feasible | `DrawSpline`/`Get Spline Data`, `Spline Sampler`, `Difference`, `Spawn Spline Mesh` |
| F | Photoreal swap (City Sample buildings) | ⚠️ Gate — assets need Epic login + multi-GB download (NOT via MCP); swapping the spawner palette IS via MCP | `Static Mesh Spawner` palette → City Sample meshes |

**Verdict from design pass:** ~85% faithful, fully MCP-driven build; the two honest caveats are
KMeans-instead-of-Voronoi (Stage B) and the City Sample download being a manual gate (Stage F).

## Build-time confirmations (run these read-only BEFORE a live run)
1. Tower meshes present at `/Game/FuturisticCity/Towers/Tower_01..12`.
2. `PCGMeshSelector*` subclass refPaths via `ObjectTools.list_subclasses`.
3. `Spawn Spline Mesh` schema (`GetNativeNodeSchema`).
4. `Match And Set Attributes` schema (DistrictID → SizeClass mapping).
5. `Difference` node pin labels.

## Photoreal / City Sample — the manual gate (Epic login)
> Decided 2026-06-20: we ARE going photoreal. Pat has an Epic login.
- **City Sample Buildings** (free w/ Epic login): 24 modular kits + 44 sample buildings,
  **2,000+ meshes**, UE 5.0+, native .uasset. This is the photoreal palette.
  Fab: https://www.fab.com/listings/008fe959-5511-428e-93bd-f99b1179f6d5
- **Pat's exact steps (the one step the MCP can't do):**
  1. Sign in to Fab (fab.com) / Epic Games Launcher with the Epic account. ✅ done
  2. Open the City Sample Buildings listing → **Add to My Library** (free, Epic Content License).
     ✅ **done 2026-06-20 — saved to library.**
  3. ⏳ **NEXT:** Epic Launcher → Library / Fab → the asset → **Add to Project** → pick
     `MyProject` (UE 5.8) → downloads + imports (multi-GB; takes a while). *(Library ≠ in the
     project yet — this step does the actual download/import.)*
  4. Tell me when it's in — meshes land under `/Game/.../CitySampleBuildings/...` (we'll
     `find_assets` to confirm the exact path).
- Once imported, swap is trivial via MCP: point the `Static Mesh Spawner` palette at the City
  Sample building meshes (weighted by height class) and re-`ExecuteGraphInstance`.
- ⚠️ City Sample's *own* city was built in Houdini (Rule Processor), NOT PCG — so it's the
  asset/look source, not a PCG pipeline to copy.

## Optional upgrade — PCGEx plugin (real Voronoi + A* roads)
- **PCGEx (PCG Extended Toolkit)** — free, MIT, supports UE 5.8: adds Voronoi/Delaunay district
  partition + A*/Dijkstra road pathfinding that base PCG lacks.
  https://github.com/PCGEx/PCGExtendedToolkit (also on Fab).
- **Optional** — base PCG's `Cluster` (KMeans) districts look the same on camera, so we build
  v1 WITHOUT PCGEx (zero extra install). Add PCGEx later only if we want fancier roads/region
  edges. Companion `PCGExElementsWatabou` can import Watabou city-map layouts as a shortcut.

## Presentation tips (for the live audience build)
- Build incrementally: AddNode → Connect → Execute per stage so each layer pops as its own beat.
- Gate districts behind an `ActiveDistrict` graph param + re-execute to reveal them one at a time.
- `AddCommentBox` to label regions of the graph live (readable on camera).
- Fallback in back pocket: `ProgrammaticToolset` + `SceneTools.add_to_scene_from_asset` to
  grid-place towers directly if PCG misbehaves mid-stream.

## Learnings log (append as we build — date each entry)
- **2026-06-20** — Design pass complete (agents `pcg-design` + `pcg-research`). PCG is a real
  authoring API via MCP. No native Voronoi → Cluster/KMeans for districts. Photoreal = City
  Sample manual download gate. Our 12 towers work as the v1 spawner palette.
- **2026-06-20** — City Sample Buildings **added to Pat's Fab library** (free, Epic license).
  Still needs **Add to Project** to actually download/import into MyProject (multi-GB). PCG
  graph asset `/Game/PCG/PCG_LiveCity` created; `pcg-builder` agent building/testing the
  pipeline with our 12 towers as the v1 palette.
- **2026-06-20 — FIRST LIVE BUILD (rehearsal/debug pass, agent `pcg-build`).** Stages B/C/D
  built + executed end-to-end in `/Game/futuristiccity` with the PCGVolume **`LiveCity`**
  (Stage A real surface skipped — fed the grid directly). Verified via `GetNodeDataView` +
  `get_components`. WORKING reliably:
  - **Smoke loop:** `Create Points Grid` -> `Static Mesh Spawner` -> spawn `LiveCity` volume ->
    `ExecuteGraphInstance`. 100 points -> 100 towers, 12 distinct `ISM_Tower_*` components on the
    actor. The MCP PCG path is real, not faked.
  - **Districts (Stage B):** `Cluster` (KMeans, numClusters=5, clusterAttribute="DistrictID")
    fed by the grid points directly. Verified exactly 5 distinct DistrictID values 0-4.
    `clusterAttribute` is a selector — pass the bare name `"DistrictID"`; it reads back as a
    STRING ("0".."4"), not an int.
  - **Rise (Stage D):** `Transform Points` scaleMin.z=3 / scaleMax.z=15, bUniformScale=false,
    bAbsoluteScale=false. Verified per-point random Z (7.6..14.0), X/Y stay 1.
  - Final working chain (saved): `Blocks(grid)` -> `Districts(Cluster)` -> `Rise(Transform Points)`
    -> `Towers(Static Mesh Spawner)`, with 3 labeled comment boxes.

  GOTCHAS / EXACT VALUES (use these for the clean live run):
  1. **`mcp__unreal__call_tool` shape:** pass `toolset_name` (e.g. `"PCGToolset.PCGToolset"`)
     SEPARATELY from `tool_name` (e.g. `"AddNode"`, NO prefix). Full dotted name in `tool_name`
     errors "Tool not found".
  2. **Static Mesh Spawner palette is NOT a node param.** `meshSelectorType`/`meshSelectorParameters`
     live on the node's SETTINGS object: `node -> get_properties(["settingsInterface"])` ->
     `Towers.PCGStaticMeshSpawnerSettings_1`, whose `meshSelectorParameters` -> the
     `...DefaultSelectorInstance` subobject. Node defaults to `PCGMeshSelectorWeighted` already.
  3. **Weighted palette schema:** set `meshEntries` on DefaultSelectorInstance = array of
     `{"descriptor":{"staticMesh":{"refPath":"/Game/.../Tower_01.Tower_01"}},"weight":1,"displayName":"Tower_01"}`.
     - StaticMesh refPath MUST be the full object path with `.AssetName` suffix
       (`/Game/FuturisticCity/Towers/Tower_01.Tower_01`); asset path alone errors
       "not a valid object path".
     - **`set_properties` CANNOT grow an empty array straight to N** — errors "ArrayAdd:
       insertion points are ambiguous." Append ONE entry per call (read-back, append, set);
       each call grows by exactly 1. Looped towers 02-12 via `execute_tool_script`; all 12 landed.
  4. **`ProgrammaticToolset`:** call `get_execution_environment` first; scripts define `run()`,
     use `execute_tool(dotted_name, json_string)`; allowed modules json/math/datetime/copy/re/time.
  5. **Cull-to-volume is the trap.** `Create Points Grid` with `bCullPointsOutsideVolume:true`
     returned ZERO points on first execute (volume bounds at gen-start didn't cover the
     World-space grid). With cull OFF it generates correctly. Volume bounds AUTO-EXPAND to wrap
     generated content after a run (measured ±620,000cm XY, Z to 8,000,000cm), so cull behaviour
     is order-dependent — for clip-to-shape later use a dedicated `Difference` /
     `Cull Points Outside Actor Bounds` node vs the Stage-A surface, NOT the grid's own cull flag.
  6. **WORKING node params (copy verbatim for the live run):**
     - Grid: `{"gridExtents":{"x":30000,"y":30000,"z":0},"cellSize":{"x":6000,"y":6000,"z":1},"pointPosition":"CellCenter","coordinateSpace":"World","bSetPointsBounds":true,"bCullPointsOutsideVolume":false}` -> 10x10=100 pts, ±27000cm (540m), 60m spacing.
     - Volume spawn scale `{x:700,y:700,z:200}` at origin (bounds auto-expand anyway).
     - Cluster: `{"algorithm":"KMeans","numClusters":5,"clusterAttribute":"DistrictID"}`.
     - Rise: `{"scaleMin":{"x":1,"y":1,"z":3},"scaleMax":{"x":1,"y":1,"z":15},"bAbsoluteScale":false,"bUniformScale":false}`.
  7. **No editor freeze** at any point with one graph + one volume and serial execute calls.
  8. **`PCGMeshSelectorBase` subclasses present:** Weighted, ByAttribute, WeightedByCategory,
     PrimitiveData. For size-coding by district later, switch `meshSelectorType` to
     `PCGMeshSelectorByAttribute` (`staticMeshComponentPropertyOverrides` only works in
     SelectByAttribute mode per the spawner schema).

  NOT YET BUILT (next pass): Stage A real surface from a drawn/created spline (fed grid directly);
  Stage D1 DistrictID->SizeClass mapping + per-district material color; Stage E highways. Core
  B-D loop is proven and saved (`/Game/PCG/PCG_LiveCity` + level `/Game/futuristiccity`).

- **2026-06-21 — PHOTOREAL BUILD in the City Sample project (`futuristiccitysample`), agent
  `pcg-builder`.** Built `/Game/PCG/PCG_PhotorealCity` in the `/Game/Map/Startup/Startup` level
  (the near-empty startup map — safe to build in, no City Sample content to wreck). Pipeline
  `Blocks(grid) -> Districts(Cluster) -> Rise+yaw(Transform Points) -> Buildings(Static Mesh
  Spawner)`. 100 buildings spawned, 5 districts (DistrictID 0-4, contiguous), photoreal facades
  under a sun/sky/skylight I added. Graph + level SAVED.

  ⚠️⚠️ **BIGGEST GOTCHA — the City Sample "buildings" are NOT spawnable single meshes.** The
  team brief said use `/Game/Building/HDA/Bake/*_main_geo` as a complete-building palette. They
  are NOT buildings — each `*_main_geo` is a **thin ~20cm ROOF CAP** floating at Z≈7000-7400cm
  (bounds min.z≈7245, only 20 triangles; rendered thumbnail = a flat plate). Confirmed across 6
  of the 24. There are only 24 of them and each building has ONLY its main_geo in Bake.
  - **Why:** this full City Sample project has NO discrete reusable building meshes. The city is
    a Houdini **PointCloud** (`/Game/City/Small_City/PBC/CITY_buildings` = `PointCloudImpl`)
    driven by **Mantle Rule Sets** (`Small_City_FULL_buildings` = `PointCloudSliceAndDiceRuleSet`),
    assembled at bake time from modular KIT pieces. Not PCG, not single meshes.
  - **The real photoreal building content = the modular kit** at
    `/Game/Building/CH/{A..J}/Kit_Bldg_CH*_L{1..21}_*/Mesh/SM_BLDG_*_Wall|Corner|Column|CornerEx|CornerIn_*_N1`.
    A `Wall` mesh = one photoreal facade FLOOR panel: ~325cm wide × 300cm tall (1 floor = 3m),
    pivot at the base (min.z=0), real windows/cornice/stonework (thumbnail confirmed). ~10
    building styles (A-J) × up to 21 floor levels each. Find them all with
    `AssetTools.find_assets(folder_path="/Game/Building/CH", name="_Wall_01_N1", asset_type=/Script/Engine.StaticMesh)`.
  - The FuturisticCity fallback towers (`/Game/FuturisticCity/Towers/Tower_*`) do NOT exist in
    this project — that was the other project.

  **What WORKED (the v1 photoreal recipe — copy verbatim):**
  - Palette = 12 `SM_BLDG_*_Wall_01_N1` facades spread across styles A-J and tall floor levels
    (L6-L19), weighted 1 each, appended ONE per call to
    `Buildings.PCGStaticMeshSpawnerSettings_1.DefaultSelectorInstance.meshEntries` (the
    read-back-append-set loop from gotcha #3 still holds; `bAllowDescriptorChanges` left default).
  - Grid: `{"gridExtents":{"x":20000,"y":20000,"z":0},"cellSize":{"x":4000,"y":4000,"z":1},"pointPosition":"CellCenter","coordinateSpace":"World","bSetPointsBounds":true,"bCullPointsOutsideVolume":false}` -> 10x10 = 100 pts, ±18000cm, 40m spacing (= street gaps).
  - Districts: `{"algorithm":"KMeans","numClusters":5,"clusterAttribute":"DistrictID"}` (same as
    rehearsal; reads back as STRING "0".."4").
  - Rise+yaw (Transform Points): `{"scaleMin":{"x":4,"y":4,"z":8},"scaleMax":{"x":6,"y":6,"z":32},"bAbsoluteScale":false,"bUniformScale":false,"rotationMin":{"pitch":0,"yaw":0,"roll":0},"rotationMax":{"pitch":0,"yaw":270,"roll":0}}`
    — X/Y 4-6× widens the single facade into a multi-bay block; Z 8-32× gives varied tower
    heights (NOT the 3-15× rehearsal rise — these aren't thin towers); yaw 0-270 so backs face
    streets too.
  - Volume spawn scale `{x:500,y:500,z:200}` at origin.

  **HONEST LIMITATION (documented gap):** a single facade `Wall` panel is a ONE-SIDED billboard
  — windows on the front, blank/thin back+sides. From a distance the clustered grid reads as a
  convincing downtown skyline (verified via CaptureViewport — varied photoreal towers, real
  sky), but up close / from behind you see flat backs. TRUE closed photoreal buildings need a
  multi-stage "stack 4 walls + corners into a box, per floor" graph (i.e. re-implementing the
  Mantle Rule Processor in PCG) — deferred pending Pat's call on whether the skyline-cluster v1
  is enough for the "watch a photoreal city generate itself" demo.

  **Lighting note:** the Startup map ships with NO sky/sun — geometry renders pure black. Add
  `/Script/Engine.DirectionalLight` (pitch -45) + `/Script/Engine.SkyAtmosphere` +
  `/Script/Engine.SkyLight` before any viewport QA or the demo. (Facades render a touch
  blown-out white under a strong sun — drop sun intensity / exposure for a cleaner look.)

- **2026-06-21 — PIVOT TO CUBE-EXTRUSION (the approach that WON), agent `pcg-builder`.**
  Pat/lead pivoted off facade panels (they read as flat one-sided slabs) to **Epic's actual
  demo method: PCG extrudes the Engine Cube into boxes + a windowed-glass material.** This is
  the canonical recipe now — NO City Sample asset dependency, NO asset hunting. Same graph
  `/Game/PCG/PCG_PhotorealCity` in `/Game/Map/Startup/Startup`, fully working + saved.

  **Final pipeline (5 nodes):** `Blocks(Create Points Grid)` -> `Districts(Cluster KMeans 5)` ->
  `Rise(Transform Points, scale only)` -> `Anchor(Attribute Maths Op)` -> `Buildings(Static Mesh
  Spawner: 1 Cube, M_TowerGlass override)`. Plus a `HalfCube(Create Constant=50)` feeding Anchor.

  **Building mesh = `/Engine/BasicShapes/Cube.Cube`** — exists in every project. Bounds are
  100×100×100cm **centered** (z -50..+50), so the pivot is at the CENTER, not the base.

  **THE GROUND-ANCHOR GOTCHA + FIX (important):** because the cube pivot is centered, scaling Z
  by S makes it extend ±50·S → half the building ends up BURIED below Z=0. Transform Points'
  `offset` does NOT scale per-point (verified: a non-absolute offsetZ=50 produced a fixed
  translation.Z=50, not 50·scaleZ). **Fix = an `Attribute Maths Op` node AFTER the scale that
  sets `$Position.Z = $Scale.Z × 50`:** operation `Multiply`, `inputSource1="$Scale.Z"`,
  `inputSource2="HalfCube"` (a `Create Constant` Double=50 wired into the **InB** pin; point data
  into **InA**), `outputTarget="$Position.Z"`. Verified exact: scaleZ=10.62 → Position.Z=530.84
  = 10.62×50, so box base sits exactly on Z=0 and grows straight up. (Watch: `UpdateNode` only
  overrides the JSON keys you pass — it does NOT clear old ones, so a stale `inputSource2:$Density`
  lingered and errored "Attribute '$Density' from pin InB does not exist"; pass the full param set.)

  **Working params (copy verbatim):**
  - Grid: `{"gridExtents":{"x":20000,"y":20000,"z":0},"cellSize":{"x":4000,"y":4000,"z":1},"pointPosition":"CellCenter","coordinateSpace":"World","bSetPointsBounds":true,"bCullPointsOutsideVolume":false}` → 10×10=100, 40m cells.
  - Districts: `{"algorithm":"KMeans","numClusters":5,"clusterAttribute":"DistrictID"}`.
  - Rise (scale ONLY, no offset): `{"scaleMin":{"x":18,"y":18,"z":8},"scaleMax":{"x":26,"y":26,"z":40},"bAbsoluteScale":false,"bUniformScale":false}` → 18-26m footprint (fits 40m cell w/ street gaps), 8-40m tall.
  - Anchor: Attribute Maths Op as above. HalfCube: `Create Constant` `{"attributeTypes":{"type":"Double","doubleValue":50},"outputTarget":"HalfCube"}`.
  - Volume spawn scale `{x:500,y:500,z:200}` at origin.

  **Material `/Game/PCG/M_TowerGlass` (emissive window grid, WorldPosition-based — 25 nodes):**
  WorldPosition → ComponentMask R (worldX) & B (worldZ) → ×Constant tiling (X=1/350=0.00286,
  Z=1/450=0.00222) → Frac → ConstantBiasScale(bias=-0.5,scale=1) → Abs (= dist from cell
  center) → SmoothStep(min~0.30,max~0.42) → OneMinus (window=1 center / mullion=0 edge) →
  multiply the X-window × Z-window → × warm WindowColor(1,0.85,0.55) × Boost(7) → MP_EmissiveColor.
  BaseColor dark-blue glass (0.012,0.02,0.045), Metallic 0.85, Roughness 0.12. SmoothStep pins
  are `Min`/`Max`/`Value`; its constant props are `constMin`/`constMax`. ComponentMask channels =
  bool `r`/`g`/`b`/`a`. Build the whole graph in ONE `execute_tool_script` (add_expression +
  set_properties + connect_expressions), then `MaterialTools.recompile`.

  **MATERIAL-OVERRIDE-ON-SPAWNER GOTCHA (cost real time):** setting the cube meshEntry's
  `descriptor.overrideMaterials=[{refPath:M_TowerGlass}]` is correct, BUT a plain re-
  `ExecuteGraphInstance` does NOT push the new descriptor onto the already-spawned ISM (the ISM's
  `OverrideMaterials` stayed `[]`). **Fix: remove the PCGVolume actor and `SpawnGraphInstance`
  fresh, THEN execute** — the new ISM then shows `OverrideMaterials=[M_TowerGlass]`.
  (`bAllowDescriptorChanges` was already true; that wasn't the issue.)

  **LIGHTING/EXPOSURE (needed or the city is black, then blown white):** Startup map has no
  sky/sun — add DirectionalLight(pitch -45, intensity 10) + SkyAtmosphere + SkyLight. Then the
  dark-glass material + auto-exposure blows everything to flat white (windows invisible). Fix =
  add an **unbound `/Script/Engine.PostProcessVolume`** (`bUnbound:true`) with MANUAL exposure:
  `Settings.bOverride_AutoExposureMethod:true, AutoExposureMethod:"AEM_Manual",
  bOverride_AutoExposureApplyPhysicalCameraExposure:true, AutoExposureApplyPhysicalCameraExposure:false,
  bOverride_AutoExposureBias:true, AutoExposureBias:-2.5`. **AutoExposureBias is an EV offset:
  +11 → pitch black (warned "Exposure -11, safe range [-8,12]"); ~-2.5 to -4 = crisp, legible
  window grid.** At -2.5 the towers read as bright windowed glass skyscrapers. Screenshots:
  `~/coding/unreal-agent-harness/docs/city_cubes_01.png` (greybox), `city_glass_05.png` (EV-4),
  `city_glass_final.png` (EV-2.5, the keeper).

  **This cube-extrusion + M_TowerGlass recipe is the recommended default for "watch a photoreal
  city generate itself"** — proven, asset-independent, and reads as real buildings from every
  angle (closed boxes, not one-sided panels).

  **FINAL DEMO POLISH (2026-06-21) — per-district color + bigger grid + ground.** Now demo-ready:
  5 distinctly-colored districts of windowed glass towers on an asphalt ground. Screenshots:
  `~/coding/unreal-agent-harness/docs/city_districts_wide.png` + `city_districts_aerial.png`.
  - **Ground:** spawn `/Engine/BasicShapes/Plane.Plane` at Z=0 scale 5000 (±250m), assign dark
    asphalt `/Game/PCG/M_Asphalt` (BaseColor ~0.02, Rough 0.85) via the StaticMeshComponent's
    `OverrideMaterials` (plain actor, not the spawner).
  - **Bigger skyline:** Blocks `gridExtents` 20000→29000 (cellSize 4000) → 14×14=196 buildings
    (~31000 for a true 15×15); bump PCGVolume spawn scale to {x:750,y:750,z:200}.
  - **Per-district color chain:** (1) `Cluster`'s DistrictID is a STRING → add `Attribute Cast`
    (DistrictID→Float `DistrictNum`) between Districts and Rise. (2) On the spawner SETTINGS set
    `instanceDataPackerType=/Script/PCG.PCGInstanceDataPackerByAttribute`, then its
    `attributeSelectors=["DistrictNum"]` → packs into ISM PerInstanceCustomData[0]
    (`NumCustomDataFloats` becomes 1). (3) In M_TowerGlass add `PerInstanceCustomData` (dataIndex
    0) → a 5-way `MaterialExpressionIf` chain (compare to 0/1/2/3 via `constB`+`equalsThreshold`
    0.1; `A==B`→tint_i, `A>B`/`A<B`→next If) selecting 5 Constant3Vector tints (blue/teal/amber/
    magenta/green). (4) Emissive = window-emissive × tint; BaseColor = Lerp(dark-glass, tint×0.06,
    0.5). Recompile. Rebuild via remove+re-SpawnGraphInstance (descriptor/custom-data won't hot-
    update on a plain re-execute).
  - Districts differ by COLOR; heights vary randomly across the whole grid.

- **2026-06-21 — 15×15 bump + DOWNTOWN-CORE ATTEMPT (reverted), agent `pcg-builder`.**
  Final demo state is **15×15 = 225 buildings** (Blocks `gridExtents` 31000, cellSize 4000;
  volume spawn scale {x:900,y:900,z:250}). Captures: `~/coding/unreal-agent-harness/docs/
  city_final_wide.png` + `city_final_aerial.png`.

  **Downtown-core (radial tallest center) — ATTEMPTED then REVERTED. Read before retrying.**
  Built a radial chain after Rise: `CoreLen(Attribute Vector Op, Length of $Position → CoreDist)`
  → `CoreNorm(Divide CoreDist/CoreRadius)` → `CoreInv(OneMinus)` → `CoreZMul(MulAdd ×3+1)` →
  `CoreApply(Multiply $Scale.Z × CoreZMul)` → Anchor. Verified: CoreLen/CoreNorm/CoreZMul each
  produced 225 valid elements, BUT `CoreApply` produced NO data and the **whole city stopped
  spawning (0 ISM instances)**. Break was at the final `$Scale.Z = $Scale.Z × CoreZMul` write-
  back. Reverted all 8 Core* nodes, reconnected Rise→Anchor.InA, city spawns fine. Lesson: a
  radial multi-node Attribute-Maths chain writing back to `$Scale.Z` after several attribute-set
  joins is fragile via MCP — ALWAYS confirm ISM count > 0 after each execute, not just that
  ExecuteGraphInstance returned empty (it returns empty on this silent failure too).

  **PIN-NAME GOTCHA for Attribute Maths/Vector Op (cost the most time):** the input pin label
  depends on operand sourcing. Operand read from a point PROPERTY/attribute via `inputSource`
  (`$Position`, `$Scale.Z`, `CoreFactor`) → node exposes a single **`In`** pin. Wire a separate
  `Create Constant` (Attribute Set) as the 2nd operand → node exposes **`InA`/`InB`** (+`InC` for
  MulAdd). ClampMin/ClampMax are unary (only `In`, no constant pin) — avoid; instead set the
  divisor to the CORNER distance (≈√2·halfExtent, e.g. 43850 for a ±31000 grid) so `dist/R ∈
  [0,1]` and `1-norm ≥ 0` needs no clamp.

  **ProgrammaticToolset rolls back on error:** a multi-call `execute_tool_script` that throws
  partway leaves the graph UNCHANGED (its AddNode/Connect don't persist). Build graph nodes with
  DIRECT AddNode/ConnectNodePins calls so each persists and you can discover pin names as you go.

  If a downtown core is wanted later, the SAFER route is per-district height applied BEFORE the
  single Rise: branch on DistrictID (Select/Branch by attribute) into Rise variants with
  different scaleMax.z, or a Match-And-Set DistrictID→heightScale — avoids the write-back-to-
  $Scale.Z-after-joins fragility that broke spawning.

  **MCP mechanics confirmed this session:** scene toolset is `editor_toolset.toolsets.scene.SceneTools`
  (NOT `SceneTools.SceneTools`); `CaptureAssetImage`/`CaptureViewport` return huge base64 —
  they blow the context token cap, so they auto-save to a tool-results .txt: decode the
  `returnValue.image.data` (or `.data`) base64 to a PNG with python and Read the PNG.
  `CaptureViewport` REQUIRES the `annotations` object (pass all-zero fields to disable overlays).
  `GetNodeDataView` returns "produced no data" on the FIRST execute (it only ENABLES inspection
  then) — re-execute once and it returns data. The level here is non-OFPA, so `save_actor`
  fails ("not an external actor"); use `AssetTools.save_assets([])` to save the level + all dirty.

## The METHOD — progressive refinement (the demo's "keep going")
The colored boxes are an **intentional intermediate stage**, not the finish — exactly how the
Epic demo works: start with proxy blocks, then keep refining. The pipeline is a ladder; each
rung is a "keep going" pass you can run live on camera:

1. **Footprint / area** — the city outline (spline/volume).
2. **Grid → blocks** — Create Points Grid (cellSize > footprint = streets).
3. **Districts** — Cluster (KMeans) → colored zones (Visualize / per-instance custom-data tint).
4. **Extrude → heights** — Transform Points scaleZ; spawn a PROXY **box** per point. ← *boxes on purpose*
5. **Swap proxy → real building meshes** — point the Static Mesh Spawner palette at actual
   building meshes (varied silhouettes) instead of the Cube. This is the jump from "colored
   boxes" to "buildings."
6. **Streets / roads** — spline → Spline Sampler → Difference (carve roads) → road meshes.
7. **Detail** — per-district HEIGHT (a tall downtown core), rooftop variation, props, richer
   facade materials (ground floors, varied window styles).
8. **Lighting / mood** — time-of-day, exposure, fog → the final beauty pass.

**Where each stage lands you:** stages 1-4 = the "watch it generate" wow (fast, live, proxy
boxes). Stage 5+ = making it look real. **Honest ceiling:** true Matrix-Awakens photoreal
comes from Houdini/Mantle assembling modular kit pieces (NOT replicable via the MCP in a sane
timeframe) — our PCG path reaches a believable *stylized* city. For genuine photoreal, use City
Sample's prebuilt `Small_City` (the walk/drive payoff) rather than trying to PCG it.

**Status (2026-06-21):** STAGE 5 DONE — Cube proxy swapped for 12 real generated tower meshes.
225 varied towers (spires/needles/faceted/tiered), 5 colored districts, windowed glass, grounded,
lit. Reads as a real stylized sci-fi metropolis. Captures: `docs/city_towers_wide.png` (skyline
hero), `docs/city_towers_aerial.png` (3/4, shows the 5 color districts). Proportions tuned in a
finishing pass (see "Stage 5 refinement" below). Per-district downtown core still pending.

## Stage 5 — real tower meshes (2026-06-21, agent `pcg-builder`)
- **Mesh source:** headless Blender job `~/coding/unreal-agent-harness/towers_jobs.py` →
  `assets/futuristic_city/towers/tower_01..12.fbx` (12 varied skyscrapers, base-pivoted).
  Run: `/Applications/Blender.app/Contents/MacOS/Blender --background --python <path>`. Worked
  first try (Blender 5.1.2). Imported via `StaticMeshTools.import_file` → `/Game/PCG/Towers/Tower_01..12`.
- **⚠️ SCALE GOTCHA: FBX imports 100× TOO BIG.** Blender said h=146-560m; UE `get_bounds`
  reported z up to 8,000,000cm (=80,000m) — a 100× blow-up (Blender metres treated as ×100).
  Footprints likewise ±330,000-600,000cm. **Fix = spawn at absolute scale ~0.003** (Rise:
  `bAbsoluteScale:true`, scaleMin/Max ≈0.0024-0.0042) → towers become ~44-336m tall, 16-36m
  footprint, fitting the 40m cells with street gaps. ALWAYS `get_bounds` imported FBXs before
  setting spawner scale.
- **Base-pivoted → NO anchor offset.** These towers have z-min=0 (base at origin), unlike the
  centered Cube. So REMOVE the Anchor node ($Position.Z=Scale.Z×50) entirely and connect
  Rise→Buildings directly — otherwise they float. (Anchor was cube-only.)
- **Palette swap:** set the spawner DefaultSelectorInstance `meshEntries` to the 12 towers
  (weight 1 each, each `descriptor.overrideMaterials=[M_TowerGlass]`). District color custom-data
  + glass material carry over unchanged; verified ISM `NumCustomDataFloats=1` + override present.
  Spawns 12 distinct `ISM_Tower_*` components.
- **DOWNTOWN CORE — STILL BLOCKED by the $Scale.Z write-back (confirmed a 2nd + 3rd time).**
  Tried per-district height as `$Scale.Z = $Scale.Z×(1+DistrictNum×0.35)` via a 2-node
  MulAdd→$Scale.Z. Math is valid but it **silently zeroed the spawn (0 ISM)** — same failure
  class as the radial attempt. ANY mid-graph write to `$Scale.Z` after the district joins kills
  spawning. Reverted; the 12 varied tower meshes already give a 44-336m height spread so the
  skyline reads varied without it. **To actually get a spatial/per-district tall core, do NOT
  write $Scale.Z — instead either (a) per-district MESH selection (PCGMeshSelectorByAttribute on
  DistrictNum → core district gets the tall spire towers, outer gets mid-rise), or (b) split the
  point cloud by district (Filter/Branch), run the core subset through its own Transform Points
  with bigger absolute scale, then Merge before the spawner.** Both avoid the fatal write-back.
- **Honest read:** this is stylized-futuristic (varied sci-fi towers), NOT photoreal-Matrix
  (that's the Houdini/Mantle path). Big jump over the boxes.

### Stage 5 refinement — proportions tuned for a real skyline (2026-06-21, finishing pass)
- The first-pass absolute scale (~0.0024-0.0042 uniform on XYZ) read as a SQUAT low cluster, not
  a skyline (footprint ±900m vastly wider than ~300m tall). **Decouple XY from Z:** XY is the
  binding constraint (must fit the 40m cell), Z runs higher for skyscraper proportions. Final
  Rise params (the keeper — chunky believable towers, hero spires to ~1100m):
  `{"scaleMin":{"x":0.003,"y":0.003,"z":0.005},"scaleMax":{"x":0.004,"y":0.004,"z":0.011},"bAbsoluteScale":true,"bUniformScale":false,"rotationMin":{"pitch":0,"yaw":0,"roll":0},"rotationMax":{"pitch":0,"yaw":360,"roll":0}}`
  - XY ≈0.003-0.004: widest tower (Tower_07, 120m native = 1,201,322cm imported) → ~36-48m, just
    around the 40m cell (a little overlap on the few wide ones = fine for dense downtown);
    typical ~60m towers → 18-24m with street gaps.
  - Z 0.005-0.011: low-Z(≈XY)=squat cluster; high-Z(0.008-0.016)=thin needles; 0.005-0.011 = the
    sweet spot. The 12 meshes' native 146-800m spread × one global scale gives free height variety.
  - yaw 0-360 (full) — towers are closed on all sides.
- **Count verify:** `GetNodeDataView` on Rise (any attr, e.g. "DistrictNum") → `"totalElements":225`.
  (ISM `InstanceCount` is NOT readable via ObjectTools — it errors. Use the node data view, or
  `get_components` type=InstancedStaticMeshComponent to count the 12 `ISM_Tower_*`.) Scale-only
  Rise changes hot-update on a plain re-`ExecuteGraphInstance` — no remove+re-spawn needed (only
  palette/material/custom-data changes need that). First `GetNodeDataView`/post-change execute
  returns "produced no data" — execute once more, then it returns.
- Fresh captures saved: `docs/city_towers_wide.png` (street-level hero skyline) +
  `docs/city_towers_aerial.png` (3/4 aerial showing the 5 contiguous color districts). The
  PCGVolume brush wireframe (faint yellow box) always renders in-editor; deselect actors to dim it.
- Minor: actor bounds z-min ≈ -25,000cm (one leaning/needle tower dips below its base pivot) —
  not visible in renders; left as-is. Tower slot 1 (Frame) has no override material (imported
  import_materials=false) → default; slot 0 glass dominates so it looks right.

## 2026-06-21 — PHOTOREAL PATH FOUND: Epic's shipped PCG building-GRAMMAR generator (agent `real-pcg-iter1`)
**THE BIG FIND.** The PCG plugin ships Epic's real building-assembly generator — the exact "assemble
buildings from modular kit pieces" technique the demo uses. NO need to hand-build a stacker.

- **Generator graph:** `/PCG/SampleContent/Grammar/Graphs/PCG_BuildingSample` (use full object path
  `…PCG_BuildingSample.PCG_BuildingSample` for PCGToolset calls).
- **Wrapped in a ready BP actor:** `/PCG/SampleContent/Grammar/BP_BuildingSample` — has a closed-loop
  Spline (the footprint) + the PCG component. Drop it in via
  `SceneTools.add_to_scene_from_asset` and it **auto-generates a real closed building on spawn**
  (verified: ISM_PCG_Wall / _Column / _Window / _Cube components appear immediately).
- **Supporting graphs/subgraphs:** `Grammar/Graphs/ExtractMeshInfo` (symbol→mesh map), `PCG_SplineSlicer`,
  plus `/PCG/GraphTemplates/TPL_Showcase_ShapeGrammar` and the `EdMode/DrawSpline/…LinearGrammar*`
  tools. Modular sample meshes: `/PCG/SampleContent/Grammar/Assets/PCG_{Wall,Window,HoleWindow,Column}`
  (real StaticMeshes, brick material `Grammar/Materials/PCG_Bricks`).

**How the generator works (the pipeline, top to bottom):**
1. Input = a **closed footprint spline** + graph param `buildingHeight`.
2. `Duplicate Cross-Sections` (VolumeSlicer) slices vertically into FLOORS via a vertical grammar
   `[MainFloor][Intermediate]*` (MainFloor=300cm ground floor, Intermediate=250cm upper floors).
3. `Spline to Segment` → each floor's perimeter edges become segments.
4. `Select Grammar` → picks a horizontal grammar per segment, e.g. `[C][W,W1]*[C]`
   (Corner, then repeating Wall/Window bays, then Corner) — taller ground floor gets a different rule.
5. `Subdivide Segment` → places module SYMBOLS along each segment per the grammar.
6. `Static Mesh Spawner` (`PCGMeshSelectorByAttribute` on the `Mesh` attr) → spawns the real modular
   meshes with correct per-module pivot/scale/rotation (PivotOffset transformed by $Transform, Z scaled
   to floor height). **This closes the box on all 4 sides with proper corners — NOT one-sided panels.**

**Full control surface (all exposed as graph-instance params on `BP_BuildingSample_C.PCG.PCGGraphInstance`,
read/set via `ObjectTools.get/set_properties` on `ParametersOverrides`):**
- `buildingHeight` (cm), `debugFloors`/`debugModules` (bool, **leave OFF** for real meshes),
  `spawnMeshes` (bool, ON).
- `moduleInfo`: array of `{symbol,size,bScalable,debugColor}` — the grammar alphabet. C=Corner(100,
  non-scalable), W/W1/W2=Wall/Window variants (100, scalable).
- `meshInfo`: array of `/Script/Engine.StaticMesh` refs, **positional to the symbols** ([0]→Column/C,
  [1]→Wall/W, [2]→Window/W1, [3]→HoleWindow/W2). **THIS is the photoreal swap point.**

**PROTOTYPE BUILT + CAPTURED (this iteration):** dropped `BP_BuildingSample` at X=200000 in the Startup
level, set a wider footprint (actor scale 8×8×1 → ~21m×19m), debug flags off. Result = a genuine
**closed, multi-floor brick building** with real corners, walls, and round+rect windows on every face.
Captures: `docs/real_iter1_grammar_building.png` (3/4 hero), `docs/real_iter1_grammar_building_close.png`
(top-down into the open box). This is a categorical jump over the cube-extrusion + one-sided-facade work.

**GOTCHAS THIS ITERATION:**
1. **Green tint on the building = the `CopyAttributes_9` node** (`@Data.DebugColor → $Color`) writes the
   module debug color to vertex color, and it runs **even with debugFloors/debugModules OFF**. For a
   clean look, disable that node in the graph (or strip the DebugColor copy) — it's a graph artifact,
   NOT a material/lighting bug. Don't edit the shared sample asset in place; duplicate the graph first.
2. **The grammar builds facade walls only — the box is HOLLOW with no roof** (open top, no floor slabs).
   Fine for a skyline of closed-perimeter buildings; add a roof cap separately if needed up close.
3. **BP-component PCG can't be regen'd via `ExecuteGraphInstance`/`SetGraphInstanceParams`** — those
   require a real `PCGVolume` ("not a valid PCGVolume" error on the BP actor). The BP **auto-regenerates
   on property edit** (the component goes to TRASH_ and rebuilds). To drive it cleanly: change params on
   `…PCG.PCGGraphInstance` `ParametersOverrides`. After a BP reconstruct, earlier component refPaths go
   stale — re-fetch via `ActorTools.get_components`. NOTE: in this pass `buildingHeight=3000` did not take
   on the live regen (stayed 10m) — the override likely got reset by the reconstruct; next iter set the
   param and confirm `get_properties` reads it back BEFORE relying on the regen.
4. **Spline footprint array can't shrink in one `set_properties`** (6→4 pts errors "removed elements
   ambiguous", same class as the meshEntries gotcha). Easiest reshape = SCALE the actor, or append/remove
   one point per call. The default BP spline is already a closed loop (`bIsLooped:true`), just tiny
   (~2.5m) — scale it up rather than rewriting points.

**THE SCALE-TO-A-CITY PLAN (next iteration):**
- **Photoreal swap:** point `meshInfo` at City Sample facade meshes — `[0]` a corner/column piece, `[1]`
  `…/SM_BLDG_CHx_*_Wall_01_N1`, `[2]/[3]` window variants — chosen from the ~125 `SM_BLDG_*_Wall_01_N1`
  across styles A–J (all present, confirmed). MUST also set `moduleInfo` `size` to the real panel width
  (the CH walls are ~325cm wide, base-pivoted, ~300cm/floor) so the grammar subdivides at the right bay
  width, and align `Intermediate`/`MainFloor` slice sizes to ~300cm. Verify pivots: CH walls are base-
  pivoted (min.z=0), which the generator's pivot math already expects.
- **One building per block:** instead of one Static Mesh Spawner of cubes across the grid, generate ONE
  `BP_BuildingSample`-style PCG per block footprint. Either (a) loop the grammar subgraph over many
  footprint splines/points (the demo uses a spline-per-building), or (b) feed the block grid points as
  footprints. Vary `buildingHeight` per point for a skyline (and a tall downtown core — done at the
  footprint/height stage, which AVOIDS the fatal `$Scale.Z`-write-back that killed the cube path).
- **District color** stays as before via per-instance custom data, or just let the photoreal facade
  materials carry the realism (kill the rainbow — use the kit's own materials, no district tint).
- Honest read: this is the real path to photoreal — modular grammar assembly with City Sample's own
  facade meshes and materials. Heavier than cube-extrusion but it's what the demo actually does.

## 2026-06-21 — ITER 2: clean grammar building + the City-Sample-kit-swap WALL (agent `real-pcg-iter2`)
**Result: a genuinely closed, multi-floor BRICK building — debug-tint killed, height fixed, lit, captured.
The CH-kit photoreal swap was attempted and FAILS by design (proven with a capture). The grammar's own
modules are the reliable photoreal path; CH panels are pivot/axis-incompatible.**

Captures (the keepers): `docs/real_iter2_grammar_building.png` (3/4 hero — closed ~16-floor brick tower,
window grid all faces, real corners, ground shadow), `docs/real_iter2_grammar_building_close.png`
(corner close-up — brick courses, recessed framed windows, corner column). Failure evidence:
`docs/real_iter2_chkit_swap_fail.png` (CH meshes in meshInfo → overlapping panels, jagged broken
upper section, irregular grid).

**Graph: duplicated, NOT edited in place.** `AssetTools.duplicate /PCG/SampleContent/Grammar/Graphs/
PCG_BuildingSample → /Game/PCG/PCG_Building_CitySample`. Pointed the existing `BP_BuildingSample_C_0`
actor (Startup level, X≈200000) at it by `set_properties` on `…PCG.PCGGraphInstance` `Graph` =
the dup. The BP auto-regenerates on the change.

**1) GREEN TINT — real cause + the fix that worked.** It is NOT the `CopyAttributes_9` node (that
DebugColor→$Color copy only feeds the `Debug_11` viz branch, not the spawn path). The green came from
**`debugFloors:true`+`debugModules:true`** in the graph's `userParameters` AND the `DebugColor`
attribute being written onto the spawned points (the kit glass/brick materials read vertex `$Color`).
The clean fix (all on the DUP graph):
  - Set `userParameters.debugFloors=false, debugModules=false`.
  - On `VolumeSlicer_5` (Duplicate Cross-Sections) `UpdateNode` → `bOutputDebugColorAttribute:false`.
  - On `SegmentSlicer_27` (Subdivide Segment) `UpdateNode` → `bOutputDebugColorAttribute:false` AND
    `modulesInfoAttributeNames.bProvideDebugColor:false`.
  - Belt+suspenders: set every `moduleInfo[].debugColor` to white `{1,1,1,1}` (vertex color ×1 = no tint).
  Green gone, walls render as plain brick. (Did NOT need to delete CopyAttributes_9.)

**2) buildingHeight OVERRIDE — the method that STUCK (iter1's open bug, now solved).** Setting
`ParametersOverrides.parameters.buildingHeight` on the BP's `PCGGraphInstance` does NOT take —
`propertiesIdsOverridden` stays `[]` so the override is INERT and the regen reads the graph default.
**Fix: set the default on the GRAPH asset's `userParameters` instead** (`ObjectTools.set_properties`
on `/Game/PCG/PCG_Building_CitySample.PCG_Building_CitySample` → `{"userParameters":{...,"buildingHeight":4500,...}}`),
then force ONE regen (any `UpdateNode`/graph edit triggers it). Verified: `ActorTools.get_actor_bounds`
Z-max went 1300→4300cm (= 300 MainFloor + 16×250 Intermediate ≈ the 4500 request → ~16 floors).
**CONFIRM via get_actor_bounds AFTER the regen — a userParameters set with no subsequent regen does NOT
apply (the first set looked applied on read-back but bounds were still the stale 1300).** The BP
component goes to `TRASH_…` on every regen, so re-fetch components via `ActorTools.get_components`.

**3) THE CITY-SAMPLE KIT SWAP HITS A WALL — root cause (categorical, not tunable).** The generator's
`ExtractMeshInfo` subgraph computes each module's horizontal **`Size = $Extents.X × 2`** and
`PivotOffset = -$LocalCenter`, i.e. it assumes the facade panel's WIDTH runs along local **X**, centered,
base-pivoted in Z (exactly the native `PCG_Wall`: X ±100 = 200cm wide, Y ±10 thin, Z 0..300).
**City Sample CH `_Wall_01_N1` panels carry their 325cm width on the Y axis** (bounds X −63.7..20.8 ≈ 84cm
shallow depth, **Y −325..0** = the real width, edge-pivoted at Y=0, Z 0..300). So the generator reads
the CH panel's width as ~84cm (its X depth) and leaves the 325cm Y-span sticking perpendicular out of the
facade. Result = overlapping/rotated panels, broken grid (see the fail capture). `meshInfo` is just a
positional StaticMesh-ref array — it exposes **no per-mesh rotation/pivot correction**, and the grammar
has no hook to say "this module's width is on Y." Setting `moduleInfo.size=325` doesn't help — Size is
recomputed from mesh bounds inside ExtractMeshInfo regardless. CH materials DO resolve to real photoreal
MIs (e.g. `MI_CHA_L10_A_Wall_01_1`, slots Bldg_block_limestone_beige / _glass / _paintedMetal_black), so
the look is there — only the assembly is broken.
  - **To actually use the CH kit you must FIRST make X-aligned, X-centered copies** of the panels
    (re-import each CH mesh rotated 90° about Z so width→X, re-pivot to center), then point `meshInfo` at
    those. That's an FBX/Blender re-export per panel (no in-editor mesh-rotate tool exposed) — deferred;
    heavier than its payoff for one iteration. The kit is confirmed present & complete (Wall/Column/
    CornerEx/CornerIn/CornerEx{L,R}/CornerIn{L,R} per kit, ~125 `_Wall_01_N1` across styles A–J, all with
    base-pivot min.z=0 and real per-kit MIs).

**4) GRAMMAR MESH SYMBOL MAP (verified, for when X-aligned meshes exist).** `moduleInfo` symbols
C/W/W1/W2 map POSITIONALLY to `meshInfo[0..3]` = Column/Wall/Window/HoleWindow. The native sample meshes:
PCG_Wall X±100 base-pivot, PCG_Column X/Y±12.5 base-pivot, **PCG_Window is Z-CENTERED (−150..150)** not
base-pivoted. Vertical grammar = `[MainFloor][Intermediate]*` (MainFloor 300cm, Intermediate 250cm).
Horizontal grammar (Select Grammar, by floor): ground `[C][W,W1]*[C]`, upper `[C][W1]*[W2][W1]*[C]`.

**5) LIGHTING/EXPOSURE that read well (Startup map already had Sun+SkyAtmosphere+SkyLight).** Left the
DirectionalLight at intensity **10** (jumping it to 75000 + auto-exposure = pure white). Added an unbound
`PostProcessVolume` (`bUnbound:true`) with **manual** exposure: `AutoExposureMethod:AEM_Manual`,
`AutoExposureApplyPhysicalCameraExposure:false`, `AutoExposureBias:-1.0`. **Sign gotcha: in AEM_Manual,
LOWER-magnitude bias = BRIGHTER** (−1.0 daytime-bright; −2.5 dusk; −3.8 darker; **+11 → "Exposure −11,
safe range [−8,12]" = blown white**). The earlier dark captures were just auto-exposure failing to lift
the weak sun — manual exposure fixed it. Capture pipeline unchanged from iter1 (CaptureViewport base64 →
decode to PNG → Read).

**NET for the scale-to-a-city plan:** the generator + its OWN modules is the proven, reliable one-building
unit (closed box, real masonry, per-footprint height via `userParameters.buildingHeight`). The
City-Sample photoreal upgrade needs pre-rotated kit meshes — do that ONCE (a batch FBX re-export to
X-centered pivots) before relying on the kit swap. Per-block height for a downtown core stays at the
footprint/buildingHeight stage (one BP/PCG per block footprint), which AVOIDS the fatal `$Scale.Z`
write-back that killed the cube path.

## 2026-06-21 — ITER 3: ONE grammar building → a 5×5 CITY with a downtown core (agent `pcg-scale-city`)
**Result: 25 closed brick grammar buildings on a real block grid with street gaps, height stepping
down from a tall central tower to a low outer ring (concentric downtown core). No editor freeze.
Captures (the keepers): `docs/real_iter3_wide.png` (street-level skyline hero) + `docs/real_iter3_aerial.png`
(3/4 aerial showing the 5×5 grid + core falloff).**

**THE MECHANISM THAT WORKED — grid of BP actors, each pointed at a height-TIER duplicate graph.**
Chose actor-grid (b) over a per-footprint PCG graph (a) because per-actor height is the crux and the
ONLY proven-reliable height control is the GRAPH asset's `userParameters.buildingHeight` default (iter2).
So: make N duplicate graphs, each a different height, and assign each block the tier for its ring.
  - **Why NOT a single graph + per-actor override:** the BP's `PCG.PCGGraphInstance.parametersOverrides`
    holds a `buildingHeight` value but `propertiesIdsOverridden` stays `[]` → the override is INERT
    (confirmed again this iter). Populating it needs the param's PropertyBag GUID, which the MCP property
    tools don't expose (FInstancedPropertyBag descriptors aren't in the JSON; the sandboxed Python only
    orchestrates registered tools, no raw reflection). Per-tier-graph sidesteps the GUID entirely.
  - **Tiers built:** duplicated `/Game/PCG/PCG_Building_CitySample` → `/Game/PCG/Tiers/PCG_Bldg_T{0,1,2}_*`,
    set each graph's `userParameters.buildingHeight` to 3000 / 7500 / 13000 cm (≈10 / 26 / 44 floors)
    via `ObjectTools.set_properties` (pass the FULL userParameters bag as the `values` JSON STRING —
    `set_properties` takes `instance` + `values:string`, NOT a `properties` dict). Saved the tier assets.

**THE PER-ACTOR HEIGHT RECIPE (copy verbatim):**
  1. `SceneTools.add_to_scene_from_asset('/PCG/SampleContent/Grammar/BP_BuildingSample', name, xform)`
     at the block position, scale `{x:8,y:8,z:1}` (→ ~21×18m footprint). The BP auto-generates its
     building on spawn using its DEFAULT graph.
  2. Switch the actor's graph: `ObjectTools.set_properties` on
     `<actor>.PCG.PCGGraphInstance` with `values='{"graph":{"refPath":"<tier graph .Asset path>"}}'`.
     **Setting `graph` AUTO-TRIGGERS a regen** to the tier's height — verified: bounds Z-max jumped
     to the tier value (e.g. 12800 for the 13000 tier). This is the clean per-block height knob.
  3. The auto-regen is **ASYNC** — a `get_actor_bounds` read in the SAME tight script loop returned the
     pre-regen zmax (128 = just the billboard). Read bounds in a SEPARATE later call (a few seconds /
     a follow-up tool call later) and they're correct. ⚠️ Don't conclude "silent failure" from a low
     zmax read immediately after the graph swap — wait, re-read.

**GRID LAYOUT (5×5, spacing 4000cm):** cell centers `(i-2)*4000, (j-2)*4000` for i,j∈0..4, with a
per-actor offset `(-940,-87)` to center each footprint in its cell (the grammar footprint extends +X
and ±Y from the actor origin, not symmetric). ~2100cm building + ~1900cm street gap = clean block grid.
**Downtown core = ring-based tier:** `ring = max(|i-2|,|j-2|)` → ring0(center)=T2_Tall(13000),
ring1=T1_Mid(7500), ring2(edge)=T0_Short(3000). Verified all 25: center 12800, 8× mid 7300, 16× edge
2800, each with 4 `ISM_PCG_*` components (Column/Wall/Window/HoleWindow = closed building), zero empties.

**SPAWN ALL 25 IN ONE `execute_tool_script`** (spawn + set_graph + bounds per building, serial inside
the script) — no freeze. The grammar gen is heavy but serial-in-script is safe; concurrent
ExecuteGraphInstance is what freezes, and the BP path doesn't use that (it auto-regens on property edit).
**Gotcha: the spawn returns the real refPath (`BP_BuildingSample_C_N`), NOT a label-based path.** A
`get_actor_bounds` on `...PersistentLevel.<label>` errors "not valid Actor" — use the returned refPath,
or `SceneTools.find_actors(name='CityBldg')` to re-collect them (they keep the class-instance name).

**LIGHTING/EXPOSURE for the BRICK city (different sweet spot than the glass-cube city!):** the glass
city's `sun=10 / AEM_Manual EV -1` renders the BRICK masonry too dark/murky. **Keeper = DirectionalLight
intensity 12 + unbound PostProcessVolume AEM_Manual `AutoExposureBias = 0.5`.** Calibration ladder this
iter: sun=10/EV-1 → dark brown; sun=6000/EV-1 → blown pure white (the iter2 "high sun + low-mag EV =
blown" warning holds); sun=12/EV+2 → washed/pale low-contrast; **sun=12/EV+0.5 → warm detailed brick,
visible window grids, real asphalt ground, blue sky (the keeper).** `ObjectTools.set_properties` on the
PPV with a partial `Settings:{bOverride_AutoExposureBias:true,AutoExposureBias:0.5}` MERGES (doesn't wipe
the other overrides) — verified read-back. Ground plane ("Ground", ±250m asphalt at Z=0) + Sun/SkyAtmo/
SkyLight already in the Startup map from prior passes; reused as-is.

**Scene cleanup:** removed the OLD cube/tower `PhotorealCity_*` PCGVolume actor (12 ISM_Tower components
overlapping ±90000cm) so the grammar grid is the only city — it's recoverable from `/Game/PCG/PCG_PhotorealCity`.

**CAPTURE plumbing unchanged:** `CaptureViewport` REQUIRES `captureTransform` (no default — passing only
`annotations` errors "captureTransform needs a default value"); pass the same pose you set. Output blows
the token cap → auto-saves to a tool-results .txt; `json.loads` it and base64-decode `returnValue.image.data`
to a PNG. **Tell from the .txt SIZE:** ~200KB = near-solid (blown white) image; 2.5-3.7MB = full detail.
Deselect all actors (`EditorAppToolset.SelectActors([])`) before capture to drop gizmos/brush wireframe.

**HONEST VISION READ vs a real / demo city:**
  - ✅ Reads clearly as a real city block grid with a downtown core — the concentric height falloff
    (tall center → low edges) is exactly the demo's silhouette, and the aerial shows a clean 5×5 grid
    with streets between blocks.
  - ✅ Buildings are genuinely closed multi-floor brick masonry (real corners, window grids on all faces)
    — categorically better than the one-sided facade panels and the colored cubes.
  - ⚠️ Proportions skew SLAB/thin: at scale-8 footprint (~21m) with up to ~128m height, several towers
    read as narrow slabs rather than chunky mid-rise. Next iter: widen footprints (scale 10-12, OR
    non-square scale) and/or trim the tall tier to ~9000cm for believable downtown proportions.
  - ⚠️ Monotone material — every building is the SAME brick. A real city varies facade color/style.
    The grammar's `meshInfo`/materials are identical across all 25. Variety is the biggest realism lever left.
  - ⚠️ No roads/sidewalks (just gaps over flat asphalt) and no rooftops (grammar boxes are open-top,
    not visible from these angles but would show from directly above / up close).

**PERF / counts:** 25 buildings × ~4 ISM = ~100 ISM components; tallest ~44 floors. Generation was
smooth, no freeze, all via serial MCP calls. A grammar building is HEAVY (per-floor slice + per-segment
subdivide + hundreds of module instances each), so a 10×10=100 grid is ~4× this load — likely fine but
untested; scale up incrementally and verify ISM counts + no-freeze after each batch rather than
spawning 100 in one shot.

**WHAT THE NEXT ITERATION SHOULD PUSH (priority order):**
  1. **Variety** (biggest realism win): give the tiers different `meshInfo` palettes / materials (e.g.
     2-3 brick/stone/concrete variants), and/or randomize `buildingHeight` per block within its tier
     (make more tier graphs, or jitter footprint scale) so the skyline isn't a clean pyramid of clones.
  2. **Proportions:** widen footprints (scale ~10-12) and cap the tall tier ~9000cm for chunkier towers.
  3. **Scale up** to 7×7 / 10×10 using the exact same actor-grid+tier recipe (verify counts/perf per batch).
  4. **Roads:** carve street meshes / sidewalks into the gaps (Stage E spline → road meshes).
  5. Photoreal facade swap (the CH-kit re-pivot job from iter2) once variety + proportions read well.

  **Tier graphs (saved):** `/Game/PCG/Tiers/PCG_Bldg_T0_Short` (3000), `_T1_Mid` (7500), `_T2_Tall` (13000).
  **City actors:** `BP_BuildingSample_C_2..C_26` in `/Game/Map/Startup/Startup`. Level + assets saved.

## 2026-06-21 — ITER 4: THE CONVERGENCE — BRICK grammar city → FUTURISTIC GLASS city (agent `pcg-futuristic-fuse`)
**Result: the working 5×5 grammar city is now a sleek GLASS downtown. Swapped the grammar's native
brick modules for the futuristic curtain-wall kit, applied `M_TowerGlass`, widened footprints to chunky
proportions, capped the tall tier, and tuned dusk exposure so the glass glows. All 25 buildings still
generate closed (3 ISM each), zero empties. Captures (keepers): `docs/real_iter4_wide.png` (street-level
glass-skyline hero, blue-hour) + `docs/real_iter4_aerial.png` (3/4 aerial — 5×5 grid + lit downtown core).**

**1) FBX IMPORT — the NOTES.md "imports 1:1, no 100× bug" claim was WRONG; fixed at the source.** The
futuristic kit (`~/coding/unreal-agent-harness/assets/futuristic_kit/*.fbx`, builder
`futuristic_kit_jobs.py`) exported with `FBX_SCALE_NONE` but Blender's default scene unit is METERS, so
the cm-magnitude geometry got tagged as meters → UE multiplied ×100 on import (a 400cm module came in at
**40000cm = 400m**; `ExtractMeshInfo` would then read Size=40000 and tile modules 400m apart). FIX (in the
builder, no geometry change): set `scene.unit_settings.system='METRIC', scale_length=0.01,
length_unit='CENTIMETERS'` and export with `apply_scale_options='FBX_SCALE_ALL', apply_unit_scale=True`.
Re-ran the builder, re-imported → bounds now true cm (corner −200..200 X / 0..400 Z, window −200..200 /
0..400). **Lesson: ALWAYS get_bounds 1-2 modules right after import; do NOT trust an FBX's "1:1" claim.
If 100× too big, fix the Blender scene UNIT (not ImportUniformScale — there's no MCP reimport tool).**

**2) MATERIAL SLOTS — the kit imports with only ONE slot (`M_Glass`), not the 2 (Glass+Frame) NOTES
claimed.** The FBX export collapsed the two Blender materials to one on UE import. So you CANNOT
slot-split glass vs frame in-editor. Pragmatic call: apply `/Game/PCG/M_TowerGlass` to the single
`M_Glass` slot on all 5 modules (`StaticMeshTools.set_material(mesh, 'M_Glass', M_TowerGlass)`) → the whole
module reads as one glass curtain wall; the mullion/frame detail still reads because it's GEOMETRIC (proud
bars cast self-shadow). M_TowerGlass is **opaque DefaultLit** (not translucent) → no sort issues, reads as
solid reflective glass. (If you later want frame contrast, re-author the kit as separate Glass + Frame
meshes, or bake the 2-material split into vertex color the grammar won't overwrite.)

**3) meshInfo SWAP (the core fuse) — works cleanly because the kit matches the X-centered/base-pivot spec.**
On each tier graph set the FULL `userParameters` bag (`set_properties` `values` = JSON STRING) with
`meshInfo = [mod_corner (C), mod_wall (W), mod_window (W1), mod_window (W2)]` (W1 and W2 reuse mod_window).
Kept `debugFloors/debugModules=false` and `moduleInfo[].debugColor` white (no vertex-tint bleed — the iter2
green-tint gotcha). Set `moduleInfo[].size=400` for editor readability (inert — Size is recomputed from
Extents.X=200 anyway). **Result: the grammar assembled the kit with ZERO axis/scale breakage** (unlike the
City-Sample CH kit in iter2) — proving the "width on X, centered, base-pivoted" authoring is the whole game.
**ISM naming changed:** components are now `ISM_mod_corner_0 / ISM_mod_window_0 / ISM_mod_wall_0` (named per
MESH), NOT `ISM_PCG_*`. A closed building = **3 ISMs** here (corner+wall+window), because W1=W2=mod_window
share one ISM. ⚠️ Update any verify filter from `'ISM_PCG'` to `'ISM_mod'` or you'll false-alarm "0 ISM /
all empty" (I did, briefly — the buildings were fine).

**4) PROPORTIONS — widen footprints via ACTOR SCALE (more bays), cap the tall tier.** iter3 towers were
slabs (~21×18m footprint × up to 128m). Two fixes: (a) bumped every actor scale 8→**13** → footprint
**~34×29m** (the grammar adds more bays, it does NOT stretch the 400cm module — confirmed: module count
goes up, module size stays); (b) capped tiers **T2 13000→9000, T1 7500→6000, T0 stays 3000** (center now
~88m not 128m → ~3:1 chunky tower, believable downtown). **Recentering when you rescale:** the per-actor
centering offset scales with actor scale — `offset=(-940,-87)*S/8`; applied via one `execute_tool_script`
over all 25, then verified bounds-center ≈ cell-center (±50cm). Spacing 4000cm with a 34m footprint leaves
~5-6m streets (dense-downtown tight, still clean gaps).

**5) THE HEIGHT-CAP REGEN GOTCHA (important, cost two wasted regen passes).** Changing a tier GRAPH's
`buildingHeight` default does NOT propagate to already-spawned actors that reference it — they cache the
height at their last regen. AND re-setting an actor's `graph` to the SAME tier it already holds does NOT
trigger a regen (no property delta). **The reliable force-regen = TOGGLE the graph ref to a DIFFERENT graph
then back:** set every actor's `PCG.PCGGraphInstance.graph` to the base `PCG_Building_CitySample`, sleep ~3s,
then set it back to its ring tier — each set is a real delta so each fires a fresh regen that re-reads the
now-capped height. Verified after: ring0 zmax 8800, ring1 5800, ring2 2800 (≈ the 9000/6000/3000 caps).
(Changing the actor TRANSFORM also regens the footprint, but it reuses the cached height — so transform
alone won't apply a new tier height.)

**6) LIGHTING/EXPOSURE for GLASS — dusk/blue-hour, NOT the brick daytime setting.** The brick keeper
(sun 12 / AEM_Manual EV +0.5) renders the reflective glass as flat blown-WHITE silver (glass is bright in
full day; the window grid reads but the city looks washed). Dropping exposure uniformly to EV -0.5 barely
helped (scene + sky darken together, relative contrast unchanged). **Keeper = both unbound PostProcessVolumes
at AEM_Manual `AutoExposureBias = -1.5`** → a twilight city where the glass curtain walls GLOW against a
darkened dusk sky/ground, window grids crisp and luminous, downtown-core silhouette pops. (Sign rule from
iter2/3 still holds: lower-magnitude bias = brighter; -1.5 = dusk-dark. There are TWO unbound PPVs in the
Startup map — set BOTH to the same bias or they fight.) Reflective opaque glass wants a darker key than
diffuse brick — that's the whole lesson.

**HONEST VISION READ vs a real futuristic city / the demo:**
  - ✅ It genuinely reads as a FUTURISTIC GLASS city now — sleek curtain-wall towers with lit window grids,
    a clear downtown core (tall glowing center → mid ring → low edges), clean 5×5 block grid with streets.
    Categorically past the brick city and miles past the colored cubes. The dusk glow sells "sci-fi skyline."
  - ✅ Proportions fixed — chunky blocky towers, not iter3's needles/slabs. The cap + wider footprint worked.
  - ✅ The grammar+kit fuse is ROBUST: zero axis/scale breakage, all 25 closed, no freeze (serial MCP only).
  - ⚠️ MONOTONE — every tower is the SAME glass module set. A real futuristic city varies facade
    treatment (spandrel ratios, tints, setbacks, crowns, a few signature towers). Biggest realism lever left.
  - ⚠️ Single-material glass — no frame/metal contrast (the import collapsed slots). Re-authoring the kit as
    separate Glass + Frame meshes (or 2 real UE slots) would add depth/legibility to the facades.
  - ⚠️ FLAT TOPS + no crowns/setbacks — grammar boxes are open-top, so towers end abruptly (visible from the
    aerial). Real skylines vary rooflines. And still no roads/sidewalks (flat asphalt gaps) — Stage E next.
  - ⚠️ Reflections are skylight-driven (Lumen), no SSR cubemap detail / no emissive interior lighting, so
    the glass glows uniformly rather than showing varied lit/dark windows like a real night tower.

**NEXT LEVER (priority):** (1) VARIETY — 2-3 facade material variants (tints) and/or per-block height jitter
within a tier; a couple signature towers (different module mix). (2) ROOFLINE — add a crown/cap module or
vary top floors (setbacks) so towers don't end flat. (3) Frame/glass 2-material kit re-author for facade
depth. (4) Roads/sidewalks in the gaps (Stage E spline → road meshes). (5) Scale up 7×7/10×10 (same
actor-grid+tier recipe; verify ISM counts + no-freeze per batch). (6) Night/emissive-window pass for a true
sci-fi-at-night look.

  **Futuristic kit (imported, M_TowerGlass on slot 0):** `/Game/PCG/FuturisticKit/{mod_corner,mod_wall,
  mod_window,mod_column,mod_window_ground}` (true cm, X-centered, base-pivoted, 1 slot `M_Glass`).
  **Tier graphs (updated heights, futuristic meshInfo):** `_T0_Short` (3000), `_T1_Mid` (6000), `_T2_Tall` (9000).
  **City actors:** `BP_BuildingSample_C_2..C_26`, scale 13, in `/Game/Map/Startup/Startup`. Level + assets saved.

## 2026-06-21 — ITER 5: VARIETY + SCALE — 5×5 monotone glass → 7×7 (49) MULTI-TINT downtown (agent `pcg-variety-scale`)
**Result: the two biggest realism gaps from iter4 (MONOTONE + small) are closed. The glass city now has
5 distinct facade tints scattered across a 7×7=49 grid, a ring-based downtown core with TWO signature
hero towers, and 5 height levels. All 49 buildings generate closed (3 ISM each), ZERO empties, no freeze.
Captures (keepers): `docs/real_iter5_wide.png` (street-level multi-tint skyline, blue-hour) +
`docs/real_iter5_aerial.png` (3/4 aerial — the 7×7 grid + color scatter + core falloff, the hero shot).**

**THE VARIETY MECHANISM (the #1 lever — fully solved). Tint can't be per-building via meshInfo because
the grammar's `meshInfo` is a bare `[{refPath}]` StaticMesh array with NO overrideMaterials hook — the
tint lives on the SHARED kit mesh's `M_Glass` slot (set_material), shared across every building. So
per-building tint = per-tint COPIES of the kit meshes + per-tier-graph meshInfo pointing at the right set.**
  1. **Parameterized M_TowerGlass** (was hardcoded constants → no MI variety possible). Added two
     VectorParameters and multiplied them into the outputs (non-destructive, default white = old look):
     - `WindowTint`: new `MaterialExpressionVectorParameter` (default 1,1,1,1) → `Multiply` AFTER the old
       emissive chain (old `Multiply_5` → new `Multiply_7.A`, WindowTint → `.B`, `Multiply_7` → MP_EmissiveColor).
     - `GlassTint`: same pattern on base color (old `LinearInterpolate_0` → new `Multiply_8.A`, GlassTint →
       `.B`, → MP_BaseColor). Then `MaterialTools.recompile`. Verify with
       `MaterialInstanceTools.list_parameters` (must show WindowTint + GlassTint as Vector).
     - Set param name + default via `ObjectTools.set_properties` on the expression node:
       `values='{"ParameterName":"WindowTint","DefaultValue":{"r":1,"g":1,"b":1,"a":1}}'`.
  2. **4 MaterialInstanceConstants** via `MaterialInstanceTools.create(folder,name,parent=M_TowerGlass)` in
     `/Game/PCG/GlassTints/`: `MI_Glass_{Blue,Teal,Amber,Silver}`. Set tints with
     `set_vector_parameter(instance,"WindowTint"|"GlassTint",{r,g,b,a})`. Tasteful (NOT rainbow) values that
     read at dusk (window glow multiplies an already-warm emissive, so push the hue but keep ~1.0-1.5 mag):
     Blue Window(0.4,0.6,1.4)/Glass(0.7,0.85,1.4); Teal W(0.35,1.1,1.05)/G(0.55,1.1,1.05);
     Amber W(1.5,1.0,0.5)/G(1.25,0.95,0.65); Silver W(1.1,1.15,1.3)/G(1.0,1.05,1.25). The base
     `M_TowerGlass` (untinted warm) is the 5th palette → 5 distinct looks.
  3. **Per-tint mesh sets:** duplicated the 3 USED kit meshes (corner/wall/window — W1=W2 reuse window) per
     tint into `/Game/PCG/FuturisticKit/Tints/<Tint>/mod_*_<Tint>` and `StaticMeshTools.set_material(dst,
     "M_Glass", MI_<Tint>)`. 4 tints × 3 meshes = 12 duplicates (Warm stays the base kit). One
     `execute_tool_script` (AssetTools.duplicate + StaticMeshTools.set_material), all 12 succeeded.

**THE TIER-GRAPH MATRIX (variety + height in ONE knob — extends iter3/4's per-tier-graph height recipe).**
Because the only proven-reliable per-building height control is the GRAPH asset's
`userParameters.buildingHeight` (iter2/3), and tint is now also graph-scoped (via meshInfo), I baked BOTH
axes into a set of tier graphs and assign each block one graph:
  - **15 graphs** `/Game/PCG/CityTiers/PCG_B_<Tint>_<Height>` = 5 tints × 3 heights {Short 3000, Mid 6000,
    Tall 9000} + **2 signature** `PCG_B_Silver_Signature` (16000) & `PCG_B_Blue_Signature` (14000).
  - Each built by `AssetTools.duplicate('/Game/PCG/PCG_Building_CitySample', dst)` then ONE
    `ObjectTools.set_properties(dst_inst, {"userParameters":{...,"buildingHeight":H,"moduleInfo":<4 white-
    debug entries>,"meshInfo":[corner,wall,window,window for that tint]}})` (values = JSON STRING; pass the
    FULL userParameters bag — set_properties only overrides keys you pass and won't clear stale ones).
  - **Assignment (7×7, i,j∈0..6, center (3,3)):** `ring=max(|i-3|,|j-3|)`. ring0→Silver_Signature;
    designated cells (2,3)&(4,3)→Blue_Signature; else height by ring (ring1 Tall / ring2 Mid / ring3 Short)
    and **tint = TINTS[(i*3+j*2)%5]** ([Warm,Blue,Teal,Amber,Silver]) — the `(i*3+j*2)%5` scatter gives
    good adjacent-cell color contrast (no two-neighbour clumps). Result reads as a real varied skyline.

**SPAWN RECIPE (49 buildings, batched, copy verbatim) — same actor-grid+tier path as iter3/4:**
  1. Removed the old 25 (`remove_from_scene` on `BP_BuildingSample_C_2..C_26`) in one script.
  2. Per building: `SceneTools.add_to_scene_from_asset('/PCG/SampleContent/Grammar/BP_BuildingSample',
     name, xform)` at cell center `((i-3)*4000, (j-3)*4000)` + per-actor centering offset `(-940,-87)*S/8`
     (S=13 → ~34×29m footprint, 4000cm spacing = tight ~5-6m downtown streets), scale {13,13,1}; then
     `ObjectTools.set_properties(<actor>.PCG.PCGGraphInstance, {"graph":{"refPath":<tier graph .Asset>}})`
     — on a FRESH spawn (default base graph) this is a real delta so it auto-regens to the tier's
     height+tint. (No toggle needed here — that's only for re-applying a CHANGED height to an actor already
     on that same tier, iter4 gotcha #5.)
  3. **Batched 21 + 28** (rows i=0-2, then i=3-6) with a count+freeze check between. NO freeze at 49; a
     grammar building is heavy but serial-in-script spawn is safe (concurrent ExecuteGraphInstance is what
     freezes, and the BP path doesn't use it). 49 was smooth — 10×10=100 is likely fine but still untested.
  4. **VERIFY after each batch** (don't trust ExecuteGraphInstance returning empty — silent fails read empty
     too): loop `ActorTools.get_components`, count `ISM_mod*` per actor; flag any with 0. Result: 49/49 with
     3 ISM each, 0 empty. Bounds confirm the falloff: center 15800cm → blue-sig 13800 → ring1 8800 →
     ring2 5800 → ring3 2800. **ISM names carry the tint** (`ISM_mod_corner_Blue_0` etc.) — handy proof the
     right mesh set spawned; a Warm building's ISMs are the un-suffixed `ISM_mod_corner_0`.

**HONEST VISION READ vs a real futuristic city / the demo:**
  - ✅ **Monotony GONE.** The skyline now has clear tasteful color variety — blue, teal/cyan, silver/white,
    amber, warm towers scattered across the grid (obvious in both captures, striking from the aerial). This
    was iter4's #1 gap and it's closed. Reads as a believable big varied glass city, not a clone farm.
  - ✅ Bigger + denser — 49 vs 25, clean 7×7 block grid with streets, downtown core with TWO signature hero
    towers (158m + 138m) over a tall ring stepping down to a low outer ring. The core silhouette pops.
  - ✅ Robust: all 49 closed (3 ISM), zero empties, no freeze; the variety+height tier-graph matrix is a
    reliable single knob per block.
  - ⚠️ **Pronounced floor BANDING** — the grammar repeats a per-floor module so towers read as stacked
    horizontal plates/slabs rather than smooth curtain walls (very visible at street level). Biggest look
    gap now. Fixes: taller `Intermediate` floor slice (fewer, taller bands), a spandrel/vertical-mullion
    module, or a 2-material kit so glass vs floor-line reads as depth not stripes.
  - ⚠️ Street-level foreground is a touch DIM at the dusk EV -1.5 (the aerial reads better). Glass wants the
    dark key (iter4), but the short outer towers lose detail — a +0.3-0.5 EV nudge OR brighter window
    emissive on the Short tier would lift them without washing the hero glass.
  - ⚠️ Still FLAT TOPS / no crowns or setbacks (grammar boxes open-top), and no roads/sidewalks (flat
    asphalt gaps). Rooflines + Stage-E roads are the next silhouette/ground levers.

**NEXT LEVER (priority):** (1) KILL THE BANDING — taller floor slices or a spandrel module / 2-material kit
(biggest remaining look win). (2) ROOFLINE — crown/setback module so tops aren't flat. (3) Scale 10×10=100
(same recipe; verify counts/no-freeze per batch). (4) Roads/sidewalks in the gaps (Stage E). (5) Slight
exposure/emissive lift for the short outer ring. (6) Night/emissive lit-vs-dark-window pass.

  **Assets (all saved):** material params on `/Game/PCG/M_TowerGlass` (WindowTint+GlassTint); tint MIs
  `/Game/PCG/GlassTints/MI_Glass_{Blue,Teal,Amber,Silver}`; per-tint meshes
  `/Game/PCG/FuturisticKit/Tints/<Tint>/mod_{corner,wall,window}_<Tint>`; 17 tier graphs
  `/Game/PCG/CityTiers/PCG_B_*`. **City actors:** `BP_BuildingSample_C_27..C_75` (49), scale 13, named
  `CityBldg_<i>_<j>`, in `/Game/Map/Startup/Startup`. Level + assets saved.

## 2026-06-21 — ITER 6: KILL THE FLOOR BANDING + roads/ground (agent `pcg-banding-roads`)
**Result: the iter5 stacked-plate / waffle look is GONE — towers now read as smooth glass curtain
walls with vertical-pinstripe mullions and only a faint floor line. Added a light plaza ground +
dark road grid so the city sits on real streets, not void. All 49 still closed (3 ISM each, 147
total, zero empties), no freeze. Captures (keepers): `docs/real_iter6_wide.png` (street-level
glass-curtain-wall hero + foreground road strips) + `docs/real_iter6_aerial.png` (3/4 — 7×7 grid,
core, 5 tints, road grid). BEFORE baselines kept: `docs/_iter6_before_street.png` +
`docs/_iter6_before_aerial.png` (the waffle banding).**

**THE ROOT CAUSE OF THE BANDING WAS THE MATERIAL, NOT THE GEOMETRY (the key finding).** The plate
look came from `/Game/PCG/M_TowerGlass`'s procedural window-grid, which paints a window cell every
~350cm(X) × ~450cm(Z) via `WorldPosition → mask → ×(1/tile) → Frac → bias-0.5 → Abs → SmoothStep →
OneMinus` (one chain per axis). The **Z chain (mask B = worldZ, `SmoothStep_2`)** drew a FAT
horizontal mullion (dark band) at every ~450cm = the "floor plates," independent of the mesh. The
fix that worked:
  - **Widen the Z SmoothStep window so the horizontal mullion becomes a THIN line:**
    `SmoothStep_2.constMin 0.28→0.46, constMax 0.40→0.49` (mullion now occupies only the outer ~2-4%
    of each cell → thin floor line, glass continuous between). This is THE lever.
  - **Slim the X SmoothStep a touch** (`SmoothStep_1.constMin 0.30→0.40, constMax 0.42→0.47`) so the
    vertical mullions read as slim pinstripes (kept — they align across floors = tall read), not
    chunky bars. `MaterialTools.recompile` after; **no city regen needed** — a material edit is a
    shader recompile and the ISMs already reference the material. (To find which SmoothStep is Z:
    trace `get_expression_inputs` back from each SmoothStep through Abs→CBS→Frac→Multiply→ComponentMask;
    the one whose mask reads channel **b** (worldZ) is the horizontal-banding one. Read the tiling
    via `Constant_0`=1/350≈0.00286 (X) / `Constant_1`=1/450≈0.00222 (Z). SmoothStep const props are
    `constMin`/`constMax`.)

**ALSO re-authored the kit geometry to continuous glass (`futuristic_kit_jobs.py`) — secondary but
correct.** Old `m_window` had a full frame RING (left/right jambs + a 16cm head bar AND a 16cm sill
bar) + a mid transom; stacked, the sill of floor N met the head of floor N+1 = a ~32cm double dark
band per join. Rebuilt `m_window` (and `m_wall`) as: glass runs the FULL module height edge-to-edge
in Z (no head/sill/transom), vertical jambs + center mullion full-height, and only ONE thin 6cm
spandrel line at the very top → a single thin floor join when stacked. `m_wall` likewise dropped its
horizontal glass strip-band for full-height vertical glass ribbons + a thin top spandrel. (The
material fix alone removed most of the banding; the geometry rebuild reinforces it and removes the
proud-bar shadow lines.)

**THE RE-IMPORT TRAP THAT COST THE MOST TIME — deleting a mesh NULLS the hard `meshInfo` refs.**
`StaticMeshTools.import_file` REFUSES to overwrite an existing asset ("already exists"), so to swap
geometry you must delete-then-import at the same path. BUT the grammar tier graphs store
`userParameters.meshInfo` as **hard `StaticMesh*` pointers, not soft paths** — deleting the meshes
turned every tier graph's `meshInfo` into `["None","None","None","None"]`, and re-importing at the
same path did NOT re-bind them (the city regenerated to bare footprint splines, 0 ISM). **Fix: after
re-importing, rewrite `meshInfo` on ALL 17 tier graphs** (`ObjectTools.set_properties` on
`/Game/PCG/CityTiers/PCG_B_<Tint>_<Height>` with the FULL `userParameters` bag, `meshInfo`=
`[corner,wall,window,window]` for that tint; Warm→base `/Game/PCG/FuturisticKit/mod_*`, others→
`/Game/PCG/FuturisticKit/Tints/<Tint>/mod_*_<Tint>`). Then force-regen all 49 (toggle each actor's
`graph` to the base `PCG_Building_CitySample`, sleep ~5s, set back to its tier — iter4 gotcha #5).
**Lesson: if you must change a kit MESH that the grammar references, prefer editing the MATERIAL or
the mesh's verts WITHOUT delete; if you delete+reimport, expect to re-point `meshInfo` on every
graph and re-regen.** The full rebuild flow: edit `futuristic_kit_jobs.py` → Blender headless
rebuild (verify `[BOUNDS OK]` = X-centered ±200, Y-centered, base-pivot Z 0..400, true cm — the
unit fix held, no 100× blow-up) → delete the 3 base + 12 tint meshes → `import_file` the 3 base →
`set_material('M_Glass', M_TowerGlass)` → duplicate+`set_material(MI_Glass_<Tint>)` the 12 tints →
rewrite meshInfo on 17 graphs → toggle-regen 49 → verify 147 ISM / 0 empty.

**ROADS + GROUND (`CityGround` outliner folder, 17 plane actors).** First tried per-building
sidewalk PADS (one light plane under each footprint) — INVISIBLE from aerials (buildings cover the
block; pad-vs-dark-ground contrast too low at dusk). What WORKED = figure-ground at city scale:
  - **Plaza:** ONE light-concrete `/Engine/BasicShapes/Plane` at Z=1, scale 330 (±165m, covers the
    city + outer ring), material `/Game/PCG/M_Sidewalk` (grey 0.14, dup of M_Asphalt w/ base-color
    bumped + recompile).
  - **Road grid:** 8+8 dark strips (`M_Road`, near-black 0.008) along the street centerlines at
    `±2000,±6000,±10000,±14000` (between/around the 4000-spaced cells), Z=3, width ~1400cm, full
    span. Reads clearly as a street grid, esp. at the perimeter. (Existing dark `Ground` ±250m stays
    underneath/beyond as surrounding terrain.)
  - **Material-on-plain-actor:** there is NO `set_component_material_override` tool — set the
    StaticMeshComponent's `OverrideMaterials` array via `ObjectTools.set_properties(smc,
    {"OverrideMaterials":[{"refPath":M}]})` (same as the Ground plane). Spawn via
    `SceneTools.add_to_scene_from_asset('/Engine/BasicShapes/Plane', ...)`; the Plane is 100cm
    centered, +Z normal, so scale = cm/100.

**HONEST VISION READ vs a real futuristic city / the demo:**
  - ✅ **BANDING FIXED — the #1 iter5 gap is closed.** Side-by-side (before `_iter6_before_*` vs
    keepers): the uniform waffle of equal horizontal+vertical lines is now smooth vertical-pinstripe
    glass with only a faint floor line. Towers read as continuous curtain-wall skyscrapers, not
    stacked plates. Clearly closer to photoreal glass.
  - ✅ Ground/roads help a lot — the city now sits on a lit plaza with a legible dark street grid
    instead of floating on void; the figure-ground (light blocks / dark roads) reads as a real city
    block layout, and the foreground road strips ground the street-level hero.
  - ✅ Everything from iter5 preserved: 7×7=49 closed glass towers, 5 tints scattered, downtown core
    with 2 signature towers stepping down to a low ring, no freeze, 147 ISM / 0 empty.
  - ⚠️ Faces still read a touch FLAT/uniform — the glass is one emissive grid with no varied
    lit-vs-dark windows; a real night tower has random-lit windows. Per-instance window-randomization
    (hash the instance id into the emissive) is the next realism lever.
  - ⚠️ FLAT TOPS / no crowns or setbacks (grammar boxes open-top) — rooflines are the next silhouette
    lever (a crown/cap module, or vary the top floor's grammar).
  - ⚠️ Roads are flat strips (no lane lines, crossings, sidewalks-vs-road curb height, props/cars).
    Fine at this scale; curbs + lane markings + a few props would deepen the street read.
  - ⚠️ Street-level foreground is a bit bright at the head-on pose (catches sky); the dusk EV -1.5 on
    both PPVs reads best in the aerial. A slightly steeper street pose or a touch lower EV cleans it.

**NEXT LEVER (priority):** (1) ROOFLINE — crown/cap module or varied top floors so tops aren't flat
(biggest remaining silhouette gap). (2) Per-instance lit/dark WINDOW randomization for a real
night-tower look (hash instance id → emissive strength in M_TowerGlass via PerInstanceCustomData).
(3) Curbs + lane lines + a few street props on the road grid. (4) Scale 10×10=100 (same recipe;
verify ISM/no-freeze per batch). (5) Reflections/SSR pass for the glass.

  **Assets touched:** `M_TowerGlass` SmoothStep_1/2 tuned; new `/Game/PCG/M_Sidewalk` + `/Game/PCG/M_Road`
  (dups of M_Asphalt); kit meshes rebuilt from `futuristic_kit_jobs.py` (continuous-glass m_window/m_wall);
  17 tier-graph `meshInfo` re-pointed. **New actors:** `Plaza` + `RoadX_0..7` + `RoadY_0..7` in outliner
  folder `CityGround`. Capture helper: `docs/_decode_capture.py` (decodes a CaptureViewport tool-result
  .txt → PNG). Level + assets saved.

## 2026-06-21 — ITER 7: THE LOOK PASS — reflective dusk glass + golden-hour Lumen lighting (agent `pcg-lumen-light`)
**Result: the flat-pastel-paper glass of iter6 now reads as DARK REFLECTIVE dusk curtain wall with subtle
warm lit windows, lit by a low golden sun under a realtime-captured dusk sky with warm height fog. NO regen
(material + lighting only) — all 49 buildings preserved (3 ISM each, 0 empties). Keepers:
`docs/real_iter7_wide.png` (golden-hour street-canyon hero) + `docs/real_iter7_aerial.png` (3/4 aerial —
golden sun over the metropolis to a hazy waterline, the demo's reference frame).**

**THE BIG DISCOVERY — the Startup level is NOT empty; it contains the full City Sample `Small_City`.**
`find_actors` enumerates only our 49 `BP_BuildingSample` + ground/road `StaticMeshActor`s + lights, but the
viewport reveals a sprawling photoreal City Sample metropolis (realistic buildings, streets, rooftop AC
units, a red-lit landmark tower). It must be a World-Partition/streamed sublevel not surfaced by
`find_actors`. **Our 49-tower glass district lives at origin (±~16000cm) INSIDE/beside this city.** Prior
iterations rendered it pure-black (weak sun + AEM_Manual EV -1.5), so it was invisible — the iter7 lighting
pass is what made it appear. NET: we get a photoreal City Sample backdrop *for free*, and the realism job
becomes "make our glass district sit seamlessly inside it at golden hour" — which it now does. (To find our
grid amid the city: top-down at origin shows City Sample rooftops, not our towers; look from the SW corner
(~-12000,-18000) yaw 90 to see our dark-glass towers on the left vs City Sample blocks on the right.)

**1) REFLECTIVE GLASS — the material was authored as an EMISSIVE/DIFFUSE window-PANEL, not glass. The fix
that worked (all on `/Game/PCG/M_TowerGlass`, then `MaterialTools.recompile`; MIs inherit via the parent
chain so ONE edit set retints all 5 palettes):**
  - **Roughness `Constant_4` 0.12 → 0.06** (drives MP_Roughness). Crucial: the PPV's
    `lumenMaxRoughnessToTraceReflections` default is 0.4, so Lumen only ray-traces reflections on surfaces
    rougher-than ≤0.4 — 0.06 is well inside, near-mirror. (Confirmed Lumen reflections are ON via
    `SearchCVars("r.Lumen.Reflections")` → `.Allow=1`, HWRT=1.)
  - **Metallic `Constant_3` 0.85 → 0.0.** 0.85 made it a *colored metal mirror of a dim sky* (the pastel
    look). Real curtain-wall glass is a **dark dielectric**: low/zero metallic + dark base + low roughness
    → Fresnel sky reflection reads as bright glints on dark glass.
  - **Base color was too LIGHT — the killer.** MP_BaseColor = `Multiply_8`(`LinearInterpolate_0` ×
    `GlassTint`). `LinearInterpolate_0` = Lerp(A=`Constant3Vector_1` dark-glass (0.012,0.02,0.045 — good,
    deep blue-black), B=bright tint, **Alpha=`Constant_6`**). Alpha was **0.5** → base lifted 50% toward the
    bright MI tints = pastel. **Dropped Alpha `Constant_6` 0.5 → 0.15** → base stays mostly dark glass with
    a hint of tint, so reflections dominate. (Find the alpha via `get_expression_inputs` on the lerp —
    the `Alpha` input.)
  - **Emissive window-grid was DROWNING the reflection.** MP_EmissiveColor = `Multiply_7`; trace back to the
    **Boost `Constant_2`** (was **7**). At boost 7 the tiled window cells blur to a solid glowing pastel slab
    (no reflection visible). **Dropped Boost `Constant_2` 7 → 0.35** → windows are a subtle dusk glow, not a
    light source; the dark reflective glass now carries the look. (This is THE single biggest material lever —
    a window-grid material can NEVER look reflective while the emissive dominates.)
  - **LESSON: an emissive-window-grid panel and reflective glass are opposing goals.** For "mirrors the
    sky+neighbors," base must be DARK, roughness LOW, metallic LOW, and emissive a faint accent (≤~0.4), not
    a glowing fill. Tints belong at ~15% base influence, not 50%.

**2) REALTIME SKY CAPTURE — the SkyLight was a STALE static capture.** `SkyLight_0.SkyLightComponent0` was
`SourceType=SLS_CapturedScene` with **`bRealTimeCapture=false`** → it lit/reflected a frozen old sky, NOT the
live dusk. **Set `bRealTimeCapture=true`, `Intensity 1 → 3.0`, `bLowerHemisphereIsBlack=false`** → the live
warm dusk SkyAtmosphere now drives ambient + is what the glass reflects. (Realtime capture + SkyAtmosphere +
a low sun auto-reddens the sky = golden hour for free.)

**3) GOLDEN-HOUR SUN.** `DirectionalLight_0`: **rotation pitch -45 → -11** (low on the horizon = long raking
shadows + warm scattering), **`bUseTemperature=true, Temperature=5200`** (was white), **Intensity 12 → 14**.
Low + warm is the whole golden-hour read; the SkyAtmosphere does the sky reddening automatically.

**4) WARM HEIGHT FOG for depth.** Added `/Script/Engine.ExponentialHeightFog` ("DuskFog") via
`add_to_scene_from_class`. Set on `HeightFogComponent0`: `FogDensity 0.007`, `FogHeightFalloff 0.08`,
`StartDistance 2000`, `FogMaxOpacity 0.85`, `bEnableVolumetricFog=true`, `VolumetricFogScatteringDistribution
0.6`. **⚠️ UE 5.8 RENAMED the fog COLOR props — `FogInscatteringColor` and `DirectionalInscatteringColor`
both error "could not be set."** Color now comes from the SkyAtmosphere automatically (more physically
correct anyway), so skip them; the warm low sun tints the fog for you. Density 0.012 muddied mid-distance —
0.007 is the keeper.

**5) EXPOSURE / GRADE / DOF (there are TWO unbound PPVs — set BOTH or they fight, iter4 gotcha #5 holds).**
  - **Exposure: AEM_Manual `AutoExposureBias -1.5 → -0.3` on BOTH PPV_0 and PPV_1.** The realtime dusk sky is
    darker than the old static capture, so -1.5 crushed the scene to black; -0.3 = rich + legible. (PPV_1 had
    only its method set, no manual-exposure overrides — gave it the full AEM_Manual + bias set to match PPV_0.)
  - **Lumen reflection overrides forced on PPV_0** (defaults were inert `bOverride_*=false`):
    `reflectionMethod=Lumen, lumenReflectionQuality=2, lumenMaxRoughnessToTraceReflections=1.0,
    lumenMaxReflectionBounces=4, dynamicGlobalIlluminationMethod=Lumen, lumenFinalGatherQuality=2`.
  - **Bloom `bloomIntensity 0.675 → 1.2`** (subtle glow on the lit windows) + warm grade
    `whiteTemp=5400, colorSaturation 1.12, colorGain (1.06,1.0,0.9)` (golden-hour warmth/pop).
  - **DISABLE DOF for crisp architecture** — PPV_0's `depthOfFieldEnabled=true, fstop 4` blurred the
    foreground to mush. There's no single "DOF off" override exposed cleanly, so **neutralise it:
    `depthOfFieldFstop=32` + `depthOfFieldFocalDistance=1000000`** on BOTH PPVs → everything in focus.

**HONEST VISION READ vs the Unreal demo's photoreal coastal metropolis (warm light, reflective glass, depth):**
  - ✅ **Materially closer to "seamless."** The aerial keeper genuinely matches the demo's reference frame: a
    low golden sun over a dense realistic city receding to a hazy waterline, long warm shadows, reflective
    wet-look streets, real atmospheric depth. The street-canyon wide reads as a believable dusk metropolis.
  - ✅ **Glass fixed** — our towers now read as dark reflective curtain wall with subtle warm lit windows
    (visible Fresnel sky-gradient on the faces up close), not iter6's flat pastel graph-paper boxes. They sit
    seamlessly inside the City Sample city — you can't tell at a glance which towers are ours.
  - ✅ Golden-hour mood + realtime sky reflections + warm fog = the single biggest realism jump of any
    iteration (it's also what revealed the free photoreal City Sample backdrop).
  - ⚠️ **Still reads a touch GREY/desaturated overall** at this exposure — could push another +5-8% warm
    saturation / a hair more colorGain for richer gold without blowing it. The dusk is on the cool side of
    golden.
  - ⚠️ **Our glass faces still aren't sharply MIRRORING neighbours** — the reflection is a soft Fresnel
    sky-gradient, not crisp neighbor/skyline reflections (Lumen HWRT reflections of dark dusk towers are low-
    contrast; a brighter sky or SSR-cubemap detail, or pushing `r.Lumen.Reflections.SmoothBias` toward 1,
    would sharpen them). Reads as glass, but not yet a hard mirror.
  - ⚠️ **Flat tops / no crowns still** (grammar boxes are open-top) — least visible at this low golden angle
    but a roofline pass is the next silhouette lever. (Deferred this iter — the look levers were higher impact.)
  - ⚠️ Faint yellow PCGVolume/world-bounds wireframe line across the top of the wide capture (editor brush
    artifact; deselect doesn't clear the world-bounds line). Crop it for a clean still.

**NEXT LEVER (priority):** (1) Sharper glass reflections — brighter key/sky or `r.Lumen.Reflections.SmoothBias`
≈0.5-1 so faces mirror neighbours, not just a sky gradient. (2) +5-8% warm saturation/gain for richer gold.
(3) ROOFLINE crowns/setbacks so tops aren't flat. (4) Lean INTO the free City Sample backdrop — frame the demo
as "our procedural glass district generating itself inside a real photoreal city." (5) Per-instance lit/dark
window randomization for a true night-tower read.

  **Assets touched (NO regen — material + lighting + PPV only, all 49 buildings preserved):**
  `M_TowerGlass` (`Constant_4` rough 0.06, `Constant_3` metallic 0, `Constant_6` lerp-alpha 0.15,
  `Constant_2` emissive-boost 0.35); `DirectionalLight_0` (pitch -11, temp 5200, intensity 14);
  `SkyLight_0` (realtime capture on, intensity 3); new `ExponentialHeightFog_0` "DuskFog";
  `PostProcessVolume_0`/`_1` (EV -0.3, DOF off, Lumen reflection overrides, warm grade, bloom 1.2).
  Level + assets saved (`AssetTools.save_assets([])`).

## 2026-06-21 — ITER 8: GLASS DISTRICT DROPPED INTO THE REAL PHOTOREAL CITY SAMPLE (agent `glass-in-citysample`)
**Result: 14 sleek glass grammar towers placed INTO the actual photoreal `Small_City_LVL` downtown core
— grounded on the real streets, taller than the surrounding City Sample buildings, reading as a
futuristic glass financial district risen inside the real city. Pristine DEFAULT lighting left
UNTOUCHED (no fog, no sun change, no SkyLight flag). All 14 closed (3 ISM each, 0 empties), no freeze.
Keepers: `docs/glass_in_city_aerial.png` (sun-SIDE 3/4 aerial — blue/teal glass towers vivid against
warm masonry, THE shot), `docs/glass_in_city_street.png` (street canyon — glass towers framing a
photoreal limestone tower), `docs/glass_in_city_aerial_sunset.png` (sun-BEHIND 3/4 — heroes silhouette
over the ocean sunset).**

**THE BIG DIFFERENCE FROM ITERS 4-7: this time we built INTO `Small_City_LVL` itself, not the empty
`Startup` map.** Iters 4-7's glass city lives in `/Game/Map/Startup/Startup`. This iter reused the SAME
proven assets (`PCG_Building_CitySample` grammar graph + `FuturisticKit` glass modules + `M_TowerGlass`
+ the 17 `CityTiers/PCG_B_*` tier graphs) but spawned the `BP_BuildingSample` actors directly in the
loaded photoreal City Sample level so they sit among real streamed buildings. The recipe is identical
(spawn BP scale 13 → set `PCG.PCGGraphInstance.graph` to a tier graph → auto-regens to that height+tint);
it just works in-place in the real city.

**LOCATING THE DOWNTOWN CORE (no `find_actors` needed — it surfaces almost nothing in this WP level).**
`find_actors` returns only spawners/zonegraph/PlayerStart/HLOD proxy at origin — NOT the streamed
buildings. Use VISION + `trace_world` instead:
  1. `CaptureViewport` (pass `captureTransform` explicitly — it has no default) from an oblique aerial
     with a grid+axis annotation overlay (`gridSpacing:10000, gridExtent:300000, maxLabels:0`) → the
     tall skyscraper cluster is clearly visible at **+X, Y≈0** (downtown sits NE of world origin; the
     PlayerStart at (-29899,-101,169) is the SW residential edge). The core spans roughly **X 24000..56000,
     Y -12000..12000**, street level **Z≈100-190**.
  2. `SceneTools.trace_world` returns **DISTANCE from start**, not Z — so `groundZ = startZ - distance`.
     Start a downward trace at z=30000: distance ~29800 → street (Z~100-200); a much smaller distance
     → you hit a BUILDING ROOF (e.g. Z=7776 = a 78m roof). **THIS IS HOW YOU FIND STREET GAPS.**

**THE DENSITY PROBLEM + THE FIX (the crux of placing into a real city).** City Sample downtown is
WALL-TO-WALL buildings — there are no empty lots. Naively placing a tower at a grid point lands it ON
TOP of an existing building (ugly interpenetration). **Fix: scan a trace grid first, keep only cells
whose `groundZ < ~400` (= actual street/plaza, not a roof), then place towers only in those gaps.** A
4000cm trace grid over the core (X 20000..60000 × Y -16000..16000) found **55 street cells out of 99**;
hand-picked 14 well-separated ones near the core for the cluster. Even so a 34m footprint centered on a
street point can clip a neighbour — pick cells with low-Z neighbours where possible; minor base overlap
reads fine since the glass towers are much taller (new-construction look).

**GROUNDING: trace each pick, set actor Z = that street groundZ.** The kit is base-pivoted (z-min≈0) so
actor Z = street Z puts the base on the road. Verified per tower via `get_actor_bounds` zmin (all -27..118
≈ street). Do NOT use spawn `snap_to_ground` — on a FRESH BP spawn only the billboard exists (the PCG
building hasn't generated yet), so it would snap the billboard, not the tower.

**HEIGHTS — out-top the City Sample core for a futuristic accent.** Existing downtown reaches ~150-200m.
Made 2 hero supertalls by duplicating the Signature tier graphs and bumping `userParameters.buildingHeight`:
`PCG_B_Silver_Hero` (28000cm = **279m**), `PCG_B_Blue_Hero` (22000cm = **219m**). Cluster height ladder
(verified by `get_actor_bounds`): 279m + 219m heroes (dominate everything) · 159m + 139m Silver/Blue
Signatures (match the tallest existing) · 5× 89m Tall · 4× 59m Mid (sit among the mid-rise = integrate).
14 towers, 5 tints (Silver/Blue/Teal/Amber/Warm via the per-tint tier graphs) scattered for variety.

**SPAWN RECIPE (copy verbatim):** one test tower first to validate (spawn → set graph → wait ~6s →
`get_actor_bounds`+`get_components` → confirm 3 ISM + zmax≈buildingHeight + zmin≈street). Then batch the
rest in ONE `execute_tool_script` (spawn + set-graph per tower, serial). Wait ~10s for the async regens,
THEN verify ISM/empties in a SEPARATE script (regen is async — an immediate read shows pre-regen). Got
14/14 closed, 0 empty, no freeze. Foldered all under outliner `FuturisticGlassDistrict`
(`SceneTools.set_actor_folder`).

**LIGHTING — DELIBERATELY UNTOUCHED (the brief's hard constraint, and the FASTEST-PATH lesson).**
`Small_City_LVL`'s default is already the warm photoreal coastal golden look. Added BUILDINGS ONLY — no
fog, no sun rotation, no SkyLight realtime flag, no PPV. The towers inherit the real city's lighting and
sit seamlessly in it. (Iters 4-7's whole lighting saga was for the empty Startup map; in the real city
you must NOT touch it or you white-wash the pristine look — confirmed in CITY-SAMPLE-PLAYABLE.md.)

**HONEST VISION READ:**
  - ✅ It genuinely reads as a futuristic glass district risen inside a photoreal city. The **sun-SIDE
    aerial** is the money shot — vivid blue/teal reflective curtain-wall towers pop against the warm
    photoreal masonry (cool-glass-vs-warm-stone contrast sells "modern district in an old city"). The
    **street canyon** shot frames a real City Sample limestone tower between our glass towers = perfect
    integration read. Towers are grounded and correctly scaled (heroes clearly out-top the core).
  - ⚠️ **Angle-dependent: from the sun-BEHIND side the glass goes near-black** (M_TowerGlass is dark
    reflective dielectric — iter7's deliberate look — so with the sun behind it the faces read as dark
    monoliths, not glittering glass). The blue/teal tints read as glass from every angle; Silver/Warm go
    darkest. For a hero still, shoot the sun-SIDE. (Can't fix via lighting here — that's off-limits.)
  - ⚠️ Some bases sit tight against neighbours (downtown has no real lots) — minor clip on a couple, not
    visible in the keepers. The shorter 59-89m towers blend INTO the skyline rather than standing out
    (intended for integration, but means only ~6 of the 14 read as obviously "new/futuristic" at a glance).
  - ⚠️ Faint yellow editor world-bounds wireframe line in the aerials (editor artifact, crop for a clean
    still; `SelectActors([])` doesn't clear the world-bounds line).

**NEXT LEVER (priority):** (1) A few more clearly-glass tints lighter than the dark base (the blue/teal
read best — lean into cooler/lighter tints so towers pop sun-behind too, WITHOUT touching scene lighting —
do it in the per-tint MIs). (2) Bump a couple more towers to Signature/Hero height so MORE than ~6 read as
new construction. (3) Roofline crowns/setbacks (grammar boxes are flat-topped). (4) If a brighter glass
read is wanted, a tower-LOCAL bounded PostProcessVolume / brighter emissive on the MIs (local, won't
touch the city's pristine global lighting).

  **New assets:** `PCG_B_Silver_Hero` (28000) + `PCG_B_Blue_Hero` (22000) in `/Game/PCG/CityTiers/`.
  **New actors:** 14 `BP_BuildingSample` in `Small_City_LVL`, outliner folder `FuturisticGlassDistrict`
  (1 named `GlassTest_0` = the central 279m Silver hero; 13 named `Glass_*`). Cluster center ≈ (40000,0),
  spread X 26000..56000 / Y -12000..16000, all grounded on traced street Z. Level + assets saved.

- **2026-06-21 — MORE + LIGHTER GLASS pass (NEXT-LEVER items 1+2 done, agent `glass-in-city`).** Pat: more
  glass towers, and the current ones go near-black sun-behind. Did it WITHOUT touching scene lighting:
  - **Lighter/cooler tints — in the per-tint MIs ONLY (`/Game/PCG/GlassTints/MI_Glass_{Blue,Teal,Amber,
    Silver}`).** The lever is the `GlassTint` VECTOR param (each MI also has `WindowTint`). It MULTIPLIES the
    base M_TowerGlass dark-glass BaseColor, so raising it lifts the whole face — the fix for the sun-behind
    near-black. Set via `MaterialInstanceTools.set_vector_parameter(name="GlassTint", value=LinearColor)`.
    Values RAISED well above 1 (HDR-style multipliers, cooler): Blue (0.7,0.85,1.4)→(1.3,1.5,2.2),
    Teal (0.55,1.1,1.05)→(1.4,2.0,2.1), Amber (1.25,0.95,0.65)→(1.6,1.5,1.3), Silver (1.0,1.05,1.25)→
    (2.1,2.2,2.5). Blue stayed the strongest "reads-as-glass-from-every-angle" tint; Silver needed the
    biggest lift to stop going dark. **MI vector edits hot-apply — no PCG re-spawn needed** (the live ISMs
    pick up the MI change immediately; recapture confirmed).
  - **8 MORE towers** (14→**22**), favoring tall tiers so the district clearly reads as new construction:
    spawn `/PCG/SampleContent/Grammar/BP_BuildingSample` via `add_to_scene_from_asset` at scale **13×13×1**
    (matches existing) on clean street cells, then point each one's height/tint by setting its
    `<actor>.PCG.PCGGraphInstance` `Graph` to a `/Game/PCG/CityTiers/PCG_B_<Tint>_<Height>` tier graph —
    **the BP auto-regenerates on that property edit** (no ExecuteGraphInstance; it's a BP-component PCG, not
    a PCGVolume). Used Hero (Silver 280m / Blue 220m), Signature (140m), Tall (220m). Verify each via
    `get_actor_bounds` (Hero → z-max ≈ 27900; Tall ≈ 22000) AFTER the set — height only takes on the regen.
  - **⚠️ GROUND CELLS: trace first, skip rooftops.** `SceneTools.trace_world` straight down (start z=20000 →
    end z=-2000; groundZ = 20000 − returned distance) at each candidate cell. Downtown is DENSE — several
    grid cells land on existing City-Sample ROOFTOPS (groundZ read ~900-7000, way above the ~100-300 street
    level). Drop those cells; only place where groundZ ≈ 100-300. The existing grid is X∈{26472,30472,...,
    50472} step 4000, Y∈{-12141,-8141,-4141,-141,7858,11858} — fill the EMPTY street cells in/around it.
  - **HONEST RESULT (multi-angle):** sun-side aerial = big vivid blue/silver glass district, Heroes out-top
    the core, clearly "new construction." Sun-BEHIND aerial = the blue glass now holds its color + window
    grid (no longer black slabs) — categorical improvement over the prior pass's near-black. The very tallest
    backlit towers dead-center between camera and the bright sky still read dim — that's correct backlighting,
    NOT a bug; pushing tints higher to "fix" it would look unnaturally emissive. Captures:
    `docs/glass2_aerial.png` (3/4), `docs/glass2_sunbehind.png` (the hard angle), `docs/glass2_street.png`
    (street canyon, clear sky). Level + MIs saved (`save_assets([])`).

## 2026-06-21 — BEAUX-ARTS / HAUSSMANN PARIS in its OWN level (agent `paris-city`)
**Result: 49 closed cream-limestone Haussmann buildings on a uniform mid-rise grid with wide boulevards,
in a NEW level `/Game/Map/Paris_LVL` (NOT the glass-city Startup, NOT the protected Small_City/CarShowcase).
The Beaux-Arts kit + the grammar generator FUSE cleanly — zero axis/scale breakage — proving again that the
"width on +X, centered, base-pivoted, true-cm" kit spec is the whole game. All 49 closed (3 ISM each:
corner+wall+window), zero empties, no freeze. Playable: PIE drops a walkable DefaultPawn on a boulevard,
grounded. Keepers: `docs/paris_aerial.png` (3/4 — the cream-stone grid + boulevards), `docs/paris_street.png`
(in-PIE street-canyon down a boulevard, the money shot), `docs/paris_facade.png` (close — arched French
windows + iron Juliet-balcony bands + quoined corners), `docs/paris_overview.png` (high overview).**

**NEW LEVEL the safe way (no "create empty level" MCP tool exists — only `load_level`/`duplicate`).**
`AssetTools.duplicate('/Game/Map/Startup/Startup','/Game/Map/Paris_LVL')` → the dup is DIRTY immediately;
`load_level` REFUSES to switch off a level with unsaved changes, so `save_assets(['/Game/Map/Paris_LVL'])`
FIRST, then `load_level`. ⚠️ The current level when this agent started was the protected `CarShowcase_LVL`
— it was NOT dirty (verified via `is_dirty` BEFORE doing anything), so switching away was safe and it was
never saved. The "unsaved changes" block was the new Paris dup itself, not the protected level.
- **The dup carried the WHOLE iter4-6 glass city** (49 `BP_BuildingSample_C_27..75` + the `CityGround`
  plaza/road planes + 2 StartMapTextRender). Cleared it for a clean Paris slate: the CityGround/text removed
  fine via `find_actors`+`remove_from_scene`, but the **49 glass BP buildings did NOT delete by a
  name-filtered find** (the label query missed; they're WP/external-ish actors) — had to `remove_from_scene`
  each by EXACT refPath (`...PersistentLevel.BP_BuildingSample_C_<27..75>`) in a loop → all 49 gone. Kept the
  inherited Sun/SkyAtmosphere/SkyLight/2 PPVs/the ±250m `Ground` plane and re-tuned them for daylight.

**KIT IMPORT — true cm, no 100× bug (the kit's unit fix held).** `StaticMeshTools.import_file` the 5 FBXs
from `assets/beaux_arts_kit/` → `/Game/PCG/BeauxArtsKit/{mod_corner,mod_wall,mod_window,mod_ground,mod_mansard}`.
`get_bounds` confirmed X −200..+200 (400 wide, centered), base-pivot Z 0..400 (ground 0..600, mansard 0..350)
— exactly `_stats.json`, NO blow-up. **As NOTES warned, the FBX collapsed the 2 Blender slots (Stone+Iron)
to ONE slot `M_Stone` on import** (verified `get_material_slots` → `["M_Stone"]`). The relief still reads
because it's GEOMETRIC (proud cornices/quoins/balconies self-shadow). Authored a cream-limestone Material
`/Game/PCG/BeauxArtsKit/M_ParisLimestone` (BaseColor ~0.62,0.57,0.47 warm cream / Roughness 0.78 / Metallic 0)
and `set_material('M_Stone', M_ParisLimestone)` on all 5 modules.

**GRAMMAR GRAPH — `PCG_Building_CitySample` → `PCG_Building_Paris`, meshInfo swap = the whole job.** The base
graph's `userParameters.meshInfo` is positional `[0]C/Column [1]W/Wall [2]W1/Window [3]W2/HoleWindow`; set it
to `[mod_corner, mod_wall, mod_window, mod_window]` (W1=W2 reuse the window bay) + `moduleInfo[].size=400`
(inert — Size is recomputed from Extents.X=200 — but keeps the editor readable) + debugFloors/debugModules
false + debugColor white (no vertex tint). Pass the FULL `userParameters` bag as the `values` JSON STRING
(set_properties only overrides keys you pass). A ONE-building test (spawn BP scale 13 → set graph → wait ~8s
→ `get_actor_bounds`+`get_components`) returned **3 ISM (corner/wall/window), zmax≈buildingHeight, base at
Z=0** and a capture showing real arched French windows + iron balconies + quoined corners. The kit assembles
PERFECTLY (vs the CH-kit failure in iter2) — X-centered/base-pivot is confirmed the requirement.

**HAUSSMANN LAYOUT = UNIFORM MID-RISE, not a downtown core (the key difference from every prior glass iter).**
Made 4 per-height tier graphs `/Game/PCG/CityTiers/PCG_Paris_{H22,H26,H30,Landmark}` (buildingHeight
2200/2600/3000/4200 cm = ~6/7/8/11 floors) — all the SAME Paris meshInfo, only height differs. Spawned a
**7×7=49 grid**, SPACING **6000cm** (wide Paris boulevards — vs the dense glass city's 4000), scale 13
(~34×29m footprint → ~26m boulevards), per-actor centering offset `(-940,-87)*13/8`. Height assignment is a
flat scatter `HTS[(i*2+j*3)%3]` (NOT ring-based — no tall center) so the mass is uniformly mid-rise, plus
**3 Landmark cells** ((3,3),(1,5),(5,2)) at 4200cm for the "1-2 taller accents." Verified all 49: 3 ISM each,
0 empty; zmax histogram 2050×20 / 2550×13 / 2800×13 / 4050×3 = the Haussmann silhouette (uniform cornice line
+ a few taller landmarks). Spawn recipe identical to iter3/5 (spawn BP → set `PCG.PCGGraphInstance.graph` to a
tier graph → auto-regens to that height; serial-in-script, batched 28+21, no freeze). Foldered under
outliner `ParisCity`. ISM names are `ISM_mod_corner_0 / ISM_mod_wall_0 / ISM_mod_window_0`.

**LIGHTING — bright clear DAYLIGHT (its own world, so I DO tune it, unlike the in-City-Sample iter8).**
DirectionalLight pitch -48 / yaw 35 / intensity 12 / Temperature 5800; SkyLight `bRealTimeCapture=true`
intensity 0.7 `bLowerHemisphereIsBlack=false`; both unbound PPVs AEM_Manual, MotionBlur 0, DOF neutralized
(fstop 32 / focal 1e6). **EXPOSURE CALIBRATION for CREAM STONE (different from brick/glass!):** cream
limestone is far more reflective than brick — at EV +0.5 it was dim-grey, at EV +1.3 it BLEW pure white, even
EV +0.1 stayed washed. **Keeper = AEM_Manual `AutoExposureBias = -1.0` on BOTH PPVs + base color darkened to
~0.62,0.57,0.47.** Sign rule from prior iters holds (lower-magnitude = brighter) but reflective light stone
wants a darker key than diffuse brick (brick keeper was +0.5). Also gave the ±250m `Ground` plane a light
warm-grey pavement material `/Game/PCG/BeauxArtsKit/M_ParisGround` (0.34,0.33,0.30 / rough 0.9) via the
StaticMeshComponent `OverrideMaterials` so the city sits on a plaza, not dark asphalt.

**PLAYABLE.** Level had NO PlayerStart and DefaultGameMode = base `GameModeBase` (spawns/possesses a
DefaultPawn — walkable WASD). `trace_world` straight down at boulevard points returned distance=5000 from
z=5000 (= ground at z=0, no building) confirming the gaps are clear. Added a `PlayerStart` at (-22000,1500,200)
on the southern boulevard facing +X. `StartPIE` (warmup 4s) → `DefaultPawn_0` spawned in `UEDPIE_0_Paris_LVL`
at exactly the PlayerStart, grounded; in-PIE capture = a walkable boulevard receding between two rows of
Haussmann facades. StopPIE clean. (No PostProcessVolume MotionBlur issue — set to 0 on both PPVs.)

**HONEST VISION READ vs real Haussmann Paris:**
  - ✅ Reads unmistakably as Haussmann Paris: uniform cream-limestone mid-rise blocks, regular cornice line,
    a clean grid with WIDE boulevards, arched French windows + continuous wrought-iron Juliet-balcony bands +
    rusticated quoined corners on every facade (clear in `paris_facade.png` and the in-PIE street shot). The
    boulevard-perspective street shot is the strongest "this is Paris" frame.
  - ✅ Correct silhouette: uniform mid-rise (NOT skyscrapers, NOT a downtown core) with 3 subtle taller
    landmarks — exactly the brief. Kit+grammar fuse robust (49/49 closed, no freeze).
  - ⚠️ **FLAT TOPS — no mansard roofs (the one real gap).** `mod_mansard` was imported + limestoned but NOT
    placed: the grammar's vertical grammar is `[MainFloor][Intermediate]*` (in node `AddAttribute_3` →
    `@Data.Grammar`, modulesInfo MainFloor 300/Intermediate 250 in `VolumeSlicer_5`; horizontal grammar per
    floor in `SelectGrammar_26`). Adding a `[Roof]` symbol mapped to the mansard needs a 5th positional
    meshInfo/moduleInfo entry + a new SelectGrammar criterion + the ByAttribute spawner to handle the new
    symbol — exactly the fragile mid-graph grammar surgery the guide warns silently zeroes spawning, for a
    crown that's a nice-to-have over an already-strong facade. Left flat-topped + documented rather than risk
    breaking all 49. **To add later:** set `AddAttribute_3` grammar to `[MainFloor][Intermediate]*[Roof]`, add
    `{symbol:Roof,size:350...}` to `VolumeSlicer_5.modulesInfo`, add a `SelectGrammar` criterion
    `key=Roof → [C][W,W1]*[C]`, extend moduleInfo+meshInfo with a 5th `M`(mansard) symbol used by that
    grammar — TEST on ONE building and confirm ISM>0 before applying to the grid (revert if it zeroes).
    Safer alt: a separate mansard top-course pass placing `mod_mansard` instances per building top edge.
  - ⚠️ Single material slot (Stone only; the Iron slot collapsed on import) so railings/zinc aren't a distinct
    dark metal — the relief still reads geometrically. For true stone-vs-iron contrast, re-author the kit as
    separate Stone+Iron meshes (or bake the slot split to vertex color).
  - ⚠️ All buildings share ONE limestone tone — a real Paris street has subtle per-building stone variation
    + soot grime gradients. A few tint MIs (like the glass-city per-tint sets) or a WorldZ grime gradient in
    M_ParisLimestone is the next realism lever.
  - ⚠️ The grammar footprint is the BP's default L/corner spline (open courtyard side), uniform orientation —
    Parisian-ish (interior courtyards) but the open sides face the same way; varying footprint rotation per
    block would help.

  **Assets (all saved):** level `/Game/Map/Paris_LVL`; kit `/Game/PCG/BeauxArtsKit/{mod_*, M_ParisLimestone,
  M_ParisGround}`; grammar `/Game/PCG/PCG_Building_Paris` + tiers `/Game/PCG/CityTiers/PCG_Paris_{H22,H26,H30,
  Landmark}`. **Actors:** 49 `BP_BuildingSample_C_*` in outliner folder `ParisCity` (scale 13, 6000 spacing) +
  `PlayerStart_0` + re-lit Sun/SkyLight/2 PPVs + the limestone-pavement `Ground`. Captures `docs/paris_*.png`.
  Protected levels untouched (CarShowcase/Small_City never loaded-into or saved this session).

## 2026-06-21 — ART-DECO 1920s SKYSCRAPER CITY in its OWN level (agent `artdeco-city`)
**Result: 49 closed warm-limestone Art-Deco towers in a NEW level `/Game/Map/ArtDeco_LVL`, with a RADIAL
DOWNTOWN CORE (4 height tiers, tallest at center) + 9 stepped-ziggurat CROWNS on the core cluster. This is
the first build with a real spatial downtown core — and the CROWN WORKED, via the separate-actor approach
(NOT the fragile grammar surgery). All 49 closed (3 ISM each: corner/wall/window), zero empties, no freeze.
Playable: PIE drops a walkable DefaultPawn on the southern boulevard facing the crowned core, grounded.
Mirrors the Paris pipeline exactly; the Art-Deco kit + grammar FUSE cleanly (X-centered/base-pivot/true-cm
spec holds again). Keepers: `docs/artdeco_aerial.png` (3/4 hero — crowned setback skyline), `docs/artdeco_street.png`
(in-PIE boulevard canyon — chevron spandrel detail, money shot), `docs/artdeco_facade.png` (close — floor-by-floor
window bays + bronze grille banding + crowned core behind), `docs/artdeco_aerial_crowns.png` (high overview).**

**NEW LEVEL — same safe sequence as Paris.** Current level at start was `Paris_LVL`, `is_dirty=false` → safe to
switch away without saving. `AssetTools.duplicate('/Game/Map/Startup/Startup','/Game/Map/ArtDeco_LVL')` → the dup is
DIRTY → `save_assets(['/Game/Map/ArtDeco_LVL'])` FIRST, then `load_level`. The Startup dup carried the glass city
(49 `BP_BuildingSample_C_27..75` + `StaticMeshActor_51..67` glass towers + 2 StartMapTextRender = 68 actors). Removed
all 68 by EXACT refPath in one ProgrammaticToolset loop (name-filtered finds miss these WP actors — use refPaths) →
clean slate kept: WorldSettings, Brush_0, PCGWorldActor_0, DirectionalLight/SkyAtmosphere/SkyLight, 2 PPVs, the
±250m ground `StaticMeshActor_1`, engine subsystems. Protected levels (Small_City/CarShowcase/Paris) never loaded-into.

**KIT IMPORT — true cm, no 100× bug.** `import_file` the 5 FBXs from `assets/art_deco_kit/` → `/Game/PCG/ArtDecoKit/
{mod_corner,mod_wall,mod_window,mod_ground,mod_crown}`. `get_bounds` confirmed exactly `_stats.json`: X −200..+200
(400 wide, centered), base-pivot Z 0..400 (ground 0..600, crown 0..800, Y ±55). As NOTES warned the FBX collapsed
the 2 Blender slots (Stone+Bronze) to ONE slot `M_Stone`; the geometric flutes/chevrons/grilles still read (they're
GEOMETRY). Authored warm-limestone `/Game/PCG/ArtDecoKit/M_ArtDecoStone` (BaseColor 0.60,0.50,0.37 / Rough 0.72 /
Metallic 0) + `set_material('M_Stone', M_ArtDecoStone)` on all 5 modules. Ground plane got `M_ArtDecoGround`
(0.20,0.185,0.165 / rough 0.88) via the StaticMeshComponent `OverrideMaterials`.

**GRAMMAR GRAPH — `PCG_Building_CitySample` → `PCG_Building_ArtDeco`, meshInfo swap = the whole job.** Duplicated the
base CitySample graph (clean provenance), set the FULL `userParameters` bag (set_properties only overrides keys you
pass): `meshInfo=[mod_corner, mod_wall, mod_window, mod_window]` (W1=W2 reuse), `moduleInfo[].size=400`, debugFloors/
debugModules false, debugColor white. ONE-building test (spawn BP scale 13 → set `PCG.PCGGraphInstance.Graph` to the
dup → ~9s regen → get_components+bounds) returned **3 ISM (corner/window/wall), zmax 7800≈buildingHeight 8000** and a
capture showing a genuinely closed multi-floor Deco tower (vertical piers, window grid all faces). Kit assembles
PERFECTLY — confirms the X-centered/base-pivot spec is the requirement.

**RADIAL DOWNTOWN CORE = the new thing (Art-Deco ≠ uniform Paris).** Made 4 per-height tier graphs
`/Game/PCG/CityTiers/PCG_ArtDeco_{H40,H80,H120,H160}` (buildingHeight 4000/8000/12000/16000 cm = ~9/19/28/37 floors)
— all the SAME Art-Deco meshInfo, only height differs (set on each GRAPH asset's `userParameters.buildingHeight`,
confirmed via read-back). Spawned a **7×7=49 grid**, SPACING **6500cm**, scale 13 (~34×29m footprint → ~31m streets),
per-actor centering offset `(-1568,-141)` (measured from the test building's footprint-vs-pivot offset at scale 13).
**Height = chebyshev RING distance from center (3,3):** ring0→H160, ring1→H120, ring2→H80, ring3→H40. This places the
tallest tower dead center stepping DOWN to mid-rise at the edges = the Manhattan-1929 setback silhouette. Verified the
spine: (3,3) zmax 15800 / (2,3) 11800 / (1,3) 7800 / (0,3) 3800 — exactly the 4 tiers. **All 49: 3 ISM each, 0 empty,
ISM histogram {3:49}.** Spawn recipe identical to Paris (spawn BP → set `PCG.PCGGraphInstance.Graph` to a tier graph →
auto-regen to that height; serial-in-script, all 49 in one loop, no freeze). Foldered under outliner `ArtDecoCity`.

**THE ZIGGURAT CROWN WORKED — via separate capping ACTORS, NOT grammar surgery (the safe path the brief/NOTES called).**
The stock vertical grammar `[MainFloor][Intermediate]*` has no crown symbol; adding a `[Roof]` symbol is the documented
fragile mid-graph surgery that silently zeroed Paris's mansard — so I did NOT touch the grammar. Instead spawned
`mod_crown` as 9 separate StaticMesh actors on top of the tall core cluster (center H160 + the 8 ring-1 H120 towers):
each at the tower's footprint center `(cellX+1568, cellY+141)`, Z = the building's `get_actor_bounds().max.z − 50`,
**crown scale 6.0** (native 4m base → 24m wide, sits inset on the ~34m roof like a real setback; 800cm native ×6 = 48m
crown). Foldered `ArtDecoCity/Crowns`. Result = the central tower carries a tall spired ziggurat, 8 crowned towers
around it → the iconic crowned-downtown silhouette (see `artdeco_aerial.png`). **Recipe for crowns on any grammar city:**
get each target building's `get_actor_bounds().max.z`, spawn the crown mesh at the footprint center at that Z, scale so
the crown base ≈ 0.6–0.7× the roof width. Zero risk to the spawned grammar buildings. (A grammar `[Roof]` symbol remains
the "purist" alt but is the fragile path — not worth it when separate actors read identically.)

**LIGHTING — warm clear DAYLIGHT.** DirectionalLight pitch −45 / yaw 40 / Temperature 5600 / intensity 11; kept the
inherited SkyAtmosphere/SkyLight. Both unbound PPVs: AEM_Manual, **AutoExposureBias −0.5** (warm limestone at base 0.60
is darker than Paris's cream 0.62 so it wants a brighter key than Paris's −1.0; −0.5 reads crisp, not blown),
ApplyPhysicalCameraExposure false, **MotionBlurAmount 0** (override). At −0.5 the stone reads warm-tan in sun with clean
shadows and a blue sky.

**PLAYABLE.** DefaultGameMode = base `GameModeBase` (spawns/possesses a walkable DefaultPawn, WASD). `trace_world` down
at the south boulevard point returned ground at z=0 (clear, no building). Added `PlayerStart` at (1568,−22000,150) yaw 90
facing +Y straight up the central avenue toward the crowned core. `StartPIE` (warmup 5s) → `DefaultPawn_0` spawned in
`UEDPIE_0_ArtDeco_LVL` at exactly the PlayerStart, grounded (bounds z 115..185). In-PIE capture = a walkable Deco street
canyon. StopPIE clean.

**HONEST VISION READ vs real 1920s Art-Deco:**
  - ✅ Reads unmistakably as a 1920s Art-Deco downtown: warm-limestone towers, vertical-pier window rhythm, geometric
    chevron/zigzag bronze spandrel banding floor-to-floor (clear in `artdeco_facade.png` and the street shot), and the
    RADIAL setback massing (tall crowned core stepping down to mid-rise) = the Chrysler/Empire-State-era Manhattan
    silhouette. The boulevard street canyon is the strongest frame.
  - ✅ The crown is the win the brief asked for — 9 stepped-ziggurat tops with central finials cap the core cluster;
    it WORKED without the grammar surgery that zeroed Paris's mansard.
  - ✅ Height variation + downtown core (the key Art-Deco vs uniform-Paris difference) is real and spatial (4 tiers,
    37→9 floors center-to-edge), not a flat scatter.
  - ⚠️ Single material slot (Stone only; the Bronze slot collapsed on import like Paris's Iron) so the bronze grilles/
    chevrons/crown banding aren't a distinct metal — the relief still reads geometrically. For true stone-vs-bronze
    contrast, re-author the kit as separate Stone+Bronze meshes (or bake the slot split to vertex color).
  - ⚠️ All towers share ONE limestone tone; per-building stone/soot variation (a few tint MIs or a WorldZ grime
    gradient in M_ArtDecoStone) would add realism — same lever noted for Paris.
  - ⚠️ Crowns are placed at one global scale (6.0) sized to the core towers; they slightly overhang the narrower towers.
    Per-building crown scale (= roof width / crown base) would seat them perfectly. Cosmetic; reads fine at skyline scale.
  - ⚠️ Grammar footprint is the BP's default L/corner spline (open courtyard side), uniform orientation — same as Paris.

  **Assets (all saved):** level `/Game/Map/ArtDeco_LVL`; kit `/Game/PCG/ArtDecoKit/{mod_*, M_ArtDecoStone, M_ArtDecoGround}`;
  grammar `/Game/PCG/PCG_Building_ArtDeco` + tiers `/Game/PCG/CityTiers/PCG_ArtDeco_{H40,H80,H120,H160}`. **Actors:** 49
  `BP_BuildingSample_C_*` in outliner folder `ArtDecoCity` (scale 13, 6500 spacing, radial height tiers) + 9 `Crown_*`
  in `ArtDecoCity/Crowns` (mod_crown scale 6) + `PlayerStart_0` + re-lit Sun/SkyLight/2 PPVs + limestone-pavement ground.
  Captures `docs/artdeco_*.png`. Protected levels untouched (Small_City/CarShowcase/Paris never loaded-into or saved).

## 2026-06-21 — PARIS BLOCK: the REALISM template (agent `paris-block`)
**The point of this pass: the prior `Paris_LVL` looked FAKE because every building was identical, one flat tone,
flat-topped, no street. This builds ONE genuinely realistic tree-lined Parisian BLOCK that fixes all four levers,
in a NEW level `/Game/Map/ParisBlock_LVL` (Startup-dup, protected levels untouched). 10 Haussmann buildings in 2
rows of 5 facing a boulevard; every building unique; mansard roofs; full street life; playable. All 10 closed
(4 ISM each: corner/wall/window×2), 0 empties, no freeze. Keepers: `docs/parisblock_street.png` (boulevard canyon
— the money shot), `docs/parisblock_facade.png` (close — adjacent buildings clearly differ in window/wall/tone),
`docs/parisblock_aerial.png` (3/4), `docs/parisblock_pie_street.png` (in-PIE eye level).**

**THE FOUR REALISM LEVERS — exactly how each was solved:**

**1) FACADE VARIETY (no two buildings alike).** The grammar's `meshInfo` is POSITIONAL `[C,W,W1,W2]` — ONE mesh per
symbol per graph, so a single graph = uniform facade and there is NO per-bay random-palette hook in the stock
grammar. **The realism mechanism = ONE grammar graph PER BUILDING, each with a different (corner,wall,window1,window2)
pick from the 12 `beaux_arts_kit/variants` modules.** Imported all 12 variants → `/Game/PCG/ParisVariants/mod_*`
(true cm, X-centered ±200, base-pivot Z 0..400; ground 0..600, mansard 0..350 — the unit fix held, NO 100× bug).
Within one building W1 and W2 are separate symbols so the grammar already mixes wall + 2 window types per facade;
across buildings the corner/wall/window picks differ → genuinely distinct facades. Verified the variant kit
ASSEMBLES CLEAN (4 distinct `ISM_mod_*` per building, zmax≈buildingHeight, base≈0) — same X-centered/base-pivot
rule that makes the base kit work. Also varied HEIGHT per building (buildingHeight 2200-2900 = 5-7 storeys) and
WIDTH per building (per-actor X-SCALE 12-15 → the grammar adds more BAYS, it does NOT stretch the 400cm module).

**2) PER-BUILDING TONE (color variation).** `meshInfo` is a bare StaticMesh-ref array with NO overrideMaterials hook,
and the tone lives on the SHARED mesh's material slot — so per-building tone = per-building MESH COPIES with the tone
baked on. Authored base material `/Game/PCG/ParisVariants/M_ParisStone` (params: `StoneColor` vector, `GrimeColor`
vector, `Rough` scalar; BaseColor = Lerp(GrimeColor, StoneColor, saturate(worldZ × 0.00045)) → a soot/grime gradient
darker toward the street base = lived-in). 5 tone MIs in `…/ParisVariants/Tones/MI_Stone_{Cream,WarmGrey,Beige,Soot,
PaleGold}`. **Per building: duplicate its 4 chosen variant meshes into `/Game/PCG/ParisBlock/<Bid>/` and
`set_material('M_Stone', MI_<tone>)` on each, then point that building's graph meshInfo at its own copies.** 10
buildings × 4 = 40 mesh copies; cycle the 5 tones across the row. **TONE-CONTRAST LESSON:** first pass the tones read
near-identical — needed (a) BIGGER value+hue separation (soot ~0.42 vs cream ~0.80, push hue not just brightness) AND
(b) raise `GrimeColor` close to `StoneColor` so the grime gradient doesn't muddy every building toward the same dark
base. After that the row reads as distinct buildings from street level and aerial.

**3) MANSARD ROOFS — separate-actor recipe (NOT grammar surgery; same safe path as the Art-Deco crowns).** The stock
vertical grammar `[MainFloor][Intermediate]*` has no roof symbol and adding `[Roof]` is the documented fragile surgery
that silently zeroed Paris's mansard. Instead place `mod_mansard` (dark-zinc `M_ParisZinc`: BaseColor 0.09/0.10/0.115,
metallic 0.55, rough 0.38) as a **continuous ROW of separate actors along the FRONT and BACK roof edges only** (NOT the
short side edges — wrapping all 4 made a "castle merlon / tooth-ring" that looked wrong; front+back only reads as a
mansard line). Per building: get `get_actor_bounds`, tile N = round(width/400) modules along each long edge at
`z = bounds.max.z - 25`, X-scale = segment/400 so they're gap-free, dormer face pointing OUTWARD (`mod_mansard`'s dormer
side is local −Y → yaw 0 toward −Y street, 180 toward +Y). **GOTCHA: the mod_mansard mesh's 3 dormers are deep boxes —
at a 34m roof they tile into a slightly chunky dark band, acceptable but not elegant; reads fine at street scale.**
**Plus ROOF-CAP planes:** the grammar boxes are HOLLOW open-top — invisible from the street but the open interiors show
from any aerial. Fix = one `/Engine/BasicShapes/Plane` per building inset ~150cm inside the footprint at
`z = max.z - 120`, M_ParisZinc material via the StaticMeshComponent `OverrideMaterials` → solid dark roof, hollow gone.

**4) STREET LIFE (lived-in, not bare).** Re-materialed the inherited ±250m ground plane with warm pavement
`M_ParisGround`; added a dark `M_Road` plane along the street centerline (Y=0) + two light `M_Sidewalk` strips
(Y=±1300) between road and buildings. Then City Sample props (all under `/Game/Prop/...`): **trees** = a row of
`Kit_Tree_Maple_Sugar/Tree_Maple_{A,B}` + `Kit_Tree_Maple_Red/Tree_Maple_Red_A` (scale ~1.9×2.1, ~10 per sidewalk)
on `Kit_TreeBase_A/SM_TreeBase_Circle_A` bases; **5 parked cars** = `Vehicle/vehCar_vehicle{02,05,06,13}/Mesh/
SM_vehCar_vehicle*` (body mesh only — wheels are separate; lift z≈38 so it reads, fine at distance) along the road
edge (Y≈±720, long axis = X = yaw 0); **12 lamp posts** `Kit_StreetLamp_B/SM_StreetLamp_B`; **6 benches**
`Kit_bench_RR/mesh/SM_street_bench`. (Vehicle/tree assets present in the City Sample project; `find_assets` them.)

**LAYOUT (street along X).** Block X[−9400..9400], boulevard centerline Y=0. North row (Y center +3000, footprint
inner face ≈ Y 1300) and South row (Y center −3000) of 5 buildings each at X = −7400,−3700,0,3700,7400, spaced ~3700
(34m building + small gap = a continuous Haussmann street wall), ~26-33m boulevard between inner faces.
**Per-actor footprint centering offset = `(-940*S/8, -87*S/8)`** for actor scale S (the grammar footprint extends +X/+Y
from the actor origin, not symmetric — same offset rule as iter3/Paris). Both rows yaw 0 (the grammar box is closed on
all sides, so orientation only affects the open-courtyard footprint side — uniform orientation reads fine, the
documented Paris behavior).

**LIGHTING — bright clear Paris daylight (own level, so tuned).** DirectionalLight pitch −48 / yaw 35 / intensity 11 /
Temperature 5800; SkyLight `bRealTimeCapture=true` intensity 0.8; both unbound PPVs AEM_Manual, MotionBlurAmount 0, DOF
neutralized (fstop 32 / focal 1e6). **EXPOSURE: cream/light stone wants a slightly brighter key than the prior Paris
−1.0 — `AutoExposureBias = -0.4` on BOTH PPVs** read crisp+warm (−1.0 was dim/flat-grey and flattened the tone
variety; do NOT go positive or the light stone blows white). Sign rule holds (lower-magnitude = brighter).

**PLAYABLE.** `PlayerStart` at (−9000,−1250,150) on the south sidewalk facing down the boulevard. `StartPIE`
(warmup 5s) → `DefaultPawn_0` spawned at exactly the PlayerStart, grounded (z 115-185 = standing on the sidewalk),
walkable WASD. MotionBlur 0 on both PPVs.

**HONEST VISION READ (QA loop: captured + LOOKED, iterated the weakest lever each pass):**
  - ✅ The **street-level boulevard canyon is genuinely convincing** — two rows of varied Haussmann facades receding
    in perspective, tree-lined sidewalks, parked car, lit lamps, real road. Reads as a real Paris street, not a
    repeated block. The facade close-up shows ADJACENT buildings with clearly different window heads (arched /
    pedimented / balconied), wall treatments (ashlar / rusticated / pilastered), quoined corners, and different stone
    tones. This is the categorical fix over `Paris_LVL`'s clone-row.
  - ✅ Mansard roofs (dark zinc) on every building → no more flat tops. Roof caps hide the hollow interiors from above.
  - ✅ Per-building height (5-7 storeys) + width variety reads in the rooflines.
  - ⚠️ **Tone variety reads clearly at street level but is SUBTLE from the high aerial** (exposure flattens it) — the
    biggest remaining realism gap. Pushing the MI separation further (or a per-building WorldZ grime variance) would
    help the bird's-eye read; at eye level it's already good.
  - ⚠️ The mod_mansard dormers tile a touch CHUNKY at 34m width (deep dormer boxes) — reads as a dark roofline but not
    a delicate mansard slope. A shallower-dormer mansard variant, or scaling one continuous mansard per edge, would
    refine it. Minor at street scale.
  - ⚠️ Parked cars are body-mesh-only (City Sample wheels are separate meshes) — reads fine at distance, slightly
    low/wheel-less up close. Assemble body+4 wheels (or use a City Sample vehicle BP) for a hero close-up.
  - ⚠️ Trees are the bare-branch maple LODs (wintry Paris) — atmospheric but could swap to a leafed variant for summer.

**Assets (all saved):** level `/Game/Map/ParisBlock_LVL`; 12 variant meshes `/Game/PCG/ParisVariants/mod_*`; base
material `…/ParisVariants/M_ParisStone` (StoneColor/GrimeColor/Rough params + WorldZ grime lerp) + zinc
`…/ParisVariants/M_ParisZinc`; 5 tone MIs `…/ParisVariants/Tones/MI_Stone_*`; 10 per-building graphs
`/Game/PCG/ParisBlock/PCG_B0..B9` + 40 per-building tinted mesh copies `/Game/PCG/ParisBlock/B*/`. **Actors:** 10
`BP_BuildingSample_C_1..10` (folders `ParisBlock/NorthRow` + `/SouthRow`, scale 12-15), 182 `Mansard_*`
(`ParisBlock/Mansards`), 10 `RoofCap_*` (`ParisBlock/Roofs`), road+2 sidewalks (`ParisBlock/Street`), 20 trees+bases
(`ParisBlock/Trees`), 12 lamps + 6 benches (`ParisBlock/StreetProps`), 5 cars (`ParisBlock/Cars`), `PlayerStart_0`,
re-lit Sun/SkyLight/SkyAtmosphere/2 PPVs + pavement Ground. Captures `docs/parisblock_*.png`. Protected levels
(Small_City/CarShowcase/Paris/ArtDeco) never loaded-into or saved (ArtDeco was the start level, verified `is_dirty`
false before switching).

**REUSABLE RECIPE (this is the template for the Art-Deco block + any "realistic block"):**
  1. NEW level = dup Startup → save → load; clear inherited city actors by EXACT refPath (name-filtered finds miss
     some). Verify the start level `is_dirty=false` before switching so you never save a protected level.
  2. Import the kit's VARIANT modules (X-centered/base-pivot/true-cm — `get_bounds` to confirm).
  3. Base stone material with `StoneColor`+`GrimeColor` vector params + a WorldZ grime lerp; N tone MIs (push value AND
     hue apart, keep grime near stone).
  4. ONE grammar graph PER building (dup `PCG_Building_CitySample`, set FULL `userParameters` bag with a distinct
     `meshInfo`=[corner,wall,window,window] pick + `buildingHeight`); per-building tinted MESH COPIES for tone.
  5. Spawn `BP_BuildingSample` per building (scale 12-15 for width variety), set `PCG.PCGGraphInstance.graph` to its
     graph (auto-regens), centering offset `(-940*S/8,-87*S/8)`. Wait for async regen, verify ISM>0 in a SEPARATE call.
  6. Mansards = separate-actor row of the mansard module along front+back roof edges (dormer face out, gap-free X-scale,
     z=bounds.max.z−25), dark-zinc material. Roof-cap plane per building to hide hollow tops.
  7. Street: pavement ground + road + sidewalk planes (materials via StaticMeshComponent `OverrideMaterials`), then
     City Sample trees/cars/lamps/benches rows. Bright daylight (sun warm ~intensity 11, EV ≈ −0.4 for light stone,
     MotionBlur 0). PlayerStart on the sidewalk.

- **2026-06-21 — PARIS BLOCK DETAIL PASS (flat → carved stone), agent `paris-detail`.** Realism upgrade on the
  SAME `ParisBlock_LVL`. Before/after captures `docs/parisblock_detail_BEFORE_*` → `_FINAL_*`. **Full ranked recipe
  + every gotcha is in [REALISM-GUIDE.md](REALISM-GUIDE.md) → "THE PARIS-BLOCK DETAIL PASS".** PCG-specific
  takeaways:
  - **Upgrade the SHARED master material, never re-point per-building meshInfo for surface looks.** All 10 buildings
    use tinted MIs of `/Game/PCG/ParisVariants/M_ParisStone`; adding albedo-texture + hand-rolled normal
    (`DeriveNormalZ` from 3 height samples) to that master textured every building at once, tones preserved. New
    textures in `/Game/PCG/ParisDetail/Tex`; decal materials in `/Game/PCG/ParisDetail/Decals`; 25 grime
    `DecalActor`s under outliner folder `ParisBlock/Decals`.
  - **Decals project onto PCG/ISM facades fine** (ISM `bReceivesDecals` true) — `DecalActor` projects along **+X**:
    north-row wall (faces −Y) = **yaw 90**, south-row (faces +Y) = **yaw −90**, actor ~100cm in front,
    `decalSize.x ≥ 400`. Imported decal PNGs come in as `TC_EditorIcon` → set `TC_Default`; decal BaseColor must be a
    neutral dark CONSTANT (the generated soot/stain RGB is warm → paints walls red), use texture only for the alpha mask.
  - **⚠️ The detailed-geometry swap (`beaux_arts_kit/detailed/` → `/Game/PCG/ParisDetailGeo`, Nanite on) is BLOCKED
    by BP-component regen.** Re-pointing graph `userParameters.meshInfo` / the graphInstance / `seed` / a full level
    reload does NOT re-execute a `BP_BuildingSample` PCG (GenerateOnLoad output is cached/serialized);
    `ExecuteGraphInstance` errors "not a valid PCGVolume" on BP actors. Data is staged (C_3/`PCG_B2` → `B2det_*`
    copies, WarmGrey tone) and the block is intact, but the live swap needs the editor UI / a fresh spawn. **Confirm
    a swap via `ObjectTools.get_properties(ISM, ["StaticMesh"])`, NOT the ISM component name (names are sticky).**
    Lesson: for these grammar buildings, do all SURFACE realism in the shared material (regen-proof) and only attempt
    geometry swaps when you can drive the BP regen.
