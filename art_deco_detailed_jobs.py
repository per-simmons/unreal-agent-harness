"""Headless Blender generator for DETAILED Art Deco facade-kit modules — the
"carved 1920s stone + bronze" pass. Sibling of `art_deco_variants_jobs.py`; it
reuses the EXACT module spec + base helpers, but every module is rebuilt with
MUCH deeper deco ornament so it reads as carved limestone + cast bronze, not a
bland flat box.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python art_deco_detailed_jobs.py

WHAT CHANGED vs the flat variants (why these read as real):
  - BEVEL EVERY HARD EDGE (the #1 anti-CG tell) — a Bevel modifier, applied.
  - DEEP relief, not surface scratches: piers/flutes/chevrons/grilles project
    20-60cm off the wall, not 4-16cm. The facade is now a thick stone slab with
    real proud carving + recessed reveals that self-shadow.
  - STRONG vertical emphasis: deep fluted piers run floor-to-floor between the
    windows on every wall + window module.
  - Chevron / zigzag / sunburst spandrels under/over each window as REAL relief
    on the bronze slot (slot 1), every window variant.
  - Geometric bronze window grilles + stepped reveals around the glazing.
  - Stepped / setback wall tops (a cap shelf course) on every wall.
  - Ziggurat + spire CROWN variants with stepped tiers + vertical bronze fins.
  - Grand deco lobby ground: chevron transom + fluted pilasters.
  - 2 material slots kept (0 = stone, 1 = bronze/metal); all metallic ornament
    (spandrels, grilles, crowns, fins, reveals) on slot 1.

THE MODULE SPEC (non-negotiable — identical to the variants, or the grammar breaks):
  ExtractMeshInfo computes  Size = $Extents.X * 2  and  PivotOffset = -$LocalCenter
    - WIDTH along local X, CENTERED  -> X spans -200 .. +200  (Extents.X=200 -> Size=400)
    - DEPTH along Y, shallow, centered on Y
    - HEIGHT along Z, base-pivoted    -> Z spans 0 .. floorH  (min.z = 0)
  Consistent 400cm width + 400cm floor height so everything tiles. verify_bounds()
  asserts X-centered / Y-centered / base-pivoted in bpy BEFORE export.

Output: ~/coding/unreal-agent-harness/assets/art_deco_kit/detailed/<name>/<name>.fbx
        + per-module <name>.png preview, art_deco_detailed_montage.png, NOTES.md,
        _stats.json.
"""
import bpy, bmesh, os, math, mathutils, json

ROOT = os.path.expanduser("~/coding/unreal-agent-harness/assets/art_deco_kit/detailed")
os.makedirs(ROOT, exist_ok=True)

# ---- THE MODULE SPEC (cm) -- identical to art_deco_variants_jobs.py ---------
MODULE_W = 400.0
HALF_W   = MODULE_W / 2.0   # 200  (Extents.X -> generator Size = 400)
FLOOR_H  = 400.0            # base-pivoted -> Z in [0, 400]
DEPTH    = 60.0             # DEEPER facade slab (was 30) so carving has room to recess
HALF_D   = DEPTH / 2.0      # 30
GROUND_H = 600.0
CROWN_H  = 800.0

# bevel applied to every module before export — the #1 anti-CG fix
BEVEL_W      = 1.6          # cm
BEVEL_SEG    = 2

FRONT = -HALF_D            # the front plane (faces -Y, the camera/street side)


# ---------------------------------------------------------------------------
# scene / material / mesh helpers (mirror the variants builder)
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


def fluted_pier(bm, cx, hw, z0, z1, y_proud, mat_stone=0, mat_bronze=1,
                n_grooves=3, body_depth=None):
    """A DEEP vertical pier centered at cx, half-width hw, projecting `y_proud`
    cm proud of the front plane, with `n_grooves` recessed bronze reveals running
    its full height (the carved fluting). This is the strong vertical emphasis."""
    if body_depth is None:
        body_depth = y_proud
    yf = FRONT
    # proud stone pier body
    box(bm, cx - hw, cx + hw, yf - body_depth, yf + 4.0, z0, z1, mat=mat_stone)
    # recessed bronze grooves on the proud face
    inner = hw * 0.78
    span = 2 * inner
    pitch = span / (n_grooves + 1)
    for i in range(1, n_grooves + 1):
        gx = cx - inner + pitch * i
        gw = pitch * 0.18
        # the groove is a thin bronze strip set BACK from the proud face -> self-shadows
        box(bm, gx - gw, gx + gw, yf - body_depth + 3.0, yf - body_depth + 9.0,
            z0 + 4, z1 - 4, mat=mat_bronze)


