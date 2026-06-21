"""Headless Blender generator for a FUTURISTIC modular building kit that drops
directly into Epic's PCG building-grammar generator (PCG_Building_CitySample /
PCG_BuildingSample).

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python futuristic_kit_jobs.py

WHY THE CITY SAMPLE CH KIT FAILED (and why we match the spec exactly):
The generator's ExtractMeshInfo subgraph computes each module's horizontal
  Size       = $Extents.X * 2      (i.e. WIDTH must run along LOCAL +X, CENTERED)
  PivotOffset = -$LocalCenter      (XY centered, Z base-pivoted, min.z = 0)
So every module MUST be:
  - WIDTH along local X, CENTERED on X  -> X spans -halfW .. +halfW
  - DEPTH along Y, shallow, centered on Y
  - HEIGHT along Z, base-pivoted        -> Z spans 0 .. floorH
The native PCG_Wall is X +/-100 (200cm wide), Y +/-10 (thin), Z 0..300.
We pick a CONSISTENT module width and floor height so everything tiles:
  MODULE_W = 400 cm   (Extents.X = 200 -> Size = 400)
  FLOOR_H  = 400 cm   (Z 0..400)
  DEPTH    = 24 cm    (shallow facade panel; centered Y -12..+12)

All units are CENTIMETERS in Blender here (NOT meters) so the FBX exports 1:1 to
UE cm with FBX_SCALE_NONE. The generator scales Z to floor height at spawn and
transforms PivotOffset by $Transform, so base-pivoted + X-centered is mandatory.

KIT (FBX each, to ~/coding/unreal-agent-harness/assets/futuristic_kit/):
  mod_wall.fbx   - solid futuristic spandrel wall panel (sleek metal)         -> symbol W
  mod_window.fbx - glass curtain-wall panel with mullions (main facade unit)  -> symbol W1 / W2
  mod_corner.fbx - metal corner column / chamfer that closes the box          -> symbol C
  mod_column.fbx - vertical mullion / pilaster                                 -> symbol (column)
  mod_ground.fbx - taller ground-floor / lobby variant (full-height glazing)  -> ground W1

Material slots (consistent across all modules so UE / M_TowerGlass apply):
  slot 0 = Glass   (curtain wall, dark blue, metallic)
  slot 1 = Frame   (thin metal frame / mullion / spandrel / column)
"""
import bpy, bmesh, os, math, mathutils

ROOT = os.path.expanduser("~/coding/unreal-agent-harness/assets/futuristic_kit")
os.makedirs(ROOT, exist_ok=True)

# ---- THE MODULE SPEC (cm) -------------------------------------------------
MODULE_W = 400.0          # width along local X, CENTERED -> X in [-200, +200]
HALF_W   = MODULE_W / 2.0 # 200  (Extents.X -> generator Size = HALF_W*2 = 400)
FLOOR_H  = 400.0          # height along Z, base-pivoted -> Z in [0, 400]
DEPTH    = 24.0           # shallow facade depth along Y, centered -> Y in [-12, +12]
HALF_D   = DEPTH / 2.0    # 12
GROUND_H = 600.0          # taller lobby floor variant


# ---------------------------------------------------------------------------
# scene / material / finalize helpers
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
    """slot 0 = glass curtain wall, slot 1 = frame / metal mullion."""
    glass = bpy.data.materials.new("M_Glass")
    glass.use_nodes = True
    b = glass.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = (0.10, 0.42, 0.62, 1.0)
        b.inputs["Metallic"].default_value = 0.80
        b.inputs["Roughness"].default_value = 0.08
        if "Emission Color" in b.inputs:
            b.inputs["Emission Color"].default_value = (0.05, 0.22, 0.35, 1.0)
            b.inputs["Emission Strength"].default_value = 0.6
    frame = bpy.data.materials.new("M_Frame")
    frame.use_nodes = True
    b = frame.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = (0.82, 0.85, 0.88, 1.0)
        b.inputs["Metallic"].default_value = 0.95
        b.inputs["Roughness"].default_value = 0.28
    return glass, frame


def bm_to_obj(bm, name):
    me = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    return obj


