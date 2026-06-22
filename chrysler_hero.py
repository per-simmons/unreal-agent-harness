"""Headless Blender generator for a BESPOKE CHRYSLER BUILDING hero landmark — a
single tall hero mesh for import into UE 5.8 as a City Sample centerpiece.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python chrysler_hero.py

GOAL: an unmistakable Chrysler Building silhouette. In priority order:
  1. THE CROWN (the icon) — the famous terraced sunburst: 7 diminishing arched
     tiers stacked vertically, each tier a nested semicircular arch carrying a
     fan/row of TRIANGULAR windows radiating like a sunburst, capped by a tall
     needle SPIRE. Crown + spire on slot 1 = polished stainless / chrome.
  2. THE SHAFT — a tall tapered Art-Deco tower with a few setbacks rising to the
     crown; strong vertical pier emphasis; pale warm stone on slot 0.
  3. SCALE — HERO: ~300m tall (Chrysler is 319m), footprint ~55m, base-pivoted
     (min.z = 0) so it drops straight onto the ground in UE.
  4. 2 material slots (0 = stone shaft, 1 = steel/chrome crown+spire). Bevels.
     Higher poly fine (Nanite).

CONVENTIONS borrowed from art_deco_detailed_jobs.py (the sibling builder):
  - units in CENTIMETERS, scale_length 0.01
  - 2 material slots, faces tagged material_index 0/1 at build time
  - finalize() does NOT call me.materials.clear() (that bug zeroes every
    material_index, collapsing slot-1 ornament into slot 0)
  - bevel every hard edge (anti-CG); base-pivoted; X/Y centered footprint
  - FBX export axis_forward -Z / axis_up Y, FBX_SCALE_ALL, bake_space_transform

THE CROWN GEOMETRY (the part that must read):
  The real crown is built from nested radial arches on each of the 4 faces. We
  approximate the iconic profile with `n_tiers` (=7) stacked terraces. Each tier
  is a thin horizontal slab whose FRONT (and all 4 faces) carry a semicircular
  arch cut-out, and inside each arch a fan of triangular windows points up and
  out (the sunburst). Tiers shrink in radius and height as they rise, giving the
  swept telescoping curve. A square spire base then launches a long needle.

Output: ~/coding/unreal-agent-harness/assets/chrysler/chrysler_hero.fbx
        + chrysler_34.png, chrysler_crown.png, chrysler_front.png, montage,
        NOTES.md, _stats.json
"""
import bpy, bmesh, os, math, mathutils, json

ROOT = os.path.expanduser("~/coding/unreal-agent-harness/assets/chrysler")
os.makedirs(ROOT, exist_ok=True)

# ---- DIMENSIONS (cm) --------------------------------------------------------
# Footprint ~55m base; tapers in setbacks. Heights chosen so total ~= 30000cm.
BASE_HW      = 2600.0     # base half-width (52 m footprint) — slender
SHAFT_TOP_Z  = 21500.0    # top of the stone shaft / start of crown (215 m)
CROWN_TOP_Z  = 27800.0    # top of the terraced crown (278 m) — bigger crown
SPIRE_TOP_Z  = 31000.0    # tip of the needle (310 m) — long dramatic needle

N_SETBACKS   = 3          # number of shaft setbacks below the crown
N_TIERS      = 7          # the iconic 7 arched crown terraces
N_SUN_WINDOWS = 11        # triangular windows per arch face (the sunburst fan)
N_ARCH_RINGS = 3          # concentric arch rings nested per tier face

BEVEL_W   = 4.0           # cm — scaled up for the hero's size
BEVEL_SEG = 2


