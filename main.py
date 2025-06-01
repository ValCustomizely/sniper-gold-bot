import asyncio
import os
from datetime import datetime
import httpx
from bs4 import BeautifulSoup
from notion_client import Client

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

notion = Client(auth=NOTION_API_KEY)

BARCHART_URL = "https://www.barchart.com/futures/quotes/GCM25/interactive-chart"

async def fetch_gold_data():
    print(f"[{datetime.utcnow()}] ✅ fetch_gold_data exécutée")

    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(BARCHART_URL, timeout=10)
            r.raise_for_status()
        except Exception as e:
            print(f"❌ Erreur HTTP : {e}")
            return

        soup = BeautifulSoup(r.text, "html.parser")

        try:
            price_elem = soup.select_one(".bc-dataview .last-change .last")
            volume_elem = soup.find("span", string="Volume").find_next("span")

            price = float(price_elem.text.replace(",", ""))
            volume = int(volume_elem.text.replace(",", ""))

            print(f"📈 Prix : {price} $ | 🔊 Volume : {volume}")

            await notion.pages.create(
                parent={"database_id": NOTION_DATABASE_ID},
                properties={
                    "Signal": {
                        "title": [{"text": {"content": f"Gold - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}}" }]
                    },
                    "Horodatage": {"date": {"start": datetime.utcnow().isoformat()}},
                    "Prix": {"number": price},
                    "Volume": {"number": volume},
                    "Commentaire": {
                        "rich_text": [{"text": {"content": "Auto-import Barchart"}}]
                    },
                    "SL": {"number": 0},
                    "SL suiveur": {"number": 0}
                }
            )

            print("✅ Données envoyées à Notion.")

        except Exception as e:
            print(f"❌ Erreur parsing/envoi : {e}")

async def main_loop():
    print("✅ Bot démarré")
    while True:
        await fetch_gold_data()
        print("🔁 Tick terminé, en attente...\n")
        await asyncio.sleep(300)  # toutes les 5 minutes

if __name__ == "__main__":
    asyncio.run(main_loop())