def box(bm, x0, x1, y0, y1, z0, z1):
    """Axis-aligned box, return list of 6 faces (for material tagging)."""
    v = [bm.verts.new((x, y, z))
         for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    # index: bit0=x, bit1=y, bit2=z
    def V(ix, iy, iz):
        return v[iz * 4 + iy * 2 + ix]
    faces = []
    faces.append(bm.faces.new((V(0,0,0), V(1,0,0), V(1,1,0), V(0,1,0))))  # bottom
    faces.append(bm.faces.new((V(0,0,1), V(0,1,1), V(1,1,1), V(1,0,1))))  # top
    faces.append(bm.faces.new((V(0,0,0), V(0,1,0), V(0,1,1), V(0,0,1))))  # -X
    faces.append(bm.faces.new((V(1,0,0), V(1,0,1), V(1,1,1), V(1,1,0))))  # +X
    faces.append(bm.faces.new((V(0,0,0), V(0,0,1), V(1,0,1), V(1,0,0))))  # -Y (front)
    faces.append(bm.faces.new((V(0,1,0), V(1,1,0), V(1,1,1), V(0,1,1))))  # +Y (back)
    return faces


def finalize(obj, name, glass, frame, half_w=HALF_W, floor_h=FLOOR_H):
    """2 mat slots, UV, normals out, then FORCE exact bounds:
    X centered [-half_w, half_w], Y centered, Z base [0, floor_h].
    We do NOT recenter by bbox here (geometry is authored to spec); we just
    set origin to world (0,0,0) which is the base-center by construction."""
    me = obj.data
    me.materials.clear()
    me.materials.append(glass)  # slot 0
    me.materials.append(frame)  # slot 1
    obj.name = name
    me.name = name + "_mesh"

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    # normals outward
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    # UVs
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")

    # origin to world origin (= base-center by construction)
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    return obj


def verify_bounds(obj, label, exp_half_w=HALF_W, exp_floor_h=FLOOR_H, tol=0.5):
    """Assert X-centered width, shallow Y, base-pivoted Z. Print + flag."""
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
    status = "OK" if (ok_xcenter and ok_width and ok_basez and ok_height and ok_ycenter) else "**FAIL**"
    print(f"[BOUNDS {status}] {label}: "
          f"X[{minx:.1f},{maxx:.1f}] w={w:.1f} (Xcenter={ok_xcenter} width={ok_width}) | "
          f"Y[{miny:.1f},{maxy:.1f}] (Ycenter={ok_ycenter}) | "
          f"Z[{minz:.1f},{maxz:.1f}] (base={ok_basez} height={ok_height})")
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
# the modules
# ---------------------------------------------------------------------------

def m_wall(floor_h=FLOOR_H):
    """Solid futuristic spandrel wall panel (anti-banding rebuild).

    Old version had a recessed glass STRIP BAND across the front in the upper
    third -> a per-floor horizontal accent that reinforced the stacked-plate read.
    NEW: a clean metal spandrel slab with FULL-HEIGHT proud VERTICAL seams (they
    align across floors = tall read) and only a thin spandrel line at the top
    floor break. The vertical glass slivers (between the seams) run full height so
    stacked walls read as continuous vertical ribbons, not horizontal bands."""
    bm = bmesh.new()
    spand_t = 6.0
    # main metal spandrel slab (frame metal)
    f = box(bm, -HALF_W, HALF_W, -HALF_D, HALF_D, 0, floor_h)
    for face in f:
        face.material_index = 1  # frame metal
    # full-height vertical glass slivers (reads as recessed glazing ribbons)
    for sx in (-HALF_W * 0.55, HALF_W * 0.0, HALF_W * 0.55):
        gf = box(bm, sx - 26, sx + 26, -HALF_D, -HALF_D + 3.0, spand_t, floor_h - spand_t)
        for face in gf:
            face.material_index = 0  # glass ribbon
    # full-height proud vertical metal seams flanking the slivers (align across floors)
    for sx in (-HALF_W * 0.78, -HALF_W * 0.30, HALF_W * 0.30, HALF_W * 0.78):
        sf = box(bm, sx - 4, sx + 4, -HALF_D, -HALF_D + 4.0, 0, floor_h)
        for face in sf:
            face.material_index = 1
    # thin spandrel line at the top only (single thin floor join)
    sp = box(bm, -HALF_W, HALF_W, -HALF_D, -HALF_D + 6.0, floor_h - spand_t, floor_h)
    for face in sp:
        face.material_index = 1
    return bm_to_obj(bm, "mod_wall")


def m_window(floor_h=FLOOR_H, ground=False):
    """CONTINUOUS-GLASS curtain-wall panel (anti-banding rebuild).

    The old design had a full frame RING (left/right jambs + a head bar AND a
    sill bar) plus a mid horizontal transom. Stacked floor-on-floor, the sill of
    floor N met the head of floor N+1 -> a ~32cm double dark band at every floor
    line, and the mid transom added a second band per floor. The tower read as a
    stack of waffle plates, not a smooth glass wall.

    NEW: glass runs the FULL module height edge-to-edge in Z (no head, no sill,
    no transom), so vertically-adjacent panes butt into one continuous sheet.
    The ONLY horizontal element is a THIN spandrel line at the very top of the
    module -> a single thin mullion at each floor join (real curtain-wall look),
    not a heavy plate edge. Vertical mullions (jambs + center) stay and ALIGN
    across floors, reinforcing the tall read. Verticals are the dominant lines."""
    bm = bmesh.new()
    jamb_t  = 11.0        # left/right vertical jamb thickness (vertical = OK, tall read)
    mull_t  = 8.0         # center vertical mullion thickness
    spand_t = 6.0         # THIN spandrel line at the floor break (was 16cm head+16cm sill)
    # left + right vertical jambs, full height (these line up across floors)
    for sx in (-HALF_W, HALF_W - jamb_t):
        ff = box(bm, sx, sx + jamb_t, -HALF_D, HALF_D, 0, floor_h)
        for face in ff:
            face.material_index = 1
    # glass pane: FULL height (0..floor_h), recessed in Y so jambs/mullions read proud.
    # No head/sill -> stacked panes read continuous; only the thin top spandrel breaks them.
    gx0, gx1 = -HALF_W + jamb_t, HALF_W - jamb_t
    gz0, gz1 = 0.0, floor_h
    gy0, gy1 = -HALF_D + 5.0, HALF_D - 5.0
    gf = box(bm, gx0, gx1, gy0, gy1, gz0, gz1)
    for face in gf:
        face.material_index = 0  # glass
    # central vertical mullion (proud of glass on the front), full height
    mf = box(bm, -mull_t / 2, mull_t / 2, -HALF_D, -HALF_D + 7.0, gz0, gz1)
    for face in mf:
        face.material_index = 1
    # ground variant gets one extra vertical mullion pair for a richer lobby grid
    if ground:
        for sx in (-HALF_W * 0.5, HALF_W * 0.5):
            mf2 = box(bm, sx - mull_t / 2, sx + mull_t / 2, -HALF_D, -HALF_D + 7.0, gz0, gz1)
            for face in mf2:
                face.material_index = 1
    # THIN spandrel line at the TOP only (proud, shallow) -> single thin floor line
    sp = box(bm, -HALF_W, HALF_W, -HALF_D, -HALF_D + 6.0, floor_h - spand_t, floor_h)
    for face in sp:
        face.material_index = 1
    return bm_to_obj(bm, "mod_window_ground" if ground else "mod_window")


def m_corner():
    """Corner piece: a sturdy metal corner COLUMN that closes the box cleanly at
    90 degrees. Occupies the SAME module width footprint (X centered +/-HALF_W)
    so the grammar tiles it like any other module; the visible column sits at the
    panel center as a vertical chamfered pier, with thin glass return slivers so
    it reads as a glazed corner mullion, not a brick quoin."""
    bm = bmesh.new()
    col_hw = 34.0   # column half-width
    # main chamfered column (octagonal pier) centered, base-pivoted
    ring = []
    r = col_hw
    c = r * 0.41  # chamfer
    pts = [(-r, -c), (-c, -r), (c, -r), (r, -c),
           (r, c), (c, r), (-c, r), (-r, c)]
    bottom = [bm.verts.new((x, y, 0.0)) for (x, y) in pts]
    top = [bm.verts.new((x, y, FLOOR_H)) for (x, y) in pts]
    bm.faces.new(bottom)
    bm.faces.new(list(reversed(top)))
    n = len(pts)
    side_faces = []
    for i in range(n):
        side_faces.append(bm.faces.new(
            (bottom[i], bottom[(i + 1) % n], top[(i + 1) % n], top[i])))
    obj_faces = [f for f in bm.faces]
    for f in obj_faces:
        f.material_index = 1  # all metal column

    # thin glass return slivers flanking the column to bridge to neighbor panels
    for sx in (-HALF_W, HALF_W - 26.0):
        gf = box(bm, sx, sx + 26.0, -HALF_D + 4.0, HALF_D - 4.0,
                 FLOOR_H * 0.05, FLOOR_H * 0.95)
        for face in gf:
            face.material_index = 0
    return bm_to_obj(bm, "mod_corner")


def m_column():
    """Vertical mullion / pilaster: a slim metal pier the grammar can place as a
    column symbol. Centered on X, base-pivoted, shallow."""
    bm = bmesh.new()
    cw = 26.0   # full width of the pier
    cd = 30.0   # depth (sticks a bit proud)
    f = box(bm, -cw / 2, cw / 2, -cd / 2, cd / 2, 0, FLOOR_H)
    for face in f:
        face.material_index = 1
    # a thin emissive-ready glass spine groove down the front (within depth env)
    gf = box(bm, -4, 4, -cd / 2, -cd / 2 + 3.0, FLOOR_H * 0.06, FLOOR_H * 0.94)
    for face in gf:
        face.material_index = 0
    return bm_to_obj(bm, "mod_column")


# ---------------------------------------------------------------------------
# render preview
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
        bg.inputs[0].default_value = (0.11, 0.13, 0.17, 1.0)
        bg.inputs[1].default_value = 1.4


def add_cam_and_lights(half_w, floor_h):
    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam_data.lens = 55
    cam_data.clip_start = 1.0
    cam_data.clip_end = 1.0e6
    extent = max(half_w * 2, floor_h)
    dist = extent * 2.0
    # stronger 3/4 angle so the proud mullions / frame depth read
    cam.location = (dist * 0.95, -dist * 0.95, floor_h * 0.58 + extent * 0.18)
    target = mathutils.Vector((0, 0, floor_h * 0.5))
    direction = target - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam

    key = bpy.data.lights.new("Key", "SUN")
    key.energy = 4.5
    ko = bpy.data.objects.new("Key", key)
    ko.rotation_euler = (math.radians(52), math.radians(12), math.radians(35))
    bpy.context.collection.objects.link(ko)
    rim = bpy.data.lights.new("Rim", "SUN")
    rim.energy = 2.2
    rim.color = (0.55, 0.72, 1.0)
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

# (file, desc, builder, floor_h, expected_half_width)
# Tiling modules share MODULE_W (HALF_W). The column is intentionally a SLIM
# pier symbol, so it carries its own narrow expected width.
MODULES = [
    ("mod_wall",          "Solid futuristic spandrel wall (metal + glass strip)", lambda: m_wall(),          FLOOR_H, HALF_W),
    ("mod_window",        "Glass curtain-wall panel w/ mullions (main facade)",   lambda: m_window(),         FLOOR_H, HALF_W),
    ("mod_corner",        "Metal corner column / chamfer (closes the box)",       lambda: m_corner(),         FLOOR_H, HALF_W),
    ("mod_column",        "Slim metal mullion / pilaster column",                 lambda: m_column(),         FLOOR_H, 13.0),
    ("mod_window_ground", "Taller ground-floor lobby glazing variant",           lambda: m_window(GROUND_H, ground=True), GROUND_H, HALF_W),
]

# FBX UNIT FIX: our vertex numbers are in centimeters. UE expects FBX authored in
# cm and imports 1:1 ONLY if the FBX declares its unit as centimeters. Blender's
# default scene unit is METERS, so a cm-magnitude scene gets tagged as meters and
# UE multiplies by 100 on import (the 400cm module came in as 400m = 40000cm).
# Set the scene unit to centimeters so the exported FBX carries the cm unit and
# UE imports at true size. (scale_length 0.01 => 1 Blender unit = 1 cm.)
us = bpy.context.scene.unit_settings
us.system = "METRIC"
us.scale_length = 0.01
us.length_unit = "CENTIMETERS"

results = []
setup_render()

for fname, desc, builder, fh, ehw in MODULES:
    reset_scene()
    setup_render()
    glass, frame = make_mats()
    obj = builder()
    finalize(obj, fname, glass, frame, floor_h=fh)
    b = verify_bounds(obj, fname, exp_half_w=ehw, exp_floor_h=fh)

    me = obj.data
    me.calc_loop_triangles()
    tris = len(me.loop_triangles)

    # preview render
    add_cam_and_lights(HALF_W, fh)
    png = os.path.join(ROOT, fname + ".png")
    bpy.context.scene.render.filepath = png
    bpy.ops.render.render(write_still=True)

    fbx = export_fbx(obj, fname)
    results.append({"file": fname, "desc": desc, "tris": tris, "bounds": b,
                    "floor_h": fh})
    print(f"DONE {fname}: {desc} | tris={tris} -> {fbx}")

import json
with open(os.path.join(ROOT, "_stats.json"), "w") as f:
    json.dump(results, f, indent=2)

print("ALL MODULES DONE:", len(results))
