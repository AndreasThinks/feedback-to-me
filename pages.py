# we use this page for our templates and skins

from fasthtml.common import *
from config import BASE_URL, STARTING_CREDITS, COST_PER_CREDIT_USD
from models import users


def generate_themed_page(page_body, auth=None, page_title="Feedback to Me"):
    """Generate a themed page with appropriate navigation bar based on auth status"""
    from main import beta_mode

    
    nav_bar = navigation_bar_logged_out
    if auth:
        user = users("id=?", (auth,))[0]
        nav_bar = navigation_bar_logged_in(user)
    else:
        nav_bar = navigation_bar_logged_out

    beta_elements = []
    if beta_mode:
        beta_elements.extend([
            Div(
                "⚠️ Beta Testing Notice: This is an early version of Feedback to Me. While functional, it may contain bugs or undergo significant changes. We recommend not using it for critical feedback processes at this time.",
                cls="alpha-warning"
            ) if "landing-page" in str(page_body) else None
        ])

    return (Title(page_title),
    Favicon('static/favicon.ico', dark_icon='static/favicon.ico'),
    Container(
        nav_bar,
        *[el for el in beta_elements if el is not None],
        Div(page_body, id="main-content"),
        footer_bar
    ))

def dashboard_page(user):
    return Container(
        H2(f"Hello {user.first_name}, you have {user.credits} credits remaining"),
        Div(
            H3("Collecting responses"),
            P("No active feedback collection processes.", cls="text-muted"),
            Button("Start New Feedback Collection", hx_get="/start-new-feedback-process", hx_target="#main-content", hx_swap="innerHTML"),
        ),
        Div(
            H3("Report ready to generate"),
            P("No feedback ready for review.", cls="text-muted")
        ),
        Div(
            H3("Completed Reports"),
            P("No completed feedback reports.", cls="text-muted")
        )
    )

intro_paragraph = """Professional development shouldn't be a privilege. While top organizations have dedicated teams for feedback and growth, most professionals lack access to these valuable insights.

Feedback to Me democratizes professional development with AI-powered 360° feedback. Our platform combines anonymous feedback collection with intelligent analysis to deliver actionable, personalized insights that help you grow—all while ensuring complete confidentiality."""

landing_page = Container(
    Div(
        H2("Peer-to-peer feedback, reimagined"),
        P("Your personal 360° feedback team, powered by AI"),
        A(Button("Start Free", href="/get-started", cls="btn-primary"), href='/get-started'),
        P("Create your first feedback report at no cost"),
        Div(
            Div(intro_paragraph, cls='marked'),
            Div(
                Video(
                    Source(src="/static/feedback-to-me.mp4", type="video/mp4"),
                    controls=True,
                    muted=False,
                    loop=True,
                    preload="auto"
                ),
                cls="video-embed"
            ),
            H3("Why Choose Feedback to Me"),
            Ul(
                Li("Smart Insights: AI-driven analysis for actionable recommendations"),
                Li("Complete Privacy: Anonymous feedback collection and secure processing"),
                Li("Enterprise Ready: ", A("Cloud-based or on-premises deployments available", href="/pricing", style='margin-left: 5px;')),
                Li("Accessible: Start with a free report, scale as you grow"),
                Li("Open source: ", A("Open code, MIT licensed", href="https://github.com/AndreasThinks/feedback-to-me", style='margin-left: 5px;')),
                cls="features-list"
            ),
            P("Get the insights you need to excel, with the privacy everyone deserves."),
            cls="content-section"
        ),
        cls="landing-page"
    )
)

