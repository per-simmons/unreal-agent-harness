"""Headless Blender generator for ART DECO facade-kit VARIANTS — so an Art Deco
block can be built from modules that all look DIFFERENT (no two buildings the
same). The realism lever for the PCG grammar generator.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python art_deco_variants_jobs.py

This is a sibling of `art_deco_kit_jobs.py` (the original 5-module kit). It reuses
the EXACT module spec + helpers so every variant drops into Epic's PCG grammar
generator (PCG_Building_CitySample / PCG_BuildingSample → ExtractMeshInfo) the
same way the originals do.

THE MODULE SPEC (non-negotiable — or the grammar assembles broken geometry):
  ExtractMeshInfo computes  Size = $Extents.X * 2   and   PivotOffset = -$LocalCenter
  So every module MUST be:
    - WIDTH along local X, CENTERED on X  -> X spans -200 .. +200  (Extents.X=200 -> Size=400)
    - DEPTH along Y, shallow, centered on Y
    - HEIGHT along Z, base-pivoted        -> Z spans 0 .. floorH  (min.z = 0)
  Consistent 400cm width + 400cm floor height so everything tiles. verify_bounds()
  asserts X-centered / Y-centered / base-pivoted in bpy BEFORE export.

VARIANTS (the goal — variety per grammar symbol so 1920s skyscrapers differ):
  WALL   (symbol W):  a = plain pier, b = fluted pier, c = chevron-spandrel, d = geometric-relief
  WINDOW (W1/W2):     a = vertical ribbon, b = window+metal grille, c = stepped-spandrel, d = window+sunburst
  CORNER (C):         a = plain quoin, b = stepped/chamfered
  CROWN  (top):       a = ziggurat step, b = spire-top, c = fluted cap
  GROUND (ground W1): the grand deco lobby (kept, single variant)

2 material slots on EVERY mesh: slot 0 = Stone (warm terracotta/limestone),
slot 1 = Bronze (metal trim). FBX exports cm-1:1 to UE (the iter4 unit lesson).
"""
import bpy, bmesh, os, math, mathutils, json

ROOT = os.path.expanduser("~/coding/unreal-agent-harness/assets/art_deco_kit/variants")
os.makedirs(ROOT, exist_ok=True)

# ---- THE MODULE SPEC (cm) -------------------------------------------------
MODULE_W = 400.0          # width along local X, CENTERED -> X in [-200, +200]
HALF_W   = MODULE_W / 2.0 # 200  (Extents.X -> generator Size = HALF_W*2 = 400)
FLOOR_H  = 400.0          # height along Z, base-pivoted -> Z in [0, 400]
DEPTH    = 30.0           # shallow facade depth along Y, centered -> Y in [-15, +15]
HALF_D   = DEPTH / 2.0    # 15
GROUND_H = 600.0          # taller grand-lobby floor variant
CROWN_H  = 800.0          # stepped crown is taller than a normal floor


# ---------------------------------------------------------------------------
# scene / material / mesh helpers (mirror art_deco_kit_jobs.py exactly)
# ---------------------------------------------------------------------------

def reset_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images,
                 bpy.data.cameras, bpy.data.lights, bpy.data.objects):
        for b in list(coll):
            if getattr(b, "users", 0) == 0:
                try:
                    coll.remove(b)
                except Exception:
                    pass


def make_mats():
    """slot 0 = warm stone / terracotta, slot 1 = bronze metal trim."""
    stone = bpy.data.materials.new("M_Stone")
    stone.use_nodes = True
    b = stone.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = (0.62, 0.45, 0.32, 1.0)
        b.inputs["Metallic"].default_value = 0.0
        b.inputs["Roughness"].default_value = 0.72
    bronze = bpy.data.materials.new("M_Bronze")
    bronze.use_nodes = True
    b = bronze.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = (0.46, 0.31, 0.13, 1.0)
        b.inputs["Metallic"].default_value = 1.0
        b.inputs["Roughness"].default_value = 0.30
        if "Emission Color" in b.inputs:
            b.inputs["Emission Color"].default_value = (0.30, 0.18, 0.05, 1.0)
            b.inputs["Emission Strength"].default_value = 0.15
    return stone, bronze


def bm_to_obj(bm, name):
    me = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    return obj


