import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.core.config import get_settings
from app.core.rate_limit import check_rate_limit
from app.db.models import Garment, StylistMessage, StylistSession
from app.services.catalog import GarmentCard, card
from app.services.gemini import GeminiError
from app.services.stylist.agent import run_stylist

router = APIRouter(prefix="/stylist", tags=["stylist"])


class ChatIn(BaseModel):
    session_id: uuid.UUID | None = None
    message: str = Field(min_length=1, max_length=2000)


class ChatOut(BaseModel):
    session_id: uuid.UUID
    reply: str
    recommended_garments: list[GarmentCard]
    tools_used: list[str]


class MessageOut(BaseModel):
    role: str
    content: str
    garments: list[GarmentCard]
    created_at: datetime


class SessionOut(BaseModel):
    id: uuid.UUID
    title: str
    updated_at: datetime


async def _cards(db, ids: list[str]) -> list[GarmentCard]:
    if not ids:
        return []
    rows = {str(g.id): g for g in await db.scalars(select(Garment).where(Garment.id.in_([uuid.UUID(i) for i in ids])))}
    return [card(rows[i]) for i in ids if i in rows]


@router.post("/chat", response_model=ChatOut)
async def chat(body: ChatIn, user: CurrentUser, db: DB):
    await check_rate_limit(f"stylist:{user.id}", get_settings().rate_stylist_per_minute, 60)
    if body.session_id:
        session = await db.scalar(
            select(StylistSession).where(StylistSession.id == body.session_id, StylistSession.user_id == user.id)
        )
        if not session:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found.")
    else:
        session = StylistSession(user_id=user.id, title=body.message[:120])
        db.add(session)
        await db.flush()

    history = [
        {"role": m.role, "content": m.content}
        for m in await db.scalars(
            select(StylistMessage)
            .where(StylistMessage.session_id == session.id)
            .order_by(StylistMessage.created_at.desc())
            .limit(12)
        )
    ][::-1]

    try:
        result = await run_stylist(db, user.id, body.message, history, session.context_memory or {})
    except GeminiError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Stylist unavailable: {exc}") from exc

    garment_ids = result.get("garment_ids", [])
    trace = [{"tool": s["tool"], "args": s["args"]} for s in result.get("steps", [])]
    db.add(StylistMessage(session_id=session.id, role="user", content=body.message))
    db.add(
        StylistMessage(
            session_id=session.id, role="assistant", content=result["reply"], garment_ids=garment_ids, tool_trace=trace
        )
    )
    updates = result.get("memory_updates") or {}
    if any(updates.values()):
        memory = dict(session.context_memory or {})
        for key, values in updates.items():
            merged = list(dict.fromkeys([*memory.get(key, []), *values]))
            memory[key] = merged[-20:]
        session.context_memory = memory
    await db.commit()
    return ChatOut(
        session_id=session.id,
        reply=result["reply"],
        recommended_garments=await _cards(db, garment_ids),
        tools_used=[t["tool"] for t in trace],
    )


@router.get("/sessions", response_model=list[SessionOut])
async def sessions(user: CurrentUser, db: DB):
    rows = await db.scalars(
        select(StylistSession).where(StylistSession.user_id == user.id).order_by(StylistSession.updated_at.desc()).limit(50)
    )
    return [SessionOut(id=s.id, title=s.title, updated_at=s.updated_at) for s in rows]


@router.get("/sessions/{session_id}", response_model=list[MessageOut])
async def session_messages(session_id: uuid.UUID, user: CurrentUser, db: DB):
    session = await db.scalar(
        select(StylistSession).where(StylistSession.id == session_id, StylistSession.user_id == user.id)
    )
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found.")
    msgs = await db.scalars(
        select(StylistMessage).where(StylistMessage.session_id == session.id).order_by(StylistMessage.created_at)
    )
    return [
        MessageOut(role=m.role, content=m.content, garments=await _cards(db, m.garment_ids), created_at=m.created_at)
        for m in msgs
    ]


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: uuid.UUID, user: CurrentUser, db: DB):
    session = await db.scalar(
        select(StylistSession).where(StylistSession.id == session_id, StylistSession.user_id == user.id)
    )
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found.")
    await db.delete(session)
    await db.commit()
