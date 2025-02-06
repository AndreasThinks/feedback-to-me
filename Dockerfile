FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Sync the project into a new environment, using the frozen lockfile
WORKDIR /app

# Copy the environment variables file (if exists)
COPY .env ./

COPY pyproject.toml ./

COPY uv.lock ./

RUN uv sync --frozen

# Copy the environment variables file (if exists)

# Install dependencies using uv
RUN uv sync

# Copy the rest of the application code
COPY . .

# Set environment variables for Cloud Run
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

# Run the app (uses .env automatically)
CMD ["uv", "run", "main.py"]
