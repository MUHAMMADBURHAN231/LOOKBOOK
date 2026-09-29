"""Render the prepared robot parts (and optional garment meshes) with Cycles.

    bvenv/bin/python view_parts.py out_prefix [--angles 0,-35] [--extra mesh.npz ...]
"""
import argparse
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--angles", default="0,-35")
ap.add_argument("--extra", nargs="*", default=[])
ap.add_argument("--no-robot", action="store_true")
ap.add_argument("--res", type=int, default=520)
ap.add_argument("--samples", type=int, default=40)
ap.add_argument("--focus", type=float, default=0.5)
ap.add_argument("--zoom", type=float, default=1.0)
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene


def material(name, color, rough, metal=0.0, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat
    return m


mats = {"shell": material("shell", (0.9, 0.9, 0.91), 0.32, coat=0.4), "joint": material("joint", (0.05, 0.05, 0.055), 0.4, metal=0.3)}


def add(name, v, f, mat):
    me = bpy.data.meshes.new(name)
    me.from_pydata(v.tolist(), [], f.tolist())
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    ob.data.materials.append(mat)
    sc.collection.objects.link(ob)


d = np.load(HERE / "work/robot-parts.npz", allow_pickle=True)
if not args.no_robot:
    for n, c, v, f in zip(d["names"], d["cls"], d["verts"], d["faces"], strict=True):
        add(str(n), v, f, mats[str(c)])
for path in args.extra:
    e = np.load(path, allow_pickle=True)
    col = tuple(e["color"]) if "color" in e else (0.5, 0.6, 0.8)
    m = material(Path(path).stem, col, 0.7)
    m.use_backface_culling = False
    add(Path(path).stem, e["v"], e["f"], m)

sc.render.engine = "CYCLES"
sc.cycles.samples = args.samples
sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = args.res, int(args.res * 1.5)
sc.view_settings.view_transform = "AgX"
w = bpy.data.worlds.new("w")
sc.world = w
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.97, 0.965, 0.955, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.6
c = Vector((0, 0, 0.84))
for nm, loc, e, s in (("key", (-1.6, -2.6, 2.6), 380, 2.2), ("rim", (1.2, 2.4, 2.0), 260, 1.4), ("fill", (2.4, -1.4, 1.0), 90, 2.5)):
    L = bpy.data.lights.new(nm, "AREA")
    L.energy, L.size = e, s
    ob = bpy.data.objects.new(nm, L)
    ob.location = Vector(loc)
    ob.rotation_euler = (c - ob.location).to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(ob)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
cam.data.lens = 60
sc.collection.objects.link(cam)
sc.camera = cam
target = Vector((0, 0, 1.68 * args.focus))
for k, a in enumerate(float(x) for x in args.angles.split(",")):
    r = math.radians(a)
    cam.location = target + Vector((math.sin(r), -math.cos(r), 0.05)) * 4.2 / args.zoom
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = str(HERE / f"{args.out}-{k}.png")
    bpy.ops.render.render(write_still=True)
