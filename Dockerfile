# ── Base image (CPU, mock-capable). Build the ML image separately for GPU. ──
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

# ffmpeg for audio demux; libGL/glib for OpenCV.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-deps -e .

# Non-root runtime user.
RUN useradd -m -u 10001 aimw && mkdir -p /app/storage/uploads /app/storage/frames \
    && chown -R aimw:aimw /app/storage
USER aimw

EXPOSE 8000

# Default: run the API. docker-compose overrides command for workers/migrate.
CMD ["uvicorn", "aimw.main:app", "--host", "0.0.0.0", "--port", "8000"]