def box(bm, x0, x1, y0, y1, z0, z1, mat=None):
    """Axis-aligned box. Return its 6 faces (optionally pre-tagged with mat)."""
    v = [bm.verts.new((x, y, z))
         for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    def V(ix, iy, iz):
        return v[iz * 4 + iy * 2 + ix]
    faces = []
    faces.append(bm.faces.new((V(0,0,0), V(1,0,0), V(1,1,0), V(0,1,0))))  # bottom
    faces.append(bm.faces.new((V(0,0,1), V(0,1,1), V(1,1,1), V(1,0,1))))  # top
    faces.append(bm.faces.new((V(0,0,0), V(0,1,0), V(0,1,1), V(0,0,1))))  # -X
    faces.append(bm.faces.new((V(1,0,0), V(1,0,1), V(1,1,1), V(1,1,0))))  # +X
    faces.append(bm.faces.new((V(0,0,0), V(0,0,1), V(1,0,1), V(1,0,0))))  # -Y (front)
    faces.append(bm.faces.new((V(0,1,0), V(1,1,0), V(1,1,1), V(0,1,1))))  # +Y (back)
    if mat is not None:
        for f in faces:
            f.material_index = mat
    return faces


def chevron_row(bm, x0, x1, z_base, h, n, mat=1, y_front=None, y_depth=4.0):
    """Row of n up-pointing chevron triangles (the Deco zigzag), proud off the
    front plane. Sits flush on y_front so the module stays Y-centered."""
    if y_front is None:
        y_front = -HALF_D
    span = x1 - x0
    step = span / n
    for i in range(n):
        bx = x0 + i * step
        pts = [(bx, z_base), (bx + step/2, z_base + h), (bx + step, z_base)]
        b2 = [bm.verts.new((px, y_front, pz)) for (px, pz) in pts]
        t2 = [bm.verts.new((px, y_front + y_depth, pz)) for (px, pz) in pts]
        cf = [bm.faces.new(b2), bm.faces.new(list(reversed(t2)))]
        for k in range(3):
            cf.append(bm.faces.new((b2[k], b2[(k+1)%3], t2[(k+1)%3], t2[k])))
        for f in cf:
            f.material_index = mat


def sunburst(bm, cx, z_base, radius, h, n_rays, mat=1, y_front=None, y_depth=5.0):
    """Fan of bronze rays (the iconic Deco sunburst), proud off the front plane,
    radiating up from a base center. Stays within the X envelope."""
    if y_front is None:
        y_front = -HALF_D
    for i in range(n_rays):
        frac = i / (n_rays - 1)
        ang = math.radians(20 + 140 * frac)  # 20..160 deg fan
        tipx = cx + math.cos(ang) * radius
        tipz = z_base + math.sin(ang) * h
        rw = radius * 0.05
        pts = [(cx - rw, z_base), (cx + rw, z_base), (tipx, tipz)]
        b2 = [bm.verts.new((px, y_front, pz)) for (px, pz) in pts]
        t2 = [bm.verts.new((px, y_front + y_depth, pz)) for (px, pz) in pts]
        cf = [bm.faces.new(b2), bm.faces.new(list(reversed(t2)))]
        for k in range(3):
            cf.append(bm.faces.new((b2[k], b2[(k+1)%3], t2[(k+1)%3], t2[k])))
        for f in cf:
            f.material_index = mat


def finalize(obj, name, stone, bronze):
    """2 mat slots (stone, bronze), UV, normals out, origin at base-center."""
    me = obj.data
    me.materials.clear()
    me.materials.append(stone)   # slot 0
    me.materials.append(bronze)  # slot 1
    obj.name = name
    me.name = name + "_mesh"

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=0.001)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")

    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    return obj


def verify_bounds(obj, label, exp_floor_h=FLOOR_H, exp_half_w=HALF_W, tol=0.5):
    """Assert X-centered 400cm width, shallow centered Y, base-pivoted Z."""
    me = obj.data
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    zs = [v.co.z for v in me.vertices]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    minz, maxz = min(zs), max(zs)
    w = maxx - minx
    ok_xcenter = abs((minx + maxx) / 2.0) <= tol
    ok_width   = abs(w - exp_half_w * 2) <= tol
    ok_basez   = abs(minz) <= tol
    ok_height  = abs(maxz - exp_floor_h) <= tol
    ok_ycenter = abs((miny + maxy) / 2.0) <= tol
    ok = ok_xcenter and ok_width and ok_basez and ok_height and ok_ycenter
    status = "OK" if ok else "**FAIL**"
    print(f"[BOUNDS {status}] {label}: "
          f"X[{minx:.1f},{maxx:.1f}] w={w:.1f} (Xc={ok_xcenter} w={ok_width}) | "
          f"Y[{miny:.1f},{maxy:.1f}] (Yc={ok_ycenter}) | "
          f"Z[{minz:.1f},{maxz:.1f}] (base={ok_basez} h={ok_height})")
    return {
        "x": [round(minx, 1), round(maxx, 1)],
        "y": [round(miny, 1), round(maxy, 1)],
        "z": [round(minz, 1), round(maxz, 1)],
        "width": round(w, 1),
        "extents_x": round(w / 2.0, 1),
        "generator_size": round(w, 1),
        "x_centered": ok_xcenter,
        "base_pivoted": ok_basez,
        "status": status,
    }


