FROM python:3.12-slim

# Runtime deps: libpq5 for psycopg, ffmpeg for video processing,
# postgresql-client-16 for backup/restore (pg_dump/pg_restore) — pulled from the
# official PGDG repo since Debian bookworm only ships client v15 (too old for a
# v16 server).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    ffmpeg \
    gosu \
    curl \
    gnupg \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client-16 \
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
RUN chmod +x /app/docker-entrypoint.sh && cp /app/docker-entrypoint.sh /usr/local/bin/postmarked-entrypoint

USER root
ENTRYPOINT ["postmarked-entrypoint"]
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
