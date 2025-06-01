import asyncio
import httpx
from datetime import datetime

BARCHART_URL = "https://www.barchart.com/proxies/core-api/v1/quotes/get"
BARCHART_PARAMS = {
    "lists": "futures.mostActive",
    "raw": "1"
}
NOTION_WEBHOOK_URL = "https://api.notion.com/YOUR_WEBHOOK_ENDPOINT"  # Mets ici ton URL réelle

async def fetch_gold_data():
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(BARCHART_URL, params=BARCHART_PARAMS, timeout=10)
            r.raise_for_status()
            data = r.json()

            gold_data = next((item for item in data["data"] if item["symbol"] == "XAUUSD"), None)
            if not gold_data:
                print("❌ XAUUSD non trouvé")
                return

            payload = {
                "timestamp": datetime.utcnow().isoformat(),
                "symbol": gold_data["symbol"],
                "price": gold_data["lastPrice"],
                "volume": gold_data["volume"]
            }

            response = await client.post(NOTION_WEBHOOK_URL, json=payload)
            print(f"✅ Données envoyées : {payload}")
            response.raise_for_status()
        except Exception as e:
            print(f"❌ Erreur dans fetch_gold_data : {e}")

async def run_worker():
    print("🚀 Worker démarré...")
    while True:
        await fetch_gold_data()
        await asyncio.sleep(30)  # boucle toutes les 30 secondes

if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except Exception as e:
        print(f"❌ Erreur dans main : {e}")