# ===========================================================================
# WALL VARIANTS (grammar symbol W) — solid bay between windows
# ===========================================================================

def _wall_slab_and_cap(bm, floor_h, cap_t=14.0, body_inset=14.0):
    """Common to all walls: stone body slab (set back so detail reads proud) +
    a bronze cap line at the top. Returns nothing; mutates bm."""
    box(bm, -HALF_W, HALF_W, -HALF_D + body_inset, HALF_D, 0, floor_h, mat=0)
    box(bm, -HALF_W, HALF_W, -HALF_D, -HALF_D + 8.0, floor_h - cap_t, floor_h, mat=1)


def wall_a(floor_h=FLOOR_H):
    """W variant A — PLAIN PIER: a clean stone bay with a single proud center
    pilaster and the bronze cap line. The quiet bay (lets neighbours breathe)."""
    bm = bmesh.new()
    _wall_slab_and_cap(bm, floor_h)
    # one broad proud pilaster up the center
    box(bm, -40, 40, -HALF_D, -HALF_D + 12.0, 12, floor_h - 18, mat=0)
    # thin bronze reveals flanking it
    for sx in (-46, 40):
        box(bm, sx, sx + 6, -HALF_D + 10, -HALF_D + 12.0, 12, floor_h - 18, mat=1)
    return bm_to_obj(bm, "mod_wall_a")


def wall_b(floor_h=FLOOR_H):
    """W variant B — FLUTED PIER: 6 proud vertical stone flutes full height with
    bronze reveals in the grooves (the original mod_wall look)."""
    bm = bmesh.new()
    cap_t = 14.0
    _wall_slab_and_cap(bm, floor_h, cap_t=cap_t)
    n_flutes = 6
    span = (HALF_W - 12) - (-HALF_W + 12)
    pitch = span / n_flutes
    for i in range(n_flutes):
        cx = (-HALF_W + 12) + pitch * (i + 0.5)
        box(bm, cx - pitch*0.30, cx + pitch*0.30, -HALF_D, -HALF_D + 16.0,
            12.0, floor_h - cap_t - 2, mat=0)
        box(bm, cx - pitch*0.06, cx + pitch*0.06, -HALF_D + 14.0, -HALF_D + 15.0,
            12.0, floor_h - cap_t - 2, mat=1)
    return bm_to_obj(bm, "mod_wall_b")


def wall_c(floor_h=FLOOR_H):
    """W variant C — CHEVRON-SPANDREL: a stone bay carrying a tall stacked
    chevron/zigzag bronze band up its center (the Deco spandrel motif as the
    whole bay face)."""
    bm = bmesh.new()
    _wall_slab_and_cap(bm, floor_h)
    # two narrow stone piers framing a recessed central panel
    for sx in (-HALF_W, HALF_W - 56):
        box(bm, sx, sx + 56, -HALF_D, HALF_D, 0, floor_h, mat=0)
    # stacked chevrons up the central recessed panel
    px0, px1 = -HALF_W + 56, HALF_W - 56
    n_rows = 5
    row_h = (floor_h - 40) / n_rows
    for r in range(n_rows):
        chevron_row(bm, px0, px1, 20 + r * row_h, row_h * 0.7, n=4, mat=1)
    return bm_to_obj(bm, "mod_wall_c")


def wall_d(floor_h=FLOOR_H):
    """W variant D — GEOMETRIC-RELIEF: a stone bay with a stepped/concentric
    rectangular relief panel (the Deco 'frozen fountain' geometric inset),
    bronze-lined."""
    bm = bmesh.new()
    _wall_slab_and_cap(bm, floor_h)
    # concentric stepped rectangular relief, centered
    rings = [(150, floor_h*0.42, 0), (110, floor_h*0.30, 1), (72, floor_h*0.19, 0)]
    zc = floor_h * 0.52
    for hw, hh, mat in rings:
        yo = -HALF_D + (2.0 if mat == 0 else 0.0)
        box(bm, -hw, hw, yo, yo + 8.0, zc - hh, zc + hh, mat=mat)
    # vertical bronze accent bars top + bottom of the panel
    for zc2 in (floor_h*0.90, floor_h*0.12):
        box(bm, -150, 150, -HALF_D, -HALF_D + 4.0, zc2 - 8, zc2 + 8, mat=1)
    return bm_to_obj(bm, "mod_wall_d")