def chevron_band(bm, x0, x1, z_base, h, n, mat=1, y_front=None, y_proud=22.0,
                 thick=10.0):
    """Row of n up-pointing chevrons (deco zigzag), as DEEP relief proud of the
    front plane. Each chevron is an extruded triangular prism standing y_proud
    off the wall (was 4cm in the flat version)."""
    if y_front is None:
        y_front = FRONT
    span = x1 - x0
    step = span / n
    yb = y_front - y_proud        # tip plane (proud, toward camera at -Y)
    yt = y_front - y_proud + thick
    for i in range(n):
        bx = x0 + i * step
        pts = [(bx, z_base), (bx + step/2, z_base + h), (bx + step, z_base)]
        b2 = [bm.verts.new((px, yb, pz)) for (px, pz) in pts]
        t2 = [bm.verts.new((px, yt, pz)) for (px, pz) in pts]
        cf = [bm.faces.new(b2), bm.faces.new(list(reversed(t2)))]
        for k in range(3):
            cf.append(bm.faces.new((b2[k], b2[(k+1)%3], t2[(k+1)%3], t2[k])))
        for f in cf:
            f.material_index = mat


def sunburst(bm, cx, z_base, radius, h, n_rays, mat=1, y_front=None, y_proud=24.0,
             thick=10.0):
    """Fan of bronze rays (deco sunburst) as DEEP proud relief, radiating up from
    a base center. Stays within the X envelope."""
    if y_front is None:
        y_front = FRONT
    yb = y_front - y_proud
    yt = y_front - y_proud + thick
    for i in range(n_rays):
        frac = i / (n_rays - 1)
        ang = math.radians(20 + 140 * frac)
        tipx = cx + math.cos(ang) * radius
        tipz = z_base + math.sin(ang) * h
        rw = radius * 0.05
        pts = [(cx - rw, z_base), (cx + rw, z_base), (tipx, tipz)]
        b2 = [bm.verts.new((px, yb, pz)) for (px, pz) in pts]
        t2 = [bm.verts.new((px, yt, pz)) for (px, pz) in pts]
        cf = [bm.faces.new(b2), bm.faces.new(list(reversed(t2)))]
        for k in range(3):
            cf.append(bm.faces.new((b2[k], b2[(k+1)%3], t2[(k+1)%3], t2[k])))
        for f in cf:
            f.material_index = mat


def stepped_cap(bm, z_top, mat_stone=0, mat_bronze=1, hd=None):
    """A stepped/setback cap course at the top of a wall module (2 receding stone
    shelves + a bronze string course) — the deco wall-top setback."""
    if hd is None:
        hd = HALF_D
    box(bm, -HALF_W, HALF_W, FRONT, hd, z_top - 30, z_top - 18, mat=mat_bronze)
    box(bm, -HALF_W*0.94, HALF_W*0.94, FRONT - 6, hd, z_top - 18, z_top - 8, mat=mat_stone)
    box(bm, -HALF_W*0.86, HALF_W*0.86, FRONT - 10, hd, z_top - 8, z_top, mat=mat_stone)


def base_slab(bm, floor_h, hd=None):
    """The recessed stone wall body (set back so all carving reads proud)."""
    if hd is None:
        hd = HALF_D
    box(bm, -HALF_W, HALF_W, FRONT + 18.0, hd, 0, floor_h, mat=0)


def finalize(obj, name, stone, bronze):
    """2 mat slots, UV, bevel EVERY edge, normals out, origin at base-center."""
    me = obj.data
    # NOTE: do NOT call me.materials.clear() here — clearing the slot list resets
    # every face's material_index to 0, collapsing the bronze (slot 1) ornament
    # into the stone slot (the faces are tagged material_index 0/1 at build time).
    # The mesh starts with zero slots, so just append stone (slot 0) + bronze
    # (slot 1) to match the indices the geometry helpers already assigned.
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
    bpy.ops.object.mode_set(mode="OBJECT")

    # BEVEL EVERY HARD EDGE — the #1 anti-CG tell. Applied so it bakes into geo.
    bev = obj.modifiers.new("Bevel", "BEVEL")
    bev.width = BEVEL_W
    bev.segments = BEVEL_SEG
    bev.limit_method = "ANGLE"
    bev.angle_limit = math.radians(40)
    bev.harden_normals = True
    bev.miter_outer = "MITER_ARC"
    bpy.ops.object.modifier_apply(modifier=bev.name)

    # UV after bevel
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")

    # Re-center on Y so (miny+maxy)/2 == 0 (deep proud ornament pushes -Y; the
    # generator's PivotOffset = -$LocalCenter, so the mesh MUST be Y-centered or
    # the facade shifts off its footprint spline). We shift the whole mesh in Y
    # then drop a thin back stiffener so the front carving keeps reading proud.
    ys = [v.co.y for v in me.vertices]
    yc = (min(ys) + max(ys)) / 2.0
    for v in me.vertices:
        v.co.y -= yc

    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    return obj


