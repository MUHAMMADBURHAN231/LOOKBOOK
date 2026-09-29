"""Split a fitted garment into sewing panels and choreograph them onto the body.

    python panels.py blouse|blazer|coat

Writes work/<name>-panels.npz: panel mesh (seams split), per-vertex pin weights, and per-frame rigid
transforms of every panel (the path the cloth is pinned to). Also writes the pinned target path as a
PC2 point cache for Blender.

Timeline (30 fps): 0-60 fly in from the right and fan out around her, 60-95 close onto her,
95-130 settle; for garments that are later taken off, 130-190 open and fly off to the left.
"""
from __future__ import annotations

import json
import struct
import sys

import numpy as np
import trimesh
from scipy.spatial.transform import Rotation, Slerp

from common import HERE

name = sys.argv[1]
LEAVES = name != "coat"
FRAMES = 190 if LEAVES else 130
D = 0.28  # how far outside the body panels wait before closing

lm = json.loads((HERE / "work/landmarks.json").read_text())
g = np.load(HERE / f"work/{name}-cloth.npz")
V, F = g["v"], g["f"]

# --- Panel labels per vertex: sleeve halves, then torso front (split left/right) and back.
labels = np.full(len(V), -1)
for k, s in enumerate(("l", "r")):
    S = np.array(lm[f"shoulder_{s}"])
    d = np.array(lm[f"arm_dir_{s}"])
    sign = 1 if s == "l" else -1
    rel = V - S
    along = rel @ d
    radial = np.linalg.norm(rel - np.outer(along, d), axis=1)
    sleeve = (sign * V[:, 0] > 0.155) & (radial < 0.11) & (along > -0.06)
    # Split each sleeve into front and back halves along the arm.
    yperp = np.array([0, 1, 0]) - d * d[1]
    yperp /= np.linalg.norm(yperp)
    front = rel @ yperp < 0
    labels[sleeve & front] = 2 + 2 * k
    labels[sleeve & ~front] = 3 + 2 * k
torso = labels < 0
labels[torso & (V[:, 1] >= 0)] = 1  # back
labels[torso & (V[:, 1] < 0) & (V[:, 0] >= 0)] = 0  # front, her left
labels[torso & (V[:, 1] < 0) & (V[:, 0] < 0)] = 6  # front, her right
PANEL_NAMES = ["front_l", "back", "sleeve_l_front", "sleeve_l_back", "sleeve_r_front", "sleeve_r_back", "front_r"]

# Face labels by majority, then smooth them a little over the face graph so seams are clean.
fl = np.array([np.bincount(labels[f], minlength=7).argmax() for f in F])
adj = trimesh.graph.face_adjacency(faces=F)
for _ in range(3):
    votes = np.zeros((len(F), 7))
    np.add.at(votes, (np.arange(len(F)), fl), 1.5)
    np.add.at(votes, (adj[:, 0], fl[adj[:, 1]]), 1)
    np.add.at(votes, (adj[:, 1], fl[adj[:, 0]]), 1)
    fl = votes.argmax(1)

# Split vertices along seams: one copy per (vertex, panel) pair.
pairs = np.stack([F.ravel(), np.repeat(fl, 3)], 1)
uniq, inv = np.unique(pairs, axis=0, return_inverse=True)
inv = inv.ravel()
PV = V[uniq[:, 0]]
PF = inv.reshape(-1, 3)
panel = uniq[:, 1]
source = uniq[:, 0]  # original vertex, for colours and for sewing pairs
present = sorted(set(panel.tolist()))
print(f"{name}: {len(V)} -> {len(PV)} vertices; panels " + ", ".join(f"{PANEL_NAMES[p]}={int((panel == p).sum())}" for p in present))

# Seam pairs (same original vertex in two panels), for sewing springs.
order = np.argsort(source, kind="stable")
s_sorted = source[order]
same = np.nonzero(s_sorted[1:] == s_sorted[:-1])[0]
seams = np.stack([order[same], order[same + 1]], 1)

