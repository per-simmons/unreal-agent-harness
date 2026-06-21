"""Headless Blender generator for a BEAUX-ARTS / HAUSSMANN PARISIAN modular
building kit that drops directly into Epic's PCG building-grammar generator
(PCG_Building_CitySample / PCG_BuildingSample → ExtractMeshInfo).

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python beaux_arts_kit_jobs.py

WHY WE MATCH THE SPEC EXACTLY (same as the futuristic kit — non-negotiable):
The generator's ExtractMeshInfo subgraph computes each module's horizontal
  Size        = $Extents.X * 2      (i.e. WIDTH must run along LOCAL +X, CENTERED)
  PivotOffset = -$LocalCenter       (XY centered, Z base-pivoted, min.z = 0)
So every module MUST be:
  - WIDTH along local X, CENTERED on X  -> X spans -HALF_W .. +HALF_W
  - DEPTH along Y, shallow, centered on Y
  - HEIGHT along Z, base-pivoted        -> Z spans 0 .. floorH
The native PCG_Wall is X +/-100 (200cm wide), Y +/-10 (thin), Z 0..300.
We pick a CONSISTENT module width + floor height so everything tiles:
  MODULE_W = 400 cm   (Extents.X = 200 -> Size = 400)
  FLOOR_H  = 400 cm   (Z 0..400)  -- tall, grand Haussmann floors
  DEPTH    = 30 cm    (shallow facade panel; a touch deeper than futuristic to
                       carry the stone relief / cornices; centered Y -15..+15)

UNIT FIX (learned the hard way — see PCG-GUIDE iter4): Blender's default scene
unit is METERS, so a cm-magnitude scene gets tagged as meters and UE multiplies
by 100 on import (a 400cm module came in as 40000cm = 400m). We set the scene
unit to CENTIMETERS and export with apply_scale_options='FBX_SCALE_ALL' +
apply_unit_scale=True so the FBX carries the cm unit and UE imports 1:1.
ALWAYS get_bounds 1-2 modules right after import to confirm.

STYLE = Beaux-Arts / Haussmann Paris:
  cream limestone walls, tall arched/French windows with decorative surrounds,
  wrought-iron Juliet balconies + a continuous balcony band, cornices / string
  courses between floors, rusticated ground floor, ornamental keystones, a steep
  dark-zinc MANSARD roof variant for the top.

KIT (FBX each, to ~/coding/unreal-agent-harness/assets/beaux_arts_kit/):
  mod_wall.fbx    - plain limestone ashlar wall + string course   -> symbol W
  mod_window.fbx  - ornate French-window facade unit (arch +       -> symbol W1 / W2
                    surround + keystone + Juliet balcony + cornice)
  mod_corner.fbx  - rusticated limestone quoined corner pier       -> symbol C
  mod_ground.fbx  - rusticated ground-floor / lobby (tall arched)  -> ground W1
  mod_mansard.fbx - steep dark-zinc mansard roof cap + dormer      -> roof cap

Material slots (consistent across all modules):
  slot 0 = Stone   (cream limestone, matte)
  slot 1 = Iron    (wrought-iron / dark zinc / metal trim)
"""
import bpy, bmesh, os, math, mathutils

ROOT = os.path.expanduser("~/coding/unreal-agent-harness/assets/beaux_arts_kit")
os.makedirs(ROOT, exist_ok=True)

# ---- THE MODULE SPEC (cm) -------------------------------------------------
MODULE_W = 400.0          # width along local X, CENTERED -> X in [-200, +200]
HALF_W   = MODULE_W / 2.0 # 200  (Extents.X -> generator Size = HALF_W*2 = 400)
FLOOR_H  = 400.0          # height along Z, base-pivoted -> Z in [0, 400]
DEPTH    = 30.0           # shallow facade depth along Y, centered -> Y in [-15, +15]
HALF_D   = DEPTH / 2.0    # 15
GROUND_H = 600.0          # taller rusticated lobby floor variant
MANSARD_H = 350.0         # mansard roof-cap height


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
    """slot 0 = cream limestone, slot 1 = wrought-iron / dark zinc / trim."""
    stone = bpy.data.materials.new("M_Stone")
    stone.use_nodes = True
    b = stone.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = (0.78, 0.72, 0.58, 1.0)  # cream limestone
        b.inputs["Metallic"].default_value = 0.0
        b.inputs["Roughness"].default_value = 0.78
    iron = bpy.data.materials.new("M_Iron")
    iron.use_nodes = True
    b = iron.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = (0.06, 0.06, 0.07, 1.0)  # near-black wrought iron / zinc
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
    """Axis-aligned box, return list of 6 faces (for material tagging)."""
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
    return faces