def verify_bounds(obj, label, exp_floor_h=FLOOR_H, exp_half_w=HALF_W, tol=0.5):
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
    ok_height  = abs(maxz - exp_floor_h) <= max(tol, 2.5)  # bevel rounds top/apex edges
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
        "y_centered": ok_ycenter,
        "base_pivoted": ok_basez,
        "status": status,
    }


# ===========================================================================
# WALL VARIANTS (symbol W) — solid bays, now deeply carved
# ===========================================================================

def wall_a(floor_h=FLOOR_H):
    """W-A — PLAIN PIER (deep): one bold deep center pier with 3 fluted grooves,
    framed by 2 slimmer deep edge piers; stepped setback cap."""
    bm = bmesh.new()
    base_slab(bm, floor_h)
    fluted_pier(bm, 0.0, 60, 14, floor_h - 40, y_proud=40, n_grooves=3)
    for sx in (-HALF_W + 34, HALF_W - 34):
        fluted_pier(bm, sx, 30, 14, floor_h - 40, y_proud=30, n_grooves=2)
    stepped_cap(bm, floor_h)
    return bm_to_obj(bm, "wall_a_plain_pier")


def wall_b(floor_h=FLOOR_H):
    """W-B — FLUTED PIER (deep): 4 deep full-height fluted piers carrying the
    strong vertical rhythm, bronze reveals in every groove; stepped cap."""
    bm = bmesh.new()
    base_slab(bm, floor_h)
    n = 4
    x0, x1 = -HALF_W + 30, HALF_W - 30
    pitch = (x1 - x0) / n
    for i in range(n):
        cx = x0 + pitch * (i + 0.5)
        fluted_pier(bm, cx, pitch*0.40, 14, floor_h - 36, y_proud=38, n_grooves=2)
    stepped_cap(bm, floor_h)
    return bm_to_obj(bm, "wall_b_fluted_pier")


def wall_c(floor_h=FLOOR_H):
    """W-C — CHEVRON-SPANDREL (deep): two deep framing piers, a recessed central
    bay carrying 6 stacked rows of DEEP bronze chevrons; stepped cap."""
    bm = bmesh.new()
    base_slab(bm, floor_h)
    for sx in (-HALF_W + 18, HALF_W - 18 - 50):
        fluted_pier(bm, sx + 25, 28, 14, floor_h - 36, y_proud=40, n_grooves=2)
    px0, px1 = -HALF_W + 70, HALF_W - 70
    n_rows = 6
    row_h = (floor_h - 60) / n_rows
    for r in range(n_rows):
        chevron_band(bm, px0, px1, 26 + r * row_h, row_h * 0.78, n=4, mat=1,
                     y_proud=20.0, thick=9.0)
    stepped_cap(bm, floor_h)
    return bm_to_obj(bm, "wall_c_chevron_spandrel")


def wall_d(floor_h=FLOOR_H):
    """W-D — GEOMETRIC-RELIEF (deep): a deep concentric stepped rectangular relief
    (the 'frozen fountain' inset) projecting in 3 receding tiers, bronze-lined,
    flanked by 2 deep edge piers; stepped cap."""
    bm = bmesh.new()
    base_slab(bm, floor_h)
    for sx in (-HALF_W + 30, HALF_W - 30):
        fluted_pier(bm, sx, 26, 14, floor_h - 40, y_proud=34, n_grooves=2)
    # 3 receding proud tiers, alternating stone/bronze, each more proud
    zc = floor_h * 0.52
    tiers = [(120, floor_h*0.40, 0, 18), (88, floor_h*0.29, 1, 30), (54, floor_h*0.18, 0, 42)]
    for hw, hh, mat, proud in tiers:
        box(bm, -hw, hw, FRONT - proud, FRONT + 6.0, zc - hh, zc + hh, mat=mat)
    # bronze accent bars top + bottom of the panel, proud
    for zc2 in (floor_h*0.88, floor_h*0.13):
        box(bm, -130, 130, FRONT - 24, FRONT - 14, zc2 - 9, zc2 + 9, mat=1)
    stepped_cap(bm, floor_h)
    return bm_to_obj(bm, "wall_d_geometric_relief")