# ===========================================================================
# WINDOW VARIANTS (grammar symbols W1 / W2) — the main facade unit
# ===========================================================================

def _window_piers(bm, floor_h, pier_w=46.0, pinstripe=True):
    """Two full-height stone piers framing the bay (the vertical ribs that align
    across floors). Returns the inner glazing x-range (gx0, gx1)."""
    for sx in (-HALF_W, HALF_W - pier_w):
        box(bm, sx, sx + pier_w, -HALF_D, HALF_D, 0, floor_h, mat=0)
        if pinstripe:
            cx = sx + pier_w/2
            box(bm, cx - 6, cx + 6, -HALF_D, -HALF_D + 4.0, 8, floor_h - 8, mat=1)
    return -HALF_W + pier_w, HALF_W - pier_w


def window_a(floor_h=FLOOR_H):
    """W variant A — VERTICAL RIBBON WINDOW: tall uninterrupted recessed glazing
    between the two piers, a single slim bronze mullion stack — the clean
    soaring vertical-ribbon Deco window."""
    bm = bmesh.new()
    gx0, gx1 = _window_piers(bm, floor_h)
    # recessed glazing full height
    box(bm, gx0, gx1, -HALF_D + 9.0, HALF_D, 0, floor_h - 16, mat=0)
    # one central slim bronze mullion full height
    box(bm, -5, 5, -HALF_D + 6, -HALF_D + 9.0, 14, floor_h - 28, mat=1)
    # thin bronze sill + lintel
    for hz in (12, floor_h - 22):
        box(bm, gx0 + 4, gx1 - 4, -HALF_D + 6, -HALF_D + 9.0, hz - 4, hz + 4, mat=1)
    return bm_to_obj(bm, "mod_window_a")


def window_b(floor_h=FLOOR_H):
    """W variant B — WINDOW + METAL GRILLE: recessed glazing crossed by a full
    bronze grille (2 vertical mullions + 3 horizontal bars = the Deco window
    screen) and a chevron spandrel on top (the original mod_window)."""
    bm = bmesh.new()
    gx0, gx1 = _window_piers(bm, floor_h)
    spand_h = floor_h * 0.20
    gz0, gz1 = 0.0, floor_h - spand_h
    box(bm, gx0, gx1, -HALF_D + 9.0, HALF_D, gz0, gz1, mat=0)
    for mx in (gx0 + (gx1-gx0)*0.33, gx0 + (gx1-gx0)*0.66):
        box(bm, mx - 4, mx + 4, -HALF_D + 6, -HALF_D + 9.0, gz0 + 6, gz1 - 6, mat=1)
    for hz in (gz0 + (gz1-gz0)*0.25, gz0 + (gz1-gz0)*0.5, gz0 + (gz1-gz0)*0.75):
        box(bm, gx0 + 6, gx1 - 6, -HALF_D + 6, -HALF_D + 9.0, hz - 4, hz + 4, mat=1)
    chevron_row(bm, gx0, gx1, floor_h - spand_h + 6, spand_h * 0.7, n=4, mat=1)
    return bm_to_obj(bm, "mod_window_b")


def window_c(floor_h=FLOOR_H):
    """W variant C — STEPPED-SPANDREL WINDOW: glazing topped by a STEPPED
    (ziggurat) bronze+stone spandrel panel — horizontal setback bars stacking up
    to the next floor, the layered Deco spandrel."""
    bm = bmesh.new()
    gx0, gx1 = _window_piers(bm, floor_h)
    spand_h = floor_h * 0.28
    gz0, gz1 = 0.0, floor_h - spand_h
    box(bm, gx0, gx1, -HALF_D + 9.0, HALF_D, gz0, gz1, mat=0)
    # simple cross mullion on the glazing
    box(bm, gx0 + 6, gx1 - 6, -HALF_D + 6, -HALF_D + 9.0,
        gz0 + (gz1-gz0)*0.5 - 4, gz0 + (gz1-gz0)*0.5 + 4, mat=1)
    box(bm, -5, 5, -HALF_D + 6, -HALF_D + 9.0, gz0 + 8, gz1 - 8, mat=1)
    # stepped spandrel: 3 stacked bars, each narrower + proud, alternating mat
    steps = [(gx1 - gx0) * 0.5, (gx1 - gx0) * 0.40, (gx1 - gx0) * 0.30]
    sh = spand_h / 3.0
    for i, hw in enumerate(steps):
        z0 = gz1 + i * sh
        mat = 1 if i % 2 else 0
        box(bm, -hw, hw, -HALF_D, -HALF_D + 9.0, z0, z0 + sh * 0.8, mat=mat)
    return bm_to_obj(bm, "mod_window_c")


