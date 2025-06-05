import asyncio
import httpx
import os
from datetime import datetime
from notion_client import Client

notion = Client(auth=os.environ["NOTION_API_KEY"])
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
POLYGON_API_KEY = os.environ["POLYGON_API_KEY"]
SEUILS_DATABASE_ID = os.environ["SEUILS_DATABASE_ID"]

SEUILS_MANUELS = []
DERNIERE_MAJ_HORAIRES = set()

def est_heure_de_mise_a_jour_solide():
    now = datetime.utcnow()
    return now.hour == 4 and f"{now.date().isoformat()}_4" not in DERNIERE_MAJ_HORAIRES and not DERNIERE_MAJ_HORAIRES.add(f"{now.date().isoformat()}_4")

async def charger_seuils_depuis_notion():
    global SEUILS_MANUELS
    try:
        today = datetime.utcnow().date().isoformat()
        pages = notion.databases.query(
            database_id=SEUILS_DATABASE_ID,
            filter={"property": "Date", "date": {"equals": today}}
        ).get("results", [])

        SEUILS_MANUELS = []
        noms = ["Pivot", "R1", "R2", "R3", "S1", "S2", "S3"]
        for idx, page in enumerate(sorted(pages, key=lambda p: p["properties"].get("Valeur", {}).get("number", 0))):
            props = page["properties"]
            valeur = props.get("Valeur", {}).get("number")
            type_ = props.get("Type", {}).get("select", {}).get("name")
            if valeur is not None and type_ in {"support", "résistance", "pivot"}:
                nom = noms[idx] if idx < len(noms) else f"Seuil{idx}"
                SEUILS_MANUELS.append({"valeur": valeur, "type": type_, "nom": nom})
        print(f"🗕️ {len(SEUILS_MANUELS)} seuils chargés depuis Notion", flush=True)
    except Exception as e:
        print(f"❌ Erreur chargement seuils : {e}", flush=True)

async def fetch_gold_data():
    now = datetime.utcnow()
    print(f"[fetch_gold_data] ⏳ Début de la récupération à {now.isoformat()}", flush=True)

    if now.hour >= 21 or now.hour < 4:
        print(f"⏸️ Marché fermé (UTC {now.hour}h), tick ignoré", flush=True)
        return

    await charger_seuils_depuis_notion()

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

            signal_type = None
            seuil_casse = None

            for seuil in SEUILS_MANUELS:
                seuil_val = seuil["valeur"]
                seuil_type = seuil["type"]
                nom_seuil = seuil["nom"]
                if seuil_type == "résistance" and last_price > seuil_val + 0.5:
                    ecart = round(last_price - seuil_val, 2)
                    signal_type = f"📈 Cassure {nom_seuil} +{ecart}$"
                    seuil_casse = seuil_val
                    break
                elif seuil_type == "support" and last_price < seuil_val - 0.5:
                    ecart = round(seuil_val - last_price, 2)
                    signal_type = f"📉 Cassure {nom_seuil} -{ecart}$"
                    seuil_casse = seuil_val
                    break

            if not signal_type:
                pivot = next((s["valeur"] for s in SEUILS_MANUELS if s["type"] == "pivot"), None)
                r1 = next((s["valeur"] for s in SEUILS_MANUELS if s["nom"] == "R1"), None)
                s1 = next((s["valeur"] for s in SEUILS_MANUELS if s["nom"] == "S1"), None)

                if pivot and r1 and last_price >= pivot and last_price < r1:
                    ecart = round(r1 - last_price, 2)
                    signal_type = f"🚧📈 +{ecart}$ du R1"
                elif pivot and s1 and last_price <= pivot and last_price > s1:
                    ecart = round(last_price - s1, 2)
                    signal_type = f"🚧📉 -{ecart}$ du S1"

            if not signal_type:
                print("⚠️ ERREUR : aucun signal défini (devrait être impossible)", flush=True)
                return

            print(f"✅ {signal_type} | {last_price} USD | Vol: {volume}", flush=True)

            props = {
                "Signal": {"title": [{"text": {"content": signal_type}}]},
                "Horodatage": {"date": {"start": now.isoformat()}},
                "Prix": {"number": float(last_price)},
                "Volume": {"number": int(volume)},
                "Commentaire": {"rich_text": [{"text": {"content": "Signal via Polygon.io"}}]}
            }

            if seuil_casse:
                props["SL"] = {"number": round(seuil_casse - 1, 2) if "📈" in signal_type else round(seuil_casse + 1, 2)}
                props["SL suiveur"] = {"number": round(last_price + 5, 2) if "📈" in signal_type else round(last_price - 5, 2)}

            notion.pages.create(parent={"database_id": NOTION_DATABASE_ID}, properties=props)
            print("✅ Signal ajouté à Notion", flush=True)

        except Exception as e:
            print(f"❌ Erreur attrapée dans fetch_gold_data : {e}", flush=True)

async def main_loop():
    while True:
        now = datetime.utcnow()
        print("\n🔁 Tick exécuté ", now.isoformat(), flush=True)
        if est_heure_de_mise_a_jour_solide():
            await mettre_a_jour_seuils_auto()
        await fetch_gold_data()
        print("🔕 Tick terminé, pause de 60s\n", flush=True)
        await asyncio.sleep(60)

if __name__ == "__main__":
    print("\n🚀 Bot en exécution", datetime.utcnow().isoformat(), flush=True)
    try:
        asyncio.run(main_loop())
    except Exception as e:
        print(f"❌ Erreur critique dans le bot principal : {e}", flush=True)
