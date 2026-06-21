"""Headless Blender generator for an ART DECO modular building kit that drops
directly into Epic's PCG building-grammar generator (PCG_Building_CitySample /
PCG_BuildingSample) — the 1920s-30s Chrysler/Empire-State skyscraper look.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python art_deco_kit_jobs.py

WHY WE MATCH THE SPEC EXACTLY (same as the futuristic kit):
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
  DEPTH    = 30 cm    (deco facades have proud piers, slightly deeper than glass)

All units are CENTIMETERS in Blender here (scene unit set to cm, scale_length
0.01) so the FBX exports 1:1 to UE cm. This is the LESSON from the futuristic kit
iter4: Blender's default scene unit is METERS, so a cm-magnitude scene gets tagged
as meters and UE multiplies by 100 on import. We set the scene unit to cm AND
export with FBX_SCALE_ALL + apply_unit_scale so the FBX carries the cm unit and
UE imports at true size. ALWAYS get_bounds 1-2 modules after import to confirm.

ART DECO STYLE (the whole point):
  - Strong VERTICAL piers / fluting running floor-to-floor (the Deco signature) —
    these align across floors so a stacked tower reads as soaring vertical ribs.
  - Geometric CHEVRON / ZIGZAG spandrel panels in the recess between window bays.
  - Stepped / setback feel; warm STONE/terracotta + BRONZE metal trim.
  - Decorative bronze window grilles (geometric bars across the glazing).
  - A stepped ZIGGURAT crown variant for the top of the tower.

KIT (FBX each, to ~/coding/unreal-agent-harness/assets/art_deco_kit/):
  mod_wall.fbx   - fluted stone pier wall panel (vertical flutes, chevron base)  -> symbol W
  mod_window.fbx - vertical-pier window bay (recessed glazing + bronze grille +
                   chevron spandrel between floors)                              -> symbol W1 / W2
  mod_corner.fbx - stepped stone corner pier that closes the box                 -> symbol C
  mod_ground.fbx - grand deco lobby (tall arched/stepped entrance, bronze)       -> ground W1
  mod_crown.fbx  - stepped ziggurat / setback crown cap for the tower top        -> crown

Material slots (consistent across all modules):
  slot 0 = Stone   (warm terracotta / limestone, matte)
  slot 1 = Bronze  (metal trim: piers caps, grilles, chevrons, crown banding)
"""
import bpy, bmesh, os, math, mathutils

ROOT = os.path.expanduser("~/coding/unreal-agent-harness/assets/art_deco_kit")
os.makedirs(ROOT, exist_ok=True)

# ---- THE MODULE SPEC (cm) -------------------------------------------------
MODULE_W = 400.0          # width along local X, CENTERED -> X in [-200, +200]
HALF_W   = MODULE_W / 2.0 # 200  (Extents.X -> generator Size = HALF_W*2 = 400)
FLOOR_H  = 400.0          # height along Z, base-pivoted -> Z in [0, 400]
DEPTH    = 30.0           # shallow facade depth along Y, centered -> Y in [-15, +15]
HALF_D   = DEPTH / 2.0    # 15
GROUND_H = 600.0          # taller grand-lobby floor variant
CROWN_H  = 800.0          # stepped ziggurat crown is taller than a normal floor


# ---------------------------------------------------------------------------
# scene / material / finalize helpers (mirrors futuristic_kit_jobs.py)
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
        b.inputs["Base Color"].default_value = (0.62, 0.45, 0.32, 1.0)  # warm terracotta limestone
        b.inputs["Metallic"].default_value = 0.0
        b.inputs["Roughness"].default_value = 0.72
    bronze = bpy.data.materials.new("M_Bronze")
    bronze.use_nodes = True
    b = bronze.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = (0.46, 0.31, 0.13, 1.0)  # warm bronze
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


