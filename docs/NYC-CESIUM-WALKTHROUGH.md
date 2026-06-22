# NYC (Real City) — Cesium Walkthrough, start to finish

> Demo 1: stream the **actual** New York City into Unreal (photoreal Google 3D Tiles) and fly
> through it. The audience-facing step-by-step. Companion reference: [`cesium-for-unreal.md`](cesium-for-unreal.md)
> (the actor/property/function reference) and [`cesium-rebase-solution.md`](cesium-rebase-solution.md)
> (why the origin rebase works). Connect the MCP first: [`UNREAL-MCP-ENABLE.md`](UNREAL-MCP-ENABLE.md).

## What you'll build
A georeferenced photoreal Manhattan you can fly around — no modeling, it's real-world data streamed live. Same trick works for any city: just change the coordinates.

## Prerequisites
> **Plugin + Google API key setup (the 2 one-time human steps) → [CESIUM-SETUP.md](CESIUM-SETUP.md). Do that first.** Quick recap below.
- **Cesium for Unreal** plugin — one-click free install from **Fab** (Edit → Plugins → enable → restart; UI lives under Window → Cesium). *(On a UE version too new for a Fab release — like our UE 5.8 — you build it from source; see the CESIUM-SETUP footnote. Most people just install from Fab.)*
- **A Google Photorealistic 3D Tiles key** — Google Maps Platform API key with the **Map Tiles API** enabled.
  - ⚠️ Cesium ion's old free Google P3DT asset (id `2275207`) is **no longer free** — don't rely on it. Use the **direct Google key URL** instead:
    `https://tile.googleapis.com/v1/3dtiles/root.json?key=YOUR_KEY`
  - (Cesium World Terrain / Bing imagery via a free **Cesium ion** token also works for a non-Google look.)
- Ray tracing **OFF** for stability/perf on Mac (`r.RayTracing=0`).

## The actor set (what a georeferenced scene needs)
1. **CesiumGeoreference** — defines where on Earth the Unreal origin maps to (your NYC lat/lon).
2. **Cesium3DTileset** — the streamed geometry (Google P3DT), linked to the georeference.
3. **CesiumSunSky** (or a Directional Light + Sky) — lighting.
4. **A flying pawn** — Cesium's `DynamicPawn` / a `GlobeAwareDefaultPawn` (handles origin-shift while you fly).

## Steps

### 1. Add the CesiumGeoreference + set NYC as the origin
Place a `CesiumGeoreference` actor. Set its origin to Manhattan (Empire State area):
- `OriginLatitude = 40.7484`
- `OriginLongitude = -73.9857`
- `OriginHeight = 0` (ground-ish; tune up/down so you sit at street level vs roof level)

> **Why this is the rebase.** Setting `OriginLatitude/Longitude/Height` through the editor property
> system (`ObjectTools.set_properties`) fires `PostEditChangeProperty → SetOrigin* →
> UpdateGeoreference → OnGeoreferenceUpdated.Broadcast()`, and the linked tileset's root
> auto-recomputes ECEF→Unreal and moves the tiles to the world origin. **No `RefreshTileset()`,
> no UFUNCTION call needed.** See [`cesium-rebase-solution.md`](cesium-rebase-solution.md).

### 2. Add the Cesium3DTileset (Google P3DT) and LINK it to the georeference
- Add a `Cesium3DTileset` actor.
- **Set its `Georeference` to the CesiumGeoreference from step 1 *first*** (linking before setting the origin is what made it work — our early failures were ordering, not capability).
- Source: **From Url**, Url = `https://tile.googleapis.com/v1/3dtiles/root.json?key=YOUR_KEY`.
- LOD/quality: `MaximumScreenSpaceError` ~ **8** is a good speed↔sharpness dial (higher = faster/blurrier; lower = sharper/heavier). Cache ~2 GB.

### 3. Render check
In the plain editor the tiles may sit at ECEF until the rebase settles; **StartPIE in Simulate** fires `BeginPlay` → the rebase, and Manhattan snaps to the origin. (Or just confirm the georeference link + origin are set — the broadcast moves them.)

### 4. Lighting
Add **CesiumSunSky** (gives real sun position for the lat/lon/time) — or a Directional Light + SkyAtmosphere + SkyLight if you want manual control. Keep exposure sane (auto-exposure or a Manual PostProcessVolume; don't over-bias).

### 5. Fly it
Add Cesium's **`DynamicPawn`** (or a `GlobeAwareDefaultPawn`), set `AutoPossessPlayer = Player0`, place it above the city. Press Play → fly with WASD + mouse. (For a chase aircraft over the city, see [`plane-chase-pawn.md`](plane-chase-pawn.md).)

## Gotchas (the ones that actually bit us)
- **Recurring tick crash** in `UCesiumGaussianSplatSubsystem::Tick` (every tick, `UObjectArray.h`). No cvar disables it → patch `GetTickableTickType()`→`Never` + rebuild the CesiumRuntime dylib. See [`cesium-splat-subsystem-disable.md`](cesium-splat-subsystem-disable.md).
- **Tiles render 6,000 km away (at ECEF).** The georeference link/order — link the tileset to the georeference, *then* set the origin. Step 2 above.
- **Google ion asset 2275207 = 404 / not free.** Use the direct Google key URL.
- **Ray tracing on = instability/slowness on Mac.** `r.RayTracing=0` (DefaultEngine `[SystemSettings] r.RayTracing=False`).
- **A landscape can bury the city.** If your level has an OpenWorld landscape, remove those tiles or the city sits under them.

## MCP-driven version (what the agent runs)
1. `SceneTools.add_to_scene_from_class` → `CesiumGeoreference`, `Cesium3DTileset`, `CesiumSunSky`, pawn.
2. `ObjectTools.set_properties` on the tileset → set `Georeference` (link) + `TilesetSource`/`Url`.
3. `ObjectTools.set_properties` on the georeference → `OriginLatitude/Longitude/Height` (this rebases).
4. `EditorAppToolset.StartPIE` (Simulate) to fire the BeginPlay rebase; QA with `ue_qa.py decode`.
5. For finer control there are Python remote-exec helpers in [`../ue_remote/`](../ue_remote/) (`cesium_rebase.py`).

## Reuse for any city
Change `OriginLatitude/Longitude` to anywhere on Earth (Dubai, Tokyo, SF…) — the Google P3DT covers most of the globe. Everything else stays the same.
