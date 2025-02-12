FROM python:3.12-slim-bookworm
# Install Litestream
RUN apt-get update && apt-get install -y wget coreutils
RUN wget https://github.com/benbjohnson/litestream/releases/download/v0.3.13/litestream-v0.3.13-linux-amd64.deb
RUN dpkg -i litestream-v0.3.13-linux-amd64.deb
RUN rm litestream-v0.3.13-linux-amd64.deb

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Sync the project into a new environment, using the frozen lockfile
WORKDIR /app

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

# Setup GCP credentials and data directory
RUN mkdir -p /app/data
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/gcp-credentials.json
RUN echo "$GCP_CREDENTIALS_B64" | base64 -d > $GOOGLE_APPLICATION_CREDENTIALS

# Run the app with Litestream
CMD litestream replicate -config /app/litestream.yml -exec "uv run main.py"
