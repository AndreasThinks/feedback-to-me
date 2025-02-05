# we use this page for our templates and skins


from fasthtml.common import *

dashboard_page = Container(
    H2("Your Feedback Dashboard"),
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
    H2("Welcome to the Feedback App"),
    Button("Start Collecting Feedback"),
    P("This is a simple app to collect feedback from your team."),
)

navigation_bar_logged_out = Nav(
    Ul(
        Li(Strong(A("Feedback to Me", href="/"))),
    Ul(
        Li(A("About", href="/about")),
        Li(A("Get Started", href="/login-or-register"))
    )),
    cls='navbar'
)

navigation_bar_logged_out = Nav(
    Ul(
        Li(Strong(A("Feedback to Me", href="/")))),
    Ul(
        Li(A("About", href="/about")),
        Li(A("Get Started", href="/login-or-register"))
    ),
    cls='navbar'
)

navigation_bar_logged_in = Nav(
    Ul(
        Li(Strong(A("Feedback to Me", href="/")))),
    Ul(
        Li(A("Dashboard", href="/dashboard")),
        Li(A("About", href="/about")),
        Li(A("Logout", href="/logout"))
    ),
    cls='navbar'
)

footer_bar = Footer(P("© 2021 Feedback App"), cls='footer')

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
    id="login-register-buttons"
))

login_form = Form(
        Group(
            Input(name="email", type="email", placeholder="Email", required=True),
            Input(name="pwd", type="password", placeholder="Password", required=True)
        ),
        Button("Login", type="submit", cls="primary"),
        action="/login", method="post",
    )

register_form = Form(
        Group(
            Input(name="first_name", type="text", placeholder="First Name", required=True),
            Input(name="email", type="email", placeholder="Email", required=True),
            Input(name="role", type="text", placeholder="Role (e.g. Software Engineer)", required=True),
            Input(name="company", type="text", placeholder="Company", required=True),
            Input(name="team", type="text", placeholder="Team", required=True),
            Input(name="pwd", type="password", placeholder="Password", required=True)
        ),
        Button("Register", type="submit", cls="secondary"),
        action="/register-new-user", method="post")
