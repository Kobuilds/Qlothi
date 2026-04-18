import base64
from io import BytesIO
from PIL import Image
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_root_returns_status_page():
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Qlothi Backend API" in response.text


def test_analyze_rejects_garbage_base64():
    response = client.post("/analyze", json={"base64_image": "not-valid-base64!!!"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["items"] == []


def test_analyze_accepts_valid_image():
    buf = BytesIO()
    Image.new("RGB", (64, 64), color=(255, 255, 255)).save(buf, format="JPEG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    response = client.post("/analyze", json={"base64_image": b64})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["image_size"] == {"width": 64, "height": 64}
    assert isinstance(body["items"], list)