def window_d(floor_h=FLOOR_H):
    """W variant D — WINDOW + SUNBURST MOTIF: recessed glazing with a bronze
    SUNBURST fan rising over the lintel (the iconic Deco sunrise motif) and a
    simple sill grille below."""
    bm = bmesh.new()
    gx0, gx1 = _window_piers(bm, floor_h)
    sun_zone = floor_h * 0.26
    gz0, gz1 = 0.0, floor_h - sun_zone
    box(bm, gx0, gx1, -HALF_D + 9.0, HALF_D, gz0, gz1, mat=0)
    # light grille on the glazing (2 horizontal bars)
    for hz in (gz0 + (gz1-gz0)*0.4, gz0 + (gz1-gz0)*0.72):
        box(bm, gx0 + 6, gx1 - 6, -HALF_D + 6, -HALF_D + 9.0, hz - 3, hz + 3, mat=1)
    # bronze lintel bar
    box(bm, gx0, gx1, -HALF_D, -HALF_D + 6.0, gz1 - 6, gz1, mat=1)
    # sunburst fan over the lintel, centered, within X envelope
    sunburst(bm, 0.0, gz1 + 4, radius=(gx1 - gx0)*0.46, h=sun_zone * 0.82,
             n_rays=9, mat=1)
    return bm_to_obj(bm, "mod_window_d")


# ===========================================================================
# CORNER VARIANTS (grammar symbol C) — closes the box
# ===========================================================================

def corner_a(floor_h=FLOOR_H):
    """C variant A — PLAIN QUOIN: a clean full-height stone corner pier with a
    single bronze cap band. The quiet corner."""
    bm = bmesh.new()
    box(bm, -HALF_W, HALF_W, -HALF_D, HALF_D, 0, floor_h, mat=0)
    # bronze cap band
    box(bm, -HALF_W, HALF_W, -HALF_D, -HALF_D + 4.0, floor_h - 12, floor_h, mat=1)
    # a single proud vertical stone edge rib
    box(bm, -HALF_W, -HALF_W + 28, -HALF_D, -HALF_D + 12.0, 8, floor_h - 16, mat=0)
    return bm_to_obj(bm, "mod_corner_a")


def corner_b(floor_h=FLOOR_H):
    """C variant B — STEPPED / CHAMFERED QUOIN: 3 setback stone boxes shrinking
    upward with bronze banding at each shelf + proud flutes on the lower section
    (the original mod_corner — the Deco quoin)."""
    bm = bmesh.new()
    steps = [(HALF_W, HALF_D, 0.0, floor_h * 0.55),
             (HALF_W * 0.86, HALF_D * 0.9, floor_h * 0.55, floor_h * 0.82),
             (HALF_W * 0.72, HALF_D * 0.8, floor_h * 0.82, floor_h)]
    for hw, hd, z0, z1 in steps:
        box(bm, -hw, hw, -hd, hd, z0, z1, mat=0)
        box(bm, -hw, hw, -hd, -hd + 4.0, z1 - 8.0, z1, mat=1)
    # proud vertical flutes on the lower section
    x0, x1 = -HALF_W + 20, HALF_W - 20
    n = 4
    pitch = (x1 - x0) / n
    for i in range(n):
        cx = x0 + pitch * (i + 0.5)
        box(bm, cx - pitch*0.21, cx + pitch*0.21, -HALF_D, -HALF_D + 10.0,
            8.0, floor_h * 0.55 - 8.0, mat=0)
    return bm_to_obj(bm, "mod_corner_b")


# ===========================================================================
# CROWN VARIANTS (top course) — the iconic Art Deco silhouette
# ===========================================================================

