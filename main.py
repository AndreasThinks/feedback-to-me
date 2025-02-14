#!/usr/bin/env python
from fasthtml.common import *
from datetime import datetime, timedelta
dev_mode = os.environ.get("DEV_MODE", "false").lower() == "true"
alpha_mode = os.environ.get("ALPHA_MODE", "true").lower() == "true"

import secrets, os
import bcrypt
import logging
from datetime import datetime
import json

# Configure logging based on environment variable
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


from models import password_reset_tokens_tb, feedback_themes_tb, feedback_submission_tb, users, feedback_process_tb, feedback_request_tb, FeedbackProcess, FeedbackRequest, Login, confirm_tokens_tb
from pages import how_it_works_page, generate_themed_page, faq_page, error_message, login_or_register_page, register_form, login_form, landing_page, navigation_bar_logged_out, navigation_bar_logged_in, footer_bar, privacy_policy_page, pricing_page

from llm_functions import convert_feedback_text_to_themes, generate_completed_feedback_report

from config import MINIMUM_SUBMISSIONS_REQUIRED, MAGIC_LINK_EXPIRY_DAYS, FEEDBACK_QUALITIES, STARTING_CREDITS, BASE_URL
from utils import beforeware, validate_email_format, validate_password_strength, validate_passwords_match

import requests
import math
import stripe
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")


from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# --------------------
# FastHTML App Setup
# --------------------
app, rt = fast_app(
    before=beforeware,
    hdrs=(
        MarkdownJS(),  # Allows rendering markdown in feedback text, if needed.
        Link(rel='stylesheet', href='/static/styles.css', type='text/css')
    ),
    htmlkw={'data-theme':'light'},
    exception_handlers={HTTPException: lambda req, exc: Response(content="", status_code=exc.status_code, headers=exc.headers)}
)

# Create admin user if it doesn't exist
admin_email = os.environ.get("ADMIN_USERNAME")
admin_password = os.environ.get("ADMIN_PASSWORD")

if admin_email and admin_password:
    try:
        admin_user = users[admin_email]
        logger.info("Admin user already exists")
    except Exception:
        logger.info("Creating admin user")
        admin_user = users.insert({
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
            "credits": 999999  # Large number of credits for admin
        })
        logger.info("Admin user created successfully")

limiter = Limiter(key_func=get_remote_address)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --------------------
# Helper Functions
# --------------------

def generate_external_link(url):
    """Find the base domain env var, if it exists, and return the link with the base domain as as a string"""
    base_domain = os.environ.get("BASE_URL")
    if base_domain:
        return f"https://{base_domain}/{url}"
    return url

def generate_magic_link(email: str, process_id: Optional[str] = None) -> str:
    """
    Generates a unique magic link token, stores it with expiry in the FeedbackRequest table, and returns the link.
    Optionally links it to a specific FeedbackProcess.
    """
    token = secrets.token_urlsafe()
    expiry = datetime.now() + timedelta(days=MAGIC_LINK_EXPIRY_DAYS)
    feedback_request_tb.insert({
        "token": token,
        "email": email,
        "process_id": process_id,
        "expiry": expiry,
    })
    return uri("new-feedback-form", token=token)

