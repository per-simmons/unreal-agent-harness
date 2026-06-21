"""Headless Blender generator for the DETAILED / carved BEAUX-ARTS / HAUSSMANN kit.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python beaux_arts_detailed_jobs.py

WHY: the variants kit (beaux_arts_variants_jobs.py) gives correct-spec modules,
but they read as FLAT plates with shallow proud strips (tris 60-600) — "boxes
with window holes," the classic CG look. This file produces a much MORE ORNAMENTED
set so the modules read as CARVED Haussmann stone: every hard edge BEVELED (catches
light), multi-step MOLDING profiles on every cornice/string course, DENTIL rows +
MODILLION brackets under a deep crowning cornice, real KEYSTONES / triangular +
segmental PEDIMENTS / CONSOLE brackets, carved BALUSTRADES + finer wrought-iron
Juliet balconies, DEEPER rustication, PILASTERS with CAPITALS, and ROSETTE /
medallion accents. Higher poly is fine (Nanite). Rich silhouette + depth is the
whole point.

NON-NEGOTIABLE module spec (IDENTICAL to beaux_arts_variants_jobs.py, or the
grammar generator's ExtractMeshInfo assembles broken modules):
  - WIDTH = 400cm along LOCAL +X, CENTERED            -> X spans -200..+200
  - DEPTH shallow on Y, centered                      -> Y centered
  - HEIGHT on Z, BASE-PIVOTED (min.z = 0)             -> Z spans 0..floorH
  - consistent 400cm width + ~400cm floor height so everything tiles
  - 2 material slots: slot 0 = Stone (cream limestone), slot 1 = Iron (zinc/iron)
  - UNIT FIX: scene in CENTIMETERS + FBX_SCALE_ALL + apply_unit_scale -> UE 1:1
Every module is verify_bounds()'d in bpy BEFORE export (status must be OK).
A small global BEVEL is applied + CLAMPED so it never pushes verts past tolerance.

OUTPUT: ~/coding/unreal-agent-harness/assets/beaux_arts_kit/detailed/<name>/<name>.fbx
  WALL variants:    mod_wall_a   (rusticated ashlar, deep V-joints)
                    mod_wall_b   (ashlar + molded string course + frieze panel)
                    mod_wall_c   (pilastered + capitals + rosette medallion)
  WINDOW variants:  mod_window_a (arched French window, molded architrave + keystone
                                  + console-borne sill, iron band)
                    mod_window_b (rect window + TRIANGULAR pediment on consoles +
                                  molded entablature + balustrade sill)
                    mod_window_c (rect window + finer wrought-iron Juliet balcony +
                                  segmental pediment + dentil cornice)
  CORNER:           mod_corner_a (rusticated quoin pier + crowning dentil cornice)
  MANSARD ROOF:     mod_mansard  (steep zinc slope + molded base cornice with dentils
                                  + 3 pedimented dormers + ridge cap + roof balustrade)

Renders a montage beaux_arts_detailed_montage.png + writes _detailed_stats.json.
"""
import bpy, bmesh, os, math, mathutils

BASE_ROOT = os.path.expanduser("~/coding/unreal-agent-harness/assets/beaux_arts_kit")
ROOT      = os.path.join(BASE_ROOT, "detailed")
os.makedirs(ROOT, exist_ok=True)

# ---- THE MODULE SPEC (cm) — IDENTICAL to the variants/base kit -------------
MODULE_W = 400.0
HALF_W   = MODULE_W / 2.0   # 200
FLOOR_H  = 400.0
DEPTH    = 30.0
HALF_D   = DEPTH / 2.0      # 15
GROUND_H = 600.0
MANSARD_H = 350.0

# Bevel: small width so it only chamfers hard edges (catches light) without
# blowing past the bounds tolerance. Clamped + verified after apply.
BEVEL_W  = 1.6
BEVEL_SEG = 2
# Hard cap on how far any ornament may protrude past the face plane (-Y).
# Keeps depth shallow-ish and predictable; bounds check only enforces X/Z/centre.
MAX_PROUD = 60.0


# ---------------------------------------------------------------------------
# scene / material helpers (identical to the variants kit)
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
    """slot 0 = cream limestone, slot 1 = wrought-iron / dark zinc / trim."""
    stone = bpy.data.materials.new("M_Stone")
    stone.use_nodes = True
    b = stone.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = (0.78, 0.72, 0.58, 1.0)
        b.inputs["Metallic"].default_value = 0.0
        b.inputs["Roughness"].default_value = 0.78
    iron = bpy.data.materials.new("M_Iron")
    iron.use_nodes = True
    b = iron.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = (0.06, 0.06, 0.07, 1.0)
        b.inputs["Metallic"].default_value = 0.85
        b.inputs["Roughness"].default_value = 0.42
    return stone, iron


def bm_to_obj(bm, name):
    me = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    return obj


