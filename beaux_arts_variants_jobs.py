"""Headless Blender generator for VARIANTS of the BEAUX-ARTS / HAUSSMANN kit.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python beaux_arts_variants_jobs.py

WHY: the base kit (beaux_arts_kit_jobs.py) gives ONE of each module, so an
assembled Parisian block looks copy-pasted. This file produces MULTIPLE variants
of each Haussmann module — different wall stonework, different window ornament,
two corner treatments, plus a proper MANSARD roof course — so the grammar
generator can pull a WEIGHTED/random palette per symbol and no two buildings on
a block read the same. That variety IS the realism lever.

NON-NEGOTIABLE module spec (IDENTICAL to beaux_arts_kit_jobs.py, or the grammar
generator's ExtractMeshInfo assembles broken modules):
  - WIDTH = 400cm along LOCAL +X, CENTERED            -> X spans -200..+200
  - DEPTH shallow on Y, centered                      -> Y centered
  - HEIGHT on Z, BASE-PIVOTED (min.z = 0)             -> Z spans 0..floorH
  - consistent 400cm width + ~400cm floor height so everything tiles
  - 2 material slots: slot 0 = Stone (cream limestone), slot 1 = Iron (zinc/iron)
  - UNIT FIX: scene in CENTIMETERS + FBX_SCALE_ALL + apply_unit_scale -> UE 1:1
Every module is verify_bounds()'d in bpy BEFORE export (status must be OK).

OUTPUT: ~/coding/unreal-agent-harness/assets/beaux_arts_kit/variants/<name>/<name>.fbx
  3-4 WALL variants:    mod_wall_a (plain ashlar), mod_wall_b (ashlar+string course),
                        mod_wall_c (rusticated), mod_wall_d (pilastered)
  4 WINDOW variants:    mod_window_a (arched French window),
                        mod_window_b (rectangular + triangular pediment + consoles),
                        mod_window_c (Juliet balcony + wrought-iron),
                        mod_window_d (segmental pediment + balustrade)
  2 CORNER variants:    mod_corner_a (plain quoin), mod_corner_b (rusticated quoin)
  1 MANSARD roof:       mod_mansard (steep dark zinc + dormers, top course)
  + the existing ground/lobby is kept (re-emitted as mod_ground for completeness)

Renders a montage beaux_arts_variants_montage.png + writes _variants_stats.json.
"""
import bpy, bmesh, os, math, mathutils

BASE_ROOT = os.path.expanduser("~/coding/unreal-agent-harness/assets/beaux_arts_kit")
ROOT      = os.path.join(BASE_ROOT, "variants")
os.makedirs(ROOT, exist_ok=True)

# ---- THE MODULE SPEC (cm) — IDENTICAL to the base kit ----------------------
MODULE_W = 400.0
HALF_W   = MODULE_W / 2.0   # 200
FLOOR_H  = 400.0
DEPTH    = 30.0
HALF_D   = DEPTH / 2.0      # 15
GROUND_H = 600.0
MANSARD_H = 350.0


# ---------------------------------------------------------------------------
# scene / material helpers (identical to the base kit)
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


def arch_band(bm, x0, x1, y0, y1, z_spring, z_top, n=28, mat=0, ring=True):
    """Semicircular arch over an opening (see base kit). ring=True -> proud
    constant-thickness arc molding; ring=False -> solid filled tympanum."""
    cx = (x0 + x1) / 2.0
    rx = (x1 - x0) / 2.0
    rz = (z_top - z_spring)
    band = min(rx, rz) * 0.34
    prev = None
    for i in range(n + 1):
        t = i / n
        ang = math.pi * t
        x = cx - rx * math.cos(ang)
        z = z_spring + rz * math.sin(ang)
        if prev is not None:
            px, pz = prev
            if ring:
                f = box(bm, min(px, x) - 3, max(px, x) + 3, y0, y1,
                        max(z, pz) - band, max(z, pz))
            else:
                f = box(bm, min(px, x), max(px, x), y0, y1, z_spring, max(z, pz))
            tag(f, mat)
        prev = (x, z)


