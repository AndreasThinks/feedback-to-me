#!/usr/bin/env python
from fasthtml.common import *
from datetime import datetime, timedelta
dev_mode = os.environ.get("DEV_MODE", "false").lower() == "true"

import secrets, os
import bcrypt
import logging
from datetime import datetime

# Configure logging based on environment variable
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from models import feedback_themes_tb, feedback_submission_tb, users, feedback_process_tb, feedback_request_tb, FeedbackProcess, FeedbackRequest, Login, confirm_tokens_tb
from pages import generate_themed_page, faq_page, error_message, login_or_register_page, register_form, login_form, landing_page, navigation_bar_logged_out, navigation_bar_logged_in, footer_bar, about_page, privacy_policy_page

from llm_functions import convert_feedback_text_to_themes, generate_completed_feedback_report

from config import MIN_PEERS, MIN_SUPERVISORS, MIN_REPORTS, MAGIC_LINK_EXPIRY_DAYS, FEEDBACK_QUALITIES, STARTING_CREDITS, BASE_URL
from utils import beforeware

import requests
import stripe
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")


# --------------------
# FastHTML App Setup
# --------------------
app, rt = fast_app(
    before=beforeware,
    hdrs=(
        MarkdownJS(),  # Allows rendering markdown in feedback text, if needed.
        Link(rel='stylesheet', href='/static/styles.css', type='text/css')
    ),
    exception_handlers={HTTPException: lambda req, exc: Response(content="", status_code=exc.status_code, headers=exc.headers)}
)

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

def send_feedback_email(recipient: str,  link: str, recipient_first_name: str = "", recipient_company: str = "") -> bool:
    try:
        link = generate_external_link(link)
        with open("feedback_email_template.txt", "r") as f:
            template = f.read()
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
def get():
    return generate_themed_page(landing_page)


@app.get("/homepage")
def get():
    return generate_themed_page(landing_page)

@app.get("/about")
def get():
    return generate_themed_page(about_page)

@app.get("/faq")
def get():
    return faq_page()

@app.get("/privacy-policy")
def get():
    return generate_themed_page(privacy_policy_page)

@app.get("/get-started")
def get(sess):
    if "auth" in sess:
        return Redirect("/dashboard")
    return generate_themed_page(login_or_register_page)

# -----------------------
# User Registration and Login Pages
# -----------------------

@app.get("/login-or-register")
def get():
    return login_or_register_page 

@app.get("/login-form")
def get():
    return login_form

@app.get("/registration-form")
def get():
    return register_form

@app.post("/login")
def post_login(login: Login, sess):
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

@app.get("/register")
def get(req):
    auth = req.scope.get("auth")
    if auth:
        logger.debug(f"Already logged in user ({auth}) accessing register page, redirecting to dashboard")
        return RedirectResponse("/dashboard", status_code=303)
    logger.debug("Serving registration form")
    return register_form