pricing_page = Container(
    Div(
        Div(
            H3("Individual Feedback"),
            P(f"Start with {STARTING_CREDITS} free credits to try the service"),
            P("Our process is simple:"),
            Ul(
                Li("1. Create your account and get your free credits"),
                Li("2. Enter email addresses for your feedback providers"),
                Li("3. Each feedback request uses 1 credit"),
                Li("4. Get your comprehensive AI-powered feedback report"),
                cls="pricing-features"
            ),
            P(f"Additional credits: ${COST_PER_CREDIT_USD} per feedback request"),
            A(Button("Get Started", href="/get-started"), href="/get-started", cls="pricing-cta"),
            cls="pricing-tier individual"
        ),
        Div(
            H3("Business Solutions"),
            P("Unlock organization-wide insights"),
            Ul(
                Li("Custom feedback processes for teams"),
                Li("Aggregated insights across departments"),
                Li("Advanced analytics and reporting"),
                Li("Dedicated support and training"),
                Li("Hybrid cloud and on-premises hosting options"),
                cls="pricing-features"
            ),
            P("Contact us for enterprise pricing and features"),
            A(Button("Contact Sales", href="mailto:contact@feedback-to.me"), href="mailto:contact@feedback-to.me", cls="pricing-cta"),
            cls="pricing-tier business"
        ),
        cls="pricing-container"
    )
)

navigation_bar_logged_out = Nav(
    Ul(
        Li(Strong(A("Feedback to Me", href="/")))),
    Ul(
        Li(AX("How It Works", href="/how-it-works")),
        Li(AX("Pricing", href="/pricing")),
        Li(AX("FAQ", href="/faq")),
        Li(AX("Get Started", href='/get-started'))
    ),
    cls='navbar'
)

def navigation_bar_logged_in(user):
    nav_items = [
        Li(A("Dashboard", href="/dashboard")),
        Li(A("How It Works", href="/how-it-works")),
        Li(A("Pricing", href="/pricing")),
        Li(AX("FAQ", href="/faq")),
    ]
    
    if user.is_admin:
        nav_items.append(Li(A("Admin", href="/admin")))
    
    nav_items.append(Li(A("Logout", href="/logout")))
    
    return Nav(
        Ul(Li(Strong(A("Feedback to Me", href="/")))),
        Ul(*nav_items),
        cls='navbar'
    )

footer_bar = Footer(A("© 2025 Feedback to Me"), href=BASE_URL, cls='footer')

how_it_works_page = Container(
    Div(
        Div(
            Video(
                Source(src="/static/feedback-to-me.mp4", type="video/mp4"),
                controls=True,
                muted=False,
                loop=True,
                preload="auto"
            ),
            cls="video-embed"
        ),
        H2("Expert insights in 3 simple steps", style=f"font-size: 2.8rem; color: var(--nord10); text-align: center; margin: 2rem 0 3rem; letter-spacing: -0.5px;"),
        Div(
            # Step 1
            Div(
                Div(
                    Video(
                        Source(src="/static/process_1.mp4", type="video/mp4"),
                        controls=True,
                        muted=True,
                        loop=True,
                        preload="false",
                        cls="process-video"
                    ),
                    cls="process-image"
                ),
                Div(
                    H3("Create your request", style=f"color: var(--nord10);"),
                    Ul(
                        Li("Register to create your free feedback process"),
                        Li("Enter the email of colleagues you'd like to get feedback from"),
                        Li("We recommend a mix of roles and seniority levels, but it's up to you"),
                        Li("Select which categories you'd like to be graded on, or enter your own"),
                        cls="features-list"
                    ),
                    cls="process-content"   
                ),
                cls="process-step"
            ),
            # Step 2
            Div(
                Div(
                    Video(
                        Source(src="/static/process_2.mp4", type="video/mp4"),
                        controls=True,
                        muted=True,
                        loop=True,
                        preload="false",
                        cls="process-video"
                    ),
                    cls="process-image"
                ),
                Div(
                    H3("Collect your feedback", style=f"color: var(--nord10);"),
                    Ul(
                        Li("We generate a unique survey for each participant"),
                        Li("Simply click the button to copy the unique link, and send it to your colleague"),
                        Li("Or just press the send email button, and we'll send it for you"),  
                        Li("Now just wait! Don't worry, we'll email you when you're ready to continue"),  
                        cls="features-list"
                    ),
                    cls="process-content"
                ),
                cls="process-step"
            ),
            # Step 3
            Div(
                Div(
                    Video(
                        Source(src="/static/process_3.mp4", type="video/mp4"),
                        controls=True,
                        muted=True,
                        loop=True,
                        preload="false",
                        cls="process-video"
                    ),
                    cls="process-image"
                ),
                Div(
                    H3("Generate your report", style=f"color: var(--nord10);"),
                    Ul(
                        Li("Once your submissions are complete, click the button to generate your report"),
                        Li("Our AI agents will review every submission, extracting themes and feedback"),
                        Li("Finally, our reasoning agent will review every all your materials, and generate your expert report"),
                        cls="features-list"
                    ),
                    cls="process-content"
                ),
                cls="process-step"
            ),
            cls="process-container"
        ),
        cls="how-it-works-page"
    )
)