def prism_tri(bm, pts_xy, z0, z1, mat=1):
    """Extrude an XY polygon (list of (x,y)) from z0 to z1. For chevrons."""
    bottom = [bm.verts.new((x, y, z0)) for (x, y) in pts_xy]
    top = [bm.verts.new((x, y, z1)) for (x, y) in pts_xy]
    n = len(pts_xy)
    f = []
    f.append(bm.faces.new(bottom))
    f.append(bm.faces.new(list(reversed(top))))
    for i in range(n):
        f.append(bm.faces.new((bottom[i], bottom[(i+1) % n], top[(i+1) % n], top[i])))
    for face in f:
        face.material_index = mat
    return f


def finalize(obj, name, stone, bronze, half_w=HALF_W, floor_h=FLOOR_H):
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

def _vertical_flutes(bm, x0, x1, z0, z1, n_flutes, depth_y, mat):
    """Proud vertical fluting between x0..x1: n thin stone ribs running full
    height. Deco signature -> these align across floors = soaring vertical read."""
    span = x1 - x0
    pitch = span / n_flutes
    rib_w = pitch * 0.42
    for i in range(n_flutes):
        cx = x0 + pitch * (i + 0.5)
        f = box(bm, cx - rib_w/2, cx + rib_w/2, -HALF_D, -HALF_D + depth_y, z0, z1)
        for face in f:
            face.material_index = mat


def _chevron_band(bm, x0, x1, zc, band_h, mat=1):
    """A geometric zigzag/chevron band across x0..x1 centered vertically at zc.
    Series of up-pointing triangles (the Deco spandrel motif), proud bronze."""
    span = x1 - x0
    n = 5
    step = span / n
    h = band_h
    yfront = -HALF_D
    ydepth = 3.0
    for i in range(n):
        bx = x0 + i * step
        # up-pointing chevron triangle (front face proud bronze)
        pts = [(bx, zc - h/2), (bx + step/2, zc + h/2), (bx + step, zc - h/2)]
        # build as thin prism in Y (extrude along Y a few cm), but it's an X-Z
        # shape, so make a flat extruded triangle in the X-Z plane.
        bottom = [bm.verts.new((px, yfront, pz)) for (px, pz) in pts]
        top = [bm.verts.new((px, yfront + ydepth, pz)) for (px, pz) in pts]
        bm.faces.new(bottom)
        bm.faces.new(list(reversed(top)))
        for k in range(3):
            bm.faces.new((bottom[k], bottom[(k+1)%3], top[(k+1)%3], top[k]))
    # tag everything just-added on the front as bronze
    for face in bm.faces:
        if face.material_index == 0 and all(abs(v.co.y - yfront) < ydepth + 1 for v in face.verts):
            pass  # leave; tagged below by builder pass


def m_wall(floor_h=FLOOR_H):
    """Fluted STONE spandrel/pier wall panel (the solid bay between windows).

    Reads as a Deco stone pier: a stone slab with proud VERTICAL FLUTES running
    full height (align across floors = tall vertical ribs), a bronze cap line at
    the top, and a small chevron motif near the base. No glass — this is the
    solid W symbol.
    """
    bm = bmesh.new()
    cap_t = 14.0
    # main stone slab (set the body back a touch so flutes read PROUD off it)
    f = box(bm, -HALF_W, HALF_W, -HALF_D + 14.0, HALF_D, 0, floor_h)
    for face in f:
        face.material_index = 0  # stone
    # proud vertical flutes full height (Deco signature) — deep + alternating
    # stone rib / bronze reveal so the verticals read strongly across floors
    n_flutes = 6
    span = (HALF_W - 12) - (-HALF_W + 12)
    pitch = span / n_flutes
    for i in range(n_flutes):
        cx = (-HALF_W + 12) + pitch * (i + 0.5)
        rib = box(bm, cx - pitch*0.30, cx + pitch*0.30, -HALF_D, -HALF_D + 16.0, 12.0, floor_h - cap_t - 2)
        for face in rib:
            face.material_index = 0  # proud stone rib
        # thin bronze reveal in the groove between ribs
        bz = box(bm, cx - pitch*0.06, cx + pitch*0.06, -HALF_D + 14.0, -HALF_D + 15.0, 12.0, floor_h - cap_t - 2)
        for face in bz:
            face.material_index = 1
    # bronze cap line at the top
    cap = box(bm, -HALF_W, HALF_W, -HALF_D, -HALF_D + 8.0, floor_h - cap_t, floor_h)
    for face in cap:
        face.material_index = 1
    # chevron/zigzag bronze band at the BASE of the wall (the Deco motif)
    zc = 22.0
    n = 6
    cspan = 2 * HALF_W
    cstep = cspan / n
    for i in range(n):
        bx = -HALF_W + cstep * i
        tpts = [(bx, 0.0), (bx + cstep/2, 30.0), (bx + cstep, 0.0)]
        b2 = [bm.verts.new((px, -HALF_D, pz)) for (px, pz) in tpts]
        t2 = [bm.verts.new((px, -HALF_D + 5.0, pz)) for (px, pz) in tpts]
        cf = [bm.faces.new(b2), bm.faces.new(list(reversed(t2)))]
        for k in range(3):
            cf.append(bm.faces.new((b2[k], b2[(k+1)%3], t2[(k+1)%3], t2[k])))
        for face in cf:
            face.material_index = 1
    return bm_to_obj(bm, "mod_wall")


