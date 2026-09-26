from typing import Literal

from pydantic import BaseModel, Field

GarmentCategory = Literal["upper_body", "lower_body", "dresses"]
Pipeline = Literal["edit", "vton"]


class Garment(BaseModel):
    """One piece of the outfit, e.g. a navy blazer."""

    type: str = Field(description="Garment type, e.g. 'blazer', 'turtleneck', 'sherwani'")
    color: str = Field(default="", description="Main color(s)")
    material: str = Field(default="", description="Fabric or material, if stated or implied")
    fit: str = Field(default="", description="Cut or fit, e.g. 'tailored', 'oversized'")
    details: str = Field(default="", description="Patterns, embroidery, logos, etc.")
    category: GarmentCategory = Field(
        default="upper_body", description="Body region for try-on masking"
    )


class OutfitSpec(BaseModel):
    """Structured version of a plain-English outfit description."""

    summary: str = Field(description="One-line restatement of the outfit")
    garments: list[Garment] = Field(default_factory=list)
    accessories: list[str] = Field(default_factory=list)
    footwear: str = ""
    scene: str = Field(default="", description="Background or setting, if requested")
    style_tags: list[str] = Field(default_factory=list)


class InterpretRequest(BaseModel):
    description: str = Field(min_length=3, max_length=1000)


class GenerateResponse(BaseModel):
    id: str
    image_url: str
    source_url: str
    spec: OutfitSpec
    pipeline: Pipeline
    mock: bool
    elapsed_ms: int


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)


class OutfitSuggestion(BaseModel):
    title: str
    description: str = Field(description="Plain-English outfit description usable for try-on")


class ChatResponse(BaseModel):
    reply: str
    suggestions: list[OutfitSuggestion] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    mock: bool


class SaveLookRequest(BaseModel):
    generation_id: str
    title: str = Field(default="", max_length=120)
    collection: str = Field(default="", max_length=60)


class Look(BaseModel):
    id: str
    title: str
    collection: str
    description: str
    image_url: str
    spec: OutfitSpec
    created_at: str
