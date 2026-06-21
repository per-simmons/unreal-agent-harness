# PCG Procedural City — Research Brief

> Goal: replicate Epic's "watch a city build itself" demo (oval/shape footprint → colored
> districts → blocks → buildings → highway splines → realistic city), driven live from a
> chat/agent panel. We already have 12 custom tower meshes destined for
> `/Game/FuturisticCity/Towers/`.
>
> Researched 2026-06-20 for UE 5.8 on the Mac Studio harness. Every claim has a URL.
> Skeptic flags (⚠️) mark older-UE or paid/login-gated info.

---

## 0. TL;DR / recommended fastest path

There is **no single "click and the whole city assembles" Epic sample** you can download and
run as-is. The demo Pat is describing is a **composite** of two real Epic things plus a
runtime trigger:

1. **The technique** = the standard PCG "area → Voronoi districts → grid of blocks →
   spawn building meshes → spline roads" graph, shown most directly in Epic's
   **Unreal Fest 2025 "Buildings and Biomes PCG"** talk and the **PCG Biome Core** plugin.
2. **The "watch it build live"** = UE 5.7+ **PCG Editor Mode** + **runtime generation**
   (PCG can regenerate at runtime / on parameter change). The "oval → districts → blocks →
   buildings" reveal is staged: you fire each PCG stage in sequence and let the viewport
   redraw. Color-coded districts = debug-colored point sets per Voronoi cell.
3. **The chat/agent panel** is **not** an Epic feature — that is *our* layer. We drive the
   PCG graph's exposed parameters (and stage triggers) over the Unreal MCP from Claude Code.
   That is exactly the harness we already have.

**Fastest convincing demo given our 12 towers:**

1. Install **PCGEx** (free, MIT, supports 5.8) — gives Voronoi/Delaunay district partition +
   A* road pathfinding that base PCG lacks. `github.com/PCGEx/PCGExtendedToolkit`.
2. Footprint actor (a spline or volume — an oval is just a closed spline) → **PCGEx Voronoi**
   to cut it into N districts → debug-color each cell (the "colored districts" beat).
3. Per district: **Create Points Grid** → **Subdivide / partition** into block lots → inset
   each lot (Bounds Modifier) → **Static Mesh Spawner** picking from a weighted palette =
   our 12 `/Game/FuturisticCity/Towers/` meshes (+ free filler, see §3) keyed by an attribute
   for height class.
4. Roads/highways: **PCGEx pathfinding (A*)** between district centroids → **Spline Sampler**
   → spawn road meshes / a highway spline. (Base-PCG-only alternative: hand-draw the highway
   spline in PCG Editor Mode and let buildings `Difference` against it.)
5. Stage the reveal from the agent panel: expose `enableDistricts`, `enableBlocks`,
   `enableBuildings`, `enableRoads` (or per-stage subgraphs) as graph params; the MCP toggles
   them one at a time, calling regenerate → viewport animates the build.
6. "Realistic" final beat: swap/augment the palette with **City Sample Buildings** (free w/
   Epic login, 2,000+ meshes) for photoreal midground; keep our towers as hero pieces.

Realistic effort: a believable staged build is **days, not weeks** because PCGEx does the hard
graph math and we already have the MCP + towers. The genuinely realistic *final frame* is the
expensive part (lighting, City Sample assets, density) — approximate it, don't chase Matrix
Awakens fidelity.

---

## 1. What the demo actually IS — candidates & sources

The "city builds itself live, driven from a panel" demo is **not one named downloadable**.
It maps to these real Epic artifacts:

### a) Unreal Fest 2025 — "Buildings and Biomes PCG" (closest match)
The Learning Lab on integrating PCG + the Biomes plugin to build dynamic environments,
including buildings. This is the talk where you see districts/blocks/buildings assemble.
- https://dev.epicgames.com/community/learning/talks-and-demos/pBl1/unreal-engine-unreal-fest-2025-buildings-and-biomes-pcg
- ⚠️ Epic dev-community pages are CAPTCHA/login-walled to scrapers — watch it logged in.

