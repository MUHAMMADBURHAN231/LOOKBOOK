"""Pack simulated garments for the web: one binary per garment plus a manifest.

Each vertex position is its panel's rigid transform (stored every frame, tiny) plus the cloth's own
motion on top (the residual: flutter, lag, drape), stored every STRIDE frames as int8 with one scale
per panel per stored frame. Seam pairs are fused before packing. Everything is converted to three.js
axes (Y up, facing +Z).

Binary layout (little endian, each section 4-byte aligned), described in the manifest:
  index   uint16|uint32 [indexCount]
  rest    float32 [V*3]      fitted shape
  panel   uint8   [V]        panel id per vertex
  seams   uint16|uint32 [S*2] vertex pairs that are one point of the garment
  centre  float32 [P*3]      panel pivots
  track   float32 [frames*P*7] quaternion xyzw + translation per panel per frame
  scale   float32 [stored*P] residual scale per panel per stored frame (metres per unit)
  resid   int8    [stored*V*3]
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial.transform import Rotation

from common import HERE
from seams import fuse_seams, zip_weight

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "web"
OUT.mkdir(parents=True, exist_ok=True)
STRIDE = 2
M = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], dtype=np.float64)  # canonical (Z up) -> three (Y up)


def align(buf: bytearray):
    buf.extend(b"\0" * (-len(buf) % 4))


manifest = {"body": "/look/3d/body.glb", "stride": STRIDE, "garments": {}}
for name in ("blouse", "blazer", "coat"):
    d = np.load(HERE / f"work/{name}-panels.npz")
    V, F, panel, seams = d["v"], d["f"], d["panel"], d["seams"]
    tracks, centre = d["tracks"], d["centroid"]
    frames, P = tracks.shape[0], tracks.shape[1]
    zipped = zip_weight(frames, leaves=name != "coat")
    sim = np.load(HERE / f"work/{name}-sim.npy").astype(np.float64)

    def target(f, V=V, panel=panel, tracks=tracks, centre=centre, P=P):
        """Rigid target at frame f (canonical axes), to take the residual against."""
        out = np.empty_like(V)
        for p in range(P):
            m = panel == p
            if m.any():
                out[m] = Rotation.from_quat(tracks[f, p, :4]).apply(V[m] - centre[p]) + centre[p] + tracks[f, p, 4:]
        return out

    # Clean the cloth motion before packing:
    # - straighten seam edges while panels are apart (they're cut along triangle edges, so they
    #   zig-zag); once a seam closes the two sides are fused and nothing changes;
    # - smooth the residual over neighbours, which removes single-vertex spikes at fluttering edges
    #   and keeps the waves.
    mesh = trimesh.Trimesh(V, F, process=False)
    e = mesh.edges_unique
    be = mesh.edges[trimesh.grouping.group_rows(mesh.edges_sorted, require_count=1)]
    seam_v = np.zeros(len(V), bool)
    seam_v[seams.ravel()] = True
    be = be[seam_v[be[:, 0]] & seam_v[be[:, 1]]]
    partner = np.full(len(V), -1)
    partner[seams[:, 0]] = seams[:, 1]
    partner[seams[:, 1]] = seams[:, 0]

    def neighbour_mean(x, edges):
        acc = np.zeros_like(x)
        cnt = np.zeros(len(x))
        np.add.at(acc, edges[:, 0], x[edges[:, 1]])
        np.add.at(acc, edges[:, 1], x[edges[:, 0]])
        np.add.at(cnt, edges[:, 0], 1)
        np.add.at(cnt, edges[:, 1], 1)
        return acc / np.maximum(cnt, 1)[:, None], cnt > 0

    # On her, the garment is exactly its fitted shape: the simulation's own motion fades out as it
    # settles (95-115) and back in as it starts to leave (130-145). Flight and closing keep all of it;
    # on the body it would only add collision snags (an arm poking through where friction held cloth).
    fo = np.arange(frames, dtype=np.float64)
    fade = 1 - np.clip((fo - 95) / 20, 0, 1)
    if name != "coat":
        fade = np.maximum(fade, np.clip((fo - 130) / 15, 0, 1))
    fade = fade * fade * (3 - 2 * fade)
    for f in range(frames):
        tf = target(f)
        r = (sim[f] - tf) * fade[f]
        for _ in range(6):
            m, _has = neighbour_mean(r, e)
            r = 0.5 * r + 0.5 * m
        x = tf + r
        sv = np.nonzero(seam_v)[0]
        gap = np.linalg.norm(x[sv] - x[partner[sv]], axis=1)
        w = np.zeros(len(V))
        w[sv] = np.clip((gap - 0.02) / 0.06, 0, 1)  # 0 when fused, 1 when well apart
        for _ in range(4):
            m, has = neighbour_mean(x, be)
            k = has & (w > 0)
            x[k] += (m[k] - x[k]) * 0.5 * w[k, None]
        sim[f] = x
    sim = fuse_seams(sim, seams, closed=zipped)

    stored = list(range(0, frames, STRIDE))
    if stored[-1] != frames - 1:
        stored.append(frames - 1)
    resid = np.stack([(sim[f] - target(f)) @ M.T for f in stored])  # three axes
    scales = np.zeros((len(stored), P), np.float32)
    q = np.zeros(resid.shape, np.int8)
    for k in range(len(stored)):
        for p in range(P):
            m = panel == p
            if not m.any():
                continue
            s = np.abs(resid[k, m]).max() / 127 if m.any() else 0
            scales[k, p] = s
            if s > 0:
                q[k, m] = np.clip(np.round(resid[k, m] / s), -127, 127).astype(np.int8)

    rest3 = V @ M.T
    centre3 = centre @ M.T
    track3 = np.zeros_like(tracks, dtype=np.float32)
    for f in range(frames):
        for p in range(P):
            R = Rotation.from_quat(tracks[f, p, :4]).as_matrix()
            track3[f, p, :4] = Rotation.from_matrix(M @ R @ M.T).as_quat()
            track3[f, p, 4:] = M @ tracks[f, p, 4:]

    big = len(V) > 65535
    it = np.uint32 if big else np.uint16
    buf = bytearray()
    sections = {}
    for key, arr in (("index", F.ravel().astype(it)), ("rest", rest3.astype(np.float32).ravel()),
                     ("panel", panel.astype(np.uint8)), ("seams", seams.ravel().astype(it)),
                     ("centre", centre3.astype(np.float32).ravel()), ("track", track3.ravel()),
                     ("scale", scales.ravel()), ("resid", q.ravel())):
        align(buf)
        sections[key] = [len(buf), int(arr.size)]
        buf.extend(arr.tobytes())
    # Shipped gzipped (the page decompresses it), so hosts that don't compress binaries still send 1/3.
    packed = gzip.compress(bytes(buf), 9, mtime=0)
    (OUT / f"{name}.bin.gz").write_bytes(packed)
    gz = len(packed)
    manifest["garments"][name] = {
        "url": f"/look/3d/{name}.bin.gz", "vertices": int(len(V)), "frames": int(frames), "panels": int(P),
        "stored": stored, "index32": bool(big), "sections": sections, "bytes": len(buf),
    }
    err = np.abs(q.astype(np.float32) * scales[:, panel][..., None] - resid).max()
    print(f"{name}: {len(V)} verts, {frames} frames ({len(stored)} stored), {len(buf) / 1e6:.2f} MB "
          f"({gz / 1e6:.2f} MB gzip), max quantisation error {err * 1000:.2f} mm")

# Choreography marks (frames): arrive 0-130 (settled at 130), leave 130-190.
manifest["timeline"] = {"settled": 129, "leaveStart": 130, "leaveEnd": 189}
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