def segmental_band(bm, x0, x1, y0, y1, z_base, rise, n=18, mat=0):
    """A shallow SEGMENTAL (flattened) arch pediment over an opening — a wide
    low arc, the typical 'flattened' Haussmann window head. Proud molding."""
    cx = (x0 + x1) / 2.0
    half = (x1 - x0) / 2.0
    R = (half * half + rise * rise) / (2.0 * rise)   # radius of the segment
    cz = z_base + rise - R                            # arc center below the base
    band = 16.0
    prev = None
    for i in range(n + 1):
        t = -1.0 + 2.0 * (i / n)
        x = cx + half * t
        z = cz + math.sqrt(max(R * R - (x - cx) ** 2, 0.0))
        if prev is not None:
            px, pz = prev
            f = box(bm, min(px, x) - 3, max(px, x) + 3, y0, y1,
                    min(z, pz) - band, max(z, pz))
            tag(f, mat)
        prev = (x, z)


# ---------------------------------------------------------------------------
# finalize / verify  (identical to the base kit)
# ---------------------------------------------------------------------------
def finalize(obj, name, stone, iron):
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
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")

    me = obj.data
    ys = [v.co.y for v in me.vertices]
    yshift = -(min(ys) + max(ys)) / 2.0
    if abs(yshift) > 1e-4:
        for v in me.vertices:
            v.co.y += yshift

    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    return obj


def verify_bounds(obj, label, exp_floor_h=FLOOR_H, tol=0.5):
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


# ---------------------------------------------------------------------------
# shared facade pieces
# ---------------------------------------------------------------------------
def _string_course(bm, z, proud=8.0, h=14.0, mat=0):
    f = box(bm, -HALF_W, HALF_W, -HALF_D - proud, -HALF_D, z, z + h)
    tag(f, mat)


def _ashlar_courses(bm, floor_h, course_h=80.0, proud=2.0):
    """Faint proud horizontal ashlar joints up the wall face (-Y)."""
    z = course_h
    while z < floor_h - 10:
        tag(box(bm, -HALF_W, HALF_W, -HALF_D - proud, -HALF_D, z - 2.5, z + 2.5), 0)
        z += course_h


def _rustication(bm, floor_h, band=60.0, depth=5.0, z_start=60.0):
    """Heavy deep horizontal rustication joints across the whole face."""
    z = z_start
    while z < floor_h - 30:
        tag(box(bm, -HALF_W, HALF_W, -HALF_D - depth, -HALF_D, z - 5.0, z + 5.0), 0)
        z += band


def _juliet_balcony(bm, op_x0, op_x1, sill_z, rail_h=80.0):
    """Wrought-iron Juliet balcony railing in front of the sill (mat 1)."""
    bal_y0 = -HALF_D - 22.0
    bal_y1 = -HALF_D - 14.0
    rail_top = sill_z + rail_h
    tag(box(bm, op_x0 - 14, op_x1 + 14, bal_y0, bal_y1, sill_z + 2, sill_z + 8), 1)
    tag(box(bm, op_x0 - 14, op_x1 + 14, bal_y0, bal_y1, rail_top - 6, rail_top), 1)
    bx = op_x0 - 6
    while bx <= op_x1 + 6:
        tag(box(bm, bx - 2.0, bx + 2.0, bal_y0, bal_y1, sill_z + 2, rail_top), 1)
        bx += 16.0


def _balustrade(bm, op_x0, op_x1, sill_z, rail_h=70.0):
    """Stone balustrade (turned stone balusters) in front of the sill (mat 0)."""
    by0 = -HALF_D - 26.0
    by1 = -HALF_D - 16.0
    rail_top = sill_z + rail_h
    tag(box(bm, op_x0 - 16, op_x1 + 16, by0, by1, sill_z, sill_z + 12), 0)        # base rail
    tag(box(bm, op_x0 - 16, op_x1 + 16, by0, by1, rail_top - 12, rail_top), 0)    # cap rail
    bx = op_x0 - 8
    while bx <= op_x1 + 8:
        tag(box(bm, bx - 5.0, bx + 5.0, by0, by1, sill_z + 12, rail_top - 12), 0)  # stone baluster
        bx += 26.0


def _consoles(bm, op_x0, op_x1, z, mat=0):
    """Two stone console brackets (corbels) supporting a pediment / cornice."""
    for sx in (op_x0 - 6, op_x1 - 18):
        tag(box(bm, sx, sx + 24, -HALF_D - 20.0, -HALF_D, z - 36, z), mat)