### b) PCG Biome Core & Sample plugins (the "colored districts" system)
Biome Core manages procedural content across distinct zones, each zone = its own PCG graph,
with blending/transition rules where zones meet — exactly the "color-coded districts" idea
applied to a city. Runtime vs pre-serialized options.
- Overview: https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-overview-guide-in-unreal-engine
- Reference: https://dev.epicgames.com/documentation/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-reference-guide-in-unreal-engine

### c) GDC 2026 PCG framework (the "live, zero-code, watch it build" feel)
UE 5.7 graduated PCG to production: **PCG Editor Mode** (in-viewport spline drawing, point
painting, volume creation that triggers generation in real time), GPU Compute path, **2×
performance vs 5.5**, **Biome Core**. This is the source of the "draw a shape, watch it fill"
live-demo vibe.
- https://blog.imseankim.com/unreal-engine-5-7-pcg-framework-gdc-2026-procedural-worlds/ (3rd-party, accessible)

### d) Electric Dreams Environment (the famous "1 artist, 0 code, 4km²" PCG demo)
The flagship "PCG is production-ready" sample — a 4km×4km procedural jungle. It is the
*nature/biome* showcase, not a city, but it is the demo people remember as "the PCG one."
- https://www.unrealengine.com/en-US/electric-dreams-environment
- ⚠️ It's a biome/foliage sample, **not** a city builder. Useful as a reference for runtime
  PCG + Biome Core, not for building meshes.

### e) City Sample (the "realistic city" people picture at the end)
The Matrix Awakens city. ⚠️ Its city was **generated in SideFX Houdini** and imported via the
**Rule Processor** — it is NOT a PCG-graph city. So it's the *look* target and the *building
asset source*, but its generation pipeline is Houdini, not the PCG graph we'd demo.
- Docs: https://dev.epicgames.com/documentation/unreal-engine/city-sample-project-unreal-engine-demonstration
- Quick start: https://dev.epicgames.com/documentation/en-us/unreal-engine/city-sample-quick-start-for-generating-a-city-and-freeway-in-unreal-engine-5

**Verdict:** the demo = (b)+(c) technique with our agent panel on top; (e) is the asset/look
source; (d) is the "feel" reference. The chat-driven build is our own layer.

---

## 2. The standard PCG city technique (node-by-node)

PCG generates **Points** (transforms + density + custom attributes) and a **Static Mesh
Spawner** turns points into meshes. A minimal **area → grid of blocks → spawn buildings**:

```
[Footprint]            Closed spline (an "oval" = an ellipse spline) OR a PCG Volume.
   │                   This is the city outline.
   ▼
[Spline Sampler /      Convert the footprint into a filled region of points / bounds.
 Surface Sampler]      (Surface Sampler conforms points to the landscape surface.)
   │
   ▼
[Districts]            PCGEx ► Voronoi  (seed N points, partition the area into N cells).
   │                   Tag each point with a `districtId` attribute. Debug-color by
   │                   districtId = the "colored districts" reveal beat.
   ▼
[Blocks]               Per district: Create Points Grid (regular lattice) → Subdivide /
   │                   partition into lots. Bounds Modifier to inset each lot (street gaps).
   ▼
[Filter / classify]    Point Filter + Density Filter to drop edge/road lots.
   │                   Write a `heightClass` attribute (e.g. by distance-to-center:
   │                   downtown = tall, outskirts = short) → drives mesh choice.
   ▼
[Roads]                Difference: subtract road/spline corridors so buildings don't spawn on
   │                   streets. Highways = PCGEx A* pathfinding between district centroids →
   │                   Spline Sampler → road mesh, or a hand-drawn PCG-Editor-Mode spline.
   ▼
[Self Pruning]         Bounds Modifier + Self Pruning so footprints don't overlap.
   │
   ▼
[Static Mesh Spawner]  Weighted mesh entries keyed by `heightClass`. Palette =
                       /Game/FuturisticCity/Towers/ (our 12) + filler kit (§3).
                       Transform Points for per-instance rotation/scale variation.
```

