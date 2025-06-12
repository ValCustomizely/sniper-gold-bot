import asyncio
import httpx
import os
import json
from datetime import datetime, timedelta
from notion_client import Client

notion = Client(auth=os.environ["NOTION_API_KEY"])
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
POLYGON_API_KEY = os.environ["POLYGON_API_KEY"]
SEUILS_DATABASE_ID = os.environ["SEUILS_DATABASE_ID"]

SEUILS_MANUELS = []
DERNIERE_MAJ_HORAIRES = set()

ETAT_PATH = "etat_cassure.json"

def charger_etat():
    if not os.path.exists(ETAT_PATH):
        return {"seuil": None, "compteur": 0}
    with open(ETAT_PATH, "r") as f:
        return json.load(f)

def sauvegarder_etat(seuil, compteur):
    with open(ETAT_PATH, "w") as f:
        json.dump({"seuil": seuil, "compteur": compteur}, f)

def get_last_trading_day():
    today = datetime.utcnow().date()
    weekday = today.weekday()
    if weekday == 0:
        return today - timedelta(days=3)
    elif weekday == 6:
        return today - timedelta(days=2)
    elif weekday == 5:
        return today - timedelta(days=1)
    else:
        return today - timedelta(days=1)

def calculer_seuils(high, low, close):
    pivot = round((high + low + close) / 3, 2)
    r1 = round((2 * pivot) - low, 2)
    s1 = round((2 * pivot) - high, 2)
    r2 = round(pivot + (high - low), 2)
    s2 = round(pivot - (high - low), 2)
    r3 = round(high + 2 * (pivot - low), 2)
    s3 = round(low - 2 * (high - pivot), 2)
    return [
        ("R3", r3, "résistance"),
        ("R2", r2, "résistance"),
        ("R1", r1, "résistance"),
        ("Pivot", pivot, "pivot"),
        ("S1", s1, "support"),
        ("S2", s2, "support"),
        ("S3", s3, "support")
    ]

async def enregistrer_seuils_notions(seuils, session):
    today = datetime.utcnow().date().isoformat()
    for nom, valeur, type_ in seuils:
        notion.pages.create(parent={"database_id": SEUILS_DATABASE_ID}, properties={
            "Nom": {"title": [{"text": {"content": nom}}]},
            "Valeur": {"number": valeur},
            "Type": {"select": {"name": type_}},
            "Date": {"date": {"start": today}},
            "Session": {"select": {"name": session}}
        })

async def mettre_a_jour_seuils_auto():
    try:
        print("[INFO] Mise à jour des seuils journalier", flush=True)
        yesterday = get_last_trading_day().isoformat()
        url = f"https://api.polygon.io/v2/aggs/ticker/C:XAUUSD/range/1/day/{yesterday}/{yesterday}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params={"adjusted": "true", "sort": "desc", "limit": 1, "apiKey": POLYGON_API_KEY}, timeout=10)
            response.raise_for_status()
            results = response.json().get("results", [])
            if not results:
                print("[WARN] Pas de données Polygon", flush=True)
                return
            candle = results[0]
            seuils = calculer_seuils(candle["h"], candle["l"], candle["c"])
            await enregistrer_seuils_notions(seuils, "journalier")
    except Exception as e:
        print(f"[ERREUR] seuils journalier : {e}", flush=True)

async def mettre_a_jour_seuils_asie():
    try:
        print("[INFO] Mise à jour des seuils Asie", flush=True)
        today = datetime.utcnow().date().isoformat()
        url = f"https://api.polygon.io/v2/aggs/ticker/C:XAUUSD/range/1/hour/{today}/{today}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params={"adjusted": "true", "sort": "asc", "limit": 4, "apiKey": POLYGON_API_KEY}, timeout=10)
            response.raise_for_status()
            results = response.json().get("results", [])
            if not results:
                print("[WARN] Pas de données pour seuils Asie", flush=True)
                return
            high = max(r["h"] for r in results)
            low = min(r["l"] for r in results)
            close = results[-1]["c"]
            seuils = calculer_seuils(high, low, close)
            await enregistrer_seuils_notions(seuils, "asie")
    except Exception as e:
        print(f"[ERREUR] seuils asie : {e}", flush=True)

async def mettre_a_jour_seuils_us():
    try:
        print("[INFO] Mise à jour des seuils US", flush=True)
        today = datetime.utcnow().date().isoformat()
        url = f"https://api.polygon.io/v2/aggs/ticker/C:XAUUSD/range/1/hour/{today}/{today}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params={"adjusted": "true", "sort": "asc", "limit": 17, "apiKey": POLYGON_API_KEY}, timeout=10)
            response.raise_for_status()
            results = response.json().get("results", [])
            if len(results) < 17:
                print("[WARN] Pas assez de données horaires pour seuils US", flush=True)
                return
            us_range = results[13:17]
            high = max(r["h"] for r in us_range)
            low = min(r["l"] for r in us_range)
            close = us_range[-1]["c"]
            seuils = calculer_seuils(high, low, close)
            await enregistrer_seuils_notions(seuils, "us")
    except Exception as e:
        print(f"[ERREUR] seuils us : {e}", flush=True)

