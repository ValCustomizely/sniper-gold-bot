
# === Sniper Bot Binance Futures - XAU/USDT ===
# Auteur : ChatGPT pour Valentin

import websockets
import asyncio
import json
import datetime

PAIR = "XAUUSDT"
THRESHOLD_LEVELS = [3320, 3307, 3285]
VOLUME_THRESHOLD = 3000
CANDLE_COUNT = 3

candles = []

def is_trending(candles):
    if len(candles) < CANDLE_COUNT:
        return False
    directions = ["up" if c[4] > c[1] else "down" for c in candles[-CANDLE_COUNT:]]
    return all(d == directions[0] for d in directions)

def is_breaking(price):
    return any(abs(price - level) <= 0.5 for level in THRESHOLD_LEVELS)

def analyze_candle(candle):
    timestamp = datetime.datetime.fromtimestamp(candle[0]/1000)
    open_, high, low, close, volume = map(float, candle[1:6])
    return [timestamp, open_, high, low, close, volume]

async def send_alert(price, volume, direction):
    print(f"\n🚨 SIGNAL SNIPER DETECTÉ !")
    print(f"Prix : {price} USDT")
    print(f"Volume : {volume} ")
    print(f"Tendance : {direction} sur {CANDLE_COUNT} bougies")
    print(f"Heure : {datetime.datetime.now().strftime('%H:%M:%S')}\n")

async def watch():
    url = f"wss://fstream.binance.com/ws/{PAIR.lower()}@kline_1m"
    async with websockets.connect(url) as ws:
        print("Connexion à Binance Futures en cours...")
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            k = data['k']
            if k['x']:
                candle = analyze_candle([
                    k['t'], k['o'], k['h'], k['l'], k['c'], k['v']
                ])
                candles.append(candle)
                if len(candles) > 10:
                    candles.pop(0)

                price = candle[4]
                volume = float(k['v'])
                trending = is_trending(candles)
                breaking = is_breaking(price)

                if trending and breaking and volume * 60 >= VOLUME_THRESHOLD:
                    direction = "hausse" if candle[4] > candle[1] else "baisse"
                    await send_alert(price, volume * 60, direction)

if __name__ == "__main__":
    asyncio.run(watch())
