"""Prepare the NEXBOT robot for the dressing scene.

    bvenv/bin/python robot_prep.py nexbot.gltf

- Drops the logo, lights and cameras from the Spline export.
- Swings each arm out at the shoulder (A-pose), so sleeves can close around the arms.
- Scales to 1.68 m, feet on z=0, torso centred on x=y=0, facing -Y (Blender axes).
- Writes work/robot-parts.npz (every part's triangles in that frame, with a material class) and
  work/landmarks.json (shoulders, elbows, wrists, arm axes, neck, hips, knees) measured from parts.
"""
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
HEIGHT = 1.68
ARM_OUT = math.radians(14)

src = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else sys.argv[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(src))
scene = bpy.context.scene

# Drop everything that isn't the robot.
drop = set()
for o in scene.objects:
    n = (o.name or "").lower()
    if o.type in ("LIGHT", "CAMERA") or n.startswith("logo") or n.startswith("shape"):
        drop.add(o)
        drop.update(o.children_recursive)
for o in drop:
    bpy.data.objects.remove(o, do_unlink=True)

# A-pose: rotate each arm about its shoulder pivot, outward.
for name, sign in (("Hand LEFT", -1), ("Hand LEFT.001", 1)):
    arm = bpy.data.objects[name]
    p = arm.matrix_world.translation.copy()
    rot = Matrix.Translation(p) @ Matrix.Rotation(-sign * ARM_OUT, 4, "Y") @ Matrix.Translation(-p)
    arm.matrix_world = rot @ arm.matrix_world
bpy.context.view_layer.update()

meshes = [o for o in scene.objects if o.type == "MESH"]
allpts = np.concatenate([np.array([o.matrix_world @ v.co for v in o.data.vertices]) for o in meshes])
zmin, zmax = allpts[:, 2].min(), allpts[:, 2].max()
scale = HEIGHT / (zmax - zmin)
body = bpy.data.objects["Body"]
bpts = np.array([body.matrix_world @ v.co for v in body.data.vertices])
cx = (bpts[:, 0].min() + bpts[:, 0].max()) / 2
cy = (bpts[:, 1].min() + bpts[:, 1].max()) / 2


def canon(p):
    p = np.asarray(p, dtype=np.float64)
    return (p - np.array([cx, cy, zmin])) * scale


names, cls, verts, faces = [], [], [], []
for o in meshes:
    me = o.data
    me.calc_loop_triangles()
    v = canon([o.matrix_world @ x.co for x in me.vertices])
    f = np.array([t.vertices[:] for t in me.loop_triangles], dtype=np.int32)
    size = (v.max(0) - v.min(0)).max()
    # Small parts (joint rings, pivots, neck segments) are graphite; the shells are white.
    kind = "joint" if size < 0.07 or o.name.startswith(("Cylinder", "Ellipse", "Mesh_8", "Cube.")) or o.name == "Cube" else "shell"
    names.append(o.name)
    cls.append(kind)
    verts.append(v.astype(np.float32))
    faces.append(f)
np.savez(HERE / "work/robot-parts.npz", names=np.array(names), cls=np.array(cls),
         verts=np.array(verts, dtype=object), faces=np.array(faces, dtype=object), allow_pickle=True)


def world(name):
    return canon(bpy.data.objects[name].matrix_world.translation)


def bbox(name):
    o = bpy.data.objects[name]
    pts = []
    for c in [o] + list(o.children_recursive):
        if c.type == "MESH":
            pts += [c.matrix_world @ x.co for x in c.data.vertices]
    pts = canon(pts)
    return pts.min(0), pts.max(0)


lm = {"height": HEIGHT, "scale": scale}
for side, arm_root, elbow, hand in (("l", "Hand LEFT.001", "elbow.001", "Hand.002"), ("r", "Hand LEFT", "elbow", "Hand")):
    sh = world(arm_root)
    el = world(elbow)
    hand_obj = bpy.data.objects[hand]
    hp = canon([hand_obj.matrix_world @ x.co for x in hand_obj.data.vertices])
    # Wrist: the end of the hand nearest the elbow.
    wr = hp[np.argsort(np.linalg.norm(hp - el, axis=1))[:40]].mean(0)
    axis = wr - sh
    lm[f"shoulder_{side}"] = sh.tolist()
    lm[f"elbow_{side}"] = el.tolist()
    lm[f"wrist_{side}"] = wr.tolist()
    lm[f"arm_dir_{side}"] = (axis / np.linalg.norm(axis)).tolist()
    lm[f"hand_{side}"] = [hp.min(0).tolist(), hp.max(0).tolist()]
blo, bhi = bbox("Body")
lm["torso"] = [blo.tolist(), bhi.tolist()]
lm["neck_z"] = float(bhi[2])
plo, phi = bbox("Pelvic")
lm["hip_z"] = float(phi[2])
lm["crotch_z"] = float(plo[2])
llo, lhi = bbox("shin.001")
lm["knee_z"] = float(lhi[2])
hlo, hhi = bbox("Head")
lm["head"] = [hlo.tolist(), hhi.tolist()]
(HERE / "work/landmarks.json").write_text(json.dumps(lm, indent=1))
print(json.dumps({k: (np.round(v, 3).tolist() if isinstance(v, list) else round(v, 3)) for k, v in lm.items()}, indent=None))
print("parts:", len(names), "shell", cls.count("shell"), "joint", cls.count("joint"))