# -----------------------
# Routes: User Registration
# -----------------------
@app.post("/register-new-user")
def post_register(email: str, first_name:str, role: str, company: str, team: str, pwd: str, sess):
    logger.debug(f"Registration attempt for email: {email}")
    if "auth" in sess:
        logger.debug("Clearing existing session auth")
        del sess["auth"]
    
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
         session = stripe.checkout.Session.retrieve(session_id)
         credits = int(session.metadata.get("credits", 0))
         user_id = session.metadata.get("user_id")
         if user_id:
             user = users("id=?", (user_id,))[0]
             user.credits += credits
             users.update(user)
         message = f"Payment successful! {credits} credits have been added to your account."
         return Titled("Payment Success", P(message), A("Go to Dashboard", href="/dashboard"))
    except Exception as e:
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
        Div(Button("Start New Feedback Collection", hx_get="/start-new-feedback-process", hx_target="#main-content", hx_swap="innerHTML"), cls="collect-feedback-button"),
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
@app.get("/start-new-feedback-process")
def get_new_feedback():
    if MIN_REPORTS == 0:
        respondents_div = Div(
            P(f"You'll need at least {MIN_PEERS} peers, {MIN_SUPERVISORS} supervisors, and {MIN_REPORTS} direct reports to generate your finalised report"),
            cls="min-requirements"
        )
    else:
        respondents_div = Div(
            P(f"You'll need at least {MIN_PEERS} peers and {MIN_SUPERVISORS} supervisors to generate your finalised report"),
            cls="min-requirements"
        )
    
    form = Form(
        Input(name='process_title', type='text', placeholder="Provide a short title for this process"),
        respondents_div,
        Div(
            P("Enter emails (one per line) for each category:")
        ),
        Div(
            H3("Peers"),
            Textarea(name="peers_emails", placeholder="Enter peer emails, one per line", rows=3)
        ),
        Div(
            H3("Supervisors"),
            Textarea(name="supervisors_emails", placeholder="Enter supervisor emails, one per line", rows=3)
        ),
        Div(
            H3("Reports"),
            Textarea(name="reports_emails", placeholder="Enter report emails, one per line", rows=3)
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
            H3("Other Qualities (comma separated)"),
            Input(name="custom_qualities", type="text", placeholder="Enter custom qualities separated by commas")
        ),
        Button("Begin collecting feedback", type="submit", cls="primary")
        , action="/create-new-feedback-process", method="post"
    )
    
    return Titled("Start new feedback process", form)

@app.post("/create-new-feedback-process")
def create_new_feedback_process(process_title : str, peers_emails: str, supervisors_emails: str, reports_emails: str, sess, data: dict):
    logger.debug("create_new_feedback_process called with:")
    logger.debug(f"peers_emails: {peers_emails!r}")
    logger.debug(f"supervisors_emails: {supervisors_emails!r}")
    logger.debug(f"reports_emails: {reports_emails!r}")
    logger.debug(f"Additional form data: {data!r}")
    user_id = sess.get("auth")
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
    custom_qualities = data.get("custom_qualities", "")
    if custom_qualities:
        custom_list = [s.strip() for s in custom_qualities.split(",") if s.strip()]
        selected_qualities.extend(custom_list)
    process_data = {
        "id": secrets.token_hex(8),
        "process_title" :  process_title,
        "user_id": user_id,
        "created_at": datetime.now(),
        "min_required_peers": MIN_PEERS,
        "min_required_supervisors": MIN_SUPERVISORS,
        "min_required_reports": MIN_REPORTS,
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
def get_report_status_page(process_id : str):
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
    
    can_generate_report = (
        submission_counts["peer"] >= process.min_required_peers and
        submission_counts["supervisor"] >= process.min_required_supervisors and
        submission_counts["report"] >= process.min_required_reports and
        not process.feedback_report
    )

    report_in_progress_text = "Your request for feedback has been created, along with a custom questionaire for each participant. Please email them each their custom link, or click the button below for us to email them on your behalf. "
    report_awaiting_generation_text = "You've received enough feedback to generate a report! Click the button when you're ready to create your report summary. "
    report_completed_text = "Your feedback process is complete, and your final report has been generated. "
    
    if process.feedback_report:
        opening_text = report_completed_text
    elif can_generate_report:
        opening_text = report_awaiting_generation_text
    else:
        needed_peers = max(process.min_required_peers - submission_counts["peer"], 0)
        needed_supervisors = max(process.min_required_supervisors - submission_counts["supervisor"], 0)
        needed_reports = max(process.min_required_reports - submission_counts["report"], 0)
        missing_parts = []
        if needed_peers > 0:
            missing_parts.append(f"{needed_peers} peer(s)")
        if needed_supervisors > 0:
            missing_parts.append(f"{needed_supervisors} supervisor(s)")
        if needed_reports > 0:
            missing_parts.append(f"{needed_reports} report(s)")
        missing_text = "Additional responses required before report is available: " + ", ".join(missing_parts) if missing_parts else ""
        opening_text = report_in_progress_text + " " + missing_text

    try:
        created_at_dt = datetime.fromisoformat(process.created_at)  # If stored in ISO format (e.g., "2025-02-07T14:30:00")
    except ValueError:
        created_at_dt = datetime.strptime(process.created_at, "%Y-%m-%d %H:%M:%S")  # Adjust format if needed

    formatted_date = created_at_dt.strftime("%B %d, %Y %H:%M")

    status_section = Article(
        H3(f"{process.process_title} {' (Complete)' if process.feedback_report else ' (In Progress)'}"),
        P(f"Created: {formatted_date}"),
        Div(opening_text, cls='marked'),
    )
    
    requests_list = []
    for req in requests:
        submission = req.completed_at
        requests_list.append(
            Article(
                Div(
                Strong(f"{req.email}", cls='request-status-email'),
                Kbd('Completed', cls='request-status-completed') if submission else Kbd('Pending', cls='request-status-pending'),
                cls="request-status-header"),
                Div(
                P(
                  Button("Copy link to clipboard", cls="request-status-button", onclick=f"if(navigator.clipboard && navigator.clipboard.writeText){{ navigator.clipboard.writeText('{generate_external_link(uri('new-feedback-form', process_id=req.token))}').then(()=>{{ let btn=this; btn.setAttribute('data-tooltip', 'Copied to clipboard!'); setTimeout(()=>{{ btn.removeAttribute('data-tooltip'); }}, 1000); }}); }} else {{ alert('Clipboard functionality is not supported in this browser.'); }}"),
                  " ",
                  Div(
                    (P(f"Email sent on {req.email_sent}") 
                      if req.email_sent
                      else Button("Send email", 
                          hx_post=f"/feedback-process/{process_id}/send_email?token={req.token}", 
                          hx_target=f"#email-status-{req.token}", 
                          hx_swap="outerHTML",  cls="request-status-button")
                    ),
                    id=f"email-status-{req.token}", 
                  ), 
                ),cls="form-links-row", hidden=True if submission else False),
                cls=f"request-{req.user_type}"
            )
        )
    
    requests_section = Article(
        *requests_list
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
                    hx_post=f"/feedback-process/{process_id}/generate_completed_feedback_report",
                    hx_target="#report-section",
                    hx_swap="outerHTML",
                    hx_indicator="#loading-indicator"
                ),
                id="report-section"
            ),
            Div("Generating your report...", id="loading-indicator", aria_busy="true", style="display:none;")


    process_page_content = generate_themed_page(page_body=Container(
            status_section,
            requests_section,   
            report_section
        ), page_title="Feedback Process {process_id}")
    
    return process_page_content