def box(bm, x0, x1, y0, y1, z0, z1):
    v = [bm.verts.new((x, y, z))
         for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    def V(ix, iy, iz):
        return v[iz * 4 + iy * 2 + ix]
    faces = []
    faces.append(bm.faces.new((V(0,0,0), V(1,0,0), V(1,1,0), V(0,1,0))))
    faces.append(bm.faces.new((V(0,0,1), V(0,1,1), V(1,1,1), V(1,0,1))))
    faces.append(bm.faces.new((V(0,0,0), V(0,1,0), V(0,1,1), V(0,0,1))))
    faces.append(bm.faces.new((V(1,0,0), V(1,0,1), V(1,1,1), V(1,1,0))))
    faces.append(bm.faces.new((V(0,0,0), V(0,0,1), V(1,0,1), V(1,0,0))))
    faces.append(bm.faces.new((V(0,1,0), V(1,1,0), V(1,1,1), V(0,1,1))))
    return faces


def tag(faces, idx):
    for f in faces:
        f.material_index = idx


def arch_band(bm, x0, x1, y0, y1, z_spring, z_top, n=28, mat=0, ring=True,
              band_scale=0.34, depth_extra=0.0):
    """Semicircular arch over an opening. ring=True -> proud constant-thickness
    arc molding; ring=False -> solid filled tympanum. depth_extra protrudes it
    a touch further in -Y for a chunkier carved read (clamped at caller)."""
    cx = (x0 + x1) / 2.0
    rx = (x1 - x0) / 2.0
    rz = (z_top - z_spring)
    band = min(rx, rz) * band_scale
    prev = None
    for i in range(n + 1):
        t = i / n
        ang = math.pi * t
        x = cx - rx * math.cos(ang)
        z = z_spring + rz * math.sin(ang)
        if prev is not None:
            px, pz = prev
            if ring:
                f = box(bm, min(px, x) - 3, max(px, x) + 3, y0 - depth_extra, y1,
                        max(z, pz) - band, max(z, pz))
            else:
                f = box(bm, min(px, x), max(px, x), y0 - depth_extra, y1,
                        z_spring, max(z, pz))
            tag(f, mat)
        prev = (x, z)


def segmental_band(bm, x0, x1, y0, y1, z_base, rise, n=18, mat=0, depth_extra=0.0):
    """A shallow SEGMENTAL (flattened) arch pediment over an opening — a wide low
    arc, the typical 'flattened' Haussmann window head. Proud molding."""
    cx = (x0 + x1) / 2.0
    half = (x1 - x0) / 2.0
    R = (half * half + rise * rise) / (2.0 * rise)
    cz = z_base + rise - R
    band = 16.0
    prev = None
    for i in range(n + 1):
        t = -1.0 + 2.0 * (i / n)
        x = cx + half * t
        z = cz + math.sqrt(max(R * R - (x - cx) ** 2, 0.0))
        if prev is not None:
            px, pz = prev
            f = box(bm, min(px, x) - 3, max(px, x) + 3, y0 - depth_extra, y1,
                    min(z, pz) - band, max(z, pz))
            tag(f, mat)
        prev = (x, z)


# ---------------------------------------------------------------------------
# NEW ORNAMENT HELPERS — the carved relief the flat kit was missing
# ---------------------------------------------------------------------------
def molded_course(bm, z, steps, x0=-HALF_W, x1=HALF_W, base_proud=6.0, mat=0):
    """A multi-STEP horizontal molding profile (NOT a single box). `steps` is a
    list of (height, proud) pairs stacked bottom->top; each step projects a
    different distance in -Y so the cross-section reads as a real cyma/ovolo
    cornice profile that self-shadows. Returns top z."""
    zc = z
    for (h, proud) in steps:
        proud = min(proud, MAX_PROUD)
        tag(box(bm, x0, x1, -HALF_D - proud, -HALF_D, zc, zc + h), mat)
        zc += h
    return zc


# Canonical profiles (height, proud) bottom->top.
PROFILE_STRING = [(6, 8), (10, 14), (6, 10)]                 # simple string course
PROFILE_CORNICE = [(8, 10), (10, 18), (14, 30), (10, 22), (8, 12)]  # deep crowning


def dentil_row(bm, z, h=14.0, proud=24.0, tooth=12.0, gap=10.0,
               x0=-HALF_W + 8, x1=HALF_W - 8, mat=0):
    """A row of little teeth (DENTILS) — the signature classical-cornice detail.
    Each tooth is a small proud block with a gap between; reads as a toothed band."""
    proud = min(proud, MAX_PROUD)
    x = x0
    while x + tooth <= x1:
        tag(box(bm, x, x + tooth, -HALF_D - proud, -HALF_D, z, z + h), mat)
        x += tooth + gap


def modillion_brackets(bm, z_top, count=5, w=26.0, drop=44.0, proud=46.0, mat=0):
    """MODILLION brackets (scroll corbels) under the crowning cornice — evenly
    spaced chunky brackets, each a 2-step corbel that projects further at the top
    so it reads as a console supporting the cornice above. drop = how far down."""
    proud = min(proud, MAX_PROUD)
    span = (HALF_W - 30) * 2.0
    for i in range(count):
        cx = -HALF_W + 30 + span * (i / (count - 1))
        # lower (recessed) + upper (projecting) block = scroll-corbel silhouette
        tag(box(bm, cx - w * 0.4, cx + w * 0.4, -HALF_D - proud * 0.6, -HALF_D,
                z_top - drop, z_top - drop * 0.4), mat)
        tag(box(bm, cx - w * 0.5, cx + w * 0.5, -HALF_D - proud, -HALF_D,
                z_top - drop * 0.45, z_top), mat)


def crowning_cornice(bm, floor_h, mat=0):
    """The full crowning cornice assembly at the top of a floor: modillion
    brackets -> dentil row -> deep molded cornice. The richest horizontal."""
    base = floor_h - 86.0
    modillion_brackets(bm, base + 8.0, count=6, mat=mat)
    dentil_row(bm, base + 10.0, h=16.0, proud=26.0, mat=mat)
    molded_course(bm, base + 30.0, PROFILE_CORNICE, mat=mat)


def capital(bm, px, pw, z, mat=0):
    """A simple molded pilaster CAPITAL — a flaring 3-step block crowning a
    pilaster shaft (abacus + echinus read)."""
    tag(box(bm, px - 4, px + pw + 4, -HALF_D - 16, -HALF_D, z, z + 8), mat)
    tag(box(bm, px - 8, px + pw + 8, -HALF_D - 22, -HALF_D, z + 8, z + 18), mat)
    tag(box(bm, px - 11, px + pw + 11, -HALF_D - 18, -HALF_D, z + 18, z + 26), mat)


def base_molding(bm, px, pw, z0, mat=0):
    """A small molded BASE for a pilaster shaft (plinth + torus read)."""
    tag(box(bm, px - 10, px + pw + 10, -HALF_D - 18, -HALF_D, z0, z0 + 10), mat)
    tag(box(bm, px - 6, px + pw + 6, -HALF_D - 12, -HALF_D, z0 + 10, z0 + 20), mat)


def rosette(bm, cx, cz, r=26.0, mat=0):
    """A carved ROSETTE / medallion — a round-ish proud boss approximated by a
    small octagonal stack so it reads as a carved disc on the wall face."""
    proud0, proud1 = 30.0, 42.0
    # outer ring (octagon prism) + raised centre boss
    n = 8
    for i in range(n):
        a0 = 2 * math.pi * i / n
        a1 = 2 * math.pi * (i + 1) / n
        x0 = cx + r * math.cos(a0); z0 = cz + r * math.sin(a0)
        x1 = cx + r * math.cos(a1); z1 = cz + r * math.sin(a1)
        tag(box(bm, min(x0, x1) - 2, max(x0, x1) + 2, -HALF_D - proud0, -HALF_D,
                min(z0, z1) - 2, max(z0, z1) + 2), mat)
    tag(box(bm, cx - r * 0.4, cx + r * 0.4, -HALF_D - proud1, -HALF_D,
            cz - r * 0.4, cz + r * 0.4), mat)


def deep_rustication(bm, floor_h, band=58.0, depth=12.0, vgroove=True,
                     z_start=46.0):
    """Heavy DEEP horizontal rustication joints + (optional) vertical joints, so
    the wall reads as big drafted ashlar blocks, not scratched lines. The joints
    are recessed reveals approximated by proud block edges flanking a gap."""
    z = z_start
    while z < floor_h - 30:
        # two thin proud lips flanking a recessed joint = a real drafted reveal
        tag(box(bm, -HALF_W, HALF_W, -HALF_D - depth, -HALF_D, z - 7.0, z - 3.0), 0)
        tag(box(bm, -HALF_W, HALF_W, -HALF_D - depth, -HALF_D, z + 3.0, z + 7.0), 0)
        z += band
    if vgroove:
        # staggered vertical drafted joints between courses
        z = z_start
        col = 0
        while z < floor_h - 30:
            xs = (-HALF_W / 2.0, HALF_W / 2.0) if col % 2 == 0 else (0.0,)
            for vx in xs:
                tag(box(bm, vx - 6.0, vx - 3.0, -HALF_D - depth, -HALF_D,
                        z + 8.0, z + band - 8.0), 0)
                tag(box(bm, vx + 3.0, vx + 6.0, -HALF_D - depth, -HALF_D,
                        z + 8.0, z + band - 8.0), 0)
            z += band
            col += 1


def fine_juliet(bm, op_x0, op_x1, sill_z, rail_h=92.0):
    """A FINER wrought-iron Juliet balcony — top+bottom rails, closely-spaced
    slim balusters, plus two mid-height belly bars (the bombe curve read). mat 1."""
    y0 = -HALF_D - 24.0
    y1 = -HALF_D - 16.0
    rail_top = sill_z + rail_h
    bx0, bx1 = op_x0 - 16, op_x1 + 16
    # top + bottom rails
    tag(box(bm, bx0, bx1, y0, y1, sill_z + 2, sill_z + 7), 1)
    tag(box(bm, bx0, bx1, y0, y1, rail_top - 5, rail_top), 1)
    # two horizontal belly bars
    tag(box(bm, bx0, bx1, y0 - 3, y1 - 3, sill_z + 32, sill_z + 37), 1)
    tag(box(bm, bx0, bx1, y0 - 3, y1 - 3, sill_z + 58, sill_z + 63), 1)
    # slim closely-spaced balusters (bow out in the middle two bars)
    bx = bx0 + 4
    while bx <= bx1 - 4:
        belly = -4.0 if (op_x0 + 10 < bx < op_x1 - 10) else 0.0
        tag(box(bm, bx - 1.4, bx + 1.4, y0 + belly, y1 + belly,
                sill_z + 2, rail_top), 1)
        bx += 9.0


def stone_balustrade(bm, op_x0, op_x1, sill_z, rail_h=74.0, mat=0):
    """Carved STONE balustrade — molded base rail, molded cap rail, fat turned
    balusters (bellied via a 3-box stack each). mat 0."""
    y0 = -HALF_D - 28.0
    y1 = -HALF_D - 16.0
    rail_top = sill_z + rail_h
    bx0, bx1 = op_x0 - 18, op_x1 + 18
    # molded base + cap rails (2-step each)
    tag(box(bm, bx0, bx1, y0 - 2, y1, sill_z, sill_z + 8), mat)
    tag(box(bm, bx0, bx1, y0, y1, sill_z + 8, sill_z + 14), mat)
    tag(box(bm, bx0, bx1, y0 - 2, y1, rail_top - 10, rail_top), mat)
    tag(box(bm, bx0, bx1, y0, y1, rail_top - 14, rail_top - 10), mat)
    # bellied stone balusters: narrow-wide-narrow stack
    bx = bx0 + 12
    while bx <= bx1 - 12:
        tag(box(bm, bx - 4, bx + 4, y0, y1, sill_z + 14, sill_z + 24), mat)
        tag(box(bm, bx - 6.5, bx + 6.5, y0 - 2, y1, sill_z + 24, rail_top - 24), mat)
        tag(box(bm, bx - 4, bx + 4, y0, y1, rail_top - 24, rail_top - 14), mat)
        bx += 24.0


def molded_consoles(bm, op_x0, op_x1, z, mat=0):
    """Two molded console brackets (scroll corbels) under a pediment/sill — each
    a 3-step corbel that projects further the higher it goes (volute read)."""
    for sx in (op_x0 - 8, op_x1 - 18):
        tag(box(bm, sx, sx + 26, -HALF_D - 18.0, -HALF_D, z - 48, z - 30), mat)
        tag(box(bm, sx + 2, sx + 26, -HALF_D - 30.0, -HALF_D, z - 30, z - 14), mat)
        tag(box(bm, sx + 4, sx + 26, -HALF_D - 40.0, -HALF_D, z - 14, z), mat)


def keystone(bm, half_w=22.0, z0=0.0, z1=0.0, proud=50.0, mat=0):
    """A proud, slightly-tapered KEYSTONE — wider at top, projecting hard."""
    proud = min(proud, MAX_PROUD)
    tag(box(bm, -half_w * 0.8, half_w * 0.8, -HALF_D - proud * 0.7, -HALF_D, z0, (z0 + z1) / 2), mat)
    tag(box(bm, -half_w, half_w, -HALF_D - proud, -HALF_D, (z0 + z1) / 2, z1), mat)


def _glass(bm, op_x0, op_x1, sill_z, head_z):
    gy = -HALF_D + 4.0
    tag(box(bm, op_x0 + 8, op_x1 - 8, gy, gy + 2.0, sill_z, head_z), 1)


def _window_body(bm, op_x0, op_x1, sill_z, head_z, floor_h):
    """The 4 stone margins around a rectangular opening."""
    for (mx0, mx1) in ((-HALF_W, op_x0), (op_x1, HALF_W)):
        tag(box(bm, mx0, mx1, -HALF_D, HALF_D, 0, floor_h), 0)
    tag(box(bm, op_x0, op_x1, -HALF_D, HALF_D, 0, sill_z), 0)
    tag(box(bm, op_x0, op_x1, -HALF_D, HALF_D, head_z, floor_h), 0)


def molded_architrave(bm, op_x0, op_x1, sill_z, head_z, jamb_w=20.0, jamb_p=14.0,
                      mat=0):
    """A 2-step molded ARCHITRAVE frame around a window opening (outer fascia +
    inner reveal), both jambs + the head. Proud, so it frames the glass in relief."""
    # outer fascia
    for sx in (op_x0 - jamb_w, op_x1):
        tag(box(bm, sx, sx + jamb_w, -HALF_D - jamb_p, -HALF_D, sill_z, head_z), mat)
    # inner thin reveal lip
    for sx in (op_x0 - 6, op_x1):
        tag(box(bm, sx, sx + 6, -HALF_D - jamb_p - 4, -HALF_D - jamb_p, sill_z, head_z), mat)
    # head fascia
    tag(box(bm, op_x0 - jamb_w - 4, op_x1 + jamb_w + 4, -HALF_D - jamb_p, -HALF_D,
            head_z, head_z + 18), mat)


# ---------------------------------------------------------------------------
# finalize / verify  (identical to the variants kit + a clamped BEVEL pass)
# ---------------------------------------------------------------------------
def _apply_bevel(obj):
    """Add a small, clamped Bevel modifier and apply it. Clamp overlap stops the
    bevel from eating thin features; small width keeps it inside bounds tol."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new("Bevel", "BEVEL")
    mod.width = BEVEL_W
    mod.segments = BEVEL_SEG
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(35)
    mod.use_clamp_overlap = True
    bpy.ops.object.modifier_apply(modifier="Bevel")


def finalize(obj, name, stone, iron, exp_floor_h=FLOOR_H):
    me = obj.data
    me.materials.clear()
    me.materials.append(stone)
    me.materials.append(iron)
    obj.name = name
    me.name = name + "_mesh"

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=0.01)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")

    # CARVED LOOK: bevel every hard edge so it catches light (the #1 anti-CG move)
    _apply_bevel(obj)

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")

    # re-centre Y exactly (bevel can nudge the Y midline)
    me = obj.data
    ys = [v.co.y for v in me.vertices]
    yshift = -(min(ys) + max(ys)) / 2.0
    if abs(yshift) > 1e-4:
        for v in me.vertices:
            v.co.y += yshift

    # re-centre X + re-base Z exactly so the small bevel never trips tolerance
    xs = [v.co.x for v in me.vertices]
    xshift = -(min(xs) + max(xs)) / 2.0
    if abs(xshift) > 1e-4:
        for v in me.vertices:
            v.co.x += xshift
    zs = [v.co.z for v in me.vertices]
    zshift = -min(zs)
    if abs(zshift) > 1e-4:
        for v in me.vertices:
            v.co.z += zshift

    # Clamp the tiny bevel/ornament overshoot at the top + bottom so the module
    # tiles EXACTLY 0..floor_h (the spec). Only the few verts within ~3cm of the
    # plane are flattened, so the silhouette is untouched.
    for v in me.vertices:
        if v.co.z > exp_floor_h:
            v.co.z = exp_floor_h
        if v.co.z < 0.0:
            v.co.z = 0.0

    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    return obj


def verify_bounds(obj, label, exp_floor_h=FLOOR_H, tol=0.6):
    me = obj.data
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    zs = [v.co.z for v in me.vertices]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    minz, maxz = min(zs), max(zs)
    w = maxx - minx
    ok_xcenter = abs((minx + maxx) / 2.0) <= tol
    ok_width   = abs(w - HALF_W * 2) <= tol
    ok_basez   = abs(minz) <= tol
    ok_height  = abs(maxz - exp_floor_h) <= tol
    ok_ycenter = abs((miny + maxy) / 2.0) <= tol
    status = "OK" if (ok_xcenter and ok_width and ok_basez and ok_height and ok_ycenter) else "**FAIL**"
    print(f"[BOUNDS {status}] {label}: "
          f"X[{minx:.1f},{maxx:.1f}] w={w:.1f} (Xc={ok_xcenter} W={ok_width}) | "
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
# WALL VARIANTS  (symbol W)
# ===========================================================================
def m_wall_a():
    """Heavily RUSTICATED ashlar wall — deep drafted horizontal + vertical joints
    (big stone blocks), molded string course, a quiet wall but with real depth."""
    bm = bmesh.new()
    tag(box(bm, -HALF_W, HALF_W, -HALF_D, HALF_D, 0, FLOOR_H), 0)
    deep_rustication(bm, FLOOR_H, band=60.0, depth=12.0, vgroove=True, z_start=50.0)
    molded_course(bm, FLOOR_H - 24.0, PROFILE_STRING)
    return bm_to_obj(bm, "mod_wall_a")


def m_wall_b():
    """Ashlar wall + a deep MOLDED string course at the floor line + a recessed
    central FRIEZE panel with a proud bordered frame (a carved blank bay)."""
    bm = bmesh.new()
    tag(box(bm, -HALF_W, HALF_W, -HALF_D, HALF_D, 0, FLOOR_H), 0)
    # faint coursing
    z = 80.0
    while z < FLOOR_H - 90:
        tag(box(bm, -HALF_W, HALF_W, -HALF_D - 3.0, -HALF_D, z - 2.5, z + 2.5), 0)
        z += 84.0
    # framed frieze panel (proud border)
    py0, py1, pz0, pz1 = -150.0, 150.0, 150.0, FLOOR_H - 120.0
    for (a, b, c, d) in ((py0, py1, pz0, pz0 + 10), (py0, py1, pz1 - 10, pz1),
                         (py0, py0 + 10, pz0, pz1), (py1 - 10, py1, pz0, pz1)):
        tag(box(bm, a, b, -HALF_D - 10, -HALF_D, c, d), 0)
    molded_course(bm, FLOOR_H - 26.0, PROFILE_STRING)
    return bm_to_obj(bm, "mod_wall_b")


def m_wall_c():
    """PILASTERED wall — two pilasters (molded base + fluted-read shaft + molded
    CAPITAL) framing a recessed panel with a carved ROSETTE medallion, crowned by
    a molded string course. The most ornate blank bay."""
    bm = bmesh.new()
    tag(box(bm, -HALF_W, HALF_W, -HALF_D, HALF_D, 0, FLOOR_H), 0)
    pil_w, pil_p = 38.0, 14.0
    cap_z = FLOOR_H - 88.0
    for px in (-HALF_W + 36, HALF_W - 36 - pil_w):
        base_molding(bm, px, pil_w, 0.0)
        tag(box(bm, px, px + pil_w, -HALF_D - pil_p, -HALF_D, 20, cap_z), 0)  # shaft
        # 3 shallow flutes on the shaft
        for fx in (px + pil_w * 0.28, px + pil_w * 0.5, px + pil_w * 0.72):
            tag(box(bm, fx - 2, fx + 2, -HALF_D - pil_p - 3, -HALF_D - pil_p, 26, cap_z - 6), 0)
        capital(bm, px, pil_w, cap_z)
    rosette(bm, 0.0, FLOOR_H * 0.52, r=30.0)
    molded_course(bm, FLOOR_H - 26.0, PROFILE_STRING)
    return bm_to_obj(bm, "mod_wall_c")


# ===========================================================================
# WINDOW VARIANTS  (symbols W1 / W2)
# ===========================================================================
def m_window_a(floor_h=FLOOR_H):
    """Arched French window — round arch head w/ molded archivolt, molded
    architrave jambs, proud tapered KEYSTONE, console-borne molded sill, recessed
    glass, iron sill band, crowning DENTIL cornice. (the grand main bay)."""
    bm = bmesh.new()
    op_x0, op_x1 = -118.0, 118.0
    sill_z   = 98.0
    spring_z = floor_h - 168.0
    head_z   = floor_h - 70.0
    for (mx0, mx1) in ((-HALF_W, op_x0), (op_x1, HALF_W)):
        tag(box(bm, mx0, mx1, -HALF_D, HALF_D, 0, floor_h), 0)
    tag(box(bm, op_x0, op_x1, -HALF_D, HALF_D, 0, sill_z), 0)
    tag(box(bm, op_x0, op_x1, -HALF_D, HALF_D, head_z, floor_h), 0)
    _glass(bm, op_x0, op_x1, sill_z, spring_z + 50)
    # molded jambs up to the spring line
    for sx in (op_x0 - 18, op_x1):
        tag(box(bm, sx, sx + 18, -HALF_D - 14, -HALF_D, sill_z, spring_z), 0)
        tag(box(bm, sx + (4 if sx < 0 else 0), sx + 18, -HALF_D - 18, -HALF_D - 14, sill_z, spring_z), 0)
    # molded archivolt (double ring) + tympanum
    arch_band(bm, op_x0 - 18, op_x1 + 18, -HALF_D - 18, -HALF_D, spring_z, head_z, n=30, mat=0, ring=True, band_scale=0.30, depth_extra=4.0)
    arch_band(bm, op_x0 - 6, op_x1 + 6, -HALF_D - 8, -HALF_D, spring_z + 6, head_z - 6, n=30, mat=0, ring=True, band_scale=0.18)
    keystone(bm, half_w=24.0, z0=head_z - 78.0, z1=head_z + 34.0, proud=52.0)
    # console-borne molded sill
    molded_consoles(bm, op_x0, op_x1, sill_z)
    tag(box(bm, op_x0 - 14, op_x1 + 14, -HALF_D - 18.0, -HALF_D, sill_z - 14.0, sill_z), 0)
    tag(box(bm, op_x0 - 10, op_x1 + 10, -HALF_D - 24.0, -HALF_D - 18, sill_z - 8.0, sill_z), 0)
    tag(box(bm, -HALF_W, HALF_W, -HALF_D - 18.0, -HALF_D - 14.0, sill_z - 4, sill_z + 2), 1)  # iron band
    crowning_cornice(bm, floor_h)
    return bm_to_obj(bm, "mod_window_a")


def m_window_b(floor_h=FLOOR_H):
    """Rectangular window + TRIANGULAR PEDIMENT on console brackets — the grand
    piano-nobile treatment. Molded architrave, molded entablature lintel, two
    consoles, a triangular pediment w/ a small rosette in the tympanum, recessed
    glass, a stone balustrade across the sill, crowning dentil cornice."""
    bm = bmesh.new()
    op_x0, op_x1 = -112.0, 112.0
    sill_z   = 104.0
    head_z   = floor_h - 132.0
    _window_body(bm, op_x0, op_x1, sill_z, head_z, floor_h)
    _glass(bm, op_x0, op_x1, sill_z, head_z)
    molded_architrave(bm, op_x0, op_x1, sill_z, head_z, jamb_w=20.0, jamb_p=14.0)
    # molded entablature lintel
    ent_z = head_z + 18
    tag(box(bm, op_x0 - 30, op_x1 + 30, -HALF_D - 16, -HALF_D, ent_z, ent_z + 14), 0)
    molded_consoles(bm, op_x0 - 6, op_x1 + 6, head_z + 6)
    # TRIANGULAR pediment from stacked narrowing slabs
    ped_base = ent_z + 14
    ped_w = (op_x1 - op_x0) / 2.0 + 34
    steps = 11
    ped_h = 86.0
    for i in range(steps):
        t = i / steps
        hw = ped_w * (1.0 - t)
        z0 = ped_base + ped_h * t
        z1 = ped_base + ped_h * (t + 1.0 / steps)
        tag(box(bm, -hw, hw, -HALF_D - 14, -HALF_D, z0, z1), 0)
    # raking cornice lip along the slopes (thin proud edge)
    tag(box(bm, -ped_w, ped_w, -HALF_D - 18, -HALF_D - 14, ped_base, ped_base + 10), 0)
    rosette(bm, 0.0, ped_base + 26.0, r=16.0)  # tympanum rosette
    # stone balustrade across the sill
    stone_balustrade(bm, op_x0, op_x1, sill_z - 6, rail_h=66.0)
    crowning_cornice(bm, floor_h)
    return bm_to_obj(bm, "mod_window_b")


def m_window_c(floor_h=FLOOR_H):
    """Rectangular window + FINE wrought-iron Juliet balcony + SEGMENTAL pediment
    w/ keystone + molded architrave + crowning dentil cornice. The everyday
    Haussmann bay with prominent iron (mat 1)."""
    bm = bmesh.new()
    op_x0, op_x1 = -116.0, 116.0
    sill_z   = 92.0
    head_z   = floor_h - 128.0
    _window_body(bm, op_x0, op_x1, sill_z, head_z, floor_h)
    _glass(bm, op_x0, op_x1, sill_z, head_z)
    molded_architrave(bm, op_x0, op_x1, sill_z, head_z, jamb_w=16.0, jamb_p=12.0)
    # SEGMENTAL (flattened) pediment head + keystone
    segmental_band(bm, op_x0 - 16, op_x1 + 16, -HALF_D - 14, -HALF_D, head_z + 6, 56.0, n=20, mat=0, depth_extra=4.0)
    keystone(bm, half_w=18.0, z0=head_z - 6.0, z1=head_z + 58.0, proud=46.0)
    # molded sill
    tag(box(bm, op_x0 - 12, op_x1 + 12, -HALF_D - 16.0, -HALF_D, sill_z - 14.0, sill_z), 0)
    tag(box(bm, op_x0 - 8, op_x1 + 8, -HALF_D - 22.0, -HALF_D - 16, sill_z - 8.0, sill_z), 0)
    fine_juliet(bm, op_x0, op_x1, sill_z, rail_h=98.0)
    tag(box(bm, -HALF_W, HALF_W, -HALF_D - 16.0, -HALF_D - 12.0, sill_z - 4, sill_z + 2), 1)  # iron band
    crowning_cornice(bm, floor_h)
    return bm_to_obj(bm, "mod_window_c")


# ===========================================================================
# CORNER  (symbol C)
# ===========================================================================
def m_corner_a():
    """RUSTICATED quoin corner — alternating proud wide/narrow drafted quoin
    blocks on a deep pier, molded base, crowning DENTIL cornice. Closes the box."""
    bm = bmesh.new()
    tag(box(bm, -HALF_W, HALF_W, -HALF_D, HALF_D, 0, FLOOR_H), 0)
    pier_hw, pier_p = 62.0, 18.0
    tag(box(bm, -pier_hw, pier_hw, -HALF_D - pier_p, -HALF_D, 0, FLOOR_H), 0)
    z = 0.0
    block_h = 48.0
    i = 0
    while z < FLOOR_H - 90:
        w = pier_hw + (20.0 if i % 2 == 0 else 4.0)
        tag(box(bm, -w, w, -HALF_D - pier_p - 8.0, -HALF_D - pier_p, z + 3, z + block_h - 3), 0)
        z += block_h
        i += 1
    dentil_row(bm, FLOOR_H - 80.0, h=16.0, proud=26.0,
               x0=-pier_hw - 4, x1=pier_hw + 4)
    molded_course(bm, FLOOR_H - 60.0, PROFILE_CORNICE)
    return bm_to_obj(bm, "mod_corner_a")


# ===========================================================================
# MANSARD ROOF  (symbol Roof)
# ===========================================================================
def m_mansard(floor_h=MANSARD_H):
    """Detailed MANSARD ROOF course — deep MOLDED base cornice w/ a DENTIL row +
    modillion brackets, steep battered dark-ZINC slope, THREE PEDIMENTED stone
    dormers poking through, a flat zinc ridge cap, and a low stone BALUSTRADE
    running along the cornice. Base-pivoted (0..MANSARD_H), X-centered 400cm."""
    bm = bmesh.new()
    top_inset = 120.0
    yb1 = HALF_D
    # --- deep molded base cornice with dentils + modillions (the building crown) ---
    tag(box(bm, -HALF_W, HALF_W, -HALF_D - 30.0, HALF_D, 0, 18.0), 0)
    dentil_row(bm, 18.0, h=16.0, proud=34.0, mat=0)
    modillion_brackets(bm, 64.0, count=6, w=24.0, drop=40.0, proud=44.0, mat=0)
    cornice_top = molded_course(bm, 38.0, [(8, 14), (10, 24), (12, 34), (8, 22)], mat=0)
    # low stone balustrade sitting on the cornice (in front, mat 0)
    by0, by1 = -HALF_D - 30.0, -HALF_D - 18.0
    btop = cornice_top + 46.0
    tag(box(bm, -HALF_W + 8, HALF_W - 8, by0, by1, cornice_top, cornice_top + 8), 0)
    tag(box(bm, -HALF_W + 8, HALF_W - 8, by0, by1, btop - 8, btop), 0)
    bx = -HALF_W + 18
    while bx <= HALF_W - 18:
        tag(box(bm, bx - 4, bx + 4, by0, by1, cornice_top + 8, btop - 8), 0)
        bx += 22.0
    # --- steep battered zinc roof slab (wider at base, leaning back at top) ---
    z0, z1 = cornice_top + 4.0, floor_h - 26.0
    fx0, fx1 = -HALF_W, HALF_W
    tx0, tx1 = -HALF_W + 70, HALF_W - 70
    fy_base = -HALF_D
    fy_top  = -HALF_D + top_inset
    v = [bm.verts.new((fx0, fy_base, z0)), bm.verts.new((fx1, fy_base, z0)),
         bm.verts.new((tx1, fy_top,  z1)), bm.verts.new((tx0, fy_top,  z1))]
    vb = [bm.verts.new((fx0, yb1, z0)), bm.verts.new((fx1, yb1, z0)),
          bm.verts.new((tx1, yb1, z1)), bm.verts.new((tx0, yb1, z1))]
    faces = []
    faces.append(bm.faces.new((v[0], v[1], v[2], v[3])))
    faces.append(bm.faces.new((vb[3], vb[2], vb[1], vb[0])))
    faces.append(bm.faces.new((v[0], v[3], vb[3], vb[0])))
    faces.append(bm.faces.new((v[1], vb[1], vb[2], v[2])))
    faces.append(bm.faces.new((v[0], vb[0], vb[1], v[1])))
    tag(faces, 1)
    # flat zinc ridge cap
    tag(box(bm, tx0, tx1, fy_top, yb1, z1, floor_h), 1)
    # --- THREE pedimented stone dormers poking through the front slope ---
    for cx in (-120.0, 0.0, 120.0):
        dz0, dz1 = z0 + 50.0, z0 + 168.0
        dw = 44.0
        dy = fy_base - 22.0
        tag(box(bm, cx - dw, cx + dw, dy, fy_base + 30.0, dz0, dz1), 0)  # dormer stone body
        # molded jambs
        for sx in (cx - dw, cx + dw - 10):
            tag(box(bm, sx, sx + 10, dy - 4, dy, dz0, dz1), 0)
        # little triangular pediment cap
        pb = dz1
        for i in range(6):
            t = i / 6
            hw = (dw + 6) * (1 - t)
            tag(box(bm, cx - hw, cx + hw, dy - 6, dy, pb + 30 * t, pb + 30 * (t + 1 / 6)), 0)
        tag(box(bm, cx - dw + 8, cx + dw - 8, dy + 2, dy + 4, dz0 + 12, dz1 - 6), 1)  # dark dormer glass
    return bm_to_obj(bm, "mod_mansard")


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------
def setup_render(res_x=900, res_y=1000):
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
        bg.inputs[0].default_value = (0.16, 0.18, 0.22, 1.0)
        bg.inputs[1].default_value = 0.7


def add_cam_and_lights(floor_h):
    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam_data.lens = 55
    cam_data.clip_start = 1.0
    cam_data.clip_end = 1.0e6
    extent = max(HALF_W * 2, floor_h)
    dist = extent * 2.0
    cam.location = (dist * 0.9, -dist * 0.95, floor_h * 0.55 + extent * 0.18)
    target = mathutils.Vector((0, 0, floor_h * 0.5))
    direction = target - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    key = bpy.data.lights.new("Key", "SUN")
    key.energy = 3.2
    ko = bpy.data.objects.new("Key", key)
    ko.rotation_euler = (math.radians(64), math.radians(18), math.radians(48))
    bpy.context.collection.objects.link(ko)
    fill = bpy.data.lights.new("Fill", "SUN")
    fill.energy = 0.7
    fill.color = (0.80, 0.85, 1.0)
    fo = bpy.data.objects.new("Fill", fill)
    fo.rotation_euler = (math.radians(58), 0, math.radians(205))
    bpy.context.collection.objects.link(fo)


def export_fbx(obj, name):
    out_dir = os.path.join(ROOT, name)
    os.makedirs(out_dir, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    fbx = os.path.join(out_dir, name + ".fbx")
    bpy.ops.export_scene.fbx(
        filepath=fbx, use_selection=True,
        apply_scale_options="FBX_SCALE_ALL", apply_unit_scale=True,
        global_scale=1.0,
        object_types={"MESH"}, mesh_smooth_type="FACE",
        use_mesh_modifiers=True, bake_space_transform=True,
        axis_forward="-Z", axis_up="Y",
    )
    return fbx, out_dir


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
MODULES = [
    ("mod_wall_a",   "W",  "Heavily rusticated ashlar (deep drafted H+V joints) + molded string",   m_wall_a,   FLOOR_H),
    ("mod_wall_b",   "W",  "Ashlar + molded string course + framed frieze panel",                   m_wall_b,   FLOOR_H),
    ("mod_wall_c",   "W",  "Pilastered (base+flutes+capital) + rosette medallion + molded string",   m_wall_c,   FLOOR_H),
    ("mod_window_a", "W1", "Arched French window: molded archivolt+keystone, console sill, dentils",  m_window_a, FLOOR_H),
    ("mod_window_b", "W1", "Rect window + triangular pediment on consoles + balustrade + dentils",     m_window_b, FLOOR_H),
    ("mod_window_c", "W2", "Rect window + fine wrought-iron Juliet balcony + segmental pediment",      m_window_c, FLOOR_H),
    ("mod_corner_a", "C",  "Rusticated quoin pier + crowning dentil cornice",                          m_corner_a, FLOOR_H),
    ("mod_mansard",  "Roof", "Zinc mansard + molded dentil/modillion cornice + 3 pedimented dormers",  m_mansard,  MANSARD_H),
]

us = bpy.context.scene.unit_settings
us.system = "METRIC"
us.scale_length = 0.01
us.length_unit = "CENTIMETERS"

results = []
for name, symbol, desc, builder, fh in MODULES:
    reset_scene()
    setup_render()
    stone, iron = make_mats()
    obj = builder()
    finalize(obj, name, stone, iron, exp_floor_h=fh)
    b = verify_bounds(obj, name, exp_floor_h=fh)

    me = obj.data
    me.calc_loop_triangles()
    tris = len(me.loop_triangles)

    add_cam_and_lights(fh)
    fbx, out_dir = export_fbx(obj, name)
    png = os.path.join(out_dir, name + ".png")
    bpy.context.scene.render.filepath = png
    bpy.ops.render.render(write_still=True)

    results.append({"file": name, "symbol": symbol, "desc": desc,
                    "tris": tris, "bounds": b, "floor_h": fh, "png": png})
    print(f"DONE {name} [{symbol}]: {desc} | tris={tris} -> {fbx}")

import json
with open(os.path.join(ROOT, "_detailed_stats.json"), "w") as f:
    json.dump(results, f, indent=2)

# ---- montage of all detailed previews ----
try:
    cols = 4
    rows = math.ceil(len(results) / cols)
    cell_w, cell_h = 450, 500
    montage = bpy.data.images.new("montage", width=cell_w * cols, height=cell_h * rows)
    import numpy as np
    canvas = np.zeros((cell_h * rows, cell_w * cols, 4), dtype=np.float32)
    canvas[..., 3] = 1.0
    for i, r in enumerate(results):
        img = bpy.data.images.load(r["png"])
        w, h = img.size
        px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
        sy = max(1, h // cell_h)
        sx = max(1, w // cell_w)
        small = px[::sy, ::sx][:cell_h, :cell_w]
        sh, sw = small.shape[:2]
        cr = i // cols
        cc = i % cols
        y0 = (rows - 1 - cr) * cell_h
        x0 = cc * cell_w
        canvas[y0:y0 + sh, x0:x0 + sw] = small
        bpy.data.images.remove(img)
    montage.pixels = canvas.flatten().tolist()
    montage.filepath_raw = os.path.join(BASE_ROOT, "beaux_arts_detailed_montage.png")
    montage.file_format = "PNG"
    montage.save()
    print("MONTAGE ->", montage.filepath_raw)
except Exception as e:
    print("MONTAGE FAILED:", e)

print("ALL DETAILED DONE:", len(results))
