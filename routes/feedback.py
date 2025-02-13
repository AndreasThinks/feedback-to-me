from typing import Optional, Dict, Any
from fasthtml.common import *
import logging
from datetime import datetime
from models import feedback_process_tb, feedback_request_tb, feedback_submission_tb
from services import email_service

logger = logging.getLogger(__name__)

def register_routes(app):
    """
    Register all feedback related routes.
    
    Args:
        app: The FastHTML application instance
    """
    
    @app.get("/dashboard")
    def get_dashboard(req):
        """Display user dashboard with feedback processes"""

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
            A(Button("Start New Feedback Collection"), href="/start-new-feedback-process", cls="collect-feedback-button"),
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

    
    @app.get("/start-new-feedback-process")
    def get_new_feedback(req):
        """Display new feedback process form"""
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

    
    @app.post("/start-new-feedback-process/count")
    def count_submissions(
        peers_emails: str = "",
        supervisors_emails: str = "",
        reports_emails: str = ""
    ):
        """Count and validate submitted emails"""
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
                    P(f"Need {remaining} more to reach the minimum of {MINIMUM_SUBMISSIONS_REQUIRED}."),
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

    
    @app.post("/create-new-feedback-process")
    def create_new_feedback_process(
        process_title: str,
        peers_emails: str,
        supervisors_emails: str,
        reports_emails: str,
        custom_qualities: str,
        sess,
        data: Dict[str, Any]
    ):
        """Create new feedback process"""
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

    
    @app.get("/feedback-process/{process_id}")
    def get_report_status_page(process_id: str, req):
        """Display feedback process status page"""
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
            H3(f"{process.process_title} {' (Complete)' if process.feedback_report else ' (In Progress)'}"),
            P(f"Created: {formatted_date}"),
            Div(opening_text, cls='marked'),
            Div(missing_text) if missing_text else None,
            Div(
                Button("Delete Process", 
                    cls="delete-process-btn",
                    onclick=f"if(confirm('Are you sure you want to delete this entire feedback process? Your credits for pending requests will be refunded, but completed questionnaires will be discarded.')) window.location.href='/feedback-process/{process_id}/delete'"),
                style="margin-top: 1rem;"
            )
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
                            onclick=f"if(confirm('Are you sure you want to delete this feedback request? Your credits will be refunded.')) window.location.href='/feedback-process/{process_id}/delete-request/{feedback_request.token}'")
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
    
    @app.post("/new-feedback-form/{request_token}/submit")
    def submit_feedback_form(request_token: str, feedback_text: str, data: Dict[str, Any]):
        """Handle feedback submission"""
        pass
    
    @app.post("/feedback-process/{process_id}/add-request")
    def add_feedback_request(process_id: str, email: str, role: str, sess):
        """Add new feedback request to process"""
        pass
    
    @app.get("/feedback-process/{process_id}/delete-request/{token}")
    def delete_feedback_request(process_id: str, token: str, sess):
        """Delete feedback request"""
        pass
    
    @app.get("/feedback-process/{process_id}/delete")
    def delete_process(process_id: str, sess):
        """Delete entire feedback process"""
        pass
    
    @app.get("/feedback-process/{process_id}/generate_completed_feedback_report")
    def create_feedback_report(process_id: str):
        """Generate completed feedback report"""
        pass
