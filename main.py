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

from models import feedback_themes_tb, feedback_submission_tb, users, feedback_process_tb, feedback_request_tb, FeedbackProcess, FeedbackRequest, Login
from pages import dashboard_page, login_or_register_page,register_form, login_form, landing_page, navigation_bar_logged_out, navigation_bar_logged_in, footer_bar, about_page, privacy_policy_page

from llm_functions import convert_feedback_text_to_themes, generate_completed_feedback_report


from config import MIN_PEERS, MIN_SUPERVISORS, MIN_REPORTS, MAGIC_LINK_EXPIRY_DAYS, FEEDBACK_QUALITIES

from utils import beforeware


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
    return uri("new-feedback-form", token=token)

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
def get_report_status_page(process_id : str):
    # Get the feedback process
    try:
        process = feedback_process_tb[process_id]
    except Exception as e:
        logger.warning(f"Feedback process not found: {process_id}")
        return RedirectResponse("/dashboard", status_code=303)
    
    # Get all feedback requests for this process
    requests = feedback_request_tb("process_id=?", (process_id,))
    
    # Get all feedback submissions for this process
    submissions = feedback_submission_tb("process_id=?", (process_id,))
    
    # Count submissions by type
    submission_counts = {
        "peer": len([s for s in submissions if feedback_request_tb[s.requestor_id].user_type == "peer"]),
        "supervisor": len([s for s in submissions if feedback_request_tb[s.requestor_id].user_type == "supervisor"]),
        "report": len([s for s in submissions if feedback_request_tb[s.requestor_id].user_type == "report"])
    }
    
    # Check if we have enough submissions to generate a report
    can_generate_report = (
        submission_counts["peer"] >= process.min_required_peers and
        submission_counts["supervisor"] >= process.min_required_supervisors and
        submission_counts["report"] >= process.min_required_reports and
        not process.feedback_report  # Only if report doesn't exist yet
    )
    
    # Create status sections
    status_section = Article(
        H2("Feedback Process Status"),
        P(f"Process ID: {process.id}"),
        P(f"Created: {process.created_at}"),
        P(f"Status: {'Complete' if process.feedback_report else 'In Progress'}"),
        Div(
            H3("Progress"),
            P(f"Peers: {submission_counts['peer']}/{process.min_required_peers}"),
            P(f"Supervisors: {submission_counts['supervisor']}/{process.min_required_supervisors}"),
            P(f"Reports: {submission_counts['report']}/{process.min_required_reports}")
        )
    )
    
    # Create requests section showing each request and its status
    requests_list = []
    for req in requests:
        # Find matching submission if it exists
        submission = next((s for s in submissions if s.requestor_id == req.token), None)
        
        requests_list.append(
            Article(
                H4(f"{req.user_type.title()} Feedback Request"),
                P(f"Email: {req.email}"),
                P(f"Status: {'Submitted' if submission else 'Pending'}"),
                P("Magic Link: ",
                  A("Click to open feedback form", link=uri("new-feedback-form", process_id=req.token)),
                  " ",
                  Button("Copy", onclick=f"navigator.clipboard.writeText('{uri('new-feedback-form', process_id=req.token)}').then(()=>{{ let btn=this; btn.setAttribute('data-tooltip', 'Copied to clipboard!'); setTimeout(()=>{{ btn.removeAttribute('data-tooltip'); }}, 1000); }});")
                ),
                cls=f"request-{req.user_type}"
            )
        )
    
    requests_section = Article(
        H3("Feedback Requests"),
        *requests_list
    )
    
    # Add report generation button if eligible
    action_section = Div()
    if can_generate_report:
        action_section = Div(
            Button(
                "Generate Feedback Report",
                hx_post=f"/feedback-process/{process_id}/generate_completed_feedback_report",
                hx_target="#report-section"
            )
        )
    
    # Show existing report if it exists
    report_section = Div(id="report-section")
    if process.feedback_report:
        report_section = Article(
            H3("Feedback Report"),
            Div(process.feedback_report, cls="markdown"),
            id="report-section"
        )
    
    return Titled(
        f"Feedback Process {process_id}",
        Container(
            status_section,
            requests_section,
            action_section,
            report_section
        )
    )

