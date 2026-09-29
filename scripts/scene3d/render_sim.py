"""Render frames of a garment simulation on the body (Cycles).

    bvenv/bin/python render_sim.py blazer --frames 1,30,60,80,100,130 [--angle 0] [--res 360]
"""
import argparse
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve().parent
COLORS = {"blouse": (0.55, 0.66, 0.80), "blazer": (0.018, 0.018, 0.02), "coat": (0.50, 0.26, 0.11)}

ap = argparse.ArgumentParser()
ap.add_argument("name")
ap.add_argument("--frames", default="1,30,60,80,100,130")
ap.add_argument("--angle", type=float, default=0)
ap.add_argument("--res", type=int, default=360)
ap.add_argument("--samples", type=int, default=24)
ap.add_argument("--out", default="")
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=str(HERE / "work/body.glb"))

data = np.load(HERE / f"work/{args.name}-panels.npz")
sim = np.load(HERE / f"work/{args.name}-sim.npy")
sys.path.insert(0, str(HERE))
from seams import fuse_seams, zip_weight  # noqa: E402
sim = fuse_seams(sim, data["seams"], closed=zip_weight(len(sim), leaves=args.name != "coat"))
me = bpy.data.meshes.new("g")
me.from_pydata(data["v"].tolist(), [], data["f"].tolist())
for p in me.polygons:
    p.use_smooth = True
ob = bpy.data.objects.new("g", me)
scene.collection.objects.link(ob)
mat = bpy.data.materials.new("fabric")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (*COLORS[args.name], 1)
bsdf.inputs["Roughness"].default_value = 0.75
bsdf.inputs["Sheen Weight"].default_value = 0.15
me.materials.append(mat)
ob.modifiers.new("solid", "SOLIDIFY").thickness = 0.003

scene.render.engine = "CYCLES"
scene.cycles.samples = args.samples
scene.cycles.use_denoising = True
scene.render.resolution_x = int(args.res * 1.6)
scene.render.resolution_y = args.res
scene.view_settings.view_transform = "AgX"
world = bpy.data.worlds.new("w")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.97, 0.965, 0.955, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.4
center = Vector((float(__import__("os").environ.get("CX", 0.3)), 0, float(__import__("os").environ.get("CZ", 1.0))))
for nm, loc, e, sz in (("key", (-1.8, -2.6, 2.4), 450, 2.5), ("fill", (2.6, -1.6, 1.4), 160, 3), ("rim", (0.6, 2.6, 2.2), 260, 1.6)):
    L = bpy.data.lights.new(nm, "AREA")
    L.energy, L.size = e, sz
    o = bpy.data.objects.new(nm, L)
    o.location = loc
    o.rotation_euler = (center - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(o)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
cam.data.lens = 35
scene.collection.objects.link(cam)
scene.camera = cam
r = math.radians(args.angle)
DIST = float(__import__("os").environ.get("DIST", 4.6))
cam.location = center + Vector((math.sin(r) * DIST, -math.cos(r) * DIST, 0.15))
cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()

prefix = args.out or f"r/{args.name}-sim"
for f in [int(x) for x in args.frames.split(",")]:
    me.vertices.foreach_set("co", sim[f - 1].ravel())
    me.update()
    scene.render.filepath = str(HERE / f"{prefix}-{f:03d}.png")
    bpy.ops.render.render(write_still=True)
    print("wrote", scene.render.filepath, flush=True)