# --- Straighten the seam edges. Panels are cut along existing triangle edges, which leaves a
# staircase that shows as saw teeth while the panels are apart. Smooth each seam-edge vertex along
# its own panel's edge (and relax the next ring in a little); the two sides are fused back together
# once the seam closes.
mesh0 = trimesh.Trimesh(PV, PF, process=False)
be0 = mesh0.edges[trimesh.grouping.group_rows(mesh0.edges_sorted, require_count=1)]
on_seam = np.zeros(len(PV), bool)
on_seam[seams.ravel()] = True
be0 = be0[on_seam[be0[:, 0]] & on_seam[be0[:, 1]]]
sv = np.unique(be0)
PV = PV.copy()
for _ in range(10):
    acc = np.zeros_like(PV)
    cnt = np.zeros(len(PV))
    np.add.at(acc, be0[:, 0], PV[be0[:, 1]])
    np.add.at(acc, be0[:, 1], PV[be0[:, 0]])
    np.add.at(cnt, be0[:, 0], 1)
    np.add.at(cnt, be0[:, 1], 1)
    PV[sv] = 0.5 * PV[sv] + 0.5 * acc[sv] / np.maximum(cnt[sv], 1)[:, None]
e0 = mesh0.edges_unique
ring = np.zeros(len(PV), bool)
ring[e0[np.isin(e0, sv).any(1)].ravel()] = True
ring[sv] = False
for _ in range(3):
    acc = np.zeros_like(PV)
    cnt = np.zeros(len(PV))
    np.add.at(acc, e0[:, 0], PV[e0[:, 1]])
    np.add.at(acc, e0[:, 1], PV[e0[:, 0]])
    np.add.at(cnt, e0[:, 0], 1)
    np.add.at(cnt, e0[:, 1], 1)
    PV[ring] = 0.5 * PV[ring] + 0.5 * acc[ring] / np.maximum(cnt[ring], 1)[:, None]
# Both sides of a seam were straightened along their own panel's edge and have drifted apart; put
# each pair back together at their midpoint so every seam starts closed at rest.
mid = 0.5 * (PV[seams[:, 0]] + PV[seams[:, 1]])
PV[seams[:, 0]] = mid
PV[seams[:, 1]] = mid
# Straightening shortcuts across curves, which can pull seam points into her (around the arm, at the
# elbow). Put everything back at least 10 mm outside the body.
_cb = np.load(HERE / "work/body-collision.npz")
_body = trimesh.Trimesh(_cb["v"], _cb["f"], process=False)
_cp, _, _tri = _body.nearest.on_surface(PV)
_sd = np.einsum("ij,ij->i", PV - _cp, _body.face_normals[_tri])
_low = _sd < 0.009
PV[_low] += _body.face_normals[_tri][_low] * (0.010 - _sd[_low])[:, None]
print(f"straightened {len(sv)} seam-edge vertices; moved {int(_low.sum())} back outside the body")

# --- Pin weights: strong in the middle of each panel, weak at its edges so edges flutter.
mesh = trimesh.Trimesh(PV, PF, process=False)
edges = mesh.edges_unique
boundary = np.zeros(len(PV), bool)
be = mesh.edges[trimesh.grouping.group_rows(mesh.edges_sorted, require_count=1)]
boundary[be.ravel()] = True
dist = np.where(boundary, 0.0, np.inf)
elen = np.linalg.norm(PV[edges[:, 0]] - PV[edges[:, 1]], axis=1)
for _ in range(40):  # Bellman-Ford style relaxation along edges
    a = np.minimum(dist[edges[:, 0]], dist[edges[:, 1]] + elen)
    b = np.minimum(dist[edges[:, 1]], dist[edges[:, 0]] + elen)
    dist[edges[:, 0]] = np.minimum(dist[edges[:, 0]], a)
    dist[edges[:, 1]] = np.minimum(dist[edges[:, 1]], b)
dist = np.nan_to_num(dist, posinf=1.0)
core = np.clip(dist / 0.06, 0, 1)
pin = 0.4 + 0.6 * core * core * (3 - 2 * core)