def send_feedback_email(recipient: str,  link: str, recipient_first_name: str = "", sender_first_name: str = "") -> bool:
    try:
        link = generate_external_link(link)
        with open("feedback_email_template.txt", "r") as f:
            template = f.read()
        filled_template = (
            template
            .replace("{link}", link)
            .replace("{recipient_first_name}", recipient_first_name)
            .replace("{sender_first_name}", sender_first_name)
        )

        endpoint = os.environ.get("SMTP2GO_EMAIL_ENDPOINT", "https://api.smtp2go.com/v3")
        api_key = os.environ.get("SMTP2GO_API_KEY")
        if not api_key:
            logger.error("SMTP2GO_API_KEY is missing.")
            return False

        payload = {
            "sender": "noreply@feedback-to.me",
            "to": [recipient],
            "subject": "Feedback Request from Feedback to Me",
            "text_body": filled_template
        }

        headers = {
            "Content-Type": "application/json",
            "X-Smtp2go-Api-Key": api_key
        }

        logger.info(f"Sending email to {recipient} using SMTP2GO with payload: {payload}")
        response = requests.post(endpoint.rstrip("/") + "/email/send", json=payload, headers=headers)

        if response.status_code == 200:
            result_json = response.json()
            succeeded = result_json.get("data", {}).get("succeeded", 0)
            if succeeded == 1:
                logger.info("Email sent successfully via SMTP2GO.")
                return True
            else:
                logger.error(f"SMTP2GO error: {result_json}")
                return False
        else:
            logger.error(f"Error sending email: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        logger.error(f"Exception during sending email for {recipient}: {str(e)}")
        return False

def send_password_reset_email(recipient: str, token: str, recipient_first_name: str = "") -> bool:
    """
    Sends an email with a password reset link containing the given token.
    """
    try:
        with open("password_reset_email_template.txt", "r") as f:
            template = f.read()
        link = generate_external_link(("reset-password") + f"/{token}")
        filled_template = (
            template
            .replace("{link}", link)
            .replace("{recipient_first_name}", recipient_first_name)
        )

        endpoint = os.environ.get("SMTP2GO_EMAIL_ENDPOINT", "https://api.smtp2go.com/v3")
        api_key = os.environ.get("SMTP2GO_API_KEY")
        if not api_key:
            logger.error("SMTP2GO_API_KEY is missing.")
            return False

        payload = {
            "sender": "noreply@feedback-to.me",
            "to": [recipient],
            "subject": "Password Reset Request",
            "text_body": filled_template
        }

        headers = {
            "Content-Type": "application/json",
            "X-Smtp2go-Api-Key": api_key
        }

        logger.info(f"Sending password reset email to {recipient}")
        response = requests.post(endpoint.rstrip("/") + "/email/send", json=payload, headers=headers)

        if response.status_code == 200:
            result_json = response.json()
            succeeded = result_json.get("data", {}).get("succeeded", 0)
            if succeeded == 1:
                logger.info("Password reset email sent successfully.")
                return True
            else:
                logger.error(f"SMTP2GO error sending password reset email: {result_json}")
                return False
        else:
            logger.error(f"Error sending password reset email: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Exception while sending password reset email to {recipient}: {str(e)}")
        return False

def send_confirmation_email(recipient: str, token: str, recipient_first_name: str = "", recipient_company: str = "") -> bool:
    """
    Sends an email with a confirmation link containing the given token.
    """
    try:
        with open("confirmation_email_template.txt", "r") as f:
            template = f.read()
        # We'll build a direct link to trigger /confirm-email?token=<token>
        link = generate_external_link(("confirm-email") + f"/{token}")
        filled_template = (
            template
            .replace("{link}", link)
            .replace("{recipient_first_name}", recipient_first_name)
            .replace("{recipient_company}", recipient_company)
        )

        endpoint = os.environ.get("SMTP2GO_EMAIL_ENDPOINT", "https://api.smtp2go.com/v3")
        api_key = os.environ.get("SMTP2GO_API_KEY")
        if not api_key:
            logger.error("SMTP2GO_API_KEY is missing.")
            return False

        payload = {
            "sender": "noreply@feedback-to.me",
            "to": [recipient],
            "subject": "Please Confirm Your Email Address",
            "text_body": filled_template
        }

        headers = {
            "Content-Type": "application/json",
            "X-Smtp2go-Api-Key": api_key
        }

        logger.info(f"Sending confirmation email to {recipient} with payload: {payload}")
        response = requests.post(endpoint.rstrip("/") + "/email/send", json=payload, headers=headers)

        if response.status_code == 200:
            result_json = response.json()
            succeeded = result_json.get("data", {}).get("succeeded", 0)
            if succeeded == 1:
                logger.info("Confirmation email sent successfully.")
                return True
            else:
                logger.error(f"SMTP2GO error sending confirmation email: {result_json}")
                return False
        else:
            logger.error(f"Error sending confirmation email: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Exception while sending confirmation email to {recipient}: {str(e)}")
        return False

# -----------------------
# static pages
# -----------------------

@app.get("/")
def get(req):
    return generate_themed_page(landing_page, auth=req.scope.get("auth"))


@app.get("/homepage")
def get(req):
    return generate_themed_page(landing_page, auth=req.scope.get("auth"))

@app.get("/how-it-works")
def get(req):
    return generate_themed_page(how_it_works_page, auth=req.scope.get("auth"))

@app.get("/faq")
def get():
    return faq_page()

@app.get("/privacy-policy")
def get(req):
    return generate_themed_page(privacy_policy_page, auth=req.scope.get("auth"))

@app.get("/pricing")
def get(req):
    return generate_themed_page(pricing_page, auth=req.scope.get("auth"))

@app.get("/get-started")
def get(req, sess):
    if "auth" in sess:
        return Redirect("/dashboard")
    return generate_themed_page(login_or_register_page, auth=req.scope.get("auth"))

# -----------------------
# User Registration and Login Pages
# -----------------------

@app.get("/login-or-register")
def get(req):
    return generate_themed_page(login_or_register_page, auth=req.scope.get("auth"))

@app.get("/login-form")
def get():
    return login_form

@limiter.limit("5/minute")
@app.post("/login")
def post_login(login: Login, request: Request, sess):
    print(login)
    logger.debug(f"Login attempt for email: {login.email}")
    try:
        u = users[login.email]
        logger.debug(f"User found: {login.email}")
    except Exception:
        logger.warning(f"Login failed - user not found: {login.email}")
        return error_message
    
    if not bcrypt.checkpw(login.pwd.encode("utf-8"), u.pwd.encode("utf-8")):
        logger.warning(f"Login failed - invalid password for user: {login.email}")
        return error_message
    
    # Check if user is confirmed
    if not u.is_confirmed:
        logger.warning(f"Login failed - user not confirmed: {login.email}")
        return Titled(
            "Email Not Confirmed",
            P("Please check your email for a confirmation link. You cannot log in until you confirm.")
        )

    sess["auth"] = u.id
    logger.info(f"User successfully logged in: {login.email}")
    return Redirect("/dashboard")

@rt("/logout")
def get_logout(sess):
    if "auth" in sess:
        auth_id = sess["auth"]
        del sess["auth"]
        logger.info(f"User logged out: {auth_id}")
    return RedirectResponse("/", status_code=303)

@app.get("/forgot-password")
def get_forgot_password():
    """Display the forgot password form"""
    form = Form(
        H2("Reset Password"),
        P("Enter your email address and we'll send you a link to reset your password."),
        Input(name="email", type="email", placeholder="Enter your email", required=True),
        Button("Send Reset Link", type="submit"),
        action="/send-reset-email",
        method="post"
    )
    return generate_themed_page(form, page_title="Reset Password")

@limiter.limit("3/hour")
@app.post("/send-reset-email")
def post_send_reset_email(email: str, request: Request):
    """Handle forgot password form submission"""
    logger.debug(f"Password reset requested for email: {email}")
    
    # Validate email format
    is_valid_email, email_msg = validate_email_format(email)
    if not is_valid_email:
        return Titled("Invalid Email", P(email_msg))
    

    # Check if user exists
    user = users[email]
    
    # Generate and store reset token
    token = secrets.token_urlsafe()
    expiry = datetime.now() + timedelta(hours=1)  # Token expires in 1 hour
    password_reset_tokens_tb.insert({
        "token": token,
        "email": email,
        "expiry": expiry,
        "is_used": False
    })
    
    # Send reset email
    if send_password_reset_email(email, token, user.first_name):
        return Titled(
            "Check Your Email",
            P("We've sent a password reset link to your email. The link will expire in 1 hour.")
        )
    else:
        return Titled("Error", P("Failed to send reset email. Please try again later."))
        


@app.get("/reset-password/{token}")
def get_reset_password(token: str):
    """Display the password reset form"""
    try:
        # Verify token exists and is valid
        reset_token = password_reset_tokens_tb[token]
        if reset_token.is_used:
            return Titled("Invalid Link", P("This password reset link has already been used."))
        
        expiry_datetime = reset_token.expiry if isinstance(reset_token.expiry, datetime) else datetime.fromisoformat(reset_token.expiry)
        if expiry_datetime < datetime.now():
            return Titled("Link Expired", P("This password reset link has expired. Please request a new one."))
        
        # Show password reset form
        form = Form(
            H2("Reset Your Password"),
            Input(name="pwd", type="password", placeholder="New password", required=True,
                  hx_post="/validate-password",
                  hx_trigger="keyup changed delay:300ms",
                  hx_target="#pwd-validation"),
            Div(id="pwd-validation"),
            Input(name="pwd_confirm", type="password", placeholder="Confirm new password", required=True,
                  hx_post="/validate-password-match",
                  hx_trigger="keyup changed delay:300ms",
                  hx_include="[name='pwd']",
                  hx_target="#pwd-match-validation"),
            Div(id="pwd-match-validation"),
            Button("Reset Password", type="submit"),
            action=f"/reset-password/{token}",
            method="post"
        )
        return generate_themed_page(form, page_title="Reset Password")
        
    except Exception:
        return Titled("Invalid Link", P("This password reset link is invalid or has expired."))

@app.post("/reset-password/{token}")
def post_reset_password(token: str, pwd: str, pwd_confirm: str):
    """Process password reset"""
    try:
        # Verify token exists and is valid
        reset_token = password_reset_tokens_tb[token]
        if reset_token.is_used:
            return Titled("Invalid Link", P("This password reset link has already been used."))
        
        expiry_datetime = reset_token.expiry if isinstance(reset_token.expiry, datetime) else datetime.fromisoformat(reset_token.expiry)
        if expiry_datetime < datetime.now():
            return Titled("Link Expired", P("This password reset link has expired. Please request a new one."))
        
        # Validate password strength
        score, issues = validate_password_strength(pwd)
        if score < 70:
            return Titled("Password Too Weak", 
                         P("Please choose a stronger password:"),
                         Ul(*(Li(issue) for issue in issues)))
        
        # Validate passwords match
        match, match_msg = validate_passwords_match(pwd, pwd_confirm)
        if not match:
            return Titled("Passwords Don't Match", P(match_msg))
        
        # Update user's password
        user = users[reset_token.email]
        user.pwd = bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        users.update(user)
        
        # Mark token as used
        reset_token.is_used = True
        password_reset_tokens_tb.update(reset_token, reset_token.token)
        
        logger.info(f"Password reset successful for user: {reset_token.email}")
        return Titled(
            "Password Reset Complete",
            P("Your password has been reset successfully. You can now log in with your new password."),
            A("Go to Login", href="/get-started", cls="button")
        )
        
    except Exception as e:
        logger.error(f"Error resetting password: {str(e)}")
        return Titled("Error", P("An error occurred while resetting your password."))

@app.get("/register")
def get(req):
    auth = req.scope.get("auth")
    if auth:
        logger.debug(f"Already logged in user ({auth}) accessing register page, redirecting to dashboard")
        return RedirectResponse("/dashboard", status_code=303)
    logger.debug("Serving registration form")
    return register_form

# -----------------------
# Routes: Validation
# -----------------------

@app.post("/validate-password")
def validate_password(pwd: str):
    """Validate password strength and return feedback"""
    score, issues = validate_password_strength(pwd)
    
    # Create progress bar color based on score
    color = "var(--pico-color-red)" if score < 40 else \
            "var(--pico-color-yellow)" if score < 70 else \
            "var(--pico-color-green)"
    
    return Article(
        Progress(value=str(score), max="100", id="pwd-strength", 
                style=f"color: {color}; background: {color}"),
        Div(
            *(Li(issue) for issue in issues) if issues else [P("Password strength is good", cls="success")],
            id="password-validation",
            role="alert",
            cls="error" if issues else "success"
        ),
    id="password-verification-status")

@app.post("/validate-registration-email")
def validate_registration_email(email: str):
    """Validate email format and availability for registration"""
    is_valid, message = validate_email_format(email)
    if not is_valid:
        return Div(message, id="email-validation", role="alert", cls="error")
    
    try:
        existing = users[email]
        return Div("Email already in use", id="email-validation", role="alert", cls="error")
    except Exception:
        return Div("Email is available", id="email-validation", role="alert", cls="success")

@app.post("/validate-email")
def validate_email(email: str):
    """Validate only email format"""
    is_valid, message = validate_email_format(email)
    if not is_valid:
        return Div(message, id="email-validation", role="alert", cls="error")
    return Div("Email format is valid", id="email-validation", role="alert", cls="success")

@app.post("/validate-password-match")
def validate_password_match(pwd: str, pwd_confirm: str):
    """Validate that passwords match"""
    match, message = validate_passwords_match(pwd, pwd_confirm)
    return Div(message, id="pwd-match-validation", role="alert", 
              cls="success" if match else "error")

@app.post("/validate-email-list")
def validate_email_list(emails: str):
    """Validate a list of emails, one per line"""
    invalid_emails = []
    for line in emails.splitlines():
        email = line.strip()
        if email:  # Only validate non-empty lines
            is_valid, _ = validate_email_format(email)
            if not is_valid:
                invalid_emails.append(email)
    
    if not invalid_emails:
        return Div("All emails are valid", id="email-validation", role="alert", cls="success")
    return Div(
        "Invalid email format:",
        Ul(*(Li(email) for email in invalid_emails)),
        id="email-validation",
        role="alert",
        cls="error"
    )

# -----------------------
# Routes: User Registration
# -----------------------
@limiter.limit("10/hour")
@app.post("/register-new-user")
def post_register(email: str, first_name:str, role: str, company: str, team: str, pwd: str, pwd_confirm: str, sess, request: Request):
    logger.debug(f"Registration attempt for email: {email}")
    if "auth" in sess:
        logger.debug("Clearing existing session auth")
        del sess["auth"]
    
    # Validate email format
    is_valid_email, email_msg = validate_email_format(email)
    if not is_valid_email:
        return Titled("Registration Failed", P(email_msg))
    
    # Validate password strength
    score, issues = validate_password_strength(pwd)
    if score < 70:  # Require a strong password
        return Titled("Registration Failed", 
                     P("Password is not strong enough:"),
                     Ul(*(Li(issue) for issue in issues)))
    
    # Validate passwords match
    match, match_msg = validate_passwords_match(pwd, pwd_confirm)
    if not match:
        return Titled("Registration Failed", P(match_msg))
    
    user_data = {
        "id": secrets.token_hex(16),
        "first_name": first_name,
        "email": email,
        "role": role,
        "company": company,
        "team": team,
        "created_at": datetime.now(),
        "pwd": bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
        "is_confirmed": False,
        "credits": int(STARTING_CREDITS)
    }
    try:
        existing = users[email]
        logger.warning(f"Registration failed - email already exists: {email}")
        return Titled("Registration Failed", P("That email is already in use."))
    except Exception:
        new_user = users.insert(user_data)
        logger.info(f"New user registered (unconfirmed): {email}")

        # Generate and store a new confirmation token
        token = secrets.token_urlsafe()
        expiry = datetime.now() + timedelta(days=7)
        confirm_tokens_tb.insert({
            "token": token,
            "email": email,
            "expiry": expiry,
            "is_used": False
        })
        if dev_mode:
            logger.warning("DEV_MODE is enabled; automatically confirming new user.")
            new_user.is_confirmed = True
            users.update(new_user)
        else:
            # Send them a confirmation link
            send_confirmation_email(email, token, first_name, company)

    return Titled(
        "Check Your Email",
        P("We've sent a confirmation link to your email. Please click it to confirm before logging in.")
    )

@app.get("/confirm-email/{token}")
def confirm_email(token: str):
    logger.debug(f"Confirm email attempt with token: {token}")
    try:
        ct = confirm_tokens_tb[token]
        if ct.is_used:
            logger.debug("Confirmation token already used.")
            return Titled("Already Used", P("That link has already been used."))
        expiry_datetime = ct.expiry if isinstance(ct.expiry, datetime) else datetime.fromisoformat(ct.expiry)
        if expiry_datetime < datetime.now():
            return Titled("Link Expired", P("Please request a new confirmation link."))

        user_entry = users[ct.email]
        if user_entry.is_confirmed:
            logger.debug("User is already confirmed.")
            return Titled("Already Confirmed", P("Your email is already confirmed."))

        # Mark user as confirmed
        user_entry.is_confirmed = True
        users.update(user_entry, ct.email)

        # Mark the token as used
        ct.is_used = True
        confirm_tokens_tb.update(ct, ct.token)

        logger.info(f"User {ct.email} confirmed email successfully.")
        return Titled("Email Confirmed", P("Thank you! Your email has been confirmed. You may now log in."))
    except Exception as e:
        logger.error(f"Error confirming email: {str(e)}")
        return Titled("Invalid Link", P("That confirmation link isn't valid or doesn't exist."))

@app.get("/buy-credits")
def buy_credits(req, sess):
    auth = req.scope.get("auth")
    if not auth:
        return RedirectResponse("/login", status_code=303)
    # Display a simple form for purchasing extra credits
    form = Form(
         Input(name="credits", type="number", min="1", placeholder="Number of credits"),
         Button("Buy Credits"),
         action="/create-checkout-session", method="post"
    )
    return Titled("Buy Credits", form)

@app.post("/create-checkout-session")
def create_checkout_session(req, sess, credits: int):
    auth = req.scope.get("auth")
    if not auth:
        return RedirectResponse("/login", status_code=303)
    from config import COST_PER_CREDIT_USD
    # Calculate total amount in cents
    amount = credits * COST_PER_CREDIT_USD * 100
    # Build success and cancel URLs using uri helper
    success_url = generate_external_link(uri("payment-success") + "?session_id={CHECKOUT_SESSION_ID}")
    cancel_url = generate_external_link(uri("payment-cancel"))
    checkout_session = stripe.checkout.Session.create(
         payment_method_types=["card"],
         line_items=[{
             "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": f"{credits} Extra Credit{'s' if credits > 1 else ''}"
                },
                "unit_amount": amount,
             },
             "quantity": 1,
         }],
         mode="payment",
         success_url=success_url,
         cancel_url=cancel_url,
         metadata={
             "credits": credits,
             "user_id": auth
         }
    )
    return RedirectResponse(checkout_session.url, status_code=303)