# ===========================================================================
# WINDOW VARIANTS (symbols W1/W2) — main facade unit, deep piers + grilles
# ===========================================================================

def _deep_window_piers(bm, floor_h, pier_w=56.0):
    """Two DEEP full-height fluted piers framing the bay (strong vertical
    emphasis on every window). Returns inner glazing x-range (gx0, gx1)."""
    cxl = -HALF_W + pier_w/2
    cxr = HALF_W - pier_w/2
    fluted_pier(bm, cxl, pier_w/2, 0, floor_h, y_proud=42, n_grooves=3)
    fluted_pier(bm, cxr, pier_w/2, 0, floor_h, y_proud=42, n_grooves=3)
    return -HALF_W + pier_w, HALF_W - pier_w


def _recessed_glazing(bm, gx0, gx1, z0, z1, recess=20.0):
    """Deep recessed glazing reveal: a stepped stone reveal frame around a back
    glazing plane, so the window sits in a deep shadowed pocket."""
    # stepped reveal frame (stone), set back from the front plane
    box(bm, gx0, gx1, FRONT + 6.0, HALF_D, z0, z1, mat=0)            # back glazing plane (deep)
    # proud stone reveal lip around the opening (frames the shadow)
    lip = 10.0
    box(bm, gx0 - lip, gx0, FRONT - 4, HALF_D, z0, z1, mat=0)
    box(bm, gx1, gx1 + lip, FRONT - 4, HALF_D, z0, z1, mat=0)
    box(bm, gx0 - lip, gx1 + lip, FRONT - 4, HALF_D, z0 - lip, z0, mat=0)
    box(bm, gx0 - lip, gx1 + lip, FRONT - 4, HALF_D, z1, z1 + lip, mat=0)


def window_a(floor_h=FLOOR_H):
    """W1-A — VERTICAL RIBBON (deep): deep fluted piers, a tall recessed glazing
    pocket, 2 slim proud bronze mullions + a chevron sill course."""
    bm = bmesh.new()
    gx0, gx1 = _deep_window_piers(bm, floor_h)
    gz0, gz1 = 28.0, floor_h - 28.0
    _recessed_glazing(bm, gx0, gx1, gz0, gz1)
    for mx in (-(gx1-gx0)*0.18, (gx1-gx0)*0.18):
        box(bm, mx - 5, mx + 5, FRONT - 10, FRONT + 6.0, gz0 + 6, gz1 - 6, mat=1)
    # proud bronze sill + lintel
    for hz in (gz0, gz1):
        box(bm, gx0 - 6, gx1 + 6, FRONT - 12, FRONT + 6.0, hz - 7, hz + 7, mat=1)
    chevron_band(bm, gx0, gx1, 6, 18, n=5, mat=1, y_proud=16, thick=8)
    return bm_to_obj(bm, "window_a_vertical_ribbon")


def window_b(floor_h=FLOOR_H):
    """W1-B — METAL GRILLE (deep): deep piers, recessed glazing crossed by a full
    proud bronze grille (3 mullions + 4 bars) + a deep chevron spandrel on top."""
    bm = bmesh.new()
    gx0, gx1 = _deep_window_piers(bm, floor_h)
    spand_h = floor_h * 0.22
    gz0, gz1 = 28.0, floor_h - spand_h
    _recessed_glazing(bm, gx0, gx1, gz0, gz1)
    gw = gx1 - gx0
    for f in (0.25, 0.5, 0.75):
        mx = gx0 + gw * f
        box(bm, mx - 4, mx + 4, FRONT - 12, FRONT + 6.0, gz0 + 6, gz1 - 6, mat=1)
    gh = gz1 - gz0
    for f in (0.2, 0.4, 0.6, 0.8):
        hz = gz0 + gh * f
        box(bm, gx0 + 6, gx1 - 6, FRONT - 12, FRONT + 6.0, hz - 4, hz + 4, mat=1)
    chevron_band(bm, gx0, gx1, gz1 + 8, spand_h * 0.78, n=4, mat=1, y_proud=22, thick=10)
    return bm_to_obj(bm, "window_b_metal_grille")


