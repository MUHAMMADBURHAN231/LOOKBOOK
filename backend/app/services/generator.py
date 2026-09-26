"""Generation engine: photo + OutfitSpec -> photo of the user wearing the outfit.

Two pipelines:
  edit  Gemini image editing. One call; handles backgrounds/scenes. Fastest.
  vton  Garment image (FLUX) -> try-on (IDM-VTON) per garment -> face restore (CodeFormer).
        Keeps the original background; closer to the classic virtual try-on research stack.
"""

import asyncio

from ..config import get_settings
from ..schemas import Garment, OutfitSpec, Pipeline
from . import gemini, imaging
from . import replicate_client as rep

MAX_VTON_GARMENTS = 2


class GenerationError(RuntimeError):
    pass


async def generate(photo: bytes, spec: OutfitSpec, pipeline: Pipeline) -> bytes:
    settings = get_settings()
    if settings.use_mock:
        await asyncio.sleep(0.4)  # keep the UI's loading state visible in demos
        return imaging.render_mock(photo, spec.summary)
    try:
        if pipeline == "vton":
            return await _vton(photo, spec)
        return await asyncio.to_thread(
            gemini.edit_image, settings.gemini_image_model, photo, edit_prompt(spec)
        )
    except (gemini.GeminiError, rep.ReplicateError) as exc:
        raise GenerationError(str(exc)) from exc


def describe_garment(g: Garment) -> str:
    parts = [g.fit, g.color, g.material, g.type]
    text = " ".join(p for p in parts if p)
    return f"{text} with {g.details}" if g.details else text


def edit_prompt(spec: OutfitSpec) -> str:
    items = [describe_garment(g) for g in spec.garments]
    if spec.footwear:
        items.append(spec.footwear)
    items += spec.accessories
    outfit = "; ".join(items) if items else spec.summary
    lines = [
        "Edit this photo so the same person is wearing a new outfit.",
        f"Outfit: {outfit}.",
        f"Overall look: {spec.summary}.",
        "Keep the person's face, identity, skin tone, hair, body shape and pose exactly the same.",
        "Make the clothes fit naturally with realistic fabric folds, texture and lighting.",
    ]
    if spec.scene:
        lines.append(f"Place them {spec.scene}, with lighting that matches the new setting.")
    else:
        lines.append("Keep the original background.")
    lines.append("Photorealistic, full resolution, no text or watermarks.")
    return "\n".join(lines)


async def _vton(photo: bytes, spec: OutfitSpec) -> bytes:
    settings = get_settings()
    garments = _pick_vton_garments(spec)
    if not garments:
        raise GenerationError("No clothing items found in the description to try on.")

    person = imaging.to_vton_canvas(photo)
    # Garment images don't depend on each other, so generate them in parallel.
    garment_images = await asyncio.gather(*(_garment_image(g) for g in garments))

    for garment, garment_img in zip(garments, garment_images):
        out = await rep.run(
            settings.replicate_vton_model,
            {
                "human_img": rep.data_uri(person),
                "garm_img": rep.data_uri(garment_img, "image/png"),
                "garment_des": describe_garment(garment),
                "category": garment.category,
                "crop": False,
                "steps": 30,
                "seed": 42,
            },
        )
        person = await rep.download(rep.first_url(out))

    try:
        restored = await rep.run(
            settings.replicate_restore_model,
            {
                "image": rep.data_uri(person, "image/png"),
                "codeformer_fidelity": 0.8,
                "upscale": 1,
                "face_upsample": True,
                "background_enhance": False,
            },
        )
        person = await rep.download(rep.first_url(restored))
    except rep.ReplicateError:
        pass  # face restoration is a nice-to-have; keep the try-on result
    return person


def _pick_vton_garments(spec: OutfitSpec) -> list[Garment]:
    """IDM-VTON takes one garment per pass. A full-body item wins; otherwise top then bottom."""
    dresses = [g for g in spec.garments if g.category == "dresses"]
    if dresses:
        return dresses[:1]
    # One top only: IDM-VTON replaces the whole upper-body region, so layering isn't possible.
    tops = [g for g in spec.garments if g.category == "upper_body"]
    bottoms = [g for g in spec.garments if g.category == "lower_body"]
    picked = bottoms[:1] + tops[-1:]
    return picked[:MAX_VTON_GARMENTS]


async def _garment_image(g: Garment) -> bytes:
    prompt = (
        f"Product photo of a {describe_garment(g)}, flat lay, front view, centered, "
        "plain white background, studio lighting, no person, no mannequin, e-commerce catalog"
    )
    out = await rep.run(
        get_settings().replicate_garment_model,
        {"prompt": prompt, "aspect_ratio": "3:4", "output_format": "png", "num_outputs": 1},
    )
    return await rep.download(rep.first_url(out))
