#!/usr/bin/env python
from fasthtml.common import *
from datetime import datetime, timedelta
import secrets, os
import bcrypt

# ----------------------
# Configuration Settings
# ----------------------
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from a .env file

# These configuration values are now sourced from environment variables with defaults given below.
MIN_PEERS = int(os.getenv("MIN_PEERS", "3"))
MIN_SUPERVISORS = int(os.getenv("MIN_SUPERVISORS", "1"))
MAGIC_LINK_EXPIRY_DAYS = int(os.getenv("MAGIC_LINK_EXPIRY_DAYS", "14"))
# Number of reports (people who report) defaults to 0
NUMBER_OF_REPORTS = int(os.getenv("NUMBER_OF_REPORTS", "0"))
FEEDBACK_QUALITIES = os.getenv("FEEDBACK_QUALITIES", "Communication,Leadership,Technical Skills,Teamwork,Problem Solving").split(",")

# -------------------------
# Database and Schema Setup
# -------------------------
db = database("data/feedback.db")
# Users table: using email as unique identifier
from dataclasses import dataclass
from typing import Dict, List, Optional
from llm_functions import process_feedback
@dataclass
class User:
    id: str
    email: str
    role: str
    company: str
    team: str
    created_at: datetime
    pwd: str

users = db.create(User, pk="email")  # Use email as primary key for simpler login

# Feedback table: stores feedback submissions
@dataclass
class Feedback:
    id: str
    requestor_id: str
    provider_id: str  # May be None for anonymous submissions
    feedback_text: str
    ratings: dict     # Expected to be a JSON-like dict for quality ratings
    process_id: str    # UUID linking to FeedbackProcess table
    created_at: datetime

feedback_tb = db.create(Feedback, pk="id")

# Themes table: stores extracted themes from feedback
@dataclass
class Theme:
    id: str
    feedback_id: str
    theme: str
    sentiment: str  # 'positive', 'negative', or 'neutral'
    created_at: datetime

themes_tb = db.create(Theme, pk="id")

# FeedbackProcess table: tracks the overall feedback collection process
@dataclass
class FeedbackProcess:
    id: str
    user_id: str
    created_at: datetime
    min_required_peers: int
    min_required_supervisors: int
    min_required_reports: int
    feedback_count: int
    status: str  # 'collecting', 'ready', 'generated'

feedback_process_tb = db.create(FeedbackProcess, pk="id")

# FeedbackRequest table: stores feedback request tokens linked to a feedback process.
@dataclass
class FeedbackRequest:
    token: str
    email: str
    process_id: Optional[str]  # Link back to FeedbackProcess; may be None for standalone requests.
    expiry: datetime
    feedback_text: Optional[str] = None  # Filled when feedback is submitted.
    ratings: Optional[dict] = None       # Filled with rating scores when feedback is submitted.


feedback_request_tb = db.create(FeedbackRequest, pk="token")

# ----------------------------------
# Utility Functions and Business Logic
# ----------------------------------
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
        "feedback_text": None,
        "ratings": None
    })
    return f"/feedback/submit/{token}"

# ------------------------------
# FastHTML Beforeware for Auth
# ------------------------------
def auth_before(req, sess):
    """
    Beforeware function to inject 'auth' from session into request scope.
    Also attaches a filter on feedback_tb based on requestor_id.
    """
    auth = req.scope["auth"] = sess.get("auth", None)
    if not auth:
        return RedirectResponse("/login", status_code=303)
    # Limit feedback visibility to the authenticated user
    feedback_tb.xtra(requestor_id=auth)

beforeware = Beforeware(auth_before, skip=[r'/login', r'/register', r'/magic/.*', r'/feedback/submit/.*', r'/static/.*'])

# --------------------
# FastHTML App Setup
# --------------------
app, rt = fast_app(
    before=beforeware,
    hdrs=(
        MarkdownJS(),  # Allows rendering markdown in feedback text, if needed.
        Style(f":root {{ --min-peers: {MIN_PEERS}; --min-supervisors: {MIN_SUPERVISORS}; }}")
    ),
    exception_handlers={HTTPException: lambda req, exc: Response(content="", status_code=exc.status_code, headers=exc.headers)}
)

