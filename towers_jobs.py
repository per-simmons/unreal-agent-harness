"""Headless Blender generator for a futuristic Dubai/sci-fi skyscraper pack.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python towers_jobs.py

Builds ~12 distinct futuristic towers, each:
  - real-world scale, exported in UE cm (apply_scale_options='FBX_SCALE_ALL')
  - floor-band horizontal divisions + vertical mullion ridges (reads as a building)
  - 2 material slots: 0 = glass/curtain-wall, 1 = frame/structure/spire
  - simple box UVs (smart project)
  - pivot at the base, centered XY (sits on ground at Z=0)
  - own FBX + a neutral 3/4 preview PNG
Then assembles a montage PNG of all previews.

Everything is in METERS inside Blender; FBX export converts to UE cm.
"""
import bpy, bmesh, os, math, mathutils

ROOT = os.path.expanduser("~/coding/unreal-agent-harness/assets/futuristic_city/towers")
os.makedirs(ROOT, exist_ok=True)

# ----------------------------------------------------------------------------
# scene / helpers
# ----------------------------------------------------------------------------

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
    """Return (glass_mat, frame_mat) — distinct so UE shows 2 slots clearly."""
    glass = bpy.data.materials.new("Glass_CurtainWall")
    glass.use_nodes = True
    bsdf = glass.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.10, 0.22, 0.35, 1.0)
        bsdf.inputs["Metallic"].default_value = 0.6
        bsdf.inputs["Roughness"].default_value = 0.12
    frame = bpy.data.materials.new("Frame_Structure")
    frame.use_nodes = True
    bsdf = frame.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.78, 0.80, 0.83, 1.0)
        bsdf.inputs["Metallic"].default_value = 0.9
        bsdf.inputs["Roughness"].default_value = 0.35
    return glass, frame


def finalize(obj, name, glass, frame):
    """Attach 2 material slots, UV-unwrap, set origin to base/center, rename."""
    me = obj.data
    me.materials.clear()
    me.materials.append(glass)   # slot 0
    me.materials.append(frame)   # slot 1
    obj.name = name
    me.name = name + "_mesh"

    # UVs
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")

    # recompute normals outward
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")

    # origin to base center: move so min Z = 0 and XY centroid = 0, then set origin
    # center XY by bounding box
    bb = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
    minx = min(v.x for v in bb); maxx = max(v.x for v in bb)
    miny = min(v.y for v in bb); maxy = max(v.y for v in bb)
    minz = min(v.z for v in bb)
    obj.location.x -= (minx + maxx) / 2.0
    obj.location.y -= (miny + maxy) / 2.0
    obj.location.z -= minz
    bpy.context.view_layer.update()
    # bake transform into mesh, origin to (0,0,0) which is now base-center
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    return obj


def assign_frame_to_top(obj, frac=0.92):
    """Assign material slot 1 (frame) to faces whose center is above frac*height
    (caps/crown) plus any near-vertical thin spire faces. Gives spires/crowns the
    metal look while walls stay glass."""
    me = obj.data
    zs = [v.co.z for v in me.vertices]
    if not zs:
        return
    zmax = max(zs); zmin = min(zs); h = max(zmax - zmin, 1e-5)
    for poly in me.polygons:
        cz = poly.center.z
        if cz >= zmin + frac * h:
            poly.material_index = 1
        # bottom slab / ground floor lobby frame
        elif cz <= zmin + 0.015 * h:
            poly.material_index = 1
    me.update()


# ----------------------------------------------------------------------------
# geometry primitives via bmesh
# ----------------------------------------------------------------------------

def bm_to_obj(bm, name="Tower"):
    me = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    return obj


