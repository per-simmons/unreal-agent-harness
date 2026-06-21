# Gaussian-Splat → Cesium-for-Unreal tooling (§17b)

Local, FOSS, Apple-Silicon-native pipeline to take ANY Gaussian splat (captured
or downloaded) and load it as a streamed hero block in our **Cesium for Unreal
v2.27** build (UE 5.8, built at `~/coding/cesium-build/cesium-unreal`).

Our Cesium build renders the **`KHR_gaussian_splatting`** glTF extension
natively via Niagara — see the main guide §17.0. This directory is the
"get a splat INTO that path" half.

---

## TL;DR — make a loadable tileset from a splat

```bash
# from a 3DGS .ply  (if you have an .spz: spz_to_ply it first — see note)
python3 ~/coding/unreal-agent-harness/splat/make_splat_tile.py \
    INPUT.ply  ~/coding/unreal-agent-harness/splat/out/myblock  --name myblock

# emits:
#   out/myblock/model.glb     (UNCOMPRESSED, self-validating — crash-proof)
#   out/myblock/tileset.json  (3D Tiles 1.1, points at model.glb)

# .spz input? convert to .ply first:
~/coding/spz/build/spz_to_ply INPUT.spz /tmp/in.ply
python3 ~/coding/unreal-agent-harness/splat/make_splat_tile.py /tmp/in.ply out/myblock --name myblock
```

> **The generator was rewritten (Jun 2026) after a hard Metal RHI crash.** The
> old SPZ-embedded version wrote placeholder accessors pointing at a 32-byte stub
> bufferView and trusted Cesium's `decodeSpz.cpp` to rebind them at load. When
> the rebind didn't land, `POSITION` failed Cesium's bound check
> (`AccessorViewStatus::BufferViewTooSmall`, **status 4**) and the editor
> SIGSEGV'd in `FMetalDynamicRHI::RHILockBuffer` via
> `UCesiumGaussianSplatDataInterface::PerInstanceTick`. The current generator
> emits **real, uncompressed accessors** sized exactly `stride*count` for every
> attribute — no SPZ, no decode dependency, valid by construction — and
> self-validates before writing. The runtime splat component reads the
> attributes identically either way (verified in
> `CesiumGltfGaussianSplatComponent.cpp`). Trade-off: bigger `.glb`. The old
> generator is preserved at `make_splat_tile.py.bak-spz`; the broken tile at
> `../assets/splat_hero/tile_spz_broken/`. See the `unreal-stability-gotchas`
> skill for the full story.

Then in UE: add a **second `Cesium3DTileset`** actor, set its source to
`file:///…/out/myblock/tileset.json` (or an HTTP URL), share the level's
`CesiumGeoreference`, position by lat/long, and carve the photogrammetry
underneath with a Cartographic Polygon. Full steps below.

---

## Components installed in this harness

| Tool | Path | License | Purpose |
|------|------|---------|---------|
| **Niantic `spz`** CLI + lib | `~/coding/spz` (built: `~/coding/spz/build/{ply_to_spz,spz_to_ply,spz_info}`) | MIT | `.ply` ⇄ `.spz` compression (~10x). `spz_info` reports numPoints/shDegree/bbox. |
| **`make_splat_tile.py`** | `~/coding/unreal-agent-harness/splat/make_splat_tile.py` | (ours) | Wraps a 3DGS `.ply` as an UNCOMPRESSED `KHR_gaussian_splatting` 3D Tile + self-validates. Pure stdlib. (`.spz` → `spz_to_ply` first.) |
| **Brush** (Arthur Brussee) | `~/coding/brush` (CLI: `~/coding/brush/target/release/brush-cli`) | Apache-2.0 | Local Metal/wgpu Gaussian-splat **trainer** — train a `.ply` from a phone video on the M-series Mac, no NVIDIA/cloud. |

### Build / rebuild the spz CLI
```bash
cd ~/coding/spz
cmake -B build -DSPZ_BUILD_TOOLS=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build -j8
# spz auto-fetches libz/libzstd if missing; self-contained C++17.
```

---

## How `make_splat_tile.py` works (and why this exact shape)

