"""Turn one film shot (a generated video) into scroll-scrubbed frames for the landing page.

    python scripts/build_film.py assets/film/video/shirt-1080p.mp4 --name shirt

Writes frontend/public/film/<name>/: WebP frames in one folder per width, small proxy sprite sheets
(every frame, so scrubbing never shows a blank while full frames stream in), a poster, and
manifest.json for ScrollVideo. Steps:

1. Decode at the source frame rate, keeping the 16:9 shot whole (the page crops for phones).
2. Re-time: generated clips move unevenly (a garment drifting barely changes the picture, one
   wrapping on changes it a lot), so output frames are picked at equal steps of on-screen change,
   with a floor so still moments keep some scroll. A steady scroll then gives steady motion.
3. Measure the backdrop colour from the frame borders, so the page can sit on exactly that colour.
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
OUT = ROOT / "frontend" / "public" / "film"
PROXY_W = 320


def decode(clip: Path, tmp: Path) -> list[Path]:
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ff, "-loglevel", "error", "-y", "-i", str(clip), "-q:v", "2", str(tmp / "s%04d.jpg")],
                   check=True)
    return sorted(tmp.glob("s*.jpg"))


def retime(frames: list[Path], count: int, floor: float) -> list[float]:
    """Fractional source positions for `count` output frames, at equal steps of visible change."""
    small = [np.asarray(Image.open(f).convert("L").resize((160, 90)), np.float32) for f in frames]
    diff = np.array([np.abs(b - a).mean() for a, b in zip(small, small[1:], strict=False)])
    diff = np.maximum(diff, floor * diff.mean())
    cum = np.concatenate([[0], np.cumsum(diff)])
    targets = np.linspace(0, cum[-1], count)
    return list(np.interp(targets, cum, np.arange(len(frames))))


def blend(frames: list[Path], pos: float) -> Image.Image:
    i = int(np.floor(pos))
    t = pos - i
    a = Image.open(frames[i]).convert("RGB")
    if t < 0.02 or i + 1 >= len(frames):
        return a
    return Image.blend(a, Image.open(frames[i + 1]).convert("RGB"), float(t))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clip", type=Path)
    ap.add_argument("--name", required=True, help="output folder under frontend/public/film/")
    ap.add_argument("--frames", type=int, default=180, help="output frame count (default 180)")
    ap.add_argument("--widths", default="960,1600", help="output widths (default 960,1600)")
    ap.add_argument("--quality", type=int, default=74, help="WebP quality (default 74)")
    ap.add_argument("--floor", type=float, default=0.25,
                    help="minimum share of average change a still moment keeps (default 0.25)")
    args = ap.parse_args()

    out = OUT / args.name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    widths = [int(w) for w in args.widths.split(",")]

    with tempfile.TemporaryDirectory() as td:
        src = decode(args.clip, Path(td))
        positions = retime(src, args.frames, args.floor)
        w0, h0 = Image.open(src[0]).size
        pad = len(str(args.frames))

        # Backdrop colour: the median of the top band and the left edge (never the subject).
        first = np.asarray(Image.open(src[0]).convert("RGB"), np.float32)
        border = np.concatenate([first[: h0 // 12].reshape(-1, 3), first[:, : w0 // 20].reshape(-1, 3)])
        backdrop = "#{:02X}{:02X}{:02X}".format(*np.median(border, 0).round().astype(int))

        def render(k: int):
            img = blend(src, positions[k])
            for w in widths:
                h = round(h0 * w / w0 / 2) * 2
                img.resize((w, h), Image.LANCZOS).save(out / str(w) / f"{k + 1:0{pad}d}.webp",
                                                       quality=args.quality, method=6)
            return img.resize((PROXY_W, round(h0 * PROXY_W / w0)), Image.LANCZOS)

        for w in widths:
            (out / str(w)).mkdir()
        with ThreadPoolExecutor() as ex:
            proxies = list(ex.map(render, range(args.frames)))

        # Proxies: every frame, small, in sprite sheets.
        pw, ph = proxies[0].size
        cols, rows = 8, 8
        per = cols * rows
        sheets = (len(proxies) + per - 1) // per
        (out / "proxy").mkdir()
        for s in range(sheets):
            sheet = Image.new("RGB", (pw * cols, ph * rows), backdrop)
            for k, p in enumerate(proxies[s * per:(s + 1) * per]):
                sheet.paste(p, ((k % cols) * pw, (k // cols) * ph))
            sheet.save(out / "proxy" / f"{s + 1}.webp", quality=70, method=6)

        # Posters: first and last frames, for the instant first paint and the reduced-motion page.
        big = widths[-1]
        shutil.copy(out / str(big) / f"{1:0{pad}d}.webp", out / "poster-start.webp")
        shutil.copy(out / str(big) / f"{args.frames:0{pad}d}.webp", out / "poster-end.webp")

    base = f"/film/{args.name}"
    manifest = {
        "count": args.frames,
        "pad": pad,
        "width": w0,
        "height": h0,
        "backdrop": backdrop,
        "marks": [1.0],
        "tiers": [{"width": w, "pattern": f"{base}/{w}/{{i}}.webp"} for w in widths],
        "proxy": {"pattern": f"{base}/proxy/{{i}}.webp", "width": pw, "height": ph, "cols": cols, "rows": rows,
                  "sheets": sheets},
        "poster": {"start": f"{base}/poster-start.webp", "end": f"{base}/poster-end.webp"},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    sizes = {p.name: sum(f.stat().st_size for f in p.glob("*")) for p in out.iterdir() if p.is_dir()}
    print(f"{args.frames} frames from {len(src)} source frames, backdrop {backdrop}")
    print("sizes:", {k: f"{v / 1e6:.1f} MB" for k, v in sizes.items()})


if __name__ == "__main__":
    main()