def create_feedback_report_input(process_id):
    process = feedback_process_tb[process_id]
    submissions = feedback_submission_tb("process_id=?", (process_id,))
    
    quality_stats = {}
    import json
    for quality in process.qualities:
        rating_values = []
        for s in submissions:
            r = s.ratings
            if isinstance(r, str):
                try:
                    r = json.loads(r)
                except Exception:
                    r = {}
            if quality in r:
                rating_values.append(r[quality])
        if rating_values:
            avg = sum(rating_values) / len(rating_values)
            variance = sum((r - avg) ** 2 for r in rating_values) / len(rating_values)
            quality_stats[quality] = {
                "average": round(avg, 2),
                "variance": round(variance, 2),
                "count": len(rating_values)
            }
    
    themes = feedback_themes_tb("feedback_id IN (SELECT id FROM feedback_submission WHERE process_id=?)", (process_id,))
    themed_feedback = {
        "positive": [t.theme for t in themes if t.sentiment == "positive"],
        "negative": [t.theme for t in themes if t.sentiment == "negative"],
        "neutral": [t.theme for t in themes if t.sentiment == "neutral"]
    }
    
    report_input = f"""Feedback Report Summary for Process {process_id}

Quality Ratings:
{'-' * 40}"""
    for quality, stats in quality_stats.items():
        report_input += f"""
{quality}:
- Average Rating: {stats['average']}
- Rating Variance: {stats['variance']}
- Number of Ratings: {stats['count']}"""

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
"""
    return report_input

@app.post("/feedback-process/{process_id}/generate_completed_feedback_report")
def create_feeback_report(process_id : str):
    try:
        process = feedback_process_tb[process_id]
        submissions = feedback_submission_tb("process_id=?", (process_id,))

        submission_counts = {
            "peer": len(feedback_request_tb("process_id=? AND user_type='peer' AND completed_at IS NOT NULL", (process_id,))),
            "supervisor": len(feedback_request_tb("process_id=? AND user_type='supervisor' AND completed_at IS NOT NULL", (process_id,))),
            "report": len(feedback_request_tb("process_id=? AND user_type='report' AND completed_at IS NOT NULL", (process_id,))),
        }
        if (submission_counts["peer"] < process.min_required_peers or
            submission_counts["supervisor"] < process.min_required_supervisors or
            submission_counts["report"] < process.min_required_reports):
            logger.warning(f"Attempted to generate report without sufficient feedback for process: {process_id}")
            return "Not enough feedback submissions to generate report", 400

        feedback_report_input = create_feedback_report_input(process_id)
        feedback_report = generate_completed_feedback_report(feedback_report_input)
        
        feedback_process_tb.update({"feedback_report": feedback_report}, process_id)
        
        return Article(
            H3("Feedback Report"),
            Div(feedback_report, cls="markdown"),
            id="report-section"
        )
        
    except Exception as e:
        logger.error(f"Error generating feedback report for process {process_id}: {str(e)}")
        return "Error generating feedback report", 500

# -------------------------------
# Route: Feedback Submission
# -------------------------------
@app.get("/new-feedback-form/{process_id}", name="new-feedback-form")
def get_feedback_form(process_id: str):

    if process_id.startswith('process_id='):
        process_id = process_id.replace('process_id=','')

    original_process_id = feedback_request_tb[process_id].process_id

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

    onward_request_id = process_id
    
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
                       Input(type="range", min=1, max=8, value=4, id=f"rating_{q.lower()}"),
                       cls="range-wrapper"
                   )
              ) for q in qualities],
              textbox_text,
            Textarea(id="feedback_text", placeholder="Provide detailed feedback...", rows=5, required=True),
        Button("Submit Feedback", type="submit"),
        hx_post=f"/new-feedback-form/{onward_request_id}/submit", hx_target="body", hx_swap="outerHTML"
    )
    return Titled("Submit Feedback", introduction_text, process_explanation, form,footer_bar)

@app.get("/feedback-submitted")
def get_feedback_submitted():
    thank_you_text = Div("Thank you for your feedback! It has been submitted successfully.", cls='marked')
    learn_more_text = Div(f"If you'd like to generate your own free feedback report, check out [Feedback to Me!](https://feedback-to.me)", cls='marked')
    return Titled("Feedback Submitted", thank_you_text, learn_more_text,footer_bar)
    

@app.post("/new-feedback-form/{request_token}/submit")
def submit_feedback_form(request_token: str, feedback_text: str, data : dict):
    print(data)
    try:
        feedback_request = feedback_request_tb[request_token]
        print('found feedback request')
        ratings = {}
        for quality in FEEDBACK_QUALITIES:
            rating_key = f"rating_{quality.lower()}"
            if rating_key in data:
                try:
                    ratings[quality] = int(data[rating_key])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid rating value for {quality}: {data[rating_key]}")
                    continue
        submission_data = {
            "id": secrets.token_hex(8),
            "request_id": feedback_request.process_id,
            "feedback_text": feedback_text,
            "ratings": ratings,
            "process_id": feedback_request.process_id,
            "created_at": datetime.now()
        }
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

@app.post("/feedback-process/{process_id}/send_email")
def send_feedback_email_route(process_id: str, token: str, recipient_first_name: str = "", recipient_company: str = ""):
    try:
        req = feedback_request_tb[token]
        link = uri("new-feedback-form", process_id=req.token)
        success = send_feedback_email(req.email, link, recipient_first_name, recipient_company)
        if success:
            feedback_request_tb.update({"email_sent": datetime.now()}, token=token)
            return P("Email sent successfully!")
        else:
            return P("Failed to send email."), 500
    except Exception as e:
        logger.error(f"Error sending email for token {token}: {str(e)}")
        return P("Error sending email."), 500

# Start the App
# -------------
if __name__ == "__main__":
    serve(port=8080)
