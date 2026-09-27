import io
import time
from pathlib import Path

from PIL import Image

from tests.conftest import ORIGIN, TMP, Api, portrait_bytes, unique_email, upload_photo, PASSWORD


def _garment_id(api, q="navy blazer") -> str:
    return api.get("/api/v1/garments", params={"q": q}).json()[0]["id"]


def _wait(api, task_id: str, timeout=15) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        t = api.get(f"/api/v1/try-on/tasks/{task_id}").json()
        if t["status"] in ("COMPLETED", "FAILED"):
            return t
        time.sleep(0.2)
    raise AssertionError("task did not finish")


# --- uploads --------------------------------------------------------------------------------------


def test_upload_requires_consent(api, user):
    r = api.post("/api/v1/media/presign-upload", {"file_name": "a.jpg", "mime_type": "image/jpeg", "file_size_bytes": 100})
    assert r.status_code == 403


def test_upload_validates_and_strips_metadata(api, user):
    photo = upload_photo(api, portrait_bytes(exif_gps=True))
    assert photo["status"] == 200 and photo["width"] == 600
    data = api.get(photo["url"].replace("http://testserver", "")).content
    assert Image.open(io.BytesIO(data)).getexif().get(0x8825) is None  # GPS gone


def test_upload_rejects_disguised_files(api, user):
    bad = upload_photo(api, b"#!/bin/sh\necho pwned\n" * 20)
    assert bad["status"] == 400


def test_upload_ticket_enforces_type_and_size(api, user):
    api.post("/api/v1/account/consent", {"granted": True})
    assert api.post("/api/v1/media/presign-upload", {"file_name": "a.gif", "mime_type": "image/gif", "file_size_bytes": 10}).status_code == 415
    assert api.post("/api/v1/media/presign-upload", {"file_name": "a.jpg", "mime_type": "image/jpeg", "file_size_bytes": 50_000_000}).status_code == 413
    ticket = api.post("/api/v1/media/presign-upload", {"file_name": "a.jpg", "mime_type": "image/jpeg", "file_size_bytes": 10}).json()
    path = ticket["upload"]["url"].replace("http://testserver", "")
    assert api.c.put(path, content=b"x", headers={"Content-Type": "image/png"}).status_code == 415
    assert api.c.put(path[:-4] + "abcd", content=b"x", headers={"Content-Type": "image/jpeg"}).status_code == 403


def test_stored_files_are_encrypted_at_rest(api, user):
    photo = upload_photo(api)
    files = list((Path(TMP) / "objects" / "raw").rglob("*.jpg"))
    assert files and all(b"\xff\xd8\xff" not in f.read_bytes()[:200] for f in files)
    assert photo["status"] == 200


# --- try-on pipeline ------------------------------------------------------------------------------


def test_tryon_with_catalog_garment_streams_progress(api, app_client, user):
    photo = upload_photo(api)
    r = api.post("/api/v1/try-on/execute", {"user_photo_id": photo["id"], "garment_id": _garment_id(api)})
    assert r.status_code == 202, r.text
    task = _wait(api, r.json()["task_id"])
    assert task["status"] == "COMPLETED" and task["progress"] == 100 and task["adapter"] == "mock"
    img = api.get(task["result_url"].replace("http://testserver", ""))
    assert img.status_code == 200 and img.content[:4] == b"RIFF"  # webp

    with app_client.websocket_connect(f"/api/v1/ws/tasks/{task['task_id']}", headers={"origin": ORIGIN}) as ws:
        snap = ws.receive_json()
    assert snap["type"] == "snapshot" and snap["status"] == "COMPLETED" and snap["result_url"]


def test_tryon_from_prompt_uses_outfit_interpreter(api, user):
    photo = upload_photo(api)
    r = api.post(
        "/api/v1/try-on/execute",
        {"user_photo_id": photo["id"], "prompt": "a sleek black turtleneck with a tailored navy blazer, in front of a Ferrari"},
    )
    task = _wait(api, r.json()["task_id"])
    assert task["status"] == "COMPLETED"
    types = {g["type"] for g in task["outfit_spec"]["garments"]}
    assert {"turtleneck", "blazer"} <= types and "ferrari" in task["outfit_spec"]["scene"]


def test_tryon_requires_garment_or_prompt(api, user):
    photo = upload_photo(api)
    assert api.post("/api/v1/try-on/execute", {"user_photo_id": photo["id"]}).status_code == 422


def test_tryon_rate_limited(api, user):
    photo = upload_photo(api)
    gid = _garment_id(api)
    codes = [api.post("/api/v1/try-on/execute", {"user_photo_id": photo["id"], "garment_id": gid}).status_code for _ in range(7)]
    assert codes[:5] == [202] * 5 and 429 in codes


