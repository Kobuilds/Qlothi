from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Qlothi API is running."}

def test_analyze_endpoint():
    request_data = {"image_url": "https://i.pinimg.com/originals/placeholder.jpg"}
    response = client.post("/analyze", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "items" in data
    assert len(data["items"]) == 2
