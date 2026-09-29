"""Cut a garment out of a generated look and fit it to the base body as a single-layer cloth mesh.

    python extract.py blouse|blazer|coat
"""
from __future__ import annotations

import colorsys
import json
import sys

import numpy as np
import pymeshlab
import trimesh
from scipy.spatial import cKDTree

from common import HERE, canonical, export_gltf, landmarks, load_raw

GARMENTS = {
    # hue range (0..1), min saturation, value range, height range (m)
    "blouse": {"hue": (0.52, 0.70), "sat": 0.10, "val": (0.35, 1.0), "z": (0.80, 1.45)},
    "blazer": {"hue": (0.0, 1.0), "sat": 0.0, "val": (0.0, 0.26), "z": (0.72, 1.42)},
    "coat": {"hue": (0.03, 0.12), "sat": 0.38, "val": (0.20, 0.85), "z": (0.28, 1.45)},
}

name = sys.argv[1]
spec = GARMENTS[name]
EDGE = 0.015 if name == "coat" else 0.012  # cloth edge length (m); the coat is big
lm = json.loads((HERE / "work/landmarks.json").read_text())
body, _ = canonical(load_raw(HERE / "gen/body-meshy.glb"), lm["ref"])
raw = load_raw(HERE / f"gen/look-{name}.glb")
look, _ = canonical(raw)

# Colours before any geometry edits (sampled from the texture at each vertex).
colors = look.visual.to_color().vertex_colors[:, :3].astype(np.float32) / 255

# Weld vertices split along texture seams (same position, different UV), so the surface is one
# connected piece for the steps below. Colours are averaged per welded vertex.
key = np.round(look.vertices / 1e-6).astype(np.int64)
_, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
inv = inv.ravel()
welded_colors = np.zeros((len(first), 3), np.float32)
np.add.at(welded_colors, inv, colors)
welded_colors /= np.bincount(inv, minlength=len(first))[:, None]
look = trimesh.Trimesh(look.vertices[first], inv[look.faces], process=False)
colors = welded_colors
print(f"welded: {len(inv)} -> {len(first)} vertices")

# Align the look to the body using parts the garment doesn't cover: head and lower legs.
keep = (look.vertices[:, 2] > 1.47) | (look.vertices[:, 2] < 0.45)
matrix, _, cost = trimesh.registration.icp(look.vertices[keep][::3], body, max_iterations=60, scale=True)
look.apply_transform(matrix)
print(f"aligned: icp cost {cost * 1000:.1f} mm")

# The look's arms hang at a slightly different angle from the body's, which puts the sleeves partly
# inside the body's forearms. Rotate each sleeve about the shoulder so the look's arm axis matches
# the body's, blending from the shoulder (no change) to the elbow (full rotation).
from scipy.spatial.transform import Rotation as _R  # noqa: E402

look_lm = landmarks(look)
V = look.vertices.copy()
for side in ("l", "r"):
    S_b, d_b = np.array(lm[f"shoulder_{side}"]), np.array(lm[f"arm_dir_{side}"])
    S_l, d_l = np.array(look_lm[f"shoulder_{side}"]), np.array(look_lm[f"arm_dir_{side}"])
    axis = np.cross(d_l, d_b)
    angle = np.arcsin(np.clip(np.linalg.norm(axis), -1, 1))
    rot = _R.from_rotvec(axis / max(np.linalg.norm(axis), 1e-9) * angle)
    sign = 1 if side == "l" else -1
    # Pivot at the body's shoulder: the look is already aligned as a whole, and its own shoulder
    # estimate is unreliable (a jacket joins the arm to the torso lower down).
    rel = V - S_b
    along = rel @ d_l
    radial = np.linalg.norm(rel - np.outer(along, d_l), axis=1)
    on_arm = (sign * V[:, 0] > 0.12) & (radial < 0.16) & (along > -0.05)
    w = np.clip(along / 0.2, 0, 1)
    w = w * w * (3 - 2 * w) * on_arm
    moved = rot.apply(rel) + S_b
    V = V + (moved - V) * w[:, None]
    print(f"arm {side}: rotated {np.degrees(angle):.1f} deg")
look.vertices = V

