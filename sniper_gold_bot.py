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
            "Signal": {"title": [{"text": {"content": commentaire}}]}
        }
    )
    print(f"✅ Envoyé : {price} USD | Vol: {volume} | {commentaire}")

async def watch():
    uri = f"wss://stream.binance.com:9443/ws/{PAIR.lower()}@kline_1m"
    print("Tentative de connexion à Binance WebSocket...")
    try:
        async with websockets.connect(uri, ping_interval=20, ping_timeout=20) as ws:
            print("✅ Connexion établie avec Binance Futures")
            last_minute = None
            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=30)
                    k = json.loads(msg)['k']
                    candle = [k['t'], k['o'], k['h'], k['l'], k['c'], k['v']]
                    candles.append(candle)
                    if len(candles) > 10:
                        candles.pop(0)

                    price = float(k['c'])
                    volume = float(k['v'])
                    trending = is_trending(candles)
                    breaking = is_breaking(price)

                    # On envoie une fois par minute
                    timestamp = datetime.datetime.fromtimestamp(k['t'] / 1000)
                    current_minute = timestamp.replace(second=0, microsecond=0)
                    if last_minute != current_minute:
                        last_minute = current_minute

                        if trending and breaking and volume > VOLUME_THRESHOLD:
                            direction = "hausse" if k['c'] > k['o'] else "baisse"
                            await send_alert(price, volume, direction)
                        else:
                            await send_to_notion(price, volume, "PAS DE SIGNAL")

                except asyncio.TimeoutError:
                    print(f"⏳ [{datetime.datetime.now().strftime('%H:%M:%S')}] Aucun message reçu depuis 30s, WebSocket toujours actif...")
                    continue
    except Exception as e:
        print("❌ Erreur WebSocket :", e)

if __name__ == "__main__":
    asyncio.run(watch())