def m_window(floor_h=FLOOR_H, ground=False):
    """Vertical-pier WINDOW bay — the main Deco facade unit.

    Two proud STONE PIERS frame the bay left/right (full height, they align
    across floors -> the soaring vertical lines). Between them: recessed GLASS
    (rendered as dark stone here; in UE slot 0 stone or a glass MI) crossed by a
    BRONZE GRILLE (geometric horizontal+vertical bars = the Deco window screen).
    A geometric CHEVRON/ZIGZAG bronze spandrel sits at the TOP of the bay (the
    panel between this floor's window and the next floor's sill).
    """
    bm = bmesh.new()
    pier_w = 46.0          # proud stone pier each side (the vertical Deco rib)
    spand_h = floor_h * 0.20  # top chevron spandrel zone
    # left + right stone piers, full height (these line up across floors)
    for sx in (-HALF_W, HALF_W - pier_w):
        ff = box(bm, sx, sx + pier_w, -HALF_D, HALF_D, 0, floor_h)
        for face in ff:
            face.material_index = 0  # stone pier
        # a thin proud flute up the face of each pier (within the Y depth
        # envelope so the module stays Y-centered for the generator pivot)
        cx = sx + pier_w/2
        fl = box(bm, cx - 6, cx + 6, -HALF_D, -HALF_D + 4.0, 8, floor_h - 8)
        for face in fl:
            face.material_index = 1  # bronze pinstripe up the pier
    # recessed window glazing block (set back in Y), spans between piers,
    # full height up to the spandrel band
    gx0, gx1 = -HALF_W + pier_w, HALF_W - pier_w
    gz0, gz1 = 0.0, floor_h - spand_h
    gf = box(bm, gx0, gx1, -HALF_D + 9.0, HALF_D, gz0, gz1)
    for face in gf:
        face.material_index = 0  # recessed glazing/stone (UE: glass MI on slot0)
    # BRONZE GRILLE across the glazing: 2 vertical mullions + 3 horizontal bars
    for mx in (gx0 + (gx1-gx0)*0.33, gx0 + (gx1-gx0)*0.66):
        mf = box(bm, mx - 4, mx + 4, -HALF_D + 6, -HALF_D + 9.0, gz0 + 6, gz1 - 6)
        for face in mf:
            face.material_index = 1
    for hz in (gz0 + (gz1-gz0)*0.25, gz0 + (gz1-gz0)*0.5, gz0 + (gz1-gz0)*0.75):
        hf = box(bm, gx0 + 6, gx1 - 6, -HALF_D + 6, -HALF_D + 9.0, hz - 4, hz + 4)
        for face in hf:
            face.material_index = 1
    # CHEVRON spandrel band at the top of the bay (geometric zigzag, bronze)
    zc = floor_h - spand_h/2
    n = 4
    span = gx1 - gx0
    step = span / n
    for i in range(n):
        bx = gx0 + i * step
        pts = [(bx, zc - spand_h*0.35), (bx + step/2, zc + spand_h*0.35),
               (bx + step, zc - spand_h*0.35)]
        bottom = [bm.verts.new((px, -HALF_D, pz)) for (px, pz) in pts]
        top = [bm.verts.new((px, -HALF_D + 4.0, pz)) for (px, pz) in pts]
        bm.faces.new(bottom)
        bm.faces.new(list(reversed(top)))
        for k in range(3):
            bm.faces.new((bottom[k], bottom[(k+1)%3], top[(k+1)%3], top[k]))
    # tag the chevron prisms bronze (they were created with default index 0)
    for face in bm.faces:
        if face.material_index == 0:
            zs = [v.co.z for v in face.verts]
            ys = [v.co.y for v in face.verts]
            if min(zs) >= floor_h - spand_h - 1 and max(ys) <= -HALF_D + 4.5:
                face.material_index = 1
    # ground variant: add a tall bronze base panel (lobby band)
    if ground:
        lb = box(bm, gx0, gx1, -HALF_D + 4.0, -HALF_D + 9.0, 0, floor_h * 0.18)
        for face in lb:
            face.material_index = 1
    return bm_to_obj(bm, "mod_ground" if ground else "mod_window")