@app.get("/payment-success")
def payment_success(req, sess, session_id: str):
    try:
        # Validate session exists
        current_user_id = sess.get("auth")
        if not current_user_id:
            logger.error("Payment success accessed without valid session")
            return RedirectResponse("/login", status_code=303)

        session = stripe.checkout.Session.retrieve(session_id)
        credits = int(session.metadata.get("credits", 0))
        user_id = session.metadata.get("user_id")

        # Validate payment is for current user
        if not user_id or current_user_id != user_id:
            logger.error(f"User session {current_user_id} mismatch with payment user {user_id}")
            return Titled("Security Error", P("Invalid payment session detected"))

        # Only show success message, actual credit addition happens in webhook
        message = f"Payment successful! {credits} credits will be added to your account shortly."
        if user_id:
            user = users("id=?", (user_id,))[0]
            user.credits += credits
            users.update(user)
        return Titled("Payment Success", P(message), A("Go to Dashboard", href="/dashboard"))
    except Exception as e:
        logger.error(f"Error in payment success route: {str(e)}")
        return Titled("Error", P("Error processing payment."))


@app.get("/payment-cancel")
def payment_cancel():
    return Titled("Payment Cancelled", P("Your payment was cancelled."), A("Go back", href="/dashboard"))

# -----------------------
# Routes: Dashboard
# -----------------------
@app.get("/dashboard")
def get(req):
    auth = req.scope.get("auth")
    logger.debug(f"Dashboard accessed by user: {auth}")
    user = users("id=?", (auth,))[0]
    processes = feedback_process_tb("user_id=?", (auth,))
    logger.debug(f"Found {len(processes)} feedback processes")
    
    active_html = []
    completed_html = []
    for p in processes:
        if p.feedback_report:
            completed_html.append(p)
        else:
            active_html.append(p)

    dashboard_page_active = Container(
        H2(f"Hi {user.first_name}!"),
        P("Welcome to your dashboard. Here you can manage your feedback collection processes."),
        P(f"You have {user.credits} credits remaining"),
        Div(
            A(Button("Start New Feedback Collection"), href="/start-new-feedback-process", cls="collect-feedback-button"),
            A(Button("Buy More Credits"), href='/buy-credits'),
            cls="dashboard-buttons"
        ),
        Div(
            H3("Collecting responses"),
            *active_html or P("No active feedback collection processes.", cls="text-muted"),
        cls="report-section"),
        Div(
            H3("Report ready to generate"),
            P("No feedback ready for review.", cls="text-muted"),
        cls="report-section"),
        Div(
            H3("Completed reports"),
            *completed_html or P("No completed feedback reports.", cls="text-muted"),
        cls="report-section")
    )
    return generate_themed_page(dashboard_page_active, auth=auth, page_title="Your Dashboard")