# Classify vertices by colour and height.
hsv = np.array([colorsys.rgb_to_hsv(*c) for c in colors])
h, s, v = hsv.T
z = look.vertices[:, 2]
lo, hi = spec["hue"]
mask = (h >= lo) & (h <= hi) & (s >= spec["sat"]) & (v >= spec["val"][0]) & (v <= spec["val"][1])
mask &= (z >= spec["z"][0]) & (z <= spec["z"][1])
# Hands are never garment: beyond the wrist along each arm.
for side in ("l", "r"):
    w = np.array(lm[f"wrist_{side}"])
    d = np.array(lm[f"arm_dir_{side}"])
    rel = look.vertices - w
    along = rel @ d
    radial = np.linalg.norm(rel - np.outer(along, d), axis=1)
    mask &= ~((along > 0.015) & (radial < 0.07))
print(f"garment vertices: {mask.sum()} of {len(mask)}")

# Colour tests are noisy (highlights on black cloth, shadows in folds), so smooth the mask over the
# surface: diffuse it along edges and threshold. Fills gaps and drops specks up to ~2 cm, and
# straightens ragged edges.
e = look.edges_unique
deg = np.bincount(e.ravel(), minlength=len(mask)).astype(np.float32)
m = mask.astype(np.float32)
for _ in range(40):
    acc = np.bincount(e[:, 0], weights=m[e[:, 1]], minlength=len(m)) + np.bincount(e[:, 1], weights=m[e[:, 0]], minlength=len(m))
    m = 0.5 * m + 0.5 * acc / np.maximum(deg, 1)
mask = m > 0.5
print(f"after smoothing: {mask.sum()}")

# Faces with at least two garment vertices, then close small holes and drop specks on the face graph.
faces = look.faces
sel = mask[faces].sum(1) >= 2
adj = trimesh.graph.face_adjacency(mesh=look)


def grow(s, n):
    for _ in range(n):
        hit = s[adj[:, 0]] | s[adj[:, 1]]
        s = s.copy()
        s[adj[hit, 0]] = True
        s[adj[hit, 1]] = True
    return s


def shrink(s, n):
    for _ in range(n):
        miss = ~(s[adj[:, 0]] & s[adj[:, 1]])
        s = s.copy()
        s[adj[miss, 0]] = False
        s[adj[miss, 1]] = False
    return s


sel = shrink(grow(sel, 4), 4)
# Plain geometry (no texture): splitting a textured mesh copies the texture into every piece.
sub = trimesh.Trimesh(look.vertices, look.faces[sel], process=False)
sub.remove_unreferenced_vertices()
parts = sub.split(only_watertight=False)
big = max(len(p.faces) for p in parts)
sub = trimesh.util.concatenate([p for p in parts if len(p.faces) > 0.03 * big])
print(f"garment faces: {len(sub.faces)} in {len([p for p in parts if len(p.faces) > 0.03 * big])} pieces")

# Remesh to an even cloth mesh (about 12 mm edges), boundaries kept.
ms = pymeshlab.MeshSet()
ms.add_mesh(pymeshlab.Mesh(sub.vertices, sub.faces))
ms.meshing_remove_duplicate_vertices()
ms.meshing_repair_non_manifold_edges()
ms.meshing_isotropic_explicit_remeshing(targetlen=pymeshlab.PureValue(EDGE), iterations=8, featuredeg=180)
ms.meshing_repair_non_manifold_edges()
ms.meshing_repair_non_manifold_vertices()
ms.meshing_close_holes(maxholesize=12, newfaceselected=False)
ms.meshing_isotropic_explicit_remeshing(targetlen=pymeshlab.PureValue(EDGE), iterations=3, featuredeg=180)
m = ms.current_mesh()
cloth = trimesh.Trimesh(m.vertex_matrix(), m.face_matrix(), process=True)
cloth = max(cloth.split(only_watertight=False), key=lambda p: len(p.faces))


# Fill holes left where the look's texture was in shadow (under the arms, around gathers), but keep
# the garment's real openings: loops that wrap around the torso or an arm, and large outlines
# (the front opening of a jacket). Where a cuff has two loops (a gap before the cuff band), trim the
# band off at the gap.
def winding(points, centre, axis):
    u = np.cross(axis, [1, 0, 0] if abs(axis[0]) < 0.9 else [0, 1, 0])
    u /= np.linalg.norm(u)
    w = np.cross(axis, u)
    rel = points - centre
    ang = np.unwrap(np.arctan2(rel @ w, rel @ u))
    return abs(ang[-1] - ang[0] + np.angle(np.exp(1j * (ang[0] - ang[-1])))) / (2 * np.pi)


def ordered_loops(mesh):
    out = mesh.outline()
    return [np.asarray(e.points)[:-1] if e.closed else np.asarray(e.points) for e in out.entities]


