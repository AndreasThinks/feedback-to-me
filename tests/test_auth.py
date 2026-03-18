import pytest
import sys
import os
from pathlib import Path

# Add parent directory to path to import main
sys.path.insert(0, str(Path(__file__).parent.parent))

from starlette.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
from main import app

@pytest.fixture
def client():
    return TestClient(app)

def _set_oauth_state(client):
    """Helper: hit /auth/google with mocked client to set oauth_state in session, return the state value."""
    mock_client = MagicMock()
    mock_client.login_link.return_value = "https://accounts.google.com/o/oauth2/auth?client_id=test"
    with patch('main._google_oauth_configured', True), \
         patch('main._create_google_client', return_value=mock_client):
        resp = client.get("/auth/google", follow_redirects=False)
    # Extract state param from the redirect (it's also stored in session by the route)
    # We need to read it from session, but since TestClient manages cookies we can
    # just mock _create_google_client for the callback and pass the state from the login_link call.
    # The actual state is set in the session via sess["oauth_state"] inside the route.
    # We'll use a different approach: patch secrets.token_urlsafe to control the state value.
    return resp

def _callback_with_state(client, mock_retr_info_return, state_value="test_state_123"):
    """Helper: initiate OAuth flow with controlled state, then call callback with matching state."""
    mock_login_client = MagicMock()
    mock_login_client.login_link.return_value = f"https://accounts.google.com/o/oauth2/auth?state={state_value}"

    mock_callback_client = MagicMock()
    mock_callback_client.retr_info.return_value = mock_retr_info_return

    # Patch secrets.token_urlsafe to return a known state value
    with patch('main._google_oauth_configured', True), \
         patch('main.secrets.token_urlsafe', return_value=state_value):
        # Step 1: initiate login to set oauth_state in session
        with patch('main._create_google_client', return_value=mock_login_client):
            client.get("/auth/google", follow_redirects=False)

        # Step 2: call callback with matching state
        with patch('main._create_google_client', return_value=mock_callback_client):
            return client.get(
                f"/auth/callback?code=test_auth_code&state={state_value}",
                follow_redirects=False
            )

# ==========================================
# OAuth Tests
# ==========================================

class TestOAuthGoogleLogin:
    """Test suite for Google OAuth login initiation"""

    def test_google_login_redirects_when_configured(self, client):
        """Test that /auth/google redirects to Google when OAuth is configured"""
        mock_client = MagicMock()
        mock_client.login_link.return_value = "https://accounts.google.com/o/oauth2/auth?client_id=test"

        with patch('main._google_oauth_configured', True), \
             patch('main._create_google_client', return_value=mock_client):
            response = client.get("/auth/google", follow_redirects=False)

            assert response.status_code == 303
            assert "google.com" in response.headers["location"]

    def test_google_login_error_when_not_configured(self, client):
        """Test that /auth/google returns error when OAuth is not configured"""
        with patch('main._google_oauth_configured', False):
            response = client.get("/auth/google")

            assert response.status_code == 200
            assert b"OAuth Error" in response.content or b"not configured" in response.content

    def test_google_login_handles_exception(self, client):
        """Test that /auth/google handles exceptions gracefully"""
        mock_client = MagicMock()
        mock_client.login_link.side_effect = Exception("OAuth error")

        with patch('main._google_oauth_configured', True), \
             patch('main._create_google_client', return_value=mock_client):
            response = client.get("/auth/google")

            assert response.status_code == 200
            assert b"OAuth Error" in response.content or b"Failed to initiate" in response.content


