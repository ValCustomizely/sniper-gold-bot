import asyncio
import httpx
import os
from datetime import datetime
from bs4 import BeautifulSoup
from notion_client import Client

# Init Notion
notion = Client(auth=os.environ["NOTION_API_KEY"])
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]

async def fetch_gold_data():
    print(f"[fetch_gold_data] ⏳ Début de la récupération à {datetime.utcnow().isoformat()}", flush=True)
    async with httpx.AsyncClient() as client:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0"
            }
            url = "https://www.barchart.com/futures/quotes/GCM25/overview"
            response = await client.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Récupération du prix
            price_tag = soup.select_one("div.quote-header__pricing span.last-price")
            price = float(price_tag.text.strip().replace(",", "")) if price_tag else None

            # Récupération du volume
            volume = None
            for block in soup.select("div.quote-block--field"):
                label = block.select_one("span.quote-block__label")
                if label and "Volume" in label.text:
                    val = block.select_one("span.quote-block__value")
                    if val:
                        volume = int(val.text.strip().replace(",", ""))
                        break

            if price is None or volume is None:
                print("❌ Échec de récupération du prix ou volume", flush=True)
                return

            # Préparation pour Notion
            sl = round(price - 10, 2)
            sl_suiveur = round(price - 5, 2)
            title = f"Signal - {datetime.utcnow().isoformat()}"

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
            print("✅ Signal ajouté à Notion avec prix =", price, "et volume =", volume, flush=True)
        except Exception as e:
            print(f"❌ Erreur attrapée dans fetch_gold_data : {e}", flush=True)

async def main_loop():
    while True:
        print("\n🔁 Tick exécuté", datetime.utcnow().isoformat(), flush=True)
        await fetch_gold_data()
        print("🔕 Tick terminé, pause de 60s", flush=True)
        await asyncio.sleep(60)

if __name__ == "__main__":
    print("\n🚀 Bot en exécution", datetime.utcnow().isoformat(), flush=True)
    try:
        asyncio.run(main_loop())
    except Exception as e:
        print(f"❌ Erreur critique dans le bot principal : {e}", flush=True)
