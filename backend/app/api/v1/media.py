"""Portrait uploads: presigned direct-to-storage upload, then server-side validation on confirm."""

import asyncio
import io
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response
from PIL import Image
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from app.api.deps import DB, CurrentUser
from app.core.config import get_settings
from app.db.models import TryOnTask, UserPhoto
from app.services import imaging
from app.services.storage import LocalStorage, StorageError, get_storage

router = APIRouter(prefix="/media", tags=["media"])
ALLOWED_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


class PresignIn(BaseModel):
    file_name: str = Field(max_length=255)
    mime_type: str
    file_size_bytes: int = Field(gt=0)


class UploadInfo(BaseModel):
    url: str
    method: str
    fields: dict[str, str]
    headers: dict[str, str]
    expires_in: int


class PresignOut(BaseModel):
    asset_id: uuid.UUID
    storage_key: str
    upload: UploadInfo


class PhotoOut(BaseModel):
    id: uuid.UUID
    url: str
    width: int | None
    height: int | None
    is_primary: bool
    created_at: datetime


def photo_out(p: UserPhoto) -> PhotoOut:
    return PhotoOut(
        id=p.id,
        url=get_storage().presign_download(p.storage_key),
        width=p.width,
        height=p.height,
        is_primary=p.is_primary,
        created_at=p.created_at,
    )


@router.post("/presign-upload", response_model=PresignOut)
async def presign_upload(body: PresignIn, user: CurrentUser, db: DB):
    if not user.biometric_consent_granted:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Please give consent before uploading a photo.")
    ext = ALLOWED_TYPES.get(body.mime_type)
    if not ext:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Use a JPEG, PNG or WebP photo.")
    max_bytes = get_settings().max_upload_bytes
    if body.file_size_bytes > max_bytes:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Photos must be under 10 MB.")

    photo_id = uuid.uuid4()
    key = f"raw/{user.id}/{photo_id}.{ext}"
    db.add(UserPhoto(id=photo_id, user_id=user.id, storage_key=key, mime_type=body.mime_type))
    await db.commit()
    ticket = await asyncio.to_thread(get_storage().presign_upload, key, body.mime_type, max_bytes)
    return PresignOut(asset_id=photo_id, storage_key=key, upload=UploadInfo(**ticket.__dict__))


@router.post("/{asset_id}/confirm", response_model=PhotoOut)
async def confirm_upload(asset_id: uuid.UUID, user: CurrentUser, db: DB):
    """Validate the uploaded bytes (magic numbers, decodability, size), strip metadata and
    re-encode. Anything that fails is deleted from storage."""
    photo = await db.scalar(select(UserPhoto).where(UserPhoto.id == asset_id, UserPhoto.user_id == user.id))
    if not photo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Upload not found.")
    if photo.status == "ready":
        return photo_out(photo)

    storage = get_storage()
    try:
        raw = await asyncio.to_thread(storage.get, photo.storage_key)
    except StorageError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The upload didn't finish. Please try again.") from exc
    try:
        if len(raw) > get_settings().max_upload_bytes:
            raise imaging.InvalidImage("Photos must be under 10 MB.")
        clean = await asyncio.to_thread(imaging.normalize_upload, raw)
    except imaging.InvalidImage as exc:
        await asyncio.to_thread(storage.delete, photo.storage_key)
        photo.status = "rejected"
        await db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    width, height = Image.open(io.BytesIO(clean)).size
    new_key = photo.storage_key.rsplit(".", 1)[0] + ".jpg"
    await asyncio.to_thread(storage.put, new_key, clean, "image/jpeg")
    if new_key != photo.storage_key:
        await asyncio.to_thread(storage.delete, photo.storage_key)
    has_primary = await db.scalar(
        select(UserPhoto.id).where(UserPhoto.user_id == user.id, UserPhoto.is_primary.is_(True))
    )
    photo.storage_key = new_key
    photo.mime_type = "image/jpeg"
    photo.status = "ready"
    photo.width, photo.height = width, height
    photo.aspect_ratio = round(width / height, 2)
    photo.is_primary = has_primary is None
    await db.commit()
    return photo_out(photo)


@router.get("/photos", response_model=list[PhotoOut])
async def list_photos(user: CurrentUser, db: DB):
    rows = await db.scalars(
        select(UserPhoto)
        .where(UserPhoto.user_id == user.id, UserPhoto.status == "ready")
        .order_by(UserPhoto.created_at.desc())
    )
    return [photo_out(p) for p in rows]


@router.delete("/photos/{photo_id}", status_code=204)
async def delete_photo(photo_id: uuid.UUID, user: CurrentUser, db: DB):
    photo = await db.scalar(select(UserPhoto).where(UserPhoto.id == photo_id, UserPhoto.user_id == user.id))
    if not photo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo not found.")
    storage = get_storage()
    results = await db.scalars(
        select(TryOnTask.result_storage_key).where(TryOnTask.user_photo_id == photo.id)
    )
    for key in [photo.storage_key, *[k for k in results if k]]:
        await asyncio.to_thread(storage.delete, key)
    await db.execute(delete(UserPhoto).where(UserPhoto.id == photo.id))  # cascades to its try-ons
    await db.commit()


# --- Local storage backend: signed, expiring URLs ---------------------------------------------


def _local() -> LocalStorage:
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return storage


@router.put("/local/{token}", status_code=204, include_in_schema=False)
async def local_upload(token: str, request: Request):
    storage = _local()
    try:
        ticket = storage.verify_token(token, "put")
    except StorageError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    if request.headers.get("content-type", "").split(";")[0] != ticket["ct"]:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Content type doesn't match the upload ticket.")
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > ticket["max"]:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File too large.")
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty upload.")
    await asyncio.to_thread(storage.put, ticket["k"], bytes(data), ticket["ct"])


@router.get("/local/{token}", include_in_schema=False)
async def local_download(token: str):
    storage = _local()
    try:
        ticket = storage.verify_token(token, "get")
        data, content_type = await asyncio.to_thread(storage.get_with_type, ticket["k"])
    except StorageError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found or link expired.") from exc
    return Response(
        data,
        media_type=content_type,
        headers={
            "Cache-Control": "private, max-age=600",
            # Images are fetched cross-origin by the frontend (<img> and canvas).
            "Cross-Origin-Resource-Policy": "cross-origin",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )
