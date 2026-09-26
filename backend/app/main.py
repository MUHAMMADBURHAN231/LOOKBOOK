import asyncio
import logging
import re
import time
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .schemas import (
    ChatRequest,
    ChatResponse,
    GenerateResponse,
    InterpretRequest,
    Look,
    OutfitSpec,
    Pipeline,
    SaveLookRequest,
)
from .services import generator, imaging, interpreter, stylist
from .services.gemini import GeminiError
from .storage import Storage

log = logging.getLogger("lookbook")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_MEDIA_NAME = re.compile(r"^[0-9a-f]{32}\.(jpg|png)$")

settings = get_settings()
storage = Storage(settings.storage_dir)


@asynccontextmanager
async def lifespan(_: FastAPI):
    removed = storage.purge_older_than(settings.retention_days)
    log.info("Retention: removed %d expired files", removed)
    yield


app = FastAPI(title="LOOKBOOK API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/media", StaticFiles(directory=storage.media_dir), name="media")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "mock": settings.use_mock,
        "default_pipeline": settings.default_pipeline,
        "vton_available": bool(settings.replicate_api_token) and not settings.use_mock,
        "retention_days": settings.retention_days,
    }


@app.post("/api/interpret", response_model=OutfitSpec)
async def interpret(req: InterpretRequest):
    return await _interpret(req.description)


@app.post("/api/generate", response_model=GenerateResponse)
async def generate(
    description: Annotated[str, Form(min_length=3, max_length=1000)],
    consent: Annotated[bool, Form()] = False,
    pipeline: Annotated[Pipeline | None, Form()] = None,
    photo: Annotated[UploadFile | None, File()] = None,
    source_file: Annotated[str | None, Form()] = None,
):
    """Photo + outfit description -> image of the user wearing it.

    Send `photo` on the first request; the response's `source_url` names the stored photo,
    which later requests can reuse via `source_file` instead of uploading again.
    """
    if not consent:
        raise HTTPException(400, "Please confirm consent to process your photo.")
    pipeline = pipeline or settings.default_pipeline  # type: ignore[assignment]
    if pipeline == "vton" and not settings.replicate_api_token and not settings.use_mock:
        raise HTTPException(400, "The vton pipeline needs REPLICATE_API_TOKEN.")

    started = time.perf_counter()
    if photo is not None:
        raw = await photo.read(MAX_UPLOAD_BYTES + 1)
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Photo must be under 10 MB.")
        try:
            source_bytes = imaging.normalize_upload(raw)
        except imaging.InvalidImage as exc:
            raise HTTPException(400, str(exc)) from exc
        source_file = storage.save_image(source_bytes, ".jpg")
    elif source_file and _MEDIA_NAME.match(source_file) and (storage.media_dir / source_file).exists():
        source_bytes = storage.read_image(source_file)
    else:
        raise HTTPException(400, "Upload a photo first.")

    spec = await _interpret(description)
    try:
        result = await generator.generate(source_bytes, spec, pipeline)  # type: ignore[arg-type]
    except generator.GenerationError as exc:
        log.warning("Generation failed: %s", exc)
        raise HTTPException(502, f"Image generation failed: {exc}") from exc

    suffix = ".png" if result[:8] == b"\x89PNG\r\n\x1a\n" else ".jpg"
    image_file = storage.save_image(result, suffix)
    gen_id = storage.add_generation(description, spec, image_file, source_file)
    return GenerateResponse(
        id=gen_id,
        image_url=f"/media/{image_file}",
        source_url=f"/media/{source_file}",
        spec=spec,
        pipeline=pipeline,  # type: ignore[arg-type]
        mock=settings.use_mock,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )


@app.post("/api/stylist/chat", response_model=ChatResponse)
async def stylist_chat(req: ChatRequest):
    try:
        return await asyncio.to_thread(stylist.chat, req.messages)
    except GeminiError as exc:
        raise HTTPException(502, f"Stylist unavailable: {exc}") from exc


@app.get("/api/looks", response_model=list[Look])
def list_looks(collection: str | None = None):
    return storage.list_looks(collection)


@app.post("/api/looks", response_model=Look, status_code=201)
def save_look(req: SaveLookRequest):
    gen = storage.get_generation(req.generation_id)
    if gen is None:
        raise HTTPException(404, "Generation not found (it may have expired).")
    title = req.title.strip() or OutfitSpec.model_validate_json(gen["spec"]).summary[:120]
    look_id = storage.add_look(req.generation_id, title, req.collection.strip())
    return next(look for look in storage.list_looks() if look.id == look_id)


@app.delete("/api/looks/{look_id}", status_code=204)
def delete_look(look_id: str):
    if not storage.delete_look(look_id):
        raise HTTPException(404, "Look not found.")


@app.delete("/api/data", status_code=204)
def delete_all_data():
    """Privacy: wipe every stored photo, generation and saved look."""
    storage.wipe()


async def _interpret(description: str) -> OutfitSpec:
    try:
        return await asyncio.to_thread(interpreter.interpret, description)
    except GeminiError as exc:
        raise HTTPException(502, f"Outfit interpreter unavailable: {exc}") from exc
