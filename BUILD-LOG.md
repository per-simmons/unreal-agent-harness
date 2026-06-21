# Build Log — Real NYC in Unreal, Agent-Driven (for the audience)

A plain-language, chronological log of how we built a real New York City inside Unreal Engine 5.8,
driven almost entirely by an AI agent (Claude) over MCP — what we tried, what broke, and how we fixed it.
Free / open-source only, on a Mac Studio M4 Max. (Technical companion: `AGENTIC-GAMEDEV-GUIDE.md`.)

---

## The goal
Build a recognizable, real New York City in a game engine — as photoreal as possible — **programmatically**,
with an AI agent doing the clicking, and as little manual work from me as possible. $0 budget: FOSS only.

## The setup (what we wired up first)
- **Unreal Engine 5.8** + the official **Unreal MCP plugin** — this is the bridge that lets the agent
  place actors, set properties, move the camera, and screenshot the viewport, all over a local port (8123).
- **`AllToolsets` + Python plugins** — unlock the full set of building tools (scene, static mesh, materials, etc.).
- **A "vision" harness (`ue_qa.py`)** — the screenshot the editor returns is multi-megabytes; this script
  decodes it to a small PNG + a JSON of the camera pose and actors, so the agent can actually *see* its work
  without drowning in data. This "capture → decode → look → fix" loop is the core of agent-driven 3D.
- **Cesium for Unreal v2.27, built from source for 5.8** — the plugin that streams real-world 3D map data.
  (Took fixing 8 compile errors to get it building on 5.8.)

## The three ways to get "real NYC" (all free, all programmatic)
1. **Photoreal tiles (Google Photorealistic 3D Tiles via Cesium)** — real textures, windows, facades. The
   "actual buildings" look. Streams from the cloud.
2. **Accurate massing (FOSS `roofer` LOD2)** — reconstructs Manhattan's true building shapes from open LiDAR
   + city footprints. Real Empire State setbacks + spire, real street grid. White/untextured (open data only
   sees rooftops), but the *shape* is genuinely NYC. A plain mesh → imports clean, never crashes.
3. **Gaussian splat from existing video** — took a Creative-Commons YouTube walking-tour of a real Manhattan
   street and reconstructed it as a photoreal "splat," with **zero filming** — fully automated on the Mac
   (yt-dlp → COLMAP → Brush trainer → tile). Pixel-level realism along the camera path.

## What actually shipped
- ✅ **roofer Manhattan rendered live in UE 5.8** — accurate massing, Empire State visible, stable, agent-imported.
- ✅ **Splat pipeline proven** — real NYC street block reconstructed from existing video, $0, no capture.
- 🟡 **Photoreal Google tiles** — in progress (auth/token + the "rebase to scene origin" step; see below).

---

## The hard-won fixes (the stuff that actually broke — the good audience material)
These are the real lessons of agent-driven game dev. Every one cost time; each is now a one-line rule.

