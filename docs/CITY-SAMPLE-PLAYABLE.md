# City Sample — Make It Playable ("It's a Game Now")

How to take Epic's free **City Sample** (the Matrix Awakens city) and run a playable
character around it — on foot and driving — targeting **UE 5.8** on a **Mac Studio M4 Max
/ 64 GB** with the project on an external SSD.

> **Corrected 2026-06-20.** An earlier version of this doc claimed City Sample was
> "Windows/DX12-only, capped at UE 5.4, unsupported on Mac." **That was wrong.** The current
> Fab listing for **City Sample** (the Complete Project) explicitly states **Supported Unreal
> Engine Versions 5.0 – 5.8** and **Supported Target Platforms: Windows, Linux, Mac**. [1a]
> Modern Unreal on Apple Silicon (Metal RHI) runs Nanite, Lumen (software *and* hardware ray
> tracing), Virtual Shadow Maps, TSR, and MetalFX. [11][14] So City Sample on a Mac in 5.8 is
> **officially supported** — the real consideration is **performance tuning of a genuinely
> heavy project**, not platform support. And the bonus: **City Sample is already a playable
> game out of the box** — you do not build the "make it playable" part; it ships done.

Sources are cited inline as `[n]` and listed at the end.

---

## 0. The single most important fact

**City Sample is already playable.** It ships with a hero character, ~13 drivable
vehicles, walk / drive / fly modes, a working enter-exit-car interaction, crowds, and AI
traffic. You press Play and you are running around the Matrix city immediately. [1][2]

So the real question splits in two:

- **Path A — "just play what ships"**: open the project, load `Small_City_LVL`, press Play,
  move. This is the simplest "it's a game now" demo and needs *zero* Blueprint work. (§1, §6)
- **Path B — "drop in *my* character"**: replace the shipped hero with the standard UE5
  Third Person mannequin via a GameMode override. Only do this if you specifically want the
  generic Manny/Quinn character. (§2)

For an on-camera "I made the Matrix city into a game" demo, **Path A is the move.** It's
fewer steps, it can't fall through the world, and the city already behaves like a game.

---

## 1. What City Sample ships with for play (out of the box)

Per Epic's official City Sample documentation: [1]

**Maps (both are fully playable — walk, drive, fly):**
| Map | Asset name | Size | Notes |
|-----|-----------|------|-------|
| Big City | `Big_City_LVL` | 4 km × 4 km | The full Matrix Awakens city. Extremely heavy. |
| Small City | `Small_City_LVL` | scaled-down | Same features, far lighter. **Use this for the demo.** |

There is also a `Sample_Default_Map` / sandbox-style entry map in some builds, but the two
above are the playable city levels you care about. [1]

**Built-in controls (these work the instant you press Play):** [1]

*On foot (Walking):*
- **WASD** — move
- **Left-Shift** — sprint
- **X** — toggle fly mode

*Driving:*
- **W** — accelerate, **S** — brake / reverse
- **A / D** — steer
- **Spacebar** — handbrake
- **C** — **enter / exit vehicle** (see §4)

*Flying (the demo "spectator/drone" mode):*
- **WASD** — move, **E / Q** — up / down, **F / R** — speed

**GameMode + pawn:** the level's GameMode possesses **`BP_CitySamplePlayerCharacter`** as
the default pawn via the default controller. This is the shipped hero, and it's what gives
you walk/drive/fly + the camera system out of the box. [3] The camera is driven by a
custom **`BP_CitySampleCameraManager`** (in `Gameplay/Camera`) with named modes like
`Cam3P_Walking` — *not* a stock UE camera, which matters if you ever want first-person
(you duplicate a cam mode rather than bolting on a `UCameraComponent`). [4]

**Crowds + traffic:** MetaHuman crowds and AI traffic run via Mass AI. The hero and the
traffic cars share the same simulation, which is why driving feels "alive." [2]

---

## 2. Path B — drop in the standard UE5 Third Person character

Only needed if you want the generic mannequin instead of the shipped hero. Steps:

1. **Add the Third Person content to the project.** In the City Sample project, click the
   **Add (+)** button in the Content Browser → **Add Feature or Content Pack** → **Blueprint**
   tab → select **Third Person** → **Add to Project**. This drops
   `Content/ThirdPerson/…` in, including: [5][6]
   - **`BP_ThirdPersonCharacter`** — the playable mannequin (Quinn = default, Manny = alt),
     in `Content/ThirdPerson/Blueprints`. [7]
   - **`BP_ThirdPersonGameMode`** — its GameMode (default pawn = `BP_ThirdPersonCharacter`). [6]
   - Enhanced Input assets (`IMC_Default`, `IA_Move`, `IA_Jump`, …). **UE5's Third Person
     template uses Enhanced Input by default** — there's no legacy axis/action mapping to
     wire. [8]

2. **Override the level's GameMode.** Open `Small_City_LVL` → **Window → World Settings** →
   **GameMode Override** → set to `BP_ThirdPersonGameMode` (or leave City Sample's GameMode
   and just change its **Default Pawn Class** to `BP_ThirdPersonCharacter`). [9]

3. **Place a PlayerStart on solid ground.** Drag a **PlayerStart** from Place Actors into
   the viewport, on a sidewalk/street that you can confirm is a loaded, collidable tile (see
   §3). If `GetPlayerStart` finds none, the mannequin spawns at origin and may drop through
   unstreamed space.

4. **Press Play.** WASD + mouse + Space to jump (Enhanced Input default mapping). [8]

