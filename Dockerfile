# Utilise l’image Python officielle
FROM python:3.11-slim

# Installe les dépendances système requises par Playwright
RUN apt-get update && \
    apt-get install -y wget gnupg curl unzip fonts-liberation libglib2.0-0 libnss3 libatk-bridge2.0-0 libxss1 libasound2 libx11-xcb1 libxcb1 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libgtk-3-0 && \
    apt-get clean

# Crée le dossier d'app
WORKDIR /app

# Copie les fichiers
COPY . .

# Installe les dépendances Python
RUN pip install --upgrade pip && pip install -r requirements.txt

# Installe Chromium via Playwright
RUN playwright install chromium

# Commande de lancement
CMD ["python", "gold_scraper_render.py"]
