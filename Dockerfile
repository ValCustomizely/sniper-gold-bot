FROM python:3.11-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    wget gnupg unzip curl fonts-liberation libnss3 libatk1.0-0 \
    libatk-bridge2.0-0 libcups2 libxss1 libasound2 libxshmfence1 \
    libgbm1 libx11-xcb1 libgtk-3-0 xvfb && \
    rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m playwright install chromium

# Copy code
COPY . .

# Run the script
CMD ["python", "gold_scraper_render.py"]