# -----------------------
# Route: User Registration
# -----------------------
@rt("/register")
def post_register(email: str, role: str, company: str, team: str, pwd: str, sess):
    if "auth" in sess:
        del sess["auth"]
    user_data = {
        "id": secrets.token_hex(16),
        "email": email,
        "role": role,
        "company": company,
        "team": team,
        "created_at": datetime.now(),
        "pwd": bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    }
    try:
        u = users[email]
    except Exception:
        u = users.insert(user_data)
    sess["auth"] = u.id
    raise HTTPException(status_code=303, headers={"Location": f"/magic/link?email={email}"})

# -----------------------
# Route: Generate Magic Link (Feedback Request)
# -----------------------
@rt("/magic/link")
def get_magic(email: str):
    link = generate_magic_link(email)
    return Titled(
        title="Magic Link Generated",
        content=[
            P("Share this Feedback Request link with your feedback providers:"),
            P(link)
        ]
    )

# -------------------------------
# Route: Feedback Submission (GET)
# -------------------------------
@rt("/feedback/submit/{token}")
def get_feedback_submit(token: str):
    try:
        record = magic_links_tb[token]
    except Exception:
        record = None
    if record and record["expiry"] > datetime.now():
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
        return Titled(title="Submit Feedback", content=form)
    else:
        return Titled(
            title="Invalid or Expired Link",
            content=P("This Feedback Request link is invalid or has expired.")
        )

# -------------------------------
# Route: Feedback Submission (POST)
# -------------------------------
@rt("/feedback/submit")
def post_feedback(feedback_text: str, sess, **kwargs):
    """Stores a submitted feedback under a FeedbackProcess."""
    ratings = {}
    for quality in FEEDBACK_QUALITIES:
        rating_key = f"rating_{quality.lower()}"
        if rating_key in kwargs:
            ratings[quality] = int(kwargs[rating_key])
    processes = feedback_process_tb("user_id=? AND status=? ORDER BY created_at DESC LIMIT 1", (sess.get("auth"), 'collecting'))
    if not processes:
        return Titled(
            title="No Active Feedback Process",
            content=P("There is no active feedback collection process. Please create a new process first.")
        )
    process = processes[0]
    feedback_data = {
        "id": secrets.token_hex(16),
        "requestor_id": sess.get("auth"),
        "provider_id": None,
        "feedback_text": feedback_text,
        "ratings": ratings,
        "process_id": process.id,
        "created_at": datetime.now()
    }
    feedback = feedback_tb.insert(feedback_data)
    new_count = process.feedback_count + 1
    update_data = {"feedback_count": new_count}
    total_required = process.min_required_peers + process.min_required_supervisors + process.min_required_reports
    if new_count >= total_required:
        update_data["status"] = "ready"
    feedback_process_tb.update(update_data, process.id)
    themes_result = process_feedback(feedback_text)
    if themes_result:
        for sentiment, theme_list in themes_result.items():
            sentiment_type = sentiment.replace('_themes', '')
            for theme in theme_list:
                theme_data = {
                    "id": secrets.token_hex(16),
                    "feedback_id": feedback.id,
                    "theme": theme,
                    "sentiment": sentiment_type,
                    "created_at": datetime.now()
                }
                themes_tb.insert(theme_data)
    return Titled(
        title="Feedback Submitted",
        content=P("Thank you for your feedback! It has been processed and themes have been extracted.")
    )

# ------------------------------
# Route: Feedback Report Generation (Feedback Report)
# ------------------------------
@rt("/feedback/report/{process_id}")
def get_report(process_id: str, auth):
    try:
        process = feedback_process_tb[process_id]
    except Exception:
        return Titled("Process Not Found", P("No feedback process found for the given ID."))
    if process.user_id != auth:
        return Titled(
            title="Access Denied",
            content=P("You are not allowed to view this Feedback Report.")
        )
    return Titled(
            title="Feedback Report",
            content=P("Feedback Report contents would be generated here.")
        )