def _glass(bm, op_x0, op_x1, sill_z, head_z):
    gy = -HALF_D + 4.0
    tag(box(bm, op_x0 + 8, op_x1 - 8, gy, gy + 2.0, sill_z, head_z), 1)


# ---------------------------------------------------------------------------
# WALL VARIANTS  (symbol W)
# ---------------------------------------------------------------------------
def m_wall_a():
    """Plain limestone ashlar wall — quiet, no string course. The blank bay."""
    bm = bmesh.new()
    tag(box(bm, -HALF_W, HALF_W, -HALF_D, HALF_D, 0, FLOOR_H), 0)
    _ashlar_courses(bm, FLOOR_H, course_h=80.0, proud=2.0)
    return bm_to_obj(bm, "mod_wall_a")


def m_wall_b():
    """Ashlar wall + proud string course at the floor line (aligns floor-to-floor)."""
    bm = bmesh.new()
    tag(box(bm, -HALF_W, HALF_W, -HALF_D, HALF_D, 0, FLOOR_H), 0)
    _ashlar_courses(bm, FLOOR_H, course_h=80.0, proud=2.0)
    _string_course(bm, FLOOR_H - 18.0, proud=10.0, h=18.0, mat=0)
    return bm_to_obj(bm, "mod_wall_b")


def m_wall_c():
    """Rusticated wall — heavy deep banded stone joints across the whole face,
    plus a string course. Reads as a heavier, more fortified bay."""
    bm = bmesh.new()
    tag(box(bm, -HALF_W, HALF_W, -HALF_D, HALF_D, 0, FLOOR_H), 0)
    _rustication(bm, FLOOR_H, band=55.0, depth=6.0, z_start=40.0)
    _string_course(bm, FLOOR_H - 18.0, proud=12.0, h=18.0, mat=0)
    return bm_to_obj(bm, "mod_wall_c")


def m_wall_d():
    """Pilastered wall — two flat stone pilasters (proud vertical strips) with a
    small capital band near the top, framing a recessed central panel + string
    course. The most ornate blank bay."""
    bm = bmesh.new()
    tag(box(bm, -HALF_W, HALF_W, -HALF_D, HALF_D, 0, FLOOR_H), 0)
    _ashlar_courses(bm, FLOOR_H, course_h=90.0, proud=2.0)
    pil_w = 34.0
    pil_p = 12.0
    cap_z = FLOOR_H - 70.0
    for px in (-HALF_W + 40, HALF_W - 40 - pil_w):
        tag(box(bm, px, px + pil_w, -HALF_D - pil_p, -HALF_D, 0, cap_z), 0)       # pilaster shaft
        tag(box(bm, px - 6, px + pil_w + 6, -HALF_D - pil_p - 4, -HALF_D,
                cap_z, cap_z + 22), 0)                                            # capital band
    _string_course(bm, FLOOR_H - 18.0, proud=12.0, h=18.0, mat=0)
    return bm_to_obj(bm, "mod_wall_d")


# ---------------------------------------------------------------------------
# WINDOW VARIANTS  (symbols W1 / W2)
# ---------------------------------------------------------------------------
def _window_body(bm, op_x0, op_x1, sill_z, head_z, floor_h):
    """The 4 stone margins around a rectangular opening (left/right/below/above)."""
    for (mx0, mx1) in ((-HALF_W, op_x0), (op_x1, HALF_W)):
        tag(box(bm, mx0, mx1, -HALF_D, HALF_D, 0, floor_h), 0)
    tag(box(bm, op_x0, op_x1, -HALF_D, HALF_D, 0, sill_z), 0)        # spandrel below
    tag(box(bm, op_x0, op_x1, -HALF_D, HALF_D, head_z, floor_h), 0)  # above head


