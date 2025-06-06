import asyncio
import httpx
import os
from datetime import datetime, timedelta
from notion_client import Client

notion = Client(auth=os.environ["NOTION_API_KEY"])
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
POLYGON_API_KEY = os.environ["POLYGON_API_KEY"]
SEUILS_DATABASE_ID = os.environ["SEUILS_DATABASE_ID"]

SEUILS_MANUELS = []
DERNIERE_MAJ_HORAIRES = set()
DERNIER_SEUIL_CASSE = None
COMPTEUR_APRES_CASSURE = 0

async def mettre_a_jour_seuils_auto():
    try:
        print("[INFO] Mise à jour automatique des seuils (calcul depuis Polygon)", flush=True)

        yesterday = (datetime.utcnow().date() - timedelta(days=1)).isoformat()
        today = datetime.utcnow().date().isoformat()
        url = f"https://api.polygon.io/v2/aggs/ticker/C:XAUUSD/range/1/day/{yesterday}/{yesterday}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params={
                "adjusted": "true",
                "sort": "desc",
                "limit": 1,
                "apiKey": POLYGON_API_KEY
            }, timeout=10)

            response.raise_for_status()
            results = response.json().get("results", [])

            if not results:
                print("[WARN] Aucune donnée reçue de Polygon pour la veille", flush=True)
                return

            candle = results[0]
            high = candle["h"]
            low = candle["l"]
            close = candle["c"]

            pivot = round((high + low + close) / 3, 2)
            r1 = round((2 * pivot) - low, 2)
            s1 = round((2 * pivot) - high, 2)
            r2 = round(pivot + (high - low), 2)
            s2 = round(pivot - (high - low), 2)
            r3 = round(high + 2 * (pivot - low), 2)
            s3 = round(low - 2 * (high - pivot), 2)

            seuils = [
                {"valeur": r3, "type": "résistance"},
                {"valeur": r2, "type": "résistance"},
                {"valeur": r1, "type": "résistance"},
                {"valeur": pivot, "type": "pivot"},
                {"valeur": s1, "type": "support"},
                {"valeur": s2, "type": "support"},
                {"valeur": s3, "type": "support"},
            ]

            for seuil in seuils:
                notion.pages.create(
                    parent={"database_id": SEUILS_DATABASE_ID},
                    properties={
                        "Valeur": {"number": seuil["valeur"]},
                        "Type": {"select": {"name": seuil["type"]}},
                        "Date": {"date": {"start": today}}
                    }
                )

            print(f"[INFO] 7 seuils enregistrés pour {today} (données du {yesterday})", flush=True)

    except Exception as e:
        print(f"[ERREUR] dans mettre_a_jour_seuils_auto : {e}", flush=True)

async def charger_seuils_depuis_notion():
    global SEUILS_MANUELS
    try:
        today = datetime.utcnow().date().isoformat()
        pages = notion.databases.query(
            database_id=SEUILS_DATABASE_ID,
            filter={"property": "Date", "date": {"equals": today}}
        ).get("results", [])

        supports = []
        resistances = []
        pivots = []

        for page in pages:
            props = page["properties"]
            valeur = props.get("Valeur", {}).get("number")
            type_ = props.get("Type", {}).get("select", {}).get("name")
            if valeur is not None:
                if type_ == "support":
                    supports.append(valeur)
                elif type_ == "résistance":
                    resistances.append(valeur)
                elif type_ == "pivot":
                    pivots.append(valeur)

        SEUILS_MANUELS = []
        for i, val in enumerate(sorted(resistances)):
            SEUILS_MANUELS.append({"valeur": val, "type": "résistance", "nom": f"R{i+1}"})
        for val in pivots:
            SEUILS_MANUELS.append({"valeur": val, "type": "pivot", "nom": "Pivot"})
        for i, val in enumerate(sorted(supports, reverse=True)):
            SEUILS_MANUELS.append({"valeur": val, "type": "support", "nom": f"S{i+1}"})

        print(f"[INFO] {len(SEUILS_MANUELS)} seuils chargés depuis Notion", flush=True)
    except Exception as e:
        print(f"[ERREUR] chargement seuils : {e}", flush=True)

