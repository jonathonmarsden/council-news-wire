# Use Python 3.9 slim image for a small footprint
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ="Australia/Sydney"

# Install system dependencies
# We need curl for the WAF bypass scraper
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create a non-root user for security
RUN useradd -m botuser && chown -R botuser:botuser /app
USER botuser

# Run the scheduler
CMD ["python", "scheduler.py"]