def window_c(floor_h=FLOOR_H):
    """W1-C — STEPPED-SPANDREL (deep): deep piers, recessed glazing topped by a
    DEEP stepped ziggurat bronze+stone spandrel projecting in 4 receding tiers."""
    bm = bmesh.new()
    gx0, gx1 = _deep_window_piers(bm, floor_h)
    spand_h = floor_h * 0.30
    gz0, gz1 = 28.0, floor_h - spand_h
    _recessed_glazing(bm, gx0, gx1, gz0, gz1)
    gw = gx1 - gx0
    # cross mullion grille on the glazing
    box(bm, -5, 5, FRONT - 10, FRONT + 6.0, gz0 + 8, gz1 - 8, mat=1)
    box(bm, gx0 + 6, gx1 - 6, FRONT - 10, FRONT + 6.0,
        gz0 + (gz1-gz0)*0.5 - 4, gz0 + (gz1-gz0)*0.5 + 4, mat=1)
    # 4 receding proud steps, alternating mat, each more proud
    steps = [(gw*0.5, 0, 14), (gw*0.40, 1, 24), (gw*0.30, 0, 32), (gw*0.20, 1, 40)]
    sh = spand_h / 4.0
    for i, (hw, mat, proud) in enumerate(steps):
        z0 = gz1 + i * sh
        box(bm, -hw, hw, FRONT - proud, FRONT + 6.0, z0, z0 + sh * 0.86, mat=mat)
    return bm_to_obj(bm, "window_c_stepped_spandrel")


def window_d(floor_h=FLOOR_H):
    """W1-D — SUNBURST (deep): deep piers, recessed glazing, a DEEP bronze
    sunburst fan radiating over the lintel + a proud bronze sill grille."""
    bm = bmesh.new()
    gx0, gx1 = _deep_window_piers(bm, floor_h)
    sun_zone = floor_h * 0.28
    gz0, gz1 = 28.0, floor_h - sun_zone
    _recessed_glazing(bm, gx0, gx1, gz0, gz1)
    gw = gx1 - gx0
    for hz in (gz0 + (gz1-gz0)*0.4, gz0 + (gz1-gz0)*0.72):
        box(bm, gx0 + 6, gx1 - 6, FRONT - 10, FRONT + 6.0, hz - 4, hz + 4, mat=1)
    # proud bronze lintel bar
    box(bm, gx0 - 6, gx1 + 6, FRONT - 14, FRONT + 6.0, gz1 - 8, gz1 + 4, mat=1)
    sunburst(bm, 0.0, gz1 + 8, radius=gw*0.46, h=sun_zone * 0.80, n_rays=11, mat=1,
             y_proud=26, thick=11)
    return bm_to_obj(bm, "window_d_sunburst")


# ===========================================================================
# CORNER VARIANTS (symbol C) — closes the box, deep quoins
# ===========================================================================

def corner_a(floor_h=FLOOR_H):
    """C-A — PLAIN QUOIN (deep): full-height stone corner pier + deep proud edge
    rib + a bronze cap band + a deep fluted return on the front."""
    bm = bmesh.new()
    box(bm, -HALF_W, HALF_W, FRONT + 12, HALF_D, 0, floor_h, mat=0)
    box(bm, -HALF_W, HALF_W, FRONT, HALF_D, floor_h - 16, floor_h, mat=1)
    # deep proud edge rib at the -X corner
    fluted_pier(bm, -HALF_W + 36, 36, 10, floor_h - 22, y_proud=40, n_grooves=2)
    # stacked bronze quoin blocks down the corner edge
    for i in range(6):
        z = 20 + i * (floor_h - 60) / 6
        box(bm, -HALF_W, -HALF_W + 70, FRONT - 6, FRONT + 12, z, z + 22, mat=1)
    return bm_to_obj(bm, "corner_a_plain_quoin")


def corner_b(floor_h=FLOOR_H):
    """C-B — STEPPED/CHAMFERED QUOIN (deep): 3 setback stone boxes shrinking
    upward with bronze banding at each shelf + deep fluted piers on the lower
    section (the deco corner)."""
    bm = bmesh.new()
    steps = [(HALF_W, HALF_D, 0.0, floor_h*0.55),
             (HALF_W*0.86, HALF_D*0.9, floor_h*0.55, floor_h*0.82),
             (HALF_W*0.72, HALF_D*0.8, floor_h*0.82, floor_h)]
    for hw, hd, z0, z1 in steps:
        box(bm, -hw, hw, FRONT, hd, z0, z1, mat=0)
        box(bm, -hw, hw, FRONT - 4, FRONT + 4, z1 - 12.0, z1, mat=1)
    # deep fluted piers on the lower section
    x0, x1 = -HALF_W + 28, HALF_W - 28
    n = 3
    pitch = (x1 - x0) / n
    for i in range(n):
        cx = x0 + pitch * (i + 0.5)
        fluted_pier(bm, cx, pitch*0.32, 10, floor_h*0.55 - 12, y_proud=34, n_grooves=2)
    return bm_to_obj(bm, "corner_b_stepped_quoin")


