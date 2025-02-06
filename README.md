# Feedback to Me

Feedback to Me is a web application built with FastHTML, designed to collect 360° feedback and provide dynamic functionality including user registration, feedback processing, and an integrated Stripe payment flow for purchasing additional credits.

This README has been updated to reflect the latest features and to guide developers on how to run and test the application locally.

---

## Features

- **User Registration & Confirmation:**  
  Users can register for the app, receive an email with a confirmation token, and then log in. When running in development mode (DEV_MODE enabled), new users are automatically confirmed.

- **Feedback Collection:**  
  The app allows users to start new feedback processes by entering emails for peers, supervisors, and reports. It manages feedback requests, submissions, and calculates summaries based on quality ratings and themes.

- **Dashboard:**  
  After logging in, users are presented with a dashboard that shows active feedback processes, ready items for review, completed reports, and their remaining credits.

- **Stripe Payment Integration:**  
  Users are allocated a start amount of credits. They can purchase additional credits via a "Buy Credits" page. The payment flow uses Stripe Checkout in test mode so that you can simulate transactions without spending real money.

- **Dynamic URL Generation with BASE_URL Override:**  
  A custom helper `base_uri` is implemented which uses an environment variable `BASE_URL` (e.g., an ngrok URL) so that all generated links and redirects use a secure public URL when testing locally.

---

## Setup

1. **Clone the Repository:**  
   Clone the project to your local machine.

2. **Environment Variables:**  
   Create a `.env` file in the project root and configure the following variables:
   
   - `DEV_MODE` (set to `true` for development if you want automatic confirmation of users)  
   - `LOG_LEVEL` (e.g., `DEBUG` or `INFO`)  
   - `STRIPE_SECRET_KEY` (your Stripe test secret key)  
   - `BASE_URL` (set this to your public URL when using ngrok, for example: `https://abcdef.ngrok.io`)  
   - Stripe and SMTP2GO specific variables:
     - `SMTP2GO_EMAIL_ENDPOINT`
     - `SMTP2GO_API_KEY`
   - Other configuration values can be set in `config.py` via environment variables such as:
     - `MIN_PEERS`, `MIN_SUPERVISORS`, `MIN_REPORTS`
     - `STARTING_CREDITS`
     - `COST_PER_CREDIT_USD`
     - `MAGIC_LINK_EXPIRY_DAYS`
     - `FEEDBACK_QUALITIES`

3. **Dependencies:**  
   Install required packages:
   ```bash
   pip install -r requirements.txt
   ```
   _Note: If there is no requirements.txt file, ensure you have installed packages like `python-fasthtml`, `uvicorn`, `bcrypt`, and `stripe`._

4. **Database Setup:**  
   The app uses a MiniDataAPI compliant database. By default, the sample setup uses SQLite. Make sure the necessary tables are created, or check the logging for any errors on initial run.

---

## Running the Application

To run the application locally, execute:

```bash
python main.py
```

This will start the FastHTML server on the default port (8080). You can view the application in your browser at [http://localhost:8080](http://localhost:8080).

---

## Testing Locally with ngrok

Since Stripe requires HTTPS for payment redirection, you can test your integration locally with ngrok:

1. **Install ngrok:**  
   Download ngrok from [ngrok.com](https://ngrok.com/download) and install it on your system.

2. **Start Your Local Server:**  
   Run your FastHTML server on port 8080:
   ```bash
   python main.py
   ```

3. **Launch ngrok Tunnel:**  
   Open a separate terminal, and run:
   ```bash
   ngrok http 8080
   ```
   ngrok will generate a public HTTPS URL (e.g., `https://abcdef.ngrok.io`).

4. **Configure BASE_URL:**  
   In your `.env` file, set:
   ```
   BASE_URL=https://abcdef.ngrok.io
   ```
   This ensures that all generated URLs in your app (including those used in the payment flow) use the ngrok URL.

5. **Test Payment Flow:**  
   - Navigate to the ngrok URL using your browser.  
   - Log in and go to the "Buy Credits" page.  
   - Initiate a purchase using Stripe’s test card details (e.g., card number `4242 4242 4242 4242`, any future expiry date, and any CVC).  
   - Complete the transaction and check that the payment-success route updates your credits appropriately.

---

## Stripe Integration in Test Mode

The app uses Stripe Checkout for processing credit purchases:
- When a user submits the "Buy Credits" form, the `/create-checkout-session` route creates a Stripe Checkout session.
- The success and cancel URLs are generated using the `base_uri` helper, ensuring that if `BASE_URL` is set, they point to your ngrok URL.
- On a successful payment, Stripe redirects the user to the `/payment-success` route, where the app retrieves the session information, updates the user's credits, and shows a success message.
- Ensure you are using Stripe's test keys and test card numbers for testing.

---

## Further Development

- **Routes and Beforeware:**  
  The app uses FastHTML’s routing mechanism and beforeware to manage authentication and dynamic content rendering.
- **Feedback Processing:**  
  The feedback module supports creating new feedback processes, sending out magic link emails, and generating detailed feedback reports.
  
For more details, please refer to the documentation in the `docs/` directory and additional inline comments in `main.py` and `config.py`.

---

Happy coding!