# ---------------------------------------------------------------------------
# scene / material helpers
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
    """slot 0 = pale warm limestone, slot 1 = polished stainless / chrome."""
    stone = bpy.data.materials.new("M_Stone")
    stone.use_nodes = True
    b = stone.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = (0.74, 0.69, 0.58, 1.0)
        b.inputs["Metallic"].default_value = 0.0
        b.inputs["Roughness"].default_value = 0.70
    steel = bpy.data.materials.new("M_Steel")
    steel.use_nodes = True
    b = steel.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = (0.86, 0.88, 0.90, 1.0)
        b.inputs["Metallic"].default_value = 1.0
        b.inputs["Roughness"].default_value = 0.12
    return stone, steel


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------

def bm_to_obj(bm, name):
    me = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    return obj


def box(bm, x0, x1, y0, y1, z0, z1, mat=0):
    """Axis-aligned box, faces tagged with mat."""
    v = [bm.verts.new((x, y, z))
         for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    def V(ix, iy, iz):
        return v[iz * 4 + iy * 2 + ix]
    faces = [
        bm.faces.new((V(0,0,0), V(1,0,0), V(1,1,0), V(0,1,0))),  # bottom
        bm.faces.new((V(0,0,1), V(0,1,1), V(1,1,1), V(1,0,1))),  # top
        bm.faces.new((V(0,0,0), V(0,1,0), V(0,1,1), V(0,0,1))),  # -X
        bm.faces.new((V(1,0,0), V(1,0,1), V(1,1,1), V(1,1,0))),  # +X
        bm.faces.new((V(0,0,0), V(0,0,1), V(1,0,1), V(1,0,0))),  # -Y
        bm.faces.new((V(0,1,0), V(1,1,0), V(1,1,1), V(0,1,1))),  # +Y
    ]
    for f in faces:
        f.material_index = mat
    return faces


def prism_z(bm, poly_bottom, poly_top, mat=0, cap_bottom=True, cap_top=True):
    """Generic prism between two equal-length polygon rings (lists of (x,y,z))."""
    n = len(poly_bottom)
    bv = [bm.verts.new(p) for p in poly_bottom]
    tv = [bm.verts.new(p) for p in poly_top]
    if cap_bottom:
        bm.faces.new(bv).material_index = mat
    if cap_top:
        bm.faces.new(list(reversed(tv))).material_index = mat
    for k in range(n):
        bm.faces.new((bv[k], bv[(k+1)%n], tv[(k+1)%n], tv[k])).material_index = mat
    return bv, tv


def square_ring(hw, z, hd=None):
    """4-pt square ring at height z, half-width hw (centered on origin)."""
    if hd is None:
        hd = hw
    return [(-hw, -hd, z), (hw, -hd, z), (hw, hd, z), (-hw, hd, z)]


def octa_ring(hw, z):
    """8-pt regular-ish octagon ring (chamfered square) — the crown reads rounder."""
    c = hw * 0.41   # chamfer
    return [(-hw+c, -hw, z), (hw-c, -hw, z), (hw, -hw+c, z), (hw, hw-c, z),
            (hw-c, hw, z), (-hw+c, hw, z), (-hw, hw-c, z), (-hw, -hw+c, z)]


# ---------------------------------------------------------------------------
# the SHAFT — tapered Art-Deco tower with setbacks + vertical piers
# ---------------------------------------------------------------------------

def build_shaft(bm):
    """Stacked setback blocks from BASE_HW up to SHAFT_TOP_Z, narrowing each
    setback. Strong vertical fluted piers run the full height of each block
    front; thin steel string-courses band each setback shelf."""
    # half-width at base and at the top (where the crown launches)
    top_hw = BASE_HW * 0.66
    seg_h = SHAFT_TOP_Z / N_SETBACKS
    for i in range(N_SETBACKS):
        z0 = i * seg_h
        z1 = (i + 1) * seg_h
        f = i / max(1, N_SETBACKS - 1)
        hw = BASE_HW + (top_hw - BASE_HW) * f
        # main block body (stone)
        box(bm, -hw, hw, -hw, hw, z0, z1, mat=0)
        # steel string-course banding the shelf at the top of each block
        box(bm, -hw - 18, hw + 18, -hw - 18, hw + 18, z1 - 90, z1 - 30, mat=1)
        # vertical fluted piers on all 4 faces (strong vertical emphasis)
        add_piers(bm, hw, z0 + 40, z1 - 120)


def add_piers(bm, hw, z0, z1, n_per_face=9, proud=70.0, mat_pier=0, mat_groove=1):
    """Full-height vertical piers proud of each of the 4 faces, with a recessed
    steel reveal groove between them (the deco vertical rhythm)."""
    span = 2 * hw
    pitch = span / n_per_face
    pw = pitch * 0.30
    # iterate the 4 faces: (-Y front, +Y back, -X left, +X right)
    for face in range(4):
        for k in range(n_per_face):
            c = -hw + pitch * (k + 0.5)
            if face == 0:    # -Y
                box(bm, c-pw, c+pw, -hw-proud, -hw+10, z0, z1, mat=mat_pier)
            elif face == 1:  # +Y
                box(bm, c-pw, c+pw, hw-10, hw+proud, z0, z1, mat=mat_pier)
            elif face == 2:  # -X
                box(bm, -hw-proud, -hw+10, c-pw, c+pw, z0, z1, mat=mat_pier)
            else:            # +X
                box(bm, hw-10, hw+proud, c-pw, c+pw, z0, z1, mat=mat_pier)


# ---------------------------------------------------------------------------
# the CROWN — the icon. Terraced sunburst: 7 diminishing arched tiers + spire.
# ---------------------------------------------------------------------------

def arch_tier(bm, hw, z0, z1, arch_depth, mat_body=1, n_windows=N_SUN_WINDOWS):
    """ONE crown terrace. A slab of half-width `hw` from z0..z1 whose 4 faces
    each carry a big SEMICIRCULAR arch, and inside each arch a fan of TRIANGULAR
    windows radiating up like a sunburst. Built on slot 1 (steel/chrome).

    Implementation: the slab body is an octagonal prism (reads rounded). On each
    of the 4 cardinal faces we build the arch as a curved band of small steel
    segments following a semicircle, and place a fan of recessed triangular
    window prisms (slot 0 = dark stone interior so they read as openings) under
    the arch crown."""
    tier_h = z1 - z0
    # --- slab body: octagonal prism, slightly tapered top ---
    bot = octa_ring(hw, z0)
    top = octa_ring(hw * 0.93, z1)
    prism_z(bm, bot, top, mat=mat_body, cap_bottom=False, cap_top=False)

    # --- the arch + sunburst on each of the 4 cardinal faces ---
    arch_r = hw * 0.74                 # arch radius
    arch_cz = z0 + tier_h * 0.30       # springline of the arch
    arch_top = arch_cz + arch_r        # crown of the arch
    if arch_top > z1:
        arch_r = (z1 - arch_cz) * 0.96
        arch_top = arch_cz + arch_r
    faces = [
        ("-Y", (0, -1)), ("+Y", (0, 1)), ("-X", (-1, 0)), ("+X", (1, 0)),
    ]
    for _, (nx, ny) in faces:
        _arch_face(bm, hw, arch_cz, arch_r, nx, ny, n_windows, mat_body)


def _arch_face(bm, hw, springz, r, nx, ny, n_windows, mat_body):
    """Build a raised semicircular arch ARCHIVOLT on one face + a sunburst fan
    of triangular windows beneath it. nx,ny = outward face normal direction."""
    # face plane sits at distance `hw` along the normal; build in a local 2D
    # frame (u = tangent across the face, v = world Z). The face tangent:
    if nx != 0:   # -X / +X face: tangent runs along Y
        def P(u, z, out):  # u across face (Y), out = extra outward offset
            return (nx * (hw + out), u, z)
    else:         # -Y / +Y face: tangent runs along X
        def P(u, z, out):
            return (u, ny * (hw + out), z)

    seg = 24
    band_t = r * 0.07        # band thickness (radial)
    cz = springz + r * 0.02

    # --- N_ARCH_RINGS concentric archivolts (the signature stacked arches) ---
    # each ring is a steel semicircular band proud of the face; rings step DOWN
    # in radius and the proud-offset shrinks as they nest inward.
    for ring in range(N_ARCH_RINGS):
        rr = r * (1.0 - 0.22 * ring)
        proud = 70.0 - 16.0 * ring
        for s in range(seg):
            a0 = math.pi * s / seg
            a1 = math.pi * (s + 1) / seg
            u0o, z0o = math.cos(a0) * rr,          cz + math.sin(a0) * rr
            u1o, z1o = math.cos(a1) * rr,          cz + math.sin(a1) * rr
            u0i, z0i = math.cos(a0) * (rr-band_t), cz + math.sin(a0) * (rr-band_t)
            u1i, z1i = math.cos(a1) * (rr-band_t), cz + math.sin(a1) * (rr-band_t)
            front = [P(u0o, z0o, proud), P(u1o, z1o, proud),
                     P(u1i, z1i, proud), P(u0i, z0i, proud)]
            vs = [bm.verts.new(p) for p in front]
            bm.faces.new(vs).material_index = mat_body
            back = [P(u0o, z0o, 0), P(u1o, z1o, 0), P(u1i, z1i, 0), P(u0i, z0i, 0)]
            vb = [bm.verts.new(p) for p in back]
            bm.faces.new([vs[0], vs[1], vb[1], vb[0]]).material_index = mat_body  # outer wall
            bm.faces.new([vs[3], vs[2], vb[2], vb[3]]).material_index = mat_body  # inner wall

    # --- the SUNBURST: a fan of triangular windows under the innermost arch ---
    # windows radiate from a center just above the springline, pointing up/out.
    rin = r * 0.16
    rout = r * (1.0 - 0.22 * N_ARCH_RINGS) * 0.94
    for w in range(n_windows):
        frac = (w + 0.5) / n_windows
        ang = math.pi * (0.05 + 0.90 * frac)   # stay inside the arch
        spread = (math.pi / n_windows) * 0.42
        u_tip, z_tip = math.cos(ang) * rin, cz + math.sin(ang) * rin
        ua, za = math.cos(ang - spread) * rout, cz + math.sin(ang - spread) * rout
        ub, zb = math.cos(ang + spread) * rout, cz + math.sin(ang + spread) * rout
        # recessed dark triangular pane (slot 0) set BACK of the face -> reads as opening
        tri = [P(u_tip, z_tip, -55), P(ua, za, -55), P(ub, zb, -55)]
        vs = [bm.verts.new(p) for p in tri]
        bm.faces.new(vs).material_index = 0
        # steel mullion walls framing each window (proud)
        tri_f = [P(u_tip, z_tip, 35), P(ua, za, 35), P(ub, zb, 35)]
        vf = [bm.verts.new(p) for p in tri_f]
        for k in range(3):
            bm.faces.new([vs[k], vs[(k+1)%3], vf[(k+1)%3], vf[k]]).material_index = mat_body


def build_crown(bm):
    """7 diminishing arched terraces from SHAFT_TOP_Z to CROWN_TOP_Z, then the
    spire base + needle. Each terrace shrinks in radius and height as it rises,
    producing the swept telescoping Chrysler curve."""
    top_hw = BASE_HW * 0.66      # matches the shaft top
    crown_span = CROWN_TOP_Z - SHAFT_TOP_Z
    z = SHAFT_TOP_Z
    # tier heights shrink as they rise (geometric-ish), summing to crown_span
    weights = [1.0 - 0.085 * i for i in range(N_TIERS)]
    wsum = sum(weights)
    for i in range(N_TIERS):
        f = i / (N_TIERS - 1)
        # half-width follows a curved telescoping taper (eased); tier 0 == shaft top
        hw = top_hw * (1.0 - 0.80 * (f ** 1.55)) + 50.0
        th = crown_span * weights[i] / wsum
        z1 = z + th
        arch_tier(bm, hw, z, z1, arch_depth=th * 0.5)
        z = z1

    # --- spire base: a short tapered steel pyramid frustum on top of tier 7 ---
    base_hw = top_hw * (1.0 - 0.78) + 60.0   # ~tier-7 width
    sp0 = CROWN_TOP_Z
    sp_base_top = CROWN_TOP_Z + (SPIRE_TOP_Z - CROWN_TOP_Z) * 0.18
    bot = square_ring(base_hw * 0.55, sp0)
    top = square_ring(base_hw * 0.22, sp_base_top)
    prism_z(bm, bot, top, mat=1, cap_bottom=False, cap_top=False)

    # --- the NEEDLE: long slender steel spike to the tip ---
    needle_hw = base_hw * 0.22
    nb = square_ring(needle_hw, sp_base_top)
    apex = [(0.0, 0.0, SPIRE_TOP_Z)]
    bv = [bm.verts.new(p) for p in nb]
    av = bm.verts.new(apex[0])
    for k in range(4):
        bm.faces.new((bv[k], bv[(k+1)%4], av)).material_index = 1
    bm.faces.new(bv).material_index = 1


# ---------------------------------------------------------------------------
# finalize / verify
# ---------------------------------------------------------------------------

def finalize(obj, name, stone, steel):
    me = obj.data
    # do NOT clear materials (that zeroes material_index). Append in slot order.
    me.materials.append(stone)   # slot 0
    me.materials.append(steel)   # slot 1
    obj.name = name
    me.name = name + "_mesh"

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=0.5)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")

    bev = obj.modifiers.new("Bevel", "BEVEL")
    bev.width = BEVEL_W
    bev.segments = BEVEL_SEG
    bev.limit_method = "ANGLE"
    bev.angle_limit = math.radians(35)
    bev.harden_normals = True
    bpy.ops.object.modifier_apply(modifier=bev.name)

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")

    # center X/Y, base-pivot Z
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    zs = [v.co.z for v in me.vertices]
    xc = (min(xs) + max(xs)) / 2.0
    yc = (min(ys) + max(ys)) / 2.0
    zmin = min(zs)
    for v in me.vertices:
        v.co.x -= xc
        v.co.y -= yc
        v.co.z -= zmin

    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    return obj


