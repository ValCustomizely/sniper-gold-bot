import os
import json
import asyncio
import websockets
import datetime
from notion_client import Client

# === Paramètres ===
PAIR = "XAUUSDT"
THRESHOLD_LEVELS = [1300, 1387, 1285]
VOLUME_THRESHOLD = 3000
CANDLE_COUNT = 3
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
NOTION_TOKEN = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

print(f"TOKEN utilisé : {NOTION_TOKEN}")
notion = Client(auth=NOTION_TOKEN)
candles = []

def is_trending(candles):
    if len(candles) < CANDLE_COUNT:
        return False
    directions = ["up" if c[4] > c[1] else "down" for c in candles[-CANDLE_COUNT:]]
    return all(d == directions[0] for d in directions)

def is_breaking(price):
    return any(abs(price - level) / level <= 0.005 for level in THRESHOLD_LEVELS)

def analyze_candle(candle):
    timestamp = datetime.datetime.fromtimestamp(candle[0]/1000)
    open_, high, low, close, volume = map(float, candle[1:6])
    return [timestamp, open_, high, low, close, volume]

async def send_alert(price, volume, direction):
    print("\n📢 SIGNAL SNIPER DÉTECTÉ !")
    print(f"Prix = {price} $/oz")
    print(f"Volume : {volume}")
    print(f"Tendance : {direction} sur {CANDLE_COUNT} bougies")
    print(f"Heure : {datetime.datetime.now().strftime('%H:%M:%S')}\n")
    await send_to_notion(price, volume, "SIGNAL")

async def send_to_notion(price, volume, commentaire):
    now = datetime.datetime.utcnow().isoformat()
    notion.pages.create(
        parent={"database_id": NOTION_DATABASE_ID},
        properties={
            "Horodatage": {"date": {"start": now}},
            "Prix": {"number": price},
            "Volume": {"number": volume},
            "Commentaire": {"title": [{"text": {"content": commentaire}}]}
        }
    )
    print(f"✅ Envoyé : {price} USD | Vol: {volume} | {commentaire}")

async def watch():
    uri = f"wss://stream.binance.com:9443/ws/btcusdt@kline_1m"
    async with websockets.connect(uri) as ws:
        print("Connexion à Binance Futures en cours...")
        while True:
            msg = await ws.recv()
            k = json.loads(msg)['k']
            candle = [
                k['t'], k['o'], k['h'], k['l'], k['c'], k['v']
            ]
            candles.append(candle)
            if len(candles) > 10:
                candles.pop(0)

            price = float(k['c'])
            volume = float(k['v'])
            trending = is_trending(candles)
            breaking = is_breaking(price)

            # Log à chaque minute même sans signal
            await send_to_notion(price, volume, "PAS DE SIGNAL")

            if trending and breaking and volume > VOLUME_THRESHOLD:
                direction = "hausse" if k['c'] > k['o'] else "baisse"
                await send_alert(price, volume, direction)

if __name__ == "__main__":
    asyncio.run(watch())
