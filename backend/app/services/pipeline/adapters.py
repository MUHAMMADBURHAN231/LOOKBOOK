"""Inference adapters. The worker picks one per job (see `select_adapter`), so switching between
free local development, a self-hosted GPU and hosted APIs needs configuration only, not code."""

import asyncio
import base64
import io

import httpx
from PIL import Image

from app.core.config import get_settings
from app.core.spend import record_paid_call
from app.services import gemini, imaging
from app.services.prompts import edit_prompt
from app.services import replicate_client as rep
from app.services.pipeline.base import (
    PipelineError,
    Report,
    TransientPipelineError,
    TryOnAdapter,
    TryOnJob,
    TryOnResult,
)


def to_webp(data: bytes, quality: int = 90) -> bytes:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=quality, method=4)
    return buf.getvalue()


class MockAdapter(TryOnAdapter):
    """No external calls. Walks the full state machine with short delays and returns the photo
    with a caption, so the UI, WebSocket progress and storage flow can be exercised offline."""

    name = "mock"

    def __init__(self, delay: float = 0.35):
        self.delay = delay

    async def run(self, job: TryOnJob, report: Report) -> TryOnResult:
        for stage, pct in (
            ("PREPROCESSING_POSE", 25),
            ("PREPROCESSING_MASK", 40),
            ("DIFFUSION_WARP", 70),
            ("POSTPROCESSING_FACE", 85),
        ):
            await report(stage, pct)
            await asyncio.sleep(self.delay)
        rendered = imaging.render_mock(job.photo, job.description)
        return TryOnResult(to_webp(rendered))


class GeminiEditAdapter(TryOnAdapter):
    """Instruction-based image editing. One call; also handles scene/background changes."""

    name = "gemini"
    paid = True

    async def run(self, job: TryOnJob, report: Report) -> TryOnResult:
        await report("DIFFUSION_WARP", 55)
        record_paid_call("gemini")
        try:
            out = await asyncio.to_thread(
                gemini.edit_image, get_settings().gemini_image_model, job.photo, edit_prompt(job)
            )
        except gemini.GeminiError as exc:
            raise _classify(str(exc)) from exc
        return TryOnResult(to_webp(out))


class ReplicateVtonAdapter(TryOnAdapter):
    """Hosted diffusion try-on: FLUX garment flat-lay (if needed) -> IDM-VTON -> CodeFormer.
    IDM-VTON performs its own DensePose + human parsing, so there are no separate pose/mask calls."""

    name = "replicate"
    paid = True

    async def run(self, job: TryOnJob, report: Report) -> TryOnResult:
        s = get_settings()
        try:
            garment = job.garment_image
            if garment is None:
                await report("GENERATING_GARMENT", 25)
                record_paid_call("replicate")
                out = await rep.run(
                    s.replicate_garment_model,
                    {
                        "prompt": (
                            f"Product photo of a {job.description}, flat lay, front view, centered, "
                            "plain white background, studio lighting, no person, no mannequin"
                        ),
                        "aspect_ratio": "3:4",
                        "output_format": "png",
                        "num_outputs": 1,
                    },
                )
                garment = await rep.download(rep.first_url(out))

            await report("DIFFUSION_WARP", 55)
            record_paid_call("replicate")
            out = await rep.run(
                s.replicate_vton_model,
                {
                    "human_img": rep.data_uri(imaging.to_vton_canvas(job.photo)),
                    "garm_img": rep.data_uri(garment, "image/png"),
                    "garment_des": job.description,
                    "category": job.category,
                    "crop": False,
                    "steps": 30,
                    "seed": 42,
                },
            )
            result = await rep.download(rep.first_url(out))

            if job.enhance_face:
                await report("POSTPROCESSING_FACE", 85)
                record_paid_call("replicate")
                try:
                    restored = await rep.run(
                        s.replicate_restore_model,
                        {
                            "image": rep.data_uri(result, "image/png"),
                            "codeformer_fidelity": 0.8,
                            "upscale": 1,
                            "face_upsample": True,
                            "background_enhance": False,
                        },
                    )
                    result = await rep.download(rep.first_url(restored))
                except rep.ReplicateError:
                    pass  # restoration is an enhancement; keep the try-on result
        except (rep.ReplicateError, httpx.HTTPError) as exc:
            raise _classify(str(exc)) from exc
        return TryOnResult(to_webp(result))


class RemoteGpuAdapter(TryOnAdapter):
    """Self-hosted worker (Kaggle/RunPod/local GPU) running DWPose + SCHP + CatVTON/IDM-VTON +
    CodeFormer behind the HTTP contract in docs/gpu-worker.md."""

    name = "remote"

    async def run(self, job: TryOnJob, report: Report) -> TryOnResult:
        s = get_settings()
        await report("PREPROCESSING_POSE", 20)
        payload = {
            "person_image": base64.b64encode(job.photo).decode(),
            "garment_image": base64.b64encode(job.garment_image).decode() if job.garment_image else None,
            "garment_description": job.description,
            "category": job.category,
            "enhance_face": job.enhance_face,
            "steps": 30,
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(240, connect=10)) as http:
                resp = await http.post(
                    s.gpu_worker_url.rstrip("/") + "/v1/tryon",
                    json=payload,
                    headers={"Authorization": f"Bearer {s.gpu_worker_token}"} if s.gpu_worker_token else {},
                )
        except httpx.HTTPError as exc:
            raise TransientPipelineError(f"GPU worker unreachable: {type(exc).__name__}") from exc
        if resp.status_code >= 500 or resp.status_code == 429:
            raise TransientPipelineError(f"GPU worker error {resp.status_code}")
        if resp.status_code >= 400:
            raise PipelineError(f"GPU worker rejected the job ({resp.status_code})")
        body = resp.json()
        await report("POSTPROCESSING_FACE", 85)
        extras = {k: body[k] for k in ("pose_keypoints", "timings") if k in body}
        return TryOnResult(to_webp(base64.b64decode(body["image"])), extras=extras)


def _classify(message: str) -> Exception:
    lowered = message.lower()
    transient = ("timeout", "timed out", "rate limit", "429", "500", "502", "503", "504", "unreachable")
    if any(t in lowered for t in transient):
        return TransientPipelineError(message)
    return PipelineError(message)


def select_adapter(pipeline: str) -> TryOnAdapter:
    """pipeline: 'auto' | 'edit' | 'vton'. The TRYON_ADAPTER setting can force one adapter."""
    s = get_settings()
    forced = s.tryon_adapter
    if s.use_mock or forced == "mock":
        return MockAdapter()
    if forced == "gemini" or (forced == "auto" and pipeline == "edit" and s.gemini_api_key):
        return GeminiEditAdapter()
    if forced == "remote" or (forced == "auto" and s.gpu_worker_url):
        return RemoteGpuAdapter()
    if forced == "replicate" or (forced == "auto" and s.replicate_api_token):
        return ReplicateVtonAdapter()
    if s.gemini_api_key:
        return GeminiEditAdapter()
    return MockAdapter()

