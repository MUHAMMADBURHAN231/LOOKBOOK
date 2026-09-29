"""Robot for the web: shells and joints as two meshes (three.js axes), smooth normals.

Writes work/robot-web.glb; compress with gltf-transform (see README).
"""
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
d = np.load(HERE / "work/robot-parts.npz", allow_pickle=True)
scene = trimesh.Scene()
for kind in ("shell", "joint"):
    parts = [trimesh.Trimesh(v, f, process=True) for v, f, c in zip(d["verts"], d["faces"], d["cls"], strict=True) if c == kind]
    m = trimesh.util.concatenate(parts)
    m.merge_vertices()
    n = m.vertex_normals.copy()
    v = m.vertices.copy()
    m.vertices = np.column_stack([v[:, 0], v[:, 2], -v[:, 1]])
    m.vertex_normals = np.column_stack([n[:, 0], n[:, 2], -n[:, 1]])
    m.visual = trimesh.visual.ColorVisuals(m)
    scene.add_geometry(m, node_name=kind, geom_name=kind)
    print(kind, len(m.vertices), "verts", len(m.faces), "faces")
scene.export(HERE / "work/robot-web.glb", include_normals=True)
