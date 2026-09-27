"""Test harness: real PostgreSQL (pgvector) + Redis, Celery in eager mode, local encrypted storage.

Requires the services from docker-compose (or local installs). Override with TEST_DATABASE_URL,
TEST_MIGRATION_DATABASE_URL and TEST_REDIS_URL.
"""

import os
import tempfile
import uuid

TMP = tempfile.mkdtemp(prefix="lookbook-test-")
os.environ.update(
    {
        "ENVIRONMENT": "test",
        "DATABASE_URL": os.getenv(
            "TEST_DATABASE_URL", "postgresql+psycopg://lookbook_app:app_dev_pw@localhost:5432/lookbook_test"
        ),
        "MIGRATION_DATABASE_URL": os.getenv(
            "TEST_MIGRATION_DATABASE_URL",
            "postgresql+psycopg://lookbook_owner:owner_dev_pw@localhost:5432/lookbook_test",
        ),
        "REDIS_URL": os.getenv("TEST_REDIS_URL", "redis://localhost:6379/15"),
        "MOCK_MODE": "true",
        "STORAGE_BACKEND": "local",
        "LOCAL_STORAGE_DIR": TMP,
        "CELERY_EAGER": "true",
        "SECRET_KEY": "test-secret-key-that-is-long-enough-1234567890",
        "APP_URL": "http://localhost:3000",
        "API_URL": "http://testserver",
        "RATE_AUTH_PER_15MIN": "50",
        "TURNSTILE_SECRET_KEY": "",
    }
)

import io  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

ORIGIN = "http://localhost:3000"


@pytest.fixture(scope="session", autouse=True)
def database():
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")

    import asyncio

    from scripts.seed_catalog import main as seed

    asyncio.run(seed(False))
    from app.db.session import reset_engines

    reset_engines()  # the seed ran on its own event loop
    yield


@pytest.fixture(scope="session")
def app_client(database):
    from app.core.redis import sync_redis
    from app.main import app

    sync_redis().flushdb()
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from app.core.redis import sync_redis

    for key in sync_redis().scan_iter("rate_limit:*"):
        sync_redis().delete(key)
    yield


class Api:
    """Browser-like client: keeps cookies and echoes the CSRF token like the frontend does."""

    def __init__(self, client: TestClient):
        self.c = client
        self.c.cookies.clear()
        self.csrf = self.c.get("/api/v1/auth/csrf").json()["csrf_token"]

    def _h(self, extra=None):
        return {"X-CSRF-Token": self.csrf, "Origin": ORIGIN, **(extra or {})}

    def get(self, url, **kw):
        return self.c.get(url, **kw)

    def post(self, url, json=None, headers=None, **kw):
        return self.c.post(url, json=json, headers=self._h(headers), **kw)

    def put(self, url, **kw):
        return self.c.put(url, headers=self._h(kw.pop("headers", None)), **kw)

    def delete(self, url, **kw):
        return self.c.delete(url, headers=self._h(), **kw)


@pytest.fixture
def api(app_client):
    return Api(app_client)


def unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:10]}@example.com"


PASSWORD = "correct horse battery staple"


@pytest.fixture
def user(api):
    email = unique_email()
    r = api.post("/api/v1/auth/signup", {"email": email, "password": PASSWORD, "full_name": "Test User"})
    assert r.status_code == 201, r.text
    return {"email": email, **r.json()}


def portrait_bytes(size=(600, 800), exif_gps=False) -> bytes:
    img = Image.new("RGB", size, (120, 140, 160))
    buf = io.BytesIO()
    if exif_gps:
        exif = Image.Exif()
        exif[0x8825] = {1: "N", 2: (31.0, 30.0, 0.0)}  # GPSInfo
        img.save(buf, format="JPEG", exif=exif)
    else:
        img.save(buf, format="JPEG")
    return buf.getvalue()


def upload_photo(api: Api, data: bytes | None = None) -> dict:
    data = data or portrait_bytes()
    api.post("/api/v1/account/consent", {"granted": True})
    r = api.post(
        "/api/v1/media/presign-upload",
        {"file_name": "me.jpg", "mime_type": "image/jpeg", "file_size_bytes": len(data)},
    )
    assert r.status_code == 200, r.text
    ticket = r.json()
    up = ticket["upload"]
    path = up["url"].replace("http://testserver", "")
    assert up["method"] == "PUT"
    r2 = api.c.put(path, content=data, headers=up["headers"])
    assert r2.status_code == 204, r2.text
    r3 = api.post(f"/api/v1/media/{ticket['asset_id']}/confirm")
    return {"status": r3.status_code, **(r3.json() if r3.status_code == 200 else {"detail": r3.json()})}