# ------------------------------
# Basic Login and Logout Routes
# ------------------------------
@rt("/login")
def get_login():
    login_form = Form(
        H2("Login to Feedback2Me"),
        P("Enter your credentials to access your feedback dashboard.", style="margin-bottom: 2rem;"),
        Group(
            Input(name="email", type="email", placeholder="Email", required=True),
            Input(name="pwd", type="password", placeholder="Password", required=True)
        ),
        Button("Login", type="submit", cls="primary"),
        action="/login", method="post",
        style="margin-bottom: 2rem;"
    )
    register_form = Form(
        H2("New to Feedback2Me?"),
        P("Create an account to start collecting feedback.", style="margin-bottom: 2rem;"),
        Group(
            Input(name="email", type="email", placeholder="Email", required=True),
            Input(name="role", type="text", placeholder="Role (e.g. Software Engineer)", required=True),
            Input(name="company", type="text", placeholder="Company", required=True),
            Input(name="team", type="text", placeholder="Team", required=True),
            Input(name="pwd", type="password", placeholder="Password", required=True)
        ),
        Button("Register", type="submit", cls="secondary"),
        action="/register", method="post",
        style="margin-bottom: 2rem;"
    )
    styles = Style("""
        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
        }
        form {
            background: var(--pico-card-background-color);
            padding: 2rem;
            border-radius: 8px;
            margin-bottom: 2rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h2 {
            margin-top: 0;
            color: var(--pico-color-primary);
        }
        .primary {
            background: var(--pico-color-primary);
            color: white;
        }
        .secondary {
            background: var(--pico-color-secondary);
            color: white;
        }
        .big-button {
            display: inline-block;
            padding: 1rem 2rem;
            font-size: 1.5rem;
            margin-bottom: 2rem;
            background: var(--pico-color-primary);
            color: white;
            text-decoration: none;
            border-radius: 8px;
            text-align: center;
        }
        .big-button:hover {
            background: var(--pico-color-primary-hover);
        }
    """)
    return Title("Login"), styles, Container(login_form, register_form)

@dataclass
class Login:
    email: str
    pwd: str

@rt("/login")
def post_login(login: Login, sess):
    try:
        u = users[login.email]
    except Exception:
        return RedirectResponse("/login", status_code=303)
    if not bcrypt.checkpw(login.pwd.encode("utf-8"), u.pwd.encode("utf-8")):
        return RedirectResponse("/login", status_code=303)
    sess["auth"] = u.id
    return RedirectResponse("/", status_code=303)

@rt("/logout")
def get_logout(sess):
    if "auth" in sess:
        del sess["auth"]
    return RedirectResponse("/login", status_code=303)