Confirmed node names (UE 5.8):
- **Surface Sampler, Spline Sampler, Static Mesh Spawner, Transform Points, Point Filter,
  Density Filter, Difference, Bounds Modifier, Self Pruning, Normal To Density, Projection**
  — Epic 5.8 PCG overview: https://dev.epicgames.com/documentation/unreal-engine/procedural-content-generation-overview
  and field walkthrough: https://medium.com/@deaconline/procedural-content-generation-pcg-b54f4c1959cd
- **Create Points Grid / Subdivision / Voronoi partition** are NOT well-documented in base PCG
  for spatial *partitioning* — get them from **PCGEx** (Voronoi/Delaunay/cluster/partition).

Two community city walkthroughs (district/block/building + spline roads):
- "Create Entire Cities Automatically With PCG Splines": https://dev.epicgames.com/community/learning/tutorials/Obk3/create-entire-cities-automatically-with-pcg-splines-procedural-content-generation-in-unreal-engine (YouTube mirror: https://www.youtube.com/watch?v=STqt92VF3KM)
- "You Won't Believe How Easy City Streets Can Be in UE5 Using PCG" — uses the **PCGEx plugin**, UE 5.7: https://dev.epicgames.com/community/learning/tutorials/VxP9/unreal-engine-you-won-t-believe-how-easy-city-streets-can-be-in-ue5-using-pcg
- ⚠️ Both are 5.6/5.7-era; node names are stable into 5.8 but UI/PCG-Editor-Mode differs.

---

## 3. Free starting assets

### Plugins / generators (free, open source)
- **PCGEx (PCG Extended Toolkit)** — the missing pieces: Delaunay, **Voronoi**, convex hulls,
  MST, **A*/Dijkstra pathfinding** (for roads), partition/cluster, filtering. **MIT license,
  free, actively supports UE 5.8/5.7/5.6.** Available on GitHub and Fab.
  - https://github.com/PCGEx/PCGExtendedToolkit
  - Companion: **PCGExElementsWatabou** imports Watabou's procedural city maps (oval/medieval
    layouts) straight into PCGEx — could shortcut the district/block layout entirely.
    https://github.com/PCGEx/PCGExElementsWatabou
- **Grzybojad/ProceduralCityGeneration** — C++ UE city gen (terrain + Voronoi roads +
  building extrusion). MIT, ~18 stars, ⚠️ UE version unstated/old; reference, not drop-in.
  https://github.com/Grzybojad/ProceduralCityGeneration

### Building mesh kits

**Truly CC0 (no login, redistributable) — but generic/low-poly, NOT futuristic:**
- Kenney City Kits (Roads/Commercial/Suburban/Industrial) — CC0, FBX/OBJ/glTF, no login.
  https://kenney.nl/assets/city-kit-commercial (+ -roads, -suburban, -industrial)
- Quaternius **Ultimate Buildings Pack** — CC0, FBX/OBJ/Blend, no login.
  https://quaternius.com/packs/ultimatetexturedbuildings.html
- Quaternius **Modular Sci-Fi MEGAKIT** — CC0; mostly interiors/greebles, use for detailing.
  https://quaternius.com/packs/modularscifimegakit.html
- Poly Pizza (per-asset CC0/CC-BY, GLB/OBJ): https://poly.pizza/search/skyscraper
- Sketchfab CC0 filter, e.g. "FREE Sci-Fi City (CC0)" — ⚠️ free *account* login to download,
  many "free sci-fi" results are actually CC-BY/paid, verify the badge.

