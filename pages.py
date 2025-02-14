# we use this page for our templates and skins

from fasthtml.common import *
from config import BASE_URL, STARTING_CREDITS, COST_PER_CREDIT_USD
from models import users

def generate_themed_page(page_body, auth=None, page_title="Feedback to Me"):
    """Generate a themed page with appropriate navigation bar based on auth status"""
    from main import alpha_mode
    
    nav_bar = navigation_bar_logged_out
    if auth:
        user = users("id=?", (auth,))[0]
        nav_bar = navigation_bar_logged_in(user)
    else:
        nav_bar = navigation_bar_logged_out

    # Add alpha badge to title if in alpha mode
    if alpha_mode:
        page_title = f"{page_title} " "ALPHA"

    # Create alpha banner if in alpha mode
    alpha_elements = []
    if alpha_mode:
        alpha_elements.extend([
            Div("🚧 This site is in alpha testing - please don't use it with sensitive data 🚧", cls="alpha-banner"),
            Div(
                "⚠️ Alpha Testing Notice: This is an early version of Feedback to Me. While functional, it may contain bugs or undergo significant changes. We recommend not using it for critical feedback processes at this time.",
                cls="alpha-warning"
            ) if "landing-page" in str(page_body) else None
        ])

    return (Title(page_title),
    Favicon('static/favicon.ico', dark_icon='static/favicon.ico'),
    Container(
        nav_bar,
        *[el for el in alpha_elements if el is not None],
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

landing_page = Container(
    Div(
        H2("Welcome to Feedback to Me"),
        P("360° feedback, made simple and powered by AI"),
        A(Button("Get Started", href="/get-started", cls="btn-primary"), href='/get-started'),
        P("Join now and create your first report for free!"),
        Div(
            P("Professional development shouldn't be limited by traditional feedback costs. Our advanced AI transforms colleague insights into personalized growth recommendations, making expert development guidance accessible to everyone."),
            H3("✨ What makes us different:"),
            Ul(
                Li("Fast: Get started with just a few email addresses"),
                Li("Impactive: Personalised expert recommendations, bespoke to your needs"),
                Li("Anonymous: Advanced AI agents to make feedback detailed but untrackable"),
                Li("Secure: Store our data in our secure cloud, or host on-premises"),
                Li("Affordable: Start with a free report today"),
                cls="features-list"
            ),
            P("Get valuable insights about your performance and growth areas, all while maintaining complete confidentiality."),
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
                cls="pricing-features"
            ),
            P("Contact us for enterprise pricing and features"),
            A(Button("Contact Sales", href="mailto:sales@feedback-to.me"), href="mailto:sales@feedback-to.me", cls="pricing-cta"),
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
    Div("""
360° feedback is a powerful tool for personal and professional development. By collecting insights from peers, supervisors, and reports, you get a comprehensive view of your strengths and areas for growth.

## Our Process

1. **Initial Setup**
   - Create your account
   - Choose the qualities you want feedback on
   - Enter email addresses for your feedback providers

2. **Feedback Collection**
   - We send personalized survey links to your chosen participants
   - Each participant provides anonymous ratings and written feedback
   - Our AI ensures all feedback remains anonymous by removing identifying details

3. **AI-Powered Analysis**
   - Once enough responses are collected, our AI analyzes the feedback
   - We identify common themes and patterns
   - Statistical analysis shows how different groups perceive your performance

4. **Comprehensive Report**
   - Receive a detailed report with actionable insights
   - View aggregated ratings across different qualities
   - See anonymized themes from written feedback
   - Get specific recommendations for growth

## Privacy & Security

Your privacy and data security are our top priorities. All feedback is anonymized, and we use enterprise-grade encryption to protect your information. Learn more in our [Privacy Policy](/privacy-policy).

## Credit System

- Start with free credits for your first feedback process
- Purchase additional credits as needed
- One credit = one feedback request
- Credits never expire

## Support

Need help? Check our [FAQ](/faq) for common questions or contact our support team.
    """, cls="marked"),
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

We share data only with:
- Essential service providers (e.g., payment processors)
- When legally required
- With your explicit consent

We never sell your data to third parties.

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
- Email: privacy@feedback-to.me
- Address: [Company Address]
- Data Protection Officer: dpo@feedback-to.me

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
            "answer": "Your feedback data is securely stored and used solely to generate meaningful, actionable feedback reports. We do not share your data with third parties."
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
            "question": "Can I update or change my feedback?",
            "answer": "Once feedback is submitted, it is used to generate a report. For any modifications, please contact our support team."
        },
        {
            "question": "What if I experience technical issues?",
            "answer": "Our support team is available to assist you. Please reach out through our contact page if you encounter any problems."
        },
        {
            "question": "Are there any costs associated?",
            "answer": "During our alpha testing phase, the service is free. Future pricing details will be available on our pricing page."
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
                    cls="faq-answer",
                    style="display:none;"
                )
            )
            for item in faq_items
        ],
        cls="faq-container"
    )
    return generate_themed_page(faq_content, page_title="FAQ")