def create_feedback_report_input(process_id):
    # Get the feedback process
    process = feedback_process_tb[process_id]
    
    # Get all submissions for this process
    submissions = feedback_submission_tb("process_id=?", (process_id,))
    
    # Calculate statistics for each quality
    quality_stats = {}
    for quality in process.qualities:
        ratings = [s.ratings.get(quality) for s in submissions if quality in s.ratings]
        if ratings:
            avg = sum(ratings) / len(ratings)
            # Calculate variance
            variance = sum((r - avg) ** 2 for r in ratings) / len(ratings)
            quality_stats[quality] = {
                "average": round(avg, 2),
                "variance": round(variance, 2),
                "count": len(ratings)
            }
    
    # Get all themes for this process's feedback
    themes = feedback_themes_tb("feedback_id IN (SELECT id FROM feedback_submission WHERE process_id=?)", (process_id,))
    
    # Group themes by sentiment
    themed_feedback = {
        "positive": [t.theme for t in themes if t.sentiment == "positive"],
        "negative": [t.theme for t in themes if t.sentiment == "negative"],
        "neutral": [t.theme for t in themes if t.sentiment == "neutral"]
    }
    
    # Format the input for the LLM
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
def create_feeback_report(process_id):
    try:
        # Get the process to verify it exists and check status
        process = feedback_process_tb[process_id]
        
        # Verify we have enough submissions
        submissions = feedback_submission_tb("process_id=?", (process_id,))
        submission_counts = {
            "peer": len([s for s in submissions if feedback_request_tb[s.requestor_id].user_type == "peer"]),
            "supervisor": len([s for s in submissions if feedback_request_tb[s.requestor_id].user_type == "supervisor"]),
            "report": len([s for s in submissions if feedback_request_tb[s.requestor_id].user_type == "report"])
        }
        
        if (submission_counts["peer"] < process.min_required_peers or
            submission_counts["supervisor"] < process.min_required_supervisors or
            submission_counts["report"] < process.min_required_reports):
            logger.warning(f"Attempted to generate report without sufficient feedback for process: {process_id}")
            return "Not enough feedback submissions to generate report", 400
        
        # Generate the report input
        feedback_report_input = create_feedback_report_input(process_id)
        
        # Generate the report using the LLM
        feedback_report = generate_completed_feedback_report(feedback_report_input)
        
        # Save the report to the database
        feedback_process_tb.update({"feedback_report": feedback_report}, process_id)
        
        # Return the report section for HTMX to update
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
        hx_post="/new-feedback-form/{process_id}/submit",
        hx_target="#feedback-status"
    )
    return Titled("Submit Feedback", form)


@app.get("/feedback-submitted")
def get_feedback_submitted():
    return Titled("Feedback Submitted", P("Thank you for your feedback! It has been submitted successfully. if You'd like to do this to, go to ..."))

@app.post("/new-feedback-form/{process_id}/submit")
def submit_feedback_form(process_id: str, feedback_text: str, **kwargs):
    try:
        # Get the feedback request to verify token and get process_id
        feedback_request = feedback_request_tb[process_id]
        
        # Create ratings dictionary from form data
        ratings = {}
        for quality in FEEDBACK_QUALITIES:
            rating_key = f"rating_{quality.lower()}"
            if rating_key in kwargs:
                try:
                    ratings[quality] = int(kwargs[rating_key])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid rating value for {quality}: {kwargs[rating_key]}")
                    continue
        
        # Store the feedback submission
        submission_data = {
            "id": secrets.token_hex(8),
            "requestor_id": process_id,
            "provider_id": None,  # Anonymous submission
            "feedback_text": feedback_text,
            "ratings": ratings,
            "process_id": feedback_request.process_id,
            "created_at": datetime.now()
        }
        submission = feedback_submission_tb.insert(submission_data)
        
        # Generate themes using the LLM
        feedback_themes = convert_feedback_text_to_themes(feedback_text)
        if feedback_themes:
            # Store each theme in the database
            for sentiment in ["positive", "negative", "neutral"]:
                for theme in feedback_themes[sentiment]:
                    theme_data = {
                        "id": secrets.token_hex(8),
                        "feedback_id": submission.id,
                        "theme": theme,
                        "sentiment": sentiment,
                        "created_at": datetime.now()
                    }
                    feedback_themes_tb.insert(theme_data)
        
        # Increment the feedback count for the process
        process = feedback_process_tb[feedback_request.process_id]
        feedback_process_tb.update(
            {"feedback_count": process.feedback_count + 1},
            feedback_request.process_id
        )
        
        # Redirect to thank you page
        return RedirectResponse("/feedback-submitted", status_code=303)
        
    except Exception as e:
        logger.error(f"Error submitting feedback: {str(e)}")
        return "Error submitting feedback. Please try again.", 500

# -------------
# Start the App
# -------------
if __name__ == "__main__":
    serve()
