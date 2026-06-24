# Hermes SEO v3 — Image Docker
FROM python:3.12-slim

LABEL org.opencontainers.image.title="Hermes SEO v3"
LABEL org.opencontainers.image.description="Plateforme SEO multi-agent — 8 pipelines, 109+ agents"
LABEL org.opencontainers.image.authors="FC Solutions"
LABEL org.opencontainers.image.version="3.0"

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application
COPY . .

# Create data directories
RUN mkdir -p data logs sessions

EXPOSE 8501

ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
