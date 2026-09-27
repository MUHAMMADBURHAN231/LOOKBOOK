"""Seed the garment catalog (images + 768-d embeddings) and a demo merchant for the widget.

    python -m scripts.seed_catalog            # insert missing garments
    python -m scripts.seed_catalog --reembed  # recompute every embedding (after switching provider)

Garment images are rendered flat-lays so the demo works without external assets; replace them by
uploading real product photos to garments/<slug>.png in storage.
"""

import argparse
import asyncio
import io
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import Garment, Merchant
from app.db.session import _async_sessionmaker
from app.services import embeddings
from app.services.storage import get_storage

SEED = Path(__file__).resolve().parents[1] / "app" / "data" / "catalog_seed.json"
W, H = 600, 800

SHAPES = {
    "long": [(150, 110), (240, 80), (300, 115), (360, 80), (450, 110), (560, 560), (495, 580), (430, 250), (435, 690), (165, 690), (170, 250), (105, 580), (40, 560)],
    "tee": [(150, 110), (240, 80), (300, 115), (360, 80), (450, 110), (545, 280), (470, 320), (430, 250), (435, 650), (165, 650), (170, 250), (130, 320), (55, 280)],
    "hoodie": [(150, 120), (230, 90), (250, 40), (350, 40), (370, 90), (450, 120), (560, 580), (495, 600), (430, 260), (440, 700), (160, 700), (170, 260), (105, 600), (40, 580)],
    "coat": [(150, 105), (245, 75), (300, 250), (355, 75), (450, 105), (565, 570), (500, 590), (440, 250), (450, 700), (150, 700), (160, 250), (100, 590), (35, 570)],
    "longcoat": [(160, 95), (250, 65), (300, 230), (350, 65), (440, 95), (560, 540), (495, 560), (435, 240), (470, 770), (130, 770), (165, 240), (105, 560), (40, 540)],
    "kurta": [(165, 95), (245, 70), (300, 105), (355, 70), (435, 95), (555, 520), (490, 540), (430, 230), (470, 780), (130, 780), (170, 230), (110, 540), (45, 520)],
    "dress": [(215, 80), (255, 80), (275, 200), (325, 200), (345, 80), (385, 80), (400, 300), (480, 770), (120, 770), (200, 300)],
    "trousers": [(175, 60), (425, 60), (470, 770), (345, 770), (300, 250), (255, 770), (130, 770)],
}


def render(item: dict) -> bytes:
    base = Image.new("RGB", (W, H), "#f4f3ef")
    shadow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shadow).polygon([(x + 10, y + 16) for x, y in SHAPES[item["shape"]]], fill=90)
    base.paste(Image.new("RGB", (W, H), "#cfccc4"), mask=shadow.filter(ImageFilter.GaussianBlur(18)))

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.polygon(SHAPES[item["shape"]], fill=item["fill"])
    # Soft vertical shading suggests fabric volume.
    shade = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(shade)
    for x in range(W):
        sd.line([(x, 0), (x, H)], fill=int(40 * abs(x - W / 2) / (W / 2)))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon(SHAPES[item["shape"]], fill=255)
    base.paste(layer, mask=layer)
    base.paste(Image.new("RGB", (W, H), "black"), mask=Image.composite(shade, Image.new("L", (W, H), 0), mask))

    trim = item.get("trim")
    if trim:
        td = ImageDraw.Draw(base)
        if item["shape"] in ("coat", "longcoat", "kurta"):
            td.line([(300, 250 if item["shape"] != "kurta" else 110), (300, 690)], fill=trim, width=4)
            for y in range(300, 660, 70):
                td.ellipse([306, y, 318, y + 12], fill=trim)
        elif item["shape"] == "trousers":
            td.rectangle([185, 380, 245, 450], outline=trim, width=4)
            td.rectangle([355, 380, 415, 450], outline=trim, width=4)
        else:
            td.line([(300, 115), (300, 690)], fill=trim, width=3)
    buf = io.BytesIO()
    base.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def text_for(item: dict) -> str:
    return f"{item['title']}. {item['description']}. {item['color']} {item['category'].replace('_', ' ')} {item['season']}"


async def main(reembed: bool) -> None:
    items = json.loads(SEED.read_text())
    storage = get_storage()
    model = embeddings.model_name()
    async with _async_sessionmaker()() as db:
        existing = {g.slug: g for g in await db.scalars(select(Garment))}
        todo = items if reembed else [i for i in items if i["slug"] not in existing]
        vectors = await embeddings.embed_texts([text_for(i) for i in todo]) if todo else []
        for item, vector in zip(todo, vectors, strict=True):
            key = f"garments/{item['slug']}.png"
            await asyncio.to_thread(storage.put, key, render(item), "image/png")
            g = existing.get(item["slug"]) or Garment(slug=item["slug"])
            g.title = item["title"]
            g.category = item["category"]
            g.color = item["color"]
            g.season = item["season"]
            g.brand = "LOOKBOOK Demo"
            g.description = item["description"]
            g.price_cents = item["price"] * 100
            g.image_key = key
            g.embedding = vector
            g.embedding_model = model
            db.add(g)
        demo = await db.scalar(select(Merchant).where(Merchant.publishable_key == "pk_demo_northwind"))
        if not demo:
            db.add(
                Merchant(
                    name="Northwind Atelier (demo)",
                    publishable_key="pk_demo_northwind",
                    allowed_origins=[get_settings().app_url.rstrip("/")],
                )
            )
        await db.commit()
    print(f"Seeded {len(todo)} garments with {model} embeddings.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reembed", action="store_true")
    asyncio.run(main(parser.parse_args().reembed))
