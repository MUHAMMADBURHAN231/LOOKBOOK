"""Garments as sewing patterns, arranged around the robot (the way Marvelous Designer / CLO do).

    python patterns.py blouse|blazer|coat

Each garment is a set of flat 2D pattern pieces (bodice fronts and back, two sleeves), meshed,
then wrapped around the robot at a little distance: bodices on elliptical cylinders around the
torso, sleeves on open cylinders around each arm with the underarm seam facing the body. Sewing
lines pair points along matching edges (side seams, shoulders, sleeve underarms, sleeve caps to
armholes, and the centre back/front where a piece is split). sew_sim.py sews and drapes them.

Writes work/<name>-pattern.npz: vertices (arranged), faces, panel id, sewing pairs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pymeshlab
from matplotlib.path import Path as MPath
from scipy.spatial import Delaunay

HERE = Path(__file__).resolve().parent
lm = json.loads((HERE / "work/landmarks.json").read_text())
name = sys.argv[1]

TOP = 1.405  # shoulder line at the neck
H = 0.012    # mesh edge length

STYLE = {
    # half widths (m, flat): chest, hem; hem height; neckline; shoulder; sleeve half widths at the
    # cap and cuff, sleeve length and cap height
    "blouse": dict(chest=0.35, hem_w=0.37, hem=0.74, neck_w=0.085, neck_front=0.07, neck_back=0.02,
                   shoulder_drop=0.05, shoulder_w=0.22, armpit=1.12, sleeve_top=0.0, sleeve_bottom=0.30,
                   sleeve_len=0.59, cap_h=0.06, open_front=False),
    "blazer": dict(chest=0.34, hem_w=0.35, hem=0.76, neck_w=0.09, neck_front=0.26, neck_back=0.02,
                   shoulder_drop=0.04, shoulder_w=0.23, armpit=1.12, sleeve_top=0.0, sleeve_bottom=0.25,
                   sleeve_len=0.58, cap_h=0.06, open_front=True),
    "coat": dict(chest=0.37, hem_w=0.47, hem=0.38, neck_w=0.095, neck_front=0.22, neck_back=0.025,
                 shoulder_drop=0.04, shoulder_w=0.24, armpit=1.11, sleeve_top=0.0, sleeve_bottom=0.27,
                 sleeve_len=0.61, cap_h=0.06, open_front=True),
}
st = STYLE[name]


def curve(p0, p1, bulge, n=12):
    """Points from p0 to p1 bowed sideways by `bulge` (quadratic)."""
    p0, p1 = np.array(p0, float), np.array(p1, float)
    t = np.linspace(0, 1, n)[:, None]
    m = (p0 + p1) / 2
    d = p1 - p0
    nrm = np.array([-d[1], d[0]]) / (np.linalg.norm(d) + 1e-9)
    c = m + nrm * bulge
    return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * c + t * t * p1


def bodice(front: bool, half: str | None):
    """Outline (u across from centre, v height) of a bodice piece, as named segments.
    half: None for a whole piece, 'l'/'r' for one side of a piece split at the centre."""
    nw, sw = st["neck_w"], st["shoulder_w"]
    top = TOP
    nd = st["neck_front"] if front else st["neck_back"]
    sp = (sw, top - st["shoulder_drop"])          # shoulder point
    ap = (st["chest"], st["armpit"])              # armpit
    hp = (st["hem_w"], st["hem"])                 # hem corner
    segs = {}
    # Right-hand side (u > 0), counter-clockwise from the centre of the neckline.
    if front and st["open_front"]:
        # Lapel line: straight V from the shoulder-neck point down to the button point.
        neck = np.array([[0.012, top - nd], [nw, top]])
    else:
        neck = curve((0, top - nd), (nw, top), -0.25 * nd, 10)
    shoulder = np.array([[nw, top], sp])
    arm = curve(sp, ap, -0.035, 12)
    side = np.array([ap, hp])
    hem = np.array([hp, [0 if not (front and st["open_front"]) else 0.012, st["hem"]]])
    segs["neck"] = neck
    segs["shoulder"] = shoulder
    segs["armhole"] = arm
    segs["side"] = side
    segs["hem"] = hem
    if front and st["open_front"]:
        segs["front"] = np.array([[0.012, st["hem"]], [0.012, top - nd]])
    right = [segs["neck"], segs["shoulder"], segs["armhole"], segs["side"], segs["hem"]] + (
        [segs["front"]] if "front" in segs else [])
    return segs, right


def mesh_polygon(poly):
    """Triangulate a 2D polygon with roughly even H-sized triangles."""
    path = MPath(poly)
    lo, hi = poly.min(0), poly.max(0)
    xs = np.arange(lo[0], hi[0] + H, H)
    ys = np.arange(lo[1], hi[1] + H, H * 0.866)
    grid = np.array([[x + (0.5 * H if j % 2 else 0), y] for j, y in enumerate(ys) for x in xs])
    inside = grid[path.contains_points(grid, radius=-H * 0.4)]
    # Resample the boundary at H spacing.
    closed = np.vstack([poly, poly[:1]])
    seg = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    t = np.arange(0, cum[-1], H)
    bpts = np.column_stack([np.interp(t, cum, closed[:, 0]), np.interp(t, cum, closed[:, 1])])
    pts = np.vstack([bpts, inside])
    tri = Delaunay(pts).simplices
    cen = pts[tri].mean(1)
    tri = tri[path.contains_points(cen)]
    ms = pymeshlab.MeshSet()
    ms.add_mesh(pymeshlab.Mesh(np.column_stack([pts, np.zeros(len(pts))]), tri))
    ms.meshing_remove_unreferenced_vertices()
    ms.meshing_isotropic_explicit_remeshing(targetlen=pymeshlab.PureValue(H), iterations=5, featuredeg=180,
                                            checksurfdist=False)
    m = ms.current_mesh()
    return m.vertex_matrix()[:, :2], m.face_matrix()


pieces = []  # dicts: name, uv, faces, segs (name -> polyline in uv)


def add_bodice(front: bool):
    segs, right = bodice(front, None)
    if front and st["open_front"]:
        # Two fronts, each from the centre line out.
        for side in ("l", "r"):
            s = 1 if side == "l" else -1
            poly = np.vstack([p[:-1] for p in right])
            poly = poly * np.array([s, 1]) if side == "l" else (poly * np.array([-1, 1]))[::-1]
            uv, f = mesh_polygon(poly)
            pieces.append(dict(name=f"front_{side}", kind="front", side=s, uv=uv, faces=f,
                               segs={k: v * np.array([s, 1]) for k, v in segs.items()}))
        return
    # Whole piece: mirror the right half.
    rpoly = np.vstack([p[:-1] for p in right])
    lpoly = (rpoly * np.array([-1, 1]))[::-1]
    poly = np.vstack([rpoly, lpoly])
    uv, f = mesh_polygon(poly)
    seg_all = {}
    for k, v in segs.items():
        seg_all[k + "_l"] = v
        seg_all[k + "_r"] = v * np.array([-1, 1])
    pieces.append(dict(name="front" if front else "back", kind="front" if front else "back", side=0,
                       uv=uv, faces=f, segs=seg_all))


def polyline_length(p):
    return float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum())


def cap_curve(top, cap_h):
    c = curve((-top, cap_h), (top, cap_h), -cap_h * 1.6, 24)
    c[:, 1] = np.clip(c[:, 1], 0, None)
    return c


def sleeve_top_for(armhole_len):
    """Half width of the sleeve at the cap so the cap edge matches the armhole plus 4% ease."""
    lo, hi = 0.05, 0.5
    for _ in range(40):
        mid = (lo + hi) / 2
        if polyline_length(cap_curve(mid, st["cap_h"])) < armhole_len * 1.04:
            lo = mid
        else:
            hi = mid
    return lo


def add_sleeve(side: str):
    segs, _ = bodice(True, None)
    armhole = 2 * polyline_length(segs["armhole"])  # front + back armholes (same shape)
    top, bot, L = sleeve_top_for(armhole), st["sleeve_bottom"], st["sleeve_len"]
    cap_h = st["cap_h"]
    if side == "l":
        print(f"armhole {armhole:.3f} m -> sleeve cap half width {top:.3f} m")
    # u across (0 = outer top of the arm), v along the arm (0 = cap top, L = cuff).
    cap = cap_curve(top, cap_h)  # dome up to v=0
    right_edge = np.array([[top, cap_h], [bot, L]])
    cuff = np.array([[bot, L], [-bot, L]])
    left_edge = np.array([[-bot, L], [-top, cap_h]])
    poly = np.vstack([cap[:-1], right_edge[:-1], cuff[:-1], left_edge[:-1]])
    uv, f = mesh_polygon(poly)
    pieces.append(dict(name=f"sleeve_{side}", kind="sleeve", side=1 if side == "l" else -1, uv=uv, faces=f,
                       segs={"cap": cap, "under_a": right_edge, "under_b": left_edge, "cuff": cuff}))


add_bodice(True)
add_bodice(False)
add_sleeve("l")
add_sleeve("r")

# --- Arrange in 3D.
A, B_FRONT, B_BACK, YC = 0.245, 0.22, 0.2, 0.01
th = np.linspace(-np.pi, np.pi, 4001)
ex, ey = A * np.sin(th), -np.where(np.cos(th) > 0, B_FRONT, B_BACK) * np.cos(th)
arc = np.concatenate([[0], np.cumsum(np.hypot(np.diff(ex), np.diff(ey)))])
arc -= np.interp(0, th, arc)  # arc length measured from the centre front


def wrap_bodice(uv, front, lift=0.03):
    """u = arc length from centre front (front piece) or centre back (back piece)."""
    u = uv[:, 0]
    t = np.interp(u, arc, th)
    if not front:
        # From the centre back (theta = pi); u > 0 still goes to her left (x > 0).
        t = np.pi - t
    x = A * np.sin(t)
    y = -np.where(np.cos(t) > 0, B_FRONT, B_BACK) * np.cos(t) + YC
    return np.column_stack([x, y, uv[:, 1] + lift])


def wrap_sleeve(uv, s):
    S = np.array(lm[f"shoulder_{'l' if s > 0 else 'r'}"])
    d = np.array(lm[f"arm_dir_{'l' if s > 0 else 'r'}"])
    out = np.array([s, 0.0, 0.0])
    e1 = out - d * (out @ d)
    e1 /= np.linalg.norm(e1)             # outer side of the arm
    e2 = np.cross(d, e1)                 # forward/back
    if e2[1] > 0:
        e2 = -e2                          # e2 points to the front (-y)
    r = 0.125
    phi = uv[:, 0] / r * s               # 0 on the outer side; +-pi underneath (towards the body)
    along = uv[:, 1] - 0.11
    return S + np.outer(along, d) + r * (np.outer(np.cos(phi), e1) + np.outer(np.sin(phi), e2))


V, F, P = [], [], []
seg3d = {}
offset = 0
for pid, pc in enumerate(pieces):
    if pc["kind"] == "front":
        xyz = wrap_bodice(pc["uv"], True)
    elif pc["kind"] == "back":
        xyz = wrap_bodice(pc["uv"], False)
    else:
        xyz = wrap_sleeve(pc["uv"], pc["side"])
    pc["xyz"] = xyz
    pc["offset"] = offset
    V.append(xyz)
    F.append(pc["faces"] + offset)
    P.append(np.full(len(xyz), pid))
    offset += len(xyz)
V, F, P = np.vstack(V), np.vstack(F), np.concatenate(P)

# Clear the body: push anything inside or within 3 cm of the envelope outward, spreading the push
# smoothly over each piece so the pieces stay smooth; repeat until clear.
import trimesh  # noqa: E402

_e = np.load(HERE / "work/envelope.npz")
_env = trimesh.Trimesh(_e["v"], _e["f"], process=False)
_edges = trimesh.Trimesh(V, F, process=False).edges_unique
for _round in range(6):
    cp, _, tri = _env.nearest.on_surface(V)
    sd = np.einsum("ij,ij->i", V - cp, _env.face_normals[tri])
    need = sd < 0.03
    if not need.any():
        break
    disp = np.where(need[:, None], _env.face_normals[tri] * (0.035 - sd)[:, None], 0.0)
    for _ in range(25):
        acc = np.zeros_like(disp)
        cnt = np.zeros(len(disp))
        np.add.at(acc, _edges[:, 0], disp[_edges[:, 1]])
        np.add.at(acc, _edges[:, 1], disp[_edges[:, 0]])
        np.add.at(cnt, _edges[:, 0], 1)
        np.add.at(cnt, _edges[:, 1], 1)
        avg = acc / np.maximum(cnt, 1)[:, None]
        # Spread the push without shrinking it: keep whichever is larger, own or neighbours'.
        own_bigger = np.linalg.norm(disp, axis=1) >= np.linalg.norm(avg, axis=1)
        disp = np.where(own_bigger[:, None], disp, avg)
    V = V + disp
cp, _, tri = _env.nearest.on_surface(V)
sd = np.einsum("ij,ij->i", V - cp, _env.face_normals[tri])
print(f"arrangement: {int((sd < 0).sum())} vertices inside, {int((sd < 0.02).sum())} within 2 cm")


def edge_vertices(pc, polyline, tol=H * 0.45):
    """Boundary vertices of a piece lying on a polyline, ordered along it."""
    uv = pc["uv"]
    seg = np.diff(polyline, axis=0)
    best_d = np.full(len(uv), np.inf)
    best_t = np.zeros(len(uv))
    cum = np.concatenate([[0], np.cumsum(np.linalg.norm(seg, axis=1))])
    for i, sv in enumerate(seg):
        L2 = sv @ sv
        t = np.clip(((uv - polyline[i]) @ sv) / max(L2, 1e-12), 0, 1)
        proj = polyline[i] + np.outer(t, sv)
        dd = np.linalg.norm(uv - proj, axis=1)
        better = dd < best_d
        best_d[better] = dd[better]
        best_t[better] = (cum[i] + t * np.sqrt(L2))[better] / max(cum[-1], 1e-12)
    idx = np.nonzero(best_d < tol)[0]
    return idx[np.argsort(best_t[idx])] + pc["offset"], np.sort(best_t[idx])


def sew(pa, sa, pb, sb, reverse=False):
    ia, ta = edge_vertices(pa, sa)
    ib, tb = edge_vertices(pb, sb)
    if reverse:
        tb = 1 - tb
    pairs = []
    short, long_, ts, tl, flip = (ia, ib, ta, tb, False) if len(ia) <= len(ib) else (ib, ia, tb, ta, True)
    for i, t in zip(short, ts, strict=True):
        j = long_[np.argmin(np.abs(tl - t))]
        pairs.append((j, i) if flip else (i, j))
    return pairs


by = {pc["name"]: pc for pc in pieces}
pairs = []
back = by["back"]
fronts = [by["front_l"], by["front_r"]] if st["open_front"] else [by["front"], by["front"]]
for s, side in ((1, "l"), (-1, "r")):
    f = fronts[0] if side == "l" else fronts[1]
    # u > 0 is her left (x > 0) on every bodice piece; whole pieces carry both halves.
    fs = (lambda k: f["segs"][k]) if st["open_front"] else (lambda k: f["segs"][f"{k}_{side}"])  # noqa: E731
    bs = lambda k: back["segs"][f"{k}_{side}"]  # noqa: E731
    pairs += sew(f, fs("side"), back, bs("side"))
    pairs += sew(f, fs("shoulder"), back, bs("shoulder"))
    sl = by[f"sleeve_{side}"]
    pairs += sew(sl, sl["segs"]["under_a"], sl, sl["segs"]["under_b"], reverse=True)
    # Sleeve cap: front half to the front armhole, back half to the back armhole.
    # Both halves run from the top of the cap to the underarm, like the armholes (shoulder point to
    # armpit). On her left arm u > 0 faces front; on the right, u < 0 does.
    cap = sl["segs"]["cap"]
    mid = len(cap) // 2
    upper, lower = cap[mid:], cap[mid::-1]
    cap_front, cap_back = (upper, lower) if s > 0 else (lower, upper)
    pairs += sew(sl, cap_front, f, fs("armhole"))
    pairs += sew(sl, cap_back, back, bs("armhole"))
pairs = np.unique(np.sort(np.array(pairs), axis=1), axis=0)
pairs = pairs[pairs[:, 0] != pairs[:, 1]]
np.savez(HERE / f"work/{name}-pattern.npz", v=V, f=F, panel=P, sew=pairs,
         names=np.array([pc["name"] for pc in pieces]))
gaps = np.linalg.norm(V[pairs[:, 0]] - V[pairs[:, 1]], axis=1)
print(f"{name}: {len(pieces)} pieces, {len(V)} vertices, {len(F)} triangles, {len(pairs)} sewing pairs "
      f"(gap mean {gaps.mean() * 100:.0f} cm, max {gaps.max() * 100:.0f} cm)")
