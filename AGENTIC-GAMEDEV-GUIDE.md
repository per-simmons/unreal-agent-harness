# Building a Pro Game-Dev Agent in Unreal Engine — Build Log & Guide

> Living doc. Started Jun 18 2026. The story of wiring Claude to Unreal Engine 5.8 so an agent can
> build (and QA) real 3D scenes — a GTA-Vice-City neon city, and a real city (NYC). Written to teach.
> Pat's running opinions are in **§11**. Keep appending as we go.

---

## 1. The vision
Make an AI agent that builds "sick-ass" 3D scenes in Unreal like a pro game dev — and, crucially,
**QAs its own work** instead of flying blind. First target: a 1980s-Miami / GTA-Vice-City neon city.
Stretch target (added mid-session): **a real city — actual New York City.**

The big realization early on: you don't "train" a model to do this — you **build a harness around it**
(eyes + hands + knowledge + a critique loop). That harness is the real product.

## 2. The setup gauntlet (what it actually took)
Nothing about getting here was one-click. In order:
- **Disk was 100% full.** Freed ~space by clearing regenerable caches (npm/brew/pip/uv), old iOS
  simulators, and **`node_modules` across ~/coding** (44 GB) — but the freed space didn't show until we
  **thinned the Time Machine local snapshot** (`tmutil thinlocalsnapshots /`), which was pinning deleted files.
- **Installed UE 5.8** via Epic Games Launcher (the Launcher ≠ the Engine ≠ the Editor — three separate things).
- **Metal Toolchain error** on first launch: Xcode 26 ships the Metal compiler as a separate download —
  fix: `xcodebuild -downloadComponent MetalToolchain`.
- **MCP plugin** ("Unreal MCP", official, experimental, built into 5.8). Gotchas that cost an hour:
  - `bAutoStartServer` defaults **false** — enabling the plugin alone never starts the server.
  - Default port **8000 was taken by WhisperFlow** (Pat's dictation) → moved MCP to **8123**.
  - Set both via `EditorPerProjectUserSettings.ini` with the editor **fully quit** (it overwrites on close).
- **The toolsets weren't registering** — only a useless "AgentSkillToolset" showed. Root cause: UE ships
  the building toolsets as ~28 **disabled-by-default plugins**; enabling the **`AllToolsets`** aggregator
  (+ `PythonScriptPlugin`) in the `.uproject` registered the full palette.

**Lesson for the audience:** the experimental AI tooling is real but raw — budget time for plumbing.

## 3. The harness — how the agent sees and builds
- **Driving UE:** `mcp__unreal__call_tool {toolset_name, tool_name, arguments}`. Discover with
  `list_toolsets` / `describe_toolset`. Key toolsets: `SceneTools` (place/find/trace actors),
  `StaticMeshTools` (incl. `import_file`), `MaterialTools`, `ObjectTools`, `EditorAppToolset`
  (camera + `CaptureViewport`), `LogsToolset`, `PCGToolset`, `ProgrammaticToolset` (batch).
- **Eyes:** `CaptureViewport` renders the editor viewport (from any pose, with an optional coordinate
  grid + actor labels). It returns a multi-MB base64 blob that floods context — so the runtime auto-saves
  it to a file, and our harness decodes it.
- **The harness** (`~/coding/unreal-agent-harness/ue_qa.py`): `decode` → small PNG + JSON sidecar
  (camera pose + labeled actors); `refdiff` → side-by-side vs a reference image. See `README.md`.
- **The loop:** act → capture 3 angles (top-down / eye-level / player-eye) → read logs → check
  overlaps (`find_actors` bounds / `trace_world`) → diff vs moodboard → correct.
- **Two hard constraints:** raw HTTP to the server returns empty for big results (async SSE) — always
  go through the agent tool layer. And there's **one editor on one game thread** → serialize all mutations.

## 4. The skill pack (`.claude/skills/`)
`unreal-mcp-toolsets` (how to drive UE), `unreal-scene-building` (level/lighting/neon/PCG/QA recipes),
`vice-city-art-direction` (the look as builder targets + critic pass/fail), `unreal-engine-cpp-pro`
(C++ hygiene). To add: `blender-headless-modeling` (see §8).

## 5. Getting assets (acquire AND generate)
- **CC0 downloads (359 MB, free):** Kenney (roads/commercial/suburban/cars), KayKit City Builder Bits,
  **Quaternius downtown-city-megakit** (153 modular building/street pieces — the richest), Poly Haven
  `venice_sunset_4k.hdr` + asphalt/concrete PBR.
- **Generated on Pat's ChatGPT sub (no API spend)** via `~/tools/chatgpt-imagegen`: a 6-image Vice City
  **moodboard** (the Critic's diff target) + textures/sprites (tileable facade, wet asphalt, transparent
  neon "MIAMI" sign, palm silhouette). Gotcha: this subscription generator bakes a grey checkerboard
  instead of true alpha — key it out in PIL to get real transparency.
- **Image-to-3D:** Meshy (via **fal.ai**, ~4 min, PBR) and TRELLIS (via Replicate, ~1 min, color-only).

## 6. The methods sandbox (the bake-off) — building the same building every way
| Method | How | Result |
|---|---|---|
| **M1 primitives** | stack UE BasicShapes | crude white box; instant; free |
| **M2 CC0 kit** | import Quaternius FBX | **cleanest real building out of the box**; trivial |
| **M4 Blender headless** | `bpy` script → FBX → import | good controllable art-deco massing; no materials yet |
| **M5 Meshy** | concept img → fal.ai → GLB→FBX | colorful PBR but blobby; mis-scaled/oriented |
| **M6 TRELLIS** | concept img → Replicate → GLB→FBX | recognizable, lighter, softer; color-only |
| M3 Fab/Megascans | (pending Epic login) | photoreal — expected best base |
| M7 Houdini | (pending SideFX account) | AAA procedural |

**Pipeline gotchas:** `import_file` takes **FBX/OBJ only, not glTF/GLB** → convert GLB→FBX with headless
Blender. Image-to-3D imports tiny (~1.4 m, scale ~10×) and axis-rotated (Y-up→Z-up).

**Verdict:** CC0 kits win for the repeated city mass; Blender headless for bespoke shapes; image-to-3D
only for one-off props (messy topology, as predicted). Fab/Megascans likely wins the photoreal base.

## 7. The pro 3D landscape (and what's agent-drivable)
You rarely "generate from scratch" — you assemble or model. Methods: DCC hand-modeling (Blender/Maya),
in-engine modeling (UE Modeling Tools), procedural (Houdini / UE PCG), kit-bashing (assemble modular
parts), scanning (Megascans/RealityCapture), AI gen (image/text-to-3D). **Every major tool now has both
a Python API and a community MCP server** — Blender (`bpy` + blender-mcp), Houdini (`hou` + houdini-mcp,
free Apprentice), Unreal (the official MCP). And Unreal already ships **enormous free libraries** (Fab,
free Megascans, the City Sample) — often you generate nothing.

## 8. Blender headless deep-dive + resources
We chose **headless `bpy`** (`blender --background --python`) for agent modeling: it IS the full Blender
API, runs locally on the M4 Max in seconds, unattended, free. `blender-mcp` exists but needs the GUI open.
Resources to make the agent smarter (to integrate):
- **Infinigen** (Princeton) — huge procedural Python+Blender generation library; LLM-drivable.
- **LL3M** — multi-agent LLM Blender modeler (plan→write→debug→refine) — template for our Builder+Critic.
- **BlenderLLM / 3D-GPT / BlenderGPT** — NL→bpy script generation.
- **Buildify** (free, Geometry Nodes) — assembles buildings from part libraries.
- **awesome-blender** — the index of everything.
- **Flue blender_adapter** (SFKislev/Flue) — clean pattern: tokenized localhost eval endpoint into bpy on
  the main thread; **"search a `docs/api-index.txt` before acting"** instead of trusting training data;
  `undo_push` after each mutation; non-destructive review-verify. Good patterns to adopt in our harness.

## 9. Cloning a REAL city — DEMO TARGET: real New York City (open-source only)
**This is the YouTube demo:** a real NYC, built with open-source tools only. Routes:
1. **PRIMARY (fully open): Blender-OSM (`blosm`, GPL) + OpenStreetMap.** Imports real Manhattan street
   grid + building footprints (many with real heights via `building:levels`; defaults where missing) →
   3D buildings → export to UE. 100% open data + open addon, local. Optionally **Buildify** (free GN) to
   prettier-ize footprints, and **Infinigen** (BSD, open) for procedural variety/props.
2. **Open-ish: Cesium for Unreal** (Apache-2.0, open plugin) streaming the **Cesium OSM Buildings** layer
   (free, OSM-derived, global extruded buildings) — near-instant whole-NYC in UE. Needs a free Cesium ion
   account (hosted service, but the data is OSM-derived/open and the plugin is open).
3. **EXCLUDED (proprietary):** Google Photorealistic 3D Tiles (Google service), Fab/Megascans (Epic EULA),
   Meshy (SaaS), BlenderGPT (GPT-4). Per "open-source only," we don't use these for the demo.

## 10. Status & open gates
- DONE: setup, harness, skill pack, asset acquisition, the 5-method sandbox.
- GATED on Pat: **Fab login** (photoreal Megascans/City Sample, M3), **SideFX account** (Houdini, M7).
- NEXT: Phase 1 Builder+Critic Vice City block (dusk lighting + dressing); Blender-OSM/Cesium real-city
  experiment; adopt Flue's api-index + undo patterns into the harness.

## 11. Pat's opinions & notes (living)
- M6 (TRELLIS) "looked good, just small." M5 (Meshy) "a little blotchy." M2 (CC0) "kind of boring — but
  maybe we just didn't add stuff" (correct: it's undressed; neon + materials will sell it).