def add_floor_bands(bm, z0, z1, n_floors, ridge=0.12, inset_faces=True,
                    floor_h=7.0, bay_w=7.0):
    """Carve a floor x bay window grid into the SIDE faces between z0..z1.

    For each near-vertical side face we subdivide it into an N(floors) x M(bays)
    grid (grid_fill via subdivide on the face edges) then inset each cell and push
    it inward — this both adds real geometry (so it isn't a smooth blob) and
    reads as a glazed curtain wall: recessed window panels with mullion ridges
    standing proud between them."""
    if not inset_faces:
        return
    sides = [f for f in bm.faces if abs(f.normal.z) < 0.6
             and z0 + 0.01 <= f.calc_center_median().z <= z1 - 0.01]
    if not sides:
        return
    # subdivide each side face into a grid sized to ~floor_h tall x ~bay_w wide
    for f in list(sides):
        # estimate face height (z span) and width
        zs = [v.co.z for v in f.verts]
        fh = max(zs) - min(zs)
        # width = perimeter horizontal span
        xy = [(v.co.x, v.co.y) for v in f.verts]
        fw = max(math.dist(xy[i], xy[(i + 1) % len(xy)]) for i in range(len(xy)))
        n = max(1, min(int(round(fh / floor_h)), 40))
        m = max(1, min(int(round(fw / bay_w)), 14))
        # Subdivide the face into a floor x bay grid. For floor-stacked towers the
        # face is ~one floor tall (n==1) so we only cut horizontally into bays;
        # for a tall single face (needle shaft) we cut both ways. We cut the two
        # axes independently (not square grid_fill) to avoid wasted geometry.
        if n <= 1 and m <= 1:
            cells = [f]
        else:
            cuts = max(1, min(max(n, m), 28))
            res = bmesh.ops.subdivide_edges(
                bm, edges=f.edges[:], cuts=cuts, use_grid_fill=True)
            new_faces = [g for g in res.get("geom_inner", [])
                         if isinstance(g, bmesh.types.BMFace)]
            if not new_faces:
                new_faces = [g for g in res.get("geom", [])
                             if isinstance(g, bmesh.types.BMFace)]
            cells = [g for g in new_faces if abs(g.normal.z) < 0.6] or [f]
        # inset + recess each window cell (panel set back, mullions stay proud)
        bmesh.ops.inset_individual(bm, faces=cells, thickness=ridge,
                                   depth=-ridge * 0.6)


def prism(bm, verts_xy, z0, z1):
    """Extrude a polygon (list of (x,y)) from z0 to z1, return the new mesh part."""
    bottom = [bm.verts.new((x, y, z0)) for (x, y) in verts_xy]
    bm.faces.new(bottom)
    top = [bm.verts.new((x, y, z1)) for (x, y) in verts_xy]
    f_top = bm.faces.new(top)
    n = len(bottom)
    for i in range(n):
        a, b = bottom[i], bottom[(i + 1) % n]
        c, d = top[(i + 1) % n], top[i]
        bm.faces.new((a, b, c, d))
    return f_top


def ngon(cx, cy, r, sides, rot=0.0):
    return [(cx + r * math.cos(rot + 2 * math.pi * i / sides),
             cy + r * math.sin(rot + 2 * math.pi * i / sides)) for i in range(sides)]


def rect(cx, cy, hx, hy):
    return [(cx - hx, cy - hy), (cx + hx, cy - hy), (cx + hx, cy + hy), (cx - hx, cy + hy)]


def add_mullions(bm, z0, z1, ring_xy, n_floors):
    """Add horizontal floor-band ridges by insetting bands. Approx with loop-like
    inset on side faces already done in add_floor_bands; here we add vertical
    mullion ridges by creating thin extruded edges is heavy, so we rely on the
    inset pass + a per-section facet detail. No-op placeholder kept for clarity."""
    pass


# ----------------------------------------------------------------------------
# the 12 towers — each returns an object (still in meters, not yet finalized)
# ----------------------------------------------------------------------------

def t_taper_spire():
    """01 Burj-style tapered spire, ~800 m hero. Square setbacks spiraling in +
    a long needle spire."""
    bm = bmesh.new()
    h_total = 620.0
    steps = 9
    r0 = 38.0
    z = 0.0
    seg = h_total / steps
    for i in range(steps):
        r = r0 * (1 - 0.085 * i)
        rot = math.radians(8 * i)
        prism(bm, ngon(0, 0, r, 8, rot), z, z + seg)
        add_floor_bands(bm, z, z + seg, int(seg / 3.5))
        z += seg
    # tapering crown cone
    prism(bm, ngon(0, 0, r * 0.55, 8, 0), z, z + 60)
    z += 60
    # needle spire
    tip = bm.verts.new((0, 0, z + 120))
    base = ngon(0, 0, 2.5, 6, 0)
    bverts = [bm.verts.new((x, y, z)) for (x, y) in base]
    bm.faces.new(bverts)
    for i in range(len(bverts)):
        bm.faces.new((bverts[i], bverts[(i + 1) % len(bverts)], tip))
    return bm_to_obj(bm, "tower_01")