def m_corner():
    """Stepped STONE corner PIER that closes the box. Same 400cm module width
    footprint (X centered) so the grammar tiles it; the visible mass is a stepped
    setback pier (deco quoin) with bronze cap banding, base-pivoted full height.
    """
    bm = bmesh.new()
    # stepped pier: 3 stacked stone boxes of decreasing footprint depth (setback)
    steps = [(HALF_W, HALF_D, 0.0, FLOOR_H * 0.55),
             (HALF_W * 0.86, HALF_D * 0.9, FLOOR_H * 0.55, FLOOR_H * 0.82),
             (HALF_W * 0.72, HALF_D * 0.8, FLOOR_H * 0.82, FLOOR_H)]
    for hw, hd, z0, z1 in steps:
        f = box(bm, -hw, hw, -hd, hd, z0, z1)
        for face in f:
            face.material_index = 0  # stone
        # bronze banding ring at each setback shelf
        band = box(bm, -hw, hw, -hd, -hd + 4.0, z1 - 8.0, z1)
        for face in band:
            face.material_index = 1
    # proud vertical flutes up the main lower section (Deco rib)
    _vertical_flutes(bm, -HALF_W + 20, HALF_W - 20, 8.0, FLOOR_H * 0.55 - 8.0,
                     n_flutes=4, depth_y=10.0, mat=0)
    return bm_to_obj(bm, "mod_corner")