def tag(faces, idx):
    for f in faces:
        f.material_index = idx


def arch_band(bm, x0, x1, y0, y1, z_spring, z_top, n=28, mat=0, ring=True):
    """A semicircular arch over an opening from x0..x1, springing at z_spring up
    to z_top, extruded in Y (y0..y1). With ring=True it's a proud ARCH MOLDING
    (a constant-thickness arc surround, the round read); with ring=False it's a
    solid filled tympanum half-disc. n high = smooth curve (no stair-stepping)."""
    cx = (x0 + x1) / 2.0
    rx = (x1 - x0) / 2.0
    rz = (z_top - z_spring)
    band = min(rx, rz) * 0.34          # radial thickness of the molding
    prev = None
    for i in range(n + 1):
        t = i / n
        ang = math.pi * t              # 0..pi across the top
        x = cx - rx * math.cos(ang)
        z = z_spring + rz * math.sin(ang)
        if prev is not None:
            px, pz = prev
            if ring:
                # thin slab tile following the arc (constant width band)
                f = box(bm, min(px, x) - 3, max(px, x) + 3, y0, y1,
                        max(z, pz) - band, max(z, pz))
            else:
                f = box(bm, min(px, x), max(px, x), y0, y1, z_spring, max(z, pz))
            tag(f, mat)
        prev = (x, z)


# ---------------------------------------------------------------------------
# finalize / verify
# ---------------------------------------------------------------------------

def finalize(obj, name, stone, iron):
    """2 mat slots (0=stone, 1=iron), UV, normals out, origin to world (0,0,0)
    which is base-center by construction."""
    me = obj.data
    me.materials.clear()
    me.materials.append(stone)  # slot 0
    me.materials.append(iron)   # slot 1
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

    # Recenter geometry on Y so the bounding box is Y-centered (proud relief is
    # authored only on -Y; the generator centers XY via PivotOffset=-$LocalCenter,
    # so a Y-centered bbox keeps the facade plane predictable + passes verify).
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


def verify_bounds(obj, label, exp_half_w=HALF_W, exp_floor_h=FLOOR_H, tol=0.5):
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

def _string_course(bm, z, proud=8.0, h=14.0, mat=0):
    """A continuous horizontal stone string course / cornice band running the
    full module width, proud of the wall in -Y. Aligns across modules."""
    f = box(bm, -HALF_W, HALF_W, -HALF_D - proud, -HALF_D, z, z + h)
    tag(f, mat)


def m_wall(floor_h=FLOOR_H):
    """Plain limestone ashlar wall panel: a solid stone slab with a subtle
    horizontal string course at the floor line and faint ashlar coursing
    (proud horizontal stone joints). Reads as a quiet limestone bay between the
    ornate windows. Stone-only (mat 0)."""
    bm = bmesh.new()
    # main limestone slab
    f = box(bm, -HALF_W, HALF_W, -HALF_D, HALF_D, 0, floor_h)
    tag(f, 0)
    # faint ashlar coursing — proud horizontal joints every ~80cm
    course_h = 80.0
    z = course_h
    while z < floor_h - 10:
        j = box(bm, -HALF_W, HALF_W, -HALF_D - 2.0, -HALF_D, z - 2.5, z + 2.5)
        tag(j, 0)
        z += course_h
    # string course / cornice at the top (floor join) — proud stone band
    _string_course(bm, floor_h - 18.0, proud=10.0, h=18.0, mat=0)
    return bm_to_obj(bm, "mod_wall")