def crown_a(crown_h=CROWN_H):
    """Crown variant A — ZIGGURAT STEP: 5 concentric setback stone steps to a
    central bronze spire, bronze banding + a sunburst-chevron band on the lowest
    step front (the Chrysler/ESB stepped crown — the original mod_crown)."""
    bm = bmesh.new()
    n_steps = 5
    for i in range(n_steps):
        frac0, frac1 = i / n_steps, (i + 1) / n_steps
        hw = HALF_W * (1.0 - 0.16 * i)
        hd = HALF_D + (HALF_W * 0.20) * (1.0 - 0.16 * i)
        z0, z1 = crown_h * 0.55 * frac0, crown_h * 0.55 * frac1
        box(bm, -hw, hw, -hd, hd, z0, z1, mat=0)
        box(bm, -hw, hw, -hd, hd, z1 - 6.0, z1, mat=1)
    # central bronze pyramidal spire
    sp_base = crown_h * 0.55
    spw = HALF_W * 0.10
    pts = [(-spw, -spw), (spw, -spw), (spw, spw), (-spw, spw)]
    bottom = [bm.verts.new((x, y, sp_base)) for (x, y) in pts]
    apex = bm.verts.new((0, 0, crown_h))
    for k in range(4):
        bm.faces.new((bottom[k], bottom[(k+1) % 4], apex)).material_index = 1
    bm.faces.new(bottom).material_index = 1
    # sunburst-chevron band on the lowest step front
    yf = -(HALF_D + (HALF_W * 0.20))
    chevron_row(bm, -HALF_W, HALF_W, crown_h * 0.04, crown_h * 0.11, n=5,
                mat=1, y_front=yf, y_depth=5.0)
    return bm_to_obj(bm, "mod_crown_a")


def crown_b(crown_h=CROWN_H):
    """Crown variant B — SPIRE-TOP: a low stepped stone base launching a TALL
    multi-tier bronze spire/needle (the Chrysler-needle silhouette) flanked by
    two short corner finials."""
    bm = bmesh.new()
    # low 2-step stone base
    base_top = crown_h * 0.30
    box(bm, -HALF_W, HALF_W, -HALF_D - HALF_W*0.18, HALF_D + HALF_W*0.18,
        0, base_top * 0.6, mat=0)
    box(bm, -HALF_W*0.78, HALF_W*0.78, -HALF_D - HALF_W*0.10, HALF_D + HALF_W*0.10,
        base_top * 0.6, base_top, mat=0)
    box(bm, -HALF_W*0.78, HALF_W*0.78, -HALF_D - HALF_W*0.10, HALF_D + HALF_W*0.10,
        base_top - 8, base_top, mat=1)
    # tall central bronze spire built from 3 stacked shrinking pyramidal tiers
    z = base_top
    tw = HALF_W * 0.34
    tiers = [(tw, crown_h * 0.26), (tw * 0.6, crown_h * 0.24), (tw * 0.3, crown_h * 0.20)]
    for halfw, th in tiers:
        pts = [(-halfw, -halfw), (halfw, -halfw), (halfw, halfw), (-halfw, halfw)]
        bottom = [bm.verts.new((x, y, z)) for (x, y) in pts]
        nhw = halfw * 0.45
        tpts = [(-nhw, -nhw), (nhw, -nhw), (nhw, nhw), (-nhw, nhw)]
        topv = [bm.verts.new((x, y, z + th)) for (x, y) in tpts]
        bm.faces.new(bottom).material_index = 1
        bm.faces.new(list(reversed(topv))).material_index = 1
        for k in range(4):
            bm.faces.new((bottom[k], bottom[(k+1)%4], topv[(k+1)%4], topv[k])).material_index = 1
        z += th
    # final needle point
    nb = z
    npw = HALF_W * 0.06
    pts = [(-npw, -npw), (npw, -npw), (npw, npw), (-npw, npw)]
    bottom = [bm.verts.new((x, y, nb)) for (x, y) in pts]
    apex = bm.verts.new((0, 0, crown_h))
    for k in range(4):
        bm.faces.new((bottom[k], bottom[(k+1)%4], apex)).material_index = 1
    bm.faces.new(bottom).material_index = 1
    # two short corner stone finials
    for sx in (-HALF_W + 18, HALF_W - 18 - 36):
        box(bm, sx, sx + 36, -HALF_D, HALF_D, base_top, base_top + crown_h * 0.12, mat=0)
        box(bm, sx, sx + 36, -HALF_D, HALF_D,
            base_top + crown_h * 0.12 - 6, base_top + crown_h * 0.12, mat=1)
    return bm_to_obj(bm, "mod_crown_b")


