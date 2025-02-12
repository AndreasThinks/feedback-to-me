# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm

# Install system dependencies including PostgreSQL client
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create and switch to app directory
WORKDIR /app

# Copy only dependency files first
COPY pyproject.toml uv.lock ./

# Copy the rest of the app code (so the Docker image is still runnable without Compose)
COPY . /app

RUN uv sync

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PATH="/venv/bin:$PATH"

# Default port
ENV PORT=8080

# By default, just run the application (without reload)
# You can override this with docker-compose to enable watch mode
CMD ["uv", "run", "main.py"]
