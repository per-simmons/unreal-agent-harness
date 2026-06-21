# Making a generated environment look REAL (not "bland 3D")

> Style-agnostic playbook for taking a procedurally-assembled scene (any architecture — Paris, Art-Deco, sci-fi, suburb, anything) from "obviously CG" to convincing. The levers are general; each one is illustrated with **what we actually did in the Paris block** (`ParisBlock_LVL`) as a concrete example. Pair with [PCG-GUIDE.md](PCG-GUIDE.md) (how to assemble) + [ENVIRONMENTS.md](ENVIRONMENTS.md) (the worlds).

## Why a generated scene looks fake (the two root causes)
1. **Repetition** — the same building/color/shape tiled across the grid. Real cities never repeat.
2. **Flat, untextured surfaces** — single-color materials with no texture, no normal map, no grime, and razor-flat geometry. This is the "bland 3D" tell even when the *shapes* are fine.

You fix realism by attacking variety, surface, and life — in that order of bang-for-buck. None of these is style-specific; swap the kit/material/props and the same recipe makes a sci-fi station or a 1950s suburb read as real.

## The realism levers (general → our Paris example)

### 1. Variety — no two objects identical
- **General:** drive each instance from a *weighted-random palette* of module variants, and vary height/width/rotation per instance. If the generator has no per-bay palette hook, use one graph (or seed) per building.
- **Paris:** built 12 facade variants (4 walls / 4 windows / 2 corners / mansard), gave each of the 10 buildings its own grammar graph picking a different mix, + varied height (5–7 storeys) and width per building. Adjacent buildings visibly differ.

### 2. Color / material variation
- **General:** author several tone variants of the base material (light/warm/cool/weathered) and assign a *different one per object* (per-instance custom data tint, or per-object material). One flat color across everything screams CG.
- **Paris:** a base stone material with StoneColor/GrimeColor params → 5 tone MIs (cream / warm-grey / beige / soot / pale-gold), a different tone per building.

### 3. Textured PBR surface + NORMAL MAPS — the #1 anti-"bland" lever
- **General:** replace flat-color materials with real PBR (albedo + **normal** + roughness, ideally with grime/variation). A normal map alone turns a flat wall into carved, weathered stone. Three free sources, in priority order:
  1. **Reuse the base project's own photoreal materials** — if you're in a project like City Sample, it already ships PBR limestone/concrete/brick with normals. Free, in-project, no download. **Do this first.**
  2. **Quixel Megascans** — free photoreal tiling surfaces + decals; Nanite/virtual-texture friendly.
  3. **Generate tiling textures** — GPT image-gen (subscription, no API spend) for albedo + a grayscale height → derive a normal in UE (`NormalFromHeightmap`).
- **Paris:** reusing City Sample's stone materials + generated limestone/plaster as the base (this pass) — the single biggest jump from "bland" to "stone."

### 4. Decals — grime, cracks, stains
- **General:** scatter DecalActors of soot streaks, cracks, water staining, posters/vents over the clean surfaces. "Parallax-occlusion decals look extremely convincing." This breaks the too-perfect CG uniformity. Free decals in Megascans; or generate transparent PNGs.
- **Paris:** soot-streak / crack / water-stain decals down the facades + a WorldZ grime gradient in the material.

### 5. Ornament GEOMETRY (where the style lives)
- **General:** flat boxes with window holes look cheap. Add real relief: **bevel every hard edge** (sharp flat edges are the top CG tell), multi-step cornices/string courses, dentils, pediments + keystones over windows, brackets, balustrades, pilaster capitals. **Nanite** makes high-poly ornament cheap — don't fear polycount. Generate this in Blender to the kit's module spec.
- **Paris:** the `beaux_arts_kit/detailed/` pass — beveled edges, deep dentil cornices, window pediments + console brackets, finer balcony bars.

### 6. Roofs / tops
- **General:** flat tops read as unfinished. Cap buildings with style-appropriate tops. The robust way is **separate roof actors** placed at each building's `get_actor_bounds().max.z` — NOT mid-graph `[Roof]` grammar surgery (that fragile edit silently zeroes spawns; see PCG-GUIDE).
- **Paris:** mansard-roof actors (dark zinc) along each roofline + cap planes hiding hollow grammar tops. (Art-Deco used the same recipe for ziggurat crowns.)

