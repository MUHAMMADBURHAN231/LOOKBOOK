"""Render a GLB from a few angles with soft studio light (Cycles, CPU).

    bvenv/bin/python preview.py model.glb out_prefix [--res 540] [--samples 48] [--angles 0,35,90]
"""
import argparse
import math
import sys

import bpy
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument("glb", nargs="+")
ap.add_argument("--out", required=True)
ap.add_argument("--res", type=int, default=540)
ap.add_argument("--samples", type=int, default=48)
ap.add_argument("--angles", default="0,35,90")
ap.add_argument("--yaw", type=float, default=0.0, help="degrees added to every angle (model facing)")
ap.add_argument("--focus", type=float, default=0.5, help="height fraction to aim at")
ap.add_argument("--zoom", type=float, default=1.0, help=">1 frames the upper body")
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])

bpy.ops.wm.read_factory_settings(use_empty=True)
for path in args.glb:
    bpy.ops.import_scene.gltf(filepath=path)

meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
# Meshes with vertex colours and no texture: show the colours, slightly soft like fabric.
for o in meshes:
    mats = [m for m in o.data.materials if m]
    has_tex = any(n.type == "TEX_IMAGE" for m in mats if m.use_nodes for n in m.node_tree.nodes)
    if o.data.color_attributes and not has_tex:
        mat = bpy.data.materials.new("vcol")
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = nt.nodes["Principled BSDF"]
        attr = nt.nodes.new("ShaderNodeVertexColor")
        attr.layer_name = o.data.color_attributes[0].name
        nt.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = 0.8
        bsdf.inputs["Sheen Weight"].default_value = 0.4
        o.data.materials.clear()
        o.data.materials.append(mat)
        for poly in o.data.polygons:
            poly.use_smooth = True
lo = Vector((1e9, 1e9, 1e9))
hi = Vector((-1e9, -1e9, -1e9))
for o in meshes:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        lo = Vector(map(min, lo, w))
        hi = Vector(map(max, hi, w))
center = (lo + hi) / 2
height = hi.z - lo.z
print("bounds", tuple(round(v, 3) for v in lo), tuple(round(v, 3) for v in hi))

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = args.samples
scene.cycles.use_denoising = True
scene.render.resolution_x = args.res
scene.render.resolution_y = int(args.res * 16 / 9)
scene.view_settings.view_transform = "AgX"
scene.render.film_transparent = False

world = bpy.data.worlds.new("w")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.97, 0.965, 0.955, 1)
bg.inputs[1].default_value = 0.35


def area(name, loc, energy, size):
    light = bpy.data.lights.new(name, "AREA")
    light.energy = energy
    light.size = size
    ob = bpy.data.objects.new(name, light)
    ob.location = loc
    direction = center - Vector(loc)
    ob.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(ob)


s = height
area("key", (center.x - 1.2 * s, center.y - 1.6 * s, center.z + 0.6 * s), 260 * s * s, 1.5 * s)
area("fill", (center.x + 1.6 * s, center.y - 1.0 * s, center.z + 0.2 * s), 90 * s * s, 2.0 * s)
area("rim", (center.x + 0.4 * s, center.y + 1.6 * s, center.z + 0.8 * s), 160 * s * s, 1.0 * s)

cam_data = bpy.data.cameras.new("cam")
cam_data.lens = 85
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
dist = height * 3.3 / args.zoom
target = center + Vector((0, 0, height * (args.focus - 0.5)))
for k, a in enumerate(float(x) for x in args.angles.split(",")):
    r = math.radians(a + args.yaw)
    cam.location = target + Vector((math.sin(r) * dist, -math.cos(r) * dist, 0.05 * height))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = f"{args.out}-{k}.png"
    bpy.ops.render.render(write_still=True)
    print("wrote", scene.render.filepath)
