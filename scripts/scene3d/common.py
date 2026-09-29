"""Shared helpers: load Meshy GLBs into one canonical frame and measure body landmarks.

Canonical frame (Blender's): metres, Z up, facing -Y, feet on z=0, torso centred on x=y=0.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
HEIGHT = 1.68


def load_raw(path: str | Path) -> trimesh.Trimesh:
    scene = trimesh.load(path, force="scene")
    mesh = scene.to_geometry() if hasattr(scene, "to_geometry") else scene.dump(concatenate=True)
    # glTF is Y-up facing +Z; convert to Z-up facing -Y.
    v = mesh.vertices.copy()
    mesh.vertices = np.column_stack([v[:, 0], -v[:, 2], v[:, 1]])
    return mesh


def canonical(mesh: trimesh.Trimesh, ref: dict | None = None) -> tuple[trimesh.Trimesh, dict]:
    """Scale to HEIGHT and move feet to z=0, torso to x=y=0. With ref, reuse its transform."""
    if ref is None:
        v = mesh.vertices
        scale = HEIGHT / (v[:, 2].max() - v[:, 2].min())
        zmin = v[:, 2].min()
        # Torso centre from a slice at 60% height (chest, arms usually joined but centred).
        band = v[(v[:, 2] - zmin) * scale > 0.55 * HEIGHT]
        band = band[(band[:, 2] - zmin) * scale < 0.65 * HEIGHT]
        cx = np.median(band[:, 0])
        cy = (band[:, 1].min() + band[:, 1].max()) / 2
        ref = {"scale": float(scale), "offset": [float(-cx), float(-cy), float(-zmin)]}
    m = mesh.copy()
    m.vertices = (m.vertices + np.array(ref["offset"])) * ref["scale"]
    return m, ref


def components_at(mesh: trimesh.Trimesh, z: float):
    """Cross-section at height z as a list of (centroid_xy, bbox) per closed loop."""
    sec = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if sec is None:
        return []
    path, _ = sec.to_2D(to_2D=np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, -z], [0, 0, 0, 1]], dtype=float))
    out = []
    for poly in path.polygons_full:
        if poly.area < 1e-5:
            continue
        c = poly.centroid
        out.append({"c": (c.x, c.y), "area": poly.area, "bounds": poly.bounds})
    return out


def landmarks(body: trimesh.Trimesh) -> dict:
    zs = np.linspace(0.3, 1.5, 241)
    arms = {"l": [], "r": []}
    armpit = None
    crotch = None
    for z in zs:
        comps = components_at(body, z)
        if not comps:
            continue
        torso = max(comps, key=lambda c: c["area"])
        tx0, _, tx1, _ = torso["bounds"]
        side = [c for c in comps if c is not torso and c["area"] > 3e-4]
        left = [c for c in side if c["c"][0] > tx1 - 0.01]
        right = [c for c in side if c["c"][0] < tx0 + 0.01]
        if z > 0.6:
            if left:
                arms["l"].append((z, *max(left, key=lambda c: c["area"])["c"]))
            if right:
                arms["r"].append((z, *max(right, key=lambda c: c["area"])["c"]))
            if left and right:
                armpit = z
        if z < 1.0 and len([c for c in comps if c["area"] > 3e-3]) >= 2 and crotch is None:
            pass
    # Arm axis: line fit through arm centroids from 25 cm below the armpit to the armpit.
    result = {"armpit_z": float(armpit)}
    for s in ("l", "r"):
        pts = np.array([p for p in arms[s] if armpit - 0.25 <= p[0] <= armpit], dtype=float)
        pts3 = pts[:, [1, 2, 0]]  # x, y, z
        c = pts3.mean(0)
        _, _, vt = np.linalg.svd(pts3 - c)
        d = vt[0] if vt[0][2] < 0 else -vt[0]  # pointing down the arm
        # Shoulder joint: on the axis, 6 cm above the armpit.
        t_sh = (armpit + 0.06 - c[2]) / d[2]
        low = min(p[0] for p in arms[s])
        t_wr = (low + 0.19 - c[2]) / d[2]  # wrist ~19 cm above the fingertips
        result[f"shoulder_{s}"] = (c + d * t_sh).tolist()
        result[f"wrist_{s}"] = (c + d * t_wr).tolist()
        result[f"arm_dir_{s}"] = d.tolist()
        result[f"fingertip_z_{s}"] = float(low)
    v = body.vertices
    result["neck_z"] = float(HEIGHT * 0.83)
    result["height"] = float(v[:, 2].max())
    return result


if __name__ == "__main__":
    body, ref = canonical(load_raw(HERE / "gen/body-meshy.glb"))
    lm = landmarks(body)
    lm["ref"] = ref
    (HERE / "work").mkdir(exist_ok=True)
    (HERE / "work/landmarks.json").write_text(json.dumps(lm, indent=2))
    print(json.dumps(lm, indent=1))
    print("bounds", body.bounds.round(3).tolist(), "faces", len(body.faces))


def export_gltf(mesh: trimesh.Trimesh, path: str | Path) -> None:
    """Write a canonical (Z-up, facing -Y) mesh as glTF (Y-up, facing +Z)."""
    m = mesh.copy()
    v = m.vertices
    m.vertices = np.column_stack([v[:, 0], v[:, 2], -v[:, 1]])
    m.export(path)
