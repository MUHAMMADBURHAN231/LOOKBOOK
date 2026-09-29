"""Simplified body for cloth collisions (about 40k triangles) -> work/body-collision.npz."""
import json

import numpy as np
import pymeshlab

from common import HERE, canonical, load_raw

lm = json.loads((HERE / "work/landmarks.json").read_text())
body, _ = canonical(load_raw(HERE / "gen/body-meshy.glb"), lm["ref"])
# Weld texture seams first so the simplified surface is closed.
key = np.round(body.vertices / 1e-6).astype(np.int64)
_, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
ms = pymeshlab.MeshSet()
ms.add_mesh(pymeshlab.Mesh(body.vertices[first], inv.ravel()[body.faces]))
ms.meshing_decimation_quadric_edge_collapse(targetfacenum=40000, preservenormal=True)
m = ms.current_mesh()
np.savez(HERE / "work/body-collision.npz", v=m.vertex_matrix(), f=m.face_matrix())
print("collision body", m.vertex_matrix().shape, m.face_matrix().shape)
