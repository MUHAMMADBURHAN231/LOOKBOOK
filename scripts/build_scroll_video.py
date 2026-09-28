"""Turn the landing-page video clips into scroll-scrubbed frames.

    pip install pillow imageio-ffmpeg
    python scripts/build_scroll_video.py clip1.mp4 clip2.mp4 clip3.mp4

Each clip is one transition (for example base look to blouse). Clips are joined in order into one
continuous sequence. One clip ends on the same look the next begins with, but generated frames
never match exactly, so the last few frames of one clip are cross-blended with the first few of
the next (both are nearly still there) and the join doesn't pop. Frames are resized, written as WebP to
frontend/public/look/frames/, and described in manifest.json, which the home page reads to switch
from the 3D fallback to the video.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import imageio_ffmpeg
    from PIL import Image
except ImportError:
    sys.exit("Requirements: pip install pillow imageio-ffmpeg")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "frontend" / "public" / "look" / "frames"


def extract(clip: Path, fps: int, width: int, tmp: Path) -> list[Path]:
    tmp.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [ffmpeg, "-loglevel", "error", "-i", str(clip), "-vf", f"fps={fps},scale={width}:-2:flags=lanczos",
         str(tmp / "%05d.png")],
        check=True,
    )
    return sorted(tmp.glob("*.png"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clips", nargs="+", type=Path)
    ap.add_argument("--fps", type=int, default=24, help="frames kept per second of video (default 24)")
    ap.add_argument("--width", type=int, default=720, help="frame width in pixels (default 720)")
    ap.add_argument("--quality", type=int, default=74, help="WebP quality (default 74)")
    ap.add_argument("--blend", type=int, default=6, help="frames cross-blended at each join (default 6)")
    args = ap.parse_args()

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    work = OUT / "_work"

    sequence: list[Image.Image] = []
    for k, clip in enumerate(args.clips):
        frames = [Image.open(f).convert("RGB") for f in extract(clip, args.fps, args.width, work / str(k))]
        if sequence and frames:
            b = min(args.blend, len(frames), len(sequence))
            size = sequence[-1].size
            for i in range(b):
                head = frames[i] if frames[i].size == size else frames[i].resize(size, Image.LANCZOS)
                t = (i + 1) / (b + 1)
                sequence[-b + i] = Image.blend(sequence[-b + i], head, t)
            frames = frames[b:]
        sequence.extend(frames)
        print(f"{clip.name}: {len(frames)} frames")
    shutil.rmtree(work)

    for n, im in enumerate(sequence, start=1):
        im.save(OUT / f"f-{n:04d}.webp", "WEBP", quality=args.quality, method=6)
    n = len(sequence)
    size = sequence[-1].size if sequence else (0, 0)

    manifest = {"pattern": "/look/frames/f-{i}.webp", "count": n, "pad": 4, "width": size[0], "height": size[1]}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    total = sum(p.stat().st_size for p in OUT.glob("*.webp"))
    print(f"{n} frames, {size[0]}x{size[1]}, {total / 1e6:.1f} MB -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