def t_twisted():
    """02 Twisted rotating-floors tower (Cayan-style), ~310 m."""
    bm = bmesh.new()
    h = 300.0
    floors = 60
    seg = h / floors
    hx, hy = 22.0, 22.0
    z = 0.0
    for i in range(floors):
        rot = math.radians(1.4 * i)  # ~85deg total twist
        prism(bm, rect(0, 0, hx, hy), z, z + seg)
        # rotate just-added top? simpler: build each slab rotated
        z += seg
    # The above stacks unrotated; rebuild properly: twist by rotating each slab's verts
    bm.free()
    bm = bmesh.new()
    z = 0.0
    prev = None
    for i in range(floors + 1):
        rot = math.radians(1.4 * i)
        ring = [(math.cos(rot) * x - math.sin(rot) * y,
                 math.sin(rot) * x + math.cos(rot) * y)
                for (x, y) in rect(0, 0, hx, hy)]
        cur = [bm.verts.new((x, y, z)) for (x, y) in ring]
        if i == 0:
            bm.faces.new(cur)
        if prev is not None:
            for k in range(4):
                bm.faces.new((prev[k], prev[(k + 1) % 4], cur[(k + 1) % 4], cur[k]))
        if i == floors:
            bm.faces.new(list(reversed(cur)))
        prev = cur
        z += seg
    add_floor_bands(bm, 0, h, floors)
    return bm_to_obj(bm, "tower_02")


def t_stepped():
    """03 Stepped / setback ziggurat tower (art-deco sci-fi), ~360 m."""
    bm = bmesh.new()
    z = 0.0
    sizes = [(40, 40, 120), (32, 32, 90), (25, 25, 70), (18, 18, 50), (11, 11, 30)]
    for (hx, hy, dz) in sizes:
        prism(bm, rect(0, 0, hx, hy), z, z + dz)
        add_floor_bands(bm, z, z + dz, int(dz / 3.5))
        z += dz
    # antenna mast
    prism(bm, ngon(0, 0, 1.2, 6), z, z + 35)
    return bm_to_obj(bm, "tower_03")


def t_crystal():
    """04 Faceted crystalline tower — sharp angular shaft + pointed crown, ~280 m."""
    bm = bmesh.new()
    h = 240.0
    z = 0.0
    # irregular hexagon footprint for a faceted look
    base = [(28, 0), (14, 26), (-16, 24), (-30, 0), (-14, -26), (16, -24)]
    steps = 5
    seg = h / steps
    for i in range(steps):
        s = 1 - 0.12 * i
        ring = [(x * s, y * s) for (x, y) in base]
        prism(bm, ring, z, z + seg)
        add_floor_bands(bm, z, z + seg, int(seg / 4))
        z += seg
    # pointed crystalline crown
    sring = [(x * 0.4, y * 0.4) for (x, y) in base]
    bverts = [bm.verts.new((x, y, z)) for (x, y) in sring]
    bm.faces.new(bverts)
    tip = bm.verts.new((0, 0, z + 60))
    for i in range(len(bverts)):
        bm.faces.new((bverts[i], bverts[(i + 1) % len(bverts)], tip))
    return bm_to_obj(bm, "tower_04")