torso_axis = np.array([0, 0, 1.0])
# No garment belongs inside the neck's radius above the collarbone; stray strips there (hairline
# colour noise) split the neck opening in two.
tc = cloth.triangles_center
neck = (tc[:, 2] > 1.34) & (np.linalg.norm(tc[:, :2] - np.array([0, 0.01]), axis=1) < 0.068)
cloth = max(cloth.submesh([np.nonzero(~neck)[0]], append=True).split(only_watertight=False), key=lambda p: len(p.faces))
print(f"carved {int(neck.sum())} faces at the neck")
arms = {s: (np.array(lm[f"shoulder_{s}"]), np.array(lm[f"arm_dir_{s}"])) for s in ("l", "r")}
fill, cuff_loops = [], {"l": [], "r": []}
for loop in ordered_loops(cloth):
    P = cloth.vertices[loop]
    c = P.mean(0)
    side = None
    for sd, (S0, d) in arms.items():
        a = (c - S0) @ d
        if a > 0.3 and np.linalg.norm((c - S0) - d * a) < 0.12:
            side = sd  # forearm zone: a cuff, or a gap or fragment near it
    around = winding(P, np.array([0, 0.01, c[2]]), torso_axis) > 0.8  # hem or neckline
    if side:
        cuff_loops[side].append((float((c - arms[side][0]) @ arms[side][1]), loop))
    elif not around and len(loop) < 150:
        fill.append(loop)
    print(f"loop {len(loop):4d} at {np.round(c, 2)}: " + (f"cuff {side}" if side else "opening" if around or len(loop) >= 150 else "fill"))
trim = np.zeros(len(cloth.faces), bool)
for s, loops in cuff_loops.items():
    if len(loops) > 1:
        S0, d = arms[s]
        cut = min(a for a, _ in loops)
        along_f = (cloth.triangles_center - S0) @ d
        radial_f = np.linalg.norm((cloth.triangles_center - S0) - np.outer(along_f, d), axis=1)
        trim |= (along_f > cut - 0.004) & (radial_f < 0.12)
        print(f"cuff {s}: {len(loops)} loops, trimmed the band past {cut:.3f} m")
new_v = [cloth.vertices]
new_f = [cloth.faces[~trim]]
n_v = len(cloth.vertices)
for loop in fill:
    new_v.append(cloth.vertices[loop].mean(0, keepdims=True))
    k = len(loop)
    new_f.append(np.column_stack([np.full(k, n_v), loop[np.arange(1, k + 1) % k], loop]))
    n_v += 1
filled = trimesh.Trimesh(np.vstack(new_v), np.vstack(new_f), process=True)
trimesh.repair.fix_winding(filled)
filled = max(filled.split(only_watertight=False), key=lambda p: len(p.faces))
ms = pymeshlab.MeshSet()
ms.add_mesh(pymeshlab.Mesh(filled.vertices, filled.faces))
ms.meshing_repair_non_manifold_edges()
ms.meshing_isotropic_explicit_remeshing(targetlen=pymeshlab.PureValue(EDGE), iterations=4, featuredeg=180)
m = ms.current_mesh()
cloth = trimesh.Trimesh(m.vertex_matrix(), m.face_matrix(), process=True)
print(f"filled {len(fill)} holes")

# Smooth the garment's edges (hems, cuffs, collar, front opening) along themselves: the colour mask
# leaves them ragged.
be = cloth.edges[trimesh.grouping.group_rows(cloth.edges_sorted, require_count=1)]
bv = np.unique(be)
vv = cloth.vertices.copy()
for _ in range(25):
    acc = np.zeros_like(vv)
    cnt = np.zeros(len(vv))
    np.add.at(acc, be[:, 0], vv[be[:, 1]])
    np.add.at(acc, be[:, 1], vv[be[:, 0]])
    np.add.at(cnt, be[:, 0], 1)
    np.add.at(cnt, be[:, 1], 1)
    vv[bv] = 0.5 * vv[bv] + 0.5 * acc[bv] / np.maximum(cnt[bv], 1)[:, None]
# Relax the rows next to the edge a little so the smoothed edge doesn't pinch.
e_all = cloth.edges_unique
near = np.zeros(len(vv), bool)
near[e_all[np.isin(e_all, bv).any(1)].ravel()] = True
near[bv] = False
for _ in range(4):
    acc = np.zeros_like(vv)
    cnt = np.zeros(len(vv))
    np.add.at(acc, e_all[:, 0], vv[e_all[:, 1]])
    np.add.at(acc, e_all[:, 1], vv[e_all[:, 0]])
    np.add.at(cnt, e_all[:, 0], 1)
    np.add.at(cnt, e_all[:, 1], 1)
    vv[near] = 0.5 * vv[near] + 0.5 * acc[near] / np.maximum(cnt[near], 1)[:, None]
