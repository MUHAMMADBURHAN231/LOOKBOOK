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
import triangle

HERE = Path(__file__).resolve().parent
lm = json.loads((HERE / "work/landmarks.json").read_text())
name = sys.argv[1]

TOP = 1.4    # shoulder line at the neck (the robot's torso top is at 1.395)
H = 0.012    # mesh edge length

# Measured on the robot's collision envelope: chest about 1.1-1.15 m round, waist 0.65 m (z 1.0),
# pelvis 0.99 m (z 0.9); arm 0.53 m round just below the shoulder, 0.46 m at the forearm, 0.40 m at
# the wrist. The arm is thick, so sleeves are sized from it and the armhole follows from the sleeve.
# Hems are drafted about 8 cm long: the sleeves sit up in the robot's high armpit (z 1.21) and lift
# the whole garment by about that much.
STYLE = {
    # Half widths of each bodice piece (m, flat; front and back alike): chest at the armpit, waist,
    # hem; heights of the waist and hem; neckline; shoulder (arc from the centre) and its drop.
    # Sleeve: half widths at the top and the cuff, length (cap top to cuff) and cap height (low: the
    # robot's upper arm is raised about 49 degrees). Buttons: heights where an open front is tacked.
    "blouse": dict(chest=0.33, waist=0.305, waist_z=1.02, hem_w=0.32, hem=0.72, neck_w=0.105, neck_front=0.08,
                   neck_back=0.02, shoulder_drop=0.035, shoulder_w=0.175, sleeve_top=0.3, sleeve_bottom=0.25,
                   sleeve_len=0.56, cap_h=0.08, open_front=False, buttons=()),
    "blazer": dict(chest=0.335, waist=0.29, waist_z=1.02, hem_w=0.34, hem=0.74, neck_w=0.11, neck_front=0.3,
                   neck_back=0.02, shoulder_drop=0.03, shoulder_w=0.18, sleeve_top=0.295, sleeve_bottom=0.245,
                   sleeve_len=0.55, cap_h=0.085, open_front=True, buttons=(1.075,)),
    "coat": dict(chest=0.355, waist=0.325, waist_z=1.03, hem_w=0.44, hem=0.4, neck_w=0.115, neck_front=0.26,
                 neck_back=0.022, shoulder_drop=0.03, shoulder_w=0.185, sleeve_top=0.31, sleeve_bottom=0.26,
                 sleeve_len=0.58, cap_h=0.085, open_front=True, buttons=(1.1, 0.97)),
}
st = STYLE[name]
ARMHOLE_SCOOP = -0.05  # the armhole curves in: the robot's arm root is thick


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
    arm = curve(sp, ap, ARMHOLE_SCOOP, 16)
    # Side seam through the waist: a quadratic through the waist point.
    wp = np.array([st["waist"], st["waist_z"]])
    t = np.linspace(0, 1, 16)[:, None]
    ctrl = 2 * wp - 0.5 * (np.array(ap) + np.array(hp))
    side = (1 - t) ** 2 * np.array(ap) + 2 * (1 - t) * t * ctrl + t * t * np.array(hp)
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
    """Triangulate a 2D polygon with even, near-equilateral H-sized triangles (constrained
    Delaunay with a quality bound; the boundary keeps its H spacing)."""
    closed = np.vstack([poly, poly[:1]])
    seg = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    n = max(3, int(round(cum[-1] / H)))
    t = np.linspace(0, cum[-1], n, endpoint=False)
    bpts = np.column_stack([np.interp(t, cum, closed[:, 0]), np.interp(t, cum, closed[:, 1])])
    segs = np.column_stack([np.arange(n), (np.arange(n) + 1) % n])
    out = triangle.triangulate(dict(vertices=bpts, segments=segs), f"pq30Ya{0.433 * H * H * 1.5:.8f}")
    uv, f = out["vertices"], out["triangles"]
    return uv, f


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
    """Sleeve cap from underarm to underarm: an S-curve dome, cap_h tall, flat on top."""
    u = np.linspace(-top, top, 33)
    return np.column_stack([u, cap_h * 0.5 * (1 - np.cos(np.pi * u / top))])


def solve_armpit():
    """Armpit height so each armhole (front, back) is half the sleeve cap's edge less 1.5% ease."""
    target = polyline_length(cap_curve(st["sleeve_top"], st["cap_h"])) / 1.015 / 2
    sp = (st["shoulder_w"], TOP - st["shoulder_drop"])
    lo, hi = 0.8, sp[1] - 0.05
    for _ in range(50):
        mid = (lo + hi) / 2
        if polyline_length(curve(sp, (st["chest"], mid), ARMHOLE_SCOOP, 16)) > target:
            lo = mid
        else:
            hi = mid
    return lo