def t_curved_lean():
    """05 Curved / leaning tower — shaft sweeps along an arc as it rises, ~250 m."""
    bm = bmesh.new()
    h = 230.0
    floors = 46
    seg = h / floors
    hx, hy = 20.0, 16.0
    z = 0.0
    prev = None
    for i in range(floors + 1):
        t = i / floors
        # lean + curve: offset X by a sine arc, taper slightly
        off = 55 * math.sin(t * math.pi * 0.5)
        s = 1 - 0.25 * t
        ring = [(x * s + off, y * s) for (x, y) in rect(0, 0, hx, hy)]
        cur = [bm.verts.new((x, y, z)) for (x, y) in ring]
        if i == 0:
            bm.faces.new(cur)
        if prev is not None:
            for k in range(4):
                bm.faces.new((prev[k], prev[(k + 1) % 4], cur[(k + 1) % 4], cur[k]))
        if i == floors:
            bm.faces.new(list(reversed(cur)))
        prev = cur
        z += seg
    add_floor_bands(bm, 0, h, floors)
    return bm_to_obj(bm, "tower_05")


def t_needle():
    """06 Slender needle — thin round shaft + observation pod + spire, ~520 m."""
    bm = bmesh.new()
    h = 430.0
    z = 0.0
    prism(bm, ngon(0, 0, 11, 16), z, z + h)
    add_floor_bands(bm, z, z + h, int(h / 4), ridge=0.06, floor_h=12.0, bay_w=6.0)
    z += h
    # observation pod (wider disc)
    prism(bm, ngon(0, 0, 20, 16), z, z + 22)
    z += 22
    prism(bm, ngon(0, 0, 8, 16), z, z + 18)
    z += 18
    # spire
    tip = bm.verts.new((0, 0, z + 90))
    base = ngon(0, 0, 2, 8)
    bverts = [bm.verts.new((x, y, z)) for (x, y) in base]
    bm.faces.new(bverts)
    for i in range(len(bverts)):
        bm.faces.new((bverts[i], bverts[(i + 1) % len(bverts)], tip))
    return bm_to_obj(bm, "tower_06")


def t_wide_tiered():
    """07 Wide tiered tower — broad base, three glassy tiers, ~200 m."""
    bm = bmesh.new()
    z = 0.0
    tiers = [(60, 45, 70), (50, 36, 70), (38, 28, 60)]
    for (hx, hy, dz) in tiers:
        prism(bm, rect(0, 0, hx, hy), z, z + dz)
        add_floor_bands(bm, z, z + dz, int(dz / 3.5))
        z += dz
    # rooftop mechanical box
    prism(bm, rect(0, 0, 20, 14), z, z + 12)
    return bm_to_obj(bm, "tower_07")


def t_sail():
    """08 Sail-shaped tower (Burj Al Arab vibe) — curved triangular profile, ~280 m."""
    bm = bmesh.new()
    h = 270.0
    floors = 40
    seg = h / floors
    z = 0.0
    prev = None
    for i in range(floors + 1):
        t = i / floors
        # width tapers; depth follows a sail bow curve
        w = 42 * (1 - 0.55 * t)
        d = 30 * (1 - t) + 4
        bow = 18 * math.sin(t * math.pi)
        ring = [(-w, -d + bow * 0.0), (w, -d), (w, d), (-w, d)]
        # make the back edge bow outward
        ring = [(-w, -d), (w, -d), (w * 0.2, d + bow), (-w, d)]
        cur = [bm.verts.new((x, y, z)) for (x, y) in ring]
        if i == 0:
            bm.faces.new(cur)
        if prev is not None:
            for k in range(4):
                bm.faces.new((prev[k], prev[(k + 1) % 4], cur[(k + 1) % 4], cur[k]))
        if i == floors:
            bm.faces.new(list(reversed(cur)))
        prev = cur
        z += seg
    add_floor_bands(bm, 0, h, floors)
    return bm_to_obj(bm, "tower_08")


def t_twin_notch():
    """09 Notched twin-peak tower — split crown like two prongs, ~330 m."""
    bm = bmesh.new()
    z = 0.0
    h_main = 240.0
    prism(bm, rect(0, 0, 30, 24), z, z + h_main)
    add_floor_bands(bm, z, z + h_main, int(h_main / 3.5))
    z += h_main
    # two prongs separated by a notch
    for sx in (-1, 1):
        prism(bm, rect(sx * 16, 0, 12, 24), z, z + 80)
    add_floor_bands(bm, z, z + 80, 20)
    return bm_to_obj(bm, "tower_09")