cloth.vertices = vv

# Remove small bumps from the generated surface (they read as blotches under a satin sheen) while
# keeping folds: a few rounds of Taubin smoothing on interior vertices.
interior = np.ones(len(cloth.vertices), bool)
interior[np.unique(cloth.edges[trimesh.grouping.group_rows(cloth.edges_sorted, require_count=1)])] = False
e_all = cloth.edges_unique
vv = cloth.vertices.copy()
for _ in range(6):
    for lam in (0.5, -0.53):
        acc = np.zeros_like(vv)
        cnt = np.zeros(len(vv))
        np.add.at(acc, e_all[:, 0], vv[e_all[:, 1]])
        np.add.at(acc, e_all[:, 1], vv[e_all[:, 0]])
        np.add.at(cnt, e_all[:, 0], 1)
        np.add.at(cnt, e_all[:, 1], 1)
        delta = acc / np.maximum(cnt, 1)[:, None] - vv
        vv[interior] += lam * delta[interior]
cloth.vertices = vv

# Colour from the original look.
src_idx = np.nonzero(mask)[0]
tree = cKDTree(look.vertices[src_idx])
_, nn = tree.query(cloth.vertices, k=6)
col = colors[src_idx][nn].mean(1)

# Keep the cloth outside the body: at least 6 mm off the surface, smoothed.
closest, dist, tri = body.nearest.on_surface(cloth.vertices)
normals = body.face_normals[tri]
signed = np.einsum("ij,ij->i", cloth.vertices - closest, normals)
push = np.clip(0.010 - signed, 0, None)
disp = normals * push[:, None]
edges = cloth.edges_unique
for _ in range(10):
    acc = np.zeros_like(disp)
    cnt = np.zeros(len(disp))
    np.add.at(acc, edges[:, 0], disp[edges[:, 1]])
    np.add.at(acc, edges[:, 1], disp[edges[:, 0]])
    np.add.at(cnt, edges[:, 0], 1)
    np.add.at(cnt, edges[:, 1], 1)
    disp = 0.5 * disp + 0.5 * acc / np.maximum(cnt, 1)[:, None]
cloth.vertices = cloth.vertices + disp
closest, dist, tri = body.nearest.on_surface(cloth.vertices)
signed = np.einsum("ij,ij->i", cloth.vertices - closest, body.face_normals[tri])
inside = signed < 0.007
cloth.vertices[inside] += body.face_normals[tri][inside] * (0.010 - signed[inside])[:, None]
# One consistent face orientation, facing away from her. The generated source mixes windings, which
# shows as dark patches once normals are averaged across the flipped regions.
# Orient coherently across the surface (after clearing non-manifold spots), then pick the overall
# direction by an area-weighted vote against the body's normals, counting only faces that clearly
# face towards or away from her.
ms = pymeshlab.MeshSet()
ms.add_mesh(pymeshlab.Mesh(cloth.vertices, cloth.faces))
ms.meshing_repair_non_manifold_edges(method=0)
ms.meshing_repair_non_manifold_vertices()
ms.meshing_re_orient_faces_coherently()
m = ms.current_mesh()
cloth = trimesh.Trimesh(m.vertex_matrix(), m.face_matrix(), process=False)
cp, _, tri = body.nearest.on_surface(cloth.triangles_center)
dots = np.einsum("ij,ij->i", cloth.face_normals, body.face_normals[tri])
vote = np.sum(np.sign(dots) * (np.abs(dots) > 0.5) * cloth.area_faces)
if vote < 0:
    cloth.invert()
    dots = -dots
print(f"winding consistent: {cloth.is_winding_consistent}; clearly outward {(dots > 0.5).sum()} vs inward {(dots < -0.5).sum()}")
print(f"cloth: {len(cloth.vertices)} vertices, {len(cloth.faces)} faces; pushed out {int((push > 0).sum())}; "
      f"boundary loops {len(trimesh.graph.connected_components(cloth.edges[trimesh.grouping.group_rows(cloth.edges_sorted, require_count=1)]))}")

np.savez(HERE / f"work/{name}-cloth.npz", v=cloth.vertices, f=cloth.faces, c=col)
cloth.visual = trimesh.visual.ColorVisuals(cloth, vertex_colors=(np.clip(col, 0, 1) * 255).astype(np.uint8))
export_gltf(cloth, HERE / f"work/{name}-cloth.glb")
if not (HERE / "work/body.glb").exists():
    export_gltf(body, HERE / "work/body.glb")
