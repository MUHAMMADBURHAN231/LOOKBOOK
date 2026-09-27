"""Relational schema (PostgreSQL 16 + pgvector). Mirrors the technical specification, section 9."""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

EMBEDDING_DIM = 768


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(128))
    biometric_consent_granted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    biometric_consent_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (Index("uq_users_email_lower", func.lower(email), unique=True),)


class AuthSession(Base):
    """Server-side login session. Only a SHA-256 of the cookie token is stored."""

    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = _created()
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(256))
    ip_prefix: Mapped[str | None] = mapped_column(String(64))  # truncated IP, never the full address


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()


class UserPhoto(Base):
    __tablename__ = "user_photos"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    mime_type: Mapped[str] = mapped_column(String(32), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    aspect_ratio: Mapped[float | None] = mapped_column(Numeric(5, 2))
    pose_keypoints: Mapped[dict | None] = mapped_column(JSONB)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = _created()


class Garment(Base):
    __tablename__ = "garments"

    id: Mapped[uuid.UUID] = _uuid_pk()
    slug: Mapped[str] = mapped_column(String(96), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    brand: Mapped[str | None] = mapped_column(String(128))
    color: Mapped[str | None] = mapped_column(String(64))
    season: Mapped[str | None] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price_cents: Mapped[int | None] = mapped_column(Integer)
    image_key: Mapped[str] = mapped_column(String(512), nullable=False)
    flatlay_mask_key: Mapped[str | None] = mapped_column(String(512))
    embedding = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        Index(
            "idx_garments_embedding",
            embedding,
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class TryOnTask(Base):
    __tablename__ = "tryon_tasks"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # SET NULL: retention may delete the raw portrait while the saved result lives on.
    user_photo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_photos.id", ondelete="SET NULL")
    )
    garment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("garments.id", ondelete="SET NULL")
    )
    custom_prompt: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32), default="upper_body", nullable=False)
    enhance_face: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    pipeline: Mapped[str] = mapped_column(String(16), default="auto", nullable=False)
    adapter: Mapped[str | None] = mapped_column(String(32))
    outfit_spec: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", index=True, nullable=False)
    stage: Mapped[str] = mapped_column(String(64), default="INIT", nullable=False)
    progress_percentage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    result_storage_key: Mapped[str | None] = mapped_column(String(512))
    execution_time_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    garment: Mapped["Garment | None"] = relationship(lazy="joined")


class Look(Base):
    """A try-on result saved to the user's wardrobe."""

    __tablename__ = "looks"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    tryon_task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tryon_tasks.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    collection: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    created_at: Mapped[datetime] = _created()

    task: Mapped[TryOnTask] = relationship(lazy="joined")


class StylistSession(Base):
    __tablename__ = "stylist_sessions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(128), default="New consultation", nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    context_memory: Mapped[dict] = mapped_column(
        JSONB,
        default=lambda: {"liked_colors": [], "disliked_cuts": [], "occasions": []},
        nullable=False,
    )
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class StylistMessage(Base):
    __tablename__ = "stylist_messages"

    id: Mapped[uuid.UUID] = _uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stylist_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    garment_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    tool_trace: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    created_at: Mapped[datetime] = _created()


class Merchant(Base):
    """A store embedding the live try-on widget. The publishable key is public by design;
    protection comes from origin allowlists, CSP frame-ancestors and rate/budget limits."""

    __tablename__ = "merchants"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    publishable_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    allowed_origins: Mapped[list[str]] = mapped_column(ARRAY(String(255)), default=list, nullable=False)
    daily_session_limit: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = _created()
