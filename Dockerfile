FROM python:3.11-slim

# Install system ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy application files
COPY . .

# Ensure downloads directory exists with full write permissions
RUN mkdir -p downloads && chmod -R 777 downloads

# Render sets PORT environment variable (default 10000)
ENV PORT=10000
EXPOSE 10000

# Start Uvicorn bound to 0.0.0.0 and dynamic $PORT
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