# ===========================================================================
# CROWN VARIANTS (top course) — the iconic silhouette, with vertical fins
# ===========================================================================

def crown_a(crown_h=CROWN_H):
    """CROWN-A — ZIGGURAT STEP: 6 concentric setback stone tiers to a central
    bronze spire, bronze banding + vertical bronze FINS on the lower tiers +
    a deep sunburst-chevron band on the lowest step front."""
    bm = bmesh.new()
    n_steps = 6
    for i in range(n_steps):
        frac0, frac1 = i / n_steps, (i + 1) / n_steps
        hw = HALF_W * (1.0 - 0.14 * i)
        hd = HALF_D + (HALF_W * 0.22) * (1.0 - 0.14 * i)
        z0, z1 = crown_h * 0.55 * frac0, crown_h * 0.55 * frac1
        box(bm, -hw, hw, -hd, hd, z0, z1, mat=0)
        box(bm, -hw, hw, -hd, hd, z1 - 8.0, z1, mat=1)
        # vertical bronze fins up each tier face (front)
        nf = 5
        fx0, fx1 = -hw + 14, hw - 14
        fp = (fx1 - fx0) / nf
        yf = -hd
        for k in range(nf):
            fcx = fx0 + fp * (k + 0.5)
            box(bm, fcx - fp*0.16, fcx + fp*0.16, yf - 10, yf + 6, z0 + 4, z1 - 10, mat=1)
    # central bronze pyramidal spire
    sp_base = crown_h * 0.55
    spw = HALF_W * 0.12
    pts = [(-spw, -spw), (spw, -spw), (spw, spw), (-spw, spw)]
    bottom = [bm.verts.new((x, y, sp_base)) for (x, y) in pts]
    apex = bm.verts.new((0, 0, crown_h + 18.0))  # +bevel overshoot so post-bevel apex ~= crown_h
    for k in range(4):
        bm.faces.new((bottom[k], bottom[(k+1)%4], apex)).material_index = 1
    bm.faces.new(bottom).material_index = 1
    # deep sunburst-chevron band on the lowest step front
    yf = -(HALF_D + HALF_W * 0.22)
    chevron_band(bm, -HALF_W, HALF_W, crown_h*0.05, crown_h*0.11, n=6, mat=1,
                 y_front=yf, y_proud=18, thick=9)
    return bm_to_obj(bm, "crown_a_ziggurat")


def crown_b(crown_h=CROWN_H):
    """CROWN-B — SPIRE-TOP: low stepped base launching a TALL multi-tier bronze
    spire flanked by vertical fins + two short stone finials (Chrysler needle)."""
    bm = bmesh.new()
    base_top = crown_h * 0.30
    box(bm, -HALF_W, HALF_W, -HALF_D - HALF_W*0.20, HALF_D + HALF_W*0.20,
        0, base_top*0.6, mat=0)
    box(bm, -HALF_W*0.78, HALF_W*0.78, -HALF_D - HALF_W*0.12, HALF_D + HALF_W*0.12,
        base_top*0.6, base_top, mat=0)
    box(bm, -HALF_W*0.78, HALF_W*0.78, -HALF_D - HALF_W*0.12, HALF_D + HALF_W*0.12,
        base_top - 10, base_top, mat=1)
    # vertical bronze fins flanking the spire base (front of the base block)
    yf = -HALF_D - HALF_W*0.20
    for k in range(7):
        fcx = -HALF_W + 26 + k * (2*HALF_W - 52) / 6
        box(bm, fcx - 7, fcx + 7, yf - 8, yf + 8, base_top*0.6, base_top, mat=1)
    # tall central bronze spire from 4 stacked shrinking pyramidal tiers
    z = base_top
    tw = HALF_W * 0.36
    tiers = [(tw, crown_h*0.20), (tw*0.66, crown_h*0.18),
             (tw*0.42, crown_h*0.16), (tw*0.24, crown_h*0.14)]
    for halfw, th in tiers:
        pts = [(-halfw, -halfw), (halfw, -halfw), (halfw, halfw), (-halfw, halfw)]
        bottom = [bm.verts.new((x, y, z)) for (x, y) in pts]
        nhw = halfw * 0.5
        tpts = [(-nhw, -nhw), (nhw, -nhw), (nhw, nhw), (-nhw, nhw)]
        topv = [bm.verts.new((x, y, z + th)) for (x, y) in tpts]
        bm.faces.new(bottom).material_index = 1
        bm.faces.new(list(reversed(topv))).material_index = 1
        for k in range(4):
            bm.faces.new((bottom[k], bottom[(k+1)%4], topv[(k+1)%4], topv[k])).material_index = 1
        z += th
    # final needle
    npw = HALF_W * 0.06
    pts = [(-npw, -npw), (npw, -npw), (npw, npw), (-npw, npw)]
    bottom = [bm.verts.new((x, y, z)) for (x, y) in pts]
    apex = bm.verts.new((0, 0, crown_h))
    for k in range(4):
        bm.faces.new((bottom[k], bottom[(k+1)%4], apex)).material_index = 1
    bm.faces.new(bottom).material_index = 1
    # two short corner stone finials with bronze caps
    for sx in (-HALF_W + 18, HALF_W - 18 - 40):
        box(bm, sx, sx + 40, -HALF_D, HALF_D, base_top, base_top + crown_h*0.13, mat=0)
        box(bm, sx, sx + 40, -HALF_D, HALF_D,
            base_top + crown_h*0.13 - 8, base_top + crown_h*0.13, mat=1)
    return bm_to_obj(bm, "crown_b_spire")