> Trade-off: Path B's mannequin has **no enter-vehicle logic** — you lose the shipped
> drive/fly. You'd be rebuilding what City Sample already gave you. That's why Path A wins
> for a demo.

---

## 3. Navigation / streaming gotchas (World Partition)

City Sample is a **World Partition** project: the world is split into cells that stream
in/out, organized further by **Data Layers**, with **HLODs** as the low-detail stand-ins
for far cells. [1] What this means for a player character:

- **Collision needs the cell loaded.** A character only has ground to stand on where the
  street/sidewalk cell is *actually streamed in*. Place your PlayerStart inside a loaded
  region, near the map's start area — not out at the map edge — or you fall through. [1]
- **Don't spawn at world origin.** With no valid PlayerStart, spawn defaults to (0,0,0),
  which in a streaming city is frequently over not-yet-loaded space → fall-through.
- **HLODs are visual only.** A far HLOD proxy may render but **not** have the same fine
  collision as the streamed-in cell. Keep the player inside genuinely loaded cells.
- **Navmesh: not required for the player.** A *player* character only needs **collision +
  streaming**, not a navmesh. Navmesh/Mass-AI lanes matter only for the **AI crowds and
  traffic**, which City Sample already ships baked. Confirmed: you do not need to build
  navigation to walk a player around. [1][2]
- **In PIE, give cells a beat to stream** before sprinting off — early frames are still
  loading. Editor "Play" from a camera already near the start region streams fastest.

---

## 4. Switching between walk and drive

City Sample has this built in — no work required on Path A:

- Walk up to one of the **parked / drivable vehicles**, press **C** to **enter**, drive
  with WASD + Spacebar handbrake, press **C** again to **exit** back on foot. [1]
- Entry/exit is handled by the **`BP_CarEntryInteraction`** Blueprint. [10]
- **Version gotcha:** on **UE 5.2 / City Sample 5.2**, entering a car caused "weird
  physics" / cars spawning without wheels. The community fix was to add a small
  **`Delay` / `DelayUntilNextTick`** before the final branch in `BP_CarEntryInteraction`
  (a timing/sync race). If driving misbehaves on whatever build you're on, that's the
  first thing to patch. [10]
- **AI-traffic caveat:** the *shipped* hero/vehicle is part of the sim. If you instead set
  a custom vehicle as the default pawn, the **AI traffic stops recognizing it and rams
  it** — a known, unsolved issue. Drive the *shipped* vehicles, don't swap in your own. [3]

---

## 5. Performance — making it playable on a Mac (M4 Max / 64 GB / external SSD)

This is a heavy project, but it is **officially Mac-supported** — the work is tuning, not
fighting the platform. Two layers:

