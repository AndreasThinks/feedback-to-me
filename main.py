#!/usr/bin/env python
from fasthtml.common import *
from datetime import datetime, timedelta
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

from models import users, feedback_process_tb, feedback_request_tb, FeedbackProcess, FeedbackRequest, Login
from pages import dashboard_page, login_or_register_page,register_form, login_form, landing_page, navigation_bar_logged_out, navigation_bar_logged_in, footer_bar, about_page, privacy_policy_page

from llm_functions import convert_feedback_text_to_themes, generate_completed_feedback_report


from config import MIN_PEERS, MIN_SUPERVISORS, MIN_REPORTS, MAGIC_LINK_EXPIRY_DAYS, FEEDBACK_QUALITIES

from utils import beforeware
from fastcore.basics import patch

@patch
def __ft__(self: FeedbackProcess):
    link = AX(f"Feedback Process {self.id}", f'/feedback-process/{self.id}', 'current-process')
    status_str = "Complete" if self.feedback_report else "In Progress"
    cts = (status_str, " - ", link)
    return Li(*cts, id=f'process-{self.id}')

# --------------------
# FastHTML App Setup
# --------------------
app, rt = fast_app(
    before=beforeware,
    hdrs=(
        MarkdownJS(),  # Allows rendering markdown in feedback text, if needed.
    ),
    exception_handlers={HTTPException: lambda req, exc: Response(content="", status_code=exc.status_code, headers=exc.headers)}
)

# --------------------
# Helper Functions
# --------------------

def generate_themed_page(page_body, auth=None, page_title="Feedback to Me"):
    """Generate a themed page with appropriate navigation bar based on auth status"""
    return Container(
        Title(page_title),
        navigation_bar_logged_in if auth else navigation_bar_logged_out,
        Div(page_body, id="main-content"),
        footer_bar
    )

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
    return f"/feedback/submit/{token}"

# -----------------------
# static pages
# -----------------------

# this is your landing page - it should have some markdown, and a link to the key pages, as well as a login button

@app.get("/")
def get(req, sess):
    # if the user is not logged in, show the static landing page
    # if the user is logged in, redirect to dashboard
    auth = req.scope["auth"] = sess.get("auth", None)
    logger.debug(f"Root path accessed with auth: {auth}")
    if not auth:
        logger.debug("User not authenticated, redirecting to homepage")
        return RedirectResponse("/homepage", status_code=303)
    else:
        logger.debug("User authenticated, redirecting to dashboard")
        return RedirectResponse("/dashboard", status_code=303)

@app.get("/homepage")
def get():
    return generate_themed_page(landing_page)

@app.get("/about")
def get():
    return about_page

@app.get("/privacy-policy")
def get():
    return privacy_policy_page

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
    logger.debug(f"Login attempt for email: {login.email}")
    try:
        u = users[login.email]
        logger.debug(f"User found: {login.email}")
    except Exception as e:
        logger.warning(f"Login failed - user not found: {login.email}")
        return RedirectResponse("/login-form", status_code=303)
    
    if not bcrypt.checkpw(login.pwd.encode("utf-8"), u.pwd.encode("utf-8")):
        logger.warning(f"Login failed - invalid password for user: {login.email}")
        return RedirectResponse("/login-form", status_code=303)
    
    sess["auth"] = u.id
    logger.info(f"User successfully logged in: {login.email}")
    return RedirectResponse("/dashboard", status_code=303)

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
        "pwd": bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    }
    try:
        u = users[email]
        logger.warning(f"Registration failed - email already exists: {email}")
    except Exception:
        u = users.insert(user_data)
        logger.info(f"New user registered: {email}")
    
    sess["auth"] = u.id
    logger.debug(f"Session auth set for new user: {u.id}")
    return RedirectResponse("/", status_code=303)

# -----------------------
# Routes: Dashboard
# -----------------------

@app.get("/dashboard")
def get(req):
    auth = req.scope.get("auth")
    logger.debug(f"Dashboard accessed by user: {auth}")
    
    # Get user's feedback processes
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
        H2("Your Feedback Dashboard"),
        Div(
            H3("Active Feedback Collection"),
            *active_html or P("No active feedback collection processes.", cls="text-muted"),
            Button("Start New Feedback Collection", hx_get="/start-new-feedback-process", hx_target="#main-content", hx_swap="innerHTML")
        ),
        Div(
            H3("Ready for Review"),
            P("No feedback ready for review.", cls="text-muted")
        ),
        Div(
            H3("Completed Reports"),
            completed_html or P("No completed feedback reports.", cls="text-muted")
        )
    )
    return generate_themed_page(dashboard_page_active, auth=auth, page_title="Your Dashboard")


# -----------------------
# Routes: New Feedback Process
# -----------------------

