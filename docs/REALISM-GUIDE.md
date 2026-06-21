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
