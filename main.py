import asyncio
import httpx
import os
from datetime import datetime
from notion_client import Client
from bs4 import BeautifulSoup

# Notion
notion = Client(auth=os.environ["NOTION_API_KEY"])
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]

# URL de Barchart
BARCHART_URL = "https://www.barchart.com/futures/quotes/GCM25/overview"

async def fetch_gold_data():
    print(f"[fetch_gold_data] ⏳ Début de la récupération à {datetime.utcnow().isoformat()}", flush=True)
    headers = {"User-Agent": "Mozilla/5.0"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(BARCHART_URL, headers=headers, timeout=10)
            
        # Récupération du volume
        volume = None
        for label in soup.select("div.quote-block--field"):
            label_text = label.select_one("span.quote-block__label")
            if label_text and "Volume" in label_text.text:
                value = label.select_one("span.quote-block__value")
                if value:
                    volume = int(value.text.strip().replace(",", ""))
                    break


            if not price or not volume:
                print("❌ Données manquantes sur la page HTML", flush=True)
                return

            print(f"✅ Données extraites : Prix = {price} / Volume = {volume}", flush=True)

            sl = round(price - 10, 2)
            sl_suiveur = round(price - 5, 2)

            title = f"Signal - {datetime.utcnow().isoformat()}"

            # Envoi vers Notion
            notion.pages.create(
                parent={"database_id": NOTION_DATABASE_ID},
                properties={
                    "Signal": {"title": [{"text": {"content": title}}]},
                    "Horodatage": {"date": {"start": datetime.utcnow().isoformat()}},
                    "Prix": {"number": price},
                    "Volume": {"number": volume},
                    "Commentaire": {"rich_text": [{"text": {"content": "Signal automatique envoyé par le bot."}}]},
                    "SL": {"number": sl},
                    "SL suiveur": {"number": sl_suiveur}
                }
            )

            print("✅ Signal ajouté à Notion avec succès", flush=True)

        except Exception as e:
            print(f"❌ Erreur attrapée dans fetch_gold_data : {e}", flush=True)

async def main_loop():
    while True:
        print("🔁 Tick commencé à", datetime.utcnow().isoformat(), flush=True)
        await fetch_gold_data()
        print("✅ Tick terminé, en attente 60s", flush=True)
        await asyncio.sleep(60)

if __name__ == "__main__":
    print("\n🚀 Bot en exécution", datetime.utcnow().isoformat(), flush=True)
    try:
        asyncio.run(main_loop())
    except Exception as e:
        print(f"❌ Erreur critique dans le bot principal : {e}", flush=True)
