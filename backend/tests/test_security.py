import email
import email.policy
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from app.core.logging import redact
from tests.conftest import ORIGIN, PASSWORD, TMP, Api, unique_email


def test_health_and_readiness(api):
    assert api.get("/healthz").json() == {"status": "ok"}
    body = api.get("/readyz").json()
    assert body["status"] == "ok", body


def test_security_headers(api):
    r = api.get("/api/v1/meta")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-request-id"]


def test_csrf_required_for_state_changes(app_client):
    app_client.cookies.clear()
    r = app_client.post("/api/v1/auth/login", json={"email": "a@b.co", "password": "x" * 12})
    assert r.status_code == 403
    assert "Security token" in r.json()["detail"]


def test_cross_origin_state_change_blocked(api):
    r = api.post("/api/v1/auth/login", {"email": "a@b.co", "password": "x" * 12}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_signup_rejects_weak_password(api):
    r = api.post("/api/v1/auth/signup", {"email": unique_email(), "password": "password123"})
    assert r.status_code == 422
    r = api.post("/api/v1/auth/signup", {"email": unique_email(), "password": "short"})
    assert r.status_code == 422


def test_signup_sets_hardened_session_cookie_and_hashes_password(api, app_client):
    email = unique_email()
    r = api.post("/api/v1/auth/signup", {"email": email, "password": PASSWORD})
    assert r.status_code == 201
    cookie = r.headers["set-cookie"]
    assert "lb_session=" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert api.get("/api/v1/auth/me").json()["email"] == email

    from app.db.session import sync_session

    with sync_session() as db:
        stored = db.execute(text("select hashed_password from users where email=:e"), {"e": email}).scalar()
        token_hashes = db.execute(text("select token_hash from auth_sessions s join users u on u.id=s.user_id where u.email=:e"), {"e": email}).scalars().all()
    assert stored.startswith("$argon2id$") and PASSWORD not in stored
    raw_token = app_client.cookies.get("lb_session")
    assert raw_token not in token_hashes  # only the SHA-256 is stored


def test_duplicate_signup_and_generic_login_errors(api, user):
    assert api.post("/api/v1/auth/signup", {"email": user["email"], "password": PASSWORD}).status_code == 409
    wrong = api.post("/api/v1/auth/login", {"email": user["email"], "password": "not the password"})
    unknown = api.post("/api/v1/auth/login", {"email": unique_email(), "password": "not the password"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]


def test_login_rotates_session_and_logout_revokes(api, app_client, user):
    first = app_client.cookies.get("lb_session")
    r = api.post("/api/v1/auth/login", {"email": user["email"], "password": PASSWORD})
    assert r.status_code == 200
    second = app_client.cookies.get("lb_session")
    assert first != second
    assert api.post("/api/v1/auth/logout").status_code == 204
    app_client.cookies.set("lb_session", second)
    assert api.get("/api/v1/auth/me").status_code == 401


def test_sessions_expire(api, user):
    from app.db.session import sync_session

    with sync_session() as db:
        db.execute(
            text("update auth_sessions set idle_expires_at=:t where user_id=:u"),
            {"t": datetime.now(timezone.utc) - timedelta(seconds=1), "u": user["id"]},
        )
    assert api.get("/api/v1/auth/me").status_code == 401


def test_login_rate_limited(api, user):
    codes = [
        api.post("/api/v1/auth/login", {"email": user["email"], "password": "wrong password!"}).status_code
        for _ in range(55)
    ]
    assert 429 in codes


def _latest_reset_token() -> str:
    outbox = Path(TMP) / "dev-outbox"
    msg = email.message_from_bytes(sorted(outbox.glob("*.eml"))[-1].read_bytes(), policy=email.policy.default)
    return re.search(r"#token=([\w-]+)", msg.get_content()).group(1)


def test_password_reset_is_single_use_and_revokes_sessions(app_client, user):
    device = Api(app_client)  # a second signed-in device
    device.post("/api/v1/auth/login", {"email": user["email"], "password": PASSWORD})
    device_cookie = app_client.cookies.get("lb_session")

    anon = Api(app_client)
    assert anon.post("/api/v1/auth/password/forgot", {"email": unique_email()}).status_code == 202
    assert anon.post("/api/v1/auth/password/forgot", {"email": user["email"]}).status_code == 202
    token = _latest_reset_token()
    new_pw = "a completely new passphrase"
    assert anon.post("/api/v1/auth/password/reset", {"token": token, "new_password": new_pw}).status_code == 204
    assert anon.post("/api/v1/auth/password/reset", {"token": token, "new_password": new_pw + "!"}).status_code == 400

    app_client.cookies.set("lb_session", device_cookie)
    assert app_client.get("/api/v1/auth/me").status_code == 401  # every session was revoked
    assert anon.post("/api/v1/auth/login", {"email": user["email"], "password": new_pw}).status_code == 200


def test_password_reset_link_expires(api, user):
    api.post("/api/v1/auth/password/forgot", {"email": user["email"]})
    token = _latest_reset_token()
    from app.db.session import sync_session

    with sync_session() as db:
        db.execute(text("update password_reset_tokens set expires_at=now() - interval '1 minute'"))
    r = api.post("/api/v1/auth/password/reset", {"token": token, "new_password": "another good passphrase"})
    assert r.status_code == 400


def test_only_latest_reset_link_works(api, user):
    api.post("/api/v1/auth/password/forgot", {"email": user["email"]})
    first = _latest_reset_token()
    api.post("/api/v1/auth/password/forgot", {"email": user["email"]})
    r = api.post("/api/v1/auth/password/reset", {"token": first, "new_password": "another good passphrase"})
    assert r.status_code == 400


def test_app_role_cannot_run_ddl():
    from app.db.session import sync_session

    with pytest.raises(Exception, match="must be owner"):
        with sync_session() as db:
            db.execute(text("DROP TABLE users"))


@pytest.mark.parametrize(
    "raw,leak",
    [
        ('{"password": "hunter2hunter2"}', "hunter2hunter2"),
        ("Authorization: Bearer abc.def.ghi-123", "abc.def.ghi-123"),
        ("api_key=AIzaSyA1234567890abcdefghijklmnopq", "AIzaSyA1234567890abcdefghijklmnopq"),
        ("card 4242 4242 4242 4242 charged", "4242 4242 4242 4242"),
        ("reset for jane.doe@example.com", "jane.doe"),
        ("token=r8_ABCDEFGHIJKLMNOPQRSTUVWXYZ12", "r8_ABCDEFGHIJKLMNOPQRSTUVWXYZ12"),
    ],
)
def test_log_redaction(raw, leak):
    assert leak not in redact(raw)


def test_production_refuses_unsafe_config(monkeypatch):
    from app.core.config import Settings

    with pytest.raises(ValueError, match="Unsafe production configuration"):
        Settings(environment="production", _env_file=None)


def test_websocket_rejects_foreign_origin(api, app_client, user):
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with app_client.websocket_connect(
            "/api/v1/ws/tasks/00000000-0000-0000-0000-000000000000", headers={"origin": "https://evil.example"}
        ) as ws:
            ws.receive_json()
    assert ORIGIN  # silence unused import when collected alone