def m_window(floor_h=FLOOR_H):
    """The ornate FRENCH-WINDOW facade unit — the signature Beaux-Arts bay.

    Stone wall with a tall, arched window opening, a decorative stone SURROUND
    (architrave jambs + a round arch head), an ornamental KEYSTONE at the crown,
    a wrought-iron JULIET BALCONY railing in front of the sill, the continuous
    iron balcony band, and a stone CORNICE / string course at the floor line.
    The glass plane is a recessed dark pane. Stone = mat 0, iron = mat 1."""
    bm = bmesh.new()
    # ---- limestone wall body with a window void (build as 4 stone margins) ----
    op_x0, op_x1 = -120.0, 120.0          # window opening width
    sill_z       = 95.0                    # sill height
    spring_z     = floor_h - 150.0         # arch springing line
    head_z       = floor_h - 60.0          # arch crown
    # left + right wall margins
    for (mx0, mx1) in ((-HALF_W, op_x0), (op_x1, HALF_W)):
        tag(box(bm, mx0, mx1, -HALF_D, HALF_D, 0, floor_h), 0)
    # below-sill margin (spandrel under the opening)
    tag(box(bm, op_x0, op_x1, -HALF_D, HALF_D, 0, sill_z), 0)
    # above-arch margin (between crown and floor top)
    tag(box(bm, op_x0, op_x1, -HALF_D, HALF_D, head_z, floor_h), 0)
    # fill the arch corners (square shoulders left of the round head)
    arch_band_solid_shoulders = True

    # ---- recessed dark glass pane (sits behind the opening), up to the arch ----
    gy = -HALF_D + 4.0
    tag(box(bm, op_x0 + 8, op_x1 - 8, gy, gy + 2.0, sill_z, spring_z + 55), 1)  # iron-dark glass

    # ---- decorative stone SURROUND (architrave) — proud jambs + arch molding ----
    jamb_w = 16.0
    jamb_p = 12.0    # proud of wall
    for sx in (op_x0 - jamb_w, op_x1):
        tag(box(bm, sx, sx + jamb_w, -HALF_D - jamb_p, -HALF_D, sill_z, spring_z), 0)
    # round arch head MOLDING (a proud constant-thickness stone arc over the opening)
    arch_band(bm, op_x0 - jamb_w, op_x1 + jamb_w, -HALF_D - jamb_p, -HALF_D,
              spring_z, head_z, n=28, mat=0, ring=True)

    # ---- ornamental KEYSTONE straddling the crown (proud trapezoidal stone) ----
    tag(box(bm, -20.0, 20.0, -HALF_D - jamb_p - 10.0, -HALF_D, head_z - 70.0, head_z + 30.0), 0)

    # ---- stone sill (proud) ----
    tag(box(bm, op_x0 - 10, op_x1 + 10, -HALF_D - 14.0, -HALF_D, sill_z - 12.0, sill_z), 0)

    # ---- wrought-iron JULIET BALCONY (railing in front of the sill) ----
    bal_y0 = -HALF_D - 22.0
    bal_y1 = -HALF_D - 14.0
    rail_top = sill_z + 80.0
    # top + bottom rails
    tag(box(bm, op_x0 - 14, op_x1 + 14, bal_y0, bal_y1, sill_z + 2, sill_z + 8), 1)
    tag(box(bm, op_x0 - 14, op_x1 + 14, bal_y0, bal_y1, rail_top - 6, rail_top), 1)
    # vertical balusters
    bx = op_x0 - 6
    while bx <= op_x1 + 6:
        tag(box(bm, bx - 2.0, bx + 2.0, bal_y0, bal_y1, sill_z + 2, rail_top), 1)
        bx += 16.0

    # ---- continuous IRON balcony band across the whole module (aligns floor-to-floor) ----
    tag(box(bm, -HALF_W, HALF_W, -HALF_D - 16.0, -HALF_D - 12.0, sill_z - 4, sill_z + 2), 1)

    # ---- stone CORNICE / string course at the floor line (top) ----
    _string_course(bm, floor_h - 20.0, proud=12.0, h=20.0, mat=0)

    return bm_to_obj(bm, "mod_window")


def m_corner():
    """Corner pier: a RUSTICATED limestone quoined corner that closes the box.
    Occupies the SAME 400cm module footprint (X centered +/-HALF_W) so the
    grammar tiles it like any other module. The visible pier is a chamfered
    stone pilaster at panel center with proud QUOIN blocks stacked up the edge
    and a string course at the floor line. Stone-only (mat 0)."""
    bm = bmesh.new()
    # full-footprint thin backing wall so the box closes at the corner
    tag(box(bm, -HALF_W, HALF_W, -HALF_D, HALF_D, 0, FLOOR_H), 0)
    # central rusticated pier (proud of wall)
    pier_hw = 60.0
    pier_p  = 16.0
    tag(box(bm, -pier_hw, pier_hw, -HALF_D - pier_p, -HALF_D, 0, FLOOR_H), 0)
    # stacked QUOIN blocks — alternating wide/narrow proud stones up the pier edge
    z = 0.0
    block_h = 50.0
    i = 0
    while z < FLOOR_H - 5:
        w = pier_hw + (18.0 if i % 2 == 0 else 0.0)   # alternate proud width
        tag(box(bm, -w, w, -HALF_D - pier_p - 6.0, -HALF_D - pier_p, z + 4, z + block_h - 4), 0)
        z += block_h
        i += 1
    # string course at the floor line
    _string_course(bm, FLOOR_H - 18.0, proud=12.0, h=18.0, mat=0)
    return bm_to_obj(bm, "mod_corner")


