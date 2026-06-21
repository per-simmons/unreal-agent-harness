"""Headless Blender jobs for the UE methods sandbox.
Run: /Applications/Blender.app/Contents/MacOS/Blender --background --python blender_jobs.py
- M4: build a procedural art-deco massing (setbacks + spire) -> FBX
- Convert Meshy GLB -> FBX
- Convert TRELLIS GLB -> FBX
(import_file in UE only accepts FBX/OBJ, not glTF/GLB.)
"""
import bpy, os

ASSETS = os.path.expanduser("~/coding/unreal-agent-harness/assets")
OUT = os.path.join(ASSETS, "generated3d")


def clear():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.armatures):
        for b in list(coll):
            if b.users == 0:
                coll.remove(b)


def box(name, sx, sy, sz, z):
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, z))
    o = bpy.context.active_object
    o.scale = (sx, sy, sz)
    o.name = name


def build_m4(fbx):
    clear()
    # Art-deco massing in meters: stacked setbacks + central spire.
    box("base", 6, 6, 9, 9)      # 12x12 footprint, 18 m tall
    box("mid", 4, 4, 6, 24)      # setback, 12 m tall, sits at 18
    box("top", 2.5, 2.5, 4, 34)  # setback, 8 m tall, sits at 30
    box("spire", 0.5, 0.5, 3, 41)  # spire, sits at 38
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.fbx(filepath=fbx, apply_unit_scale=True)
    print("M4 EXPORTED", fbx)


def convert(glb, fbx):
    clear()
    bpy.ops.import_scene.gltf(filepath=glb)
    bpy.ops.export_scene.fbx(filepath=fbx, path_mode="COPY", embed_textures=True)
    print("CONVERTED", glb, "->", fbx)


os.makedirs(os.path.join(OUT, "m4_blender"), exist_ok=True)
build_m4(os.path.join(OUT, "m4_blender", "artdeco_building.fbx"))

meshy_glb = os.path.join(OUT, "meshy", "building.glb")
if os.path.exists(meshy_glb):
    convert(meshy_glb, os.path.join(OUT, "meshy", "building.fbx"))

trellis_glb = os.path.join(OUT, "trellis", "building.glb")
if os.path.exists(trellis_glb):
    convert(trellis_glb, os.path.join(OUT, "trellis", "building.fbx"))

print("ALL BLENDER JOBS DONE")