# -----------------------
# Routes: New Feedback Process
# -----------------------

@app.post("/start-new-feedback-process/count")
def count_submissions(peers_emails: str = "", supervisors_emails: str = "", reports_emails: str = ""):
    # Count and validate emails in each textarea
    invalid_emails = []
    valid_count = 0
    
    for role, emails in [('peers', peers_emails), 
                        ('supervisors', supervisors_emails), 
                        ('reports', reports_emails)]:
        for line in emails.splitlines():
            email = line.strip()
            if email:
                is_valid, _ = validate_email_format(email)
                if is_valid:
                    valid_count += 1
                else:
                    invalid_emails.append(f"{email} ({role})")
    
    remaining = max(0, MINIMUM_SUBMISSIONS_REQUIRED - valid_count)
    
    # Create validation status content
    status_content = []
    if valid_count >= MINIMUM_SUBMISSIONS_REQUIRED:
        status_content.append(
            Div(
                Span("✅", cls="status-icon"),
                f"You have {valid_count} valid submission(s).",
                cls="status-line success"
            )
        )
    else:
        status_content.append(
            Div(
                Span("⚠️", cls="status-icon"),
                f"You currently have {valid_count} valid submission(s).",
                Div(f"Need {remaining} more to reach the minimum of {MINIMUM_SUBMISSIONS_REQUIRED}."),
                cls="status-line warning"
            )
        )
    
    if invalid_emails:
        status_content.append(
            Div(
                Div(
                    Span("❌", cls="status-icon"),
                    "Please fix the following invalid emails:",
                    cls="invalid-header"
                ),
                Ul(*(Li(email) for email in invalid_emails)),
                cls="invalid-list"
            )
        )
    
    # Button is disabled if we don't have enough valid emails
    button_disabled = valid_count < MINIMUM_SUBMISSIONS_REQUIRED or bool(invalid_emails)
    
    # Return both the message div and the submit button with appropriate state
    return (
        Div(*status_content, id="feedback-count-msg", cls="insufficient" if button_disabled else "sufficient", hx_swap_oob="true"),
        Div(
            Button("Begin collecting feedback", type="submit", cls="primary", id="submit-btn", 
                  disabled=button_disabled, aria_invalid=str(button_disabled).lower()),
            id="submit-container",
            hx_swap_oob="true"
        )
    )

@app.get("/start-new-feedback-process")
def get_new_feedback(req):
    auth = req.scope.get("auth")
    respondents_div = Div(
        Div(
            P(f"You'll need at least {MINIMUM_SUBMISSIONS_REQUIRED} total feedback submissions to generate your finalised report."),
            P("", id="feedback-count-msg"),
            cls="min-requirements"
        )
    )
    
    form = Form(
        Input(name='process_title', type='text', placeholder="Provide a short title for this process"),
        respondents_div,
        Div(
            H3("Peers"),
            Textarea(name="peers_emails", placeholder="Enter peer emails, one per line", rows=3,
                    hx_trigger="keyup changed delay:300ms",
                    hx_post="/start-new-feedback-process/count",
                    hx_include="[name='peers_emails'],[name='supervisors_emails'],[name='reports_emails']"),
            Div(cls="validation-result", 
                hx_post="/validate-email-list",
                hx_trigger="keyup changed delay:300ms from:previous",
                hx_include="[name='peers_emails']")
        ),
        Div(
            H3("Supervisors"),
            Textarea(name="supervisors_emails", placeholder="Enter supervisor emails, one per line", rows=3,
                    hx_trigger="keyup changed delay:300ms",
                    hx_post="/start-new-feedback-process/count",
                    hx_include="[name='peers_emails'],[name='supervisors_emails'],[name='reports_emails']"),
            Div(cls="validation-result",
                hx_post="/validate-email-list",
                hx_trigger="keyup changed delay:300ms from:previous",
                hx_include="[name='supervisors_emails']")
        ),
        Div(
            H3("Reports"),
            Textarea(name="reports_emails", placeholder="Enter report emails, one per line", rows=3,
                    hx_trigger="keyup changed delay:300ms",
                    hx_post="/start-new-feedback-process/count",
                    hx_include="[name='peers_emails'],[name='supervisors_emails'],[name='reports_emails']"),
            Div(cls="validation-result",
                hx_post="/validate-email-list",
                hx_trigger="keyup changed delay:300ms from:previous",
                hx_include="[name='reports_emails']")
        ),
        Div(
            H3("Select Qualities to be Graded On"),
            Div(
            *[Div(
                Input(name=f"quality_{q}", type="checkbox", value=q),
                Label(q)
              ) for q in FEEDBACK_QUALITIES],
           cls="qualities-checkboxes")
        ),
        Div(
            H3("Other Qualities (one per line)"),
            Textarea(name="custom_qualities", placeholder="Enter custom qualities, one per line", rows=2)
        ),
        Div(
            Button("Begin collecting feedback", type="submit", cls="primary", id="submit-btn"),
            id="submit-container"
        )
        , action="/create-new-feedback-process", method="post"
    )
    
    return generate_themed_page(form, auth=auth, page_title="Your Dashboard")

@app.post("/create-new-feedback-process")
def create_new_feedback_process(process_title : str, peers_emails: str, supervisors_emails: str, reports_emails: str, custom_qualities : str, sess, data: dict):
    logger.debug("create_new_feedback_process called with:")
    logger.debug(f"peers_emails: {peers_emails!r}")
    logger.debug(f"supervisors_emails: {supervisors_emails!r}")
    logger.debug(f"reports_emails: {reports_emails!r}")
    logger.debug(f"Additional form data: {data!r}")
    user_id = sess.get("auth")
    
    # Validate all emails
    invalid_emails = []
    for email_list, role in [(peers_emails, "peers"), (supervisors_emails, "supervisors"), (reports_emails, "reports")]:
        for line in email_list.splitlines():
            email = line.strip()
            if email:
                is_valid, message = validate_email_format(email)
                if not is_valid:
                    invalid_emails.append(f"{email} ({role}): {message}")
    
    if invalid_emails:
        return Titled(
            "Invalid Email Addresses",
            Container(
                P("Please correct the following email addresses:"),
                Ul(*(Li(email) for email in invalid_emails))
            )
        )
    
    peers = [line.strip() for line in peers_emails.splitlines() if line.strip()]
    supervisors = [line.strip() for line in supervisors_emails.splitlines() if line.strip()]
    reports = [line.strip() for line in reports_emails.splitlines() if line.strip()]
    
    # Calculate total feedback requests
    total_requests = len(peers) + len(supervisors) + len(reports)
    
    # Check if user has enough credits
    user = users("id=?", (user_id,))[0]
    if user.credits < total_requests:
        return Titled(
            "Insufficient Credits",
            Container(
                P(f"You need {total_requests} credits to send these feedback requests, but you only have {user.credits} credits."),
                P("Please reduce the number of feedback requests or purchase more credits.")
            )
        )
    
    # Deduct credits for each request
    user.credits -= total_requests
    users.update(user)
    selected_qualities = [q for q in FEEDBACK_QUALITIES if data.get(f"quality_{q}")]
    custom_qualities = [line.strip() for line in custom_qualities.splitlines() if line.strip()]

    if custom_qualities:
        selected_qualities.extend(custom_qualities)
    process_data = {
        "id": secrets.token_hex(8),
        "process_title" :  process_title,
        "user_id": user_id,
        "created_at": datetime.now(),
        "min_submissions_required": MINIMUM_SUBMISSIONS_REQUIRED,
        "qualities": selected_qualities,
        "feedback_count": 0,
        "feedback_report": None
    }
    fp = feedback_process_tb.insert(process_data)

    generated_process_id = fp.id
    # Create feedback requests for each role.
    for email in peers:
        link = generate_magic_link(email, process_id=process_data["id"])
        token = link.replace("new-feedback-form/token=", "")
        print('token:', token)
        feedback_request_tb.update({"user_type": "peer"}, token=token)
    for email in supervisors:
        link = generate_magic_link(email, process_id=process_data["id"])
        token = link.replace("new-feedback-form/token=", "")
        feedback_request_tb.update({"user_type": "supervisor"}, token=token)
    for email in reports:
        link = generate_magic_link(email, process_id=process_data["id"])
        token = link.replace("new-feedback-form/token=", "")
        feedback_request_tb.update({"user_type": "report"}, token=token)
    return RedirectResponse(f"/feedback-process/{generated_process_id}", status_code=303)

