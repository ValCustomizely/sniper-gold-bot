import asyncio
import httpx
import os
from datetime import datetime
from notion_client import Client

notion = Client(auth=os.environ["NOTION_API_KEY"])
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
POLYGON_API_KEY = os.environ["POLYGON_API_KEY"]
POLYGON_URL = "https://api.polygon.io/v2/aggs/ticker/C:XAUUSD/prev"

candles = []

def compute_thresholds(candles):
    closes = [c[4] for c in candles[-20:]]
    highs = [c[2] for c in candles[-20:]]
    lows = [c[3] for c in candles[-20:]]
    support = min(lows)
    resistance = max(highs)
    return support, resistance

def is_trending(candles):
    if len(candles) < 3:
        return False
    directions = ["up" if c[4] > c[1] else "down" for c in candles[-3:]]
    return all(d == directions[0] for d in directions)

async def fetch_gold_data():
    print(f"[fetch_gold_data] ⏳ Début de la récupération à {datetime.utcnow().isoformat()}", flush=True)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(POLYGON_URL, params={
                "adjusted": "true",
                "apiKey": POLYGON_API_KEY
            }, timeout=10)
            response.raise_for_status()
            results = response.json().get("results", [])
            if not results:
                print("❌ Aucune donnée reçue", flush=True)
                return

            candle = results[0]
            last_price = candle["c"]
            high = candle["h"]
            low = candle["l"]
            open_ = candle["o"]
            volume = candle["v"]
            close = candle["c"]

            now = datetime.utcnow()
            new_candle = [now.timestamp() * 1000, open_, high, low, close, volume]
            candles.append(new_candle)
            if len(candles) > 20:
                candles.pop(0)

            signal = "PAS DE SIGNAL"
            sl = None
            sl_suiveur = None

            trending = is_trending(candles)
            support, resistance = compute_thresholds(candles)
            breaking = abs(last_price - support) / support <= 0.005 or abs(last_price - resistance) / resistance <= 0.005

            if trending and breaking and volume > 3000:
                if last_price > open_:
                    signal = "SIGNAL (hausse)"
                    sl = round(support, 2)
                    sl_suiveur = round(last_price - 3, 2)
                else:
                    signal = "SIGNAL (baisse)"
                    sl = round(resistance, 2)
                    sl_suiveur = round(last_price + 3, 2)

            notion.pages.create(
                parent={"database_id": NOTION_DATABASE_ID},
                properties={
                    "Signal": {"title": [{"text": {"content": signal}}]},
                    "Horodatage": {"date": {"start": now.isoformat()}},
                    "Prix": {"number": float(last_price)},
                    "Volume": {"number": int(volume)},
                    "Commentaire": {"rich_text": [{"text": {"content": "Détection via Polygon.io"}}]},
                    **({"SL": {"number": sl}} if sl is not None else {}),
                    **({"SL suiveur": {"number": sl_suiveur}} if sl_suiveur is not None else {})
                }
            )
            print(f"✅ {signal} | {last_price} USD | Vol: {volume}", flush=True)

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
