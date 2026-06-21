# PCG Procedural City — LIVE Build Recipe via the Unreal MCP

> Goal: replicate Epic's "PCG procedural city" demo as a **live, watchable build** driven
> entirely through the Unreal MCP — city shape → colored districts → blocks → buildings rise
> (color-coded Small/Med/Large) → highway splines → (optional) realistic swap.
>
> Status of this doc: **research/design only** — grounded against the *actual* MCP toolset
> surface inspected on 2026-06-20 (`describe_toolset` on `PCGToolset.PCGToolset`,
> `PCGToolset.PCGSpatialToolset`, `SceneTools`, plus `ListNativeNodes` /
> `GetNativeNodeSchema` for every load-bearing node). Every tool name, node class, and
> property name below was read from the live editor, not guessed. Where a property name still
> needs confirming at build time, it is flagged **[CONFIRM]**.
>
> CONCURRENCY WARNING (from the PCG toolset's own docs): inspection + execution state is
> shared at the *graph asset* level. If multiple PCG actors share one graph you MUST
> `ExecuteGraphInstance` / `GetNodeDataView` on **one actor at a time** and let each call fully
> return before the next — concurrent calls freeze the editor. This plan uses ONE graph + ONE
> volume, so this is naturally satisfied, but do not parallelize execute calls.

---

## 0. What the MCP actually gives us (the feasibility floor)

The `PCGToolset.PCGToolset` is a **full PCG graph authoring API**, not a thin wrapper. Confirmed tools:

| Capability | Tool |
|---|---|
| Create a saved PCG graph asset | `CreateGraph(name, path)` |
| List the real native node palette | `ListNativeNodes(bCommonOnly=false)` → 200+ nodes |
| Get exact pin/property schema for a node | `GetNativeNodeSchema(nodeName)` |
| Add a node (with JSON params) | `AddNode(graph, nativeNodeType, nodeName, jsonParams, nodeTitle, nodeComment, x, y)` |
| Wire two nodes (auto-inserts converters!) | `ConnectNodePins(fromNode, fromPin, toNode, toPin)` |
| Change a node's params live | `UpdateNode(node, jsonParams, nodeTitle)` |
| Expose a graph param (per-instance overridable) | `SetGraphParams(graph, [PCGParamDefinition])` |
| Spawn a PCG Volume actor bound to the graph | `SpawnGraphInstance(graph, name, transform, jsonParams)` |
| Override params on a live volume | `SetGraphInstanceParams(pCGVolume, jsonParams)` |
| **Execute the graph (regenerate)** | `ExecuteGraphInstance(pCGVolume)` |
| Inspect a node's output data | `GetNodeDataView(pCGVolume, node, pinLabel, attr, range)` |
| Inspect whole graph | `GetGraphStructure(graph)` / `GetNodeInfo(node)` |
| Trigger the human to draw a spline in-viewport | `DrawSpline(actorLabel, actorTag, bRedraw, bClosedSpline)` |
| Comment boxes (great for the "live build" readability) | `AddCommentBox` / `UpdateCommentBox` |

Plus `PCGSpatialToolset.RunPCGInstantGraph(graph, params)` for fire-and-forget execution.

**This means the whole demo is authorable and executable headlessly via MCP.** The one true
gap is **Voronoi districting** — there is no native Voronoi node — but there IS a `Cluster`
node (KMeans/EM) that produces the same "irregular colored regions by nearest-centroid"
result the demo shows. See Stage B.

### The node palette that matters (verified present in `ListNativeNodes`)
`Create Points Grid`, `Surface Sampler`, `Spline Sampler`, `Create Spline`, `Create Surface
From Spline`, `Get Spline Data`, `Cluster`, `Attribute Partition`, `Add Attribute`, `Transform
Points`, `Density Filter`, `Cull Points Outside Actor Bounds`, `Difference`, `Static Mesh
Spawner`, `Spawn Spline Mesh`, `Spawn Spline Component`, `Visualize Attribute`, `Debug`,
`Self Pruning`, `Bounds Modifier`, `Point Neighborhood`, `Branch`, `Select`.

There is **no** "Voronoi", no "Building generator" macro, no "street network" node — the demo's
look is built from these primitives, exactly as we will.

---

## Pipeline overview (one graph asset, built node-by-node on camera)

We build a SINGLE graph asset `/Game/PCG/PCG_LiveCity` and ONE `PCGVolume` actor. Each stage
adds nodes + wires them, then we call `ExecuteGraphInstance` so the audience sees the city
gain a layer. The "beats" are literally: *add nodes → execute → viewport updates.*

```
[Get Spline Data (city-shape spline)]            <- Stage A
        -> [Create Surface From Spline] -> Surface
                                              |
[Surface Sampler] (coarse) --------------------+--> district seed points
        -> [Cluster numClusters=N] -> clusterID attr   <- Stage B (districts)
        -> [Visualize Attribute] (debug color per cluster)
        -> [Attribute Partition on clusterID] -> N point-sets
                  |
   per district: [Create Points Grid] clipped to district bounds  <- Stage C (blocks)
        -> street gaps via cellSize > footprint
        -> [Add Attribute] sizeClass (Small/Med/Large) from clusterID
        -> [Transform Points] height extrude (scaleZ varied)       <- Stage D (buildings)
        -> [Static Mesh Spawner] palette = Tower_01..12            (color-coded)
                  |
[Get Spline Data (highway spline)] -> [Spline Sampler]             <- Stage E (highways)
        -> [Difference] (clear buildings near road) -> road strip
        -> [Spawn Spline Mesh] road ribbon
```

---

## STAGE A — City shape  ·  **Feasible**

The demo opens by drawing the city outline. Two paths; do **A1** for the live "draw it" beat,
fall back to **A2** for a fully hands-free run.

### A1 — Human draws the outline (matches the demo's "draw a spline" beat) — *Feasible*
```
PCGToolset.DrawSpline(
  actorLabel="CityShape", actorTag="city_shape",
  bRedraw=false, bClosedSpline=true)     # closed = a region/area
```
This **blocks and hands the viewport to the presenter** to click out an oval/area, then
returns. Reads perfectly on camera ("watch me sketch the city footprint"). The created actor
carries tag `city_shape`.

### A2 — Fully programmatic outline (no human) — *Feasible*
We cannot inject spline control points through `DrawSpline` (it's interactive only). For a
hands-free oval, add a `Create Spline` node **inside** the graph instead and feed it points
from a `Create Points Sphere` / `Create Points Grid` ring, OR place a closed spline actor and
set its points. Simplest robust route: use `Create Surface From Spline` fed by a spline the
graph builds. If a precise oval is needed without a human, generate a ring of points
(`Create Points Sphere`, then flatten Z) → `Create Spline` (closed) → `Create Surface From
Spline`. **[CONFIRM]** `Create Spline` closed-loop param name via `GetNativeNodeSchema`.

### Bring the shape INTO the graph
```
AddNode(graph, nativeNodeType="Get Spline Data", nodeName="GetCityShape",
  jsonParams={"actorSelector":{"actorFilter":"AllWorldActors",
              "actorSelection":"ByTag","actorSelectionTag":"city_shape"},
              "mode":"ParseActorComponents"})
AddNode(graph, "Create Surface From Spline", "CitySurface", jsonParams={})
ConnectNodePins(GetCityShape,"Out", CitySurface,"In")
```
`Get Spline Data` output pin is `Out` (type Polyline); `Create Surface From Spline` takes
`In` (Spline) → `Out` (Surface). `ConnectNodePins` auto-inserts a Polyline→Spline converter if
needed (it returns the list of helper nodes it added — log them).

### Spawn the volume + first execute (the empty stage)
```
SpawnGraphInstance(graph=/Game/PCG/PCG_LiveCity, name="LiveCity",
  transform={location:{0,0,0}, scale:{25,25,10}}, jsonParams={})
ExecuteGraphInstance(LiveCity)
```
**Visible beat:** the bounded city area appears (surface/footprint). 
**QA:** `GetNodeDataView(LiveCity, CitySurface, "Out")` should return a non-empty surface;
`ExecuteGraphInstance` returns `[]` (no error messages) on success.

---

## STAGE B — Districts (colored regions)  ·  **Partial** (Voronoi → KMeans `Cluster`)

> Honest gap: **there is no native Voronoi node.** The demo's irregular colored districts are
> reproduced with the `Cluster` node (KMeans), which assigns every point to its nearest
> centroid — visually the same "patchwork of regions" result. This is the single biggest
> deviation from the literal demo, and it's a *faithful* substitute, not a hack.

```
# 1. coarse seed points across the city area
AddNode(graph, "Surface Sampler", "DistrictSeeds",
  jsonParams={"pointsPerSquaredMeter":0.000002,  # very sparse: ~districts not buildings
              "pointExtents":{"x":50,"y":50,"z":50}})
ConnectNodePins(CitySurface,"Out", DistrictSeeds,"Surface")

# 2. cluster into N districts -> writes clusterID attribute
AddNode(graph, "Cluster", "Districts",
  jsonParams={"algorithm":"KMeans","numClusters":5,
              "clusterAttribute":"DistrictID"})
ConnectNodePins(DistrictSeeds,"Out", Districts,"In")

# 3. COLOR the districts in-viewport (the visible beat)
AddNode(graph, "Visualize Attribute", "DistrictDebug",
  jsonParams={"attributeSource":"DistrictID","bPrefixWithAttributeName":true,
              "duration":0})
ConnectNodePins(Districts,"Out", DistrictDebug,"In")
```
`Cluster` is confirmed: `algorithm` ∈ {KMeans, EM}, `numClusters` (min 1), `clusterAttribute`
(written to output). Optional `Initial Centroids` input pin lets you *place district centers
deliberately* — feed it 5 hand-placed points for a directed layout instead of random.

**Coloring honestly:** `Visualize Attribute` prints the DistrictID as on-screen debug text per
point (good enough to *read* "5 districts" live). For true per-region **color fill** you have
two options, both Feasible:
- **B-color-1 (debug, instant):** raise district seed density a bit and let `Visualize
  Attribute` blanket the area with color-coded IDs. Cheap, reads as colored zones.
- **B-color-2 (real material tint):** carry `DistrictID` through to the `Static Mesh Spawner`
  in Stage D and drive a per-instance material color via
  `staticMeshComponentPropertyOverrides` (map an attribute → an ISM material param). The
  districts then become visible as **colored buildings**, which is exactly how the final demo
  reads anyway. Recommended.

```
# split the cloud into one data-set per district for independent block/building rules
AddNode(graph, "Attribute Partition", "ByDistrict",
  jsonParams={"partitionAttributeSelectors":["DistrictID"]})
ConnectNodePins(Districts,"Out", ByDistrict,"In")
```
`Attribute Partition` confirmed: `partitionAttributeSelectors` array → splits input into one
output data per distinct value. This is the spine of "different rules per district."

**Visible beat:** colored DistrictID labels/zones bloom across the footprint. 
**QA:** `GetNodeDataView(LiveCity, Districts, "Out", attributeName="DistrictID")` — confirm the
attribute exists and has exactly `numClusters` distinct values.

**Rank: Partial** — districts are real and color-coded; the *shape* is KMeans (convex-ish
cells) not true Voronoi polygons. Indistinguishable to a viewer.

---

## STAGE C — Blocks (grid + street gaps)  ·  **Feasible**

Grid-subdivide the city area into blocks. The street gaps come for free from cellSize vs.
point footprint. Run this on the partitioned districts so block grids align per-district, or
once over the whole surface for a uniform grid (simpler, very reliable — recommended for v1).

```
AddNode(graph, "Create Points Grid", "Blocks",
  jsonParams={"gridExtents":{"x":50000,"y":50000,"z":0},   # half-size of city
              "cellSize":{"x":4000,"y":4000,"z":1},        # 40m blocks
              "pointPosition":"CellCenter",
              "coordinateSpace":"World",
              "bCullPointsOutsideVolume":true})
# clip the grid to the city footprint so blocks only exist inside the shape
AddNode(graph, "Cull Points Outside Actor Bounds", "ClipBlocks", jsonParams={})
ConnectNodePins(Blocks,"Out", ClipBlocks,"In")
```
Both nodes confirmed. `Create Points Grid` → `cellSize` controls block spacing (the street
grid), `gridExtents` the city span, `bCullPointsOutsideVolume`. To clip to the **drawn shape**
(not just actor bounds) intersect against the Stage-A surface with a `Difference`/`Density
Filter` against `CitySurface` instead of `Cull Points Outside Actor Bounds`. **[CONFIRM]** the
cleanest clip-to-surface route at build time (`Difference` "In" vs "Differences" pins).

**Street gaps:** make `cellSize` larger than the building footprint you'll spawn in Stage D
(e.g. 40m cells, 30m buildings → 10m streets). For visible avenues, `Self Pruning` or skip
every Nth row by an attribute test.

**Visible beat:** a regular lattice of block points snaps inside the colored districts. 
**QA:** `GetNodeDataView(LiveCity, ClipBlocks, "Out")` element count ≈ (city area / cell area).

---

## STAGE D — Buildings rise (extruded, color-coded by district)  ·  **Feasible**

This is the payoff beat: buildings extrude and color-code Small/Med/Large per district.

### D1 — assign a size class per building from its district
```
AddNode(graph, "Add Attribute", "SizeClass",
  jsonParams={"outputTarget":"SizeClass","inputSource":"DistrictID"})
# (then a Match-And-Set or Attribute Maths Op to map DistrictID -> {0,1,2} size buckets)
```
Map districts to size buckets so e.g. district 0 = downtown (Large), 3 = suburbs (Small). Use
`Attribute Maths Op` / `Match And Set Attributes` (both present) for the mapping. **[CONFIRM]**
exact param shape of `Match And Set Attributes` via `GetNativeNodeSchema`.

### D2 — extrude height (the "rise") — *Feasible*
```
AddNode(graph, "Transform Points", "Rise",
  jsonParams={"scaleMin":{"x":1,"y":1,"z":3},
              "scaleMax":{"x":1,"y":1,"z":18},   # tall variation
              "bAbsoluteScale":false})
ConnectNodePins(ClipBlocks,"Out", Rise,"In")
```
`Transform Points` confirmed: `scaleMin/scaleMax` give per-point random height; the spread
*is* the Small/Med/Large variation. Drive the Z range from `SizeClass` by feeding district-
specific volumes (one `Transform Points` per partitioned district, different scale ranges) —
cleanest with the Stage-B `Attribute Partition` outputs.

> Note on "extrude": PCG doesn't literally extrude geometry; it **scales a base-pivoted mesh
> instance** up in Z. Our towers are base-pivoted (per project memory), so scaling Z reads
> exactly as a building growing taller. This is how the real demo works too (mesh instances,
> not live extrusion).

### D3 — spawn the towers, color-coded — *Feasible*
```
AddNode(graph, "Static Mesh Spawner", "Towers",
  jsonParams={"meshSelectorType": <SelectByAttribute or WeightedByCategory>,
              "staticMeshComponentPropertyOverrides":[
                 {"inputSource":"DistrictColor",
                  "propertyTarget":"StaticMeshComponent.OverrideMaterials"}],  # [CONFIRM]
              "bApplyMeshBoundsToPoints":true})
ConnectNodePins(Rise,"Out", Towers,"In")
```
`Static Mesh Spawner` confirmed. The palette = our 12 towers. Mesh selection has two real
modes (PCGMeshSelectorBase subclasses — discover exact class paths with
`ObjectTools.list_subclasses`/`get_class` on `PCGMeshSelectorBase` at build time):
- **`PCGMeshSelectorWeighted`** — give it the 12 `Tower_01..12` soft paths with weights → random
  tower per point. Simplest; gives skyline variety immediately.
- **`PCGMeshSelectorByAttribute`** — pick the tower by the `SizeClass` attribute → district 0
  always gets the big towers, suburbs get the short ones. This is the color/size-coding.

**Feeding OUR towers as the palette (no City Sample download needed):**
mesh soft paths = `/Game/FuturisticCity/Towers/Tower_01` … `/Game/FuturisticCity/Towers/Tower_12`
(the 12 imported FBX, real-world cm, base-pivoted). **[CONFIRM]** the exact `/Game/...` import
path in the Content Browser before wiring — the FBX live on disk at
`unreal-agent-harness/assets/futuristic_city/towers/tower_01..12.fbx`; confirm where
`AssetTools` imported them (team lead states `/Game/FuturisticCity/Towers/Tower_01..12`).

**Color-coding by district:** carry a `DistrictColor` (LinearColor) attribute (set via `Add
Attribute` keyed on DistrictID in Stage B) and map it to the instance material through
`staticMeshComponentPropertyOverrides` (`inputSource`=attribute, `propertyTarget`=material
param). Requires the tower material to expose a color param; if it doesn't, fall back to
3 tinted Material Instances chosen by `PCGMeshSelectorByAttribute` on SizeClass.

**Visible beat:** the skyline rises district-by-district, color-coded, towers of varied height.
This is the showpiece. To make it *theatrically* sequential, spawn per-district by toggling a
graph param (`ActiveDistrict`) and re-executing — each execute pops one district of towers.

**QA:** after `ExecuteGraphInstance`, `find_actors(name="Towers")` / inspect the spawned ISM
component counts; `GetNodeDataView(LiveCity, Towers, "Out")` element count == building count.

---

## STAGE E — Highway splines  ·  **Feasible**

```
# A2 path: human draws the highway (open spline)
PCGToolset.DrawSpline(actorLabel="Highway1", actorTag="highway", bRedraw=false, bClosedSpline=false)

# pull it into the graph
AddNode(graph, "Get Spline Data", "GetHighway",
  jsonParams={"actorSelector":{"actorFilter":"AllWorldActors","actorSelection":"ByTag",
              "actorSelectionTag":"highway"},"mode":"ParseActorComponents"})

# sample points along it (road centerline)
AddNode(graph, "Spline Sampler", "RoadPts",
  jsonParams={"samplerParams":{"dimension":"OnSpline","mode":"Distance",
              "distanceIncrement":500,"bComputeTangents":true}})
ConnectNodePins(GetHighway,"Out", RoadPts,"Spline")

# lay the road ribbon
AddNode(graph, "Spawn Spline Mesh", "RoadMesh", jsonParams={...})  # [CONFIRM] schema
ConnectNodePins(GetHighway,"Out", RoadMesh,"In")
```
`Spline Sampler` confirmed (rich: `dimension` OnSpline/OnInterior/OnVolume, `mode`
Subdivision/Distance/NumberOfSamples, tangent/curvature/segment attrs). `Spawn Spline Mesh`
present (use `GetNativeNodeSchema "Spawn Spline Mesh"` at build time for params).

**Clear buildings along the road:** sample the highway with `dimension:"OnHorizontal"` (a
band) → feed as the "Differences" input of a `Difference` node against the Stage-C block
points → buildings within the road corridor are removed.
```
AddNode(graph, "Difference", "ClearForRoad", jsonParams={})
ConnectNodePins(ClipBlocks,"Out", ClearForRoad,"In")        # keep
ConnectNodePins(RoadCorridor,"Out", ClearForRoad,"Differences")  # subtract  [CONFIRM] pin label
```
Then Stage D consumes `ClearForRoad` output instead of `ClipBlocks`.

**Visible beat:** a highway carves through the grid, buildings vacate its path, road ribbon
appears. 
**QA:** building count drops after wiring the Difference; road mesh visible following the spline.

**Rank: Feasible** — the only soft spot is the road *mesh* (`Spawn Spline Mesh` needs a road
static mesh asset). If none exists, the road still reads via cleared corridor + a tinted strip
of sampled points; ship that as fallback.

---

## STAGE F — Realistic swap (photoreal)  ·  **Partial / USER GATE**

For photorealism, replace the 12 stylized towers with **City Sample / Fab** building kits:
- **City Sample buildings** (the official Epic "Matrix Awakens" / City Sample sample) — the
  literal asset set the demo uses. Provides modular building meshes + materials designed for
  PCG instancing.
- **Fab marketplace** modular-building / megascans kits.

**What's via MCP vs. not:**
- Swapping the spawner palette to new mesh paths = **Feasible via MCP** (just change the
  `Static Mesh Spawner` mesh list / re-point `PCGMeshSelector*` at the new `/Game/...` paths,
  re-execute).
- **Acquiring** City Sample / Fab assets is **NOT via MCP**. It requires an **Epic Games
  account login + Fab/Marketplace download + add-to-project** in the Epic Launcher. 

> ⚠️ **USER GATE — flag clearly:** Stage F cannot be done autonomously. A human must log into
> Epic, download City Sample (it is large, multi-GB) or a Fab building kit, and import it into
> the project. Only after that can the MCP re-point the spawner. Do not promise photoreal in
> the live build unless these assets are already in `/Game/`.

**Rank: Partial** — palette swap is trivially MCP-driven; the asset acquisition is a hard
human/login gate.

---

## Stage-by-stage feasibility scorecard

| Stage | What | Rank | Note |
|---|---|---|---|
| A | City shape (draw / surface) | **Feasible** | `DrawSpline` (live) or `Create Surface From Spline` (auto) |
| B | Districts (colored regions) | **Partial** | No Voronoi node → `Cluster` (KMeans) substitute; color via Visualize Attribute or per-instance material |
| C | Blocks (grid + streets) | **Feasible** | `Create Points Grid` + clip; streets = cellSize gap |
| D | Buildings rise + color-coded | **Feasible** | `Transform Points` (Z scale) + `Static Mesh Spawner` w/ our 12 towers + `PCGMeshSelectorByAttribute` |
| E | Highway splines | **Feasible** | `DrawSpline` + `Spline Sampler` + `Difference` to clear corridor; road mesh is the soft spot |
| F | Realistic swap | **Partial / GATE** | Palette swap = MCP; City Sample/Fab download = Epic-login human gate |

---

## Making it READ as "building live" (presentation layer)

The audience-facing trick is **incremental execute**. Don't build the whole graph then run
once. Instead:
1. Build Stage A nodes → `ExecuteGraphInstance` → footprint appears.
2. Add Stage B nodes → `ExecuteGraphInstance` → colored districts appear.
3. Add Stage C nodes → execute → block grid appears.
4. Add Stage D nodes → execute → **buildings rise**.
5. Add Stage E nodes → execute → highway carves through.

Each `AddNode`+`ConnectNodePins`+`ExecuteGraphInstance` triple is one watchable beat. Use
`AddCommentBox` to label each stage's node group on the graph canvas (also visible if the
graph editor is on screen). Drop a camera with `SceneTools` / EditorAppToolset viewport camera
before each execute for a clean reveal angle. Theatrically, gate districts behind an
`ActiveDistrict` graph param and re-execute to pop them one at a time.

---

## Single most-important build-time confirmations (do these FIRST, in order)

1. **Tower `/Game/` path** — confirm `/Game/FuturisticCity/Towers/Tower_01..12` exist in the
   Content Browser (`AssetTools` / content-browser nav). Everything in Stage D depends on it.
2. **`PCGMeshSelector*` class paths** — `ObjectTools.list_subclasses` on
   `/Script/PCG.PCGMeshSelectorBase` → get exact refPaths for Weighted / ByAttribute.
3. **`Spawn Spline Mesh` schema** — `GetNativeNodeSchema "Spawn Spline Mesh"` (Stage E road).
4. **`Match And Set Attributes` schema** — for the DistrictID→SizeClass mapping (Stage D1).
5. **`Difference` pin labels** — confirm "In" vs "Differences"/"Source" pin names (Stage E).

---

## BLUNT OVERALL VERDICT

**We can replicate the demo faithfully — ~85% — entirely through the MCP, with one honest
substitution and one human gate.**

- City shape, blocks, building rise, color-coding, and highways are **fully MCP-authorable and
  executable** with the exact nodes verified above. The MCP `PCGToolset` is a real graph
  authoring API (create graph, add/wire nodes, set params, spawn volume, execute, inspect) —
  this is genuinely a "watch the agent build a city" demo, not a fake.
- **The single biggest deviation:** there is **no native Voronoi node**, so districts are
  produced by the `Cluster` (KMeans) node. Visually identical (irregular nearest-centroid
  regions), mathematically different. This is the one place a PCG expert in the audience could
  say "that's not the demo's Voronoi." It is not a blocker — it's a faithful stand-in.
- **The single biggest BLOCKER to the *photoreal* finish (Stage F):** acquiring City
  Sample / Fab assets requires an **Epic Games login + multi-GB Marketplace download +
  import**, which the MCP cannot do. For the *first pass we need nothing* — our 12 imported
  towers are a complete, working palette and the live build stands on its own. Photoreal is a
  later, human-gated upgrade.

Fallback if any PCG node misbehaves live: `ProgrammaticToolset.execute_tool_script` +
`SceneTools.add_to_scene_from_asset` can grid-place the 12 towers directly (fake
districts/blocks by coloring/positioning), bypassing PCG entirely. Slower, less elegant, but
guarantees a city on screen. Keep it in the back pocket; don't lead with it.