**Free with Epic login (Epic Content License, UE-only, NOT CC0) — the realistic palette:**
- **City Sample Buildings** — 24 modular kits + 44 sample buildings, **2,000+ meshes**, UE
  5.0+, .uasset native. ⚠️ Epic login gate. Best realistic midground; push neon via emissive.
  https://www.fab.com/listings/008fe959-5511-428e-93bd-f99b1179f6d5
- Full **City Sample** project (city + crowds + vehicles): https://www.fab.com/listings/4898e707-7855-404b-af0e-a505ee690e68
- ⚠️ "Downtown West Modular Pack" was a free monthly drop but **verify free vs paid** now in
  the Launcher. "Downtown/Suburbs – City Pack" Fab listings are largely **paid**.

**Best for FUTURISTIC/neon (to match our 12 towers):**
- **KitBash3D — Mini Kit: Neo City (FREE)** — Neo-Tokyo/cyber neon hero pieces. ⚠️ NOT CC0
  (proprietary free license, not redistributable raw), free *account* login, FBX/OBJ.
  https://kitbash3d.com/products/mini-kit-neo-city

**Asset bottom line:** no single CC0 source gives cohesive *futuristic* tower filler. For the
demo, combine **our 12 towers (hero)** + **City Sample Buildings (free w/ login, realistic
filler)**; if we must stay fully redistributable/CC0, fall back to Kenney + Quaternius (looks
stylized, not neon).

---

## 4. UE 5.8 PCG notes (vs the 5.3/5.4 tutorials online)

- ⚠️ **Most PCG city tutorials are 5.3–5.7.** Core node names (Surface Sampler, Static Mesh
  Spawner, Difference, Density Filter, Self Pruning) are stable, but two big shifts:
- **PCG Editor Mode** (5.7+) — in-viewport spline drawing, point painting, volume creation
  that trigger generation in real time. This is new vs older tutorials and is *the* tool for a
  live "draw the footprint, watch it fill" beat.
  https://blog.imseankim.com/unreal-engine-5-7-pcg-framework-gdc-2026-procedural-worlds/
- **Non-destructive manual edits** (5.8) — you can hand-edit on top of procedural output
  without breaking proceduralism. Lets us nudge the demo without re-running everything.
- **Complex attribute types** (5.8) — PCG now supports arrays/structs/sets/maps + new example
  graphs for spatial ops. Useful for richer `districtId`/`heightClass` data.
- **GPU Compute path** (5.7+) — point distribution/density on GPU, ~2× vs 5.5. Matters for a
  full-city point count staying interactive during the live build.
- **Mesh Terrain** (5.8, experimental) — mesh-based terrain fully interoperable with PCG
  (overhangs/tunnels). Not needed for a flat city but available.
- Source: UE 5.8 release post https://www.unrealengine.com/news/unreal-engine-5-8-is-now-available

---

## 5. The "realistic buildings" final step

How the canonical realistic city (Matrix Awakens / City Sample) gets there, and the cheap way
to approximate it:

- **City Sample's realism is Houdini-generated, Rule-Processor-imported, Nanite + Lumen +
  World Partition + MetaHuman crowds + 2K–8K textured building meshes.** That is the photoreal
  end frame — and it is heavy (needs a strong GPU, SSD, DX12).
  https://dev.epicgames.com/documentation/en-us/unreal-engine/city-sample-quick-start-for-generating-a-city-and-freeway-in-unreal-engine-5
- ⚠️ We do **not** want to reproduce that pipeline (Houdini dependency, multi-GB, perf). The
  PCG graph approach reaches "convincingly real-ish" without Houdini.

**Lightest-weight approximation for the demo:**
1. Use **City Sample Buildings** meshes (free, 2,000+, already Nanite-friendly) as the PCG
   spawn palette for midground filler; keep our 12 towers as foreground hero towers.
2. Turn on **Nanite** on the meshes + **Lumen** GI + a single skylight/sun for instant
   "realistic" lighting — far cheaper than baking.