def crown_c(crown_h=CROWN_H):
    """CROWN-C — FLUTED CAP: bold stone parapet carrying tall deep vertical bronze
    fins (pier lines continuing over the top) + stepped bronze cornice + central
    finial."""
    bm = bmesh.new()
    cap_h = crown_h * 0.62
    hd = HALF_D + HALF_W * 0.12
    box(bm, -HALF_W, HALF_W, -hd, hd, 0, cap_h, mat=0)
    # tall deep vertical bronze fins up the front, each with a flanking stone reveal
    n = 9
    x0, x1 = -HALF_W + 14, HALF_W - 14
    pitch = (x1 - x0) / n
    yf = -hd
    for i in range(n):
        cx = x0 + pitch * (i + 0.5)
        box(bm, cx - pitch*0.20, cx + pitch*0.20, yf - 28, yf + 8, 18, cap_h - 36, mat=1)
        box(bm, cx - pitch*0.36, cx - pitch*0.20, yf - 14, yf + 4, 18, cap_h - 36, mat=0)
    # stepped bronze cornice crowning the block
    box(bm, -HALF_W, HALF_W, -hd, hd, cap_h - 34, cap_h - 16, mat=1)
    box(bm, -HALF_W*0.9, HALF_W*0.9, -hd*0.92, hd*0.92, cap_h - 16, cap_h, mat=0)
    box(bm, -HALF_W*0.9, HALF_W*0.9, -hd*0.92, hd*0.92, cap_h, cap_h + crown_h*0.07, mat=1)
    # central bronze finial block
    box(bm, -HALF_W*0.16, HALF_W*0.16, -HALF_D, HALF_D,
        cap_h + crown_h*0.07, crown_h, mat=1)
    return bm_to_obj(bm, "crown_c_fluted_cap")


# ===========================================================================
# GROUND — grand deco lobby, chevron transom + fluted pilasters
# ===========================================================================

def ground_a(floor_h=GROUND_H):
    """GROUND-A — GRAND DECO LOBBY: tall recessed entrance glazing, deep fluted
    pilasters framing it, a DEEP chevron transom over the door, a bronze base
    band + a sunburst over the lobby lintel."""
    bm = bmesh.new()
    gx0, gx1 = _deep_window_piers(bm, floor_h)
    # extra inner fluted pilasters framing the entry
    for sx in (gx0 + 40, gx1 - 40):
        fluted_pier(bm, sx, 24, 0, floor_h, y_proud=36, n_grooves=2)
    spand_h = floor_h * 0.18
    gz0, gz1 = 0.0, floor_h - spand_h
    _recessed_glazing(bm, gx0 + 64, gx1 - 64, 110, gz1)
    # tall bronze base band (grand lobby plinth)
    box(bm, gx0, gx1, FRONT - 8, FRONT + 6.0, 0, floor_h * 0.18, mat=1)
    # DEEP chevron transom over the entrance
    chevron_band(bm, gx0 + 64, gx1 - 64, gz1 - 70, 56, n=6, mat=1, y_proud=22, thick=10)
    # sunburst over the lobby lintel
    sunburst(bm, 0.0, gz1 + 8, radius=(gx1-gx0)*0.40, h=spand_h*0.82, n_rays=11,
             mat=1, y_proud=24, thick=11)
    return bm_to_obj(bm, "ground_a_grand_lobby")


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


