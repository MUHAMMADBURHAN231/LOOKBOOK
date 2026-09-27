"""Prompt builders for image models."""

from app.services.outfit import describe_garment
from app.services.pipeline.base import TryOnJob


def edit_prompt(job: TryOnJob) -> str:
    spec = job.spec
    if spec and spec.garments:
        items = [describe_garment(g) for g in spec.garments]
        if spec.footwear:
            items.append(spec.footwear)
        items += spec.accessories
        outfit, summary, scene = "; ".join(items), spec.summary, spec.scene
    else:
        outfit, summary, scene = job.description, job.description, ""
    lines = [
        "Edit this photo so the same person is wearing a new outfit.",
        f"Outfit: {outfit}.",
        f"Overall look: {summary}.",
        "Keep the person's face, identity, skin tone, hair, body shape and pose exactly the same.",
        "Make the clothes fit naturally with realistic fabric folds, texture and lighting.",
        f"Place them {scene}, with lighting that matches the new setting." if scene else "Keep the original background.",
        "Photorealistic, full resolution, no text or watermarks.",
    ]
    return "\n".join(lines)