def m_window_a(floor_h=FLOOR_H):
    """Arched French window — round arch head, proud architrave jambs, keystone,
    recessed glass, continuous balcony band, floor-line cornice. (the classic)."""
    bm = bmesh.new()
    op_x0, op_x1 = -120.0, 120.0
    sill_z   = 95.0
    spring_z = floor_h - 150.0
    head_z   = floor_h - 60.0
    # left/right/below margins + above-arch margin
    for (mx0, mx1) in ((-HALF_W, op_x0), (op_x1, HALF_W)):
        tag(box(bm, mx0, mx1, -HALF_D, HALF_D, 0, floor_h), 0)
    tag(box(bm, op_x0, op_x1, -HALF_D, HALF_D, 0, sill_z), 0)
    tag(box(bm, op_x0, op_x1, -HALF_D, HALF_D, head_z, floor_h), 0)
    _glass(bm, op_x0, op_x1, sill_z, spring_z + 55)
    jamb_w, jamb_p = 16.0, 12.0
    for sx in (op_x0 - jamb_w, op_x1):
        tag(box(bm, sx, sx + jamb_w, -HALF_D - jamb_p, -HALF_D, sill_z, spring_z), 0)
    arch_band(bm, op_x0 - jamb_w, op_x1 + jamb_w, -HALF_D - jamb_p, -HALF_D,
              spring_z, head_z, n=28, mat=0, ring=True)
    tag(box(bm, -20.0, 20.0, -HALF_D - jamb_p - 10.0, -HALF_D, head_z - 70.0, head_z + 30.0), 0)  # keystone
    tag(box(bm, op_x0 - 10, op_x1 + 10, -HALF_D - 14.0, -HALF_D, sill_z - 12.0, sill_z), 0)       # sill
    tag(box(bm, -HALF_W, HALF_W, -HALF_D - 16.0, -HALF_D - 12.0, sill_z - 4, sill_z + 2), 1)      # iron band
    _string_course(bm, floor_h - 20.0, proud=12.0, h=20.0, mat=0)
    return bm_to_obj(bm, "mod_window_a")


def m_window_b(floor_h=FLOOR_H):
    """Rectangular window with a TRIANGULAR PEDIMENT on console brackets — the
    grand piano-nobile treatment. Rectangular opening, proud jambs, two console
    corbels, a triangular stone pediment over the head, recessed glass."""
    bm = bmesh.new()
    op_x0, op_x1 = -115.0, 115.0
    sill_z   = 100.0
    head_z   = floor_h - 110.0
    _window_body(bm, op_x0, op_x1, sill_z, head_z, floor_h)
    _glass(bm, op_x0, op_x1, sill_z, head_z)
    jamb_w, jamb_p = 18.0, 12.0
    for sx in (op_x0 - jamb_w, op_x1):
        tag(box(bm, sx, sx + jamb_w, -HALF_D - jamb_p, -HALF_D, sill_z, head_z), 0)
    # entablature lintel over the head
    tag(box(bm, op_x0 - jamb_w - 6, op_x1 + jamb_w + 6, -HALF_D - jamb_p - 4, -HALF_D,
            head_z, head_z + 22), 0)
    _consoles(bm, op_x0 - jamb_w, op_x1 + jamb_w, head_z)
    # TRIANGULAR pediment (built from stacked narrowing slabs forming a triangle)
    ped_base = head_z + 22
    ped_w = (op_x1 - op_x0) / 2.0 + jamb_w + 14
    steps = 9
    ped_h = 78.0
    for i in range(steps):
        t = i / steps
        hw = ped_w * (1.0 - t)
        z0 = ped_base + ped_h * t
        z1 = ped_base + ped_h * (t + 1.0 / steps)
        tag(box(bm, -hw, hw, -HALF_D - jamb_p - 6, -HALF_D, z0, z1), 0)
    tag(box(bm, op_x0 - 12, op_x1 + 12, -HALF_D - 14.0, -HALF_D, sill_z - 12.0, sill_z), 0)  # sill
    _string_course(bm, floor_h - 18.0, proud=12.0, h=18.0, mat=0)
    return bm_to_obj(bm, "mod_window_b")