def m_ground(floor_h=GROUND_H):
    """Rusticated GROUND-FLOOR / lobby unit (taller, 600cm). Heavy horizontal
    rustication (deep banded stone joints), a tall round-arched portal opening
    with a big keystone, and a heavy cornice/entablature at the top marking the
    base of the piano nobile. Stone = mat 0, iron-dark portal glass = mat 1."""
    bm = bmesh.new()
    op_x0, op_x1 = -110.0, 110.0
    spring_z = floor_h - 230.0
    head_z   = floor_h - 90.0
    # wall margins around the arched portal
    for (mx0, mx1) in ((-HALF_W, op_x0), (op_x1, HALF_W)):
        tag(box(bm, mx0, mx1, -HALF_D, HALF_D, 0, floor_h), 0)
    tag(box(bm, op_x0, op_x1, -HALF_D, HALF_D, head_z, floor_h), 0)   # above arch
    # recessed dark portal (iron-dark)
    tag(box(bm, op_x0 + 6, op_x1 - 6, HALF_D - 8, HALF_D - 6, 0, spring_z + 30), 1)
    # round arch head (proud stone)
    arch_band(bm, op_x0 - 14, op_x1 + 14, -HALF_D - 14.0, -HALF_D, spring_z, head_z, n=12, mat=0)
    # big keystone
    tag(box(bm, -22.0, 22.0, -HALF_D - 22.0, -HALF_D, head_z - 40.0, head_z + 28.0), 0)
    # HEAVY rustication — deep horizontal banded joints across the whole face
    z = 60.0
    while z < floor_h - 90:
        tag(box(bm, -HALF_W, HALF_W, -HALF_D - 4.0, -HALF_D, z - 5.0, z + 5.0), 0)
        z += 60.0
    # heavy cornice / entablature at the top (base of the piano nobile)
    tag(box(bm, -HALF_W, HALF_W, -HALF_D - 22.0, -HALF_D, floor_h - 40.0, floor_h - 8.0), 0)
    _string_course(bm, floor_h - 8.0, proud=24.0, h=8.0, mat=0)
    return bm_to_obj(bm, "mod_ground")