privacy_policy_page = Container(
    H2("Privacy Policy"),
    Div("""
## Introduction

At Feedback to Me, we take your privacy seriously and are committed to protecting your personal data. This Privacy Policy explains how we collect, use, and safeguard your information in compliance with GDPR and other applicable data protection laws.

## Data We Collect

### Account Information
- Name and email address
- Optional: Company, role, and team information
- Password (encrypted)
- Account creation date

### Feedback Process Data
- Email addresses of feedback providers
- Feedback responses and ratings
- Generated feedback reports
- Usage statistics

## How We Use Your Data

### Essential Processing
- Account management and authentication
- Sending feedback requests
- Generating feedback reports
- Processing payments
- Service communications
- Improving our processes and AI models
- Enhancing service quality and user experience

### Legal Basis (GDPR Article 6)
- Contract fulfillment for service provision
- Legitimate interests for service improvement
- Consent for marketing communications
- Legal obligations for financial records

## Data Protection

### Security Measures
- Enterprise-grade encryption
- Regular security audits
- Secure data centers
- Access controls and monitoring

### Data Retention
- Account data: Until account deletion
- Feedback data: 24 months
- Payment records: As required by law
- Marketing preferences: Until consent withdrawal

## Your Rights

Under GDPR, you have the right to:
- Access your personal data
- Correct inaccurate data
- Request data deletion
- Restrict processing
- Data portability
- Object to processing
- Withdraw consent

## Data Sharing

We maintain strict control over your data:
- We never sell your data to third parties
- Your feedback is only accessible by our internal team
- Limited sharing only with:
  - Essential service providers (e.g., payment processors)
  - When legally required
  - With your explicit consent

## Cookies & Tracking

We use essential cookies for:
- Authentication
- Security
- Basic analytics

## International Transfers

Data is processed in the EU/EEA with appropriate safeguards for any international transfers.

## Changes to Policy

We'll notify you of significant policy changes via email and website notices.

## Contact Us

For privacy inquiries or to exercise your rights:
- Email: contact@feedback-to.me
- Address: [Apologies, awaiting!]
- Data Protection Officer: contact@feedback-to.me

Last updated: February 2025
    """, cls="marked"),
)

login_or_register_page = Container(
    P("Create an account or login to start collecting feedback.", id='login-intro-text', cls='login-intro-text'),
    Div(
        Button("Login", hx_get="/login-form", hx_target="#login-register-buttons"),
        Button("Register", hx_get="/register", hx_target="#login-register-buttons"),
        id="login-register-buttons",
        style="display: flex; justify-content: center; gap: 20px; margin-top: 20px;"
    )
)

login_form = Form(
            Input(name="email", type="email", placeholder="Email", required=True),
            Input(name="pwd", type="password", placeholder="Password", required=True),
            Button("Login", type="submit", cls="primary"),
            P(A("Forgot Password?", href="/forgot-password")),
            hx_post="/login", hx_target="#login-intro-text", id='login-form'
    )

error_message = Div(
    I("We couldn't log you in... Are your details are correct?"), cls='login-error-message'
)

