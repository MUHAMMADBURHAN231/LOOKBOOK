"""Privacy controls: biometric consent, data export (GDPR Art. 15/20) and deletion (Art. 17)."""

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy import delete, select

from app.api.deps import DB, CurrentUser, clear_session_cookie
from app.db.models import Look, StylistMessage, StylistSession, TryOnTask, User, UserPhoto
from app.services.storage import get_storage

router = APIRouter(prefix="/account", tags=["account"])


class ConsentIn(BaseModel):
    granted: bool


@router.post("/consent", status_code=204)
async def set_consent(body: ConsentIn, user: CurrentUser, db: DB):
    """Granting records when consent was given. Withdrawing deletes every stored portrait and
    generated image, since they can no longer be processed."""
    if body.granted:
        user.biometric_consent_granted = True
        user.biometric_consent_timestamp = datetime.now(timezone.utc)
        await db.commit()
        return
    await _delete_media(db, user)
    user.biometric_consent_granted = False
    user.biometric_consent_timestamp = None
    await db.commit()


@router.get("/export")
async def export(user: CurrentUser, db: DB) -> dict:
    tasks = await db.scalars(select(TryOnTask).where(TryOnTask.user_id == user.id))
    looks = await db.scalars(select(Look).where(Look.user_id == user.id))
    sessions = await db.scalars(select(StylistSession).where(StylistSession.user_id == user.id))
    out_sessions = []
    for s in sessions:
        msgs = await db.scalars(select(StylistMessage).where(StylistMessage.session_id == s.id).order_by(StylistMessage.created_at))
        out_sessions.append(
            {"title": s.title, "preferences": s.context_memory, "messages": [{"role": m.role, "content": m.content, "at": m.created_at.isoformat()} for m in msgs]}
        )
    return {
        "account": {
            "email": user.email,
            "full_name": user.full_name,
            "created_at": user.created_at.isoformat(),
            "biometric_consent_granted": user.biometric_consent_granted,
            "biometric_consent_timestamp": user.biometric_consent_timestamp.isoformat() if user.biometric_consent_timestamp else None,
        },
        "try_ons": [
            {"id": str(t.id), "prompt": t.custom_prompt, "status": t.status, "created_at": t.created_at.isoformat()} for t in tasks
        ],
        "looks": [{"title": lk.title, "collection": lk.collection, "created_at": lk.created_at.isoformat()} for lk in looks],
        "stylist_conversations": out_sessions,
    }


@router.delete("/data", status_code=204)
async def delete_data(user: CurrentUser, db: DB):
    """Delete portraits, results, looks and conversations; keep the account."""
    await _delete_media(db, user)
    await db.execute(delete(StylistSession).where(StylistSession.user_id == user.id))
    await db.commit()


@router.delete("", status_code=204)
async def delete_account(user: CurrentUser, db: DB, response: Response):
    await _delete_media(db, user)
    await db.execute(delete(User).where(User.id == user.id))  # cascades to everything else
    await db.commit()
    clear_session_cookie(response)


async def _delete_media(db, user) -> None:
    storage = get_storage()
    await asyncio.to_thread(storage.delete_prefix, f"raw/{user.id}/")
    await asyncio.to_thread(storage.delete_prefix, f"results/{user.id}/")
    await db.execute(delete(Look).where(Look.user_id == user.id))
    await db.execute(delete(TryOnTask).where(TryOnTask.user_id == user.id))
    await db.execute(delete(UserPhoto).where(UserPhoto.user_id == user.id))
