import os
import asyncio
import datetime
import httpx
from notion_client import Client

# === ENV ===
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
GOLD_API_URL = os.getenv("GOLD_API_URL", "https://www.barchart.com/proxies/core-api/v1/quotes/get?symbols=GCM25")
SCRAPER_INTERVAL = int(os.getenv("SCRAPER_INTERVAL", "60"))
VOLUME_THRESHOLD = 3000
CANDLE_COUNT = 3

notion = Client(auth=NOTION_TOKEN)
candles = []

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

# === Notion logger ===
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

# === Scraper JSON ===
async def fetch_gold_data():
    print("⏳ Récupération JSON...")
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(GOLD_API_URL, headers=headers, timeout=15)
            response.raise_for_status()
            print("🪵 Réponse brute :", response.text[:300])
            return response.json()
        except Exception as e:
            print("❌ Erreur fetch_gold_data :", e)
            return None

# === Main loop ===
async def scrape_loop():
    print("▶️ Boucle démarrée avec intervalle", SCRAPER_INTERVAL, "sec")
    while True:
        data = await fetch_gold_data()
        if not data:
            await asyncio.sleep(SCRAPER_INTERVAL)
            continue

        try:
            quote = data.get("data", [{}])[0]
            price = float(quote.get("lastPrice", 0))
            volume = float(quote.get("volume", 0))

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

# === Entry point ===
if __name__ == "__main__":
    print("=== DEMARRAGE gold_scraper_render.py ===")
    asyncio.run(scrape_loop())
