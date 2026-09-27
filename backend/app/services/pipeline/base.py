"""Try-on pipeline contracts.

A job moves through the state machine from the specification:

    QUEUED -> PREPARING_INPUTS -> PREPROCESSING_POSE -> PREPROCESSING_MASK -> DIFFUSION_WARP
           -> POSTPROCESSING_FACE -> UPLOADING -> COMPLETED          (any stage -> FAILED)

Adapters only report the stages they actually perform. Hosted IDM-VTON, for example, does its
own pose and parsing internally, so that adapter reports GENERATING_GARMENT and DIFFUSION_WARP
rather than claiming separate pose/mask steps.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal

from app.services.outfit import OutfitSpec

Stage = Literal[
    "QUEUED",
    "PREPARING_INPUTS",
    "SAFETY_CHECK",
    "PREPROCESSING_POSE",
    "PREPROCESSING_MASK",
    "GENERATING_GARMENT",
    "DIFFUSION_WARP",
    "POSTPROCESSING_FACE",
    "UPLOADING",
    "RETRYING",
    "COMPLETED",
    "FAILED",
]
TERMINAL = {"COMPLETED", "FAILED"}

Report = Callable[[Stage, int], Awaitable[None]]


@dataclass
class TryOnJob:
    photo: bytes  # normalized RGB JPEG
    category: str
    enhance_face: bool
    description: str  # plain-English garment/outfit description
    spec: OutfitSpec | None = None
    garment_image: bytes | None = None  # catalog flat-lay, when a catalog garment was chosen
    garment_title: str = ""


@dataclass
class TryOnResult:
    image: bytes
    content_type: str = "image/webp"
    extras: dict = field(default_factory=dict)  # e.g. pose keypoints from a GPU worker


class PipelineError(RuntimeError):
    """Permanent failure: retrying won't help (bad input, content refused, misconfiguration)."""


class TransientPipelineError(RuntimeError):
    """Temporary failure (provider timeout, 5xx, rate limit): the job is retried with backoff."""


class TryOnAdapter:
    name: str = "base"
    paid: bool = False

    async def run(self, job: TryOnJob, report: Report) -> TryOnResult:  # pragma: no cover
        raise NotImplementedError