def m_window_c(floor_h=FLOOR_H):
    """Rectangular window + full WROUGHT-IRON JULIET BALCONY + simple cornice.
    The everyday Haussmann floor window with iron rail (mat 1 prominent)."""
    bm = bmesh.new()
    op_x0, op_x1 = -118.0, 118.0
    sill_z   = 90.0
    head_z   = floor_h - 95.0
    _window_body(bm, op_x0, op_x1, sill_z, head_z, floor_h)
    _glass(bm, op_x0, op_x1, sill_z, head_z)
    jamb_w, jamb_p = 14.0, 10.0
    for sx in (op_x0 - jamb_w, op_x1):
        tag(box(bm, sx, sx + jamb_w, -HALF_D - jamb_p, -HALF_D, sill_z, head_z), 0)
    # flat cornice lintel over the head
    tag(box(bm, op_x0 - jamb_w - 8, op_x1 + jamb_w + 8, -HALF_D - jamb_p - 6, -HALF_D,
            head_z, head_z + 26), 0)
    tag(box(bm, op_x0 - 10, op_x1 + 10, -HALF_D - 14.0, -HALF_D, sill_z - 12.0, sill_z), 0)  # sill
    _juliet_balcony(bm, op_x0, op_x1, sill_z, rail_h=88.0)
    tag(box(bm, -HALF_W, HALF_W, -HALF_D - 16.0, -HALF_D - 12.0, sill_z - 4, sill_z + 2), 1)  # iron band
    _string_course(bm, floor_h - 18.0, proud=10.0, h=18.0, mat=0)
    return bm_to_obj(bm, "mod_window_c")


def m_window_d(floor_h=FLOOR_H):
    """Rectangular window + SEGMENTAL (flattened-arch) pediment + STONE
    BALUSTRADE. The richest variant — flattened-arch head molding with a
    keystone and a turned-stone balustrade in front of the sill."""
    bm = bmesh.new()
    op_x0, op_x1 = -116.0, 116.0
    sill_z   = 105.0
    head_z   = floor_h - 120.0
    _window_body(bm, op_x0, op_x1, sill_z, head_z, floor_h)
    _glass(bm, op_x0, op_x1, sill_z, head_z)
    jamb_w, jamb_p = 16.0, 12.0
    for sx in (op_x0 - jamb_w, op_x1):
        tag(box(bm, sx, sx + jamb_w, -HALF_D - jamb_p, -HALF_D, sill_z, head_z), 0)
    # SEGMENTAL (flattened) arch pediment over the head
    segmental_band(bm, op_x0 - jamb_w, op_x1 + jamb_w, -HALF_D - jamb_p, -HALF_D,
                   head_z, 60.0, n=18, mat=0)
    tag(box(bm, -18.0, 18.0, -HALF_D - jamb_p - 10.0, -HALF_D, head_z - 10.0, head_z + 56.0), 0)  # keystone
    tag(box(bm, op_x0 - 12, op_x1 + 12, -HALF_D - 14.0, -HALF_D, sill_z - 12.0, sill_z), 0)       # sill
    _balustrade(bm, op_x0, op_x1, sill_z, rail_h=72.0)
    _string_course(bm, floor_h - 18.0, proud=12.0, h=18.0, mat=0)
    return bm_to_obj(bm, "mod_window_d")


# ---------------------------------------------------------------------------
# CORNER VARIANTS  (symbol C)
# ---------------------------------------------------------------------------
def m_corner_a():
    """Plain quoin corner — smooth stacked quoin blocks up a flat pier (no heavy
    rustication). The clean corner. Stone-only."""
    bm = bmesh.new()
    tag(box(bm, -HALF_W, HALF_W, -HALF_D, HALF_D, 0, FLOOR_H), 0)
    pier_hw, pier_p = 58.0, 12.0
    tag(box(bm, -pier_hw, pier_hw, -HALF_D - pier_p, -HALF_D, 0, FLOOR_H), 0)
    z = 0.0
    block_h = 50.0
    while z < FLOOR_H - 5:
        tag(box(bm, -pier_hw - 4, pier_hw + 4, -HALF_D - pier_p - 4.0, -HALF_D - pier_p,
                z + 5, z + block_h - 5), 0)
        z += block_h
    _string_course(bm, FLOOR_H - 18.0, proud=10.0, h=18.0, mat=0)
    return bm_to_obj(bm, "mod_corner_a")


