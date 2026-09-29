"""Choreograph the sewn garments and pack them for the page (same format as the woman scene).

    python export_sew.py <out dir>

Timeline (30 fps): 0-60 the flat pieces fly in from the right, fluttering, to where they're
arranged around the robot; 60-130 they sew together and drape (the simulation, time-warped so the
sewing gets half of it); for the blouse and
blazer, 130-155 the garment un-sews (the simulation backwards) and 155-190 the pieces fly off to
the left (pieces on her left arc over her head). Each piece's best-fit rigid motion is stored every
frame; the cloth's own deformation on top, every other frame as int8 per piece.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial.transform import Rotation, Slerp

HERE = Path(__file__).resolve().parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "web"
OUT.mkdir(parents=True, exist_ok=True)
STRIDE = 2
M = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], dtype=np.float64)  # canonical (Z up) -> three (Y up)
FLY, SEW, UNSEW, AWAY = 60, 70, 25, 35


def ease(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def warp(t):
    """Simulation time for scroll time t (0..1): the sewing (the first third of the simulation)
    gets the first half of the scroll, the settling the rest."""
    return np.clip(t, 0, 1) ** 1.6


def kabsch(a, b):
    """Rigid transform (R, t) that best maps points a onto b."""
    ca, cb = a.mean(0), b.mean(0)
    h = (a - ca).T @ (b - cb)
    u, _, vt = np.linalg.svd(h)
    dd = np.sign(np.linalg.det(vt.T @ u.T))
    r = vt.T @ np.diag([1, 1, dd]) @ u.T
    return r, cb - r @ ca


def sample(sim, s):
    """Simulation frame s (fractional), interpolated."""
    s = np.clip(s, 0, len(sim) - 1)
    i = int(np.floor(s))
    j = min(i + 1, len(sim) - 1)
    a = s - i
    return sim[i] * (1 - a) + sim[j] * a


def align(buf: bytearray):
    buf.extend(b"\0" * (-len(buf) % 4))


manifest = {"body": "/look/3d/body.glb", "stride": STRIDE, "garments": {}}
rng = np.random.default_rng(11)
for name in ("blouse", "blazer", "coat"):
    d = np.load(HERE / f"work/{name}-pattern.npz")
    sim = np.load(HERE / f"work/{name}-sew.npy").astype(np.float64)
    F, panel, sew = d["f"], d["panel"], d["sew"]
    rest = sim[0]
    leaves = name != "coat"
    frames = FLY + SEW + (UNSEW + AWAY if leaves else 0)
    P = int(panel.max()) + 1
    centre = np.array([rest[panel == p].mean(0) for p in range(P)])

    # Per-piece flight: from the right to the arrangement, and (leaving) to the left.
    flight = []
    for p in range(P):
        c = centre[p]
        rank = p
        front = c[1] < 0.02
        route = np.array([0, -0.45 if front else 0.45, 0.12])
        start = np.array([1.5 + 0.14 * rank, 0.2 + rng.normal(0, 0.06), 0.15 + rng.normal(0, 0.05)])
        over = np.array([0, -0.1, 2.3]) if c[0] > 0.05 else route
        end = np.array([-1.8 - 0.14 * rank, 0.25, 0.25])
        spin_in = Rotation.from_euler("zxy", [rng.uniform(55, 80), rng.uniform(-15, 15), rng.uniform(-10, 10)], degrees=True)
        spin_out = Rotation.from_euler("zxy", [rng.uniform(-80, -55), rng.uniform(-15, 15), rng.uniform(-10, 10)], degrees=True)
        axis = np.linalg.svd(rest[panel == p] - c)[2][0]  # the piece's long direction, for the flutter wave
        flight.append(dict(start=start, route=route, over=over, end=end, spin_in=spin_in, spin_out=spin_out,
                           axis=axis, delay=0.06 * rank))

    pos = np.zeros((frames, len(rest), 3))
    tracks = np.zeros((frames, P, 7))
    for f in range(frames):
        if f < FLY or f >= FLY + SEW + UNSEW:
            arriving = f < FLY
            x = rest.copy()
            for p in range(P):
                fl = flight[p]
                m = panel == p
                if arriving:
                    a = ease((f / (FLY - 1) - fl["delay"]) / (1 - 0.3)) ** 0.8
                    p0, p2 = fl["start"], np.zeros(3)
                    p1 = 0.5 * (p0 + p2) + fl["route"]
                    tr = (1 - a) ** 2 * p0 + 2 * (1 - a) * a * p1 + a * a * p2
                    rot = Slerp([0, 1], Rotation.concatenate([fl["spin_in"], Rotation.identity()]))(a)
                    amp = 0.03 * (1 - a) ** 1.5
                    ph = f * 0.35
                else:
                    b = ease((f - FLY - SEW - UNSEW) / (AWAY - 1) - fl["delay"]) ** 1.2
                    q0, q2 = np.zeros(3), fl["end"]
                    q1 = 0.5 * (q0 + q2) + fl["over"]
                    tr = (1 - b) ** 2 * q0 + 2 * (1 - b) * b * q1 + b * b * q2
                    rot = Slerp([0, 1], Rotation.concatenate([Rotation.identity(), fl["spin_out"]]))(b)
                    amp = 0.03 * b ** 1.2
                    ph = f * 0.35
                local = rest[m] - centre[p]
                along = local @ fl["axis"]
                # Flutter: a travelling wave across the piece, out of its surface.
                nrm = np.cross(fl["axis"], [0, 0, 1.0])
                nrm = nrm / (np.linalg.norm(nrm) + 1e-9)
                wave = amp * np.sin(along * 14 + ph)[:, None] * nrm
                x[m] = rot.apply(local + wave) + centre[p] + tr
            pos[f] = x
        elif f < FLY + SEW:
            pos[f] = sample(sim, warp((f - FLY) / (SEW - 1)) * (len(sim) - 1))
        else:
            pos[f] = sample(sim, warp(1 - (f - FLY - SEW) / (UNSEW - 1)) * (len(sim) - 1))
        # Best-fit rigid motion per piece (rest -> this frame), so the residual is only cloth.
        for p in range(P):
            m = panel == p
            r, t = kabsch(rest[m] - centre[p], pos[f][m] - centre[p])
            tracks[f, p, :4] = Rotation.from_matrix(r).as_quat()
            tracks[f, p, 4:] = t

    # Seams: fully closed while the garment is on (the simulation closes them to ~2 mm).
    fo = np.arange(frames)
    zipw = ease((fo - (FLY + 12)) / 30)
    if leaves:
        zipw = np.where(fo >= FLY + SEW, 1 - ease((fo - FLY - SEW) / 8), zipw)
    # Each seam vertex moves toward the mean of itself and its partners (a vertex can be sewn to
    # several); a few rounds close the seam without sliding along it.
    a, b = sew[:, 0], sew[:, 1]
    cnt = np.zeros(len(rest))
    np.add.at(cnt, a, 1)
    np.add.at(cnt, b, 1)
    seam = cnt > 0
    for _ in range(4):
        acc = np.zeros_like(pos)
        np.add.at(acc, (slice(None), a), pos[:, b])
        np.add.at(acc, (slice(None), b), pos[:, a])
        target = 0.5 * (pos[:, seam] + acc[:, seam] / cnt[seam][None, :, None])
        pos[:, seam] += (target - pos[:, seam]) * zipw[:, None, None]

    def target(f):
        out = np.empty_like(rest)
        for p in range(P):
            m = panel == p
            out[m] = Rotation.from_quat(tracks[f, p, :4]).apply(rest[m] - centre[p]) + centre[p] + tracks[f, p, 4:]
        return out

    stored = list(range(0, frames, STRIDE))
    if stored[-1] != frames - 1:
        stored.append(frames - 1)
    resid = np.stack([(pos[f] - target(f)) @ M.T for f in stored])
    scales = np.zeros((len(stored), P), np.float32)
    q = np.zeros(resid.shape, np.int8)
    for k in range(len(stored)):
        for p in range(P):
            m = panel == p
            s = np.abs(resid[k, m]).max() / 127
            scales[k, p] = s
            if s > 0:
                q[k, m] = np.clip(np.round(resid[k, m] / s), -127, 127).astype(np.int8)
    track3 = np.zeros_like(tracks, dtype=np.float32)
    for f in range(frames):
        for p in range(P):
            R = Rotation.from_quat(tracks[f, p, :4]).as_matrix()
            track3[f, p, :4] = Rotation.from_matrix(M @ R @ M.T).as_quat()
            track3[f, p, 4:] = M @ tracks[f, p, 4:]
    big = len(rest) > 65535
    it = np.uint32 if big else np.uint16
    buf = bytearray()
    sections = {}
    for key, arr in (("index", F.ravel().astype(it)), ("rest", (rest @ M.T).astype(np.float32).ravel()),
                     ("panel", panel.astype(np.uint8)), ("seams", sew.ravel().astype(it)),
                     ("centre", (centre @ M.T).astype(np.float32).ravel()), ("track", track3.ravel()),
                     ("scale", scales.ravel()), ("resid", q.ravel())):
        align(buf)
        sections[key] = [len(buf), int(arr.size)]
        buf.extend(arr.tobytes())
    packed = gzip.compress(bytes(buf), 9, mtime=0)
    (OUT / f"{name}.bin.gz").write_bytes(packed)
    manifest["garments"][name] = {
        "url": f"/look/3d/{name}.bin.gz", "vertices": int(len(rest)), "frames": int(frames), "panels": P,
        "stored": stored, "index32": bool(big), "sections": sections, "bytes": len(buf),
    }
    err = np.abs(q.astype(np.float32) * scales[:, panel][..., None] - resid).max()
    print(f"{name}: {len(rest)} verts, {P} pieces, {frames} frames, {len(buf) / 1e6:.2f} MB "
          f"({len(packed) / 1e6:.2f} MB gzip), max error {err * 1000:.2f} mm, "
          f"largest cloth offset {np.abs(resid).max() * 100:.0f} cm")
manifest["timeline"] = {"settled": FLY + SEW - 1, "leaveStart": FLY + SEW, "leaveEnd": FLY + SEW + UNSEW + AWAY - 1}
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
print("timeline", manifest["timeline"])
