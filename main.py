import os
import time
import asyncio
import httpx
from datetime import datetime

BARCHART_URL = "https://www.barchart.com/proxies/core-api/v1/quotes/get"
BARCHART_PARAMS = {
    "lists": "futures.mostActive",
    "raw": "1",
    "fields": "symbol,lastPrice,tradeTime,lastPriceNetChange,volume"
}
NOTION_WEBHOOK_URL = os.getenv("NOTION_WEBHOOK_URL", "https://api.notion.com/your-custom-webhook-url")
SCRAPER_INTERVAL = int(os.getenv("SCRAPER_INTERVAL", "300"))  # en secondes

async def fetch_gold_data():
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(BARCHART_URL, params=BARCHART_PARAMS, timeout=10)
            r.raise_for_status()
            data = r.json()

            # Filtrer le XAU/USD
            gold_data = next((item for item in data["data"] if item["symbol"] == "XAUUSD"), None)
            if not gold_data:
                print("❌ XAUUSD non trouvé")
                return

            # Envoie du message au webhook
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

async def main_loop():
    print("✅ Bot démarré")
    while True:
        print(f"⏳ Tick à {datetime.utcnow().isoformat()}")
        await fetch_gold_data()
        await asyncio.sleep(SCRAPER_INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("🛑 Arrêt manuel du bot")