3. Emissive neon materials on windows/signage to sell the futuristic look and hide low-detail
   filler at night (night skyline = forgiving + dramatic for the "finished city" beat).
4. Atmospheric fog + a hero camera move on the final frame — the reveal sells realism more
   than per-building detail.
5. Skip crowds/vehicles/MetaHumans for v1 (huge cost, low marginal wow for a "city builds"
   demo). Add a few City Sample vehicles only if the final shot needs life.

---

## Open questions / risks
- ⚠️ Confirm PCGEx packages cleanly for **UE 5.8 on Apple Silicon / Metal** (it lists 5.8
  support but most users are Windows; may need a source build like Cesium did).
- ⚠️ The "colored districts" beat needs PCG **debug-draw by attribute**; verify that survives
  into a packaged/PIE view or stays editor-only (likely editor-only — fine for a screen-record).
- The agent-panel staging assumes PCG graph params are reachable over the **Unreal MCP**
  (`mcp__unreal`). Verify the MCP can (a) set exposed graph params and (b) trigger regenerate;
  if not, drive via a small Editor Utility / Python the MCP calls.

---

## Sources
- Epic 5.8 PCG overview — https://dev.epicgames.com/documentation/unreal-engine/procedural-content-generation-overview
- Unreal Fest 2025 Buildings & Biomes PCG — https://dev.epicgames.com/community/learning/talks-and-demos/pBl1/unreal-engine-unreal-fest-2025-buildings-and-biomes-pcg
- PCG Biome Core overview — https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-overview-guide-in-unreal-engine
- GDC 2026 PCG framework (3rd-party) — https://blog.imseankim.com/unreal-engine-5-7-pcg-framework-gdc-2026-procedural-worlds/
- Electric Dreams Environment — https://www.unrealengine.com/en-US/electric-dreams-environment
- UE 5.8 release — https://www.unrealengine.com/news/unreal-engine-5-8-is-now-available
- City Sample docs — https://dev.epicgames.com/documentation/unreal-engine/city-sample-project-unreal-engine-demonstration
- City Sample city+freeway quick start — https://dev.epicgames.com/documentation/en-us/unreal-engine/city-sample-quick-start-for-generating-a-city-and-freeway-in-unreal-engine-5
- "Cities with PCG Splines" tutorial — https://dev.epicgames.com/community/learning/tutorials/Obk3/create-entire-cities-automatically-with-pcg-splines-procedural-content-generation-in-unreal-engine
- "City Streets in UE5 Using PCG" (PCGEx) — https://dev.epicgames.com/community/learning/tutorials/VxP9/unreal-engine-you-won-t-believe-how-easy-city-streets-can-be-in-ue5-using-pcg
- PCG-in-a-nutshell node walkthrough — https://medium.com/@deaconline/procedural-content-generation-pcg-b54f4c1959cd
- PCGEx toolkit (MIT, 5.8) — https://github.com/PCGEx/PCGExtendedToolkit
- PCGEx Watabou map importer — https://github.com/PCGEx/PCGExElementsWatabou
- Grzybojad/ProceduralCityGeneration — https://github.com/Grzybojad/ProceduralCityGeneration
- City Sample Buildings (Fab) — https://www.fab.com/listings/008fe959-5511-428e-93bd-f99b1179f6d5
- City Sample (Fab) — https://www.fab.com/listings/4898e707-7855-404b-af0e-a505ee690e68
- City Sample free assets (CG Channel) — https://www.cgchannel.com/2022/04/download-epic-games-free-city-sample-assets-for-ue5/
- Kenney City Kits (CC0) — https://kenney.nl/assets/city-kit-commercial
- Quaternius Ultimate Buildings (CC0) — https://quaternius.com/packs/ultimatetexturedbuildings.html
- KitBash3D Mini Kit Neo City (free) — https://kitbash3d.com/products/mini-kit-neo-city