class TestOAuthCallback:
    """Test suite for Google OAuth callback handling"""

    def test_callback_creates_new_user(self, client):
        """Test that OAuth callback creates a new user for unknown email"""
        response = _callback_with_state(client, {
            "email": "newuser@example.com",
            "given_name": "New",
            "sub": "google_user_123"
        })

        # Should redirect to dashboard after successful login
        assert response.status_code == 303
        assert response.headers["location"] == "/dashboard"

    def test_callback_links_existing_user(self, client):
        """Test that OAuth callback links OAuth to existing user with same email"""
        from models import users
        import secrets
        from datetime import datetime
        import bcrypt

        test_email = "existing@example.com"

        # Clean up any existing test user
        try:
            users.delete(test_email)
        except:
            pass

        # Create user
        users.insert({
            "id": secrets.token_hex(16),
            "first_name": "Existing",
            "email": test_email,
            "role": None,
            "company": None,
            "team": None,
            "created_at": datetime.now(),
            "pwd": bcrypt.hashpw("password123".encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
            "is_confirmed": True,
            "credits": 5
        })

        response = _callback_with_state(client, {
            "email": test_email,
            "given_name": "Existing",
            "sub": "google_user_456"
        })

        assert response.status_code == 303
        assert response.headers["location"] == "/dashboard"

        # Verify OAuth fields were updated
        user = users[test_email]
        assert user.oauth_provider == "google"
        assert user.oauth_id == "google_user_456"

        # Cleanup
        try:
            users.delete(test_email)
        except:
            pass

    def test_callback_handles_missing_email(self, client):
        """Test that OAuth callback handles missing email gracefully"""
        response = _callback_with_state(client, {
            "given_name": "Test",
            "sub": "google_user_789"
        })

        assert response.status_code == 200
        assert b"OAuth Error" in response.content or b"email" in response.content.lower()

    def test_callback_handles_missing_user_id(self, client):
        """Test that OAuth callback handles missing Google user ID gracefully"""
        response = _callback_with_state(client, {
            "email": "test@example.com",
            "given_name": "Test"
        })

        assert response.status_code == 200
        assert b"OAuth Error" in response.content or b"Failed to retrieve" in response.content

    def test_callback_error_when_not_configured(self, client):
        """Test that OAuth callback returns error when OAuth is not configured"""
        with patch('main._google_oauth_configured', False):
            response = client.get("/auth/callback?code=test_auth_code&state=foo")

            assert response.status_code == 200
            assert b"OAuth Error" in response.content or b"not configured" in response.content

    def test_callback_handles_api_exception(self, client):
        """Test that OAuth callback handles API exceptions gracefully"""
        mock_login_client = MagicMock()
        mock_login_client.login_link.return_value = "https://accounts.google.com/o/oauth2/auth?state=test_state"

        mock_callback_client = MagicMock()
        mock_callback_client.retr_info.side_effect = Exception("API Error")

        state_value = "test_state_err"
        with patch('main._google_oauth_configured', True), \
             patch('main.secrets.token_urlsafe', return_value=state_value):
            with patch('main._create_google_client', return_value=mock_login_client):
                client.get("/auth/google", follow_redirects=False)
            with patch('main._create_google_client', return_value=mock_callback_client):
                response = client.get(f"/auth/callback?code=test_auth_code&state={state_value}")

        assert response.status_code == 200
        assert b"OAuth Error" in response.content or b"error occurred" in response.content.lower()

    def test_callback_rejects_mismatched_state(self, client):
        """Test that OAuth callback rejects requests with mismatched CSRF state"""
        mock_login_client = MagicMock()
        mock_login_client.login_link.return_value = "https://accounts.google.com/o/oauth2/auth?state=real_state"

        with patch('main._google_oauth_configured', True), \
             patch('main.secrets.token_urlsafe', return_value="real_state"):
            with patch('main._create_google_client', return_value=mock_login_client):
                client.get("/auth/google", follow_redirects=False)

            # Send callback with wrong state
            response = client.get("/auth/callback?code=test_auth_code&state=wrong_state")

        assert response.status_code == 200
        assert b"OAuth Error" in response.content or b"invalid request" in response.content.lower()

    def test_callback_sets_session_correctly(self, client):
        """Test that OAuth callback sets session correctly after successful login"""
        response = _callback_with_state(client, {
            "email": "sessiontest@example.com",
            "given_name": "Session",
            "sub": "google_user_session"
        })

        assert response.status_code == 303
        # Session should be set (check cookies)
        assert "session" in response.cookies or len(response.cookies) > 0

    def test_callback_auto_confirms_oauth_users(self, client):
        """Test that OAuth users are automatically confirmed"""
        from models import users

        test_email = "autoconfirm@example.com"

        # Clean up
        try:
            users.delete(test_email)
        except:
            pass

        response = _callback_with_state(client, {
            "email": test_email,
            "given_name": "Auto",
            "sub": "google_user_confirm"
        })

        assert response.status_code == 303

        # Verify user is confirmed
        user = users[test_email]
        assert user.is_confirmed == True
        assert user.oauth_provider == "google"

        # Cleanup
        try:
            users.delete(test_email)
        except:
            pass

    def test_callback_gives_starting_credits(self, client):
        """Test that new OAuth users receive starting credits"""
        from models import users
        from config import STARTING_CREDITS

        test_email = "credits@example.com"

        # Clean up
        try:
            users.delete(test_email)
        except:
            pass

        response = _callback_with_state(client, {
            "email": test_email,
            "given_name": "Credits",
            "sub": "google_user_credits"
        })

        assert response.status_code == 303

        # Verify user has starting credits
        user = users[test_email]
        assert user.credits == STARTING_CREDITS

        # Cleanup
        try:
            users.delete(test_email)
        except:
            pass


class TestOAuthRedirectURI:
    """Test suite for redirect_uri generation"""

    def test_redirect_uri_with_base_url(self):
        """Test that redirect_uri is generated correctly when BASE_URL is set"""
        from main import generate_external_link

        with patch.dict(os.environ, {"BASE_URL": "example.com"}):
            result = generate_external_link("auth/callback")
            assert result == "https://example.com/auth/callback"

    def test_redirect_uri_without_base_url(self):
        """Test that redirect_uri is generated correctly when BASE_URL is not set"""
        from main import generate_external_link

        with patch.dict(os.environ, {}, clear=True):
            result = generate_external_link("auth/callback")
            assert result == "/auth/callback"

    def test_redirect_uri_preserves_http_protocol(self):
        """Test that redirect_uri preserves http:// for local dev"""
        from main import generate_external_link

        with patch.dict(os.environ, {"BASE_URL": "http://localhost:8080"}):
            result = generate_external_link("auth/callback")
            assert result == "http://localhost:8080/auth/callback"

    def test_redirect_uri_preserves_https_protocol(self):
        """Test that redirect_uri preserves https:// without duplication"""
        from main import generate_external_link

        with patch.dict(os.environ, {"BASE_URL": "https://example.com"}):
            result = generate_external_link("auth/callback")
            assert result == "https://example.com/auth/callback"
            assert result.count("https://") == 1


class TestOAuthUIButtons:
    """Test suite for OAuth UI buttons"""

    def test_login_page_has_google_button(self, client):
        """Test that login page includes Google OAuth button"""
        response = client.get("/login-form")

        assert response.status_code == 200
        assert b"Sign in with Google" in response.content or b"google" in response.content.lower()
        assert b"/auth/google" in response.content

    def test_get_started_page_has_google_button(self, client):
        """Test that get-started page includes Google OAuth button"""
        response = client.get("/get-started")

        assert response.status_code == 200
        assert b"Sign in with Google" in response.content or b"google" in response.content.lower()
        assert b"/auth/google" in response.content


class TestPasswordLoginOAuthUser:
    """Test that OAuth-only users cannot log in via password"""

    def test_oauth_user_password_login_rejected(self, client):
        """Test that an OAuth-only user (empty pwd) is rejected at password login"""
        from models import users
        import secrets as stdlib_secrets
        from datetime import datetime

        test_email = "oauthonly@example.com"

        # Clean up
        try:
            users.delete(test_email)
        except:
            pass

        # Create OAuth-only user with empty password
        users.insert({
            "id": stdlib_secrets.token_hex(16),
            "first_name": "OAuth",
            "email": test_email,
            "role": None,
            "company": None,
            "team": None,
            "created_at": datetime.now(),
            "pwd": "",
            "is_confirmed": True,
            "credits": 5,
            "oauth_provider": "google",
            "oauth_id": "google_123"
        })

        response = client.post("/login", data={"email": test_email, "pwd": "anything"})

        # Should get the error message, not a crash
        assert response.status_code == 200

        # Cleanup
        try:
            users.delete(test_email)
        except:
            pass
