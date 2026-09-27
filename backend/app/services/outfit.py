"""Structured outfit description produced by the Outfit Interpreter."""

from typing import Literal

from pydantic import BaseModel, Field

GarmentCategory = Literal["upper_body", "lower_body", "dresses"]


class GarmentSpec(BaseModel):
    """One piece of the outfit, e.g. a navy blazer."""

    type: str = Field(description="Garment type, e.g. 'blazer', 'turtleneck', 'sherwani'")
    color: str = Field(default="", description="Main color(s)")
    material: str = Field(default="", description="Fabric or material, if stated or implied")
    fit: str = Field(default="", description="Cut or fit, e.g. 'tailored', 'oversized'")
    details: str = Field(default="", description="Patterns, embroidery, logos, etc.")
    category: GarmentCategory = Field(default="upper_body", description="Body region for try-on masking")


class OutfitSpec(BaseModel):
    """Structured version of a plain-English outfit description."""

    summary: str = Field(description="One-line restatement of the outfit")
    garments: list[GarmentSpec] = Field(default_factory=list)
    accessories: list[str] = Field(default_factory=list)
    footwear: str = ""
    scene: str = Field(default="", description="Background or setting, if requested")
    style_tags: list[str] = Field(default_factory=list)


def describe_garment(g: GarmentSpec) -> str:
    text = " ".join(p for p in (g.fit, g.color, g.material, g.type) if p)
    return f"{text} with {g.details}" if g.details else text