def test_users_cannot_see_each_others_data(app_client):
    alice = Api(app_client)
    alice.post("/api/v1/auth/signup", {"email": unique_email(), "password": PASSWORD})
    photo = upload_photo(alice)
    task_id = alice.post("/api/v1/try-on/execute", {"user_photo_id": photo["id"], "garment_id": _garment_id(alice)}).json()["task_id"]
    _wait(alice, task_id)

    bob = Api(app_client)
    bob.post("/api/v1/auth/signup", {"email": unique_email(), "password": PASSWORD})
    bob.post("/api/v1/account/consent", {"granted": True})
    assert bob.get(f"/api/v1/try-on/tasks/{task_id}").status_code == 404
    assert bob.post("/api/v1/try-on/execute", {"user_photo_id": photo["id"], "garment_id": _garment_id(bob)}).status_code == 404
    assert bob.post("/api/v1/looks", {"task_id": task_id}).status_code == 404
    assert bob.delete(f"/api/v1/media/photos/{photo['id']}").status_code == 404


# --- catalog, stylist, wardrobe -------------------------------------------------------------------


def test_catalog_vector_search_ranks_relevant_items(api, user):
    results = api.get("/api/v1/garments", params={"q": "warm camel wool overcoat"}).json()
    assert results[0]["slug"] == "camel-overcoat"
    assert results[0]["similarity"] > results[-1]["similarity"]


def test_stylist_agent_uses_tools_and_persists_session(api, user):
    r = api.post("/api/v1/stylist/chat", {"message": "What should I wear to a mehndi? Something festive."})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "search_catalog" in body["tools_used"] and "search_style_notes" in body["tools_used"]
    assert 1 <= len(body["recommended_garments"]) <= 4
    follow = api.post("/api/v1/stylist/chat", {"session_id": body["session_id"], "message": "Something warmer?"})
    assert follow.status_code == 200
    history = api.get(f"/api/v1/stylist/sessions/{body['session_id']}").json()
    assert [m["role"] for m in history] == ["user", "assistant", "user", "assistant"]


def test_stylist_weather_tool_degrades_gracefully(api, user):
    r = api.post("/api/v1/stylist/chat", {"message": "Outfit for a chilly evening walk in Lahore"})
    assert r.status_code == 200 and "get_local_weather" in r.json()["tools_used"]


def test_wardrobe_save_list_delete(api, user):
    photo = upload_photo(api)
    task = _wait(api, api.post("/api/v1/try-on/execute", {"user_photo_id": photo["id"], "garment_id": _garment_id(api)}).json()["task_id"])
    look = api.post("/api/v1/looks", {"task_id": task["task_id"], "collection": "Wedding"}).json()
    assert look["title"] == "Tailored Blazer" and look["image_url"]
    assert [lk["id"] for lk in api.get("/api/v1/looks", params={"collection": "Wedding"}).json()] == [look["id"]]
    assert api.delete(f"/api/v1/looks/{look['id']}").status_code == 204
    assert api.get("/api/v1/looks").json() == []


# --- privacy & live ------------------------------------------------------------------------------


def test_withdrawing_consent_deletes_media(api, user):
    upload_photo(api)
    assert api.get("/api/v1/media/photos").json()
    api.post("/api/v1/account/consent", {"granted": False})
    assert api.get("/api/v1/media/photos").json() == []
    assert not list((Path(TMP) / "objects" / "raw" / user["id"]).rglob("*.jpg"))


def test_export_and_delete_account(api, user):
    api.post("/api/v1/stylist/chat", {"message": "interview outfit"})
    export = api.get("/api/v1/account/export").json()
    assert export["account"]["email"] == user["email"] and export["stylist_conversations"]
    assert api.delete("/api/v1/account").status_code == 204
    assert api.get("/api/v1/auth/me").status_code == 401


def test_live_token_mock_without_key(api, user):
    body = api.post("/api/v1/live/token").json()
    assert body["mock"] is True and body["model"] == "lucy-vton-latest"


def test_widget_token_checks_merchant_origin(app_client):
    app_client.cookies.clear()
    ok = app_client.post(
        "/api/v1/live/widget-token",
        headers={"Origin": ORIGIN, "X-Lookbook-Key": "pk_demo_northwind", "X-Lookbook-Host": ORIGIN},
    )
    assert ok.status_code == 200 and ok.json()["mock"] is True
    wrong_host = app_client.post(
        "/api/v1/live/widget-token",
        headers={"Origin": ORIGIN, "X-Lookbook-Key": "pk_demo_northwind", "X-Lookbook-Host": "https://copycat.example"},
    )
    assert wrong_host.status_code == 403
    bad_key = app_client.post("/api/v1/live/widget-token", headers={"Origin": ORIGIN, "X-Lookbook-Key": "pk_nope"})
    assert bad_key.status_code == 403
    policy = app_client.get("/api/v1/live/frame-policy/pk_demo_northwind").json()
    assert policy["allowed_origins"] == [ORIGIN]


def test_retention_purge_removes_old_portraits(api, user):
    from sqlalchemy import text

    from app.db.session import sync_session
    from app.workers.tasks import purge_expired_data

    photo = upload_photo(api)
    with sync_session() as db:
        db.execute(text("update user_photos set created_at = now() - interval '30 days' where id=:i"), {"i": photo["id"]})
    counts = purge_expired_data()
    assert counts["photos"] >= 1
    assert all(p["id"] != photo["id"] for p in api.get("/api/v1/media/photos").json())
