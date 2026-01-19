FROM python:3.11-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY main.py .
COPY init-user.py .
COPY entrypoint.sh .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Create data directory
RUN mkdir -p /data/storage /data/metadata

# Expose port
EXPOSE 8547

# Set log level to WARNING (only show warnings and errors)
ENV UVICORN_LOG_LEVEL=warning

# Run application with entrypoint
CMD ["./entrypoint.sh"]
