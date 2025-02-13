#!/usr/bin/env python
from fasthtml.common import *
import logging
import os
import bcrypt
import secrets
from datetime import datetime
from models import users
from routes import auth, feedback, payments, admin
from pages import (
    how_it_works_page,
    generate_themed_page,
    faq_page,
    privacy_policy_page,
    landing_page
)
from utils import beforeware

# Configure logging
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_admin_user():
    """Create admin user if it doesn't exist"""
    admin_email = os.environ.get("ADMIN_USERNAME")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    
    if not (admin_email and admin_password):
        return
        
    try:
        users[admin_email]
        logger.info("Admin user already exists")
    except Exception:
        logger.info("Creating admin user")
        users.insert({
            "id": secrets.token_hex(16),
            "first_name": "Admin",
            "email": admin_email,
            "role": "Administrator",
            "company": "Feedback to Me",
            "team": "Admin",
            "created_at": datetime.now(),
            "pwd": bcrypt.hashpw(admin_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
            "is_confirmed": True,
            "is_admin": True,
            "credits": 999999
        })
        logger.info("Admin user created successfully")

def create_app():
    """Create and configure the FastHTML application"""
    app, rt = fast_app(
        before=beforeware,
        hdrs=(
            MarkdownJS(),
            Link(rel='stylesheet', href='/static/styles.css', type='text/css')
        ),
        exception_handlers={
            HTTPException: lambda req, exc: Response(
                content="",
                status_code=exc.status_code,
                headers=exc.headers
            )
        }
    )
    
    # Create admin user
    create_admin_user()
    
    # Register route modules
    auth.register_routes(app)
    feedback.register_routes(app)
    payments.register_routes(app)
    admin.register_routes(app)
    
    # Register static pages
    @app.get("/")
    def get_home(req):
        return generate_themed_page(landing_page, auth=req.scope.get("auth"))
    
    @app.get("/how-it-works")
    def get_how_it_works(req):
        return generate_themed_page(how_it_works_page, auth=req.scope.get("auth"))
    
    @app.get("/faq")
    def get_faq():
        return faq_page()
    
    @app.get("/privacy-policy")
    def get_privacy(req):
        return generate_themed_page(privacy_policy_page, auth=req.scope.get("auth"))
    
    return app

if __name__ == "__main__":
    app = create_app()
    serve(port=8080)