- Decided: **headless Blender** is the path.
- **DEMO DECISION (locked): the YouTube demo = real New York City.** The creative GTA-Vice-City city is
  **pinned** for later.
- **CONSTRAINT (locked): open-source only.** No proprietary SaaS / "other people's software" unless it's
  open and we self-leverage. Explicitly out: BlenderGPT (GPT-4 = old + proprietary), Meshy, Fab/Megascans,
  Google 3D Tiles. In: Blender + `blosm` (GPL), OpenStreetMap data, Infinigen (BSD), Cesium-for-Unreal
  (Apache, open plugin), our own harness.
- Loves the **OpenStreetMap** real-city idea and **Infinigen** (wants to try + build on it). LL3M = good
  multi-agent template. Flue (open, 13+ app bridge) = noted for the whole creative stack.
- This doc exists to **teach his audience** the whole workflow — keep it narrative + honest about gotchas.

## 13. TOOL CATALOG — every path found (status: 🟢 using · 🟡 try · 🔵 evaluate · 📌 pinned · ⛔ excluded)
Goal: leave no tool untried. Status reflects the open-source-only + real-NYC demo constraints.

**A. Agent → 3D-app bridges (drive the software)**
- 🟢 Unreal MCP (official, 8123) — our hands in UE.
- 🟢 Blender headless `bpy` (`--background --python`) — scripted modeling, open.
- 🟡 `blender-mcp` (ahujasid, open) — live GUI Blender control.
- 🔵 **Flue** (SFKislev, open) — one bridge for 13+ apps (Blender, Houdini, Unity, 3ds Max, Photoshop,
  Premiere, AE, Office); `shell→bridge→app→JSON`, no MCP overhead. Could unify the whole stack.
- 📌 `houdini-mcp` (eliiik/oculairmedia, open) — needs Houdini.

**B. Agent 3D-modeling/generation frameworks**
- 🟡 **Infinigen** (Princeton, BSD) — huge procedural Python-Blender generator; Pat wants to try + build on.
- 🟡 **LL3M** — multi-agent plan→write→debug→refine bpy (our Builder+Critic template).
- 🔵 **3D-GPT** (Chuny1) — multi-agent that drives Infinigen from text.
- 🔵 BlenderLLM — fine-tuned LLM → Blender CAD scripts.
- ⛔ BlenderGPT (gd3kr) — GPT-4, proprietary/old.

**C. Real-city / GIS → 3D pipelines (the NYC demo)**
- 🟡 **Blender-OSM / `blosm`** (vvoovv, GPL free tier) — OSM → buildings+terrain → UE. PRIMARY.
- 🟡 **Blender GIS** (domlysz, GPL) — OSM/shapefile/GeoTIFF import, real terrain + basemaps.
- 🔵 **Cesium for Unreal** (Apache) + **Cesium OSM Buildings** (free, OSM-derived) — stream whole NYC into UE.
- 🔵 **OSM2World** / **osmbuildings** — OSM → 3D models (open).
- 🟡 **Buildify** (free GN) — footprints → nicer buildings.
- 🔵 QGIS (open) — pull NYC Open Data (building heights/footprints) for accuracy.
- ⛔ Google Photorealistic 3D Tiles, Mapbox — proprietary.

**D. Procedural**
- 🟢 UE **PCG** (built-in) — scatter/rules at city scale.
- 🟡 Infinigen, Buildify, Geometry-Nodes city kits (Easy City Creator, Building Blocks).
- 📌 Houdini — AAA procedural city.

**E. Open/CC0 asset sources** (have 359MB)
- 🟢 Kenney, Quaternius, KayKit, Poly Haven (HDRI+PBR). 🟡 ambientCG, Poly Pizza, Sketchfab-CC0, OSM.