async def fetch_gold_data(seuil_source="journalier"):
    await charger_seuils_depuis_notion()
    etat = charger_etat()
    now = datetime.utcnow()
    today = now.date().isoformat()
    url = f"https://api.polygon.io/v2/aggs/ticker/C:XAUUSD/range/1/minute/{today}/{today}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params={"adjusted": "true", "sort": "desc", "limit": 1, "apiKey": POLYGON_API_KEY}, timeout=10)
            response.raise_for_status()
            results = response.json().get("results", [])
            if not results:
                print("[ERREUR] Pas de donnée minute", flush=True)
                return

            candle = results[0]
            last_price = candle["c"]
            volume = candle["v"]
            pivot = next((s["valeur"] for s in SEUILS_MANUELS if s["nom"] == "Pivot"), None)

            seuil_prec = etat["seuil"]
            if seuil_prec:
                seuil_prec_val = next((s["valeur"] for s in SEUILS_MANUELS if s["nom"] == seuil_prec), None)
                if seuil_prec_val:
                    if (seuil_prec.startswith("R") and last_price <= seuil_prec_val - 0.2) or (seuil_prec.startswith("S") and last_price >= seuil_prec_val + 0.2):
                        sauvegarder_etat(None, 0)
                        etat = {"seuil": None, "compteur": 0}

            cassures_resistances = [(s["valeur"], s["nom"]) for s in SEUILS_MANUELS if s["type"] == "résistance" and last_price > s["valeur"] + 0.5]
            cassures_supports = [(s["valeur"], s["nom"]) for s in SEUILS_MANUELS if s["type"] == "support" and last_price < s["valeur"] - 0.5]

            signal_type = None
            seuil_casse = None
            nom_seuil_casse = None

            if cassures_resistances:
                seuil_casse, nom_seuil_casse = max(cassures_resistances, key=lambda x: x[0])
                ecart = round(last_price - seuil_casse, 2)
                signal_type = f"📈 Cassure {nom_seuil_casse} +{ecart}$"
            elif cassures_supports:
                seuil_casse, nom_seuil_casse = min(cassures_supports, key=lambda x: x[0])
                ecart = round(seuil_casse - last_price, 2)
                signal_type = f"📉 Cassure {nom_seuil_casse} -{ecart}$"
            else:
                r1 = next((s["valeur"] for s in SEUILS_MANUELS if s["nom"] == "R1"), None)
                s1 = next((s["valeur"] for s in SEUILS_MANUELS if s["nom"] == "S1"), None)
                if pivot and r1 and pivot < last_price <= r1 + 0.5:
                    signal_type = f"🚧📈 -{round(r1 - last_price, 2)}$ du R1"
                elif pivot and s1 and s1 - 0.5 <= last_price < pivot:
                    signal_type = f"🚧📉 +{round(last_price - s1, 2)}$ du S1"

            if signal_type and seuil_casse:
                if nom_seuil_casse != etat["seuil"]:
                    compteur = 1
                else:
                    compteur = etat["compteur"] + 1
                sauvegarder_etat(nom_seuil_casse, compteur)
                if compteur >= 5:
                    signal_type += " 🚧"

            if signal_type:
                props = {
                    "Horodatage": {"date": {"start": now.isoformat()}},
                    "Prix": {"number": float(last_price)},
                    "Volume": {"number": int(volume)},
                    "Commentaire": {"rich_text": [{"text": {"content": "Signal via Polygon.io"}}]}
                }

                if seuil_source == "journalier":
                    props["Signal (journalier)"] = {"rich_text": [{"text": {"content": signal_type}}]}
                else:
                    props["Signal (session)"] = {"rich_text": [{"text": {"content": signal_type}}]}

                if seuil_casse:
                    props["SL"] = {"number": round(seuil_casse - 1, 2) if "📈" in signal_type else round(seuil_casse + 1, 2)}
                    props["SL suiveur"] = {"number": round(last_price + 5, 2) if "📈" in signal_type else round(last_price - 5, 2)}
                    props["TP"] = {"number": round(seuil_casse + (seuil_casse - pivot) * 0.8, 2) if pivot else None}

                notion.pages.create(parent={"database_id": NOTION_DATABASE_ID}, properties=props)
                print(f"[INFO] {signal_type} | {last_price}$ | Vol: {volume}", flush=True)

        except Exception as e:
            print(f"[ERREUR] fetch_gold_data : {e}", flush=True)

async def main_loop():
    while True:
        if est_heure_de_mise_a_jour_solide():
            await mettre_a_jour_seuils_auto()
        await fetch_gold_data()
        await asyncio.sleep(60)

async def mise_en_route():
    await main_loop()

if __name__ == "__main__":
    print(f"[BOOT] {datetime.utcnow().isoformat()}", flush=True)
    try:
        asyncio.run(mise_en_route())
    except Exception as e:
        print(f"[ERREUR] critique bot : {e}", flush=True)