# -----------------------
# Routes: Existing Feedback Process
# -----------------------
@app.get("/feedback-process/{process_id}")
def get_report_status_page(process_id : str, req):
    try:
        process = feedback_process_tb[process_id]
    except Exception:
        logger.warning(f"Feedback process not found: {process_id}")
        return RedirectResponse("/dashboard", status_code=303)
    
    requests = feedback_request_tb("process_id=?", (process_id,))
    submissions = feedback_submission_tb("process_id=?", (process_id,))
    peer_submissions = feedback_request_tb("process_id=? AND user_type='peer' AND completed_at is not Null", (process_id,))
    print('peer_submissions:', peer_submissions)
    
    submission_counts = {
        "peer": len(feedback_request_tb("process_id=? AND user_type='peer' AND completed_at is not Null", (process_id,))),
        "supervisor": len(feedback_request_tb("process_id=? AND user_type='supervisor' AND completed_at is not Null", (process_id,))),
        "report": len(feedback_request_tb("process_id=? AND user_type='report' AND completed_at is not Null", (process_id,))),
    }
    
    total_submissions = sum(submission_counts.values())
    can_generate_report = (
        total_submissions >= process.min_submissions_required and
        not process.feedback_report
    )

    report_in_progress_text = "Your request for feedback has been created, along with a custom questionaire for each participant. Please email them each their custom link, or click the button below for us to email them on your behalf. "
    report_awaiting_generation_text = "You've received enough feedback to generate a report! Click the button when you're ready to create your report summary. "
    report_completed_text = "Your feedback process is complete, and your final report has been generated. "
    
    missing_text = None  # Default value

    if process.feedback_report:
        opening_text = report_completed_text
    elif can_generate_report:
        opening_text = report_awaiting_generation_text
    else:
        needed_submissions = max(process.min_submissions_required - total_submissions, 0)
        missing_text = f"Additional responses required before report is available: {needed_submissions} more submission(s)" if needed_submissions > 0 else ""
        opening_text = report_in_progress_text

    try:
        created_at_dt = datetime.fromisoformat(process.created_at)  # If stored in ISO format (e.g., "2025-02-07T14:30:00")
    except ValueError:
        created_at_dt = datetime.strptime(process.created_at, "%Y-%m-%d %H:%M:%S")  # Adjust format if needed

    formatted_date = created_at_dt.strftime("%B %d, %Y %H:%M")

    status_section = Article(
        Div(
            H3(f"{process.process_title} {' (Complete)' if process.feedback_report else ' (In Progress)'}"),
            Button("Delete Process", 
                  cls="delete-process-btn",
                  onclick=f"if(confirm('{process.feedback_report and 'As this report has been generated, your credits will not be refunded. ' or 'Your credits for pending requests will be refunded. '}Are you sure you want to delete this entire feedback process? Completed questionnaires will be discarded.')) window.location.href='/feedback-process/{process_id}/delete'"),
            cls="process-header"
        ),
        P(f"Created: {formatted_date}"),
        Div(opening_text, cls='marked'),
        Div(missing_text) if missing_text else None
    )
    
    requests_list = []
    for feedback_request in requests:
        submission = feedback_request.completed_at
        requests_list.append(
            Article(
                Div(
                Strong(f"{feedback_request.email}", cls='request-status-email'),
                Div(
                    Kbd('Completed', cls='request-status-completed') if submission else Kbd('Pending', cls='request-status-pending'),
                    Button("✕", 
                          cls="delete-btn",
                          onclick=f"if(confirm('{process.feedback_report and 'As this report has been generated, your credits will not be refunded. ' or 'Your credits will be refunded. '}Are you sure you want to delete this feedback request?')) window.location.href='/feedback-process/{process_id}/delete-request/{feedback_request.token}'")
                ),
                cls="request-status-header"),
                Div(
                P(
                  Button("Copy link to clipboard", cls="request-status-button", onclick=f"if(navigator.clipboard && navigator.clipboard.writeText){{ navigator.clipboard.writeText('{generate_external_link(uri('new-feedback-form', process_id=feedback_request.token))}').then(()=>{{ let btn=this; btn.setAttribute('data-tooltip', 'Copied to clipboard!'); setTimeout(()=>{{ btn.removeAttribute('data-tooltip'); }}, 1000); }}); }} else {{ alert('Clipboard functionality is not supported in this browser.'); }}"),
                  " ",
                  Div(
                    (P(f"Email sent on {feedback_request.email_sent}") 
                      if feedback_request.email_sent
                      else Button("Send email", 
                          hx_post=f"/feedback-process/{process_id}/send_email?token={feedback_request.token}", 
                          hx_target=f"#email-status-{feedback_request.token}", 
                          hx_swap="outerHTML",  cls="request-status-button")
                    ),
                    id=f"email-status-{feedback_request.token}", 
                  ), 
                ),cls="form-links-row", hidden=True if submission else False),
                cls=f"request-{feedback_request.user_type}"
            )
        )
    
    # Create collapsible new request form
    new_request_form = Form(
        Div(
            Input(type="email", name="email", placeholder="Enter email address", required=True,
                  hx_post="/validate-email",
                  hx_trigger="keyup changed delay:300ms",
                  hx_target="next .validation-result"),
            Div(cls="validation-result")
        ),
        Select(
            Option("Select role", value="", selected=True, disabled=True),
            Option("Peer", value="peer"),
            Option("Report", value="report"),
            Option("Supervisor", value="supervisor"),
            name="role",
            required=True
        ),
        Button("Add Request", type="submit"),
        action=f"/feedback-process/{process_id}/add-request",
        method="post"
    )

    requests_section = Article(
        *requests_list,
        Details(
            Summary("Add New Request", cls="button collapsible-toggle"),
            Article(new_request_form, id="new-request-section"),
        ),
        id="requests-section"
    )

    report_section = Div(id="report-section")

    if  process.feedback_report:
        report_section = Article(
        H3("Feedback Report"),
        Div(process.feedback_report, cls="marked"),
        id="report-section")
    elif can_generate_report:
            report_section = Div(
                Button(
                    "Generate Feedback Report",
                    onclick=f"window.location.href='/feedback-process/{process_id}/generate_completed_feedback_report'"
                ),
                id="report-section"
            ),
            Div("Generating your report...", id="loading-indicator", aria_busy="true", style="display:none;")


    process_page_content = generate_themed_page(
        page_body=Container(
            status_section,
            requests_section,   
            report_section
        ), 
        page_title="Feedback Process {process_id}",
        auth=req.scope.get("auth")
    )
    
    return process_page_content