def crown_c(crown_h=CROWN_H):
    """Crown variant C — FLUTED CAP: a single bold stone parapet block carrying
    tall vertical bronze flutes (continuing the pier lines up over the top) and a
    crowning bronze cornice — the simpler 'fluted cap' crown."""
    bm = bmesh.new()
    cap_h = crown_h * 0.62
    # main parapet block (slightly proud on Y for mass, still Y-centered)
    hd = HALF_D + HALF_W * 0.10
    box(bm, -HALF_W, HALF_W, -hd, hd, 0, cap_h, mat=0)
    # tall vertical bronze flutes up the front (bold, proud off the parapet)
    n = 9
    x0, x1 = -HALF_W + 14, HALF_W - 14
    pitch = (x1 - x0) / n
    for i in range(n):
        cx = x0 + pitch * (i + 0.5)
        # deep proud bronze rib + a flanking stone reveal so it self-shadows
        box(bm, cx - pitch*0.20, cx + pitch*0.20, -hd, -hd + 22.0,
            18, cap_h - 36, mat=1)
        box(bm, cx - pitch*0.34, cx - pitch*0.20, -hd + 10.0, -hd + 16.0,
            18, cap_h - 36, mat=0)
    # stepped bronze cornice crowning the block
    box(bm, -HALF_W, HALF_W, -hd, hd, cap_h - 28, cap_h - 14, mat=1)
    box(bm, -HALF_W*0.9, HALF_W*0.9, -hd*0.92, hd*0.92, cap_h - 14, cap_h, mat=0)
    box(bm, -HALF_W*0.9, HALF_W*0.9, -hd*0.92, hd*0.92, cap_h, cap_h + crown_h*0.06, mat=1)
    # a small central bronze finial block
    box(bm, -HALF_W*0.16, HALF_W*0.16, -HALF_D, HALF_D,
        cap_h + crown_h*0.06, crown_h, mat=1)
    return bm_to_obj(bm, "mod_crown_c")


# ===========================================================================
# GROUND (kept) — the grand deco lobby, single variant
# ===========================================================================

def ground_a(floor_h=GROUND_H):
    """Grand deco lobby: tall window bay + bronze base band (the kept ground module)."""
    bm = bmesh.new()
    gx0, gx1 = _window_piers(bm, floor_h)
    spand_h = floor_h * 0.16
    gz0, gz1 = 0.0, floor_h - spand_h
    box(bm, gx0, gx1, -HALF_D + 9.0, HALF_D, gz0, gz1, mat=0)
    for mx in (gx0 + (gx1-gx0)*0.33, gx0 + (gx1-gx0)*0.66):
        box(bm, mx - 4, mx + 4, -HALF_D + 6, -HALF_D + 9.0, gz0 + 6, gz1 - 6, mat=1)
    for hz in (gz0 + (gz1-gz0)*0.5, gz0 + (gz1-gz0)*0.82):
        box(bm, gx0 + 6, gx1 - 6, -HALF_D + 6, -HALF_D + 9.0, hz - 4, hz + 4, mat=1)
    # tall bronze base band (grand lobby)
    box(bm, gx0, gx1, -HALF_D + 4.0, -HALF_D + 9.0, 0, floor_h * 0.18, mat=1)
    # sunburst over the lobby lintel
    sunburst(bm, 0.0, gz1 + 4, radius=(gx1-gx0)*0.4, h=spand_h*0.8, n_rays=9, mat=1)
    return bm_to_obj(bm, "mod_ground_a")


# ---------------------------------------------------------------------------
# render preview
# ---------------------------------------------------------------------------

def setup_render(res_x=720, res_y=820):
    scene = bpy.context.scene
    engines = [e.identifier for e in
               bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    scene.render.resolution_x = res_x
    scene.render.resolution_y = res_y
    scene.render.film_transparent = False
    try:
        scene.view_settings.view_transform = "Standard"
    except Exception:
        pass
    if scene.world is None:
        scene.world = bpy.data.worlds.new("W")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.16, 0.15, 0.14, 1.0)
        bg.inputs[1].default_value = 1.3


def add_cam_and_lights(floor_h):
    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam_data.lens = 55
    cam_data.clip_start = 1.0
    cam_data.clip_end = 1.0e6
    extent = max(HALF_W * 2, floor_h)
    dist = extent * 2.0
    cam.location = (dist * 0.95, -dist * 0.95, floor_h * 0.58 + extent * 0.18)
    target = mathutils.Vector((0, 0, floor_h * 0.5))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam

    key = bpy.data.lights.new("Key", "SUN")
    key.energy = 4.0
    key.color = (1.0, 0.95, 0.85)
    ko = bpy.data.objects.new("Key", key)
    ko.rotation_euler = (math.radians(52), math.radians(12), math.radians(35))
    bpy.context.collection.objects.link(ko)
    rim = bpy.data.lights.new("Rim", "SUN")
    rim.energy = 2.0
    rim.color = (0.85, 0.78, 0.65)
    ro = bpy.data.objects.new("Rim", rim)
    ro.rotation_euler = (math.radians(62), 0, math.radians(215))
    bpy.context.collection.objects.link(ro)


