import asyncio
import httpx
import os
from datetime import datetime
from notion_client import Client

# Initialisation du client Notion
notion = Client(auth=os.environ["NOTION_API_KEY"])
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]

BARCHART_URL = "https://www.barchart.com/proxies/core-api/v1/quotes/get"
BARCHART_PARAMS = {
    "lists": "futures.mostActive",
    "raw": "1",
    "fields": "symbol,lastPrice,tradeTime,lastPriceNetChange,volume"
}

async def fetch_gold_data():
    print(f"[fetch_gold_data] ⏳ Début de la récupération à {datetime.utcnow().isoformat()}", flush=True)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(BARCHART_URL, params=BARCHART_PARAMS, timeout=10)
            response.raise_for_status()
            data = response.json()

            gold = next((item for item in data["data"] if item["symbol"] == "XAUUSD"), None)
            if not gold:
                print("❌ XAUUSD non trouvé dans la réponse", flush=True)
                return

            title = f"Signal - {datetime.utcnow().isoformat()}"
            print(f"✅ Données XAUUSD : {gold}", flush=True)

            # Données fictives pour SL et SL suiveur (tu peux les adapter)
            sl = round(float(gold["lastPrice"]) - 10, 2)
            sl_suiveur = round(float(gold["lastPrice"]) - 5, 2)

            page = notion.pages.create(
                parent={"database_id": NOTION_DATABASE_ID},
                properties={
                    "Signal": {"title": [{"text": {"content": title}}]},
                    "Horodatage": {"date": {"start": datetime.utcnow().isoformat()}},
                    "Prix": {"number": float(gold["lastPrice"] or 0)},
                    "Volume": {"number": int(gold["volume"] or 0)},
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
