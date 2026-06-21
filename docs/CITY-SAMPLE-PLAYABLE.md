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
