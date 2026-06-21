# Real architectural detail — the actual method (stop the "bland 3D")

> Why our generated buildings looked bland, and the real pro workflow for detail. Ordered by **bang-for-buck** — do the top ones first; they matter far more than the bottom. Pairs with [REALISM-GUIDE.md](REALISM-GUIDE.md) (the UE-side apply) — this is the *source-of-detail* side.

## The honest diagnosis
Detail does NOT come from decals or from cranking a normal map. It comes from, in order:
**real source assets/materials  →  geometry method  →  lighting  →  (then, barely) decals.**
We were doing the weakest version of each (hand-bpy box extrusion + GPT-tiling textures + slapped-on crack decals). Fixing the *method* is the answer, not more iteration.

## 1. Don't model from scratch if you don't have to (biggest win, least effort)
Pros **kitbash + scan**, they don't hand-model every facade. Free, high-quality sources — use these BEFORE generating anything:
- **City Sample's own buildings + materials** — already in our project, photoreal, scanned-quality, free, no login. The single best source we have. (find_assets `/Game/Building/Material`, `/Game/Prop`.)
- **Quixel Megascans** — free scanned PBR surfaces (stone/concrete/plaster/metal) with albedo+normal+roughness+**displacement**, + scanned decals. Scanned >> generated tiling, every time.
- **KitBash3D** (has free kits), **Fab** free building/asset packs, **Poly Haven** (CC0 HDRIs + PBR).
A real scanned limestone material on a simple mesh beats a generated texture on an ornate mesh.

## 2. If you DO generate geometry in Blender, use the right tool
- **Geometry Nodes**, not hand-bpy box extrusion. GN turns a blockout into windows/cornices/setbacks/railings parametrically and reads far less "CG." Free resources: the **Procedural Building Generator** (Gumroad) + free GN building node libraries (80.lv). This is the modern method our `*_kit_jobs.py` scripts are a primitive version of.
- **Bevel EVERY hard edge** (Bevel modifier / GN) — razor-flat edges are the #1 CG tell; bevels catch light.
- Keep the grammar module spec (400 cm, X-centered, base-pivoted) so output still feeds `PCG_BuildingSample`.

## 3. Trim sheets — complex detail WITHOUT polygons (the game-art core technique)
A **trim sheet** is one texture + normal map packed with strips of sculpted ornament (moldings, panels, cornices, dentils, grilles). You UV facade pieces onto the strips → richly carved-looking surfaces with almost no extra geometry. This is how shipped games get ornate buildings cheaply.
- Sculpt the ornament high-poly (Blender sculpt / ZBrush) → bake to a normal+height trim sheet → tile/UV onto the kit. Or download ready trim sheets.
- For ornament that must catch real silhouette (cornices, crowns), keep it as **geometry + Nanite**; use trim sheets for the flat-ish in-between detail.

## 4. Materials: scanned, tuned by eye
- **Scanned PBR (Megascans / City Sample) over generated tiling.** Albedo + **normal** + roughness + (ideally) displacement.
- **Normal strength is tuned BY EYE against a facade-close capture** — too high reads as gravel/sandpaper (we overcooked Paris at strength 8 and even 1.5; ~0.3 was the keeper). Drop it 4–6× at a time; stop at "smooth stone with relief only at joints/edges."
- Per-object tone variation so the row isn't one color.

## 5. Lighting + post (makes the relief read)
**Lumen GI + good key/fill + soft shadows** are what make carved ornament actually read as carved. Expose to the material (light stone wants a brighter key; don't white-out, don't drop the sun low). A tasteful post/compositing pass unifies it. Without this, even great geometry looks flat.

## 6. Decals — last, subtle, and only good ones
Subtle scanned grime/streaks to break uniformity. **Never random crack-network decals** — they read fake and are NOT a detail source. If unsure, skip them; geometry + materials + light carry it.

## The order that matters
1. Scanned materials (Megascans / City Sample) — #1 surface jump
2. Real carved geometry (Nanite) + bevels — where the style lives
3. Trim sheets for cheap in-between ornament
4. Lumen lighting tuned to the materials
5. (barely) subtle grime decals
> If a building still looks bland, it's almost always #1 or #4 — not "needs more decals."