def create_feedback_report_input(process_id):
    from html import escape
    logger.info(f"Creating feedback report input for process {process_id}")
    process = feedback_process_tb[process_id]
    logger.debug(f"Process qualities: {process.qualities}")
    
    submissions = feedback_submission_tb("process_id=?", (process_id,))
    logger.info(f"Found {len(submissions)} submissions")
    if not submissions:
        logger.error("No submissions found for this process")
        return "No submissions available for report generation"
    
    # Initialize statistics structure
    role_stats = {
        "peer": {"qualities": {}, "count": 0},
        "supervisor": {"qualities": {}, "count": 0},
        "report": {"qualities": {}, "count": 0}
    }
    
    overall_stats = {}
    import json
    from collections import defaultdict
    
    logger.debug("Initialized statistics structures")

    # Helper function to calculate statistics
    def calc_stats(values):
        if not values:
            return None
        n = len(values)
        avg = sum(values) / n
        variance = sum((x - avg) ** 2 for x in values) / n if n > 1 else 0
        std_dev = math.sqrt(variance)
        return {
            "average": round(avg, 2),
            "variance": round(variance, 2),
            "std_dev": round(std_dev, 2),
            "count": n,
            "min": min(values),
            "max": max(values),
            "raw_values": values
        }

    # Collect ratings by role and quality
    role_ratings = defaultdict(lambda: defaultdict(list))
    for s in submissions:
        logger.info(f"\nProcessing submission {s.id}")
        r = s.ratings
        logger.debug(f"Raw ratings data: {r}")
        
        if isinstance(r, str):
            try:
                r = json.loads(r)
                logger.info(f"Successfully parsed ratings JSON: {r}")
            except Exception as e:
                logger.error(f"Failed to parse ratings JSON for submission {s.id}: {e}")
                logger.error(f"Raw ratings string: {r}")
                r = {}
                continue

        if not r:
            logger.warning(f"Empty ratings for submission {s.id}")
            continue

        try:
            request = feedback_request_tb[s.request_id]
            role = request.user_type
            role_stats[role]["count"] += 1
            logger.info(f"Processing ratings for role {role}")

            # OR if process.qualities is already a list/dict, just use it directly:
            process_qualities = json.loads(process.qualities)  # Convert JSON string to Python list

            for quality in process_qualities:
                if quality in r:
                    value = r[quality]
                    logger.debug(f"Adding rating for {quality}: {value}")
                    role_ratings[role][quality].append(value)
                else:
                    logger.warning(f"Missing rating for quality: {quality}")
            
        except Exception as e:
            logger.error(f"Error processing request {s.request_id}: {e}")
            continue

    # Calculate statistics for each role and quality
    for role in role_stats:
        for quality in process_qualities:
            values = role_ratings[role][quality]
            if values:
                role_stats[role]["qualities"][quality] = calc_stats(values)

    # Calculate overall statistics for each quality
    for quality in process_qualities:
        all_values = []
        for role in role_ratings:
            all_values.extend(role_ratings[role][quality])
        if all_values:
            overall_stats[quality] = calc_stats(all_values)
    
    # Get themed feedback
    themes = feedback_themes_tb("feedback_id IN (SELECT id FROM feedback_submission WHERE process_id=?)", (process_id,))
    themed_feedback = {
        "positive": [escape(t.theme) for t in themes if t.sentiment == "positive"],
        "negative": [escape(t.theme) for t in themes if t.sentiment == "negative"],
        "neutral": [escape(t.theme) for t in themes if t.sentiment == "neutral"]
    }
    
    report_input = f"""Feedback Report Summary

Overall Quality Statistics:
{'-' * 40}"""

    for quality, stats in overall_stats.items():
        if stats:
            report_input += f"""
{quality}:
- Average Rating: {stats['average']}
- Rating Range: {stats['min']} - {stats['max']}
- Standard Deviation: {stats['std_dev']}
- Number of Ratings: {stats['count']}"""

    report_input += f"""

Role-Based Quality Analysis:
{'-' * 40}"""

    for role, data in role_stats.items():
        if data["count"] > 0:
            report_input += f"""

{role.title()} Feedback (from {data['count']} respondents):"""
            for quality, stats in data["qualities"].items():
                if stats:
                    report_input += f"""
{quality}:
- Average Rating: {stats['average']}
- Rating Range: {stats['min']} - {stats['max']}
- Rating Variance: {stats['variance']}"""

    report_input += f"""

Feedback Themes:
{'-' * 40}

Positive Themes:
{chr(10).join('- ' + theme for theme in themed_feedback['positive'])}

Areas for Improvement:
{chr(10).join('- ' + theme for theme in themed_feedback['negative'])}

Neutral Observations:
{chr(10).join('- ' + theme for theme in themed_feedback['neutral'])}

Summary Statistics:
- Total Submissions: {len(submissions)}
- Total Themes Identified: {len(themes)}
- Breakdown by Role:
  * Peers: {role_stats['peer']['count']}
  * Supervisors: {role_stats['supervisor']['count']}
  * Reports: {role_stats['report']['count']}
"""
    return report_input

@app.get("/feedback-process/{process_id}/generate_completed_feedback_report")
def create_feeback_report(process_id : str):
    process = feedback_process_tb[process_id]
    submissions = feedback_submission_tb("process_id=?", (process_id,))

    submission_counts = {
        "peer": len(feedback_request_tb("process_id=? AND user_type='peer' AND completed_at IS NOT NULL", (process_id,))),
        "supervisor": len(feedback_request_tb("process_id=? AND user_type='supervisor' AND completed_at IS NOT NULL", (process_id,))),
        "report": len(feedback_request_tb("process_id=? AND user_type='report' AND completed_at IS NOT NULL", (process_id,))),
    }
    total_submissions = sum(submission_counts.values())
    if total_submissions < process.min_submissions_required:
        logger.warning(f"Attempted to generate report without sufficient feedback ({total_submissions}/{process.min_submissions_required}) for process: {process_id}")
        return "Not enough feedback submissions to generate report", 400

    feedback_report_input = create_feedback_report_input(process_id)
    feedback_report_prompt, feedback_report = generate_completed_feedback_report(feedback_report_input)
    
    feedback_process_tb.update({
        "report_submission_prompt": feedback_report_prompt,
        "feedback_report": feedback_report
    }, process_id)
    
    # Redirect to refresh the page
    return RedirectResponse(f"/feedback-process/{process_id}", status_code=303)
    
# -------------------------------
# Route: Feedback Submission
# -------------------------------
@app.get("/new-feedback-form/{request_token}", name="new-feedback-form")
def get_feedback_form(request_token: str):

    # TODO: debug why this is happening
    if request_token.startswith('process_id='):
        request_token = request_token.replace('process_id=','')

    if feedback_request_tb[request_token].completed_at:
        return('This report has already been submitted')

    original_process_id = feedback_request_tb[request_token].process_id

    requestor_id = feedback_process_tb[original_process_id].user_id
    requestor_name = users("id=?", (requestor_id,))[0].first_name

    # make sure the first letter of the requestor's name is capitalized
    requestor_name = requestor_name[0].upper() + requestor_name[1:]

    introduction_text = Div(f"""{requestor_name} is completing a 360 feedback process through [Feedback to Me](https://feedback-to.me), and would like your help! """,
    cls='marked')

    process_explanation = Div(f"""Once you submit your feedback, we'll anonymise it, and compile it into a report for {requestor_name}. You can learn more about Feedback to Me, and how we handle your data and generate feedback [on our website.]({BASE_URL})""",
    cls='marked')

    checkbox_text = Div(f"Please rate {requestor_name} on the following qualities:", cls='marked')   

    textbox_text = Div(f"Please write any additional feedback you have for {requestor_name}. Don't worry, we'll make sure it's all anonymous!", cls='marked')

    onward_request_id = request_token
    
    qualities = feedback_process_tb[original_process_id].qualities
    if not isinstance(qualities, list):
        try:
            import ast
            qualities = ast.literal_eval(qualities)
            if not isinstance(qualities, list):
                qualities = [q.strip() for q in str(qualities).split(",") if q.strip()]
        except Exception:
            qualities = [q.strip() for q in qualities.split(",") if q.strip()]
    form = Form(checkbox_text,
            *[(
                   Label(q, cls="range-label"), 
                   Div(
                       Input(type="range", min=1, max=8, value=4, name=f"rating_{q.lower()}", id=f"rating_{q.lower()}"),
                       cls="range-wrapper"
                   )
              ) for q in qualities],
              textbox_text,
            Textarea(name="feedback_text", id="feedback_text", placeholder="Provide detailed feedback...", rows=5, required=True),
        Button("Submit Feedback", type="submit"),
        hx_post=f"/new-feedback-form/{onward_request_id}/submit", hx_target="body", hx_swap="outerHTML"
    )
    return Titled("Submit Feedback", introduction_text, process_explanation, form,footer_bar)

@app.get("/feedback-submitted")
def get_feedback_submitted():
    thank_you_text = Div("Thank you for your feedback! It has been submitted successfully.", cls='marked')
    learn_more_text = Div(f"If you'd like to generate your own free feedback report, check out [Feedback to Me!](https://feedback-to.me)", cls='marked')
    return Titled("Feedback Submitted", thank_you_text, learn_more_text,footer_bar)
    