**F. Image / texture / image-to-3D**
- 🟢 `chatgpt-imagegen` (Pat's sub — used for moodboard/textures; not FOSS but $0 + his account).
- 🟡 **Self-hostable OPEN image-to-3D**: TRELLIS (MIT), Hunyuan3D, TripoSR, Stable-Fast-3D — run locally
  on the M4 Max to stay fully open (vs the hosted Meshy/Replicate we sandboxed).
- ⛔ Meshy (hosted SaaS).

**G. UE import paths**
- 🟢 `StaticMeshTools.import_file` (FBX/OBJ only). 🔵 Interchange glTF importer, Datasmith (CAD/3ds Max).

## 14. tool-scout findings — the FOSS real-NYC→UE pipeline (verified Jun 18)
**Key insight:** geometry + real heights are 100% solved with free open data + free tools. The weak link
is AI mesh-gen on Apple Silicon (mostly CUDA-only). **Architect the city from real footprint extrusion,
NOT AI-generated buildings.**

**The "real heights" answer (open data, all EPSG:2263 ft / NAVD88 → reproject + ×0.3048 to metric):**
- ⭐ **NYC Building Footprints** (NYC Open Data, open) — `heightroof` = roof height (the extrusion value),
  `groundelev` = LiDAR ground elev (seat on terrain). SHP/GeoJSON. THE source for real Manhattan.
- **NYC 3-D Building Model** (DCP, open) — ready LOD1 + ~100 LOD2 landmarks, but **2014 vintage** (missing
  new towers) → prefer live Footprints `heightroof`.
- ⭐ **2017 NYC 1-ft LiDAR DEM** (NOAA S3 `noaa-nos-coastal-lidar-pds`, public domain) → UE Landscape 16-bit heightmap.
- OSM height tags only ~31% tagged → fallback only.

**Core FOSS tools (status):** Blender-GIS (GPL, SHP/GeoTIFF/OSM extrude — strongest free), blosm (heights
free), OSM2World (MIT), 3dfier (GPL, footprints+LiDAR→LOD1), Buildify (free GN filler, takes real
footprints), pg2b3dm (MIT, self-host 3D Tiles), cjio/citygml4j (CityJSON/CityGML), val3dity (QA).

**Into UE 5.8:** ⚠️ **Cesium for Unreal (Apache) officially supports UE 5.5–5.7, NOT 5.8 yet** — pin 5.7,
build from source, OR skip Cesium and use the **Interchange glTF headless commandlet** (`AssetTools
import_asset_tasks`) for batch import. Use **World Partition + LWC + Nanite** for city scale. **Send to
Unreal** (Blender→UE, MIT). Datasmith is the wrong tool (CAD/BIM).

**Self-host image-to-3D on M4 Max (for the occasional hero prop):** ⭐ **SF3D / Stable-Fast-3D** (official
MPS support, tested on 64GB Apple Silicon) is the #1 local option; TRELLIS.2-mac / Hunyuan3D-2.1-mac forks
work slower; most others are CUDA-only (rent a GPU / HF Space and pull the .glb back).

**RECOMMENDED PIPELINE:** (1) heights = Footprints `heightroof` + `groundelev`; (2) terrain = 2017 LiDAR
DEM → Landscape; (3) geometry = Blender-GIS/blosm extrude + Buildify, export glTF via Send-to-Unreal — OR
footprints→PostGIS→pg2b3dm self-hosted 3D Tiles; (4) into UE 5.8 via Interchange headless (or Cesium on
5.7); (5) agent drives Blender via blender-mcp/Flue + UE via the MCP toolsets here.

**Risks:** Cesium↔5.8 lag (biggest); self-host Cesium tiles to stay FOSS; AI mesh-gen weak on Mac; 2014
3-D model stale; OSM heights sparse (use `heightroof`).

## 15. NYC approaches — SANDBOX (keep all comparable, like the building bake-off)
Pat wants the different real-NYC methods kept side-by-side to compare, not collapsed into one.
Keep each as its own asset/level + capture a comparable shot. Status:
- **N1 — Open OSM extrusion (OSM Overpass + Blender)** — v1 (uniform/blobby, OSM tags) → v2 (NYC Open
  Data `heightroof`, real varied skyline + streets + concrete material) → v3 (normals fixed + flat ground).
  In `/Game/NYC/`. FOSS. Stylized. ✅ working in 5.8 now.
- **N2 — Cesium + Google Photorealistic 3D Tiles** — actual photoreal NYC streamed in. Needs the
  Cesium plugin (building from source vs 5.8) + Google key (have) + ion token (have). THE demo "wow." ⏳ building.
- **N3 — Cesium OSM Buildings** — Cesium ion's free OSM-derived global buildings; quick, complete,
  stylized; ion token only (no Google/billing). Easy third comparison once the plugin's in.
Capture all three from a matching vantage for the teaching comparison. Decision (open vs photoreal):
Pat leaning photoreal (N2); 5.7 fallback acceptable if 5.8 build hard-walls.

## 12. PINS (parked, revisit later)
- Creative GTA-Vice-City city (we have the moodboard, neon textures, CC0 kits, lighting plan ready).
- Houdini (M7) + Fab/Megascans (M3) — gated and/or proprietary; revisit if constraints change.
- Adopt Flue patterns (api-index-before-acting, undo_push) + evaluate Flue as the multi-app bridge.
- Infinigen integration for procedural variety/props.

## 16. Cesium photoreal tuning reference
Tuning Cesium for Unreal (v2.27, UE 5.8) Google Photorealistic 3D Tiles for max visual quality at street level + good perf, all driven programmatically. Every property/function/cvar below was verified against the source clone at `~/coding/cesium-build/cesium-unreal/Source/CesiumRuntime/Public/` (file:line cited). Cesium does NOT need ray tracing.

### 16.1 — Cesium3DTileset quality / LOD (file: `Cesium3DTileset.h`)
The single most important knob for crisp street-level detail is **MaximumScreenSpaceError (SSE)**.

| Property | Type / default | Line | What it does | Photoreal close-up value |
|---|---|---|---|---|
| `MaximumScreenSpaceError` | double, **16.0** | 374 | Max allowed screen-space error before a tile is refined to higher detail. **Lower = sharper, more tiles loaded, higher cost.** This is THE fix for "blobby" geometry up close. | **8.0** for a clear improvement; **4.0** for very crisp street level (heavier). Don't go below ~3–4 — diminishing returns + memory/RT blowup. Google tiles bottom out at their own native leaf detail, so ultra-low SSE just loads more of the same once you're at the leaves. |
| `PreloadAncestors` | bool, true | 394 | Loads lower-detail ancestors so something is always visible while refining. Keep **true**. |
| `PreloadSiblings` | bool, true | 404 | Preloads siblings of visible tiles (smoother as you pan/turn). Keep **true** for cinematic flythroughs; can set false to save memory if RT-budget-bound. |
| `ForbidHoles` | bool, false | 416 | Forces all child tiles to load before refining a parent, so no gaps appear during refinement. **Set true** for clean close-ups (costs more loads / latency). |
| `MaximumSimultaneousTileLoads` | int32, 20 | 432 | Parallel tile load cap. Raise to **24–32** on a fast machine + connection for quicker fill-in; lower if you're saturating bandwidth. |
| `MaximumCachedBytes` | int64, **256 MiB** (`256*1024*1024`) | 444 | Cache budget. Never unloads tiles still needed to render. Raise to **1–2 GiB** (`1073741824` / `2147483648`) for photoreal so detail doesn't churn as you move. |
| `LoadingDescendantLimit` | int32, 20 | 462 | How many loading descendants a tile tolerates before rendering itself instead of waiting. 0 = strict successive LOD (slow but gradual); high (~1000) = pops in full detail at once. Default 20 is fine; raise toward 100–200 to reach target detail faster at the cost of a visible pop. |
| `EnableFrustumCulling` | bool, true | 482 | Cull tiles outside the camera frustum. Keep **true** (perf). |
| `EnableFogCulling` | bool, true | 499 | Culls far/horizon tiles based on an *internal* fog model (NOT Unreal's atmospheric fog). Keep **true** for perf. Auto-disabled when `UseLodTransitions` is true. |
| `EnforceCulledScreenSpaceError` / `CulledScreenSpaceError` | bool false / double 64.0 | 522 / 548 | Only relevant when frustum/fog culling is OFF — sets the SSE floor for would-be-culled tiles. Leave default. |
| `EnableOcclusionCulling` | bool, true | 582 | Hardware-occlusion culling. **Experimental** — gated behind the project flag `EnableExperimentalOcclusionCullingFeature` (`CesiumRuntimeSettings.h:45`, default false) and `CanEnableOcclusionCulling` (553). For a dense NYC street view it can help perf, but leave OFF unless you've enabled the experimental flag and verified stability. |
| `OcclusionPoolSize` / `DelayRefinementForOcclusion` | int32 500 / bool true | 600 / 618 | Occlusion tuning; irrelevant while occlusion culling is off. |
| `UseLodTransitions` | bool, **false** | 704 | Cross-fades LOD changes (less popping). Nice for cinematic descents — set **true**. NOTE: turning it on **force-disables `EnableFogCulling`** (see 499 EditCondition), so you trade some far-tile culling perf for smoothness. |
| `LodTransitionLength` | float, 0.5 | 717 | Fade duration in seconds when `UseLodTransitions` is on. |

**Recommended street-level photoreal preset:** `MaximumScreenSpaceError=6` (try 4 for hero shots), `MaximumCachedBytes=1073741824`, `ForbidHoles=true`, `PreloadSiblings=true`, `MaximumSimultaneousTileLoads=28`, `EnableFrustumCulling=true`, `EnableFogCulling=true`, occlusion culling OFF. For smooth cinematic descents add `UseLodTransitions=true` (accept losing fog culling).

**Recompute behavior:** `MaximumScreenSpaceError` has a BlueprintSetter `SetMaximumScreenSpaceError` (`Cesium3DTileset.h:1115`) — setting it triggers a re-selection automatically. The other plain `UPROPERTY` flags above (PreloadSiblings, ForbidHoles, MaximumCachedBytes, LoadingDescendantLimit, culling bools) do **not** all auto-recompute when poked from outside the editor's normal PostEditChange path; after a batch of raw property sets, call **`RefreshTileset()`** (`Cesium3DTileset.h:627`, `UFUNCTION(CallInEditor, BlueprintCallable)`) to destroy + recreate the tileset with the new settings. Don't spam it — it reloads everything.

### 16.2 — Fog / atmosphere: killing the blue haze
The distant "blue fog" on Google tiles is almost always one (or both) of: (a) an **ExponentialHeightFog** actor in the level, and (b) the **SkyAtmosphere aerial perspective** — Cesium's own `CesiumSunSky` carries a `SkyAtmosphereComponent` and can double-fog if you also have the default-level one.

1. **ExponentialHeightFog** — this is a stock UE actor, not a Cesium one. To kill the haze either delete the `ExponentialHeightFog` actor from the level, or set its component `FogDensity = 0` (and `VolumetricFog = false`). Programmatically: find the actor via ActorTools, then ObjectTools `set_properties` `{FogDensity: 0.0}` on its `ExponentialHeightFogComponent`.
2. **CesiumSunSky aerial perspective** (`CesiumSunSky.h`): the haze you see at distance from the atmosphere is `AerialPerspectiveViewDistanceScale` (float, default **1.0**, line 344). Lower toward **0.0** to thin/remove distance haze for a clear photoreal look. Related atmosphere knobs that affect haze color/thickness: `RayleighScatteringScale`/`RayleighExponentialDistribution` (default 8.0, line 358) and `MieScatteringScale`/`MieExponentialDistribution` (default 1.2, line 372). For a clean look, `AerialPerspectiveViewDistanceScale` near 0 is the big lever.
3. **Double-atmosphere check:** if you placed `CesiumSunSky` it already owns `DirectionalLight` + `SkyAtmosphere` subcomponents (`CesiumSunSky.h:43,46`). Make sure the default level template's standalone `SkyAtmosphere` and `ExponentialHeightFog` actors are removed so you're not stacking two atmospheres.
4. After changing any `CesiumSunSky` atmosphere property from code, call **`UpdateAtmosphereRadius()`** (line 446) and/or `UpdateSun()` (line 441) — these are the explicit recompute functions (the headers literally say "you must call UpdateSun after changing this value").

### 16.3 — Lighting (NYC daylight)
Use the **`CesiumSunSky`** actor (`CesiumSunSky.h`) over a hand-rolled sun. It physically places the sun from geographic coordinates + time. Key props (all need `UpdateSun()` after a code change — stated in each header comment):

| Property | Default | Line | Use |
|---|---|---|---|
| `SolarTime` | 13.0 | 78 | Hour of day (0–24). 13.0 = 1pm, good high-sun NYC daylight. |
| `TimeZone` | -5.0 | 65 | NYC is **-5** (EST) / -4 (EDT). Or call `EstimateTimeZoneForLongitude(-74.0)` (line 462) to set it from longitude and auto-`UpdateSun()`. |
| `UseDaylightSavingTime` | true | 142 | Leave true for summer NYC. |
| `NorthOffset` | -90.0 | 130 | Aligns north; leave default unless azimuth looks wrong. |
| `UseLevelDirectionalLight` / `LevelDirectionalLight` | false / null | 379 / 385 | Set true + assign a level `DirectionalLight` if you want to drive your own light instead of the built-in one. Default (built-in) is fine. |
| `UseMobileRendering` | (uninit) | 414 | Leave **false** on desktop — mobile path drops the SkyAtmosphere entirely. |

The actor auto-positions itself relative to the `CesiumGeoreference` origin (header note lines 20–25), so set your georeference to NYC (16.5) and the sun is correct for that lat/long. Call `UpdateSun()` once after setting `SolarTime`/`TimeZone`.

### 16.4 — Ray tracing (the "Ray Tracing Geometry memory exceeds budget" warning)
Cesium does **not** require ray tracing. The streamed photoreal tiles generate huge amounts of transient geometry, so RT acceleration structures blow the geometry budget → that warning. Two fixes (cvars set via `EditorAppToolset` console-variable tools, or `DefaultEngine.ini`):

- **Disable RT entirely (recommended for this use case):**
  - `r.RayTracing 0` (master switch; requires editor restart to fully take effect since it gates RT at init — set it in `[/Script/Engine.RendererSettings]` of `DefaultEngine.ini` as `r.RayTracing=False` for a clean boot, or also turn off "Support Hardware Ray Tracing" in Project Settings → Rendering).
  - Belt-and-suspenders, disable the consumers so the geometry BVH stops being built: `r.RayTracing.Shadows 0`, `r.RayTracing.AmbientOcclusion 0`, `r.RayTracing.Reflections 0`, `r.RayTracing.GlobalIllumination 0`, `r.Lumen.HardwareRayTracing 0`.
- **If you must keep RT on, raise the geometry budget** (the cvar named in the warning):
  - `r.RayTracing.Geometry.StreamingMemoryBudgetMB` — raise from the default (~512) to e.g. **2048**.
  - Related: `r.RayTracing.Geometry.MaxBuiltPrimitivesPerFrame` (throttle per-frame BVH builds) and `r.RayTracing.Geometry.CacheCompactedMemoryBudget` (geometry cache budget) — bump if the warning persists.
  - Confirm the exact cvar string from the warning text in the output log; it prints the cvar it's exceeding.

For an NYC photoreal flythrough where you only want raster + good lighting, **turn RT off** — it removes the warning, frees a lot of memory for tile cache, and you lose nothing Cesium needs.

### 16.5 — Programmatic control (NO clicks)
Two layers: (a) UE-Python in the running editor, (b) the MCP toolsets registered here.

**Georeference origin** (`CesiumGeoreference.h`): point the globe at NYC. Properties `OriginLatitude` (162), `OriginLongitude` (181), `OriginHeight` (198) — all have BlueprintSetters (`SetOriginLatitude` 344, `SetOriginLongitude` 358, `SetOriginHeight` 372) that recompute on set. The convenience call is **`SetOriginLongitudeLatitudeHeight(FVector)`** (line 277) — note the argument order is **(longitude, latitude, height)** packed into the FVector x/y/z. For NYC (Times Square area): longitude **-73.9857**, latitude **40.7484**, height ~**20** m. Coordinate conversion helpers (all `BlueprintPure`): `TransformLongitudeLatitudeHeightPositionToUnreal` (468), `TransformUnrealPositionToLongitudeLatitudeHeight` (484), and the ECEF variants (494+) — use these to place a pawn/camera at a real lat/long.

UE-Python class/function names (snake_case mapping of the UFUNCTIONs above):
```python
import unreal
# Georeference
geo = unreal.GameplayStatics.get_all_actors_of_class(unreal.EditorLevelLibrary.get_editor_world(),
        unreal.CesiumGeoreference)[0]
geo.set_origin_longitude_latitude_height(unreal.Vector(-73.9857, 40.7484, 20.0))  # (lon, lat, height)

# Tileset quality
ts = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Cesium3DTileset)[0]
ts.set_maximum_screen_space_error(6.0)      # has a real setter -> auto re-selects
ts.set_editor_property('maximum_cached_bytes', 1073741824)
ts.set_editor_property('forbid_holes', True)
ts.set_editor_property('preload_siblings', True)
ts.set_editor_property('maximum_simultaneous_tile_loads', 28)
ts.refresh_tileset()                         # apply the raw-set props

# Sun / atmosphere
sky = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.CesiumSunSky)[0]
sky.set_editor_property('solar_time', 13.0)
sky.estimate_time_zone_for_longitude(-74.0) # sets TimeZone AND calls UpdateSun
sky.set_editor_property('aerial_perspective_view_distance_scale', 0.0)  # kill haze
sky.update_sun()
sky.update_atmosphere_radius()

# Ray tracing off (cvar)
unreal.SystemLibrary.execute_console_command(world, "r.RayTracing.Shadows 0")
```
**Which recompute on raw set vs need a call:** `MaximumScreenSpaceError`, the three `Origin*` values, and `OriginPlacement` have BlueprintSetters → they recompute when set. Everything else on the tileset (cache, preloads, holes, culling, load limits) is a plain UPROPERTY → set it, then call **`refresh_tileset()`**. `CesiumSunSky` atmosphere/sun props → set, then **`update_sun()`** / **`update_atmosphere_radius()`** (their headers explicitly require it).

**How to EXECUTE UE-Python in the running editor (pick one):**
1. **Editor console**: type `py "<one-liner>"` or `py.exec C:/path/script.py` in the UE console (the Python plugin must be enabled).
2. **Startup script**: drop a `.py` in `Project/Content/Python/init_unreal.py` — runs on editor load.
3. **Remote Control / Python remote-exec** (`ue_py` over the Remote Execution port 6766) for fire-from-outside.
4. **The MCP toolsets registered in this harness** (preferred here — no clicks, no console typing):
   - `EditorToolset.EditorAppToolset` → console-variable tools = set the `r.RayTracing.*` cvars directly.
   - `editor_toolset.toolsets.object.ObjectTools` → `list_properties` then `set_properties` on the Cesium3DTileset / CesiumSunSky / CesiumGeoreference actors. ALWAYS `list_properties` first to get exact property names (they're snake_case), then `set_properties`.
   - `editor_toolset.toolsets.actor.ActorTools` → find/inspect the actors (get the refPath to pass to ObjectTools).
   - `editor_toolset.toolsets.scene.SceneTools` → place the `CesiumSunSky` / `CesiumGeoreference` / `Cesium3DTileset` actors if not yet in the level, and drive the level camera to a vantage.
   - `editor_toolset.toolsets.programmatic.ProgrammaticToolset` → batch the whole set+refresh+update sequence as one sandboxed orchestration script (set tileset props → `refresh_tileset` → set sun → `update_sun`). This is the cleanest "apply the whole preset in one shot" path.
   Note: ObjectTools `set_properties` on plain UPROPERTYs won't trigger the Cesium recompute, so finish a batch by invoking `refresh_tileset` / `update_sun` (callable via the function-invoke path of ObjectTools/ProgrammaticToolset).

## 17. Pixel-perfect path: Gaussian Splatting
SOTA for pixel-for-pixel photoreal real-world scenes in UE5 is **3D Gaussian Splatting (3DGS)**, not photogrammetry mesh. This section is the GS playbook for OUR setup (UE 5.8, M4 Max Mac Studio, Cesium for Unreal v2.27 built from source at `~/coding/cesium-build/cesium-unreal`).

### 17.0 — HEADLINE: our Cesium build already renders Gaussian splats natively
Verified in the source clone, not guessed:
- `Source/CesiumRuntime/Private/CesiumGaussianSplatSubsystem.{h,cpp}`, `CesiumGltfGaussianSplatComponent.{h,cpp}`, `CesiumGaussianSplatDataInterface.{h,cpp}` — a full splat subsystem.
- `Content/GaussianSplatting/GaussianSplatSystem.uasset` + `M_CesiumSplatMaterial.uasset` + `GaussianSplatEffectType.uasset` — rendering is a **Niagara** system (the subsystem `StaticLoadObject`s a `UNiagaraSystem` and spawns it; `CesiumGaussianSplatSubsystem.cpp:11-15,186-207`).
- `Config/Game.ini:2` force-cooks `/CesiumForUnreal/GaussianSplatting` so the Niagara assets ship in packaged builds.
- `CHANGES.md`: **v2.24.0 (2026-03-02)** "Added support for loading tilesets with the `KHR_gaussian_splatting` extension." Later fixes: stop splats accumulating/crashing (v2.25-ish), `GaussianSplatSubsystem::Tick` null-world crash fix (v2.27).
So: **any 3D Tileset whose glTF payload carries `KHR_gaussian_splatting` renders as splats with zero extra plugins.** That is the whole point — GS arrives through the SAME `Cesium3DTileset` actor + tuning from §16, streamed with LOD.

### 17.1 — The GS-in-UE renderer landscape (license · UE ver · how driven · platform)
| Tool | License | UE | Renders via | Imports | Platform | Notes |
|---|---|---|---|---|---|---|
| **Cesium for Unreal (KHR_gaussian_splatting)** ⭐ | Apache-2.0 (FOSS) | our build = 5.8 (uplugin says 5.5, built against 5.8) | **Niagara** + `M_CesiumSplatMaterial` | 3D Tiles tilesets carrying the `KHR_gaussian_splatting` glTF ext (payloads typically **SPZ**-compressed) | wherever our 5.8 build runs (macOS Metal) | **Streamed + hierarchical LOD** — city-scale → sub-cm without loading the whole reconstruction. The only one here that does geospatial LOD streaming. Falls back to sparse point cloud if a renderer can't do 3DGS. |
| **XScene-UEPlugin / XV3DGS** (XVERSE) | **Apache-2.0 (FOSS)** | UE5 (5.1–5.4 era; check release tags for 5.5+) | **Niagara**, hybrid rendering, auto-LOD, editing/management, >200k splats | raw **`.ply`** trained splats (converts on import) | Windows-documented; **no stated macOS support** | Best FOSS option for a single trained `.ply` you own. Same Niagara approach as Cesium. Repos: `github.com/xverse-engine/XScene-UEPlugin`, `github.com/geothinking/XV3DGS-UEPlugin`. |
| **Jawset Postshot UE plugin** | Free download, **proprietary** (Jawset) | **5.4–5.7** | own renderer; Postshot app must be installed even for packaged builds | `.ply` / Postshot scenes | **Windows only, NVIDIA RTX 2060+** | Best-polished *desktop* capture+view, but Windows/NVIDIA — useless on the Mac for runtime, fine as a capture box. |
| **Luma AI UE plugin** | Free, **proprietary** (Luma) | UE5 (marketplace/Fab) | own real-time renderer | `.ply` interactive scenes + `.luma` volumetric | marketplace plugin | "Cleanest production path" for a Luma capture; cloud-trained. Not FOSS, not geospatial/streamed. |
| **Inria 3DGS (reference impl)** | research/non-commercial license | n/a (trainer, not a UE renderer) | — | produces `.ply` | CUDA only | The original trainer; output feeds the plugins above. License is **non-commercial** — don't ship its output commercially; use a permissive trainer (Brush/gsplat) for anything we publish. |

Open standard backing it: **Khronos `KHR_gaussian_splatting`** glTF extension (RC Feb 2026, ratification targeted Q2 2026; contributors incl. Cesium/Bentley, Autodesk, Esri, NVIDIA, Niantic, XGRIDS). **SPZ** is the compressed splat container (~90% smaller than PLY via quantization+gzip; v2 encodes rotations as normalized quaternions to fix antenna/power-line artifacts).

### 17.2 — Why GS beats photogrammetry mesh for close-ups (and its limits)
GS stores millions of view-dependent 3D gaussians (position, anisotropic covariance, opacity, spherical-harmonic color) and alpha-composites them — so it captures **view-dependent specular/reflective detail, thin structures (wires, foliage, railings, glass), and soft edges** that a baked triangle mesh can't. Photogrammetry meshes go **"melty"** up close: fixed topology, fixed albedo texture, no view-dependence, smeared thin features. GS at street level looks like a frozen photograph from any angle.
**Limits (state plainly):** GS is **per-scene capture** (you reconstruct a place you photographed — not a whole city procedurally); **storage-heavy** even with SPZ; **no real collision/material/physics** out of the box (it's a radiance field, not geometry — colliders must be authored separately); editing/relighting is immature; and quality is bounded by capture coverage (gaps where you didn't film).

### 17.3 — Getting NYC as splats
**Existing captures (fastest):** Luma AI exports any capture as **`.ply`** (web gallery → export); Polycam captures GS on iOS/Android, exports `.ply`/`.splat`; both have public galleries with NYC scenes (Times Square, landmarks) — verify per-asset license before reuse. There is **no single canonical "all of Manhattan" street-level splat dataset** publicly; closest research analogs are Block-NeRF (SF), MatrixCity, and BungeeNeRF (city-scale, but NeRF not ready-to-stream 3DGS). Treat existing NYC splats as **hero blocks**, not a city.
**Capture your own block (recommended for a controlled hero shot):** film a slow, overlapping orbit/walk of a block (a few hundred frames or 1–3 min video), then train:
- **Local on the M4 Max (no NVIDIA, no cloud):** **Brush** (Arthur Brussee) — cross-platform GS trainer on **wgpu/Burn**, runs natively on macOS Metal (and in-browser via WebGPU). FOSS, permissive. This is our primary local trainer. Mac-native alternatives: **RadianceKit**, **msplat** (fused Metal compute), **CorbeauSplat** (all-in-one macOS video→splat).
- **Cloud/turnkey:** Luma AI (upload video → `.ply` in minutes). Zero GPU needed.
- **Windows capture box:** Jawset Postshot (RTX 2060+).
COLMAP (or the trainer's built-in SfM) recovers camera poses first; then train to a `.ply`.
**Import path to UE:** trained `.ply` → either (a) **XScene/XV3DGS** plugin directly (Windows), or (b) **convert the `.ply` → SPZ and wrap as a `KHR_gaussian_splatting` 3D Tile**, then load it with the same `Cesium3DTileset` actor we already build — this is the macOS-friendly path that reuses the §16 tuning and gives us LOD streaming for free.

### 17.4 — Hybrid city: Google 3D Tiles backdrop + GS hero blocks (viable in ONE scene)
Yes, in a single UE scene via Cesium: keep the **Google Photorealistic 3D Tiles** tileset as the aerial/skyline backdrop (N2, §16), and add **one or more additional `Cesium3DTileset` actors** pointing at our SPZ/`KHR_gaussian_splatting` hero-block tilesets, georeferenced to the right lat/long via the shared `CesiumGeoreference`. Both stream under the same georeference + LOD system; the splat block "drops into" the photogrammetry city at street level. Use `Cesium Cartographic Polygon` clipping to carve the photogrammetry mesh out where the sharper splat block sits, avoiding z-fight/double-geometry.

### 17.5 — The honest ceiling (say it plainly)
- **Aerial / skyline / mid-distance:** near-photoreal **today** via Google Photorealistic 3D Tiles (N2). Done.
- **Street-level HERO blocks:** genuinely pixel-for-pixel **today** via GS — capture or download a block, train (Brush locally / Luma cloud), stream it through Cesium. A handful of blocks is realistic.
- **Full-city, street-level, pixel-perfect Manhattan:** **not achievable today.** No public city-wide street-level 3DGS dataset exists, and self-capturing all of Manhattan at street level is infeasible (capture + train + storage). The realistic deliverable is **photogrammetry city backdrop + a few GS hero blocks where the camera actually goes.**

### 17.6 — Recommended concrete pipeline for OUR setup
1. **Backdrop:** Google Photorealistic 3D Tiles via Cesium, tuned per §16 (this is N2, already in progress).
2. **Hero block:** pick the block the camera lives in. Either pull a permissively-licensed Luma/Polycam NYC capture, or capture it ourselves and train with **Brush on the M4 Max** (FOSS, Metal, no cloud/NVIDIA).
3. **Package the splat:** `.ply` → **SPZ**, wrap as a `KHR_gaussian_splatting` **3D Tile** (use the open Cesium/3d-tiles tooling).
4. **Load it:** add a second `Cesium3DTileset` actor pointing at that tile, share the `CesiumGeoreference`, position by lat/long; reuse the §16 tuning + `refresh_tileset`. Carve the photogrammetry with a Cartographic Polygon under the block.
5. **Drive it all** with the same MCP toolsets in §16.7 (ObjectTools/ProgrammaticToolset → set props → `refresh_tileset`). Add authored box/landscape colliders separately since splats have no collision.
**Why this is the right call:** it's almost entirely FOSS/local (Cesium Apache-2.0, Brush permissive, no Windows/NVIDIA dependency for the hero block), reuses the streaming + LOD + tuning we already built, and is the only path that puts genuinely pixel-perfect street-level NYC on screen on a Mac today — within the honest ceiling of "hero blocks, not the whole city."

**Sources:** Cesium KHR_gaussian_splatting in CesiumJS + Unreal — https://radiancefields.com/cesium-brings-khr_gaussian_splatting-support-to-cesiumjs-and-unreal-engine ; Cesium hierarchical-LOD for splats — https://radiancefields.com/cesium-adds-hierarchical-lod-for-gaussian-splats-to-3d-tiles-cesiumjs-and-cesium-for-unreal ; Cesium March 2026 release — https://cesium.com/blog/2026/03/03/cesium-releases-in-march-2026/ ; Khronos extension — https://www.khronos.org/news/press/gltf-gaussian-splatting-press-release ; XScene-UEPlugin (Apache-2.0) — https://github.com/xverse-engine/XScene-UEPlugin ; XV3DGS — https://github.com/geothinking/XV3DGS-UEPlugin ; Jawset Postshot UE integration — https://www.jawset.com/docs/d/Postshot+User+Guide/Unreal+Engine+Integration ; Postshot review (Windows/NVIDIA) — https://www.thefuture3d.com/software/postshot/ ; Luma UE plugin — https://www.fab.com/listings/b52460e0-3ace-465e-a378-495a5531e318 and https://lumaai.notion.site/Luma-Unreal-Engine-Plugin-0-41-8005919d93444c008982346185e933a1 ; Luma AI review/export — https://www.thefuture3d.com/software/luma-ai/ ; Brush cross-platform trainer (wgpu/Metal) — https://radiancefields.com/platforms/brush ; RadianceKit/msplat/CorbeauSplat Mac trainers — https://www.radiancekit.de/ , https://github.com/rayanht/msplat , https://github.com/freddewitt/CorbeauSplat ; State of GS 2026 — https://www.thefuture3d.com/blog/state-of-gaussian-splatting-2026/

## 18. Max-fidelity real-NYC data options
**The question:** how do we get the HIGHEST-detail photoreal *real* NYC into UE 5.8 — beyond Google Photorealistic 3D Tiles, whose aerial-photogrammetry geometry goes soft/melty below the roofline (Cesium itself confirms this is a **data limitation, nothing fixable client-side**: https://community.cesium.com/t/how-can-i-achieve-the-best-possible-level-of-detail-for-google-3d-tiles/35678 , https://community.cesium.com/t/how-can-we-improve-the-quality-to-actually-look-photorealistic-using-cesium-for-unreal/36639). This section catalogs everything sharper than Google, ranked at the end. (Complements §16 Google-tile tuning and §17 Gaussian-Splatting hero blocks — those stay the primary FOSS path; this is the "if we want maximum real-NYC fidelity / are willing to pay or capture" menu.)

### 18.1 — Commercial 3D-Tiles / city-mesh providers (sharper than Google, $$$)
Cesium for Unreal streams the open **3D Tiles** standard; any provider shipping native 3D Tiles (or OSGB/OBJ/FBX/I3S that Cesium ion re-tiles, https://cesium.com/learn/3d-tiling/tiler-data-formats/) can feed UE. So "works in UE" is rarely the blocker — coverage / resolution / license / cost are. Every vendor below is **quote-only, no public NYC pricing**.
- ⭐ **Aerometrex** — *sharpest available NYC*: **2 cm** reality mesh of **Manhattan Lower East Side** + **Hudson Yards** (5 cm Brooklyn). Native **Cesium 3D Tiles**, FBX, I3S, OBJ; **official Aerometrex↔Cesium-for-Unreal partnership** (collision/shadows). Downside: clipped neighborhoods, not all 5 boroughs. Free eval is Denver/SF only — NYC is commercial. https://aerometrex.com/models/ , https://aerometrex.com/models/manhattan-les/ , https://cesium.com/blog/2021/04/06/use-aerometrex-reality-mesh-models-in-cesium-for-unreal/
- ⭐ **Vexcel 3D Cities** — *best citywide drop-in*: **all 5 boroughs at ~7.5 cm** photogrammetric mesh, **native 3D Tiles 1.1**, **NYC already demoed running in Cesium for Unreal**. Enterprise (5–6 figures/yr). (Premise correction: the "2 cm Blue Sky Ultra" is a sensor capability, not a buyable NYC product — NYC ≈ 7.5 cm. "Gray Sky" = post-disaster capture, irrelevant.) https://vexceldata.com/countries/united-states/new-york/ , https://cesium.com/blog/2024/06/25/vexcel-cesium/
- **Nearmap 3D** — citywide NYC at **~5.5 cm** ortho, true photogrammetric mesh, delivered **as Cesium 3D Tiles** (+ OBJ/FBX). Enterprise add-on, quote-only. https://www.nearmap.com/coverage , https://www.nearmap.com/blog/cesium-3d-tiles-helping-cities-stream-3d-models
- **Hexagon / Leica HxGN Metro HD** — NYC **explicitly named** in the Metro HD city list; CityMapper-2 LiDAR+oblique mesh ~5–15 cm, streamed via **HxDR / Reality Cloud Studio as OGC 3D Tiles**. Quote-only (cheaper than a fresh flight since data exists). https://leica-geosystems.com/en-us/about-us/news-room/news-overview/2021/09/hxgn-content-program-launches-metro-hd-city-program
- **Bentley iTwin Capture / ContextCapture** (Cesium's parent) — *best pipeline, no ready NYC content*: you supply imagery → reality mesh → **native 3D Tiles → Cesium for Unreal**, resolution = your source (sub-cm possible). DIY-capture only. https://cesium.com/blog/2021/04/29/cesium-supporting-aec-with-contextcapture-and-unreal/
- **EagleView/Pictometry** — sharpest aerial (~2–3 cm) + "EagleView 3D" mesh; **not native 3D Tiles** (re-tile via ion), must confirm they'll license raw mesh. Quote. https://www.eagleview.com/product/pictometry-imagery/
- **Bluesky MetroVista** — no off-the-shelf NYC (Boston only; NYC bespoke), 5 cm, not native 3D Tiles. **Maxar/Vricon Precision3D** — satellite, **~50 cm = COARSER than Google at street level → SKIP** (wide-area context only): https://www.esri.com/partners/maxar-a2T70000000TNOvEAO/precision3d-a2d5x000005kI0FAAU . AccuCities/virtualcitySYSTEMS/CyberCity3D/Blackshark SYNTH3D — London-centric, tooling-only, roof-level, or low-fidelity synthetic; none beat Google for NYC.
- **Street-level / mobile-LiDAR mesh of Manhattan: none sold turnkey.** Cyclomedia ran NYC's official street vehicle (spherical + mobile LiDAR ~10 cm) but sells imagery/measurement subscriptions, not a mesh.

### 18.2 — Geopipe: the best *free-to-prototype* sharper-than-Google NYC (commercial-ish)
⭐ **Geopipe (geopipe.ai)** — **full-city AI-reconstructed NYC** (up to 13 LODs, semantic buildings/roads/vegetation), **streams natively into Cesium for Unreal** + exports FBX/OBJ/glTF/DAE, packaged "Digital Twins for Unreal" on Fab. **Free tier with monthly credits (CC-Attribution, incl. commercial)**; larger/commercial = paid credits, no public price. Caveat: aerial-derived *reconstructed* geometry (not laser-accurate facades), but game-ready and visually beats Google's mush. The fastest $0 path to a sharper-than-Google whole NYC. https://cesium.com/blog/2019/02/28/geopipe-contextsnap-using-3dtiles/ , https://www.geopipe.ai/unreal , https://gamefromscratch.com/entire-city-of-new-york-in-3d-for-free-from-geopipe/

### 18.3 — DIY photogrammetry (RealityScan / Metashape / splats) — a hero block
- **RealityScan 2.x** (Epic; *was* RealityCapture, renamed June 2025) — **FREE under $1M/yr revenue** (we qualify); $1,250/seat/yr above. Drone+ground photos → align → mesh → texture → OBJ/FBX/glTF/USD → straight into UE (Epic's own tool, clean import). Ground-level capture genuinely beats Google at street level. https://www.realityscan.com/license , https://rshelp.capturingreality.com/en-US/tools/export.htm
  - ⚠️ **Mac blocker:** RealityScan is **Windows-only + requires an NVIDIA CUDA GPU to mesh**. Does NOT run on the M4 Max. → need a Windows/RTX box or cloud GPU (Vagon/Paperspace/AWS). https://dev.epicgames.com/community/learning/knowledge-base/DB58/realityscan-hardware-and-operating-system-requirements
  - **Only native-Mac serious option = Agisoft Metashape** ($179 Std / $3,499 Pro, perpetual; runs on Apple Silicon). Slower, excellent quality. https://www.agisoft.com/buy/online-store/
  - **RealityScan Mobile** (free iPhone app) is photogrammetry (NOT LiDAR), good for props, impractical for a whole block.
- **Gaussian splats** are the more photoreal DIY deliverable at captured viewpoints — but that's already the §17 path (Brush local on M4 Max / Luma cloud → SPZ → Cesium tile). Splats = no collision/geometry/Lumen; **mesh = drivable/walkable**. For the GTA-style drivable goal you ultimately need the **mesh** and use splats for cinematics.
- 🚫 **Drone law is the real blocker, not software:** launching/landing any drone in NYC needs an **NYPD permit** (misdemeanor without, NYC Admin §10-126(c)); most of Manhattan is **Class B / 0-ft FAA grids = no LAANC approval**. Assume **drones are off the table** → **capture ground-only** (sidewalk, pole/monopod, multiple passes/heights). https://rules.cityofnewyork.us/rule/applications-to-launch-or-land-an-unmanned-aircraft-including-a-drone/ , https://drone-laws.com/drone-laws-in-nyc/

### 18.4 — Open-data LiDAR + ortho → reconstructed LOD2 city (FOSS, accurate massing + roofs)
Open NYC data gives an **accurate-massing, roof-textured, terrain-correct** city — but **NOT pixel-perfect**, because every open NYC aerial source is **nadir (sees roofs/tops, zero facade)**. The single biggest limiting factor is **facade texture**.
- **LiDAR point cloud (not just the DEM):** 2017 NYC Topobathymetric LiDAR, **~10 pts/m²** (dense enough for LOD2 roof shapes, same class as the Dutch 3D BAG; not enough for chimneys/HVAC). Still the newest full-borough collection. Public domain. ⚠️ the cloud does **NOT classify buildings** — you drive reconstruction with the footprints (heightroof/groundelev we already have). NOAA S3 COPC LAZ: https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/laz/geoid18/9306/index.html ; NY clearinghouse: https://gisdata.ny.gov/elevation/LIDAR/NYC_TopoBathymetric2017/ ; spec/density PDF: https://gis.ny.gov/system/files/documents/2023/04/new_york_city_2017_topobathymetric_lidar_report_final.pdf
- **Orthoimagery:** NYC OTI/DoITT **6-inch (0.5 ft) TRUE ortho** (lean removed → roof pixels register over footprints), biennial, CC BY 4.0 — drape on terrain + slice roof-top textures. https://gis.ny.gov/new-york-city-orthoimagery-downloads
- **LOD2 reconstruction (feasible for NYC):** ⭐ **roofer** (production engine behind 3D BAG; footprint + cloud → LoD1.2/1.3/**2.2** CityJSON), https://github.com/3DBAG/roofer ; **3dfier** = LOD1 flat-top only. NYC has both inputs at ~1/10 the proven NL scale; biggest risk = footprint↔cloud **CRS alignment** (NYC is feet/EPSG:2263 vs roofer's metric default). → **tyler / pg2b3dm** to 3D Tiles/glTF for UE. https://github.com/3DGI/tyler , https://github.com/Geodan/pg2b3dm
- **Official NYC 3-D Building Model:** whole-city LOD1.5 + ~100 LOD2 landmarks, **2014/2016 vintage, no textures** (post-2014 supertalls missing) → prefer fresh reconstruction. https://data.cityofnewyork.us/City-Government/3-D-Building-Model/tnru-abg2
- **THE FACADE CRUX (limit of open-data "pixel-perfect"):** nadir data = no building sides. Options: **procedural facades** (Blender Building Tools / Buildify from building:levels — *legally clean, generic-not-real*); **Mapillary/KartaView street imagery** (CC BY-SA — *legal to derive real facades but viral share-alike infects your output*); **Google Street View = PROHIBITED** (TOS bans 3D/texture derivation); oblique aerial that sees facades = all commercial (§18.1). OSM material tags ~0.3% = useless. **Realistic open-data facade ceiling = "believable generic NYC," not a recognizable per-building twin.**

### 18.5 — Epic City Sample + Megascans (AAA-photoreal but FICTIONAL NYC) + tile-sharpening verdict
- **City Sample** (the Matrix Awakens city) — free on Fab, **UE-only EULA**, modular skyscraper kit + vehicles + Mass-AI crowds/traffic. **Not real NYC** — NYC-flavored fictional. Best use: **kit-bash a hero Manhattan-feel block** at close range while Google tiles fill the skyline. ⚠️ the *procedural* building generator runs in **SideFX Houdini** (HDAs → point cloud → UE "Rule Processor" instancing), not one-click in-editor; the pre-built maps + kit are usable without Houdini. https://www.fab.com/listings/4898e707-7855-404b-af0e-a505ee690e68 , https://dev.epicgames.com/documentation/unreal-engine/city-sample-project-unreal-engine-demonstration
- **Megascans — the free era is OVER (Jan 1 2025).** Library now **priced per-asset**; a permanent **~1,500-asset free starter set** remains (https://www.unrealengine.com/fabfreecontent). Still the AAA real-scanned PBR reference for ground-floor grime/brick/concrete/glass on hero buildings; pull via the in-editor Fab/Bridge browser. https://www.cgchannel.com/2024/10/epic-games-has-made-megascans-free-to-all-but-only-until-the-end-of-2024/
- **Sharpening Google tiles — honest verdict: dead end past midground.** The detail isn't in the dataset (Cesium, twice, above). In-UE detail textures / detail normals / decals (windows, grime, signage) / POM add *plausible* — not real — close-range bite, and are best applied to **hero meshes you rebuild**, not the streamed tiles (whose textures are awkward to extract). AI upscalers (Real-ESRGAN/4x-UltraSharp, SD-tile *hallucinates*, Topaz) + normal-gen (Materialize/ArmorLab/DeepBump) shine **after** you've replaced a building, not as a live tile filter. **TSR/DLSS** = clean 4K upsampling/stability, **not** detail synthesis; **Nanite displacement** only helps geometry you own. → **The only real close-range fix is replacing hero buildings** (City Sample kit + Megascans + decals + Nanite displacement) over a Google-tile backdrop.

### 18.6 — HONEST VERDICT & RANKING (real-NYC accuracy × visual fidelity × effort/cost/openness)
- **Already-best FOSS path stands (§16+§17):** **Google Photorealistic 3D Tiles backdrop + self-captured Gaussian-splat hero blocks (Brush on M4 Max → SPZ → Cesium)** — the only way to put genuinely pixel-perfect street-level *real* NYC on screen on a Mac today, near-free, no Windows/NVIDIA. Ceiling: **hero blocks, not the whole city** (no public city-wide street-level dataset exists).
- **Sharper than Google with the LEAST effort (free):** ⭐ **Geopipe** — whole-city, sharper-than-Google, streams into Cesium for Unreal, free credits to prototype. The single best "try this first" upgrade.
- **Sharpest possible real NYC, if budget exists:** ⭐ **Aerometrex 2 cm** (Lower Manhattan / Hudson Yards) or ⭐ **Vexcel 7.5 cm** (all 5 boroughs) as native 3D Tiles — both confirmed in Cesium for Unreal. Enterprise quote.
- **Most accurate FOSS *geometry*:** **roofer LOD2 reconstruction** from 2017 LiDAR + footprints + 6-inch ortho roofs — accurate massing/roofs/terrain, but **facades only procedural/generic** (the open-data ceiling).
- **DIY film-quality block:** **RealityScan** (free, ground-only capture — drones are illegal in Manhattan) needs a **Windows/RTX box or cloud GPU**; **Metashape** is the Mac-native alternative. For drivability you need the **mesh**; for pure beauty shots a **splat** wins.
- **AAA-but-fictional fallback:** **City Sample kit + Megascans** hero block over a tile backdrop — fastest route to a sharp close-up, but not literally real NYC.
- **Don't bother:** sharpening Google tiles in-place (data-limited), Maxar/Vricon (50 cm, coarser than Google), Megascans-as-free (now paid).

---

## 17b. Splat tooling — INSTALLED + verified (the §17.6 pipeline, ready to run)

The §17 playbook is now backed by a working local toolchain at
`~/coding/unreal-agent-harness/splat/` (full docs: `splat/README.md`). All FOSS,
Apple-Silicon-native, no NVIDIA/cloud. Verified against the *actual* Cesium build
source (not blog posts).

### What's installed
| Tool | Path | License | Role |
|------|------|---------|------|
| Niantic **spz** CLI+lib | `~/coding/spz` (built → `build/{ply_to_spz,spz_to_ply,spz_info}`) | MIT | `.ply`⇄`.spz` (~10x); verified round-trip 932k-pt sample: 231MB PLY → 24MB SPZ. |
| **make_splat_tile.py** | `~/coding/unreal-agent-harness/splat/make_splat_tile.py` | ours | `.ply`/`.spz` → loadable `KHR_gaussian_splatting` 3D Tile (`model.glb`+`tileset.json`). Pure stdlib. Tested both inputs. |
| **Brush** trainer | `~/coding/brush` (built → `target/release/brush-cli`, 123MB) | Apache-2.0 | Local Metal/wgpu splat trainer — phone video → `.ply`, no cloud. `--help` verified. |

### The tile shape (verified facts, save re-deriving)
Our v2.27 reader (`cesium-native/CesiumGltfReader/src/decodeSpz.cpp`) decodes an
**SPZ-compressed** primitive at load via `spz::loadSpz()`. So `make_splat_tile.py`
embeds the raw `.spz` as a bufferView and the tile is one small self-contained glb.
Non-obvious requirements it satisfies:
- Primitive **mode = POINTS (0)** or `loadGaussianSplats()` skips it.
- The SPZ sub-ext is **nested inside** `KHR_gaussian_splatting`
  (`registerReaderExtensions.cpp:150-151` registers it as a child), at
  `…extensions.KHR_gaussian_splatting.extensions.KHR_gaussian_splatting_compression_spz_2.bufferView`.
- The decoder **overwrites but never creates** accessors, so the glb must already
  carry placeholder accessors (count = numPoints, from `spz_info`) for
  `POSITION`, `KHR_gaussian_splatting:SCALE`/`:ROTATION`, `COLOR_0`, and the
  per-degree SH coefs. Cesium reads `shDegree` off the highest SH coef present.
- Both ext names must be in model `extensionsUsed` (`hasSpzExtension` gates on it).

### Run it
```bash
python3 ~/coding/unreal-agent-harness/splat/make_splat_tile.py IN.ply OUT/dir --name block
# → OUT/dir/{model.glb, tileset.json}; load via a 2nd Cesium3DTileset (Source=From Url,
#   file://…/tileset.json), share the CesiumGeoreference, carve with a Cartographic
#   Polygon (§17.4), tune + refresh_tileset (§16).
```

### Part A status — no permissive NYC splat exists (capture is the gate)
Exhaustive search (Sketchfab, Polycam, Luma, HuggingFace, academic) found **no
clearly-licensed downloadable NYC street splat**. Big urban datasets (MatrixCity,
UrbanScene3D, INRIA benchmark splats) are **non-commercial/research-only**.
Closest *permissive* options: **Polycam Explore** CC-BY captures (only source
serving native `.ply`), Ricardo Garnica's CC-BY plazas on Sketchfab (GLB
point-cloud only). **A real NYC hero block = Pat captures a ~1-2 min phone video
→ COLMAP → `brush-cli` → `.ply` → `make_splat_tile.py`.** Tooling is ready now.

## 19. Loop corrections (Jun 19, verified)
- **Geopipe = DEAD — do NOT pursue.** geopipe-verify confirmed: Fab listing has no download (just links to marketing); the documented public demo tileset (`cs.geopi.pe/...`) TCP-times-out (server offline); docs.geopipe.ai cert broken; app/api hosts dead; no self-serve free account anymore. Abandoned product. (§18.2 "try first" is now wrong.)
- **Real free whole-NYC route stays: Cesium + Google Photorealistic 3D Tiles** (our working setup) or Cesium OSM Buildings (free ion token). That's it for free whole-city.
- **Splat tooling READY (FOSS, Apple-Silicon, $0):** Niantic `spz` built at `~/coding/spz/build/`; `~/coding/unreal-agent-harness/splat/make_splat_tile.py` (.ply/.spz → KHR_gaussian_splatting tile, tested); **Brush** trainer built at `~/coding/brush/target/release/brush-cli`. Tile format reqs (from Cesium source): primitive mode POINTS(0), SPZ sub-ext nested in KHR_gaussian_splatting, placeholder accessors for POSITION/SCALE/ROTATION/COLOR_0/SH must pre-exist, both ext names in extensionsUsed.
- **No permissive NYC splat exists** (Sketchfab/Polycam/Luma/academic all NC or not-native). Real hero block needs a capture (Pat won't) OR splat-auto's existing-CC-video path (feasibility TBD — monocular video = hard for GS). Pipeline is ready the moment any `.ply` exists.
- Still running: roofer-build (FOSS LOD2 massing), splat-auto (splat-from-existing-video). Editor track gated on Pat dismissing the relaunch "restore?" dialog.

## 20. UE Python remote-exec — call live UE/Cesium FUNCTIONS (Jun 18)
- **The fix for the Cesium-stuck-at-ECEF blocker.** MCP property-set writes raw UPROPERTYs and **skips the Cesium BlueprintSetters**, so tiles never rebase. The rebase only fires through real function calls — `CesiumGeoreference.set_origin_longitude_latitude_height(unreal.Vector(lon,lat,height))` + `Cesium3DTileset.refresh_tileset()`. Remote-exec runs arbitrary Python *inside* the running editor, so we can call them.
- **Enabled in** `~/Documents/Unreal Projects/MyProject/Config/DefaultEngine.ini` → `[/Script/PythonScriptPlugin.PythonScriptPluginSettings]` `bRemoteExecution=True` (+ multicast group `239.0.0.1:6766`, bind `0.0.0.0`, ttl 0, 2MB buffers). Names verified vs UE 5.8 `PythonScriptPluginSettings.h/.cpp`. **Needs ONE editor restart** (setting read at startup).
- **Harness:** `~/coding/unreal-agent-harness/ue_remote/` — `remote_execution.py` (UE's official client, copied verbatim), `ue_exec.py` (CLI: discover→connect→run, exit 0/2/3), `cesium_rebase.py` (rebases all georefs+tilesets; LON/LAT/HEIGHT env, defaults to NYC Times Square; also forces OriginPlacement=CartographicOrigin), `README.md`.
- **Workflow (no clicks):** launch editor → `cd ~/coding/unreal-agent-harness/ue_remote && python3 ue_exec.py "<python>"` or `python3 ue_exec.py --file cesium_rebase.py`. Verified standalone: client loads, syntax clean, discovery exits 2 cleanly with editor closed. Live connection test pending first editor launch.
- **Gotcha:** `SetOriginLongitudeLatitudeHeight` takes a single **FVector(X=lon, Y=lat, Z=height)**, NOT three floats (verified in `CesiumGeoreference.h:277`). Rebase only valid when OriginPlacement==CartographicOrigin (default, but the script sets it anyway).
