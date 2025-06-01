import asyncio
import httpx
from datetime import datetime
import sys

# 🔧 Paramètres
BARCHART_URL = "https://marketdata.websol.barchart.com/getQuote.json"
BARCHART_PARAMS = {
    "apikey": "TA_CLE_API",  # ← Remplace par ta vraie clé
    "symbols": "XAUUSD"
}

NOTION_WEBHOOK_URL = "https://api.notion.com/your_webhook_endpoint"  # ← remplace ici aussi

# ✅ Forcer l'affichage des logs dans Render
sys.stdout.reconfigure(line_buffering=True)

# 📡 Fonction principale
async def fetch_gold_data():
    async with httpx.AsyncClient() as client:
        try:
            print(f"[{datetime.utcnow()}] ⏳ Requête à Barchart...", flush=True)
            r = await client.get(BARCHART_URL, params=BARCHART_PARAMS, timeout=10)
            r.raise_for_status()
            data = r.json()

            gold_data = next((item for item in data["data"] if item["symbol"] == "XAUUSD"), None)
            if not gold_data:
                print("❌ XAUUSD non trouvé dans la réponse Barchart", flush=True)
                return

            payload = {
                "timestamp": datetime.utcnow().isoformat(),
                "symbol": gold_data["symbol"],
                "price": gold_data["lastPrice"],
                "volume": gold_data["volume"]
            }

            print(f"[{datetime.utcnow()}] ✅ Données extraites : {payload}", flush=True)

            response = await client.post(NOTION_WEBHOOK_URL, json=payload)
            response.raise_for_status()
            print(f"[{datetime.utcnow()}] 📬 Données envoyées avec succès", flush=True)

        except Exception as e:
            print(f"[{datetime.utcnow()}] ❌ Erreur dans fetch_gold_data : {e}", flush=True)

# 🔁 Boucle infinie
async def run_bot():
    print("✅ Bot démarré", flush=True)
    while True:
        print(f"[{datetime.utcnow()}] ✅ fetch_gold_data exécutée", flush=True)
        await fetch_gold_data()
        print("🔁 Tick terminé, en attente...\n", flush=True)
        await asyncio.sleep(60)

# ▶️ Lancement
if __name__ == "__main__":
    asyncio.run(run_bot())
