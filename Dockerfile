FROM python:3.10-slim

ENV TZ=Asia/Singapore \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps (libspatialindex for rtree, tzdata for timezone)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tzdata \
        libspatialindex-dev && \
    ln -fs /usr/share/zoneinfo/$TZ /etc/localtime && \
    dpkg-reconfigure --frontend noninteractive tzdata && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app

EXPOSE 10667 8888

CMD ["python", "/app/app.py", "--fps", "100"]
