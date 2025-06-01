import os
import asyncio
import datetime
import httpx
from notion_client import Client

# === ENV ===
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
SCRAPER_INTERVAL = int(os.getenv("SCRAPER_INTERVAL", "60"))

notion = Client(auth=NOTION_TOKEN)
candles = []
CANDLE_COUNT = 3
VOLUME_THRESHOLD = 3000

# === FONCTION DATA BARCHART API ===
async def fetch_gold_data():
    url = "https://www.barchart.com/proxies/core-api/v1/quotes/get"
    params = {"symbols": "GCM25", "fields": "lastPrice,volume"}
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params)
        data = r.json()
        last = float(data["data"][0]["lastPrice"])
        vol = float(data["data"][0]["volume"])
        return last, vol

# === TECHNICAL RULES ===
def compute_thresholds(candles):
    closes = [float(c[4]) for c in candles[-20:]]
    highs = [float(c[2]) for c in candles[-20:]]
    lows = [float(c[3]) for c in candles[-20:]]
    resistance = max(highs)
    support = min(lows)
    moving_avg = sum(closes) / len(closes)
    return [support, moving_avg, resistance]

def is_trending(candles):
    if len(candles) < CANDLE_COUNT:
        return False
    directions = ["up" if c[4] > c[1] else "down" for c in candles[-CANDLE_COUNT:]]
    return all(d == directions[0] for d in directions)

def is_breaking(price, thresholds):
    return any(abs(price - level) / level <= 0.005 for level in thresholds)

# === NOTION LOGGING ===
async def send_to_notion(price, volume, commentaire, sl=None, sl_suiveur=None):
    now = datetime.datetime.utcnow().isoformat()
    props = {
        "Horodatage": {"date": {"start": now}},
        "Prix": {"number": price},
        "Volume": {"number": volume},
        "Signal": {"title": [{"text": {"content": commentaire}}]}
    }
    if sl is not None:
        props["SL"] = {"number": sl}
    if sl_suiveur is not None:
        props["SL suiveur"] = {"number": sl_suiveur}
    notion.pages.create(parent={"database_id": NOTION_DATABASE_ID}, properties=props)
    print(f"✅ {now} | {price} USD | Vol {volume} | {commentaire}")

# === SCRAPER LOOP ===
async def scrape_loop():
    print(f"▶️ Boucle démarrée avec intervalle {SCRAPER_INTERVAL} sec")
    while True:
        try:
            print("⏳ Récupération des données...")
            price, volume = await fetch_gold_data()

            now = datetime.datetime.utcnow()
            candle = [now.timestamp() * 1000, price, price, price, price, volume]
            candles.append(candle)
            if len(candles) > 20:
                candles.pop(0)

            thresholds = compute_thresholds(candles)
            trending = is_trending(candles)
            breaking = is_breaking(price, thresholds)

            if trending and breaking and volume > VOLUME_THRESHOLD:
                direction = "hausse" if price > candles[-1][1] else "baisse"
                sl = thresholds[0] if direction == "hausse" else thresholds[2]
                sl_suiveur = price - 3 if direction == "hausse" else price + 3
                await send_to_notion(price, volume, f"SIGNAL ({direction})", sl=sl, sl_suiveur=sl_suiveur)
            else:
                await send_to_notion(price, volume, "PAS DE SIGNAL")

        except Exception as e:
            print("❌ Erreur dans la boucle :", e)

        await asyncio.sleep(SCRAPER_INTERVAL)

if __name__ == "__main__":
    print("=== DEMARRAGE gold_scraper_render.py ===")
    asyncio.run(scrape_loop())