# ------------------------------
# Route: Home Dashboard
# ------------------------------
@rt("/")
def get_home(req):
    if not req.scope.get("auth"):
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    auth = req.scope.get("auth")
    top_bar = Div(
        A("Log out", href="/logout", cls="top-link"),
        cls="top-bar",
        style="padding: 1rem; background-color: #f0f0f0; text-align: right;"
    )
    processes_collecting = feedback_process_tb("user_id=? AND status=?", (auth, 'collecting'))
    processes_ready = feedback_process_tb("user_id=? AND status=?", (auth, 'ready'))
    processes_generated = feedback_process_tb("user_id=? AND status=?", (auth, 'generated'))
    def process_item(process):
        status_cls = {
            'collecting': 'yellow',
            'ready': 'green',
            'generated': 'blue'
        }.get(process.status, '')
        created_at = process.created_at
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        total_required = process.min_required_peers + process.min_required_supervisors + process.min_required_reports
        return Li(
            Div(
                H3(f"Process from {created_at.strftime('%B %d, %Y')}"),
                P(f"Status: ", Span(process.status.title(), cls=f"pill {status_cls}")),
                P(f"Feedback received: {process.feedback_count} / {total_required}"),
                A("View Details", href=f"/feedback/process/{process.id}/status", cls="button"),
                cls="report-item"
            )
        )
    main_content = Div(
        H1("Your Feedback Dashboard", style="font-size: 2.5rem; margin-bottom: 1rem;"),
        A("Start a new feedback process", href="/feedback/process/new", cls="big-button"),
        Div(
            H2("Collecting Feedback Process", style="color: var(--pico-color-yellow)"),
            (Ul(*[process_item(p) for p in processes_collecting], id="collecting-ul") if processes_collecting else Ul(id="collecting-ul")),
            H2("Ready for Feedback Report", style="color: var(--pico-color-green)"),
            (Ul([process_item(p) for p in processes_ready]) if processes_ready else P("No processes ready for report generation")),
            H2("Generated Feedback Reports", style="color: var(--pico-color-blue)"),
            (Ul([process_item(p) for p in processes_generated]) if processes_generated else P("No generated reports")),
            id="reports-list",
            cls="reports-section"
        ),
        cls="main-content",
        style="text-align: left; padding: 2rem;"
    )
    styles = Style("""
        .report-item { 
            border: 1px solid var(--pico-color-gray); 
            padding: 1rem; 
            margin-bottom: 1rem; 
            border-radius: 8px;
        }
        .pill {
            padding: 0.2rem 0.8rem;
            border-radius: 1rem;
            font-size: 0.9rem;
            font-weight: bold;
        }
        .pill.yellow { background: var(--pico-color-yellow); color: black; }
        .pill.green { background: var(--pico-color-green); color: white; }
        .pill.blue { background: var(--pico-color-blue); color: white; }
    """)
    container = Container(top_bar, main_content, id="page")
    return Title("Feedback Dashboard"), styles, container

# ------------------------------
# Route: Create New Feedback Process
# ------------------------------
@rt("/feedback/process/new")
def get_process_new():
    """Display the form to create a new feedback process"""
    form = Form(
        H2("Start a New Feedback Process"),
        P(f"You'll need at least {MIN_PEERS} peers and {MIN_SUPERVISORS} supervisor to begin collecting feedback."),
        Fieldset(
            Legend(f"Peers (minimum {MIN_PEERS} required)"),
            Input(name="peers", type="text", placeholder="Enter peer emails separated by commas", required=True)
        ),
        Fieldset(
            Legend(f"Supervisors (minimum {MIN_SUPERVISORS} required)"),
            Input(name="supervisors", type="text", placeholder="Enter supervisor emails separated by commas", required=True)
        ),
        Fieldset(
            Legend("Subordinates (optional)"),
            Input(name="subordinates", type="text", placeholder="Enter subordinate emails separated by commas")
        ),
        Button("Create Feedback Process", type="submit"),
        action="/feedback/process/create",
        method="post"
    )
    return Titled("New Feedback Process", Container(form))

@rt("/feedback/process/create")
def post_process_new(auth, peers: str, supervisors: str, subordinates: str = ""):
    """Create a new feedback process and generate feedback requests"""
    # Split and validate the email lists
    peer_list = [x.strip() for x in peers.split(",") if x.strip()]
    supervisor_list = [x.strip() for x in supervisors.split(",") if x.strip()]
    subordinate_list = [x.strip() for x in subordinates.split(",") if x.strip()]
    
    errors = []
    if len(peer_list) < MIN_PEERS:
        errors.append(f"At least {MIN_PEERS} peers are required. You provided {len(peer_list)}.")
    if len(supervisor_list) < MIN_SUPERVISORS:
        errors.append(f"At least {MIN_SUPERVISORS} supervisor is required. You provided {len(supervisor_list)}.")
    
    if errors:
        return Titled("Error Creating Process", Container(
            H2("Cannot Create Feedback Process"),
            P(" ".join(errors)),
            A("Try Again", href="/feedback/process/new", cls="button")
        ))
    
    # Create the feedback process
    process_data = {
        "id": secrets.token_hex(16),
        "user_id": auth,
        "created_at": datetime.now(),
        "min_required_peers": MIN_PEERS,
        "min_required_supervisors": MIN_SUPERVISORS,
        "min_required_reports": NUMBER_OF_REPORTS,
        "feedback_count": 0,
        "status": "collecting"
    }
    process = feedback_process_tb.insert(process_data)
    
    # Generate magic links (feedback requests) for each contact
    magic_links = []
    for email in peer_list + supervisor_list + subordinate_list:
        link = generate_magic_link(email)
        magic_links.append((email, link))
    
    # Redirect the user to the process detail page (status view)
    return RedirectResponse(f"/feedback/process/{process.id}/status", status_code=303)

