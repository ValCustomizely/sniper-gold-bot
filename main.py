import asyncio
import httpx
import os
from datetime import datetime
from notion_client import Client

# Initialisation du client Notion
notion = Client(auth=os.environ["NOTION_API_KEY"])
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
POLYGON_API_KEY = os.environ["POLYGON_API_KEY"]
POLYGON_URL = "https://api.polygon.io/v2/aggs/ticker/XAUUSD/range/1/minute/2025-06-01/2025-06-01"

async def fetch_gold_data():
    print(f"[fetch_gold_data] ⏳ Début de la récupération à {datetime.utcnow().isoformat()}", flush=True)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(POLYGON_URL, params={
                "adjusted": "true",
                "sort": "desc",
                "limit": 1,
                "apiKey": POLYGON_API_KEY
            }, timeout=10)
            response.raise_for_status()
            results = response.json().get("results", [])

            if not results:
                print("❌ Aucune donnée reçue", flush=True)
                return

            candle = results[0]
            last_price = candle["c"]
            volume = candle["v"]

            print(f"✅ Donnée : {last_price} USD | Volume : {volume}", flush=True)

            sl = round(last_price - 10, 2)
            sl_suiveur = round(last_price - 5, 2)
            title = f"Signal - {datetime.utcnow().isoformat()}"

            notion.pages.create(
                parent={"database_id": NOTION_DATABASE_ID},
                properties={
                    "Signal": {"title": [{"text": {"content": title}}]},
                    "Horodatage": {"date": {"start": datetime.utcnow().isoformat()}},
                    "Prix": {"number": float(last_price)},
                    "Volume": {"number": int(volume)},
                    "Commentaire": {"rich_text": [{"text": {"content": "Signal via Polygon.io"}}]},
                    "SL": {"number": sl},
                    "SL suiveur": {"number": sl_suiveur}
                }
            )
            print("✅ Signal ajouté à Notion", flush=True)

        except Exception as e:
            print(f"❌ Erreur attrapée dans fetch_gold_data : {e}", flush=True)

async def main_loop():
    while True:
        print("\n🔁 Tick exécuté ", datetime.utcnow().isoformat(), flush=True)
        await fetch_gold_data()
        print("🔕 Tick terminé, pause de 60s\n", flush=True)
        await asyncio.sleep(60)

if __name__ == "__main__":
    print("\n🚀 Bot en exécution", datetime.utcnow().isoformat(), flush=True)
    try:
        asyncio.run(main_loop())
    except Exception as e:
        print(f"❌ Erreur critique dans le bot principal : {e}", flush=True)
