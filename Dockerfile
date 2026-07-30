# Use Official Playwright image (includes Python & Browsers)
FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ="Australia/Sydney"

# Install system dependencies
# We need curl for the WAF bypass scraper, and tzdata for correct timezone
# DEBIAN_FRONTEND=noninteractive prevents tzdata from hanging on build
# fonts-dejavu-core supplies the serif/sans faces used to render the branded
# fallback link card for councils whose sites expose no og:image. The base
# image ships only CJK/Thai/emoji fonts, which cannot set a Latin headline.
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    curl \
    tzdata \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Browsers are already included in this base image

# Copy project files
COPY . .

# Create a non-root user for security
RUN useradd -m botuser && chown -R botuser:botuser /app
USER botuser

# Idle container; cron on the host triggers runs via docker compose exec.
CMD ["tail", "-f", "/dev/null"]