def verify_bounds(obj):
    me = obj.data
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    zs = [v.co.z for v in me.vertices]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    minz, maxz = min(zs), max(zs)
    b = {
        "x": [round(minx,1), round(maxx,1)],
        "y": [round(miny,1), round(maxy,1)],
        "z": [round(minz,1), round(maxz,1)],
        "footprint_w_cm": round(maxx-minx,1),
        "footprint_d_cm": round(maxy-miny,1),
        "height_cm": round(maxz-minz,1),
        "height_m": round((maxz-minz)/100.0,1),
        "x_centered": abs((minx+maxx)/2.0) <= 5.0,
        "y_centered": abs((miny+maxy)/2.0) <= 5.0,
        "base_pivoted": abs(minz) <= 1.0,
    }
    b["status"] = "OK" if (b["x_centered"] and b["y_centered"] and b["base_pivoted"]) else "**FAIL**"
    print(f"[BOUNDS {b['status']}] X{b['x']} Y{b['y']} Z{b['z']} "
          f"| {b['height_m']}m tall | base={b['base_pivoted']} "
          f"Xc={b['x_centered']} Yc={b['y_centered']}")
    return b


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------

def setup_render(res_x=720, res_y=1100):
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
        bg.inputs[0].default_value = (0.45, 0.55, 0.72, 1.0)  # sky blue
        bg.inputs[1].default_value = 1.0