def export_fbx(obj, fname):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    fbx = os.path.join(ROOT, fname + ".fbx")
    bpy.ops.export_scene.fbx(
        filepath=fbx, use_selection=True,
        apply_scale_options="FBX_SCALE_ALL", apply_unit_scale=True,
        global_scale=1.0,
        object_types={"MESH"}, mesh_smooth_type="FACE",
        use_mesh_modifiers=True, bake_space_transform=True,
        axis_forward="-Z", axis_up="Y",
    )
    return fbx


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

# (file, symbol, desc, builder, floor_h_for_bounds)
VARIANTS = [
    ("mod_wall_a",   "W",     "Plain pier (center pilaster, quiet bay)",            lambda: wall_a(),   FLOOR_H),
    ("mod_wall_b",   "W",     "Fluted pier (6 proud flutes, bronze reveals)",       lambda: wall_b(),   FLOOR_H),
    ("mod_wall_c",   "W",     "Chevron-spandrel (stacked zigzag central panel)",    lambda: wall_c(),   FLOOR_H),
    ("mod_wall_d",   "W",     "Geometric-relief (concentric frozen-fountain inset)",lambda: wall_d(),   FLOOR_H),
    ("mod_window_a", "W1/W2", "Vertical ribbon window (single tall glazing)",       lambda: window_a(), FLOOR_H),
    ("mod_window_b", "W1/W2", "Window + metal grille (mullions+bars+chevron top)",  lambda: window_b(), FLOOR_H),
    ("mod_window_c", "W1/W2", "Stepped-spandrel window (ziggurat spandrel top)",    lambda: window_c(), FLOOR_H),
    ("mod_window_d", "W1/W2", "Window + sunburst motif (Deco sunrise over lintel)", lambda: window_d(), FLOOR_H),
    ("mod_corner_a", "C",     "Plain quoin (clean corner pier, single cap band)",   lambda: corner_a(), FLOOR_H),
    ("mod_corner_b", "C",     "Stepped/chamfered quoin (3 setbacks + flutes)",      lambda: corner_b(), FLOOR_H),
    ("mod_crown_a",  "CROWN", "Ziggurat step (5 setbacks + spire + sunburst)",      lambda: crown_a(),  CROWN_H),
    ("mod_crown_b",  "CROWN", "Spire-top (Chrysler needle, tiered bronze spire)",   lambda: crown_b(),  CROWN_H),
    ("mod_crown_c",  "CROWN", "Fluted cap (parapet + vertical flutes + cornice)",   lambda: crown_c(),  CROWN_H),
    ("mod_ground_a", "ground W1", "Grand deco lobby (tall glazing + base band + sunburst)", lambda: ground_a(), GROUND_H),
]

# FBX UNIT FIX (the iter4 lesson): cm scene unit -> FBX carries cm -> UE 1:1.
us = bpy.context.scene.unit_settings
us.system = "METRIC"
us.scale_length = 0.01
us.length_unit = "CENTIMETERS"

results = []
setup_render()

for fname, symbol, desc, builder, fh in VARIANTS:
    reset_scene()
    setup_render()
    stone, bronze = make_mats()
    obj = builder()
    finalize(obj, fname, stone, bronze)
    b = verify_bounds(obj, fname, exp_floor_h=fh)

    me = obj.data
    me.calc_loop_triangles()
    tris = len(me.loop_triangles)

    add_cam_and_lights(fh)
    png = os.path.join(ROOT, fname + ".png")
    bpy.context.scene.render.filepath = png
    bpy.ops.render.render(write_still=True)

    fbx = export_fbx(obj, fname)
    results.append({"file": fname, "symbol": symbol, "desc": desc,
                    "tris": tris, "bounds": b, "floor_h": fh})
    print(f"DONE {fname} [{symbol}]: {desc} | tris={tris} -> {fbx}")

with open(os.path.join(ROOT, "_stats.json"), "w") as f:
    json.dump(results, f, indent=2)

# fail summary
fails = [r["file"] for r in results if r["bounds"]["status"] != "OK"]
print("ALL VARIANTS DONE:", len(results), "| FAILS:", fails if fails else "none")
