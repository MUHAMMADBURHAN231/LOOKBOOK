import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, update

from app.api.deps import DB, CurrentSession, CurrentUser, clear_session_cookie, client_ip, create_session, set_cookie
from app.core.config import get_settings
from app.core.email import send_email
from app.core.rate_limit import check_rate_limit
from app.core.security import (
    hash_password,
    needs_rehash,
    new_token,
    password_problem,
    token_hash,
    verify_password,
)
from app.core.turnstile import verify_human
from app.db.models import AuthSession, PasswordResetToken, User

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger(__name__)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    biometric_consent_granted: bool
    created_at: datetime


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)
    full_name: str = Field(default="", max_length=128)
    turnstile_token: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)
    turnstile_token: str | None = None


class ForgotIn(BaseModel):
    email: EmailStr
    turnstile_token: str | None = None


class ResetIn(BaseModel):
    token: str = Field(min_length=20, max_length=128)
    new_password: str = Field(max_length=128)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(max_length=128)


class SessionOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    last_seen_at: datetime
    user_agent: str | None
    current: bool


def _user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        email=u.email,
        full_name=u.full_name,
        biometric_consent_granted=u.biometric_consent_granted,
        created_at=u.created_at,
    )


async def _limit_auth(request: Request, action: str, email: str = "") -> None:
    s = get_settings()
    ip = client_ip(request)
    await check_rate_limit(f"auth:{action}:ip:{ip}", s.rate_auth_per_15min, 900)
    if email:
        await check_rate_limit(f"auth:{action}:email:{email.lower()}", s.rate_auth_per_15min, 900)


@router.get("/csrf")
async def csrf(response: Response) -> dict:
    """Issue the double-submit CSRF token. The frontend echoes it in X-CSRF-Token."""
    token = new_token(24)
    set_cookie(response, get_settings().csrf_cookie_name, token, http_only=False, max_age=86400 * 7)
    return {"csrf_token": token}


@router.post("/signup", response_model=UserOut, status_code=201)
async def signup(body: SignupIn, request: Request, response: Response, db: DB):
    await _limit_auth(request, "signup")
    await verify_human(body.turnstile_token, client_ip(request))
    if problem := password_problem(body.password, body.email):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
    exists = await db.scalar(select(User.id).where(func.lower(User.email) == body.email.lower()))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    user = User(
        email=body.email.lower(),
        hashed_password=hash_password(body.password),
        full_name=body.full_name.strip() or None,
    )
    db.add(user)
    await db.flush()
    await create_session(db, user, request, response)
    return _user_out(user)


@router.post("/login", response_model=UserOut)
async def login(body: LoginIn, request: Request, response: Response, db: DB):
    await _limit_auth(request, "login", body.email)
    await verify_human(body.turnstile_token, client_ip(request))
    user = await db.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
    # verify_password runs a full hash even when the user is missing (no timing oracle).
    if not verify_password(body.password, user.hashed_password if user else None) or not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect.")
    if needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(body.password)
    # Always a fresh session on login (prevents session fixation).
    await create_session(db, user, request, response)
    return _user_out(user)


@router.post("/logout", status_code=204)
async def logout(found: CurrentSession, response: Response, db: DB):
    _, session = found
    await db.execute(
        update(AuthSession).where(AuthSession.id == session.id).values(revoked_at=datetime.now(timezone.utc))
    )
    await db.commit()
    clear_session_cookie(response)


@router.post("/logout-all", status_code=204)
async def logout_all(user: CurrentUser, response: Response, db: DB):
    await _revoke_all(db, user.id)
    await db.commit()
    clear_session_cookie(response)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return _user_out(user)


@router.get("/sessions", response_model=list[SessionOut])
async def sessions(found: CurrentSession, db: DB):
    user, current = found
    now = datetime.now(timezone.utc)
    rows = await db.scalars(
        select(AuthSession)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
            AuthSession.absolute_expires_at > now,
            AuthSession.idle_expires_at > now,
        )
        .order_by(AuthSession.last_seen_at.desc())
    )
    return [
        SessionOut(
            id=s.id,
            created_at=s.created_at,
            last_seen_at=s.last_seen_at,
            user_agent=s.user_agent,
            current=s.id == current.id,
        )
        for s in rows
    ]


@router.delete("/sessions/{session_id}", status_code=204)
async def revoke_session(session_id: uuid.UUID, user: CurrentUser, db: DB):
    result = await db.execute(
        update(AuthSession)
        .where(AuthSession.id == session_id, AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found.")


@router.post("/password/forgot", status_code=202)
async def forgot_password(body: ForgotIn, request: Request, db: DB) -> dict:
    """Always answers the same way, so it can't be used to discover which emails have accounts."""
    await _limit_auth(request, "forgot", body.email)
    await verify_human(body.turnstile_token, client_ip(request))
    user = await db.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
    if user and user.is_active:
        s = get_settings()
        now = datetime.now(timezone.utc)
        # Only the newest link works: earlier unused links are invalidated.
        await db.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
            .values(used_at=now)
        )
        token = new_token()
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=token_hash(token),
                expires_at=now + timedelta(minutes=s.password_reset_ttl_minutes),
            )
        )
        await db.commit()
        link = f"{s.app_url.rstrip('/')}/reset-password#token={token}"
        await send_email(
            user.email,
            "Reset your LOOKBOOK password",
            f"Someone asked to reset the password for this account.\n\n"
            f"Reset it here (the link works once and expires in {s.password_reset_ttl_minutes} minutes):\n"
            f"{link}\n\nIf this wasn't you, you can ignore this email.",
        )
    return {"detail": "If that email has an account, a reset link is on its way."}


@router.post("/password/reset", status_code=204)
async def reset_password(body: ResetIn, request: Request, db: DB):
    await _limit_auth(request, "reset")
    now = datetime.now(timezone.utc)
    # Atomically claim the token: a second use (or a race) finds used_at already set.
    user_id = await db.scalar(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == token_hash(body.token),
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .values(used_at=now)
        .returning(PasswordResetToken.user_id)
    )
    if not user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This reset link is invalid or has expired.")
    user = await db.get(User, user_id)
    if problem := password_problem(body.new_password, user.email):
        await db.rollback()  # keep the link usable so they can try a stronger password
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
    user.hashed_password = hash_password(body.new_password)
    await _revoke_all(db, user.id)  # a reset signs out every device
    await db.commit()


@router.post("/password/change", status_code=204)
async def change_password(body: ChangePasswordIn, found: CurrentSession, db: DB):
    user, current = found
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect.")
    if problem := password_problem(body.new_password, user.email):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
    user.hashed_password = hash_password(body.new_password)
    # Keep this device signed in, sign out the rest.
    await db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.id != current.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await db.commit()


async def _revoke_all(db, user_id: uuid.UUID) -> None:
    await db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
