# Environments Library — what we built + how (the worlds)

> One page tying together every environment + the method behind them. Detailed recipes are in the linked docs. This is the "what can this thing make, and how" overview for the video + the audience.

## The core method (how we make ANY environment)
Three reusable building blocks, combined per environment:
1. **City Sample (free, Epic login)** = the photoreal *base world* — the actual Matrix Awakens city. Open `Small_City_LVL` and it's a photoreal metropolis, **playable out of the box** (the shipped `BP_CitySamplePlayerCharacter` — press Play, WASD walk, C drive). See [CITY-SAMPLE-PLAYABLE.md](CITY-SAMPLE-PLAYABLE.md).
2. **PCG grammar building generator** (`/PCG/SampleContent/Grammar/PCG_BuildingSample`) = assembles full closed buildings from modular facade pieces, and we scale it across a grid into a city (downtown core via per-block height). See [PCG-GUIDE.md](PCG-GUIDE.md).
3. **Custom facade kits, generated in Blender** = the *architectural style*. City Sample ships only one generic kit, so we Blender-generate facade modules (wall/window/corner/roof) in any style, built to the generator's exact module spec, and feed them in. This is how we get futuristic / Paris / Art-Deco without buying themed packs.

**The module spec every kit must match** (or the generator assembles broken): width **400 cm along local +X, CENTERED** (X −200..+200); depth shallow on Y; height on Z, **base-pivoted (min.z = 0)**; consistent 400 cm width + ~400 cm floor height. Builder template: `futuristic_kit_jobs.py`. (This is the fix the City Sample CH-kit lacked — its panels' width was on Y, so it assembled jagged.)

**Parallelize prep, serialize the editor:** asset prep (Blender kits, downloads, research) runs across many agents at once; the editor assembly is ONE environment at a time (single editor / one game thread — concurrent edits freeze it).

**Making it look REAL (not bland CG):** the assembly above gets you the *shapes*; realism (variety + PBR/normal-mapped surfaces + decals + ornament + street life) is its own pass — see **[REALISM-GUIDE.md](REALISM-GUIDE.md)** (style-agnostic, worked through the Paris block).

## The worlds
| World | Status | Level | How it's built |
|---|---|---|---|
| 🌆 **Futuristic glass city** | ✅ built + saved | `/Game/Map/Small_City_LVL` (glass district in the City Sample city) | City Sample base + 22 PCG glass towers (futuristic kit) + de-fog. [PCG-GUIDE](PCG-GUIDE.md) |
| 🚗 **Car showcase** | 🚧 building | (separate level — `car-showcase` agent) | City Sample's ~13 drivable cars lined up; walk + C to drive |
| 🏛️ **Beaux-Arts / Paris** | ✅ built + saved | `/Game/Map/Paris_LVL` | Paris facade kit → `PCG_Building_Paris` grammar → 49 uniform Haussmann mid-rise blocks on a wide-boulevard grid. [PCG-GUIDE](PCG-GUIDE.md) |
| 🏛️ **Paris BLOCK (realism upgrade)** | ✅ built + saved | `/Game/Map/ParisBlock_LVL` | ONE tree-lined boulevard, 10 Haussmann buildings (2 rows of 5) — the realism template. Every building unique: per-building grammar graph rolls a different wall/window/corner from the **12 beaux_arts VARIANTS** + a different stone-tone MI (5 tones) + varied height (5-7 storeys) & width (per-actor X-scale). Mansard roofs via separate-actor row of `mod_mansard` (dark zinc) + roof-cap planes to hide hollow tops. Street life: road+sidewalks, 20 trees (City Sample maple kits), 5 parked cars, 12 lamps, 6 benches. Playable (PlayerStart on sidewalk). [PCG-GUIDE](PCG-GUIDE.md) |
| 🏙️ **Art-Deco city** | ✅ built + saved | `/Game/Map/ArtDeco_LVL` | Art-Deco facade kit → `PCG_Building_ArtDeco` grammar → 49 towers, RADIAL downtown core (4 height tiers 40/80/120/160m, tallest center) + 9 ziggurat-crown actors on the core. [PCG-GUIDE](PCG-GUIDE.md) |
| 🏙️ **DecoCity (deco landmarks in the photoreal city)** | ✅ built + saved | `/Game/Small_City_LVL_artdecolevel` | A SEPARATE copy of the City Sample photoreal `Small_City` with the **Chrysler hero** (`/Game/Chrysler/SM_ChryslerHero`, silver sunburst-arch chrome crown) downtown at **(38000,-1500,150)** + a ring of **9 warm Art-Deco wedding-cake towers** (3 narrowing tiers of carved `ArtDecoDetailed` wall/window panels + ziggurat/spire/fluted crowns, Honey/PaleGold/Terracotta tints + `MI_Bronze_DecoGold`) grounded on the streets within ~11000cm of the Chrysler, popping warm against the grey city. **CLEAR BLUE SKY:** hid the City Sample grey `SM_dome`/`M_sky` backdrop (`StaticMeshComponent0.bVisible=false`) + added a `SkyAtmosphere` (the DirectionalLight is already its atmosphere sun) + SkyLight → RealTimeCapture + raised sun to pitch −35 / 2800 lux / 5500K + near-zero fog. MotionBlur 0. PlayerStart near the deco district at (35500,1500). Captures: `docs/decocity_final_{aerial,streeteye,crown}.png`. |
| 🏙️ **Art-Deco BLOCK (realism upgrade)** | ✅ built + saved | `/Game/Map/ArtDecoBlock_LVL` | The Chrysler-era realism template: 8 WEDDING-CAKE SETBACK towers (3 stacked narrowing grammar tiers each) + dramatic bronze CROWNS (ziggurat/spire/fluted), built from the **DETAILED carved 2-slot kit** (`assets/art_deco_kit/detailed/`, 14 modules) so **gleaming BRONZE ornament (slot 1, Metallic 1.0 + warm emissive) reads vs matte normal-mapped limestone** — the contrast `ArtDeco_LVL` v1 lacked. Per-building tone (4 MIs) + height/width/module-mix variety; verdigris/soot/crack decals; road+sidewalks+lamps+cars; playable. Relocated to empty terrain (250000,250000) to escape the City Sample backdrop. [PCG-GUIDE](PCG-GUIDE.md) |
| 🚀 **Sci-fi station interior** | plan ✅, assembly queued | (separate level, TBD) | download CC0 kit → assemble walkable interior |
| 🗽 **Real NYC (Cesium)** | documented | (Cesium scene) | Google Photorealistic 3D Tiles. [NYC-CESIUM-WALKTHROUGH](NYC-CESIUM-WALKTHROUGH.md) |
| ✈️ **Chase plane over a city** | documented | — | imported plane + chase cam. [plane-chase-pawn](plane-chase-pawn.md) |

## The building kits (generated, reusable)
All in `assets/<kit>/` with FBXs + a `_montage.png` + `NOTES.md` (grammar-symbol→mesh mapping + dims):
- **`assets/futuristic_kit/`** — sleek glass curtain-wall (wall/window/corner/column/ground). Used in the glass city.
- **`assets/beaux_arts_kit/`** — Haussmann Paris: arched French windows + balconies, rusticated limestone, mansard roof (wall/window/corner/ground/mansard).
- **`assets/art_deco_kit/`** — 1920s Art-Deco: vertical fluted piers, geometric spandrels, stepped ziggurat crown (wall/window/corner/ground/crown).
- **`assets/art_deco_kit/detailed/`** — the CARVED 2-slot upgrade (14 modules: 4 walls / 4 windows / 2 corners / 3 crowns / lobby): deep beveled relief + **bronze ornament on slot 1** (chevrons/grilles/sunbursts/fins/crowns) for true stone-vs-metal contrast. Builder `art_deco_detailed_jobs.py`. Used in the Art-Deco BLOCK. ⚠️ Don't `me.materials.clear()` in the builder — it zeroes the bronze face indices (see PCG-GUIDE).
- (Plus the generated **towers** in `assets/futuristic_city/towers/` — whole-building meshes.)

## Sci-fi interior — the asset path (free, no login)
Full research: [scifi-interior-plan.md](scifi-interior-plan.md). TL;DR: grab the **Quaternius _Modular Sci-Fi MEGAKIT_** — **CC0, free, no login**, genuinely modular interior (corridors/rooms/doors/floors/walls/ceilings), FBX/OBJ/glTF. Download: https://quaternius.com/packs/modularscifimegakit.html (or itch). Then import + snap a small interior + emissive lighting + the City Sample player walks it. (⚠️ The flashy Fab "Modular SciFi Station" was free-of-the-month only until 2026-06-16 — now paid; only free if claimed before then.)

## Key findings index (the hard-won stuff)
- **The demo's photoreal city = City Sample** (its assets), via a prepared `Assign_CitySampleBuildings` subgraph that ISN'T in the public install — so for *futuristic* we generate kits + use the grammar generator; for *realistic photoreal* just open Small_City. (`demo/UE-DEMO-PROMPTS.md`)
- **MCP enable is per-project** + the official method (console `ModelContextProtocol.StartServer`, Editor-Prefs auto-start, port 8123). [UNREAL-MCP-ENABLE](UNREAL-MCP-ENABLE.md)
- **Playable character is verified** (City Sample ships it; press Play, WASD/C). PIE input needs a click in the viewport for focus; first Play = magenta while shaders compile. [CITY-SAMPLE-PLAYABLE](CITY-SAMPLE-PLAYABLE.md)
- **Mac perf / "crazy fast, can't move" = low FPS + motion blur** → MotionBlurAmount 0 + ScreenPercentage 50 on a PostProcessVolume + Scalability Low. [TROUBLESHOOTING](TROUBLESHOOTING.md)
- **Lighting:** Small_City's overcast = near-horizon sun + heavy ExponentialHeightFog (no SkyAtmosphere/clouds actor); reduce fog + raise sun. Adding fog/low-sun white-outs it. [CITY-SAMPLE-PLAYABLE](CITY-SAMPLE-PLAYABLE.md)
- **PCG city pipeline + every gotcha** (grammar gen, per-district color via PerInstanceCustomData, height-via-graph-default, the $Scale.Z write-back that zeroes spawns, trace-cells-skip-rooftops). [PCG-GUIDE](PCG-GUIDE.md)
- Cesium real-city (rebase, splat-crash), chase plane (scale/owner-no-see), the QA capture loop — see the [docs index](README.md).