async def fetch_gold_data():
    global DERNIER_SEUIL_CASSE, COMPTEUR_APRES_CASSURE

    now = datetime.utcnow()
    print(f"[fetch_gold_data] Début de la récupération à {now.isoformat()}", flush=True)

    if now.hour >= 21 or now.hour < 4:
        print(f"[INFO] Marché fermé (UTC {now.hour}h), tick ignoré", flush=True)
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
                print("[ERREUR] Aucune donnée reçue", flush=True)
                return

            candle = results[0]
            last_price = candle["c"]
            volume = candle["v"]

            signal_type = None
            seuil_casse = None
            nom_seuil_casse = None

            for seuil in SEUILS_MANUELS:
                seuil_val = seuil["valeur"]
                seuil_type = seuil["type"]
                nom_seuil = seuil["nom"]
                if seuil_type == "résistance" and last_price > seuil_val + 0.5:
                    ecart = round(last_price - seuil_val, 2)
                    signal_type = f"📈 Cassure {nom_seuil} +{ecart}$"
                    seuil_casse = seuil_val
                    nom_seuil_casse = nom_seuil
                    break
                elif seuil_type == "support" and last_price < seuil_val - 0.5:
                    ecart = round(seuil_val - last_price, 2)
                    signal_type = f"📉 Cassure {nom_seuil} -{ecart}$"
                    seuil_casse = seuil_val
                    nom_seuil_casse = nom_seuil
                    break

            if signal_type is None:
                pivot = next((s["valeur"] for s in SEUILS_MANUELS if s["nom"] == "Pivot"), None)
                r1 = next((s["valeur"] for s in SEUILS_MANUELS if s["nom"] == "R1"), None)
                s1 = next((s["valeur"] for s in SEUILS_MANUELS if s["nom"] == "S1"), None)

                if pivot and r1 and pivot < last_price < r1:
                    ecart = round(r1 - last_price, 2)
                    signal_type = f"🚧📈 -{ecart}$ du R1"
                elif pivot and s1 and s1 < last_price < pivot:
                    ecart = round(last_price - s1, 2)
                    signal_type = f"🚧📉 +{ecart}$ du S1"

            if not signal_type:
                print("[WARN] Aucun signal défini (devrait être impossible)", flush=True)
                return

            if seuil_casse:
                if nom_seuil_casse != DERNIER_SEUIL_CASSE:
                    DERNIER_SEUIL_CASSE = nom_seuil_casse
                    COMPTEUR_APRES_CASSURE = 1
                else:
                    COMPTEUR_APRES_CASSURE += 1
                if COMPTEUR_APRES_CASSURE >= 5:
                    signal_type += " 🚧"

            print(f"[SIGNAL] {signal_type} | {last_price} USD | Vol: {volume}", flush=True)

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
            print("[INFO] Signal ajouté à Notion", flush=True)

        except Exception as e:
            print(f"[ERREUR] attrapée dans fetch_gold_data : {e}", flush=True)

def est_heure_de_mise_a_jour_1h():
    now = datetime.utcnow()
    return now.hour == 1 and f"{now.date().isoformat()}_1" not in DERNIERE_MAJ_HORAIRES and not DERNIERE_MAJ_HORAIRES.add(f"{now.date().isoformat()}_1")

async def main_loop():
    while True:
        now = datetime.utcnow()
        print(f"[TICK] Tick exécuté {now.isoformat()}", flush=True)
        if est_heure_de_mise_a_jour_1h():
            await mettre_a_jour_seuils_auto()
        await fetch_gold_data()
        print("[PAUSE] Tick terminé, pause de 60s\n", flush=True)
        await asyncio.sleep(60)

async def mise_en_route():
    await main_loop()

if __name__ == "__main__":
    print(f"[BOOT] Bot en exécution {datetime.utcnow().isoformat()}", flush=True)
    try:
        asyncio.run(mise_en_route())
    except Exception as e:
        print(f"[ERREUR] critique dans le bot principal : {e}", flush=True)
