import os
import pytest
from starlette.testclient import TestClient
from main import app

client = TestClient(app)

def test_get_login():
    # Test that the login page returns a valid HTML form.
    response = client.get("/login")
    assert response.status_code == 200
    assert "Login" in response.text

def test_register_and_magic_link():
    # Simulate user registration. Form data is sent as a dict.
    reg_data = {
        "email": "test@example.com",
        "role": "employee",
        "company": "Acme Co.",
        "team": "Sales"
    }
    response = client.post("/register", data=reg_data)
    # Registration route should redirect.
    assert response.status_code in (302, 303)

    # Now, simulate getting the magic link.
    magic_response = client.get("/magic/link?email=test@example.com")
    assert magic_response.status_code == 200
    assert "Magic Link Generated" in magic_response.text

def test_feedback_submission_get_invalid():
    # Test that an invalid token returns an error message.
    response = client.get("/feedback/submit/invalidtoken")
    assert response.status_code == 200
    assert "Invalid or Expired Link" in response.text

def test_home_redirects_when_not_logged_in():
    # When not logged in, accessing "/" should trigger a redirect (by beforeware).
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 303)

# Additional tests could be added to simulate valid feedback submission, report generation, etc.

if __name__ == "__main__":
    pytest.main()
