import time
import os
import httpx
from datetime import datetime
from notion_client import Client
from bs4 import BeautifulSoup

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

notion = Client(auth=NOTION_API_KEY)

def get_gold_price_and_volume():
    url = "https://www.barchart.com/futures/quotes/GCM25/interactive-chart"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = httpx.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        price_elem = soup.select_one("span.last-change span.last")
        volume_elem = soup.find("span", string="Volume")
        volume_value = volume_elem.find_next("span") if volume_elem else None

        price = float(price_elem.text.strip().replace(",", "")) if price_elem else None
        volume = int(volume_value.text.strip().replace(",", "")) if volume_value else None

        return price, volume

    except Exception as e:
        print(f"❌ Erreur récupération données Barchart : {e}")
        return None, None

def post_to_notion(price, volume):
    now = datetime.utcnow().isoformat()

    try:
        notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={
                "Signal": {"title": [{"text": {"content": "Signal détecté"}}]},
                "Horodatage": {"date": {"start": now}},
                "Prix": {"number": price},
                "Volume": {"number": volume},
                "SL": {"number": price - 5},
                "SL suiveur": {"number": price - 1.5},
                "Commentaire": {"rich_text": []},
            }
        )
        print(f"✅ Notion mis à jour à {now}")
    except Exception as e:
        print(f"❌ Erreur Notion API : {e}")

if __name__ == "__main__":
    print("✅ Bot démarré")
    while True:
        price, volume = get_gold_price_and_volume()
        if price and volume:
            print(f"[{datetime.utcnow().isoformat()}] ✅ Prix: {price} | Volume: {volume}")
            post_to_notion(price, volume)
        else:
            print(f"[{datetime.utcnow().isoformat()}] ❌ Données non valides")

        print("🔁 Tick terminé, en attente...\n")
        time.sleep(300)  # 5 minutes
