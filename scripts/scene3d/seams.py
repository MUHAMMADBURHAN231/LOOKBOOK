"""Fuse seam pairs (one point of the garment split between two panels) as the panels close."""
import numpy as np


def zip_weight(frames: int, leaves: bool) -> np.ndarray:
    """How closed the seams are at each frame: zipping while the panels close (70-95), closed while
    the garment is on her, unzipping as it starts to leave (130-145)."""
    f = np.arange(frames, dtype=np.float64)

    def smooth(x):
        x = np.clip(x, 0, 1)
        return x * x * (3 - 2 * x)

    w = smooth((f - 70) / 25)
    if leaves:
        w = np.where(f > 130, 1 - smooth((f - 130) / 15), w)
    return w


def fuse_seams(frames: np.ndarray, seams: np.ndarray, near: float = 0.02, far: float = 0.08,
               closed: np.ndarray | None = None) -> np.ndarray:
    """Pull each seam pair to its midpoint: fully when the two sides are within `near`, fading out
    by `far`, and at least as much as `closed` (per frame) says the seam should be zipped."""
    out = frames.copy()
    a, b = seams[:, 0], seams[:, 1]
    pa, pb = frames[:, a], frames[:, b]
    d = np.linalg.norm(pa - pb, axis=2, keepdims=True)
    w = np.clip((far - d) / (far - near), 0, 1)
    if closed is not None:
        w = np.maximum(w, closed[:, None, None])
    mid = 0.5 * (pa + pb)
    out[:, a] = pa + (mid - pa) * w
    out[:, b] = pb + (mid - pb) * w
    return out