def add_lights():
    key = bpy.data.lights.new("Key", "SUN")
    key.energy = 4.0
    key.color = (1.0, 0.96, 0.88)
    ko = bpy.data.objects.new("Key", key)
    ko.rotation_euler = (math.radians(54), math.radians(10), math.radians(40))
    bpy.context.collection.objects.link(ko)
    rim = bpy.data.lights.new("Rim", "SUN")
    rim.energy = 2.2
    rim.color = (0.80, 0.85, 1.0)
    ro = bpy.data.objects.new("Rim", rim)
    ro.rotation_euler = (math.radians(64), 0, math.radians(210))
    bpy.context.collection.objects.link(ro)


def place_cam(name, loc, look_z, lens=60):
    cam_data = bpy.data.cameras.new(name)
    cam = bpy.data.objects.new(name, cam_data)
    bpy.context.collection.objects.link(cam)
    cam_data.lens = lens
    cam_data.clip_start = 10.0
    cam_data.clip_end = 1.0e7
    cam.location = loc
    target = mathutils.Vector((0, 0, look_z))
    cam.rotation_euler = (target - mathutils.Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    return cam


def render_to(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

us = bpy.context.scene.unit_settings
us.system = "METRIC"
us.scale_length = 0.01
us.length_unit = "CENTIMETERS"

reset_scene()
setup_render()
stone, steel = make_mats()

bm = bmesh.new()
build_shaft(bm)
build_crown(bm)
obj = bm_to_obj(bm, "chrysler_hero")
finalize(obj, "chrysler_hero", stone, steel)
b = verify_bounds(obj)

me = obj.data
me.calc_loop_triangles()
tris = len(me.loop_triangles)
n_slots = len(me.materials)
print(f"[MESH] tris={tris} slots={n_slots}")

add_lights()
H = b["height_cm"]          # ~31000

# 3/4 hero view — wide lens, pulled back, low so the tall thin tower fits frame
place_cam("cam34", (H*1.05, -H*1.05, H*0.42), H*0.46, lens=28)
render_to(os.path.join(ROOT, "chrysler_34.png"))

# crown close-up — frame the crown + full needle
crown_z = (SHAFT_TOP_Z + SPIRE_TOP_Z) / 2.0
place_cam("camcrown", (H*0.20, -H*0.20, crown_z + 1000), crown_z)
render_to(os.path.join(ROOT, "chrysler_crown.png"))

# straight-front silhouette — full height, wide lens
place_cam("camfront", (0, -H*1.5, H*0.48), H*0.48, lens=30)
render_to(os.path.join(ROOT, "chrysler_front.png"))

# export FBX
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
fbx = os.path.join(ROOT, "chrysler_hero.fbx")
bpy.ops.export_scene.fbx(
    filepath=fbx, use_selection=True,
    apply_scale_options="FBX_SCALE_ALL", apply_unit_scale=True, global_scale=1.0,
    object_types={"MESH"}, mesh_smooth_type="FACE",
    use_mesh_modifiers=True, bake_space_transform=True,
    axis_forward="-Z", axis_up="Y",
)

# montage of the three views side by side (uses Blender's bundled PIL? no — use
# the compositor-free approach: just leave the 3 PNGs; build montage via imagemagick
# in the shell after this script). Stats below.
stats = {"file": "chrysler_hero", "tris": tris, "slots": n_slots, "bounds": b,
         "dims": {"BASE_HW": BASE_HW, "SHAFT_TOP_Z": SHAFT_TOP_Z,
                  "CROWN_TOP_Z": CROWN_TOP_Z, "SPIRE_TOP_Z": SPIRE_TOP_Z,
                  "N_SETBACKS": N_SETBACKS, "N_TIERS": N_TIERS}}
with open(os.path.join(ROOT, "_stats.json"), "w") as f:
    json.dump(stats, f, indent=2)
print("DONE chrysler_hero ->", fbx)