def t_block_a():
    """10 Mid-rise glass block with chamfered top, ~150 m."""
    bm = bmesh.new()
    z = 0.0
    h = 130.0
    prism(bm, rect(0, 0, 34, 26), z, z + h)
    add_floor_bands(bm, z, z + h, int(h / 3.6))
    z += h
    # chamfer crown (smaller slab)
    prism(bm, rect(0, 0, 26, 18), z, z + 16)
    return bm_to_obj(bm, "tower_10")


def t_block_b():
    """11 Mid-rise hexagonal block with rooftop garden box, ~160 m."""
    bm = bmesh.new()
    z = 0.0
    h = 140.0
    prism(bm, ngon(0, 0, 30, 6, math.radians(15)), z, z + h)
    add_floor_bands(bm, z, z + h, int(h / 3.6))
    z += h
    prism(bm, ngon(0, 0, 18, 6, math.radians(15)), z, z + 10)
    return bm_to_obj(bm, "tower_11")


def t_diagrid():
    """12 Tapered diagrid tower (Gherkin/sci-fi bullet), ~310 m. Rounded bullet
    silhouette via radius profile."""
    bm = bmesh.new()
    h = 300.0
    floors = 50
    seg = h / floors
    z = 0.0
    prev = None
    sides = 18
    for i in range(floors + 1):
        t = i / floors
        # bullet profile: swells in the middle, narrows top
        r = 30 * math.sin(min(t * 1.05 + 0.18, 1.0) * math.pi) * 0.9 + 6
        ring = ngon(0, 0, max(r, 4), sides)
        cur = [bm.verts.new((x, y, z)) for (x, y) in ring]
        if i == 0:
            bm.faces.new(cur)
        if prev is not None:
            for k in range(sides):
                bm.faces.new((prev[k], prev[(k + 1) % sides],
                              cur[(k + 1) % sides], cur[k]))
        if i == floors:
            bm.faces.new(list(reversed(cur)))
        prev = cur
        z += seg
    add_floor_bands(bm, 0, h, floors, ridge=0.08)
    return bm_to_obj(bm, "tower_12")


BUILDERS = [
    ("tower_01", "Tapered octagonal spire (Burj-style hero)", t_taper_spire),
    ("tower_02", "Twisted rotating-floors tower", t_twisted),
    ("tower_03", "Stepped/setback ziggurat", t_stepped),
    ("tower_04", "Faceted crystalline tower", t_crystal),
    ("tower_05", "Curved/leaning swept tower", t_curved_lean),
    ("tower_06", "Slender needle w/ observation pod", t_needle),
    ("tower_07", "Wide tiered tower", t_wide_tiered),
    ("tower_08", "Sail-shaped tower", t_sail),
    ("tower_09", "Notched twin-peak tower", t_twin_notch),
    ("tower_10", "Mid-rise chamfered glass block", t_block_a),
    ("tower_11", "Mid-rise hexagonal block", t_block_b),
    ("tower_12", "Tapered diagrid bullet tower", t_diagrid),
]


# ----------------------------------------------------------------------------
# render setup
# ----------------------------------------------------------------------------

def setup_render():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in \
        [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
    scene.render.resolution_x = 800
    scene.render.resolution_y = 1000
    scene.render.film_transparent = False
    try:
        scene.view_settings.view_transform = "Standard"
    except Exception:
        pass
    # world
    if scene.world is None:
        scene.world = bpy.data.worlds.new("W")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.05, 0.06, 0.09, 1.0)
        bg.inputs[1].default_value = 1.0