Verified against the **actual build source**, not blog posts. The generator
emits a fully **uncompressed** `KHR_gaussian_splatting` tile that needs no
load-time decode:

1. **Read the 3DGS `.ply` directly.** Standard INRIA/Brush layout: `x,y,z`,
   `scale_0..2` (log), `opacity` (logit), `rot_0..3` (quaternion, `.ply` order
   `w,x,y,z`), `f_dc_0..2` (SH DC), `f_rest_0..44` (SH deg 1-3, channel-major).

2. **Apply the SAME transforms Cesium's `decodeSpz.cpp` applies**, so on-screen
   output matches the SPZ path exactly:
   - `POSITION` (VEC3) = `(x,y,z)` verbatim
   - `KHR_gaussian_splatting:SCALE` (VEC3) = `(exp(s0),exp(s1),exp(s2))`
   - `KHR_gaussian_splatting:ROTATION` (VEC4) = `(x,y,z,w)` in glTF xyzw order
   - `COLOR_0` (VEC4 float) = `(0.5 + 0.282095·f_dc_k)` + `sigmoid(opacity)`
     (the `SH_C0=0.282095` DC remap + alpha sigmoid, matching the decoder)
   - `KHR_gaussian_splatting:SH_DEGREE_{d}_COEF_{c}` (VEC3) = higher-order SH
     verbatim (the decoder copies these verbatim too)

3. **Real accessors → real bufferViews, sized exactly `stride*count`.** This is
   the whole point: every accessor passes Cesium's `AccessorView<T>::create()`
   bound check (`AccessorView.h`), so it can NEVER return status 4
   (`BufferViewTooSmall`) — the condition that crashed the old SPZ-stub tiles.
   No `KHR_gaussian_splatting_compression_spz_2`, no `decodeSpz` dependency.

4. **Primitive mode MUST be `POINTS` (0).** `loadGaussianSplats()` in
   `CesiumGltfComponent.cpp` skips any other mode.

5. **`extensionsUsed` lists `KHR_gaussian_splatting`.** Cesium keys the SH
   degree off the presence of the highest coef attribute
   (`countShCoeffsOnPrimitive` in `CesiumGltfGaussianSplatComponent.cpp`), so we
   emit all coefs up to the requested/available `shDegree` (deg 3 = 15 coefs).

6. **Self-validation before write.** The script re-parses the `.glb` and
   replicates Cesium's exact bound checks for every attribute; a tile that would
   fail is written as `model.glb.invalid` (never promoted) with a non-zero exit.

> The previous SPZ-embedded approach (placeholder accessors → 32-byte stub →
> trust `decodeSpz` to rebind) is preserved at `make_splat_tile.py.bak-spz`. It
> produced the status-4 Metal crash documented above; only use it if you've
> verified the SPZ decode end-to-end and need the ~10x-smaller file.

### Verifying a tile you generated
```bash
# Replicates Cesium's AccessorView bound checks offline — catches status-4 BEFORE
# you feed the tile to Metal. Also checks mode==POINTS and extensionsUsed.
python3 ~/coding/unreal-agent-harness/splat/make_splat_tile.py --validate-only out/myblock/model.glb
```

---

## Loading the hero block in UE 5.8 (the §17.4 hybrid scene)

No editor automation here — these are the steps for the second tileset. Drive
them with the MCP toolsets in guide §16.7 (`ObjectTools`/`SceneTools` →
`set_properties` → `refresh_tileset`).

1. **Keep the existing city tileset** (Google Photorealistic 3D Tiles, N2/§16) +
   its `CesiumGeoreference` + `CesiumSunSky`.
2. **Place a SECOND `Cesium3DTileset` actor.**
   - `Source` = **From Url**, `Url` = `file:///…/out/myblock/tileset.json`
     (local) **or** an `http(s)://…/tileset.json` if you serve the `out/myblock`
     dir (`python3 -m http.server` in that folder is enough for testing).
   - It auto-uses the SAME `CesiumGeoreference` already in the level (Cesium
     finds the georeference actor); both stream under one georeference + LOD.
