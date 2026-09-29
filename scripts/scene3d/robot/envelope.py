"""Smooth closed skin around the robot (joint gaps filled) -> work/envelope.npz.

Used as the cloth collision body and as the base the garments are shaped from.
"""
import json
from pathlib import Path

import numpy as np
import pymeshlab
import trimesh
from scipy import ndimage
from skimage import measure

HERE = Path(__file__).resolve().parent
PITCH = 0.006

d = np.load(HERE / "work/robot-parts.npz", allow_pickle=True)
parts = [trimesh.Trimesh(v, f, process=False) for v, f in zip(d["verts"], d["faces"], strict=True)]
allv = np.concatenate([p.vertices for p in parts])
lo = allv.min(0) - 0.05
dims = np.ceil((allv.max(0) + 0.05 - lo) / PITCH).astype(int)
occ = np.zeros(dims, bool)
for p in parts:
    # Surface voxels by dense sampling of each part's surface, then fill its interior.
    pts, _ = trimesh.sample.sample_surface_even(p, max(2000, int(p.area / (PITCH * PITCH) * 4)))
    idx = np.floor((pts - lo) / PITCH).astype(int)
    sub = np.zeros(dims, bool)
    sub[idx[:, 0], idx[:, 1], idx[:, 2]] = True
    sub = ndimage.binary_dilation(sub, iterations=1)
    sub = ndimage.binary_fill_holes(sub)
    occ |= sub
# Close the gaps between parts (joints) without merging the arms into the torso.
ball = ndimage.generate_binary_structure(3, 1)
occ = ndimage.binary_closing(occ, structure=ball, iterations=3)
occ = ndimage.binary_fill_holes(occ)
verts, faces, _, _ = measure.marching_cubes(occ.astype(np.float32), 0.5, spacing=(PITCH,) * 3)
verts += lo
ms = pymeshlab.MeshSet()
ms.add_mesh(pymeshlab.Mesh(verts, faces[:, ::-1]))
ms.apply_coord_taubin_smoothing(stepsmoothnum=30)
ms.meshing_isotropic_explicit_remeshing(targetlen=pymeshlab.PureValue(0.008), iterations=4)
m = ms.current_mesh()
env = trimesh.Trimesh(m.vertex_matrix(), m.face_matrix(), process=True)
env = max(env.split(only_watertight=False), key=lambda x: len(x.faces))
trimesh.repair.fix_normals(env)
np.savez(HERE / "work/envelope.npz", v=env.vertices, f=env.faces)
# Collision copy, simplified.
ms = pymeshlab.MeshSet()
ms.add_mesh(pymeshlab.Mesh(env.vertices, env.faces))
ms.meshing_decimation_quadric_edge_collapse(targetfacenum=40000, preservenormal=True)
c = ms.current_mesh()
np.savez(HERE / "work/body-collision.npz", v=c.vertex_matrix(), f=c.face_matrix())
print(f"envelope: {len(env.vertices)} verts, watertight {env.is_watertight}, volume {env.volume * 1000:.1f} L, bounds {env.bounds.round(3).tolist()}")
lm = json.loads((HERE / "work/landmarks.json").read_text())
body = [p for n, p in zip(d["names"], parts, strict=True) if n == "Body"][0]
lm["armhole_x"] = float(np.abs(body.vertices[:, 0]).max())
(HERE / "work/landmarks.json").write_text(json.dumps(lm, indent=1))
print("armhole_x", round(lm["armhole_x"], 3))