def add_sleeve(side: str):
    segs, _ = bodice(True, None)
    armhole = 2 * polyline_length(segs["armhole"])  # front + back armholes (same shape)
    top, bot, L = st["sleeve_top"], st["sleeve_bottom"], st["sleeve_len"]
    cap_h = st["cap_h"]
    if side == "l":
        print(f"sleeve {2 * top:.2f} m round at the top -> armhole {armhole:.3f} m, armpit at {st['armpit']:.3f} m")
    # u across (0 = outer top of the arm), v along the arm (0 = cap top, L = cuff).
    cap = cap_curve(top, cap_h)  # dome up to v=0
    right_edge = np.array([[top, cap_h], [bot, L]])
    cuff = np.array([[bot, L], [-bot, L]])
    left_edge = np.array([[-bot, L], [-top, cap_h]])
    poly = np.vstack([cap[:-1], right_edge[:-1], cuff[:-1], left_edge[:-1]])
    uv, f = mesh_polygon(poly)
    pieces.append(dict(name=f"sleeve_{side}", kind="sleeve", side=1 if side == "l" else -1, uv=uv, faces=f,
                       segs={"cap": cap, "under_a": right_edge, "under_b": left_edge, "cuff": cuff}))


st["armpit"] = solve_armpit()
add_bodice(True)
add_bodice(False)
add_sleeve("l")
add_sleeve("r")

# --- Arrange in 3D.
A, B_FRONT, B_BACK, YC = 0.235, 0.19, 0.18, 0.01
th = np.linspace(-np.pi, np.pi, 4001)
ex, ey = A * np.sin(th), -np.where(np.cos(th) > 0, B_FRONT, B_BACK) * np.cos(th)
arc = np.concatenate([[0], np.cumsum(np.hypot(np.diff(ex), np.diff(ey)))])
arc -= np.interp(0, th, arc)  # arc length measured from the centre front


def wrap_bodice(uv, front, lift=0.012):
    """u = arc length from centre front (front piece) or centre back (back piece)."""
    u = uv[:, 0]
    t = np.interp(u, arc, th)
    if not front:
        # From the centre back (theta = pi); u > 0 still goes to her left (x > 0).
        t = np.pi - t
    x = A * np.sin(t)
    y = -np.where(np.cos(t) > 0, B_FRONT, B_BACK) * np.cos(t) + YC
    return np.column_stack([x, y, uv[:, 1] + lift])


SLIDE = 0.05