def m_corner_b():
    """Rusticated quoin corner — alternating proud wide/narrow rusticated quoin
    blocks on a deeper pier (heavy fortified read). Stone-only."""
    bm = bmesh.new()
    tag(box(bm, -HALF_W, HALF_W, -HALF_D, HALF_D, 0, FLOOR_H), 0)
    pier_hw, pier_p = 60.0, 16.0
    tag(box(bm, -pier_hw, pier_hw, -HALF_D - pier_p, -HALF_D, 0, FLOOR_H), 0)
    z = 0.0
    block_h = 50.0
    i = 0
    while z < FLOOR_H - 5:
        w = pier_hw + (18.0 if i % 2 == 0 else 0.0)
        tag(box(bm, -w, w, -HALF_D - pier_p - 6.0, -HALF_D - pier_p, z + 4, z + block_h - 4), 0)
        z += block_h
        i += 1
    _string_course(bm, FLOOR_H - 18.0, proud=12.0, h=18.0, mat=0)
    return bm_to_obj(bm, "mod_corner_b")


# ---------------------------------------------------------------------------
# GROUND  (kept from the base kit) + MANSARD ROOF (top course)
# ---------------------------------------------------------------------------
def m_ground(floor_h=GROUND_H):
    """Rusticated tall arched ground-floor / lobby (kept from the base kit)."""
    bm = bmesh.new()
    op_x0, op_x1 = -110.0, 110.0
    spring_z = floor_h - 230.0
    head_z   = floor_h - 90.0
    for (mx0, mx1) in ((-HALF_W, op_x0), (op_x1, HALF_W)):
        tag(box(bm, mx0, mx1, -HALF_D, HALF_D, 0, floor_h), 0)
    tag(box(bm, op_x0, op_x1, -HALF_D, HALF_D, head_z, floor_h), 0)
    tag(box(bm, op_x0 + 6, op_x1 - 6, HALF_D - 8, HALF_D - 6, 0, spring_z + 30), 1)
    arch_band(bm, op_x0 - 14, op_x1 + 14, -HALF_D - 14.0, -HALF_D, spring_z, head_z, n=12, mat=0)
    tag(box(bm, -22.0, 22.0, -HALF_D - 22.0, -HALF_D, head_z - 40.0, head_z + 28.0), 0)
    z = 60.0
    while z < floor_h - 90:
        tag(box(bm, -HALF_W, HALF_W, -HALF_D - 4.0, -HALF_D, z - 5.0, z + 5.0), 0)
        z += 60.0
    tag(box(bm, -HALF_W, HALF_W, -HALF_D - 22.0, -HALF_D, floor_h - 40.0, floor_h - 8.0), 0)
    _string_course(bm, floor_h - 8.0, proud=24.0, h=8.0, mat=0)
    return bm_to_obj(bm, "mod_ground")


