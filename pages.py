# we use this page for our templates and skins

from fasthtml.common import *

def dashboard_page(user):
    return Container(
        H2(f"Hello {user.first_name}, you have {user.credits} credits remaining"),
        Div(
            H3("Active Feedback Collection"),
            P("No active feedback collection processes.", cls="text-muted"),
            Button("Start New Feedback Collection", hx_get="/start-new-feedback-process", hx_target="#main-content", hx_swap="innerHTML")
        ),
        Div(
            H3("Ready for Review"),
            P("No feedback ready for review.", cls="text-muted")
        ),
        Div(
            H3("Completed Reports"),
            P("No completed feedback reports.", cls="text-muted")
        )
    )

landing_page = Container(
    Div(
         H2("Welcome to Feedback to Me!"),
         P("Discover a revolutionary way to collect and analyze feedback from your team."),
         Ul(
              Li("Easy Account Setup & Secure Login"),
              Li("Launch Dynamic Feedback Campaigns with a Click"),
              Li("Real-Time Submissions & Comprehensive Insights"),
              Li("Empower Your Team with Actionable Analytics")
         ),
         Button("Get Started", href="/login-or-register", cls="btn-primary", hx_get="/login-or-register", hx_target="#main-content", hx_swap="innerHTML"),
         P("Join now and transform the way you gather feedback!"),
         cls="landing-page"
    )
)

navigation_bar_logged_out = Nav(
    Ul(
        Li(Strong(A("Feedback to Me", href="/")))),
    Ul(
        Li(AX("About", href="/about")),
        Li(AX("Get Started", hx_get="/login-or-register", hx_target="#main-content", hx_swap="outerHTML"))
    ),
    cls='navbar'
)

def navigation_bar_logged_in(user):
    return Nav(
        Ul(
            Li(Strong(A("Feedback to Me", href="/")))),
        Ul(
            Li(A("Dashboard", href="/dashboard")),
            Li(A("About", href="/about")),
            Li(Span(f"Credits: {user.credits}")),
            Li(A("Buy Credits", href="/buy-credits")),
            Li(A("Logout", href="/logout"))
        ),
        cls='navbar'
    )

footer_bar = Footer(P("© 2025 Feedback to Me"), cls='footer')

about_page = Container(
    H2("About the Feedback App"),
    P("This is a simple app to collect feedback from your team."),
)

privacy_policy_page = Container(
    H2("Privacy Policy"),
    P("We take your privacy seriously."),
)

login_or_register_page = Container(
    H2("Welcome to Feedback2Me"),
    P("Create an account or login to start collecting feedback."),
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
        hx_post="/login", hx_target="#login-form", hx_swap="beforebegin", id='login-form'
    )

error_message = Container(
    I("We couldn't log you in.")
)

register_form = Form(
            Div(Input(name="first_name", type="text", placeholder="First Name *", required=True)),
            Div(Input(name="email", type="email", placeholder="Email *", required=True)),
            Div(Input(name="pwd", type="password", placeholder="Password *", required=True)),
            Div(Input(name="pwd_confirm", type="password", placeholder="Confirm Password *", required=True)),
            Div(Input(name="role", type="text", placeholder="Role (Optional, e.g. Software Engineer)", required=False)),
            Div(Input(name="company", type="text", placeholder="Company (Optional)", required=False)),
            Div(Input(name="team", type="text", placeholder="Team (Optional)", required=False)),
        Button("Register", type="submit", cls="secondary"),
        action="/register-new-user", method="post",
        cls="registration-form")
