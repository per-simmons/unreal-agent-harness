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