def m_mansard(floor_h=MANSARD_H):
    """Steep dark-ZINC MANSARD roof cap — the crowning module. A steeply battered
    (inward-sloping) roof slab in dark zinc with a single arched stone DORMER
    window poking through the front, and a stone cornice at its base. Sits on top
    of the building. Base-pivoted (z 0..MANSARD_H), X-centered 400cm so it tiles
    as the top course. Zinc = mat 1, stone cornice/dormer = mat 0."""
    bm = bmesh.new()
    base_inset = 0.0
    top_inset  = 120.0     # mansard batters inward toward the top
    yb0, yb1 = -HALF_D, HALF_D
    # stone cornice at the base of the mansard (the building's main cornice).
    # Keep X within +/-HALF_W so Extents.X stays 200 (Size=400); the cornice
    # projects in -Y (proud), NOT past the module width.
    tag(box(bm, -HALF_W, HALF_W, -HALF_D - 26.0, HALF_D, 0, 40.0), 0)
    # steep battered zinc roof slab (front face slopes inward going up) -- built
    # as a trapezoidal prism: wider at base, narrower at top, leaning back in -Y.
    z0, z1 = 40.0, floor_h
    fx0, fx1 = -HALF_W, HALF_W                       # base width (front)
    tx0, tx1 = -HALF_W + 70, HALF_W - 70             # top width (front, slightly narrower)
    # front sloping face: from (fx, base, y=-HALF_D) up to (tx, top, y=+something back)
    fy_base = -HALF_D
    fy_top  = -HALF_D + top_inset                    # leans back going up
    v = [
        bm.verts.new((fx0, fy_base, z0)), bm.verts.new((fx1, fy_base, z0)),
        bm.verts.new((tx1, fy_top,  z1)), bm.verts.new((tx0, fy_top,  z1)),
    ]
    # back face (vertical, at +Y)
    vb = [
        bm.verts.new((fx0, yb1, z0)), bm.verts.new((fx1, yb1, z0)),
        bm.verts.new((tx1, yb1, z1)), bm.verts.new((tx0, yb1, z1)),
    ]
    faces = []
    faces.append(bm.faces.new((v[0], v[1], v[2], v[3])))      # front sloped
    faces.append(bm.faces.new((vb[3], vb[2], vb[1], vb[0])))  # back
    faces.append(bm.faces.new((v[0], v[3], vb[3], vb[0])))    # left
    faces.append(bm.faces.new((v[1], vb[1], vb[2], v[2])))    # right
    faces.append(bm.faces.new((v[3], v[2], vb[2], vb[3])))    # top
    faces.append(bm.faces.new((v[0], vb[0], vb[1], v[1])))    # bottom
    tag(faces, 1)  # zinc
    # arched stone DORMER poking through the front slope
    dz0, dz1 = z0 + 60.0, z0 + 200.0
    dw = 55.0
    dy = fy_base - 18.0
    tag(box(bm, -dw, dw, dy, fy_base + 30.0, dz0, dz1), 0)            # dormer stone body (proud)
    arch_band(bm, -dw, dw, dy - 6.0, dy, dz1, dz1 + 50.0, n=16, mat=0, ring=False)  # dormer arched pediment
    tag(box(bm, -dw + 12, dw - 12, dy + 2, dy + 4, dz0 + 16, dz1), 1)  # dormer dark glass
    return bm_to_obj(bm, "mod_mansard")


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
        bg.inputs[0].default_value = (0.16, 0.18, 0.22, 1.0)  # dark slate (so cream stone reads)
        bg.inputs[1].default_value = 0.7


def add_cam_and_lights(half_w, floor_h):
    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam_data.lens = 55
    cam_data.clip_start = 1.0
    cam_data.clip_end = 1.0e6
    extent = max(half_w * 2, floor_h)
    dist = extent * 2.0
    cam.location = (dist * 0.9, -dist * 0.95, floor_h * 0.55 + extent * 0.18)
    target = mathutils.Vector((0, 0, floor_h * 0.5))
    direction = target - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam

    # Low raking key so the stone relief (cornices, balusters, rustication,
    # arch surround, keystone) casts legible shadows; soft cool fill.
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


def export_fbx(obj, fname):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    fbx = os.path.join(ROOT, fname + ".fbx")
    # UNIT FIX (PCG-GUIDE iter4): scene unit is cm + FBX_SCALE_ALL + apply_unit_scale
    # => FBX carries cm, UE imports 1:1 (NO 100x blow-up).
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
MODULES = [
    ("mod_wall",    "Limestone ashlar wall + string course",                       lambda: m_wall(),    FLOOR_H,   HALF_W),
    ("mod_window",  "Ornate French-window bay (arch+surround+keystone+balcony)",   lambda: m_window(),  FLOOR_H,   HALF_W),
    ("mod_corner",  "Rusticated quoined limestone corner pier (closes the box)",   lambda: m_corner(),  FLOOR_H,   HALF_W),
    ("mod_ground",  "Rusticated tall arched ground-floor / lobby",                 lambda: m_ground(),  GROUND_H,  HALF_W),
    ("mod_mansard", "Steep dark-zinc mansard roof cap + dormer",                   lambda: m_mansard(), MANSARD_H, HALF_W),
]

# FBX UNIT FIX: author the scene in CENTIMETERS so the export carries the cm
# unit and UE imports at true size (see header + PCG-GUIDE iter4).
us = bpy.context.scene.unit_settings
us.system = "METRIC"
us.scale_length = 0.01
us.length_unit = "CENTIMETERS"

results = []
setup_render()

for fname, desc, builder, fh, ehw in MODULES:
    reset_scene()
    setup_render()
    stone, iron = make_mats()
    obj = builder()
    finalize(obj, fname, stone, iron)
    b = verify_bounds(obj, fname, exp_half_w=ehw, exp_floor_h=fh)

    me = obj.data
    me.calc_loop_triangles()
    tris = len(me.loop_triangles)

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
