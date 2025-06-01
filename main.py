import asyncio
import httpx
from datetime import datetime

BARCHART_URL = "https://www.barchart.com/proxies/core-api/v1/quotes/get"
BARCHART_PARAMS = {
    "lists": "futures.mostActive",
    "raw": "1",
    "fields": "symbol,lastPrice,tradeTime,lastPriceNetChange,volume"
}
NOTION_WEBHOOK_URL = "https://api.notion.com/your-custom-webhook-url"  # Remplace avec ton vrai webhook

# 🔁 Appelle cette fonction toutes les X minutes
async def fetch_gold_data():
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(BARCHART_URL, params=BARCHART_PARAMS, timeout=10)
            r.raise_for_status()
            data = r.json()
            xau_data = next((item for item in data["data"] if "XAU/USD" in item["symbol"]), None)

            if not xau_data:
                print("❌ Aucune donnée XAU/USD trouvée.")
                return

            price = xau_data["lastPrice"]
            volume = xau_data["volume"]
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            print(f"[{timestamp}] Cours : {price} | Volume : {volume}")

            if float(volume) > 3000:
                await notify_notion(price, volume)

        except Exception as e:
            print(f"⚠️ Erreur lors de la récupération des données : {e}")

# 📤 Envoie une alerte via webhook Notion
async def notify_notion(price, volume):
    payload = {
        "content": f"🚨 Signal sur l’or détecté :\nPrix = {price} $\nVolume = {volume} 🔥"
    }
    headers = {"Content-Type": "application/json"}
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(NOTION_WEBHOOK_URL, json=payload, headers=headers)
            r.raise_for_status()
            print("✅ Notification envoyée.")
        except Exception as e:
            print(f"⚠️ Erreur envoi Notion : {e}")

# 🔁 Boucle principale
async def main():
    print("🚀 Bot lancé")
    while True:
        await fetch_gold_data()
        await asyncio.sleep(300)  # 5 minutes (300 secondes)

if __name__ == "__main__":
    asyncio.run(main())