### 7. Street life — make it lived-in
- **General:** a bare grid on a void is the giveaway. Add ground + sidewalks + road, **trees**, **parked vehicles**, and props (lamp posts, benches, signage, trash). Reuse the base project's prop/vehicle/foliage kits, or PCG-scatter them (the way Epic's demo scattered foliage).
- **Paris:** pavement + road + 2 sidewalks, 20 City-Sample maple trees, 5 parked cars, 12 lamp posts, 6 benches.

### 8. Lighting / exposure
- **General:** clear, motivated daylight beats soup. Set exposure to the *material's* brightness (light stone wants a brighter key than dark brick); MotionBlur 0 for stills + Mac perf. **Do not** drop the sun near the horizon or pile on fog — it white-outs (hard-won lesson). Nanite + Lumen + a sane PostProcess do most of the work.
- **Paris:** warm sun, manual exposure EV ≈ −0.4 tuned for cream limestone, MotionBlur 0.

## The workflow (how to run it with agents)
Because there is **one editor** (concurrent edits freeze it), split the work:
- **Parallelize PREP (many agents, no editor):** generate the detailed geometry kit (Blender), generate/curate textures + decals, research the base project's reusable materials.
- **Serialize the APPLY (one editor agent):** import + assign PBR materials, place decals, swap in detailed meshes, scatter props.
- **QA-LOOP (don't skip):** capture aerial + eye-level + facade-close, then *actually look* — is there variety? texture/normal detail? grime? roofs? life? Fix the single weakest lever, re-capture, repeat until it reads real. (Same loop that took the glass city from spikes to real.)

## The "bland 3D → real" checklist
- [ ] Buildings differ (facade variant + height/width)
- [ ] Per-object color/tone variation
- [ ] PBR material with a **normal map** (not flat color)
- [ ] Grime / crack / stain decals
- [ ] Beveled edges + ornament relief (cornices, surrounds, brackets)
- [ ] Finished roofs (separate-actor recipe)
- [ ] Trees + vehicles + street props on real ground/sidewalks
- [ ] Exposure tuned to the material; MotionBlur 0; no fog white-out
- [ ] QA-looped from 3 angles until it actually looks real

## 2026-06-21 — THE PARIS-BLOCK DETAIL PASS (what actually moved the needle) — agent `paris-detail`
> Took `ParisBlock_LVL` from flat grey-brown "painted-drywall" facades to textured carved limestone with grime.
> Before/after: `docs/parisblock_detail_BEFORE_{street,facade}.png` → `docs/parisblock_detail_FINAL_{street,facade,aerial}.png`.
> **Ranked by bang-for-buck (do them in THIS order):**

**1. REBUILD THE SHARED MATERIAL, don't re-point meshes (the #1 fix, ~80% of the win).** Every building
already used tinted MIs of ONE master (`/Game/PCG/ParisVariants/M_ParisStone`). So adding an **albedo texture
+ a normal map to that master upgraded all 10 buildings at once** while every per-building tone MI survived
(StoneColor/GrimeColor/Rough params kept). This is far cheaper + safer than touching geometry. Recipe:
- Import the albedo + a grayscale height (TextureTools.import_file). **Set the HEIGHT texture `SRGB=false`**
  or the material won't compile ("Sampler type is Linear Color, should be Color").
- BaseColor = `existing tint Lerp` × `Albedo.RGB × ~1.75` (the ×1.75 brightens mid-grey albedo back to the
  tint's value so the textured stone keeps its tone instead of going dark).
- **Normal (the carved-stone lever) — no NormalFromHeightmap function needed** (the engine MaterialFunction
  isn't in every install). Hand-roll it: sample height at UV, UV+(du,0), UV+(0,dv); `dx=hx.R−h0.R`,
  `dy=hy.R−h0.R`; ×(−strength≈0.3, see below); `AppendVector(dx,dy)` → **`MaterialExpressionDeriveNormalZ`** (input pin
  `InXY`) → MP_Normal. Cheap, robust, reads as real relief.
  - **⚠️ CALIBRATE THE STRENGTH BY EYE — easy to overcook into sandpaper; the number that "sounds subtle"
    is still too high.** strength=8 made the limestone read as coarse gravel/popcorn. strength=1.5 was logged
    as "the keeper" but **it STILL read as all-over sandpaper grain in-level** (proven 2026-06-21 — facade
    close-ups showed crusty popcorn stone, not ashlar). **strength ≈ 0.3 is the real keeper** (-0.3 in the two
    strength Constants — `M_ParisStone:MaterialExpressionConstant_1` + `Constant_2`, signed for the −strength
    direction). At 0.3 the surface is smooth fine limestone and the carved ARCHITECTURAL relief (window frames,
    sills, cornices, quoins, ashlar courses) carries ALL the detail — the surface normal only whispers at the
    block joints. **Lesson: tune normal strength by eye against an actual facade-close capture — too high reads
    as gravel, and a value that looks reasonable as a number (1.5) can still be ~5x too strong on screen. Drop
    it 4-6x at a time and re-capture until the stone reads SMOOTH, not "lots of relief."** Also drop the
    albedo/height `TextureCoordinate` UTiling/VTiling to ~2 (not 3) so blocks are bigger / less busy.
    (Captures: `docs/parisblock_fix_BEFORE_facade.png` = strength 1.5 sandpaper; `docs/parisblock_fix_AFTER_close.png`
    + `_AFTER_facade.png` + `_AFTER_aerial.png` = strength 0.3 smooth ashlar keeper.)
- UVs: a `TextureCoordinate` with UTiling/VTiling ≈3 gave believable stone-block scale on 400cm modules.
- Surface-type variety for free: override the **`Albedo` texture param** on a few of the existing tone MIs
  (weathered-limestone on the grey/soot tones, warm-plaster on the beige) → different buildings read as
  genuinely different stone, no new materials.

**2. GRIME — bake it into the material AND scatter decals (belt + suspenders).**
- **Decals DO work on PCG/ISM facades** (ISM `bReceivesDecals` defaults true) — the trap is purely
  ORIENTATION + the decal box not reaching the wall. A `DecalActor` **projects along its local +X.**
  Wall facing −Y (e.g. a north row's boulevard face) → **yaw 90**; wall facing +Y → **yaw −90**. Place the
  actor ~100cm IN FRONT of the wall and set `decalSize.x` (projection depth) big enough to reach it
  (≥400). Verify with a bright-red full-opacity test decal first — if you see only the editor sprite, the
  box is missing the wall or the projection axis is backwards.
- **Imported decal PNGs default to `CompressionSettings=TC_EditorIcon`** (small RGBA → treated as a UI
  icon) and render wrong. Set them to **`TC_Default`** after import.
- Decal material = `MaterialDomain=MD_DeferredDecal`, `BlendMode=BLEND_Translucent`, BaseColor=a **neutral
  dark constant** (NOT the texture RGB — the generated soot/stain PNGs carry warm/red RGB that paints the
  wall blood-red), Opacity = `texture.A × scale`. Use the texture only for the alpha MASK shape.
- Material-baked grime (survives any regen, needs no actors): planar-project the soot texture via
  `WorldPosition → ComponentMask(R,B) → ×~0.0011`, then `BaseColor ×= lerp(1.0, neutralGrime≈0.40, soot.A×0.5)`.
  **Use the soot ALPHA as the mask + a NEUTRAL grime color** — multiplying the colored soot RGB straight into
  BaseColor turns shadows red (hard-won twice).

**3. ORNAMENT GEOMETRY swap — staged but the live regen is the wall (lower priority, do last).** Imported the
`beaux_arts_kit/detailed/` modules (Nanite on), made per-building tinted copies, re-pointed a building's
grammar `meshInfo`. The DATA stages fine + the block doesn't break, BUT **a BP-component PCG (BP_BuildingSample)
will NOT re-generate via MCP** — not via graph `userParameters`, not via the graphInstance, not via a `seed`
bump, not even via a full level reload (GenerateOnLoad output is serialized/cached). `ExecuteGraphInstance`
errors "not a valid PCGVolume" on BP actors. So the detailed-geo swap needs the editor UI (or a rebuilt
spawn) to land — material+decals already deliver the dominant realism, so swap geometry only when you can
drive the regen. Don't burn the budget fighting it; confirm ISM mesh refs with
`ObjectTools.get_properties(ISM, ["StaticMesh"])` (NOT the ISM component NAME — names are sticky/stale).

**Exposure for textured stone:** once the flat color became a textured albedo it read a touch dark — raised
both unbound PPVs' `Settings.autoExposureBias` from −0.4 to **+0.3** (AEM_Manual; sign rule: higher = brighter)
→ warm, legible limestone, no white-out.

**Capture loop mechanics:** `CaptureViewport` blows the token cap → it auto-saves base64 to a tool-result
`.txt`; decode with `docs/../decode_capture.py <txt> <out.png>` then Read the PNG. Pass `captureTransform`
explicitly (it has no default) and an all-zero `annotations` to disable overlays.
