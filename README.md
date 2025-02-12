# Feedback to Me - 360° Feedback Platform

A modern web application for collecting and analyzing 360° feedback, built with Python and FastHTML.

[![Alpha Version](https://img.shields.io/badge/version-0.9.0_alpha-orange)](https://feedback-to.me)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

![Feedback to Me Screenshot](https://feedback-to.me/static/screenshot.png)

## Features

- 🧑💻 User authentication with email confirmation
- 🔄 360° feedback collection process management
- 📊 AI-powered feedback analysis & report generation
- 💳 Integrated Stripe payments for credit purchases
- 📧 SMTP email integration for notifications
- 📱 Responsive web interface

## Table of Contents
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Development](#development)
- [Testing](#testing)
- [API Documentation](#api-documentation)

## Architecture

```mermaid
graph TD
    A[Client] --> B[Nginx]
    B --> C[FastHTML App]
    C --> D[(PostgreSQL Database)]
    C --> E[Stripe API]
    C --> F[SMTP2GO]
    C --> G[Google Gemini AI]
```

Key Components:
- **Web Server**: FastHTML with Python backend
- **Database**: PostgreSQL (with SQLite fallback for development)
- **AI Processing**: Google Gemini via LangChain integration
- **Payments**: Stripe Checkout integration
- **Email**: SMTP2GO service

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.12+ (for local development without Docker)
- PostgreSQL 15+ (automatically handled by Docker)

### Quick Start with Docker

```bash
# Clone repository
git clone https://github.com/yourusername/feedback-to-me.git
cd feedback-to-me

# Copy environment file and configure
cp .env.example .env

# Start the application with Docker Compose
docker compose up --build

# Initialize the database (first time only)
docker compose exec app python scripts/init_db.py
```

### Local Development without Docker

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies using uv
uv sync

# Set up environment variables
cp .env.example .env
# Edit .env to configure your database connection
```

## Configuration

Edit `.env` file:

```ini
# Core Configuration
DEV_MODE=true
LOG_LEVEL=DEBUG
BASE_URL=http://localhost:8080

# External Services
STRIPE_SECRET_KEY=sk_test_...
SMTP2GO_API_KEY=your_smtp2go_key
GEMINI_API_KEY=your_google_ai_key

# Security
SECRET_KEY=your_random_secret_here
```

Required API Keys:
1. [Stripe](https://dashboard.stripe.com/test/apikeys)
2. [SMTP2GO](https://www.smtp2go.com/settings/api/)
3. [Google AI Studio](https://makersuite.google.com/)

## Deployment to Railway

1. Create a new project on Railway and connect your repository
2. Add a PostgreSQL plugin to your project
3. Deploy your application:

```bash
# Login to Railway
railway login

# Link to your project
railway link

# Deploy the application
railway up
```

The PostgreSQL connection URL will be automatically injected as `DATABASE_URL`.

Production environment features:
- HTTPS via Railway's SSL
- PostgreSQL database with automated backups
- Docker container deployment
- Automated CI/CD pipeline
- Environment variable management
- Monitoring and logging via Railway dashboard

## Development

```bash
# Start development server
make dev

# Run tests
make test

# Generate database schema diagram
python -m eralchemy2 -i sqlite:///data/feedback.db -o docs/erd.png
```

File Structure:
```
├── data/               # Database files
├── static/             # Static assets
├── tests/              # Test suite
├── main.py             # Main application
├── models.py           # Database models
├── pages.py            # UI templates
├── llm_functions.py   # AI processing
└── config.py           # Configuration defaults
```

## Testing

Test payment flow using Stripe test cards:
- Card: 4242 4242 4242 4242
- Exp: Any future date
- CVC: Any 3 digits

```bash
# Run full test suite
pytest tests/ --cov=app --cov-report=html
```
---

**Live Alpha Version**: https://feedback-to.me  
**Support**: contact@feedback-to.me  
**License**: MIT