@app.get("/start-new-feedback-process")
def get_new_feedback():
    form = Form(
        Div(
            H2("New Feedback Process"),
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
            *[Div(
                Input(name=f"quality_{q}", type="checkbox", value=q),
                Label(q)
              ) for q in FEEDBACK_QUALITIES]
        ),
        Button("Begin collecting feedback", type="submit", cls="primary")
        , action="/create-new-feedback-process", method="post"
    )

    return Titled("Start New Feedback Process", form)


@app.post("/create-new-feedback-process")
def create_new_feedback_process(peers_emails: str, supervisors_emails: str, reports_emails: str, sess, data: dict):
    logger.debug("create_new_feedback_process called with:")
    logger.debug(f"peers_emails: {peers_emails!r}")
    logger.debug(f"supervisors_emails: {supervisors_emails!r}")
    logger.debug(f"reports_emails: {reports_emails!r}")
    logger.debug(f"Additional form data: {data!r}")
    user_id = sess.get("auth")
    peers = [line.strip() for line in peers_emails.splitlines() if line.strip()]
    supervisors = [line.strip() for line in supervisors_emails.splitlines() if line.strip()]
    reports = [line.strip() for line in reports_emails.splitlines() if line.strip()]
    selected_qualities = [q for q in FEEDBACK_QUALITIES if data.get(f"quality_{q}")]
    process_data = {
        "id": secrets.token_hex(8),
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
    # Create feedback requests for each role.
    for email in peers:
        link = generate_magic_link(email, process_id=process_data["id"])
        token = link.replace("/feedback/submit/", "")
        feedback_request_tb.update({"user_type": "peer"}, token=token)
    for email in supervisors:
        link = generate_magic_link(email, process_id=process_data["id"])
        token = link.replace("/feedback/submit/", "")
        feedback_request_tb.update({"user_type": "supervisor"}, token=token)
    for email in reports:
        link = generate_magic_link(email, process_id=process_data["id"])
        token = link.replace("/feedback/submit/", "")
        feedback_request_tb.update({"user_type": "report"}, token=token)
    return RedirectResponse("/dashboard", status_code=303)

# -----------------------
# Routes: Existing Feedback Process
# -----------------------

@app.get("/feedback-process/{process_id}")
def get_report_status_page(process_id):
    # this should get the page for a specific open feedback process
    # this should show you the detail for any specific process.  At the very top it should show you the status
    # if that status is complete, it should have a link to generate a full report
    # underneath that it should show a list of each feedback request, and the status of each, and the full magic link to send 
    # if  the report exists, it should be at the bottom
    pass

def create_feedback_report_input(process_id):
    # this should query our database, and retrieve the key facts for the feedback report, and output them ready for the LLM to process
    # 1. For each quality, generate the average score and variance
    # 2. Retrieve a list of positive, negative and neutral themes
    # 3. Combine those together into a block of text
    pass

@app.post("/feedback-process/{process_id}/generate_completed_feedback_report")
def create_feeback_report(process_id):
    # this should be the route to generate our final feedback report
    feedback_report_input = create_feedback_report_input(process_id)
    feedback_report = generate_completed_feedback_report(feedback_report_input)

    # once we have the report, we should save it to the database
    pass

# -------------------------------
# Route: Feedback Submission
# -------------------------------
@app.get("/new-feedback-form/{process_id}")
def get_feedback_form(token: str):
    # this is a page for external users to submit feedback. It should show a bit of intro text, and then it should shown the form and a submit button
    # once the feedback is submitted and saved to DB, take them to the thank you page.
    introduction_text = "{first_name} has asked for your feedback"
    
    form = Form(
        Group(
            *[Group(Label(q), Input(type="range", min=1, max=8, value=4, id=f"rating_{q.lower()}"))
              for q in FEEDBACK_QUALITIES],
            Textarea(id="feedback_text", placeholder="Provide detailed feedback...", rows=5, required=True)
        ),
        Button("Submit Feedback", type="submit"),
        hx_post="/feedback/submit",
        hx_target="#feedback-status"
    )
    return Titled("Submit Feedback", form)


@app.get("/feedback-submitted")
def get_feedback_submitted():
    return Titled("Feedback Submitted", P("Thank you for your feedback! It has been submitted successfully. if You'd like to do this to, go to ..."))

@app.post("/new-feedback-form/{process_id}/submit")
def submit_feedback_form(token: str, feedback_text: str, **kwargs):
    # first it takes the form data, and stores it in the database
    # then we pass it to the LLM to generate themes
    feedback_themes = convert_feedback_text_to_themes(feedback_text)
    # then we save the themes to the database
    pass

# -------------
# Start the App
# -------------
if __name__ == "__main__":
    serve()
