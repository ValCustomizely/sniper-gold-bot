import os
import time
import requests
from datetime import datetime
from notion_client import Client

# Authentification
BINANCE_API_URL = "https://fapi.binance.com/fapi/v1/ticker/24hr?symbol=XAUUSDT"
NOTION_TOKEN = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

notion = Client(auth=NOTION_TOKEN)

def get_gold_data():
    try:
        response = requests.get(BINANCE_API_URL, timeout=10)
        data = response.json()
        price = float(data["lastPrice"])
        volume = float(data["volume"])
        return price, volume
    except Exception as e:
        print(f"Erreur lors de la récupération de l’or : {e}")
        return None, None

def send_to_notion(price, volume):
    now = datetime.utcnow().isoformat()
    try:
        notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={
                "Horodatage": {"date": {"start": now}},
                "Prix": {"number": price},
                "Volume": {"number": volume},
                "Commentaire": {"rich_text": [{"text": {"content": "OK ✅"}}]},
            },
        )
        print(f"[{now}] ✅ Envoyé : {price} USD | Vol: {volume}")
    except Exception as e:
        print(f"Erreur Notion : {e}")

if __name__ == "__main__":
    print("🔄 Bot lancé. Envoi toutes les minutes...")
    while True:
        price, volume = get_gold_data()
        if price and volume:
            send_to_notion(price, volume)
        time.sleep(60)
