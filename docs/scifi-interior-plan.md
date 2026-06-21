# Sci-Fi Station Interior — FREE Asset + Build Plan

> Goal: build a **walkable sci-fi station interior** (corridors + rooms, emissive strip
> lighting, a couple hero props) in **UE 5.8** on the Mac harness, assembled by the agent over
> the **Unreal MCP**, and walked with the **City Sample player character we already verified**
> (see `CITY-SAMPLE-PLAYABLE.md`).
>
> Researched 2026-06-21. Every claim has a URL. Skeptic flags (⚠️) mark license/login/date
> gates. **This doc does NOT touch Unreal** — it's the import + assemble plan.

---

## 0. TL;DR — recommended path + the single asset to grab

**Grab one CC0 kit and assemble it: the Quaternius _Modular Sci-Fi MEGAKIT_ (270+ pieces,
CC0, corridors + rooms + doors + floors/walls/ceilings + props, FBX/OBJ/glTF, no login for
the free tier).** It is the only source that is *genuinely modular interior* (not just props),
*truly CC0/redistributable*, and *download-without-login*.

- https://quaternius.com/packs/modularscifimegakit.html (direct download)
- Mirror w/ no JS: https://quaternius.itch.io/modular-sci-fi-megakit (name-your-price, $0 ok)
- License: **CC0** — https://opengameart.org/content/modular-sci-fi-megakit
- ⚠️ **Only 60–70% of the pack is the free CC0 tier**; the remaining 30–40% (+ the Unreal-ready
  "Source" version with custom shaders) is gated behind Quaternius's Patreon/Discord. The free
  60–70% is still 150+ pieces and is plenty for a corridor-and-rooms interior. Don't promise
  the "Source/Unreal-shader" version — that needs a paid Patreon claim.