def m_crown(crown_h=CROWN_H):
    """Stepped ZIGGURAT crown cap — the tower top. Same 400cm module width so the
    grammar can place it as a top course; the mass steps back in concentric
    setbacks to a central spire, bronze-banded (Chrysler/ESB crown silhouette).
    Base-pivoted (Z 0..crown_h), X-centered 400cm at the base.
    """
    bm = bmesh.new()
    # concentric ziggurat steps shrinking toward a central spire
    n_steps = 5
    for i in range(n_steps):
        frac0 = i / n_steps
        frac1 = (i + 1) / n_steps
        hw = HALF_W * (1.0 - 0.16 * i)      # shrink footprint each step
        hd = HALF_D + (HALF_W * 0.20) * (1.0 - 0.16 * i)  # crown is chunkier in Y
        z0 = crown_h * 0.55 * frac0
        z1 = crown_h * 0.55 * frac1
        f = box(bm, -hw, hw, -hd, hd, z0, z1)
        for face in f:
            face.material_index = 0  # stone
        # bronze banding at each setback shelf
        band = box(bm, -hw, hw, -hd, hd, z1 - 6.0, z1)
        for face in band:
            face.material_index = 1
    # central bronze spire / finial rising from the top step (pyramidal)
    sp_base = crown_h * 0.55
    spw = HALF_W * 0.10
    pts = [(-spw, -spw), (spw, -spw), (spw, spw), (-spw, spw)]
    bottom = [bm.verts.new((x, y, sp_base)) for (x, y) in pts]
    apex = bm.verts.new((0, 0, crown_h))
    spire_faces = []
    for k in range(4):
        spire_faces.append(bm.faces.new((bottom[k], bottom[(k+1) % 4], apex)))
    spire_faces.append(bm.faces.new(bottom))
    for face in spire_faces:
        face.material_index = 1  # bronze spire
    # crown front "sunburst" chevrons: a row of up-pointing bronze triangles on
    # the front face of the lowest crown step, sitting flush on the front plane
    # (the crown's Y half-depth at step 0) so the module stays Y-centered.
    yfront = -(HALF_D + (HALF_W * 0.20))   # crown step-0 front plane
    ch_h = crown_h * 0.11
    n = 5
    step_x = (2 * HALF_W) / n
    for i in range(n):
        bx = -HALF_W + step_x * i
        tpts = [(bx, 0.0), (bx + step_x/2, ch_h), (bx + step_x, 0.0)]
        b2 = [bm.verts.new((px, yfront, pz)) for (px, pz) in tpts]
        t2 = [bm.verts.new((px, yfront + 5.0, pz)) for (px, pz) in tpts]
        ch_faces = [bm.faces.new(b2), bm.faces.new(list(reversed(t2)))]
        for k in range(3):
            ch_faces.append(bm.faces.new((b2[k], b2[(k+1) % 3], t2[(k+1) % 3], t2[k])))
        for face in ch_faces:
            face.material_index = 1  # bronze sunburst
    return bm_to_obj(bm, "mod_crown")


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
        bg.inputs[0].default_value = (0.16, 0.15, 0.14, 1.0)  # warm neutral
        bg.inputs[1].default_value = 1.3


def add_cam_and_lights(half_w, floor_h):
    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam_data.lens = 55
    cam_data.clip_start = 1.0
    cam_data.clip_end = 1.0e6
    extent = max(half_w * 2, floor_h)
    dist = extent * 2.0
    cam.location = (dist * 0.95, -dist * 0.95, floor_h * 0.58 + extent * 0.18)
    target = mathutils.Vector((0, 0, floor_h * 0.5))
    direction = target - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam

    key = bpy.data.lights.new("Key", "SUN")
    key.energy = 4.0
    key.color = (1.0, 0.95, 0.85)  # warm key for stone
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

# (file, desc, builder, floor_h, expected_half_width)
MODULES = [
    ("mod_wall",   "Fluted stone pier wall panel (solid bay, vertical flutes)", lambda: m_wall(),                FLOOR_H,  HALF_W),
    ("mod_window", "Vertical-pier window bay (bronze grille + chevron spandrel)", lambda: m_window(),            FLOOR_H,  HALF_W),
    ("mod_corner", "Stepped stone corner pier (closes the box, bronze banding)", lambda: m_corner(),             FLOOR_H,  HALF_W),
    ("mod_ground", "Grand deco lobby (tall glazing + bronze base band)",         lambda: m_window(GROUND_H, ground=True), GROUND_H, HALF_W),
    ("mod_crown",  "Stepped ziggurat crown cap (setbacks + bronze spire)",       lambda: m_crown(),              CROWN_H,  HALF_W),
]

# FBX UNIT FIX (the iter4 lesson): set scene unit to cm so the FBX carries the cm
# unit and UE imports 1:1 (no 100x blow-up). scale_length 0.01 => 1 unit = 1 cm.
us = bpy.context.scene.unit_settings
us.system = "METRIC"
us.scale_length = 0.01
us.length_unit = "CENTIMETERS"

results = []
setup_render()

for fname, desc, builder, fh, ehw in MODULES:
    reset_scene()
    setup_render()
    stone, bronze = make_mats()
    obj = builder()
    finalize(obj, fname, stone, bronze, floor_h=fh)
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