@limiter.limit("5/minute")
@app.post("/new-feedback-form/{request_token}/submit")
def submit_feedback_form(request_token: str, feedback_text: str, data : dict, request: Request):
    from html import escape
    logger.debug(f"Submitting feedback form with data: {data}")
    try:
        feedback_request = feedback_request_tb[request_token]
        logger.debug('Found feedback request')
        
        # Get process qualities
        process = feedback_process_tb[feedback_request.process_id]
        
        # Parse qualities from process
        qualities = process.qualities
        logger.debug(f"Raw qualities from process: {qualities}")
        
        if isinstance(qualities, str):
            try:
                # Try to parse as JSON first
                qualities = json.loads(qualities)
                logger.debug(f"Parsed qualities from JSON: {qualities}")
            except json.JSONDecodeError:
                try:
                    # Try to parse as Python literal
                    import ast
                    qualities = ast.literal_eval(qualities)
                    logger.debug(f"Parsed qualities from literal_eval: {qualities}")
                except (ValueError, SyntaxError):
                    # If both fail, split by comma
                    qualities = [q.strip() for q in qualities.split(",") if q.strip()]
                    logger.debug(f"Split qualities by comma: {qualities}")
        
        if not isinstance(qualities, list):
            logger.error(f"Failed to parse qualities into list. Current value: {qualities}")
            qualities = []
        
        logger.info(f"Final qualities list: {qualities}")
        logger.debug(f"Processing ratings for qualities: {qualities}")
        logger.debug(f"Form data received: {data}")
        ratings = {}
        for quality in qualities:
            rating_key = f"rating_{quality.lower()}"
            if rating_key in data:
                try:
                    rating_value = int(data[rating_key])
                    ratings[quality] = rating_value
                    logger.debug(f"Added rating for {quality}: {rating_value}")
                except (ValueError, TypeError):
                    logger.warning(f"Invalid rating value for {quality}: {data[rating_key]}")
                    continue
            else:
                logger.warning(f"Missing rating for quality: {quality} (key: {rating_key})")
        submission_data = {
            "id": secrets.token_hex(8),
            "request_id": request_token,
            "feedback_text": escape(feedback_text),
            "ratings": json.dumps(ratings),  # Explicitly JSON encode ratings
            "process_id": feedback_request.process_id,
            "created_at": datetime.now()
        }
        logger.debug(f"Submission data prepared: {submission_data}")
        submission = feedback_submission_tb.insert(submission_data)
        feedback_themes = convert_feedback_text_to_themes(feedback_text)
        if feedback_themes:
            for sentiment in ["positive", "negative", "neutral"]:
                if len(feedback_themes[sentiment]) > 0:
                    for theme in feedback_themes[sentiment]:
                        theme_data = {
                            "id": secrets.token_hex(8),
                            "feedback_id": submission.id,
                            "theme": theme,
                            "sentiment": sentiment,
                            "created_at": datetime.now()
                        }
                        feedback_themes_tb.insert(theme_data)
        process = feedback_process_tb[feedback_request.process_id]
        feedback_process_tb.update(
            {"feedback_count": process.feedback_count + 1},
            feedback_request.process_id
        )
        feedback_request_tb.update(feedback_request, completed_at=datetime.now(), token=request_token)
        return RedirectResponse("/feedback-submitted", status_code=303)
    except Exception as e:
        logger.error(f"Error submitting feedback: {str(e)}")
        return "Error submitting feedback. Please try again.", 500

@app.post("/feedback-process/{process_id}/add-request")
def add_feedback_request(process_id: str, email: str, role: str, sess):
    # Validate user owns this process
    user_id = sess.get("auth")
    if not user_id:
        return "Unauthorized", 401
    
    try:
        process = feedback_process_tb[process_id]
        if process.user_id != user_id:
            return "Unauthorized", 401
        
        # Check if user has enough credits
        user = users("id=?", (user_id,))[0]
        if user.credits < 1:
            return Article(
                P("You don't have enough credits to add another request. Please purchase more credits."),
                id="requests-section"
            )
        
        # Generate magic link and create request
        link = generate_magic_link(email, process_id=process_id)
        token = link.replace("new-feedback-form/token=", "")
        
        # Update request with role
        feedback_request_tb.update({"user_type": role}, token=token)
        
        # Deduct credit
        user.credits -= 1
        users.update(user)
        
        # Return updated requests section
        requests = feedback_request_tb("process_id=?", (process_id,))
        requests_list = []
        for feedback_request in requests:
            submission = feedback_request.completed_at
            requests_list.append(
                Article(
                    Div(
                        Strong(f"{feedback_request.email}", cls='request-status-email'),
                        Div(
                            Kbd('Completed', cls='request-status-completed') if submission else Kbd('Pending', cls='request-status-pending'),
                            Button("✕", 
                                  cls="delete-btn",
                                  onclick=f"window.location.href='/feedback-process/{process_id}/delete-request/{feedback_request.token}'")
                        ),
                        cls="request-status-header"
                    ),
                    Div(
                        P(
                            Button("Copy link to clipboard", cls="request-status-button", onclick=f"if(navigator.clipboard && navigator.clipboard.writeText){{ navigator.clipboard.writeText('{generate_external_link(uri('new-feedback-form', process_id=feedback_request.token))}').then(()=>{{ let btn=this; btn.setAttribute('data-tooltip', 'Copied to clipboard!'); setTimeout(()=>{{ btn.removeAttribute('data-tooltip'); }}, 1000); }}); }} else {{ alert('Clipboard functionality is not supported in this browser.'); }}"),
                            " ",
                            Div(
                                (P(f"Email sent on {feedback_request.email_sent}") 
                                if feedback_request.email_sent
                                else Button("Send email", 
                                    hx_post=f"/feedback-process/{process_id}/send_email?token={feedback_request.token}", 
                                    hx_target=f"#email-status-{feedback_request.token}", 
                                    hx_swap="outerHTML",  cls="request-status-button")
                                ),
                                id=f"email-status-{feedback_request.token}", 
                            ), 
                        ),
                        cls="form-links-row",
                        hidden=True if submission else False
                    ),
                    cls=f"request-{feedback_request.user_type}"
                )
            )
        
        new_request_form = Article(
            H3("Add New Request"),
            Form(
                Input(type="email", name="email", placeholder="Enter email address", required=True),
                Select(
                    Option("Select role", value="", selected=True, disabled=True),
                    Option("Peer", value="peer"),
                    Option("Report", value="report"),
                    Option("Supervisor", value="supervisor"),
                    name="role",
                    required=True
                ),
                Button("Add Request", type="submit"),
                action=f"/feedback-process/{process_id}/add-request",
                method="post",
                hx_post=f"/feedback-process/{process_id}/add-request",
                hx_target="#requests-section",
                hx_swap="outerHTML"
            )
        )
        
        # Redirect to refresh the page
        return RedirectResponse(f"/feedback-process/{process_id}", status_code=303)
        
    except Exception as e:
        logger.error(f"Error adding feedback request: {str(e)}")
        return "Error adding feedback request", 500

@app.get("/feedback-process/{process_id}/delete-request/{token}")
def delete_feedback_request(process_id: str, token: str, sess):
    # Validate user owns this process
    user_id = sess.get("auth")
    if not user_id:
        return "Unauthorized", 401
    
    try:
        # Verify process exists and user owns it
        process = feedback_process_tb[process_id]
        if process.user_id != user_id:
            return "Unauthorized", 401
        
        # Get the request to delete
        request = feedback_request_tb[token]
        if request.process_id != process_id:
            return "Invalid request", 400
        
        submissions = feedback_submission_tb("request_id=?", (token,))

        if len(submissions) > 0 :   
            for submission in submissions:
                feedback_submission_tb.delete(submission.id)
        
        # Only refund credit if no report exists
        if not process.feedback_report:
            user = users("id=?", (user_id,))[0]
            user.credits += 1
            users.update(user)
        
        # Delete the request
        feedback_request_tb.delete(token)
        
        # Redirect to refresh the page
        return RedirectResponse(f"/feedback-process/{process_id}", status_code=303)
        
    except Exception as e:
        logger.error(f"Error deleting feedback request: {str(e)}")
        return "Error deleting feedback request", 500