**5a. Platform reality (it works — here's the honest picture).** City Sample is a Complete
Project listed for **UE 5.0–5.8 on Windows, Linux, and Mac**. [1a] Epic's *recommended* spec
(64 GB RAM, RTX-2080/RX-6000-class GPU, 8 GB VRAM, SSD) is written against a Windows
reference box, [1] but it describes *target horsepower*, not a platform lock. On Apple Silicon
the renderer is **Metal RHI**, and as of modern UE the heavy features City Sample leans on all
run on Metal:

- **Nanite** — practical on Mac since **UE 5.5** via the SM6 renderer (one project-settings
  toggle, no special build; needs an **M2 or newer** GPU + macOS 15+; M1 is *not* supported
  for Nanite). [11] By **UE 5.7** (shipped Nov 2025) "Nanite on Metal works across modern
  M-series GPUs and is in the same performance neighborhood as D3D12 on comparable
  workloads." [14]
- **Lumen** — "Lumen on Metal supports both **software and hardware ray tracing**" in
  UE 5.7; hardware RT uses the M3/M4/M5 ray-tracing units. [14]
- **Virtual Shadow Maps, TSR, MetalFX upscaling, MetaHumans** — all available on macOS as of
  UE 5.7. [14] (MetaHumans matter here — City Sample's crowds are MetaHuman-based.)

Real-world capability check: the M4 Max plays **Cyberpunk 2077** (a comparable AAA Lumen/RT
workload) at **~84 fps 1080p Ultra / ~54 fps 1440p Ultra** natively, and ~34 fps at 4K with
MetalFX Quality — roughly **RTX 5060 Laptop class**. [15] City Sample is *heavier* than
Cyberpunk in one specific way (thousands of Mass-AI crowd agents + traffic on the CPU side),
so expect the **Small City** to be comfortably playable on the M4 Max with tuning, and the
**Big City** to be a slideshow unless you cut crowds/traffic hard. The honest expectation:
a smooth **Small_City_LVL** demo is realistic; a smooth **Big_City_LVL** demo is not, on any
laptop-class GPU including Windows ones.

**5b. Make it smooth (concrete Mac settings):**
- **Use `Small_City_LVL`, never `Big_City_LVL`** for any live demo. Same look, a fraction
  of the load — this is the single biggest decision. [1]
- **Cut the crowds + traffic** if you only need to roam — *this is the highest-impact Mac
  knob.* City Sample's crowd/traffic spawns are toggled via **Data Layers** + the crowd-spawn
  config; disable the crowd Data Layer and drop traffic density to reclaim huge **CPU** headroom
  (Mass AI is CPU-bound and is what makes Big City unplayable). [1]
- **Confirm SM6 + Nanite are on.** Project Settings → Platforms → Mac → **Metal Shader
  Standard / SM6** (and `r.Nanite 1`). Nanite needs SM6 + an M2-or-newer GPU on macOS 15+;
  the M4 Max qualifies. [11]
- **Screen percentage / TSR is the biggest single FPS win.** Set `r.ScreenPercentage 60–70`
  and leave **TSR** as the upscaler (it's the Mac-native temporal upscaler) so 60–70% renders
  back up to a clean 1080p/1440p. The docs call out screen percentage for lower-spec runs. [1][14]
- **Engine Scalability Settings** (toolbar **Settings → Engine Scalability Settings**):
  **Medium**, then specifically lower **Shadows**, **Effects** (crowds/Niagara), and
  **Post Processing**. [12]
- **Lumen: keep it, but pick the cheaper mode.** Lumen runs on Metal (software *and* hardware
  RT). [14] For the most headroom on a heavy scene, set Lumen to **software ray tracing**
  (Project Settings → Lumen → Ray Tracing Mode) rather than hardware RT; only flip to hardware
  RT (M3/M4/M5 RT cores) if you have FPS to spare and want crisper reflections. Dropping to
  Screen-Space GI is the fallback if even software Lumen is too heavy.
- **Install on the fastest external SSD you have** — Nanite + VSM stream constantly and are
  SSD-bound. A **TB4/TB5 or USB4 NVMe** enclosure is fine; a slow USB-3 spinner/SATA drive
  will hitch badly. [1][14]
- **Cap the framerate** (`t.MaxFPS 30`) for a stable, judder-free capture rather than a
  fluctuating 25–55.

Useful console commands while tuning: `stat fps`, `stat unit` (CPU vs GPU vs draw bound),
`stat streaming`. [12]

---

## 6. The simplest "it's a game now" demo path (Path A)

Minimum steps from "project open" to "I'm running a character around the city":

1. In the Epic Games Launcher / Fab, get **City Sample** (it's a **Complete Project**, listed
   for **UE 5.0–5.8, Win/Linux/Mac** [1a]) → **Create Project** → pick **UE 5.8** and a target
   folder on your fast external SSD, then open it. [2]
2. **Content Drawer → open `Small_City_LVL`.** (Not Big City.) [1]
3. **Settings → Engine Scalability Settings → Medium**; drop screen percentage to ~60%;
   disable the crowd Data Layer. (§5b)
4. Press **Play** (green triangle). You possess the shipped hero on foot. [1][2]
5. **WASD** to run, **Left-Shift** to sprint. Walk to a car, press **C** to get in, drive,
   press **C** to get out. Press **X** for the fly/drone cam. [1]

That's the whole demo. Nothing was built — the city *is* the game.

---

## Live-demo checklist (ordered)

1. ☐ Create the project on **UE 5.8** (officially supported, 5.0–5.8 Win/Linux/Mac [1a]).
2. ☐ Project on a **fast external SSD**; confirm **SM6 renderer** is on; project opens
   without missing-plugin/shader errors (let shaders compile fully once before demoing).
3. ☐ Open **`Small_City_LVL`** (never `Big_City_LVL`).
4. ☐ **Scalability → Medium**, **screen percentage ~60%**, **crowd Data Layer off**, **`t.MaxFPS 30`**.
5. ☐ (Path B only) Add Third Person content, set **GameMode Override → `BP_ThirdPersonGameMode`**, drop a **PlayerStart** on a loaded street.
6. ☐ Press **Play**, wait ~2–3 s for cells to stream, then **WASD** to roam.
7. ☐ Walk to a car → **C** to enter → drive → **C** to exit. (If physics glitch on a
   build, patch the `BP_CarEntryInteraction` delay. [10])
8. ☐ **X** to fly for the cinematic flyover beat.

---

> ## ✅ The real consideration (corrected 2026-06-20)
>
> **City Sample on Mac in UE 5.8 is officially supported.** The Fab listing for the City
> Sample Complete Project states **Supported Unreal Engine Versions 5.0 – 5.8** and
> **Supported Target Platforms: Windows, Linux, Mac.** [1a] A prior version of this doc claimed
> it was "Windows/DX12-only, capped at 5.4, unsupported on Mac" — that claim was incorrect and
> has been removed. Nanite, Lumen (software + hardware RT), Virtual Shadow Maps, TSR, MetalFX,
> and MetaHumans all run on the Metal RHI in modern UE (Nanite practical since 5.5, full set in
> 5.7). [11][14]
>
> **The genuine consideration is not platform — it's that this is a heavy project.** That's
> true on Windows too; it's just more pronounced on laptop-class GPUs (which the M4 Max
> effectively is — ~RTX 5060 Laptop class [15]). The two things that actually decide your
> framerate:
> - **`Small_City_LVL` vs `Big_City_LVL`.** Small City is a realistic smooth demo on the
>   M4 Max with tuning. Big City is a slideshow on *any* laptop-class GPU unless you gut the
>   crowds/traffic — that's the heaviness talking, not the Mac.
> - **Mass-AI crowds + traffic are CPU-bound.** Disabling the crowd Data Layer is the single
>   biggest win (§5b).
>
> First-run caveats (normal, not blockers): give shaders a few minutes to compile on first
> open before you judge FPS or demo; create the project onto a **fast external SSD**; and make
> sure the **SM6 renderer** is enabled so Nanite is active.
>
> **If you ever want a guaranteed-light "drivable neon city"** (e.g. for a long open-world
> roam rather than the Matrix city specifically), assembling one from CC0 kits + PCG (see this
> harness's `PCG-GUIDE.md` / `pcg-city-plan.md`) is still a fine alternative — but it is an
> *alternative for weight*, not a *workaround for an unsupported platform*. City Sample itself
> runs on this Mac.

---

## Sources

1. Epic — *City Sample Project Unreal Engine Demonstration* (**UE 5.8 docs**; maps Big_City_LVL / Small_City_LVL, walk/drive/fly controls incl. **C** to enter/exit, World Partition/Data Layers/HLOD, recommended hardware/SSD spec written against a Win10+DX12 reference box, viewport screen-percentage tip): https://dev.epicgames.com/documentation/unreal-engine/city-sample-project-unreal-engine-demonstration
1a. Fab — *City Sample* listing (**Supported Unreal Engine Versions 5.0 – 5.8**; **Supported Target Platforms: Windows, Linux, Mac**; **Distribution Method: Complete Project**): https://www.fab.com/listings/4898e707-7855-404b-af0e-a505ee690e68
2. Epic — *UE5 City Sample* getting-started forum thread (what it is, ~100 GB, press Play to roam, crowds/traffic/Mass AI): https://forums.unrealengine.com/t/ue5-city-sample/521774
3. Epic forums — *City Sample change Default Pawn to Custom Vehicle* (default pawn = `BP_CitySamplePlayerCharacter`; custom vehicle breaks AI-traffic interaction): https://forums.unrealengine.com/t/city-sample-change-default-pawn-to-custom-vehicle-interactable-with-traffic/1342592
4. Epic forums — *First Person on City Sample UE 5.3* (`BP_CitySampleCameraManager`, `Cam3P_Walking` cam modes, no stock UE camera): https://forums.unrealengine.com/t/first-person-on-city-sample-ue-5-3/1858871
5. World of Level Design — *Add additional game templates into existing projects* (Add → Add Feature or Content Pack → Blueprint → Third Person → Add to Project): https://www.worldofleveldesign.com/categories/ue5/additional-game-templates-in-existing-projects.php
6. Epic forums — *Add third person starter content to existing project*: https://forums.unrealengine.com/t/how-to-add-3rd-person-starter-content-to-my-first-person-project/2022307
7. Epic — *Third Person Template in Unreal Engine* (`BP_ThirdPersonCharacter`, Quinn/Manny, `Content/ThirdPerson/Blueprints`): https://dev.epicgames.com/documentation/en-us/unreal-engine/third-person-template-in-unreal-engine
8. Epic — *Enhanced Input in Unreal Engine* (UE5 templates use Enhanced Input by default): https://dev.epicgames.com/documentation/en-us/unreal-engine/enhanced-input-in-unreal-engine
9. Epic — *How to Set up Vehicles in Unreal Engine* (World Settings → GameMode Override / Default Pawn Class dropdowns): https://dev.epicgames.com/documentation/en-us/unreal-engine/how-to-set-up-vehicles-in-unreal-engine
10. Epic forums — *UE 5.2 + City Sample 5.2 driving bug* (`BP_CarEntryInteraction`, add Delay/DelayUntilNextTick fix, wheels-missing): https://forums.unrealengine.com/t/unreal-engine-5-2-city-sample-5-2-driving-bug/1166210
11. Epic — *Bringing Unreal Engine on macOS up to feature parity with Windows — progress report* (Nanite practical on Mac via **SM6 renderer as of UE 5.5**, no special build; needs **M2+** GPU + macOS 15+, **M1 not supported** for Nanite; Lumen software RT on M-series): https://www.unrealengine.com/tech-blog/bringing-unreal-engine-on-macos-up-to-feature-parity-with-windowsprogress-report — *(historical: older note that some 2022–2024 City Sample component packs lagged on macOS is now superseded; the current Complete Project lists Mac — see [1a])* https://forums.unrealengine.com/t/mac-support-of-ue5-assets-like-city-sample-crowds/681072
12. Epic — *Scalability Reference for Unreal Engine* / Tom Looman *optimal graphics settings*: https://dev.epicgames.com/documentation/unreal-engine/scalability-reference-for-unreal-engine • https://tomlooman.com/unreal-engine-optimal-graphics-settings/
13. Epic forums — *City Sample project on UE5.5.4 and UE5.6.1 build-option issues* (a community packaging thread; **note**: this is a build-config snag, not evidence the project is unsupported — the current Fab listing covers 5.0–5.8: [1a]): https://forums.unrealengine.com/t/city-sample-project-on-ue5-5-4-and-ue5-6-1-has-issues-restricting-the-build-options/2651499
14. StraySpark — *Apple Silicon (M5) for Unreal Engine Development: Viability in 2026* (**UE 5.7** shipped Nov 2025; "Nanite on Metal … in the same performance neighborhood as D3D12"; "Lumen on Metal supports both software and hardware ray tracing"; VSM, TSR, MetalFX, MetaHumans available on macOS; Mac Studio + fast external NVMe over TB5 recommended for asset-heavy projects): https://www.strayspark.studio/blog/apple-silicon-m5-unreal-engine-development-2026
15. NotebookCheck — *Cyberpunk / AC Shadows on Apple M4 Max* (native Cyberpunk 2077: **~84 fps 1080p Ultra, ~54 fps 1440p Ultra**, ~34 fps 4K with MetalFX Quality; gaming class ≈ RTX 5060 Laptop): https://www.notebookcheck.net/Cyberpunk-AC-Shadows-on-Apple-s-M4-Max-Gaming-performance-comparable-to-the-RTX-5060-Laptop.1166765.0.html

---
## MCP-driven launch recipe (I run this once City Sample is installed + project open)
> Goal: from "project open" → smooth, playable Small City on the Mac, with no manual fiddling.
> Confirm exact asset paths with `AssetTools.find_assets` after install (names below are expected).

1. **Load the light map:** `SceneTools.load_level` → `Small_City_LVL`
   (find it: `find_assets(folder_path="/Game", name="Small_City_LVL")`). NEVER `Big_City_LVL`.
2. **Set Mac-friendly cvars** via `EditorAppToolset` (console/cvar set):
   - `r.ScreenPercentage 60`  (biggest single FPS win; raise toward 70 if smooth)
   - `t.MaxFPS 30`            (steady, judder-free capture)
   - `r.Nanite 1`             (confirm Nanite on; needs SM6 + M2+ — Pat's M4 Max is fine)
   - scalability Medium (`sg.*` group or Engine Scalability → Medium)
   - Lumen: keep, cheaper mode if needed (`r.Lumen.HardwareRayTracing 0` to force software)
3. **Turn the crowd Data Layer off** (crowds are the heaviest cost) — via Data Layers; if no MCP
   data-layer tool, do it in the Data Layers panel (one manual click) OR `a.Crowd` cull cvars.
4. **Play:** `EditorAppToolset.StartPIE` → walk (WASD) / sprint (Shift) / fly (X) / drive (C to
   enter a car). The shipped `BP_CitySamplePlayerCharacter` is the default pawn — no setup.
5. **(Optional) custom third-person character:** add Third Person content (manual one-time),
   then set `Small_City_LVL` World Settings GameMode Override → `BP_ThirdPersonGameMode`, place a
   PlayerStart on loaded ground (NOT origin → fall-through). See `UE-PLAYABLE-CHARACTER.md`.

**Pre-flight (read-only) before a live run:** confirm `Small_City_LVL` loads, SM6/Nanite on,
shaders fully compiled (watch the compiling counter), project is on the T7 Shield SSD.

---
## FASTEST PATH to the demo's photoreal look (verified 2026-06-21)
The Unreal demo's photoreal city IS City Sample. The fastest way to that exact look — no PCG, no building:
1. With the City Sample project open + MCP connected, run:
   `SceneTools.load_level` → `/Game/Map/Small_City_LVL`  (NEVER Big_City for a demo — too heavy).
2. Let shaders compile + World Partition stream (a few min; looks rough until done).
3. Result: a photoreal downtown-on-a-peninsula, sun on the ocean, warm light — the demo's coastal frame. (`docs/citysample_pristine.png`)
4. It's PLAYABLE out of the box: press Play → WASD walk, C enter/drive a car.

### LIGHTING LESSON (learned the hard way 2026-06-21)
- **Small_City's DEFAULT lighting is already the warm late-afternoon "golden-ish" look.** Leave it alone.
- Do NOT "add golden hour" by dropping the sun very low (~-11°) — at that angle this scene's SkyAtmosphere scatters into a total white-out. And do NOT add an ExponentialHeightFog at default density (~0.02) over this huge city — also white-out. And enabling SkyLight `bRealTimeCapture` without a reachable SkyAtmosphere throws a warning + floods ambient.
- If you over-tweak and wash it out: **reload the level** (`load_level` again) to discard unsaved lighting changes → pristine default restored. (Don't save the level if you want to keep the default.)
- If you genuinely want a touch warmer: a GENTLE unbound PostProcessVolume (Manual exposure ~0, WhiteTemp ~5500, bloom ~1.1) — color only, NO fog, NO low sun. Test before relying on it.

### DE-FOG / "too foggy + too overcast" → CLEAR SUNNY DAY (verified 2026-06-21, agent `glass-in-city`)
The default warm look also reads HAZY/SOUPY and a bit dim/overcast (low warm sun + a real height fog
hanging over the whole city). REDUCING atmosphere is the SAFE direction — opposite of the white-out
mistakes above. This is what cleared it to a crisp sunny midday city (small steps, captured each):
- **The fog is real, not a cvar.** `find_actors(name="fog")` → `ExponentialHeightFog_*`. Its component is
  **`HeightFogComponent0`** — get it via `ActorTools.get_components` (the `.Component0` path is NOT
  directly reachable; you must enumerate components). Default was `FogDensity 0.01, FogMaxOpacity 1,
  StartDistance 20000, bEnableVolumetricFog false`.
  - **`ObjectTools.set_properties` on `HeightFogComponent0`: `FogDensity 0.01 → 0.0015`, `FogMaxOpacity
    1 → 0.6`, `StartDistance 20000 → 40000`.** This alone drops most of the distance haze (ocean horizon
    + far buildings get crisp). Going lower (0.001) is fine too. `bEnableVolumetricFog` was already off.
  - **⚠️ UE 5.8 renamed the fog COLOR props** — `FogInscatteringColor` / `DirectionalInscatteringColor`
    error "could not be read/set." Don't touch them; density/opacity/start-distance are all you need.
- **The "overcast/dim" is the LOW WARM SUN, not clouds — there is NO VolumetricCloud or SkyAtmosphere
  actor in Small_City** (`find_actors` for cloud/atmosphere/sky → only `SkyLight2` + `DirectionalLight2`).
  The default `DirectionalLight2.LightComponent0` was `Intensity 2000, Temperature 4500 (warm), pitch
  -13°` (near-horizon → long murky low-angle light = the "overcast dim" read).
  - **RAISE the sun (safe — the white-out is from LOWERING it): pitch -13 → -35°** (mid-afternoon =
    even lighting, crisp shadows, far less atmospheric scatter), **Intensity 2000 → 2600**, **Temperature
    4500 → 5200** (drops the dim golden cast for a neutral sunny day). Keep the same YAW (sun stays over
    the ocean). Set rotation via `ActorTools.set_actor_transform`, intensity/temp via `set_properties` on
    `LightComponent0`.
  - **Checked the toward-the-sun angle (the white-out risk) — clean, no blow-out.** Raising the sun is
    safe; it's *dropping* it to ~-11° that white-outs this SkyAtmosphere-less scene. Detail/shadows fully
    preserved at pitch -35.
- **Result:** crisp sunny midday city — clear blue ocean, sharp distant buildings, bright even light, no
  soup. Before/after: `docs/citysample_clear_BEFORE.png` vs `docs/citysample_clear_aerial.png` +
  `citysample_clear_sunside.png` (toward-sun, no blow-out). Level saved (`save_assets([])`). This is a
  PERMANENT scene change (saved) — to revert to the original hazy default, `load_level` BEFORE saving, or
  set fog back to 0.01 + sun to pitch -13/2000/4500.
- **2026-06-21 FOLLOW-UP de-fog pass (agent `glass-in-city`):** Pat still read it as "too foggy/overcast
  from some angles" — specifically the SUN-BEHIND / across-the-city aerial showed a soupy gray-white band
  where sky meets ocean (the fog `FogMaxOpacity 0.6` painting the distant horizon + far geometry with fog
  color). Took the fog DOWN further: **`HeightFogComponent0` `FogDensity 0.0015 → 0.0003`, `FogMaxOpacity
  0.6 → 0.2`** (volumetric stayed off). That killed the horizon haze band on the sun-behind side while the
  sun-side aerial stayed bright and crisp (NOT dimmed — did not need a sun nudge). Confirmed from BOTH
  angles. Captures: `docs/defog_baseline_sunbehind.png` (the soupy before) vs `docs/defog_step1_sunbehind.png`
  (clear after) + `docs/defog_step1_sunside.png` (sun-side still bright). **Lesson: on the sun-behind
  horizon, `FogMaxOpacity` is the lever that matters as much as density — at 0.6 it caps the haze high
  enough to read as overcast; ~0.2 lets the distance read clean.** Verify de-fog from a sun-BEHIND aerial,
  not just sun-side — the soup only shows looking across the city into the bright sky.

### "I fall below the water / through the ground" when navigating
- That's the **editor flycam — it has NO collision**, so flying down passes through streets, ground, and below the water plane. Normal editor behavior, not a bug.
- To stay grounded (walk the streets, not clip through): **press Play** — the City Sample character has collision and stands on the ground; you won't sink below the water.

---

## ✅ VERIFIED PLAYABLE — Path A confirmed end-to-end (2026-06-21, agent via MCP 8123)

**Bottom line: `Small_City_LVL` is playable out of the box. No GameMode/PlayerStart wiring was
needed — the shipped City Sample setup already drops a possessed, grounded hero on the street.**
Tested live in the editor with `EditorAppToolset.StartPIE`, then verified by actor + log inspection
(not by the viewport image — see the shader caveat below).

### The verified spawn chain (all already correct, nothing edited)
- **`Small_City_LVL` World Settings `GameModeOverride` = None.** It does NOT override — it inherits
  the project default. (Read via `ObjectTools.get_properties` on
  `…PersistentLevel.WorldSettings` → property name is **`DefaultGameMode`** in reflection;
  `GameModeOverride` is not directly readable. Value: `"None"`.)
- **Project `GlobalDefaultGameMode` = `/Game/Gameplay/Framework/BP_CitySampleGameMode.BP_CitySampleGameMode_C`**
  (in `Config/DefaultEngine.ini` — read from disk, NOT via the MCP `read_file`, which is sandboxed
  to Content/ + Saved/ only). This is the real player GameMode (there is also a
  `BP_CitySampleGameMode_SandboxIntro` — not the default).
- **`BP_CitySampleGameMode` CDO:** `DefaultPawnClass = BP_CitySamplePlayerCharacter_C`,
  `PlayerControllerClass = BP_CitySamplePC_C`. (Read the CDO at
  `…BP_CitySampleGameMode.Default__BP_CitySampleGameMode_C`.)
- **A `PlayerStart` already exists in the level** at world **X≈-29899, Y≈-101, Z≈169**
  (`…PersistentLevel.PlayerStart_UAID_D45D6454B40F4EEC00_1906520767`). Note: the start region is at
  **X≈-30000 (negative)**, NOT the X 24000..56000 the older note guessed — use the actual PlayerStart,
  don't invent a downtown coordinate.

### Proof it spawned + possessed + is grounded (the "confirm, don't claim" step)
After `StartPIE { bSimulate:false, playMode:PlayMode_InViewPort, warmupSeconds:8 }`:
- **`IsPIERunning` → true**, and the log shows `PIE: Play in editor total start time 16.244 seconds.`
- **Pawn spawned:** `find_actors(name="CitySamplePlayerCharacter")` →
  `…UEDPIE_0_Small_City_LVL.Small_City_LVL:PersistentLevel.BP_CitySamplePlayerCharacter_C_0`
  (the `UEDPIE_0_` prefix = the live PIE world, not the editor world). Its PlayerController
  `BP_CitySamplePC_C_0` also spawned.
- **Possessed + walking (decisive):** the log emits
  `LogCitySample: Display: Logging Custom Event Sandbox-Entered to CSV.` and
  `LogCitySample: Display: Logging Custom Event Sandbox-WalkingModeEntered to CSV.` — these
  events fire *from the possessed hero entering walking mode*, so they only run on a controlled
  player character. **This is the possession proof.** (The `Controller`/`Pawn`/`AcknowledgedPawn`
  properties are NOT readable by name via `get_properties` — use the log, not a property read.)
- **Grounded at street level, NOT below water:** the pawn transform is **Z≈165** (settled from the
  PlayerStart's Z≈169), and `get_actor_bounds` gives capsule **min.z≈67, max.z≈255** — feet on the
  sidewalk, far above the water plane. No `fell out of world` / `KillZ` / "no player start" warnings
  anywhere in the log.
- The pawn has a full `CharacterMovementComponent`, `CapsuleComponent`, and the Enhanced Input
  `inputMappingContext` + `moveAction`/`lookAction` (confirmed via `list_properties`) — i.e. it is
  wired to move, not an inert pose.

### Controls (shipped, work the instant you press Play) — same as §1
WASD move · **Left-Shift** sprint · **X** toggle fly/drone cam · walk to a car + **C** to enter/drive,
**C** to exit · in PIE, click once in the play viewport for keyboard focus; **F8** ejects, **Esc** stops.

### ⚠️ Two real caveats observed this run (neither blocks play)
1. **First-PIE viewport reads SOLID MAGENTA = shaders still compiling**, not a broken scene. The
   Output Log was actively running `LogShaderCompilers` (TBasePass… / 312 materials translated) during
   the capture. Magenta is UE's default-material fallback for not-yet-compiled shaders. **Verify play
   via actor+log checks, never the PIE viewport image** — and let shaders finish compiling once before
   judging the look or FPS. (This is also why `CaptureViewport`/`CaptureEditorImage` in PIE is
   uninformative here — the documented "grabs the editor viewport" quirk *plus* the magenta.)
2. **A "Memory Pressure Warning — your system is running low on memory" toast appeared.** City Sample
   is heavy; on the M4 Max, do the §5b cuts before a real demo (crowd Data Layer off,
   `r.ScreenPercentage 60`, `t.MaxFPS 30`, Scalability Medium) to keep RAM + FPS sane.

### To reproduce (zero setup — it's already wired)
1. `SceneTools.load_level /Game/Map/Small_City_LVL` (already loaded here).
2. `EditorAppToolset.IsPIERunning` → must be false.
3. `EditorAppToolset.StartPIE { bSimulate:false, playMode:"PlayMode_InViewPort", warmupSeconds:8 }`.
4. Verify: `find_actors(name="CitySamplePlayerCharacter")` returns a `UEDPIE_0_…` pawn; log shows
   `Sandbox-WalkingModeEntered`; pawn Z is street-level (~165), not negative.
5. `EditorAppToolset.StopPIE`. (Nothing to save — GameMode/PlayerStart were unchanged.)

---

## 🚗 CAR SHOWCASE — "drive all the cars" demo level (built 2026-06-21, agent via MCP 8123)

A SEPARATE, clean level where you can walk up to and drive **all 13 City Sample vehicles**,
laid out as a dealership lineup. Built so Small_City was never touched.

**Level:** `/Game/Vehicle/Map/CarShowcase_LVL` (a duplicate of the shipped
`/Game/Vehicle/Map/VehicleTestMap` — so the original test map is untouched too). It's a
standard (non-World-Partition) level: one big flat ground brush + directional sun + skylight
+ sky sphere + atmospheric fog + a PlayerStart. Far lighter than Small_City (no crowd/traffic
Mass-AI, no streaming), so it's smooth on the Mac with no extra tuning.

### The 13 drivable vehicles (use the `_Sandbox` BP variant — NOT the plain `BP_veh*`)
The **`_Sandbox`** variant is the player-drivable one: it derives from
`BP_VehicleBase_Drivable` and ships with the C-to-enter system built in — components
`BP_CarEntryInteraction_Left` / `_Right`, `BP_CarExitInteraction`, `ContextualAnim`,
`VehicleMovementComp`, `MassAgent`. (The plain `BP_veh*` and the `trailer01` are NOT
self-drivable showcase pawns.) Placed:

| # | Vehicle BP (all under `/Game/Vehicle/.../`) | Type |
|---|---|---|
| 1 | `vehCar_vehicle02/BP_vehCar_vehicle02_Sandbox` | car |
| 2 | `vehCar_vehicle03/BP_vehCar_vehicle03_Sandbox` | car |
| 3 | `vehCar_vehicle05/BP_vehCar_vehicle05_Sandbox` | car |
| 4 | `vehCar_vehicle06/BP_vehCar_vehicle06_Sandbox` | car |
| 5 | `vehCar_vehicle07/BP_vehCar_vehicle07_Sandbox` | car |
| 6 | `vehCar_vehicle12/BP_vehCar_vehicle12_Sandbox` | car |
| 7 | `vehCar_vehicle13/BP_vehCar_vehicle13_Sandbox` | car |
| 8 | `vehVan_vehicle01/BP_vehVan_vehicle01_Sandbox` | van |
| 9 | `vehVan_vehicle09/BP_vehVan_vehicle09_Sandbox` | van |
| 10 | `vehTruck_vehicle04/BP_vehTruck_vehicle04_Sandbox` | truck |
| 11 | `vehTruck_vehicle08/BP_vehTruck_vehicle08_Sandbox` | truck (garbage) |
| 12 | `vehTruck_vehicle11/BP_vehTruck_vehicle11_Sandbox` | truck |
| 13 | `vehBus_vehicle10/BP_vehBus_vehicle10_Sandbox` | bus |

### Layout (dealership lineup, all facing the player, yaw 90, origin Z=140 = wheels on ground)
- **Row 1 (7 cars):** Y = 2800, X from −28500 → −24000 (step 750).
- **Row 2 (6 trucks/vans/bus):** Y = 1300, X from −28500 → −24250 (step 850).
- **PlayerStart:** ~(−26360, 4521, 146), facing −Y — you spawn ~17 m in front of the lineup,
  centered, looking right at the cars.
- **Ground is flat at Z≈50** (traced); vehicles placed with `snap_to_ground` then verified at
  origin Z=140 (bounds min.z ≈ 50 = tires on the deck).

### Controls (shipped City Sample — work the instant you press Play)
**Walk up to any car and press `C` to get in and drive.** WASD move · **Left-Shift** sprint
walking · drive with **W** accel / **S** brake-reverse / **A·D** steer / **Spacebar** handbrake
· **C** again to exit · **X** fly/drone cam. Click once in the play viewport for keyboard focus;
**F8** ejects, **Esc** stops.
> The level's `WorldSettings.DefaultGameMode` = None → it **inherits the project default
> GameMode** (`BP_CitySampleGameMode`), whose default pawn is `BP_CitySamplePlayerCharacter`
> with the `BP_CitySamplePC` controller. That's why walk + C-to-drive works with zero wiring.

### Mac perf + look
- An **unbound `PostProcessVolume`** (`Showcase_PostProcess`, Priority 1) with
  **`bOverride_MotionBlurAmount=true, MotionBlurAmount=0`** — the motion-blur kill that made
  Small_City comfortable. (`bUnbound=true`.)
- **ScreenPercentage:** UE 5.8's `FPostProcessSettings` no longer exposes
  `bOverride_ScreenPercentage`, so set it at runtime if you want it: console **`r.ScreenPercentage 50`**
  (and optionally **`t.MaxFPS 30`**). Honestly this level is light enough you probably don't
  need either — there are no crowds/traffic/streaming here.
- Lighting left at the test-map default (directional sun pitch −31, skylight, sky sphere) — clean,
  even, clear shadows under the cars. Per the Small_City lesson, didn't drop the sun low / add fog
  (white-out risk).

### VERIFIED drivable (StartPIE, confirmed by actors + log — not just the image)
- `StartPIE {PlayMode_InViewPort, warmup}` → `IsPIERunning=true`; log:
  `LogWorld: Bringing World …UEDPIE_0_CarShowcase_LVL… up for play`.
- **Possessed + walking:** `find_actors("CitySamplePlayerCharacter")` → a `UEDPIE_0_…`
  pawn; log fires `LogCitySample: … Sandbox-WalkingModeEntered` + `Sandbox-Entered` (these
  only run on the controlled hero = possession proof). Pawn grounded at Z≈194 near the
  PlayerStart, no `fell out of world` / `KillZ`.
- All 13 `_Sandbox` vehicles present in the PIE world (`…_Sandbox_C_1` instances), each carrying
  `VehicleMovementComp` + the `BP_CarEntryInteraction` components → drivable via C.

### Gotchas hit (so you don't repeat them)
1. **Duplicating a level marks the copy dirty** → `load_level` refuses ("unsaved changes").
   `save_assets(["/Game/.../CarShowcase_LVL"])` first, *then* load it. (VehicleTestMap itself
   was never dirtied/saved.)
2. **VehicleTestMap is a suspension-test playground** — it has concrete barriers / ramps / kerbs
   (`StaticMeshActor_*`, `Cube*`) scattered through the middle. They sat right in the lineup and
   blocked the walk path, and a couple of vehicles `snap_to_ground`-ed *onto a barrier* and ended
   up floating (car05 at Z=438, truck08 at Z=251). Fix: delete the obstacle actors in the lineup
   footprint, then re-set the two floaters to Z=140. Verify Z per-vehicle after deleting obstacles.
3. **`get_actor_bounds` on these vehicle BPs is unreliable for a seat check** — it includes huge
   MassAgent / async-detection helper-component bounds (gave min.z = −737 nonsense). Trust the
   origin Z matching the neighbors that snapped cleanly (140), and the PIE physics settle, not the
   bounds box.
4. **`CaptureViewport` requires `captureTransform`, `annotations`, AND the base64 PNG is ~3–5 MB**
   — it blows the tool-output token cap. Pass `annotations` with everything 0 + `classFilter:null`,
   and decode `returnValue.image.data` to a file via python rather than reading it inline.
5. First-PIE viewport shows a **white/magenta ground wash = shaders still compiling** (documented
   above) — verify drivability via actors+log, not the image; let shaders finish before judging look.

### Reproduce / reset
- Open: `SceneTools.load_level /Game/Vehicle/Map/CarShowcase_LVL` → press Play → walk to a car →
  **C** to drive. That's it.
- Captures: `docs/car_showcase_aerial.png` (3/4 aerial of the lineup) + `docs/car_showcase_ground.png`
  (ground-level 3/4). (Both grabbed mid-shader-compile, hence the ground wash.)
