FROM python:3.10-slim

ENV TZ=Asia/Singapore \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps (libspatialindex for rtree, tzdata for timezone)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tzdata \
        libspatialindex-dev \
        curl && \
    ln -fs /usr/share/zoneinfo/$TZ /etc/localtime && \
    dpkg-reconfigure --frontend noninteractive tzdata && \
    rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install Python deps first (cached unless pyproject.toml changes)
COPY pyproject.toml .
RUN uv pip install --system -r pyproject.toml

# Copy application code
COPY . /app

EXPOSE 10667 18888

CMD ["python", "/app/app.py", "--fps", "100"]
