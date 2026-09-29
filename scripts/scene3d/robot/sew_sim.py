"""Sew a garment's pattern pieces onto the robot and let it drape (Blender cloth).

    python sew_sim.py blouse [--frames 130] [--sew-force 3] [--friction 0.3] [--no-self]

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
    # mass per vertex (kg), tension/compression, shear, bending, air damping; sewing force cap (N),
    # in proportion to the mass so every garment closes at the same gentle pace
    "blouse": dict(mass=0.08, tension=15, shear=8, bending=0.15, air=1.5, sew=3.0),
    "blazer": dict(mass=0.16, tension=40, shear=25, bending=3.0, air=1.0, sew=6.0),
    "coat": dict(mass=0.22, tension=40, shear=25, bending=4.0, air=1.0, sew=8.5),
}
ap = argparse.ArgumentParser()
ap.add_argument("name")
ap.add_argument("--frames", type=int, default=130)
ap.add_argument("--sew-force", type=float, default=None, help="override the fabric's sewing force")
ap.add_argument("--friction", type=float, default=0.3)
ap.add_argument("--quality", type=int, default=10)
ap.add_argument("--no-self", dest="self", action="store_false", help="skip self collisions (faster)")
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
col.collision.cloth_friction = args.friction  # low: fabric slides over the shoulder brackets into place

ob = make(args.name, d["v"], d["sew"].tolist(), d["f"])
# Rest shape: the flat pattern (lengths and flat bending), not the arrangement around the robot.
ob.shape_key_add(name="Basis")
rest = ob.shape_key_add(name="pattern")
rest.data.foreach_set("co", np.column_stack([d["uv"], np.zeros(len(d["uv"]))]).astype(np.float32).ravel())
rest.value = 0.0
cloth = ob.modifiers.new("cloth", "CLOTH")
s = cloth.settings
fab = FABRIC[args.name]
s.quality = args.quality
s.mass = fab["mass"]
s.tension_stiffness = s.compression_stiffness = fab["tension"]
s.shear_stiffness = fab["shear"]
s.bending_stiffness = fab["bending"]
s.air_damping = fab["air"]
s.rest_shape_key = rest
s.use_sewing_springs = True
s.sewing_force_max = args.sew_force or fab["sew"]  # gentle: the pieces close over ~1 s, not a snap
for frame, g in ((1, 0.0), (30, 0.0), (70, 1.0)):
    s.effector_weights.gravity = g
    s.effector_weights.keyframe_insert("gravity", frame=frame)
c = cloth.collision_settings
c.use_collision = True
c.distance_min = 0.004
c.collision_quality = 4
c.use_self_collision = args.self
c.self_distance_min = 0.003
cloth.point_cache.frame_start, cloth.point_cache.frame_end = 1, args.frames

out = np.zeros((args.frames, len(d["v"]), 3), np.float32)
t0 = time.time()
for fr in range(1, args.frames + 1):
    sc.frame_set(fr)
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    co = np.empty(len(ev.data.vertices) * 3, np.float32)
    ev.data.vertices.foreach_get("co", co)
    out[fr - 1] = co.reshape(-1, 3)
    if fr % 10 == 0:
        sew = d["sew"]
        gap = np.linalg.norm(out[fr - 1][sew[:, 0]] - out[fr - 1][sew[:, 1]], axis=1)
        print(f"frame {fr}: seam gap mean {gap.mean() * 100:.1f} cm, max {gap.max() * 100:.1f} cm, "
              f"lowest point {out[fr - 1][:, 2].min():.2f} m, {time.time() - t0:.0f}s", flush=True)
np.save(HERE / f"work/{args.name}-sew.npy", out)
print("saved", out.shape)
