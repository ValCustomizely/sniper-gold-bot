import asyncio
import httpx
import os
from datetime import datetime
from notion_client import Client

# === ENVIRONNEMENT ===
notion = Client(auth=os.environ["NOTION_API_KEY"])
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
POLYGON_API_KEY = os.environ["POLYGON_API_KEY"]
POLYGON_URL = "https://api.polygon.io/v2/aggs/ticker/C:XAUUSD/prev"

candles = []
VOLUME_SEUIL = 3000
CANDLE_TREND = 3

# === THRESHOLDS ===
def compute_thresholds(candles):
    closes = [c[4] for c in candles[-20:] if isinstance(c, list)]
    highs = [c[2] for c in candles[-20:] if isinstance(c, list)]
    lows  = [c[3] for c in candles[-20:] if isinstance(c, list)]
    if not closes or not highs or not lows:
        return None
    return {
        "support": min(lows),
        "resistance": max(highs),
        "moyenne": sum(closes) / len(closes)
    }

def is_trending(candles):
    if len(candles) < CANDLE_TREND:
        return False
    tendances = ["up" if c[4] > c[1] else "down" for c in candles[-CANDLE_TREND:] if isinstance(c, list)]
    return len(set(tendances)) == 1

def is_breaking(price, thresholds):
    if not thresholds:
        return False
    for level in [thresholds["support"], thresholds["moyenne"], thresholds["resistance"]]:
        if abs(price - level) / level <= 0.005:
            return True
    return False

# === NOTION ===
async def send_to_notion(signal_type, price, volume, commentaire, sl=None, sl_suiveur=None):
    now = datetime.utcnow().isoformat()
    props = {
        "Signal": {"title": [{"text": {"content": signal_type}}]},
        "Horodatage": {"date": {"start": now}},
        "Prix": {"number": float(price)},
        "Volume": {"number": int(volume)},
        "Commentaire": {"rich_text": [{"text": {"content": commentaire}}]}
    }
    if sl is not None:
        props["SL"] = {"number": float(sl)}
    if sl_suiveur is not None:
        props["SL suiveur"] = {"number": float(sl_suiveur)}

    notion.pages.create(parent={"database_id": NOTION_DATABASE_ID}, properties=props)
    print(f"✅ {signal_type} | {price} USD | Vol: {volume}", flush=True)

# === FETCH DATA ===
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

            c = results[0]
            price = c["c"]
            volume = c["v"]
            candle = [datetime.utcnow().timestamp(), price, price, price, price, volume]
            candles.append(candle)
            if len(candles) > 30:
                candles.pop(0)

            seuils = compute_thresholds(candles)
            if not seuils:
                print("❌ Données insuffisantes pour calculer les seuils")
                return

            tendance = is_trending(candles)
            cassure = is_breaking(price, seuils)

            if tendance and cassure and volume > VOLUME_SEUIL:
                direction = "hausse" if price > candles[-1][1] else "baisse"
                signal_label = f"SIGNAL ({direction})"
                sl = seuils["support"] if direction == "hausse" else seuils["resistance"]
                sl_suiveur = round(price - 3, 2) if direction == "hausse" else round(price + 3, 2)
                await send_to_notion(signal_label, price, volume, "Signal via Polygon.io", sl=sl, sl_suiveur=sl_suiveur)
            else:
                await send_to_notion("PAS DE SIGNAL", price, volume, "Volume ou tendance insuffisants")
        except Exception as e:
            print(f"❌ Erreur attrapée dans fetch_gold_data : {e}", flush=True)

# === MAIN LOOP ===
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