Why not the flashier Fab pack (see §1a): the **Martin Milz "Modular SciFi Station"** (147
photoreal meshes) was Fab's free-of-the-month **only until June 16, 2026 — that window is
CLOSED**; it is now **$44.99**. Use it ONLY if Pat already claimed it to his Fab account before
the 16th (then it's his forever). Otherwise it is not free.

**Build, in one line:** import the MEGAKIT FBXs via `StaticMeshTools.import_file` →
`get_bounds` to catch the 100× scale bug → snap floor/wall/ceiling tiles on a fixed grid into
a 2-corridor + 2-room layout → add emissive ceiling strips + 2 hero props → set the City
Sample / Third-Person character as the pawn → press Play and walk it. Days, not weeks.

---

## 1. Best FREE sci-fi interior asset packs — ranked

Ranking criterion: **modular interior (corridors/rooms) AND truly free to keep AND no hard
login gate AND imports cleanly to UE 5.8.**

### 🥇 1. Quaternius — Modular Sci-Fi MEGAKIT  *(the pick)*
- 270+ grid-snapping modules: "anything from a classic sci-fi corridor to large rooms or
  platforming areas." Categories: doors, floors, walls, columns, props, aliens, + more.
- **License: CC0.** FBX / OBJ / glTF. Personal + commercial + redistribution OK.
- **No login** for the free web/itch download.
- URLs: https://quaternius.com/packs/modularscifimegakit.html ·
  https://quaternius.itch.io/modular-sci-fi-megakit · CC0 confirm:
  https://opengameart.org/content/modular-sci-fi-megakit
- ⚠️ Free tier = 60–70% of pack; full set + Unreal-ready Source = Patreon/Discord. Irrelevant
  for our needs — the free tier has the corridor/room/door/floor/wall set.
- **Modular interior?** YES — corridors + rooms. This is the one.

### 🥈 2. Kenney — Modular Space Kit  *(CC0 backup / lower-poly)*
- Released 2026-02-15. **40 objects** (some animated, e.g. doors), color variants, low-poly,
  single material/atlas. CC0. Separate FBX / OBJ / glTF files. "Works with Unity, Unreal and
  all other 3D engines."
- URLs: https://kenney.nl/assets/modular-space-kit · https://kenney-assets.itch.io/space-kit
- **No login**, instant download, dead-simple to import (one atlas texture).
- **Modular interior?** Partial — it's more space-station *segments/exterior + corridor*
  than richly furnished rooms. Great as a clean, guaranteed-CC0 fallback or to mix in. Lower
  fidelity than the MEGAKIT.

### 🥉 3. Martin Milz — Modular SciFi Station (Fab)  *(best looking, but NOT free now)*
- 147 photoreal meshes: modular metal walls/flooring + solar panels, antennae, circuitry.
  UE 4.20+/5.0+, Fab Standard License (commercial + modify + distribute-in-project OK).
- ⚠️ **Free only until June 16, 2026 — EXPIRED.** Now **$44.99**.
  https://www.fab.com/listings/0667e321-31a7-40ed-b85c-6db5bbc4366b
  Context: https://www.cgchannel.com/2026/06/download-140-free-modular-assets-for-building-a-sci-fi-base/
- **Use ONLY if** Pat already clicked "Get" during the free window (then permanent on his Fab
  account → "Add to Project" in UE). Verify in his Fab Library before planning around it.
- Requires an **Epic/Fab login** to acquire either way.

### Other Fab/Marketplace "free" sci-fi interiors — verify before trusting
Fab has several modular sci-fi interior listings; most are **paid**, a few rotate as free.
Search results returned these — check each listing's price + license badge, all need a Fab login:
- "Sci-Fi Interior Modular Environment Kit" / "Modular Sci-Fi Interior" /
  "Modular Sci-Fi Corridors and Rooms" (legacy UE Marketplace) — mostly **paid**.
- https://www.fab.com/listings/322bae4e-128d-431a-b4ab-19800c6b6e88 (Modular Sci-Fi Interior Bundle)
- ⚠️ Treat "free sci-fi" search hits as paid until you see $0 + the license. Don't build the
  plan on a rotating freebie.

### CC0 community sources (mine for hero props / variety, not the base kit)
- **Sketchfab CC0 sci-fi** (e.g. "Modular Sci-Fi Kit for UE5 (FREE)" by tyapkin.art;
  "Sci-Fi Space Station Interior Pack: Modular" by noahm1216) — ⚠️ requires a **free Sketchfab
  account** to download; per-model license varies (CC0 vs CC-BY), verify the badge per model.
  https://sketchfab.com/3d-models/modular-sci-fi-kit-for-ue5-free-7f0ef96d57f741438e9e7f348d382575
- **Poly Pizza** — per-asset CC0/CC-BY GLB props (consoles, crates, terminals): https://poly.pizza
- **GitHub CC0 registries** (props + the odd room): ToxSam/open-source-3D-assets (991+ CC0
  GLB), madjin/awesome-cc0 — https://github.com/ToxSam/open-source-3D-assets ·
  https://github.com/madjin/awesome-cc0
- **Quixel Megascans** — surfaces/decals/some props are great for grunging up metal walls
  (free with Epic login, Epic Content License, **not CC0**). Good for materials, not the kit.

**Bottom line:** Quaternius MEGAKIT (CC0, corridors+rooms, no login) is the base; Kenney
Modular Space Kit is the CC0 safety net; Poly Pizza / Sketchfab-CC0 for a couple hero props;
the Milz Fab pack only if already owned.

---

## 2. Lightest path to a walkable sci-fi interior (build steps)

We already have: the Unreal MCP wired (`mcp__unreal`), FBX import via `StaticMeshTools`, a
proven mesh-placement loop, and a **verified playable character** (City Sample, both Path A
"ship's hero" and Path B "TPS mannequin via GameMode" — see `CITY-SAMPLE-PLAYABLE.md`). A
station interior is **not** a PCG grammar-facade job — it's hand-snapping modular tiles on a
grid. Steps:

1. **Download + unzip** the MEGAKIT FBXs to
   `~/coding/unreal-agent-harness/assets/scifi_interior/` (mirror our `futuristic_kit/` layout).
   Keep only: a floor tile, a wall panel, a wall-with-doorway, a ceiling tile, a door, 1–2 hero
   props (console/crate). ~6–8 meshes is enough for a convincing corridor + rooms.

2. **Import via MCP**: `StaticMeshTools.import_file` each FBX →
   `/Game/SciFiInterior/Meshes/...`. **IMMEDIATELY `get_bounds` on 1–2 meshes.**
   ⚠️ **100× scale bug (already bit us once):** Blender/exporter unit mismatch makes FBXs
   import 100× too big (a 4 m tile arrives as 400 m). If bounds are 100× off, fix at the source
   (re-export with correct scene unit) — there is **no MCP reimport-scale tool**. Quaternius
   FBXs are usually metric-correct, but **verify, never trust the "1:1" claim**
   (`PCG-GUIDE.md` lines 680–689 documents this exact failure on our facade kit).

3. **Establish a grid.** Read the floor/wall tile bounds; let `G` = tile footprint (e.g. 4 m).
   Snap everything to multiples of `G` so corridors and rooms tile seamlessly. Walls sit on
   tile edges, ceilings at wall height. (Same base-pivot/centered discipline we use for the
   facade kit — re-pivot in Blender if a tile isn't floor-pivoted.)

4. **Assemble a small layout** via MCP actor spawns (place static-mesh actors at grid coords):
   - **Corridor A** (e.g. 1×6 tiles): floor row + walls both sides + ceiling, one wall segment
     swapped for the doorway/door piece.
   - **Room 1** (e.g. 4×4): floor grid, perimeter walls, doorway connecting to Corridor A,
     ceiling, 1 hero prop (console/terminal).
   - **Corridor B** + **Room 2**: branch off Room 1 for a sense of a small station.
   Keep it ~30–60 tiles total — small, sealed, walkable. Don't build a megastructure.

5. **Emissive strip lighting** (the sci-fi "glow"):
   - Apply an **emissive material** to ceiling/wall light-strip meshes (cyan/white), OR place
     thin emissive plane actors along the ceiling seams.
   - Add a few **Rect Lights / Point Lights** for actual illumination (emissive alone doesn't
     light the scene without Lumen GI doing the work; add real lights for control).
   - Lumen handles bounce on Apple-Silicon Metal (confirmed in our docs). Keep light count
     modest.

6. **Hero props**: drop 1–2 placed props (console, crate, door frame detail) to break the
   tiled repetition. Poly Pizza / Sketchfab-CC0 props if the kit's are thin.

7. **Make it walkable** (we already verified this — reuse it):
   - **Simplest:** assemble the interior inside (or alongside) the City Sample project and use
     its shipped pawn — press Play, WASD walks it (Path A in `CITY-SAMPLE-PLAYABLE.md`).
   - **Cleaner for a bare interior level:** new level, set GameMode to the **Third Person**
     template (Manny/Quinn) so the default pawn spawns at a PlayerStart (Path B). Add a
     PlayerStart inside Corridor A, add floor collision (static meshes import with collision;
     verify `get_bounds`/collision or add a simple box collision per tile), press Play.
   - Ensure **collision** on floors/walls so the character doesn't fall through — the one thing
     to double-check on imported FBX tiles.

8. **QA capture**: use the existing PIE screenshot loop (`pie-qa-capture.md`) to confirm the
   character is standing on the floor, walls block, lights read. Iterate placement.

---

## 3. Generate-our-own fallback (Blender) — feasible, lower priority

**Yes, fully feasible** — and we already do exactly this. `futuristic_kit_jobs.py` headlessly
generates a base-pivoted, X-centered modular **facade** kit (wall/window/corner/column) as FBX
straight into the harness. A sci-fi **interior** panel kit is the same pattern, simpler
geometry:

- New `scifi_interior_jobs.py` modeled on `futuristic_kit_jobs.py`: emit
  **floor tile**, **wall panel**, **wall+doorway**, **ceiling tile**, **emissive light-strip**,
  **door** — all on a single module size (e.g. 400 cm) so they tile.
- Reuse the hard-won export rules: `bpy.context.scene.unit_settings.length_unit='CENTIMETERS'`,
  export `apply_scale_options='FBX_SCALE_ALL', apply_unit_scale=True` → **no 100× bug**
  (`PCG-GUIDE.md` lines 680–689). Base-pivot tiles (min Z = 0), center on XY.
- Material slots: slot 0 = metal panel, slot 1 = emissive trim — so UE materials apply
  consistently (same convention as the facade kit).
- Run: `/Applications/Blender.app/Contents/MacOS/Blender --background --python scifi_interior_jobs.py`

**When to use it:** if the MEGAKIT's free tier looks too sparse/off-style, or we want a kit
that's 100% ours/CC0 with zero attribution questions. Tradeoff: procedurally-generated panels
look cleaner/blockier than the MEGAKIT's detailed greebles — fine for a stylized interior, less
"lived-in" than the artist kit. **Recommendation: try the MEGAKIT first; fall back to Blender
only if needed.**

---

## 4. Scale / performance on a Mac (M4 Max, UE 5.8, Metal)

- A small interior (30–60 modular tiles, a handful of lights, 1–2 props) is **trivially light**
  vs. the City Sample city or our PCG tower fields — this is the *easy* scene to run on the Mac.
- Modular kits = heavy **mesh instance reuse** (same floor/wall mesh placed many times). Use
  **Instanced Static Mesh / HISM** or let Nanite handle it; either way draw calls stay low.
- **Lumen** (software ray tracing on Metal) handles the interior GI/emissive bounce; keep
  dynamic light count modest (a dozen is fine). **VSM** for shadows.
- Quaternius/Kenney kits are **low-to-mid poly** → near-zero geometry cost; Nanite optional.
  The Milz pack is higher-poly (use Nanite if you go that route).
- No external SSD or multi-GB download needed for the CC0 kits (tens of MB), unlike City Sample.

---

## 5. Recommended path (final) + exact grab steps

**Path:** Quaternius Modular Sci-Fi MEGAKIT (CC0) → import 6–8 tiles via MCP → verify scale →
snap a 2-corridor / 2-room interior on a 4 m grid → emissive strips + lights + 2 hero props →
walk it with the verified City Sample / TPS character → PIE-screenshot QA.

**The single asset to grab (no login, CC0):**
1. Open https://quaternius.com/packs/modularscifimegakit.html (or
   https://quaternius.itch.io/modular-sci-fi-megakit and set price to $0).
2. Download the **FBX** (or glTF) free pack — no account required for the free tier.
3. Unzip into `~/coding/unreal-agent-harness/assets/scifi_interior/`.
4. License is **CC0** (https://opengameart.org/content/modular-sci-fi-megakit) — no attribution
   needed, redistribution fine. Do **not** rely on the Patreon-gated "Source/Unreal-shader"
   version.

**If Pat wants the photoreal Milz look instead:** first check his Fab Library for "Modular
SciFi Station" — only proceed if it's already owned (the June 16 free window has closed; it's
$44.99 to buy now). It needs a Fab/Epic login and "Add to Project."

**Safety net:** Kenney Modular Space Kit (CC0, https://kenney.nl/assets/modular-space-kit) if
the MEGAKIT free tier is too thin; Blender-generate (§3) if we want a fully-owned kit.

---

## Sources
- Quaternius Modular Sci-Fi MEGAKIT — https://quaternius.com/packs/modularscifimegakit.html ·
  https://quaternius.itch.io/modular-sci-fi-megakit · CC0: https://opengameart.org/content/modular-sci-fi-megakit
- Quaternius Ultimate Modular Sci-Fi Pack (46 models, CC0) — https://quaternius.com/packs/ultimatemodularscifi.html
- Kenney Modular Space Kit (CC0, 40 obj, 2026-02-15) — https://kenney.nl/assets/modular-space-kit · https://kenney-assets.itch.io/space-kit
- Martin Milz "Modular SciFi Station" (Fab, free until 2026-06-16 — now $44.99) —
  https://www.fab.com/listings/0667e321-31a7-40ed-b85c-6db5bbc4366b ·
  https://www.cgchannel.com/2026/06/download-140-free-modular-assets-for-building-a-sci-fi-base/ ·
  https://digitalproduction.com/2026/06/11/free-sci-fi-station-lands-on-fab/
- Fab paid/rotating sci-fi interior listings — https://www.fab.com/listings/322bae4e-128d-431a-b4ab-19800c6b6e88
- Sketchfab CC0/free sci-fi (login to download, per-model license) —
  https://sketchfab.com/3d-models/modular-sci-fi-kit-for-ue5-free-7f0ef96d57f741438e9e7f348d382575
- Poly Pizza (CC0/CC-BY props) — https://poly.pizza
- GitHub CC0 registries — https://github.com/ToxSam/open-source-3D-assets · https://github.com/madjin/awesome-cc0
- Internal: `CITY-SAMPLE-PLAYABLE.md` (verified playable character), `PCG-GUIDE.md` L680–689
  (FBX 100× scale bug + fix), `futuristic_kit_jobs.py` (Blender kit-gen pattern),
  `pie-qa-capture.md` (PIE screenshot QA loop).
