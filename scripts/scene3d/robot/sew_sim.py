"""Sew a garment's pattern pieces onto the robot and let it drape (Blender cloth).

    bvenv/bin/python sew_sim.py blouse [--frames 90]

Sewing springs (loose edges between paired seam points) pull the pieces together; gravity eases in
once the seams have started to close; the robot's envelope is the collision body. Saves every
frame to work/<name>-sew.npy.
"""
import argparse
import sys
import time
from pathlib import Path

import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
FABRIC = {
    # mass per vertex (kg), tension/compression, shear, bending, air damping
    "blouse": dict(mass=0.08, tension=10, shear=6, bending=0.05, air=1.5),
    "blazer": dict(mass=0.16, tension=28, shear=18, bending=1.2, air=1.0),
    "coat": dict(mass=0.22, tension=32, shear=22, bending=2.0, air=1.0),
}
ap = argparse.ArgumentParser()
ap.add_argument("name")
ap.add_argument("--frames", type=int, default=90)
ap.add_argument("--quality", type=int, default=10)
ap.add_argument("--self", action="store_true", help="self collisions (slower)")
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])

d = np.load(HERE / f"work/{args.name}-pattern.npz")
body = np.load(HERE / "work/body-collision.npz")
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = 30
sc.frame_start, sc.frame_end = 1, args.frames


def make(name, v, e, f):
    me = bpy.data.meshes.new(name)
    me.from_pydata(v.tolist(), e, f.tolist())
    me.update()
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    return ob


col = make("body", body["v"], [], body["f"])
col.modifiers.new("collision", "COLLISION")
col.collision.thickness_outer = 0.003
col.collision.cloth_friction = 2

ob = make(args.name, d["v"], d["sew"].tolist(), d["f"])
cloth = ob.modifiers.new("cloth", "CLOTH")
s = cloth.settings
fab = FABRIC[args.name]
s.quality = args.quality
s.mass = fab["mass"]
s.tension_stiffness = s.compression_stiffness = fab["tension"]
s.shear_stiffness = fab["shear"]
s.bending_stiffness = fab["bending"]
s.air_damping = fab["air"]
s.use_sewing_springs = True
s.sewing_force_max = 6.0
for frame, g in ((1, 0.0), (18, 0.0), (45, 1.0)):
    s.effector_weights.gravity = g
    s.effector_weights.keyframe_insert("gravity", frame=frame)
c = cloth.collision_settings
c.use_collision = True
c.distance_min = 0.004
c.collision_quality = 4
c.use_self_collision = args.self
c.self_distance_min = 0.004
cloth.point_cache.frame_start, cloth.point_cache.frame_end = 1, args.frames

out = np.zeros((args.frames, len(d["v"]), 3), np.float32)
t0 = time.time()
for fr in range(1, args.frames + 1):
    sc.frame_set(fr)
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    co = np.empty(len(ev.data.vertices) * 3, np.float32)
    ev.data.vertices.foreach_get("co", co)
    out[fr - 1] = co.reshape(-1, 3)
    if fr % 15 == 0:
        sew = d["sew"]
        gap = np.linalg.norm(out[fr - 1][sew[:, 0]] - out[fr - 1][sew[:, 1]], axis=1)
        print(f"frame {fr}: seam gap mean {gap.mean() * 100:.1f} cm, max {gap.max() * 100:.1f} cm, "
              f"lowest point {out[fr - 1][:, 2].min():.2f} m, {time.time() - t0:.0f}s", flush=True)
np.save(HERE / f"work/{args.name}-sew.npy", out)
print("saved", out.shape)
