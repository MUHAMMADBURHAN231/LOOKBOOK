"""Body for the web: canonical scale, three.js axes, smooth normals across texture seams.

Writes work/body-n.glb; compress it with gltf-transform (see README).
"""
import json

import numpy as np
import trimesh

from common import HERE, canonical, load_raw

lm = json.loads((HERE / "work/landmarks.json").read_text())
body, _ = canonical(load_raw(HERE / "gen/body-meshy.glb"), lm["ref"])
# Normals on the welded surface, copied back to the seam-split vertices, so texture seams don't
# show as shading seams.
key = np.round(body.vertices / 1e-6).astype(np.int64)
_, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
inv = inv.ravel()
welded = trimesh.Trimesh(body.vertices[first], inv[body.faces], process=False)
n = welded.vertex_normals[inv]
m = body.copy()
v = m.vertices
m.vertices = np.column_stack([v[:, 0], v[:, 2], -v[:, 1]])
m.vertex_normals = np.column_stack([n[:, 0], n[:, 2], -n[:, 1]])
m.export(HERE / "work/body-n.glb", include_normals=True)
print("body", len(m.vertices), "vertices", len(m.faces), "faces")
