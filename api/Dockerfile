FROM python:3.12-slim

# Runtime deps: libpq5 for psycopg, ffmpeg for video processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser

WORKDIR /app
ENV PYTHONPATH=/app

RUN pip install uv

COPY pyproject.toml ./
# Install production dependencies only (excludes [dev] extras)
RUN uv pip install --system .

COPY . .
RUN chown -R appuser:appuser /app

USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