def arm_curve(side):
    """Smooth centreline of the (bent) arm: from above the shoulder, through the elbow, past the
    wrist; as dense points, their arc length from the shoulder, and parallel-transported frames
    (tangent, outer side, front)."""
    S, E, W = (np.array(lm[f"{k}_{side}"]) for k in ("shoulder", "elbow", "wrist"))
    up = (E - S) / np.linalg.norm(E - S)
    fore = (W - E) / np.linalg.norm(W - E)
    p0, p2 = S - 0.16 * up, W + 0.3 * fore
    ctrl = 2 * E - 0.5 * (p0 + p2)          # quadratic through the elbow at its midpoint
    t = np.linspace(0, 1, 400)[:, None]
    c = (1 - t) ** 2 * p0 + 2 * (1 - t) * t * ctrl + t * t * p2
    arc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(c, axis=0), axis=1))])
    arc -= arc[np.argmin(np.linalg.norm(c - S, axis=1))]
    tan = np.gradient(c, axis=0)
    tan /= np.linalg.norm(tan, axis=1)[:, None]
    out = np.array([1.0 if side == "l" else -1.0, 0, 0])
    e1 = [out - tan[0] * (out @ tan[0])]
    for k in range(1, len(c)):
        v = e1[-1] - tan[k] * (e1[-1] @ tan[k])
        e1.append(v / np.linalg.norm(v))
    e1 = np.array(e1)
    e2 = np.cross(tan, e1)
    if e2[len(c) // 2, 1] > 0:
        e2 = -e2                            # e2 points to the front (-y)
    return c, arc, e1, e2


def wrap_sleeve(uv, s):
    """Around the arm's centreline: u across (0 on the outer side, the underarm seam underneath),
    v along. The sleeve starts SLIDE lower than where it ends up, clear of the shoulder, with its
    open underarm seam below the arm; sewing slides it up into the armhole (as in Marvelous
    Designer)."""
    c, arc, e1, e2 = arm_curve("l" if s > 0 else "r")
    along = uv[:, 1] - 0.13 + SLIDE
    # Wider near the shoulder, to clear the robot's shoulder cap.
    r = 0.11 + 0.035 * np.clip((0.1 - along) / 0.12, 0, 1)
    phi = uv[:, 0] / r * s
    pos = np.column_stack([np.interp(along, arc, c[:, k]) for k in range(3)])
    f1 = np.column_stack([np.interp(along, arc, e1[:, k]) for k in range(3)])
    f2 = np.column_stack([np.interp(along, arc, e2[:, k]) for k in range(3)])
    return pos + r[:, None] * (np.cos(phi)[:, None] * f1 + np.sin(phi)[:, None] * f2)


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
UV = np.vstack([pc["uv"] for pc in pieces])  # the flat pattern: the cloth's rest shape

# Clear the body: anything inside or within 1.5 cm of the envelope is pushed out along the nearest
# surface normal. The push is smoothed over each flat piece (Gaussian in pattern space) so the
# arrangement stays smooth, and applied in small rounds until everything is clear.
import trimesh  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402

_e = np.load(HERE / "work/envelope.npz")
_env = trimesh.Trimesh(_e["v"], _e["f"], process=False)
_edges = trimesh.Trimesh(V, F, process=False).edges_unique
_smooth = []
for pid in range(len(pieces)):
    idx = np.nonzero(P == pid)[0]
    tree = cKDTree(UV[idx])
    nb = tree.query_ball_point(UV[idx], r=0.09)
    rows = np.repeat(np.arange(len(idx)), [len(n) for n in nb])
    cols = np.concatenate(nb)
    w = np.exp(-np.sum((UV[idx][rows] - UV[idx][cols]) ** 2, axis=1) / (2 * 0.03 ** 2))
    _smooth.append((idx, rows, cols, w))


def signed_distance(x):
    """Distance to the envelope, negative inside (sign from the nearest face's normal)."""
    cp, _, tri = _env.nearest.on_surface(x)
    nrm = _env.face_normals[tri]
    return np.einsum("ij,ij->i", x - cp, nrm), nrm


print(f"before clearing: {int((signed_distance(V)[0] < 0).sum())} vertices inside the robot")
for _round in range(40):
    sd, nrm = signed_distance(V)
    need = sd < 0.015
    if not need.any():
        break
    want = np.where(need[:, None], nrm * (0.02 - sd)[:, None], 0.0)
    disp = np.zeros_like(V)
    for idx, rows, cols, w in _smooth:
        acc = np.zeros((len(idx), 3))
        np.add.at(acc, rows, want[idx][cols] * w[:, None])
        wsum = np.zeros(len(idx))
        np.add.at(wsum, rows, w * need[idx][cols])
        # Weighted mean of the pushes nearby (only over vertices that need one), faded by how much
        # of the neighbourhood needs it, so the push falls off smoothly around the region.
        full = np.zeros(len(idx))
        np.add.at(full, rows, w)
        disp[idx] = acc / np.maximum(wsum, 1e-9)[:, None] * np.clip(wsum / full * 3, 0, 1)[:, None]
    V = V + 0.5 * disp
cp, _, tri = _env.nearest.on_surface(V)
sd = np.einsum("ij,ij->i", V - cp, _env.face_normals[tri])
_e2 = np.linalg.norm(UV[_edges[:, 0]] - UV[_edges[:, 1]], axis=1)
_e3 = np.linalg.norm(V[_edges[:, 0]] - V[_edges[:, 1]], axis=1) / _e2
print(f"arrangement: {int((sd < 0).sum())} vertices inside, {int((sd < 0.01).sum())} within 1 cm; "
      f"edge length vs pattern {_e3.min():.2f}..{_e3.max():.2f}")


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
    f = pc["faces"]
    e = np.sort(np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
    ue, cnt = np.unique(e, axis=0, return_counts=True)
    boundary = np.zeros(len(uv), bool)
    boundary[ue[cnt == 1].ravel()] = True
    idx = np.nonzero((best_d < tol) & boundary)[0]
    return idx[np.argsort(best_t[idx])] + pc["offset"], np.sort(best_t[idx])


def sew(pa, sa, pb, sb, reverse=False):
    ia, ta = edge_vertices(pa, sa)
    ib, tb = edge_vertices(pb, sb)
    if reverse:
        tb = 1 - tb
    pairs = []
    # Both ways, so no point on either edge is left unsewn (it would fold into a flap).
    for i, t in zip(ia, ta, strict=True):
        pairs.append((i, ib[np.argmin(np.abs(tb - t))]))
    for j, t in zip(ib, tb, strict=True):
        pairs.append((ia[np.argmin(np.abs(ta - t))], j))
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
# Buttons: tack the two front edges together at each button height.
if st["open_front"]:
    fl, fr = by["front_l"], by["front_r"]
    for z in st["buttons"]:
        il, _ = edge_vertices(fl, fl["segs"]["front"])
        ir, _ = edge_vertices(fr, fr["segs"]["front"])
        zl = fl["uv"][il - fl["offset"], 1]
        zr = fr["uv"][ir - fr["offset"], 1]
        for i in il[np.abs(zl - z) < 0.012]:
            j = ir[np.argmin(np.abs(zr - fl["uv"][i - fl["offset"], 1]))]
            pairs.append((i, j))
pairs = np.unique(np.sort(np.array(pairs), axis=1), axis=0)
pairs = pairs[pairs[:, 0] != pairs[:, 1]]
np.savez(HERE / f"work/{name}-pattern.npz", v=V, uv=UV, f=F, panel=P, sew=pairs,
         names=np.array([pc["name"] for pc in pieces]))
gaps = np.linalg.norm(V[pairs[:, 0]] - V[pairs[:, 1]], axis=1)
print(f"{name}: {len(pieces)} pieces, {len(V)} vertices, {len(F)} triangles, {len(pairs)} sewing pairs "
      f"(gap mean {gaps.mean() * 100:.0f} cm, max {gaps.max() * 100:.0f} cm)")
