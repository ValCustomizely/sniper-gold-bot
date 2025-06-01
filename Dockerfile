FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget gnupg unzip curl fonts-liberation libnss3 libatk1.0-0 \
    libatk-bridge2.0-0 libcups2 libxss1 libasound2 libxshmfence1 \
    libgbm1 libx11-xcb1 libgtk-3-0 xvfb && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser
RUN python -m playwright install chromium

# Copy code
COPY . .

# Default command
CMD ["python", "gold_scraper_render.py"]