# ------------------------------
# Route: Feedback Report Generation (Feedback Report)
# ------------------------------
@rt("/feedback/report/{process_id}/generate")
def post_feedback_report_generate(process_id: str, auth):
    try:
        process = feedback_process_tb[process_id]
        if process.user_id != auth:
            return Titled(
                title="Access Denied",
                content=P("You are not allowed to generate this Feedback Report.")
            )
        if process.status != 'ready':
            return Titled(
                title="Cannot Generate Feedback Report",
                content=P("This process cannot generate a report yet. Please wait until enough feedback is collected.")
            )
        feedbacks = feedback_tb("process_id=?", (process_id,))
        all_themes = []
        for feedback in feedbacks:
            themes = themes_tb("feedback_id=?", (feedback.id,))
            all_themes.extend(themes)
        theme_groups = {
            'positive': [],
            'negative': [],
            'neutral': []
        }
        for theme in all_themes:
            theme_groups[theme.sentiment].append(theme.theme)
        all_scores = {}
        for feedback in feedbacks:
            for quality, score in feedback.ratings.items():
                if quality not in all_scores:
                    all_scores[quality] = []
                all_scores[quality].append(score)
        avg_scores = { quality: sum(scores) / len(scores) for quality, scores in all_scores.items() }
        content = [
            H2("Feedback Summary"),
            H3("Scores", style="color: var(--pico-color-blue)"),
            Ul([Li(f"{quality}: {score:.1f}/8") for quality, score in avg_scores.items()]),
            H3("Key Strengths", style="color: var(--pico-color-green)"),
            Ul([Li(theme) for theme in theme_groups['positive']]) if theme_groups['positive'] else P("No specific strengths highlighted"),
            H3("Areas for Growth", style="color: var(--pico-color-yellow)"),
            Ul([Li(theme) for theme in theme_groups['negative']]) if theme_groups['negative'] else P("No specific areas for growth highlighted"),
            H3("Other Observations", style="color: var(--pico-color-gray)"),
            Ul([Li(theme) for theme in theme_groups['neutral']]) if theme_groups['neutral'] else P("No neutral observations")
        ]
        feedback_process_tb.update({"status": "generated"}, process_id)
        return Div(*content, id="report-content")
    except Exception as e:
        return Titled(
            title="Error Generating Feedback Report",
            content=P(f"An error occurred while generating the report: {str(e)}")
        )

@rt("/feedback/process/{process_id}/status")
def get_process_status(process_id: str, auth):
    try:
        process = feedback_process_tb[process_id]
    except Exception:
        return Titled("Process Not Found", P("No feedback process found for the given ID."))
    if process.user_id != auth:
        return Titled("Access Denied", P("You are not allowed to view this process."))
    # Retrieve feedback submissions for this process
    feedbacks = feedback_tb("process_id=?", (process_id,))
    total_required = process.min_required_peers + process.min_required_supervisors + process.min_required_reports
    received = process.feedback_count
    pending = total_required - received
    details_section = Div(
        H2("Process Details"),
        P(f"Process ID: {process.id}"),
        P(f"Created at: {process.created_at}"),
        P(f"Status: {process.status.capitalize()}"),
        P(f"Feedback received: {received} / {total_required}"),
        P(f"Pending feedback requests: {pending}")
    )
    feedback_list = Ul(*[Li(
        P(f"Feedback from: {fb.provider_id if fb.provider_id else 'Anonymous'}"),
        P(f"Feedback: {fb.feedback_text}")
    ) for fb in feedbacks]) if feedbacks else P("No feedback submitted yet.")
    page_content = Div(details_section, H2("Feedback Submissions"), feedback_list)
    return Titled("Process Details", page_content)

# -------------
# Start the App
# -------------
if __name__ == "__main__":
    serve()