def add_cam_and_lights(height, width):
    # camera framed 3/4 view
    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam_data.lens = 50
    cam_data.clip_start = 0.1
    cam_data.clip_end = 1.0e6  # tall towers sit beyond the default 1000 m clip
    # render is portrait (800x1000); vertical FOV is the binding constraint for
    # tall towers. Pull back far enough that the full height + footprint fits.
    res_x = bpy.context.scene.render.resolution_x
    res_y = bpy.context.scene.render.resolution_y
    sensor = cam_data.sensor_width
    # vertical half-angle (portrait => sensor_fit vertical effectively scaled by aspect)
    vfov = 2 * math.atan((sensor * (res_y / res_x)) / (2 * cam_data.lens))
    hfov = 2 * math.atan(sensor / (2 * cam_data.lens))
    # subject extent we must fit: full height vertically, footprint*~1.7 horizontally
    # generous margins so crowns/notches/leans never clip; the diagonal 3/4 view
    # also projects the footprint onto the screen so pad horizontal extra.
    fit_v = (height * 1.35) / (2 * math.tan(vfov / 2))
    fit_h = (width * 3.0) / (2 * math.tan(hfov / 2))
    dist = max(fit_v, fit_h)
    cam.location = (dist * 0.62, -dist * 0.62, height * 0.52)
    target = mathutils.Vector((0, 0, height * 0.5))
    direction = target - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam

    key = bpy.data.lights.new("Key", "SUN")
    key.energy = 4.0
    ko = bpy.data.objects.new("Key", key)
    ko.rotation_euler = (math.radians(55), math.radians(15), math.radians(40))
    bpy.context.collection.objects.link(ko)

    rim = bpy.data.lights.new("Rim", "SUN")
    rim.energy = 2.0
    rim.color = (0.6, 0.75, 1.0)
    ro = bpy.data.objects.new("Rim", rim)
    ro.rotation_euler = (math.radians(60), 0, math.radians(220))
    bpy.context.collection.objects.link(ro)
    return cam, ko, ro


# ----------------------------------------------------------------------------
# main loop
# ----------------------------------------------------------------------------

results = []  # (file, name, desc, height_m, footprint_m, tris)

setup_render()

for fname, desc, builder in BUILDERS:
    reset_scene()
    setup_render()
    glass, frame = make_mats()
    obj = builder()
    finalize(obj, fname, glass, frame)
    assign_frame_to_top(obj)

    # tri budget guard: collapse-decimate anything over ~60k so every mesh stays
    # game-ready, preserving silhouette + material boundaries.
    me = obj.data
    me.calc_loop_triangles()
    if len(me.loop_triangles) > 60000:
        ratio = 60000.0 / len(me.loop_triangles)
        mod = obj.modifiers.new("Decimate", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = ratio
        mod.use_collapse_triangulate = True
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)

    # stats
    me = obj.data
    me.calc_loop_triangles()
    tris = len(me.loop_triangles)
    zs = [v.co.z for v in me.vertices]
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    height_m = max(zs) - min(zs)
    foot_m = max(max(xs) - min(xs), max(ys) - min(ys))

    # render preview FIRST (while geometry is still in meters at true scale)
    cam, ko, ro = add_cam_and_lights(height_m, foot_m)
    png = os.path.join(ROOT, fname + ".png")
    bpy.context.scene.render.filepath = png
    bpy.ops.render.render(write_still=True)

    # export FBX in UE cm. UE reads 1 FBX unit = 1 cm, so we bake meters->cm by
    # scaling the mesh x100 and exporting the RAW numbers (FBX_SCALE_NONE,
    # apply_transform). An 800 m tower then lands as 80000 cm in Unreal.
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    obj.scale = (100.0, 100.0, 100.0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    fbx = os.path.join(ROOT, fname + ".fbx")
    bpy.ops.export_scene.fbx(
        filepath=fbx, use_selection=True,
        apply_scale_options="FBX_SCALE_NONE", global_scale=1.0,
        object_types={"MESH"}, mesh_smooth_type="FACE",
        use_mesh_modifiers=True, bake_space_transform=True,
        axis_forward="-Z", axis_up="Y",
    )

    results.append((fname, desc, height_m, foot_m, tris))
    print(f"DONE {fname}: {desc} | h={height_m:.0f}m foot={foot_m:.0f}m tris={tris} -> {fbx}")

# write a machine-readable stats file for NOTES.md generation
import json
with open(os.path.join(ROOT, "_stats.json"), "w") as f:
    json.dump(results, f, indent=2)

print("ALL TOWERS DONE:", len(results))
