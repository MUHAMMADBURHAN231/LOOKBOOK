"""Image preprocessing and the placeholder renderer used in mock mode."""

import io
import textwrap

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

MAX_SIDE = 1024
VTON_SIZE = (768, 1024)  # IDM-VTON / CatVTON expect 3:4 portrait


class InvalidImage(ValueError):
    pass


def normalize_upload(data: bytes) -> bytes:
    """Fix EXIF rotation, strip metadata (incl. GPS), convert to RGB JPEG, cap the size."""
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImage("Could not read that image. Please upload a JPEG or PNG.") from exc
    if min(img.size) < 256:
        raise InvalidImage("Image is too small. Please use a photo at least 256px wide.")
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    return to_jpeg(img)


def to_vton_canvas(data: bytes) -> bytes:
    """Letterbox a photo onto a 768x1024 canvas without cropping the person."""
    img = Image.open(io.BytesIO(data)).convert("RGB")
    fitted = ImageOps.pad(img, VTON_SIZE, color=(255, 255, 255))
    return to_jpeg(fitted)


def to_jpeg(img: Image.Image, quality: int = 92) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def render_mock(photo: bytes, summary: str) -> bytes:
    """Stand-in for the generator: the user's photo with the outfit summary drawn on it."""
    img = Image.open(io.BytesIO(photo)).convert("RGB")
    tint = Image.new("RGB", img.size, (219, 39, 119))
    img = Image.blend(img, tint, 0.12)

    draw = ImageDraw.Draw(img, "RGBA")
    width, height = img.size
    font_size = max(14, width // 32)
    try:
        font = ImageFont.load_default(size=font_size)
    except TypeError:  # Pillow < 10.1
        font = ImageFont.load_default()

    lines = ["MOCK PREVIEW", *textwrap.wrap(summary, width=max(20, width // (font_size // 2 + 1)))]
    line_h = font_size + 6
    box_h = line_h * len(lines) + 24
    draw.rectangle([0, height - box_h, width, height], fill=(17, 17, 17, 190))
    y = height - box_h + 12
    for i, line in enumerate(lines):
        draw.text((16, y), line, fill=(244, 114, 182) if i == 0 else (255, 255, 255), font=font)
        y += line_h
    return to_jpeg(img)