@app.get("/feedback-process/{process_id}/delete")
def delete_process(process_id: str, sess):
    # Validate user owns this process
    user_id = sess.get("auth")
    if not user_id:
        return "Unauthorized", 401
    
    try:
        # Verify process exists and user owns it
        process = feedback_process_tb[process_id]
        if process.user_id != user_id:
            return "Unauthorized", 401
        
        # Only refund credits if no report exists
        if not process.feedback_report:
            # Get all pending requests to refund credits
            pending_requests = feedback_request_tb("process_id=? AND completed_at IS NULL", (process_id,))
            
            # Return credits to user for pending requests
            if pending_requests:
                logger.debug(f'Refunding pending requests: {len(pending_requests)}')
                user = users("id=?", (user_id,))[0]
                user.credits += len(pending_requests)
                users.update(user)
        
        # Delete all feedback submissions for this process
        submissions = feedback_submission_tb("process_id=?", (process_id,))
        if len (submissions) > 0:
            for submission in submissions:
                feedback_submission_tb.delete(submission.id)
                
            submission_themes = feedback_themes_tb("process_id=?", (process_id,))
            if len(submission_themes) > 0:
                for theme in submission_themes:
                    feedback_themes_tb.delete(theme.id)
        
        # Delete all requests (both pending and completed)
        requests = feedback_request_tb("process_id=?", (process_id,))
        for request in requests:
            feedback_request_tb.delete(request.token)
            
        # Finally delete the process itself
        feedback_process_tb.delete(process_id)
        
        # Redirect to dashboard
        return RedirectResponse("/dashboard", status_code=303)
        
    except Exception as e:
        logger.error(f"Error deleting feedback process: {str(e)}")
        return "Error deleting feedback process", 500

# -----------------------
# Routes: Admin
# -----------------------
@limiter.limit("30/day")
@app.get("/admin")
def get_admin(request: Request):
    auth = request.scope.get("auth")
    if not auth:
        return RedirectResponse("/login", status_code=303)
    
    user = users("id=?", (auth,))[0]
    if not user.is_admin:
        return RedirectResponse("/dashboard", status_code=303)
    
    success = request.query_params.get('success')
    
    admin_page = Container(
        H2("Admin Dashboard"),
        P("Welcome to the admin dashboard."),
        Div(P("Database uploaded successfully!", cls="success"), cls="alert") if success else None,
        Article(
            H2("Database Management"),
            A(Button("Download Database"), href="/admin/download-db", cls="primary"),
            Form(
                Input(type="file", name="dbfile", accept=".db", required=True),
                Button("Upload Database", type="submit"),
                action="/admin/upload-db",
                method="post",
                enctype="multipart/form-data"
            )
        )
    )
    
    return generate_themed_page(admin_page, auth=auth, page_title="Admin Dashboard")

@limiter.limit("30/day")
@app.get("/admin/download-db")
def download_db(request: Request):
    auth = request.scope.get("auth")
    if not auth:
        return RedirectResponse("/login", status_code=303)
    
    user = users("id=?", (auth,))[0]
    if not user.is_admin:
        return RedirectResponse("/dashboard", status_code=303)
    
    try:
        import sqlite3
        import os
        from datetime import datetime
        
        # Create a backup file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"data/feedback_backup_{timestamp}.db"
        
        # Create a proper SQLite backup
        source = sqlite3.connect("data/feedback.db")
        dest = sqlite3.connect(backup_path)
        source.backup(dest)
        source.close()
        dest.close()
        
        # Serve the backup file
        response = FileResponse(backup_path, filename="feedback-backup.db", media_type="application/x-sqlite3")
        
        # Delete the backup file after sending
        def cleanup(response):
            if os.path.exists(backup_path):
                os.remove(backup_path)
            return response
            
        response.background = cleanup
        return response
        
    except Exception as e:
        logger.error(f"Database backup failed: {str(e)}")
        return Titled("Error", P("Failed to create database backup."))

@limiter.limit("30/day")
@app.post("/admin/upload-db")
async def upload_db(request : Request):
    auth = request.scope.get("auth")
    if not auth:
        return RedirectResponse("/login", status_code=303)
    
    user = users("id=?", (auth,))[0]
    if not user.is_admin:
        return RedirectResponse("/dashboard", status_code=303)
    
    try:
        import sqlite3
        import os
        from datetime import datetime
        
        form = await request.form()
        file = form["dbfile"]
        if not file.filename.endswith('.db'):
            return Titled("Error", P("Invalid file type. Please upload a .db file."))
        
        # Create a temporary file for the uploaded content
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_path = f"data/upload_temp_{timestamp}.db"
        
        try:
            # Save uploaded content to temporary file
            contents = await file.read()
            with open(temp_path, "wb") as f:
                f.write(contents)
            
            # Verify it's a valid SQLite database
            try:
                temp_conn = sqlite3.connect(temp_path)
                temp_conn.cursor().execute("SELECT name FROM sqlite_master WHERE type='table'")
                temp_conn.close()
            except sqlite3.Error:
                os.remove(temp_path)
                return Titled("Error", P("Invalid SQLite database file."))
            
            # Create backup of current database using SQLite backup API
            backup_path = f"data/feedback_backup_{timestamp}.db"
            source = sqlite3.connect("data/feedback.db")
            backup = sqlite3.connect(backup_path)
            source.backup(backup)
            source.close()
            backup.close()
            
            try:
                # Replace current database with uploaded one using SQLite backup API
                dest = sqlite3.connect("data/feedback.db")
                source = sqlite3.connect(temp_path)
                source.backup(dest)
                source.close()
                dest.close()
                
                # Clean up temporary files
                os.remove(temp_path)
                os.remove(backup_path)
                
                return RedirectResponse("/admin?success=true", status_code=303)
                
            except Exception as e:
                # Restore from backup if something went wrong
                if os.path.exists(backup_path):
                    dest = sqlite3.connect("data/feedback.db")
                    backup = sqlite3.connect(backup_path)
                    backup.backup(dest)
                    backup.close()
                    dest.close()
                    os.remove(backup_path)
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                logger.error(f"Database upload failed: {str(e)}")
                return Titled("Error", P("Failed to upload database. The previous database has been restored."))
                
        except Exception as e:
            # Clean up temporary files
            if os.path.exists(temp_path):
                os.remove(temp_path)
            if os.path.exists(backup_path):
                os.remove(backup_path)
            logger.error(f"Database upload failed: {str(e)}")
            return Titled("Error", P("Failed to process uploaded file."))
            
    except Exception as e:
        logger.error(f"Database upload failed: {str(e)}")
        return Titled("Error", P("Failed to process upload request."))

@app.post("/feedback-process/{process_id}/send_email")
def send_feedback_email_route(process_id: str, token: str, recipient_first_name: str = ""):
    try:
        req = feedback_request_tb[token]
        process = feedback_process_tb[process_id]
        sender = users("id=?", (process.user_id,))[0]
        link = uri("new-feedback-form", process_id=req.token)
        success = send_feedback_email(req.email, link, recipient_first_name, sender.first_name)
        if success:
            feedback_request_tb.update({"email_sent": datetime.now()}, token=token)
            return P("Email sent successfully!")
        else:
            return P("Failed to send email."), 500
    except Exception as e:
        logger.error(f"Error sending email for token {token}: {str(e)}")
        return P("Error sending email."), 500

# Stripe Webhook Handler
@app.post("/stripe-webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")

    if not webhook_secret:
        logger.error("STRIPE_WEBHOOK_SECRET not configured")
        return Response(status_code=500)

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError as e:
        logger.error("Invalid payload in webhook")
        return Response(status_code=400)
    except stripe.error.SignatureVerificationError as e:
        logger.error("Invalid signature in webhook")
        return Response(status_code=400)

    if event["type"] == "checkout.session.completed":
        try:
            session = event["data"]["object"]
            credits = int(session.metadata.get("credits", 0))
            user_id = session.metadata.get("user_id")

            if user_id and credits > 0:
                user = users("id=?", (user_id,))[0]
                user.credits += credits
                users.update(user)
                logger.info(f"Added {credits} credits to user {user_id} via webhook")
            else:
                logger.error(f"Invalid webhook data: credits={credits}, user_id={user_id}")
        except Exception as e:
            logger.error(f"Error processing webhook payment: {str(e)}")
            return Response(status_code=500)

    return Response(status_code=200)

# Start the App
# -------------
if __name__ == "__main__":
    serve(port=8080)
