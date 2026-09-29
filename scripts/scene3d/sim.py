"""Simulate one garment's panels dressing the body with Blender cloth, and save every frame.

    bvenv/bin/python sim.py blouse|blazer|coat [--frames N]

Pinned vertices follow the choreographed path (a PC2 cache before the Cloth modifier), weighted so
panel edges lag, flutter and drape; the body is a collision object.
"""
import argparse
import sys
import time

import bpy
import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import HERE  # noqa: E402

FABRIC = {
    # mass per vertex (kg), tension, compression, shear, bending, air damping
    "blouse": dict(mass=0.10, tension=12, compression=12, shear=8, bending=0.08, air=1.4),
    "blazer": dict(mass=0.22, tension=30, compression=30, shear=20, bending=2.5, air=1.0),
    "coat": dict(mass=0.30, tension=35, compression=35, shear=25, bending=4.0, air=1.0),
}

ap = argparse.ArgumentParser()
ap.add_argument("name")
ap.add_argument("--frames", type=int, default=0)
ap.add_argument("--quality", type=int, default=7)
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])

data = np.load(HERE / f"work/{args.name}-panels.npz")
frames = args.frames or int(data["frames"])
body = np.load(HERE / "work/body-collision.npz")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = 30
scene.frame_start, scene.frame_end = 1, frames


def make_mesh(name, v, f):
    me = bpy.data.meshes.new(name)
    me.from_pydata(v.tolist(), [], f.tolist())
    me.update()
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    return ob


col = make_mesh("body", body["v"], body["f"])
cm = col.modifiers.new("collision", "COLLISION")
col.collision.thickness_outer = 0.002
col.collision.cloth_friction = 5

ob = make_mesh(args.name, data["v"], data["f"])
vg = ob.vertex_groups.new(name="pin")
pin = data["pin"]
for w in np.unique(np.round(pin, 2)):
    idx = np.nonzero(np.round(pin, 2) == w)[0].tolist()
    vg.add(idx, float(w), "REPLACE")

mc = ob.modifiers.new("path", "MESH_CACHE")
mc.cache_format = "PC2"
mc.filepath = str(HERE / f"work/{args.name}.pc2")
mc.frame_start = 1

cloth = ob.modifiers.new("cloth", "CLOTH")
s = cloth.settings
fab = FABRIC[args.name]
s.quality = args.quality
s.mass = fab["mass"]
s.tension_stiffness = fab["tension"]
s.compression_stiffness = fab["compression"]
s.shear_stiffness = fab["shear"]
s.bending_stiffness = fab["bending"]
s.air_damping = fab["air"]
s.vertex_group_mass = "pin"
# Pins loose in flight (edges trail and flutter), firm while the garment settles on her.
for frame, value in ((1, 1.5), (60, 1.5), (95, 6.0), (130, 6.0), (140, 1.5)):
    s.pin_stiffness = value
    s.keyframe_insert("pin_stiffness", frame=frame)
c = cloth.collision_settings
c.use_collision = True
c.distance_min = 0.003
c.collision_quality = 3
c.use_self_collision = False
cloth.point_cache.frame_start, cloth.point_cache.frame_end = 1, frames

out = np.zeros((frames, len(data["v"]), 3), np.float32)
t0 = time.time()
for f in range(1, frames + 1):
    scene.frame_set(f)
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    co = np.empty(len(ev.data.vertices) * 3, np.float32)
    ev.data.vertices.foreach_get("co", co)
    out[f - 1] = co.reshape(-1, 3)
    if f % 20 == 0:
        print(f"frame {f}/{frames} {time.time() - t0:.0f}s", flush=True)
np.save(HERE / f"work/{args.name}-sim.npy", out)
print(f"saved {out.shape} in {time.time() - t0:.0f}s")
