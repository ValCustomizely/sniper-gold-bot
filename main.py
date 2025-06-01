import asyncio
import httpx
import os
from datetime import datetime
from notion_client import Client

# Initialisation du client Notion
notion = Client(auth=os.environ["NOTION_API_KEY"])
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
POLYGON_API_KEY = os.environ["POLYGON_API_KEY"]
POLYGON_URL = "https://api.polygon.io/v2/aggs/ticker/C:XAUUSD/prev"

candles = []  # Historique local pour vérifier la variation de prix

async def fetch_gold_data():
    now = datetime.utcnow()
    print(f"[fetch_gold_data] ⏳ Début de la récupération à {now.isoformat()}", flush=True)

    # ⏱️ Pause pendant les heures de clôture (UTC 21h à 6h)
    if now.hour >= 21 or now.hour < 6:
        print(f"⏸️ Marché fermé (UTC {now.hour}h), tick ignoré", flush=True)
        return

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

            # 🔁 Stockage local pour analyse
            candles.append([now.timestamp(), last_price])
            if len(candles) > 20:
                candles.pop(0)

            # 🧼 Filtrage anti-stagnation (même prix)
            if len(candles) > 1 and last_price == candles[-2][1]:
                print("📉 Prix inchangé, pas de signal envoyé.", flush=True)
                await send_to_notion(last_price, volume, "PAS DE SIGNAL")
                return

            # 📊 Détection simplifiée (seuils fictifs)
            direction = "hausse" if last_price > candles[-2][1] else "baisse"
            sl = round(last_price - 10, 2) if direction == "hausse" else round(last_price + 10, 2)
            sl_suiveur = round(last_price - 5, 2) if direction == "hausse" else round(last_price + 5, 2)
            commentaire = f"SIGNAL ({direction})"

            print(f"✅ {commentaire} | {last_price} USD | Vol: {volume}", flush=True)
            await send_to_notion(last_price, volume, commentaire, sl=sl, sl_suiveur=sl_suiveur)

        except Exception as e:
            print(f"❌ Erreur attrapée dans fetch_gold_data : {e}", flush=True)

async def send_to_notion(price, volume, commentaire, sl=None, sl_suiveur=None):
    now = datetime.utcnow().isoformat()
    props = {
        "Signal": {"title": [{"text": {"content": commentaire}}]},
        "Horodatage": {"date": {"start": now}},
        "Prix": {"number": float(price)},
        "Volume": {"number": int(volume)},
        "Commentaire": {"rich_text": [{"text": {"content": commentaire}}]}
    }
    if "SIGNAL" in commentaire:
        props["SL"] = {"number": sl}
        props["SL suiveur"] = {"number": sl_suiveur}

    notion.pages.create(parent={"database_id": NOTION_DATABASE_ID}, properties=props)
    print("✅ Signal ajouté à Notion", flush=True)

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
