from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "1.0.0"


def test_generate_unauthorized_missing_header():
    response = client.post("/api/generate", json={"prompt": "Hello"})
    assert response.status_code == 401
    assert "Invalid or missing API key" in response.json()["detail"]


def test_generate_authorized_success():
    response = client.post(
        "/api/generate",
        headers={"X-API-Key": "demo-key-123"},
        json={"prompt": "What is FastAPI Cloud?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "model" in data
    assert "provider" in data


def test_generate_stream_unauthorized():
    response = client.post("/api/generate/stream", json={"prompt": "Stream test"})
    assert response.status_code == 401


def test_generate_stream_authorized():
    response = client.post(
        "/api/generate/stream",
        headers={"X-API-Key": "demo-key-123"},
        json={"prompt": "Count 1 to 3"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    assert "data: " in response.text


def test_frontend_colocation():
    response = client.get("/")
    assert response.status_code == 200
    assert "FastAPI Cloud LLM Assistant" in response.text
