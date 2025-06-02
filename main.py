import asyncio
import httpx
import os
from datetime import datetime
from notion_client import Client

# Initialisation du client Notion
notion = Client(auth=os.environ["NOTION_API_KEY"])
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
POLYGON_API_KEY = os.environ["POLYGON_API_KEY"]
SEUILS_NOTION_DATABASE_ID = os.environ.get("SEUILS_DATABASE_ID")

SEUILS_MANUELS = []

async def charger_seuils_depuis_notion():
    global SEUILS_MANUELS
    try:
        pages = notion.databases.query(database_id=SEUILS_NOTION_DATABASE_ID).get("results", [])
        SEUILS_MANUELS = []
        for page in pages:
            props = page["properties"]
            valeur = props.get("Valeur", {}).get("number")
            type_ = props.get("Type", {}).get("select", {}).get("name")
            if valeur is not None and type_ in {"support", "résistance", "pivot"}:
                SEUILS_MANUELS.append({"valeur": valeur, "type": type_})
        print(f"📥 {len(SEUILS_MANUELS)} seuils chargés depuis Notion", flush=True)
    except Exception as e:
        print(f"❌ Erreur chargement seuils : {e}", flush=True)

async def fetch_gold_data():
    now = datetime.utcnow()
    print(f"[fetch_gold_data] ⏳ Début de la récupération à {now.isoformat()}", flush=True)

    if now.hour >= 21 or now.hour < 4:
        print(f"⏸️ Marché fermé (UTC {now.hour}h), tick ignoré", flush=True)
        return

    today = now.date().isoformat()
    url = f"https://api.polygon.io/v2/aggs/ticker/C:XAUUSD/range/1/minute/{today}/{today}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params={
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

            signal_type = "PAS DE SIGNAL"
            seuil_casse = None
            for seuil in SEUILS_MANUELS:
                seuil_val = seuil["valeur"]
                seuil_type = seuil["type"]
                if seuil_type == "résistance" and last_price > seuil_val + 0.5:
                    signal_type = "SIGNAL (hausse)"
                    seuil_casse = seuil_val
                    break
                elif seuil_type == "support" and last_price < seuil_val - 0.5:
                    signal_type = "SIGNAL (baisse)"
                    seuil_casse = seuil_val
                    break

            print(f"✅ {signal_type} | {last_price} USD | Vol: {volume}", flush=True)

            props = {
                "Signal": {"title": [{"text": {"content": signal_type}}]},
                "Horodatage": {"date": {"start": now.isoformat()}},
                "Prix": {"number": float(last_price)},
                "Volume": {"number": int(volume)},
                "Commentaire": {"rich_text": [{"text": {"content": "Signal via Polygon.io"}}]}
            }

            if signal_type != "PAS DE SIGNAL" and seuil_casse:
                if "hausse" in signal_type:
                    sl = round(seuil_casse - 1, 2)
                    sl_suiveur = round(last_price - 3, 2)
                else:
                    sl = round(seuil_casse + 1, 2)
                    sl_suiveur = round(last_price + 3, 2)
                props["SL"] = {"number": sl}
                props["SL suiveur"] = {"number": sl_suiveur}

            notion.pages.create(parent={"database_id": NOTION_DATABASE_ID}, properties=props)
            print("✅ Signal ajouté à Notion", flush=True)

        except Exception as e:
            print(f"❌ Erreur attrapée dans fetch_gold_data : {e}", flush=True)

async def main_loop():
    await charger_seuils_depuis_notion()
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