register_form = Form(
            Div(
                Input(name="first_name", type="text", placeholder="First Name *", required=True),
                Div(id="first-name-validation", role="alert")
            ),
            Div(
                Input(name="email", type="email", placeholder="Email *", required=True,
                      hx_post="/validate-registration-email",
                      hx_trigger="change delay:300ms",
                      hx_target="#email-validation"),
                Div(id="email-validation", role="alert")
            ),
            Div(
                Input(name="pwd", type="password", placeholder="Password *", required=True,
                      hx_post="/validate-password",
                      hx_trigger="keyup changed delay:300ms",
                      hx_target="#password-verification-status",
                      hx_swap='outerHTML'),
                Article(
                    Progress(value="0", max="100", id="pwd-strength"),
                    Div(id="password-validation", role="alert"),
                id='password-verification-status'),
            ),
            Div(
                Input(name="pwd_confirm", type="password", placeholder="Confirm Password *", required=True,
                      hx_post="/validate-password-match",
                      hx_trigger="keyup changed delay:300ms",
                      hx_target="#pwd-match-validation",
                      hx_include="[name='pwd']"),
                Div(id="pwd-match-validation", role="alert")
            ),
            Button("Register", type="submit", cls="secondary", id="register-btn"),
            P("The below is only helpful if you're taking part in a corporate process"),
            Div(Input(name="role", type="text", placeholder="Role (Optional, e.g. Software Engineer)", required=False)),
            Div(Input(name="company", type="text", placeholder="Company (Optional)", required=False)),
            Div(Input(name="team", type="text", placeholder="Team (Optional)", required=False)),
            P(
                "By registering, you consent to our processing of your data as described in our ",
                A("Privacy Policy", href="/privacy-policy"),
                ". We ensure your data is handled securely and in compliance with GDPR.",
                cls="privacy-consent"
            ),
        action="/register-new-user", method="post",
        cls="registration-form")

def faq_page():
    """Generate the FAQ page with collapsible sections about Feedback to Me."""
    faq_items = [
        {
            "question": "What is Feedback to Me?",
            "answer": "Feedback to Me is a platform that streamlines 360 feedback processes using AI and custom surveys to generate comprehensive reports."
        },
        {
            "question": "How do I start a feedback process?",
            "answer": "Simply sign up, enter the emails of your peers, supervisors, and reportees, and our system will take care of sending surveys and compiling the feedback."
        },
        {
            "question": "How is my feedback anonymised?",
            "answer": "All feedback is collected anonymously. Individual responses are processed without revealing the identity of those who provided the feedback."
        },
        {
            "question": "Who can view my feedback?",
            "answer": "Only you and designated administrators can view your full feedback report once the process is complete."
        },
        {
            "question": "What happens to my feedback data?",
            "answer": "Your feedback data is securely stored and used to generate meaningful, actionable feedback reports. We also use this data to improve our processes and AI models to enhance the service quality. However, we never sell your data or share it with third parties - your feedback will only ever be accessible by our internal team."
        },
        {
            "question": "How does the report generation work?",
            "answer": "We use advanced AI models to analyze the collected feedback and generate a detailed report that highlights strengths and areas for improvement."
        },
        {
            "question": "Is my data secure?",
            "answer": "Yes, we employ industry-standard security practices, including encryption, to ensure that your data remains safe and confidential."
        },
        {
            "question": "What if I experience technical issues?",
            "answer": "Our support team is available to assist you. Please [reach out to our team](mailto:contact@feedback-to.me) if you encounter any problems."
        },
        {
            "question": "Who built Feedback to Me?",
            "answer": "Feedback to Me was built by [Andreas Varotsis](https://andreasthinks.me/)"
        }
    ]
    faq_content = Div(
        *[
            Div(
                Div(
                    H2(item["question"]),
                    cls="faq-question",
                    onclick="this.nextElementSibling.style.display = (this.nextElementSibling.style.display === 'none' ? 'block' : 'none');"
                ),
                Div(
                    item["answer"],
                    cls="marked faq-answer",
                    style="display:none;"
                )
            )
            for item in faq_items
        ],
        cls="faq-container"
    )
    return generate_themed_page(faq_content, page_title="FAQ")
