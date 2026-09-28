"""Turn the landing-page video clips into scroll-scrubbed frames.

    pip install pillow numpy imageio-ffmpeg
    python scripts/build_scroll_video.py clip1.mp4 clip2.mp4 clip3.mp4

Each clip is one transition (for example base look to blouse), and they are joined in order into
one continuous sequence. Four steps make the result feel like one smooth camera move rather than a
flip-book:

1. Motion interpolation. Each clip is interpolated to several times its frame rate with ffmpeg's
   motion-compensated minterpolate, so fast movement (a coat swinging on) gets real in-between
   frames instead of a double-exposure cross-fade.
2. Joins. One clip ends on the same look the next begins with, but generated frames never match
   exactly, so the frames around each join are cross-blended (both are nearly still there).
3. Re-timing. Generated clips move unevenly: a garment settling barely changes the picture while a
   coat being thrown on changes it a lot, so a steady scroll would crawl and then lurch. The output
   frames are picked at equal steps of on-screen change (with a small floor so still moments keep
   some scroll), so a steady scroll gives steady motion. The page adds easing and pauses on top.
4. Backdrop. The studio backdrop is lifted to pure white (a per-channel gain measured from the frame
   borders), so the page can blend the video with mix-blend-mode: multiply.

Frames are written as WebP in one folder per width under frontend/public/look/frames/ (the page
picks a width for the screen) and described in manifest.json, which also records where each look
is complete ("marks", 0..1) so the page can pause there.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

try:
    import imageio_ffmpeg
    import numpy as np
    from PIL import Image
except ImportError:
    sys.exit("Requirements: pip install pillow numpy imageio-ffmpeg")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "frontend" / "public" / "look" / "frames"
THUMB = (120, 213)

# A dense frame is a file, or a cross-blend of two files at weight t: (a, b, t).
Recipe = tuple[Path, Path | None, float]


def extract(clip: Path, fps: int, factor: int, width: int, tmp: Path) -> list[Path]:
    """Crop to 9:16, scale, and motion-interpolate to fps * factor. High-quality JPEG keeps the
    intermediate files small."""
    tmp.mkdir(parents=True, exist_ok=True)
    filters = [
        "crop='min(iw,ih*9/16)':'min(ih,iw*16/9)'",
        f"scale={width}:-2:flags=lanczos",
        f"fps={fps}",
    ]
    if factor > 1:
        filters.append(f"minterpolate=fps={fps * factor}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1")
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-i", str(clip), "-vf", ",".join(filters),
         "-q:v", "2", str(tmp / "%05d.jpg")],
        check=True,
    )
    return sorted(tmp.glob("*.jpg"))


def render(recipe: Recipe) -> Image.Image:
    a, b, t = recipe
    im = Image.open(a).convert("RGB")
    if b is None or t <= 0:
        return im
    other = Image.open(b).convert("RGB")
    if other.size != im.size:
        other = other.resize(im.size, Image.LANCZOS)
    return Image.blend(im, other, t)


def thumb(recipe: Recipe) -> np.ndarray:
    return np.asarray(render(recipe).convert("L").resize(THUMB, Image.BILINEAR), dtype=np.float32)


def backdrop_gains(frames: list[Image.Image]) -> list[float]:
    """Per-channel gain that maps the median border colour to white."""
    samples: list[tuple[int, int, int]] = []
    for im in frames:
        w, h = im.size
        step = max(1, min(w, h) // 40)
        for x in range(0, w, step):
            samples += [im.getpixel((x, 4)), im.getpixel((x, h - 5))]
        for y in range(0, h, step):
            samples += [im.getpixel((4, y)), im.getpixel((w - 5, y))]
    # Ignore dark samples (a garment crossing the edge).
    light = [s for s in samples if sum(s) > 600] or samples
    medians = [sorted(s[c] for s in light)[len(light) // 2] for c in range(3)]
    return [255 / max(1, m) for m in medians]


def write_proxies(frames: list[Path], out: Path, width: int = 144, cols: int = 10, rows: int = 10) -> dict:
    """Pack every frame, small, into a few sprite sheets. They load first, so the page can draw any
    point of the timeline at once (softly) while the full frames stream in and decode."""
    out.mkdir(parents=True, exist_ok=True)
    first = Image.open(frames[0])
    height = round(first.height * width / first.width)
    per = cols * rows
    sheets = (len(frames) + per - 1) // per
    for s in range(sheets):
        chunk = frames[s * per:(s + 1) * per]
        sheet = Image.new("RGB", (width * cols, height * ((len(chunk) + cols - 1) // cols)), "white")
        for k, f in enumerate(chunk):
            sheet.paste(Image.open(f).convert("RGB").resize((width, height), Image.LANCZOS),
                        ((k % cols) * width, (k // cols) * height))
        sheet.save(out / f"s-{s + 1}.webp", "WEBP", quality=70, method=6)
    return {"pattern": f"/look/frames/{out.name}/s-{{i}}.webp", "width": width, "height": height,
            "cols": cols, "rows": rows, "sheets": sheets}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clips", nargs="+", type=Path)
    ap.add_argument("--fps", type=int, default=24, help="source frame rate (default 24)")
    ap.add_argument("--interpolate", type=int, default=4, help="motion interpolation factor, 1 for none (default 4)")
    ap.add_argument("--frames", type=int, default=420, help="output frame count (default 420)")
    ap.add_argument("--widths", default="720,1080", help="output widths, one folder each (default 720,1080)")
    ap.add_argument("--quality", type=int, default=72, help="WebP quality (default 72)")
    ap.add_argument("--blend", type=int, default=6, help="source frames cross-blended at each join (default 6)")
    ap.add_argument("--floor", type=float, default=0.12,
                    help="share of average speed that still moments keep when re-timing (default 0.12)")
    ap.add_argument("--keep-backdrop", action="store_true", help="don't lift the backdrop to white")
    args = ap.parse_args()

    widths = sorted({int(w) for w in args.widths.split(",")})
    factor = max(1, args.interpolate)

    with tempfile.TemporaryDirectory(prefix="scroll-video-") as tmpdir:
        work = Path(tmpdir)
        print(f"Interpolating {len(args.clips)} clips x{factor} at {widths[-1]} px (this takes a few minutes)...")
        with ThreadPoolExecutor(max_workers=len(args.clips)) as pool:
            clips = list(pool.map(
                lambda kc: extract(kc[1], args.fps, factor, widths[-1], work / str(kc[0])),
                enumerate(args.clips),
            ))

        # Dense sequence with cross-blended joins; joins[k] is the dense index where look k+1 is done.
        dense: list[Recipe] = []
        joins: list[int] = []
        for k, frames in enumerate(clips):
            recipes: list[Recipe] = [(f, None, 0.0) for f in frames]
            if dense and recipes:
                b = min(args.blend * factor, len(recipes), len(dense))
                for i in range(b):
                    t = (i + 1) / (b + 1)
                    a = dense[-b + i][0]
                    dense[-b + i] = (a, recipes[i][0], t)
                joins.append(len(dense) - b // 2 - 1)
                recipes = recipes[b:]
            dense.extend(recipes)
            print(f"{args.clips[k].name}: {len(frames)} frames")
        joins.append(len(dense) - 1)

        # Re-time to equal steps of on-screen change.
        thumbs = [thumb(r) for r in dense]
        motion = np.array([np.abs(thumbs[i + 1] - thumbs[i]).mean() for i in range(len(thumbs) - 1)])
        cost = motion ** 0.8
        cost += args.floor * cost.mean()
        cum = np.concatenate([[0.0], np.cumsum(cost)])
        n = min(args.frames, len(dense))
        positions = np.interp(np.linspace(0, cum[-1], n), cum, np.arange(len(dense)))
        marks = [round(float(cum[j] / cum[-1]), 4) for j in joins]

        base = [render(dense[0]), render(dense[-1])]
        gains = None if args.keep_backdrop else backdrop_gains(base)
        if gains:
            print("backdrop gain per channel: " + ", ".join(f"{g:.3f}" for g in gains))
            luts = [[min(255, round(v * g)) for v in range(256)] for g in gains]

        if OUT.exists():
            shutil.rmtree(OUT)
        for w in widths:
            (OUT / str(w)).mkdir(parents=True)

        def write(item: tuple[int, float]) -> None:
            n_out, pos = item
            i = int(pos)
            t = pos - i
            im = render(dense[i])
            # Between two dense frames (already close together), blend for exact spacing.
            if 0.15 < t < 0.85 and i + 1 < len(dense):
                im = Image.blend(im, render(dense[i + 1]), t)
            elif t >= 0.85 and i + 1 < len(dense):
                im = render(dense[i + 1])
            if gains:
                im = Image.merge("RGB", [ch.point(lut) for ch, lut in zip(im.split(), luts, strict=True)])
            for w in widths:
                out = im if im.width == w else im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
                out.save(OUT / str(w) / f"f-{n_out:04d}.webp", "WEBP", quality=args.quality, method=6)

        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(write, enumerate(positions, start=1)))

    first = Image.open(OUT / str(widths[-1]) / "f-0001.webp")
    proxy = write_proxies(sorted((OUT / str(widths[0])).glob("f-*.webp")), OUT / "proxy")
    manifest = {
        "count": n,
        "pad": 4,
        "width": first.width,
        "height": first.height,
        "marks": marks,
        "tiers": [{"width": w, "pattern": f"/look/frames/{w}/f-{{i}}.webp"} for w in widths],
        "proxy": proxy,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    steps = np.diff(np.interp(positions, np.arange(len(cum)), cum))
    print(f"{n} frames from {len(dense)} interpolated; change per step {steps.mean():.2f} "
          f"(max {steps.max():.2f}); looks complete at {marks}")
    for folder in [str(w) for w in widths] + ["proxy"]:
        total = sum(p.stat().st_size for p in (OUT / folder).glob("*.webp"))
        print(f"  {folder}: {total / 1e6:.1f} MB -> {(OUT / folder).relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
