FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for PostGIS, Pillow, Exiv2, ffmpeg
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    ffmpeg \
    libexiv2-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast python package management
RUN pip install uv

COPY pyproject.toml ./
RUN uv pip install --system -e .[dev]

COPY . .

EXPOSE 8000
CMD ["fastapi", "dev", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]
