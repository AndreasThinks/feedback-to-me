import pytest
from starlette.testclient import TestClient
from main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_register_new_user(client):
    response = client.post("/register", data={
        "email": "test@example.com",
        "role": "user",
        "company": "TestCo",
        "team": "QA"
    })
    assert response.status_code == 303
    assert "auth" in client.cookies

def test_magic_link_flow(client):
    # Test magic link generation
    response = client.get("/magic/link?email=test@example.com")
    assert response.status_code == 200
    assert "/feedback/submit/" in response.text
    
    # Test magic link expiration
    # ... would need mock for datetime testing
