# 360 Feedback Application

A web application for collecting peer feedback using FastHTML and SQLite.

## Features
- Magic link authentication
- Anonymous feedback submission
- Feedback report generation
- Role-based access control

## Installation
```bash
pip install -r requirements.txt
```

## Configuration
1. Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
2. Generate a secure secret key:
```bash
echo "SECRET_KEY=$(openssl rand -hex 32)" >> .env
```
3. Initialize database directory:
```bash
mkdir -p data
```

## Running
```bash
python main.py
```

## API Endpoints
| Endpoint              | Method | Description                  |
|-----------------------|--------|------------------------------|
| `/register`           | POST   | User registration            |
| `/magic/link`         | GET    | Generate magic link          |
| `/feedback/submit/{token}` | GET | Feedback form          |
| `/report/{user_id}`   | GET    | Generate feedback report     |

## Testing
```bash
pytest tests/ -v
```

## Deployment
Production deployment with Gunicorn:
```bash
pip install gunicorn
gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

## License
MIT