- **Editor hung on every launch (no error, frozen at ~543 MB).** Cause: we'd enabled UE Python *Remote
  Execution* (`bRemoteExecution=True`) to call functions the agent couldn't — but on macOS that multicast
  listener **hangs the boot**. Fix: turn it off. (Lesson: don't enable remote-exec on a Mac.)
- **Editor crashed to desktop (Metal GPU crash).** Cause: **our own Gaussian-splat tile** had a malformed
  data field (a "POSITION accessor" pointing at a 32-byte stub instead of the real geometry) → the GPU tried
  to lock a null buffer → instant crash. Fix: rewrote the tile generator to produce valid, self-validating
  data. (Lesson: bad asset data crashes the GPU; validate before loading.)
- **"No crash logs anywhere."** We had zero logging, so every crash was a mystery. Fix: built `ue_launch.sh`
  (full logging) + `ue_crashlog.sh` (prints the crash callstack instantly). The crash logs live in
  `~/Library/Application Support/Epic/UnrealEngine/5.8/Saved/Crashes/`, NOT the project folder.
- **The MCP "port" was up but the editor wouldn't respond.** Cause: after a crash, Unreal's **CrashReporter**
  process keeps squatting on port 8123, so commands hit the dead reporter. Fix: kill the CrashReporter.
- **Ray-tracing memory overflow on fly-through.** Fix: force ray tracing OFF at the project level
  (`[SystemSettings] r.RayTracing=0`) — more reliable than a runtime toggle.
- **Launching the raw editor binary hangs on macOS.** Fix: launch via `open MyProject.uproject` (proper GUI
  context), not the bare binary.
- **The "Cesium plugin incompatible" dialog every launch.** Fix: bump the plugin's declared engine version
  from 5.5 → 5.8 in its manifest. Dialog gone.
- **The machine got super slow mid-session.** Not Unreal — it was **Krisp** (the dictation/noise app) stuck
  at 116% CPU fighting the audio stack, plus a leftover Docker VM. Lesson: when everything lags, check the
  actual CPU hogs before blaming the heavy app. (Also: 28 GB of swap looks scary but isn't the lag if RAM is
  free — active CPU/audio loops were the real cause.)
- **The "rebase" gotcha (in progress).** Cesium tiles load at their true position on the globe (~6,000 km from
  the scene origin), where floating-point precision breaks rendering. They have to be "rebased" to the origin
  — which needs a Cesium *function* call the agent's tool layer can't make directly. Still solving cleanly.

---

## How the agent works (the meta-story for the audience)
- The agent **can't see** unless we build it eyes: every change is screenshot → decoded → looked at → corrected.
- The agent **can't click dialogs** it can't see — so account/auth steps (Cesium ion sign-in, etc.) still need a human.
- Heavy 3D work is **fragile**: GPU crashes, boot hangs, port conflicts — so the real skill is *diagnostics +
  logging + small reversible steps*, not just "ask it to build a city."
- We **spawned helper agents in parallel** for the research/asset work (one built the splat pipeline, one did
  the LiDAR reconstruction, one fixed the crash) while the main agent drove the editor.

_(This log is appended to as we go.)_

## Update — photoreal tiles: auth fixed, but a focus-crash + the rebase wall
- **Google token chain solved:** Cesium ion asset 2275207 (Google Photorealistic 3D Tiles) now 404s — Google
  no longer serves it free via ion; you need your *own* Google Maps API key. Switched the tileset to load
  Google directly (`tile.googleapis.com/v1/3dtiles/root.json?key=...`) → "Loading tileset ... done", no error.
  Tiles load fine now.
- **New crash, instantly diagnosed by our own `ue_crashlog.sh`:** calling "Focus on selected" (FocusOnActors)
  on a Cesium3DTileset crashes UE — `OnFocusEditorViewportOnThis()` calls `getRootTile()`, and if the root
  tile isn't loaded yet it dereferences null → SIGSEGV. **Rule: never FocusOnActors a Cesium tileset.**
- **Still open: the rebase.** The photoreal tiles load but sit at their true globe coordinates; getting them to
  the scene origin (so a scripted camera can see them) needs Cesium's georeference *function* call, which the
  agent's tool layer can't make. This is THE remaining piece for fully-automated photoreal.

## 2026-06-19 — Disabled Cesium Gaussian-Splat subsystem (UObjectArray.h:1083 crash fix)

`UCesiumGaussianSplatSubsystem::Tick` crashed the editor (Assertion Index>=0,
UObjectArray.h:1083) via the unconditional per-frame `initializeForWorld`. We only
use Google Photorealistic 3D Tiles, never splats. Applied Option B from
`docs/cesium-splat-subsystem-disable.md`.

- **Patch** (`cesium-build/cesium-unreal/Source/CesiumRuntime/Private/CesiumGaussianSplatSubsystem.cpp`):
  - `GetTickableTickType()` → `return ETickableTickType::Never;` (was `::Always`) — keeps the
    subsystem from registering with the tickable manager, so Tick() never runs and no
    `CesiumGaussianSplatSystemActor`/Niagara is spawned.
  - First line of `Tick(float)` → `return;` (belt-and-suspenders).
  - Backup: `CesiumGaussianSplatSubsystem.cpp.orig.bak` (pristine original).
- **Rebuild** (CesiumRuntime only, via hostproj): `Build.sh HostProjEditor Mac Development
  -Project=cesium-build/hostproj/HostProj.uproject` → **Succeeded** in ~12s. Only benign
  linker warnings (prebuilt cesium-native libs tagged macOS 26.0 vs link target 14.0).
  Output: `cesium-build/cesium-unreal/Binaries/Mac/libUnrealEditor-CesiumRuntime.dylib`
  (33,258,832 bytes, BuildId 55116800 — matches the project manifest).
- **Deploy**: copied that dylib into
  `~/Documents/Unreal Projects/MyProject/Plugins/CesiumForUnreal/Binaries/Mac/libUnrealEditor-CesiumRuntime-0003.dylib`
  (the name the project's `UnrealEditor.modules` resolves; no manifest edit needed).
  Backup of the old binary: `libUnrealEditor-CesiumRuntime-0003.dylib.prepatch.bak`.
  md5 src==dest verified.
- Also mirrored the patch into the project plugin's own Source copy
  (`MyProject/Plugins/CesiumForUnreal/Source/.../CesiumGaussianSplatSubsystem.cpp`, backup
  `.orig.bak`) so a future project-side rebuild keeps the fix.
- Editor was NOT relaunched — handing back for verification (CesiumGaussianSplatSystemActor
  should be gone + no UObjectArray.h:1083 crash; Cesium3DTileset rendering unaffected).

## ✅ WIN — Photoreal Manhattan rendering, crash-free (Jun 19)
Full Google Photorealistic 3D Tiles NYC skyline rendered in UE 5.8 via Simulate. The chain that finally worked:
1. **Splat crash killed at the root:** patched `UCesiumGaussianSplatSubsystem::GetTickableTickType → Never` (+ early `return` in Tick), rebuilt CesiumRuntime, swapped the dylib. No more `UObjectArray.h:1083` tick-crash. Editor stable through Simulate + StopPIE.
2. **Rebase order:** create georeference + tileset → set tileset `tilesetSource=FromUrl` (Google `tile.googleapis.com/v1/3dtiles/root.json?key=...`) + link `georeference` FIRST → THEN set georeference `OriginPlacement=CartographicOrigin` lat 40.758 lon -73.9855 h 150. (`set_properties` on Origin* fires PostEditChangeProperty→UpdateGeoreference; subscribe the tileset before the broadcast.)
3. **Streaming + guaranteed rebase:** `StartPIE` Simulate (BeginPlay fires rebase, world ticks → Cesium streams). Capture the editor viewport in-sim.
4. **Landscape was BURYING the city:** the OpenWorld template's 65 landscape tiles sat at Z~0 and hid everything but the tallest towers. Batch-removed all 65 via `ProgrammaticToolset.execute_tool_script` (find "Landscape" → remove_from_scene loop) → full dense skyline revealed.
- Gotchas reaffirmed: never FocusOnActors a Cesium tileset; launch via `open` not raw binary; CrashReporter squats 8123 after a crash; MCP connection drops on every editor relaunch (needs `/mcp` reconnect) — so DON'T relaunch unless necessary.

## The three approaches, plainly (and last-night vs today)
The whole project is really three different answers to "real NYC, and beat the melty-up-close problem":

1. **Photoreal (Google 3D Tiles)** — real aerial-captured city. Gorgeous from above, **melts at street level** (it's photogrammetry from planes — no real data on building sides). Whole city. This is what we flew last night and got rendering cleanly today. The melt is fundamental, not fixable by settings.
2. **Roofer / "accurate massing"** — FOSS reconstruction from open LiDAR + building footprints. Correct building *shapes* (real ESB setbacks, real grid, real heights) but **white/untextured** (LiDAR only sees rooftops). Whole city, clean, not melty. NEW today.
3. **Gaussian splat** — reconstruct ONE block from video → sharp photoreal up close (the melty fix), but one block per video. Tried last night (the tile was broken + crashed the GPU); the generator is fixed today.

**Honest ceiling:** no single FREE option is both whole-city AND sharp at street level. Pick: photoreal whole-city (melty close), accurate-white whole-city (roofer), or sharp one-block (splat).

### What changed today vs last night
- **Stability:** found + fixed the root cause of the crashes (Cesium gaussian-splat subsystem crashing every tick → patched to never tick + rebuilt the dylib). Last night was a crash/hang/reconnect loop; today the editor stays up.
- **roofer accurate-massing path added** (new).
- **splat tile fixed** (last night's crashed the GPU — malformed accessor; rewrote the generator, now valid).
- **photoreal skyline rendering cleanly** (same Google source as last night, but stable + the burying landscape removed).
- Built the diagnostics that made all this findable: `ue_launch.sh`, `ue_crashlog.sh`, the `unreal-stability-gotchas` skill, local UE/Cesium docs.

### The splat block — what + how to view
- **Block:** Cedar Street, downtown Manhattan (near Wall St / Trinity Church) — a 20s CC-BY YouTube walking-tour segment into a covered colonnade. Source + license + pipeline in `assets/splat_hero/PROVENANCE.md`.
- **Files:** trained `.ply` in `assets/splat_hero/train/`, Cesium tile in `assets/splat_hero/tile/`.
- **Viewing:** the `qa_render_*.png` is a raw point-projection (dark, NOT representative). Real splats look photoreal in a proper rasterizer. In-engine splat rendering is currently DISABLED (we patched the splat subsystem off to stop the crash) — so view the `.ply` in a standalone Gaussian-splat viewer to judge quality.

## Making it usable — navigation, streaming quality, saving (Jun 19)
After the photoreal city rendered, the work shifted to actually flying + improving it:
- **Navigation was broken for a dumb reason:** the editor's viewport **Camera Speed was 0.007** (microscopic) — right-click+WASD "did nothing" because movement was sub-millimeter. Fix: Perspective dropdown → Camera Movement → Camera Speed up to 4+. Also requires "Use WASD for camera control" enabled (Editor Prefs → search WASD → Flight Camera Control Type). NOT a bug in the scene — just the speed value.
- **Saving / "untitled" fix:** the editor reopens the OpenWorld *template* (untitled), not our map. There's no "save level" in the MCP, but `AssetTools.save_assets([...])` CAN save a level **once it has a name** — naming an untitled level still needs a one-time `Cmd+S` (saved as `/Game/NYC/NYCFklyover2`). After that the agent saves it via `save_assets` (no more Cmd+S). The Google tileset DID persist into the named save this time.
- **Tile streaming quality tuned** (on the Cesium3DTileset, via set_properties): `maximumCachedBytes` 2 GB, `maximumSimultaneousTileLoads` 32, `loadingDescendantLimit` 40, `preloadAncestors`/`preloadSiblings` true, `forbidHoles` true → pops in faster, stays sharp where you've flown. `maximumScreenSpaceError` 16→8 = noticeably sharper facades (lower = sharper but more RAM/VRAM).
- **The blotchy-on-rotate** is normal Cesium streaming (coarse→sharp, like Google Earth) — tuned, not eliminable; same at runtime, not a "gameplay" toggle.
- **RAM check:** editor ~4.2 GB, 78% free, swap 0 — tons of headroom on the 64 GB M4 Max. Golden-hour lighting is ~0 RAM (just changes the sun). The real RAM cost is the tile cache + lower MSE.
- **Golden-hour lighting:** in progress via two doc-only agents (design + crash-safety review) — apply + QA pending.

_(This log is LOCAL ONLY — `~/coding/unreal-agent-harness/` is not a git repo; nothing here is on GitHub.)_

## Golden-hour lighting (Jun 19)
Planned by two doc-only agents (design + crash-safety review), applied via MCP, no crash. Approach = plain UE rig (NOT CesiumSunSky — it ticks in-editor + re-enables RT, would crash; and its sun needs a UFUNCTION we can't call over MCP).
- **Sun angle:** `ActorTools.set_actor_transform` on the DirectionalLight → rotation pitch **-8** (sun ~8° above horizon = golden band), yaw **-55** (rakes light down the avenues), roll **0** (clears the template's 112° roll). Rotation is on the ACTOR, not the component.
- **Warmth:** `ObjectTools.set_properties` on the light's `LightComponent0` → `Temperature 4000` (`bUseTemperature` already true). Lower = more orange (3700 deep sunset, 4300 subtle).
- **Intensity:** this light is on the LEGACY units path (value was 6, NOT physical lux) — do NOT set 50000+ or it clips white. Left near default.
- **Exposure misstep + fix:** tried a PostProcessVolume with Manual exposure (`AutoExposureBias 11`) — that BLEW THE SCENE TO WHITE and threw "Cached lighting in Lumen and real-time sky capture going to be clipped (adjust r.EyeAdaptation.CachedLightingPreExposure)". Root cause: manual EV wildly mismatched the scene + real-time SkyLight capture. **Fix: removed the PostProcessVolume** → back to auto-exposure (clean, no warning); the warm low sun alone delivers golden hour. (If auto-exposure ever washes the mood out, add a PPV with a MILD bias, not 11.)
- **Kept:** SkyAtmosphere defaults (low sun + bAtmosphereSunLight=true reddens the horizon for free), SkyLight real-time capture (auto-warms ambient), VolumetricCloud (warm-lit cloud bottoms sell golden hour). Full plan: `docs/golden-hour-lighting-plan.md`.

## Reverted golden hour → neutral + more realistic (Jun 19)
Golden hour read too orange. Reverted to neutral daylight + pushed realism:
- DirectionalLight `LightComponent0`: `Temperature` 4000 → **6500** (neutral, kills the orange), `Intensity` 6.
- Sun angle raised: pitch -8 → **-38** (normal midday daylight, less extreme rake), yaw -55, roll 0.
- Cesium tileset `maximumScreenSpaceError` 8 → **4** (max practical detail — noticeably sharper facades/windows; RAM fine on 64 GB, ~78% free). This is THE realism lever for photoreal tiles.
- Removed the PostProcessVolume earlier → the Lumen/sky-capture clipping warning is gone.
- Result: clean neutral photoreal Manhattan, sharp facades, no warning. Saved to /Game/NYC/NYCFklyover2 via AssetTools.save_assets.
- Dials if wanted later: MSE lower than 4 = diminishing returns + heavier; for "more realistic" beyond tiles, options are TSR/higher screen percentage (needs console cvar, not MCP) or software Lumen GI (riskier — RT history).

## MSE tuning lesson (Jun 19)
MSE 4 was TOO aggressive — ~16x the tile data of MSE 16; the network can't keep up so it stays blobby/low-detail far longer = worse experience. Reverted to **MSE 8** (good balance, fast). Rule: MSE is the speed↔sharpness dial — HIGHER = faster load + less blobbing + lower peak detail; LOWER = sharper eventually but slow/blobby while streaming. Use 8 (balanced) or 16 (snappy) for FLYING; only drop to 4 for a STILL hero shot (let it fully resolve, capture, raise back).

## Flight mode (pilotable Play mode) — Jun 19
"Flight simulator" = full Play mode with a free-flying pawn over the photoreal city (not external MSFS). Setup (planned by the flight-pawn doc agent, docs/flight-pawn-setup.md):
- Cesium ships a globe-aware flying pawn: `DynamicPawn` (Blueprint on C++ `GlobeAwareDefaultPawn`) + `FloatingGameMode` — both in `Plugins/CesiumForUnreal/Content/` (no Samples project needed).
- Setting WorldSettings `GameModeOverride` to a class via MCP set_properties FAILED ("could not be set" — class/TSubclassOf value). **Workaround that worked:** drop `DynamicPawn` into the level via `add_to_scene_from_asset` (/CesiumForUnreal/DynamicPawn) at spawn pose (0, -15000, 30000 = ~300 m over origin, pitch -20 yaw 90), then set its `AutoPossessPlayer` = `Player0`. Saved.
- **MCP `StartPIE` (full, bSimulate=false) bails:** "PIE ended before warmup completed" — the log shows PIE actually starts clean (no crash, spawns pawn, runs ~5s) then tears down at the warmup mark. So full PIE via MCP auto-start is unreliable; **the human pressing the Play button works** (PIE stays up, DynamicPawn auto-possesses). Controls: WASD move, mouse look, E/Q up/down, Shift/wheel speed, Esc exit. Must click in the viewport for focus.
- Crash-safe: splat patch holds through PIE BeginPlay, RT off, georeference origin untouched (BeginPlay rebases), never FocusOnActors the tileset.

## Getting a realistic plane — Fab (Jun 19)
The free auto-download CC0 sites (Poly Pizza/Kenney/Quaternius) are ALL low-poly cartoon — looks terrible against photoreal tiles. Realistic + free = **Fab** (Epic's marketplace; no public API/MCP, no programmatic download — needs the user's clicks). NOTE: the "OpenAI API key" for the SemanticSearch toolset is unrelated — it only searches assets ALREADY in the project, it does NOT fetch/realistic-ize models; don't add it for this.
Fab usage: open the Fab plugin in-editor (Window → Fab, or Content Drawer's Fab button) → Discover/Search → search "airplane/airliner/jet" → filter **Free** → pick a realistic STATIC-MESH model → **Add to Project** (or Add to My Library → My Library tab → Add to Project) → imports to Content Browser (Fab/ folder). Then attach to the chase-cam pawn (rig spec: docs/plane-chase-pawn.md). Watch for SKELETAL-mesh planes (use SkeletalMeshComponent or export static). Chase-cam rig = attach StaticMesh+SpringArm(bDoCollisionTest=false)+Camera to the DynamicPawn via ActorTools.add_component; open risk = making the chase camera the active view on GlobeAwareDefaultPawn (fallback: DefaultPawn, not globe-aware).

## Third-person plane chase cam — the real bug was SCALE (Jun 19)
Long debug. Final root cause found via get_bounds + my own editor captures (NOT guessing): the imported Boeing787 mesh was ~**100× too big** — bounds ~6,000 m (6 km), not 62 m. So the chase camera (placed 24–130 m back) was always *inside* the kilometers-wide fuselage → near-clip ate it → "shadow but no plane" / giant gray surface. Fix: PlaneMesh component `RelativeScale3D` = 0.01 → plane ~60 m → chase cam at 90 m back / 28 m up / −6° framed it perfectly (verified by editor capture: 787 centered, Empire State ahead).
Other real bugs fixed along the way (all symptoms of, or compounding, the scale issue):
- `bOwnerNoSee=true` on the plane mesh → pawn's own camera hides it (still casts shadow). Set false.
- Cesium DynamicPawn uses its OWN `Camera` component as the view (no CalcCamera override) — so reposition THAT camera (RelativeLocation behind+above, bUsePawnControlRotation=false), don't fight it with a SpringArm.
- QA-capture gotcha: `CaptureViewport` during PIE grabs the EDITOR viewport, not the possessed chase cam → useless for QA. RELIABLE QA = plain editor (no PIE, no origin-shift), position editor camera at pawn+chase-offset, capture. That's how the scale bug was finally seen.
- Cesium globe-anchor moves the pawn to world origin (0,0,0) in editor after georef; chase offset is RELATIVE so it's origin-shift-proof.
- LESSON: always get_bounds an imported mesh FIRST and sanity-check meters vs cm — a 100× scale error silently breaks everything downstream.

## PCG procedural city — going photoreal (Jun 20)
New direction: build a city the way Epic's PCG demo does (shape → districts → blocks → buildings → highways → photoreal), LIVE for the audience — our own city, not a replica. Decided to go PHOTOREAL via City Sample (Epic login + download = manual gate). PCG is a real graph-authoring API via the MCP (`PCGToolset`). Full living guide: `docs/PCG-GUIDE.md` (+ detailed recipe `docs/pcg-city-plan.md`, research `docs/pcg-city-research.md`). Keep PCG-GUIDE.md updated as we learn.

## City Sample Buildings — acquisition status (Jun 20)
Pat added **City Sample Buildings** (free, Epic Content License, 2,000+ meshes) to his Fab library. Hit **"No compatible project found"** on Add-to-Project (classic UE-version-compat issue — MyProject is 5.8). Resolving: confirm the listing's supported engine versions; if 5.8 unsupported, add to a supported 5.x version then **migrate** the .uassets into MyProject. See docs/PCG-GUIDE.md.

## City Sample = the playable photoreal city (Jun 20)
Pivoted from building our own city to **City Sample** (the Matrix Awakens city, free Complete Project, **officially 5.0–5.8 + Mac** per current Fab listing — an earlier agent's "Windows-only/5.4" claim was WRONG, corrected). It ships PLAYABLE: walk/drive/fly out of the box (C to enter cars). Downloading ~182GB to the T7 Shield SSD. Runs on Mac Studio M4 Max in 5.8 (Nanite via SM6 since 5.5, Lumen/VSM/TSR/MetalFX on Metal). Use `Small_City_LVL` (never Big City) + perf settings. Guides: `docs/CITY-SAMPLE-PLAYABLE.md` (incl. MCP launch recipe) + `docs/UE-PLAYABLE-CHARACTER.md`.

## Enabled the MCP in the City Sample project (Jun 20)
City Sample created as a fresh Fab project (`futuristiccitysample` on the T7 SSD, UE 5.8, 91GB, has Small_City + Big_City maps) — but a fresh project has no MCP server, so Claude couldn't drive it ("Unable to connect"). Fixed by editing config (editor must be quit + reopened after): `.uproject` → enabled ModelContextProtocol + AllToolsets (+ Python already on); `Config/DefaultEngine.ini` → `[ModelContextProtocolSettings]` bAutoStartServer=True / port 8123 / `/mcp`, plus `bRemoteExecution=False`. Reusable recipe: `docs/UNREAL-MCP-ENABLE.md`. Next: Pat quits+reopens the editor → `/mcp` reconnect → drive Small_City_LVL.
