"""Outfit Interpreter: plain English -> structured OutfitSpec."""

import re

from app.core.config import get_settings
from app.services.outfit import GarmentSpec as Garment, OutfitSpec
from . import gemini

SYSTEM = """You are a fashion technologist. Convert the user's outfit description into a
structured garment specification. Rules:
- One entry in `garments` per clothing item (not accessories or shoes).
- Infer sensible material/fit only when strongly implied; otherwise leave blank.
- `category` is the body region: upper_body (tops, jackets, blazers, kurtas),
  lower_body (trousers, skirts, shorts), dresses (dresses, full-body suits, sherwanis, jumpsuits).
- Put sunglasses, hats, jewellery, bags and watches in `accessories`.
- Put the setting ("in front of a Ferrari", "on the moon") in `scene`.
- `style_tags`: 2-4 short tags such as "smart casual", "streetwear", "festive".
Never describe the person's body, face, skin or identity."""


def interpret(description: str) -> OutfitSpec:
    settings = get_settings()
    if settings.use_mock:
        return interpret_offline(description)
    return gemini.generate_json(
        settings.gemini_text_model, description, OutfitSpec, system=SYSTEM
    )


# --- offline fallback -----------------------------------------------------

_GARMENTS = {
    "upper_body": [
        "turtleneck", "blazer", "jacket", "hoodie", "shirt", "t-shirt", "tee", "sweater",
        "cardigan", "coat", "kurta", "polo", "blouse", "top", "vest", "waistcoat", "parka",
    ],
    "lower_body": [
        "cargo pants", "pants", "trousers", "jeans", "chinos", "shorts", "skirt", "joggers",
        "shalwar",
    ],
    "dresses": [
        "sherwani", "dress", "gown", "jumpsuit", "suit", "saree", "abaya", "lehenga", "robe",
    ],
}
_ACCESSORIES = [
    "aviator sunglasses", "sunglasses", "hat", "cap", "watch", "necklace", "scarf", "tie",
    "bag", "belt", "earrings", "helmet", "turban",
]
_FOOTWEAR = ["jordan", "sneakers", "boots", "loafers", "heels", "sandals", "khussa", "trainers"]
_COLORS = [
    "black", "white", "navy", "blue", "red", "green", "gold", "silver", "grey", "gray",
    "beige", "brown", "pink", "purple", "orange", "yellow", "cream", "maroon", "olive",
]
_FITS = ["tailored", "oversized", "slim", "loose", "cropped", "fitted", "relaxed", "sleek"]


def interpret_offline(description: str) -> OutfitSpec:
    """Keyword-based parser so the app works without an API key."""
    text = description.lower()
    garments: list[Garment] = []
    taken: list[tuple[int, int]] = []

    for category, words in _GARMENTS.items():
        for word in words:
            for m in re.finditer(rf"\b{re.escape(word)}s?\b", text):
                if any(a <= m.start() < b for a, b in taken):
                    continue
                taken.append((m.start(), m.end()))
                window = text[max(0, m.start() - 40) : m.start()]
                garments.append(
                    Garment(
                        type=word,
                        color=_last_match(window, _COLORS),
                        fit=_last_match(window, _FITS),
                        details="embroidery" if "embroider" in text else "",
                        category=category,  # type: ignore[arg-type]
                    )
                )

    accessories = []
    for word in _ACCESSORIES:
        if word in text and not any(word in a for a in accessories):
            accessories.append(word)

    scene = ""
    m = re.search(r"\b(standing |posing |sitting )?(in front of|on the|at the|in the|at a|on a)\b(.+)$", text)
    if m:
        scene = (m.group(2) + m.group(3)).strip(" .,")

    footwear = next((w for w in _FOOTWEAR if w in text), "")
    if footwear == "jordan":
        footwear = "Jordan sneakers"

    tags = []
    for tag, keys in {
        "smart casual": ["blazer", "chinos", "loafers"],
        "streetwear": ["hoodie", "cargo", "jordan", "sneakers", "oversized"],
        "festive": ["sherwani", "embroider", "lehenga", "gold"],
        "formal": ["suit", "tie", "gown", "tuxedo"],
    }.items():
        if any(k in text for k in keys):
            tags.append(tag)

    return OutfitSpec(
        summary=description.strip().rstrip("."),
        garments=garments,
        accessories=accessories,
        footwear=footwear,
        scene=scene,
        style_tags=tags,
    )


def _last_match(window: str, options: list[str]) -> str:
    best, pos = "", -1
    for opt in options:
        i = window.rfind(opt)
        if i > pos:
            best, pos = opt, i
    return best
