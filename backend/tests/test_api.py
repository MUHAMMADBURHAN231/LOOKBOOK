import io
import os
import tempfile

os.environ["MOCK_MODE"] = "true"
os.environ["STORAGE_DIR"] = tempfile.mkdtemp(prefix="lookbook-test-")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.main import app  # noqa: E402
from app.services import generator, knowledge  # noqa: E402
from app.services.interpreter import interpret_offline  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _photo(size=(600, 800)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (120, 140, 160)).save(buf, format="JPEG")
    return buf.getvalue()


def test_health_reports_mock(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["mock"] is True


def test_offline_interpreter_parses_demo_prompt():
    spec = interpret_offline(
        "Wearing a sleek black turtleneck with a tailored navy blazer, aviator sunglasses, "
        "standing in front of a Ferrari"
    )
    by_type = {g.type: g for g in spec.garments}
    assert by_type["turtleneck"].color == "black"
    assert by_type["blazer"].color == "navy" and by_type["blazer"].fit == "tailored"
    assert "aviator sunglasses" in spec.accessories
    assert spec.scene == "in front of a ferrari"


def test_offline_interpreter_streetwear():
    spec = interpret_offline("Streetwear — oversized hoodie, cargo pants, Jordan 4s")
    types = {g.type: g.category for g in spec.garments}
    assert types == {"hoodie": "upper_body", "cargo pants": "lower_body"}
    assert spec.footwear == "Jordan sneakers"
    assert "streetwear" in spec.style_tags


def test_vton_garment_selection_prefers_full_body():
    spec = interpret_offline("traditional sherwani with gold embroidery and white trousers")
    picked = generator._pick_vton_garments(spec)
    assert [g.type for g in picked] == ["sherwani"]


def test_generate_requires_consent(client):
    r = client.post(
        "/api/generate",
        data={"description": "a red hoodie"},
        files={"photo": ("me.jpg", _photo(), "image/jpeg")},
    )
    assert r.status_code == 400


def test_generate_rejects_non_image(client):
    r = client.post(
        "/api/generate",
        data={"description": "a red hoodie", "consent": "true"},
        files={"photo": ("me.jpg", b"not an image", "image/jpeg")},
    )
    assert r.status_code == 400


def test_generate_save_and_delete_look(client):
    r = client.post(
        "/api/generate",
        data={"description": "Full astronaut suit on the moon", "consent": "true"},
        files={"photo": ("me.jpg", _photo(), "image/jpeg")},
    )
    assert r.status_code == 200, r.text
    gen = r.json()
    assert gen["mock"] is True
    assert client.get(gen["image_url"]).status_code == 200

    # Reuse the stored photo without re-uploading.
    source = gen["source_url"].rsplit("/", 1)[1]
    r2 = client.post(
        "/api/generate",
        data={"description": "a white linen shirt", "consent": "true", "source_file": source},
    )
    assert r2.status_code == 200, r2.text

    r = client.post("/api/looks", json={"generation_id": gen["id"], "collection": "Space"})
    assert r.status_code == 201
    look = r.json()
    assert look["title"].startswith("Full astronaut suit")

    looks = client.get("/api/looks", params={"collection": "Space"}).json()
    assert [l["id"] for l in looks] == [look["id"]]

    assert client.delete(f"/api/looks/{look['id']}").status_code == 204
    assert client.get("/api/looks").json() == []


def test_source_file_path_traversal_rejected(client):
    r = client.post(
        "/api/generate",
        data={"description": "a red hoodie", "consent": "true", "source_file": "../lookbook.db"},
    )
    assert r.status_code == 400


def test_knowledge_search_finds_desi_wedding():
    titles = [d.title for d in knowledge.search("what should I wear to a mehndi")]
    assert titles[0] == "Pakistani / South Asian wedding events"


def test_stylist_chat_returns_suggestions(client):
    r = client.post(
        "/api/stylist/chat",
        json={"messages": [{"role": "user", "content": "What should I wear to a wedding?"}]},
    )
    body = r.json()
    assert r.status_code == 200
    assert 1 <= len(body["suggestions"]) <= 4
    assert body["sources"]


def test_delete_all_data(client):
    client.post(
        "/api/generate",
        data={"description": "a red hoodie", "consent": "true"},
        files={"photo": ("me.jpg", _photo(), "image/jpeg")},
    )
    assert client.delete("/api/data").status_code == 204
    assert client.get("/api/looks").json() == []