# --- Choreography: one rigid transform per panel per frame.
def ease(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = np.clip(x, 0, 1)
    return 1 - (1 - x) ** 3


def ease_in(x):
    x = np.clip(x, 0, 1)
    return x ** 3


rng = np.random.default_rng(7)
n_p = 7
centroid = np.zeros((n_p, 3))
outward = np.zeros((n_p, 3))
for p in present:
    c = PV[panel == p].mean(0)
    centroid[p] = c
    if p in (2, 3, 4, 5):  # sleeves: out along their half's side, and away from the arm
        side = 1 if p in (2, 3) else -1
        o = np.array([0.55 * side, -1.0 if p in (2, 4) else 1.0, 0.25])
    elif p == 1:
        o = np.array([0.0, 1.0, 0.1])
    else:
        o = np.array([0.45 if p == 0 else -0.45, -1.0, 0.1])
    outward[p] = o / np.linalg.norm(o)

# Order in which panels arrive: back, fronts, then sleeves.
arrive_rank = {1: 0, 0: 1, 6: 2, 3: 3, 5: 3.4, 2: 4, 4: 4.4}
tracks = np.zeros((FRAMES, n_p, 7))  # quaternion xyzw + translation
for p in present:
    r = arrive_rank[p]
    start_off = np.array([1.5 + 0.12 * r, 0.25 + rng.normal(0, 0.08), 0.18 + rng.normal(0, 0.06)])
    route = np.array([0, 0.45 if outward[p][1] > 0 else -0.45, 0.12])
    spin0 = Rotation.from_euler("zxy", [rng.uniform(55, 80), rng.uniform(-18, 18), rng.uniform(-12, 12)], degrees=True)
    spin_out = Rotation.from_euler("zxy", [rng.uniform(-80, -55), rng.uniform(-18, 18), rng.uniform(-12, 12)], degrees=True)
    rot_path = Slerp([0, 1], Rotation.concatenate([spin0, Rotation.identity()]))
    rot_leave = Slerp([0, 1], Rotation.concatenate([Rotation.identity(), spin_out]))
    for f in range(FRAMES):
        t_arr = (f - 5 * r) / (60 - 5 * 4.4)
        t_close = (f - 60 - 4 * r) / (35 - 4 * 4.4)
        offset = outward[p] * D * (1 - ease(t_close))
        a = ease_out(t_arr)
        # Quadratic Bezier from the start (off to her right) to the waiting position, routed in
        # front of or behind her depending on the panel.
        p0, p2 = start_off, np.zeros(3)
        p1 = 0.5 * (p0 + p2) + route
        trans = (1 - a) ** 2 * p0 + 2 * (1 - a) * a * p1 + a * a * p2 + offset
        rot = rot_path(a)
        if LEAVES and f >= 130:
            t_open = (f - 130 - 3 * (4.4 - r)) / 25
            t_fly = (f - 150 - 3 * (4.4 - r)) / 35
            trans = outward[p] * D * ease(t_open)
            b = ease_in(t_fly)
            q0, q2 = trans, np.array([-1.7 - 0.12 * r, 0.25, 0.25])
            # Panels on her left (screen right) would cross her face going left: arc them over her head.
            over = np.array([0, -0.1, 2.3]) if centroid[p][0] > 0.05 else route
            q1 = 0.5 * (q0 + q2) + over
            trans = (1 - b) ** 2 * q0 + 2 * (1 - b) * b * q1 + b * b * q2
            rot = rot_leave(b)
        tracks[f, p, :4] = rot.as_quat()
        tracks[f, p, 4:] = trans

# Target positions per frame: rotate each panel about its own centroid, then translate.
def targets(f):
    out = np.empty_like(PV)
    for p in present:
        m = panel == p
        R = Rotation.from_quat(tracks[f, p, :4])
        out[m] = R.apply(PV[m] - centroid[p]) + centroid[p] + tracks[f, p, 4:]
    return out


pc2 = HERE / f"work/{name}.pc2"
with open(pc2, "wb") as fh:
    fh.write(struct.pack("<12siiffi", b"POINTCACHE2\0", 1, len(PV), 1.0, 1.0, FRAMES))
    for f in range(FRAMES):
        fh.write(targets(f).astype(np.float32).tobytes())

np.savez(HERE / f"work/{name}-panels.npz", v=PV, f=PF, panel=panel, source=source, seams=seams,
         pin=pin, tracks=tracks, centroid=centroid, frames=FRAMES)
print(f"seams {len(seams)}; pin weight mean {pin.mean():.2f}; wrote {pc2.name} ({FRAMES} frames)")