3. **Georeference the block to its real lat/long.** Set the tileset's
   `Georeference Origin` / actor transform so the block lands where it belongs.
   The splat's own bbox is local; the actor places it on the globe. Easiest:
   move the actor in-editor over the matching spot in the Google tiles, or set
   the tileset origin lat/long to the capture location.
4. **Carve the photogrammetry underneath** to avoid z-fight / double geometry:
   add a **`CesiumCartographicPolygon`** actor over the block footprint and add
   it to the *Google* tileset's **`Cartographic Polygon`** clipping list
   (`Clip` material). The splat then "drops into" the carved hole at street
   level. (§17.4)
5. **Tune like any tileset (§16):** `MaximumScreenSpaceError` lower = sharper
   splats sooner (cost: VRAM); after batch property sets call
   **`RefreshTileset()`** (`Cesium3DTileset.h:627`) once. Don't spam it.
6. **Collision is separate.** Splats are a radiance field, not geometry — author
   box/landscape colliders for the block manually; the splat has none.

---

## Local trainer: Brush (capture → train → .ply)

Brush is our primary local trainer — cross-platform Gaussian-splatting on
**wgpu/Burn**, native macOS **Metal**, FOSS (Apache-2.0). No NVIDIA, no cloud.

### Build
```bash
cd ~/coding/brush
cargo build --release -p brush-cli       # headless trainer -> target/release/brush-cli
# (the GUI viewer is the `brush` binary / brush-app: `cargo run --release`)
```
Requires Rust 1.88+ (we have 1.95).

### Input: get camera poses from a video/photos
Brush trains from **COLMAP** output or **Nerfstudio**-format datasets. From a
phone video the pipeline is:
1. Extract frames (`ffmpeg -i clip.mov -vf fps=2 frames/%04d.jpg`).
2. Run **COLMAP** (or `ns-process-data` from Nerfstudio, or `glomap`) to get
   camera poses → a COLMAP `sparse/` + `images/` dataset.
3. Point Brush at that dataset directory.

### Train → export .ply
```bash
~/coding/brush/target/release/brush-cli  /path/to/colmap_dataset \
    --total-train-iters 30000 \
    --export-every 5000 \
    --export-path  ~/coding/unreal-agent-harness/splat/out/myblock_train \
    --export-name  block_{iter}.ply
# headless; writes a .ply (default export_{iter}.ply) every --export-every steps.
# verified flags (brush-cli --help): --total-train-iters [30000], --export-every
# [5000], --export-path, --export-name, --max-splats, --with-viewer.
# brush-cli is HEADLESS; for the live training viewer build the `brush` binary
# (brush-app): `cd ~/coding/brush && cargo run --release`.
```
Then feed the resulting `.ply` to `make_splat_tile.py` (above).

> Mac-native alternatives if Brush stalls: **CorbeauSplat** (all-in-one macOS
> video→splat), **RadianceKit**, **msplat** (fused Metal compute). See guide §17.3.

---

## What Pat needs to do to get a REAL NYC hero block

There is **no clearly-licensed, downloadable NYC street splat** anywhere public
(Sketchfab/Polycam/Luma/HuggingFace/academic all checked — see the team report).
The big urban academic datasets (MatrixCity, UrbanScene3D, INRIA benchmark
splats) are **non-commercial / research-only**. So the realistic gates are:

1. **Capture it (recommended, we then own it):** walk the block, shoot a slow
   ~1–2 min phone video (steady, lots of overlap, vary height) → COLMAP →
   `brush-cli` → `.ply` → `make_splat_tile.py` → load. 100% local + FOSS.
2. **Or download a permissively-licensed proxy block** if NYC isn't required:
   - Polycam Explore — filter "savable" + a **CC-BY** badge (only source that
     serves native `.ply`/splat files; verify each capture's license).
   - Ricardo Garnica's **CC-BY** plaza/campus splats on Sketchfab (note:
     Sketchfab serves GLB point-cloud, not native splat — would need a
     point-cloud→splat path, not this 3DGS-`.ply` tool).
   - For internal R&D **only** (NOT shippable): INRIA pretrained outdoor splats
     (`point_cloud.ply`) — research-license, do not publish.

Bottom line: **capture-by-Pat is the gate for a real NYC block.** The tooling in
this directory is ready for the `.ply` the moment it exists.
