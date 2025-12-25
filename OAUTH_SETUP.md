# Google OAuth Setup Guide

This guide explains how to implement Google OAuth authentication for the Feedback-to-Me application.

## What Was Implemented

Google OAuth has been added to allow users to:
- Sign in with their Google account (no password needed)
- Link their Google account to an existing email/password account
- Auto-confirmed accounts (no email verification needed for OAuth users)

## Changes Made

### 1. Database Schema (`models.py`)
Added OAuth fields to the User model:
```python
oauth_provider: Optional[str] = None  # 'google', 'github', etc.
oauth_id: Optional[str] = None        # Provider's unique user ID
```

### 2. Configuration (`config.py`)
Added OAuth configuration variables:
```python
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
```

### 3. Environment Variables (`.env.example`)
Added required environment variables:
```
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

### 4. Routing (`utils.py`)
Updated beforeware to skip OAuth routes:
```python
r'/auth/.*',  # OAuth routes
```

### 5. OAuth Routes (`main.py`)
Added three key components:

#### OAuth Client Initialization
```python
google_client = GoogleAppClient(
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    code="",
    scope="openid email profile"
)
```

#### OAuth Routes
- `/auth/google` - Initiates Google OAuth flow
- `/auth/callback` - Handles OAuth callback and user creation/linking

## Google Cloud Console Setup

### Step 1: Create OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to **APIs & Services** > **Credentials**
4. Click **Create Credentials** > **OAuth 2.0 Client ID**
5. Configure OAuth consent screen if prompted:
   - User Type: External (for public use)
   - Add app name, support email, and developer contact
   - Add scopes: `openid`, `email`, `profile`
   - Add test users if in development

### Step 2: Configure OAuth Client

1. Application type: **Web application**
2. Name: `Feedback to Me`
3. **Authorized redirect URIs**: Add these URLs:
   - Development: `http://localhost:8080/auth/callback`
   - Production: `https://your-domain.com/auth/callback`
   - Production alt: `https://feedback-to.me/auth/callback`

4. Click **Create**
5. Copy the **Client ID** and **Client Secret**

### Step 3: Update Environment Variables

Add to your `.env` file:
```
GOOGLE_CLIENT_ID=123456789-abcdefghijklmnop.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-client-secret-here
```

## How It Works

### OAuth Flow

1. User clicks "Sign in with Google" button (needs to be added to UI)
2. App redirects to `/auth/google`
3. Google OAuth flow begins
4. User authorizes the app
5. Google redirects back to `/auth/callback` with authorization code
6. App exchanges code for user info (email, name, Google ID)
7. App either:
   - Creates new user if email doesn't exist
   - Links OAuth to existing user if email exists
8. User is logged in and redirected to dashboard

### User Creation/Linking Logic

```python
# Check if user exists by email
try:
    user = users[email]
    # Existing user - link OAuth if not already linked
    if not user.oauth_provider:
        user.oauth_provider = "google"
        user.oauth_id = google_id
        users.update(user)
except Exception:
    # New user - create with OAuth
    user = users.insert({
        "email": email,
        "first_name": given_name,
        "oauth_provider": "google",
        "oauth_id": google_id,
        "is_confirmed": True,  # Auto-confirmed
        "pwd": "",  # No password for OAuth users
        # ... other fields ...
    })
```

## Adding the UI Button

To complete the implementation, add a "Sign in with Google" button to the login page in `pages.py`:

```python
# In login_form or login_or_register_page:
A(
    Button("Sign in with Google", cls="google-oauth-btn"),
    href="/auth/google"
)
```

Or using Google's official button:
```html
<a href="/auth/google">
    <div class="g-signin-button">
        <div class="google-icon">
            <svg><!-- Google Icon SVG --></svg>
        </div>
        <span>Sign in with Google</span>
    </div>
</a>
```

## Security Features

1. **CSRF Protection**: OAuth state parameter (handled by FastHTML OAuth library)
2. **Auto-confirmation**: OAuth users are automatically confirmed (no email verification needed)
3. **Secure tokens**: Google handles all token management
4. **Account linking**: Existing users can link Google account
5. **No password storage**: OAuth users don't have passwords stored

## Testing

### Local Testing
1. Update `.env` with your credentials
2. Add `http://localhost:8080/auth/callback` to Google Console
3. Run the app: `python main.py`
4. Navigate to the login page
5. Click "Sign in with Google"
6. Authorize the app
7. Verify you're logged in

### Production Testing
1. Update redirect URI in Google Console to production URL
2. Set production environment variables
3. Test the full flow on your live site

## Troubleshooting

### Common Issues

1. **"Redirect URI mismatch"**
   - Ensure the callback URL in Google Console exactly matches your app
   - Check for http vs https
   - Check for trailing slashes

2. **"Google OAuth not configured"**
   - Verify `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set
   - Check they're not empty strings
   - Restart the app after setting env vars

3. **"Failed to retrieve user information"**
   - Check OAuth scope includes `openid email profile`
   - Verify the consent screen is configured correctly
   - Check app logs for detailed error messages

4. **User not being created**
   - Check database permissions
   - Verify `STARTING_CREDITS` environment variable is set
   - Check logs for database errors

## Adding More OAuth Providers

The framework supports additional providers. To add GitHub, for example:

```python
# In main.py
from fasthtml.oauth import GitHubAppClient

github_client = GitHubAppClient(
    client_id=os.getenv("GITHUB_CLIENT_ID"),
    client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
    code="",
    scope="user:email"
)

@app.get("/auth/github")
def github_login(req):
    # Similar to google_login
    pass

@app.get("/auth/github/callback")
def github_callback(code: str, req, sess):
    # Similar to google_callback
    pass
```

## Notes

- OAuth users can still set a password later if needed (feature to be implemented)
- The `pwd` field for OAuth users is an empty string
- OAuth users are auto-confirmed (no email verification)
- The system tracks which provider was used via `oauth_provider` field
- Multiple OAuth providers can be added without conflicts

## Next Steps

1. Add "Sign in with Google" button to UI in `pages.py`
2. Test the OAuth flow end-to-end
3. Consider adding GitHub/Microsoft OAuth for more options
4. Add UI for users to link/unlink OAuth providers
5. Add option for OAuth users to set a password

## Resources

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [FastHTML OAuth Documentation](https://docs.fastht.ml/tutorials/oauth.html)
- [Google Cloud Console](https://console.cloud.google.com/)
