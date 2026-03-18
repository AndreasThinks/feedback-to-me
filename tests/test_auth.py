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

# ==========================================
# OAuth Tests
# ==========================================

class TestOAuthGoogleLogin:
    """Test suite for Google OAuth login initiation"""
    
    def test_google_login_redirects_when_configured(self, client):
        """Test that /auth/google redirects to Google when OAuth is configured"""
        # Mock the google_client to be available
        with patch('main.google_client') as mock_client:
            mock_client.login_link.return_value = "https://accounts.google.com/o/oauth2/auth?client_id=test"
            
            response = client.get("/auth/google", follow_redirects=False)
            
            assert response.status_code == 303
            assert "google.com" in response.headers["location"]
    
    def test_google_login_error_when_not_configured(self, client):
        """Test that /auth/google returns error when OAuth is not configured"""
        with patch('main.google_client', None):
            response = client.get("/auth/google")
            
            assert response.status_code == 200
            assert b"OAuth Error" in response.content or b"not configured" in response.content
    
    def test_google_login_handles_exception(self, client):
        """Test that /auth/google handles exceptions gracefully"""
        with patch('main.google_client') as mock_client:
            mock_client.login_link.side_effect = Exception("OAuth error")
            
            response = client.get("/auth/google")
            
            assert response.status_code == 200
            assert b"OAuth Error" in response.content or b"Failed to initiate" in response.content


class TestOAuthCallback:
    """Test suite for Google OAuth callback handling"""
    
    def test_callback_creates_new_user(self, client):
        """Test that OAuth callback creates a new user for unknown email"""
        with patch('main.google_client') as mock_client:
            # Mock the OAuth response
            mock_client.retr_info.return_value = {
                "email": "newuser@example.com",
                "given_name": "New",
                "sub": "google_user_123"
            }
            
            response = client.get(
                "/auth/callback?code=test_auth_code",
                follow_redirects=False
            )
            
            # Should redirect to dashboard after successful login
            assert response.status_code == 303
            assert response.headers["location"] == "/dashboard"
    
    def test_callback_links_existing_user(self, client):
        """Test that OAuth callback links OAuth to existing user with same email"""
        # First create a user with password
        from models import users
        import secrets
        from datetime import datetime
        import bcrypt
        
        test_email = "existing@example.com"
        
        # Clean up any existing test user
        try:
            existing = users[test_email]
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
        
        with patch('main.google_client') as mock_client:
            mock_client.retr_info.return_value = {
                "email": test_email,
                "given_name": "Existing",
                "sub": "google_user_456"
            }
            
            response = client.get(
                "/auth/callback?code=test_auth_code",
                follow_redirects=False
            )
            
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
        with patch('main.google_client') as mock_client:
            # Mock response without email
            mock_client.retr_info.return_value = {
                "given_name": "Test",
                "sub": "google_user_789"
            }
            
            response = client.get("/auth/callback?code=test_auth_code")
            
            assert response.status_code == 200
            assert b"OAuth Error" in response.content or b"email" in response.content.lower()
    
    def test_callback_handles_missing_user_id(self, client):
        """Test that OAuth callback handles missing Google user ID gracefully"""
        with patch('main.google_client') as mock_client:
            # Mock response without sub (user ID)
            mock_client.retr_info.return_value = {
                "email": "test@example.com",
                "given_name": "Test"
            }
            
            response = client.get("/auth/callback?code=test_auth_code")
            
            assert response.status_code == 200
            assert b"OAuth Error" in response.content or b"Failed to retrieve" in response.content
    
    def test_callback_error_when_not_configured(self, client):
        """Test that OAuth callback returns error when OAuth is not configured"""
        with patch('main.google_client', None):
            response = client.get("/auth/callback?code=test_auth_code")
            
            assert response.status_code == 200
            assert b"OAuth Error" in response.content or b"not configured" in response.content
    
    def test_callback_handles_api_exception(self, client):
        """Test that OAuth callback handles API exceptions gracefully"""
        with patch('main.google_client') as mock_client:
            mock_client.retr_info.side_effect = Exception("API Error")
            
            response = client.get("/auth/callback?code=test_auth_code")
            
            assert response.status_code == 200
            assert b"OAuth Error" in response.content or b"error occurred" in response.content.lower()
    
    def test_callback_sets_session_correctly(self, client):
        """Test that OAuth callback sets session correctly after successful login"""
        with patch('main.google_client') as mock_client:
            mock_client.retr_info.return_value = {
                "email": "sessiontest@example.com",
                "given_name": "Session",
                "sub": "google_user_session"
            }
            
            response = client.get(
                "/auth/callback?code=test_auth_code",
                follow_redirects=False
            )
            
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
        
        with patch('main.google_client') as mock_client:
            mock_client.retr_info.return_value = {
                "email": test_email,
                "given_name": "Auto",
                "sub": "google_user_confirm"
            }
            
            response = client.get(
                "/auth/callback?code=test_auth_code",
                follow_redirects=False
            )
            
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
        
        with patch('main.google_client') as mock_client:
            mock_client.retr_info.return_value = {
                "email": test_email,
                "given_name": "Credits",
                "sub": "google_user_credits"
            }
            
            response = client.get(
                "/auth/callback?code=test_auth_code",
                follow_redirects=False
            )
            
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
    
    def test_redirect_uri_strips_protocol(self):
        """Test that redirect_uri strips protocol from BASE_URL if present"""
        from main import generate_external_link
        
        with patch.dict(os.environ, {"BASE_URL": "https://example.com"}):
            result = generate_external_link("auth/callback")
            assert result == "https://example.com/auth/callback"
            assert result.count("https://") == 1  # Should only appear once


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