def m_mansard(floor_h=MANSARD_H):
    """Proper MANSARD ROOF course — steep battered dark-ZINC slope with THREE
    arched stone DORMER windows poking through the front, a stone cornice at the
    base, and a flat zinc ridge cap. Sits as the TOP course of the building.
    Base-pivoted (0..MANSARD_H), X-centered 400cm so it tiles as the roof slice.
    Zinc = mat 1, stone cornice/dormers = mat 0."""
    bm = bmesh.new()
    top_inset = 120.0
    yb1 = HALF_D
    # stone base cornice (the building's main cornice) — proud in -Y, within +/-HALF_W
    tag(box(bm, -HALF_W, HALF_W, -HALF_D - 26.0, HALF_D, 0, 40.0), 0)
    # steep battered zinc roof slab: wider at base, narrower + leaning back at top
    z0, z1 = 40.0, floor_h - 30.0
    fx0, fx1 = -HALF_W, HALF_W
    tx0, tx1 = -HALF_W + 70, HALF_W - 70
    fy_base = -HALF_D
    fy_top  = -HALF_D + top_inset
    v = [bm.verts.new((fx0, fy_base, z0)), bm.verts.new((fx1, fy_base, z0)),
         bm.verts.new((tx1, fy_top,  z1)), bm.verts.new((tx0, fy_top,  z1))]
    vb = [bm.verts.new((fx0, yb1, z0)), bm.verts.new((fx1, yb1, z0)),
          bm.verts.new((tx1, yb1, z1)), bm.verts.new((tx0, yb1, z1))]
    faces = []
    faces.append(bm.faces.new((v[0], v[1], v[2], v[3])))      # front sloped
    faces.append(bm.faces.new((vb[3], vb[2], vb[1], vb[0])))  # back
    faces.append(bm.faces.new((v[0], v[3], vb[3], vb[0])))    # left
    faces.append(bm.faces.new((v[1], vb[1], vb[2], v[2])))    # right
    faces.append(bm.faces.new((v[0], vb[0], vb[1], v[1])))    # bottom
    tag(faces, 1)  # zinc
    # flat zinc ridge cap on top (closes the roof, base-pivoted to MANSARD_H)
    tag(box(bm, tx0, tx1, fy_top, yb1, z1, floor_h), 1)
    # THREE arched stone dormers poking through the front slope (variety on the roofline)
    for cx in (-120.0, 0.0, 120.0):
        dz0, dz1 = z0 + 55.0, z0 + 175.0
        dw = 46.0
        dy = fy_base - 18.0
        tag(box(bm, cx - dw, cx + dw, dy, fy_base + 30.0, dz0, dz1), 0)             # dormer stone body
        arch_band(bm, cx - dw, cx + dw, dy - 6.0, dy, dz1, dz1 + 44.0, n=14, mat=0, ring=False)  # arched pediment
        tag(box(bm, cx - dw + 10, cx + dw - 10, dy + 2, dy + 4, dz0 + 14, dz1), 1)  # dormer dark glass
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
# (name, symbol, desc, builder, floor_h)
MODULES = [
    ("mod_wall_a",   "W",  "Plain limestone ashlar wall (blank bay)",                m_wall_a,   FLOOR_H),
    ("mod_wall_b",   "W",  "Ashlar wall + proud string course",                      m_wall_b,   FLOOR_H),
    ("mod_wall_c",   "W",  "Rusticated wall (deep banded joints) + string course",   m_wall_c,   FLOOR_H),
    ("mod_wall_d",   "W",  "Pilastered wall (2 pilasters + capitals + panel)",       m_wall_d,   FLOOR_H),
    ("mod_window_a", "W1", "Arched French window + architrave + keystone",           m_window_a, FLOOR_H),
    ("mod_window_b", "W1", "Rect window + triangular pediment on consoles",          m_window_b, FLOOR_H),
    ("mod_window_c", "W2", "Rect window + wrought-iron Juliet balcony",              m_window_c, FLOOR_H),
    ("mod_window_d", "W2", "Rect window + segmental pediment + stone balustrade",     m_window_d, FLOOR_H),
    ("mod_corner_a", "C",  "Plain quoin corner pier",                                m_corner_a, FLOOR_H),
    ("mod_corner_b", "C",  "Rusticated quoin corner pier",                           m_corner_b, FLOOR_H),
    ("mod_ground",   "ground W1", "Rusticated tall arched ground-floor / lobby",     m_ground,   GROUND_H),
    ("mod_mansard",  "Roof", "Steep dark-zinc mansard roof + 3 arched dormers",      m_mansard,  MANSARD_H),
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
    finalize(obj, name, stone, iron)
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
with open(os.path.join(ROOT, "_variants_stats.json"), "w") as f:
    json.dump(results, f, indent=2)

# ---- montage of all variant previews ----
try:
    import bpy
    # Build a montage by compositing the PNGs in a grid via a fresh scene render.
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
        # downscale by simple stride to fit the cell
        sy = max(1, h // cell_h)
        sx = max(1, w // cell_w)
        small = px[::sy, ::sx][:cell_h, :cell_w]
        sh, sw = small.shape[:2]
        cr = i // cols
        cc = i % cols
        # PNG rows are bottom-up; place row from top
        y0 = (rows - 1 - cr) * cell_h
        x0 = cc * cell_w
        canvas[y0:y0 + sh, x0:x0 + sw] = small
        bpy.data.images.remove(img)
    montage.pixels = canvas.flatten().tolist()
    montage.filepath_raw = os.path.join(BASE_ROOT, "beaux_arts_variants_montage.png")
    montage.file_format = "PNG"
    montage.save()
    print("MONTAGE ->", montage.filepath_raw)
except Exception as e:
    print("MONTAGE FAILED:", e)

print("ALL VARIANTS DONE:", len(results))