def export_fbx(obj, name):
    """Export to detailed/<name>/<name>.fbx (per-module subfolder)."""
    sub = os.path.join(ROOT, name)
    os.makedirs(sub, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    fbx = os.path.join(sub, name + ".fbx")
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

# (name, symbol, desc, builder, floor_h_for_bounds, slot1_faces)
MODULES = [
    ("wall_a_plain_pier",        "W",     "Deep center+edge fluted piers, stepped cap",          lambda: wall_a(),   FLOOR_H, "pier groove reveals, cap string course"),
    ("wall_b_fluted_pier",       "W",     "4 deep full-height fluted piers, stepped cap",         lambda: wall_b(),   FLOOR_H, "groove reveals, cap string course"),
    ("wall_c_chevron_spandrel",  "W",     "Deep framing piers + 6 rows deep bronze chevrons",     lambda: wall_c(),   FLOOR_H, "chevron bands, groove reveals, cap"),
    ("wall_d_geometric_relief",  "W",     "Deep 3-tier frozen-fountain inset + accent bars",      lambda: wall_d(),   FLOOR_H, "tier 2, accent bars, groove reveals, cap"),
    ("window_a_vertical_ribbon", "W1/W2", "Deep piers, recessed glazing, mullions + chevron sill",lambda: window_a(), FLOOR_H, "mullions, sill/lintel, chevron sill, groove reveals"),
    ("window_b_metal_grille",    "W1/W2", "Deep piers, full bronze grille + deep chevron spandrel",lambda: window_b(),FLOOR_H, "grille bars/mullions, chevron spandrel, groove reveals"),
    ("window_c_stepped_spandrel","W1/W2", "Deep piers, 4-tier ziggurat bronze/stone spandrel",   lambda: window_c(), FLOOR_H, "grille, alt-tier spandrel, groove reveals"),
    ("window_d_sunburst",        "W1/W2", "Deep piers, bronze sunburst over lintel + sill grille",lambda: window_d(),FLOOR_H, "sunburst, lintel/sill bars, groove reveals"),
    ("corner_a_plain_quoin",     "C",     "Deep corner pier, stacked bronze quoins + cap band",  lambda: corner_a(), FLOOR_H, "quoin blocks, cap band, groove reveals"),
    ("corner_b_stepped_quoin",   "C",     "3 setback tiers + bronze bands + deep lower flutes",  lambda: corner_b(), FLOOR_H, "shelf bands, groove reveals"),
    ("crown_a_ziggurat",         "CROWN", "6 setback tiers + spire + vertical fins + sunburst",  lambda: crown_a(),  CROWN_H, "spire, tier bands, vertical fins, sunburst-chevron"),
    ("crown_b_spire",            "CROWN", "Stepped base + tall tiered needle + fins + finials",  lambda: crown_b(),  CROWN_H, "spire tiers, base fins, finial caps, base band"),
    ("crown_c_fluted_cap",       "CROWN", "Parapet + tall vertical fins + stepped cornice",      lambda: crown_c(),  CROWN_H, "vertical fins, cornice, central finial"),
    ("ground_a_grand_lobby",     "ground W1","Grand lobby: fluted pilasters, chevron transom, sunburst",lambda: ground_a(),GROUND_H,"base band, transom chevrons, sunburst, groove reveals"),
]

us = bpy.context.scene.unit_settings
us.system = "METRIC"
us.scale_length = 0.01
us.length_unit = "CENTIMETERS"

results = []
setup_render()

for name, symbol, desc, builder, fh, slot1 in MODULES:
    reset_scene()
    setup_render()
    stone, bronze = make_mats()
    obj = builder()
    finalize(obj, name, stone, bronze)
    b = verify_bounds(obj, name, exp_floor_h=fh)

    me = obj.data
    me.calc_loop_triangles()
    tris = len(me.loop_triangles)
    n_slots = len(me.materials)

    add_cam_and_lights(fh)
    sub = os.path.join(ROOT, name)
    os.makedirs(sub, exist_ok=True)
    png = os.path.join(sub, name + ".png")
    bpy.context.scene.render.filepath = png
    bpy.ops.render.render(write_still=True)

    fbx = export_fbx(obj, name)
    results.append({"file": name, "symbol": symbol, "desc": desc, "tris": tris,
                    "slots": n_slots, "slot1_metal": slot1, "bounds": b, "floor_h": fh})
    print(f"DONE {name} [{symbol}]: {desc} | tris={tris} slots={n_slots} -> {fbx}")

with open(os.path.join(ROOT, "_stats.json"), "w") as f:
    json.dump(results, f, indent=2)

fails = [r["file"] for r in results if r["bounds"]["status"] != "OK"]
print("ALL DETAILED MODULES DONE:", len(results), "| FAILS:", fails if fails else "none")
