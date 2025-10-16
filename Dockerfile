# Dockerfile (for Hugging Face Spaces - Docker)
FROM python:3.10-slim

# System deps for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install requirements first (better caching)
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY . ./

# Ensure scripts are executable
RUN chmod +x /app/start.sh

# HF Spaces provides a $PORT; default to 7860
ENV PORT=7860
ENV PYTHONUNBUFFERED=1

# Run migrations then start the app
CMD ["/bin/bash", "/app/start.sh"]