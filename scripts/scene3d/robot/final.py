"""Last simulated frame of a garment as work/<name>-final.npz (for view_parts.py --extra)."""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
COLORS = {"blouse": (0.62, 0.70, 0.82), "blazer": (0.07, 0.07, 0.075), "coat": (0.62, 0.42, 0.25)}
for name in sys.argv[1:]:
    d = np.load(HERE / f"work/{name}-pattern.npz")
    sim = np.load(HERE / f"work/{name}-sew.npy")
    np.savez(HERE / f"work/{name}-final.npz", v=sim[-1], f=d["f"], color=np.array(COLORS[name]))
