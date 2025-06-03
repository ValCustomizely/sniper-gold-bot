import asyncio import httpx import os from datetime import datetime from notion_client import Client

notion = Client(auth=os.environ["NOTION_API_KEY"]) NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"] POLYGON_API_KEY = os.environ["POLYGON_API_KEY"] SEUILS_DATABASE_ID = os.environ["SEUILS_DATABASE_ID"]

SEUILS_MANUELS = [] DERNIERE_MAJ_HORAIRES = set()

async def charger_seuils_depuis_notion(): global SEUILS_MANUELS try: pages = notion.databases.query(database_id=SEUILS_DATABASE_ID).get("results", []) SEUILS_MANUELS = [] for page in pages: props = page["properties"] valeur = props.get("Valeur", {}).get("number") type_ = props.get("Type", {}).get("select", {}).get("name") if valeur is not None and type_ in {"support", "résistance", "pivot"}: SEUILS_MANUELS.append({"valeur": valeur, "type": type_}) print(f"🗕️ {len(SEUILS_MANUELS)} seuils chargés depuis Notion", flush=True) except Exception as e: print(f"❌ Erreur chargement seuils : {e}", flush=True)

def est_heure_de_mise_a_jour_solide(): now = datetime.utcnow() current_key = f"{now.date().isoformat()}_{now.hour}" if now.hour in [4, 13] and current_key not in DERNIERE_MAJ_HORAIRES: DERNIERE_MAJ_HORAIRES.add(current_key) return True return False

def get_nom_seuil(valeur): seuils_tries = sorted(SEUILS_MANUELS, key=lambda x: abs(x["valeur"] - valeur)) if seuils_tries: plus_proche = seuils_tries[0]["valeur"] for nom, seuil in zip(["Pivot", "R1", "R2", "R3", "S1", "S2", "S3"], sorted([s["valeur"] for s in SEUILS_MANUELS])): if abs(valeur - seuil) < 0.1: return nom return f"{valeur:.2f}"

async def mettre_a_jour_seuils_auto(): today = datetime.utcnow().date().isoformat() url = f"https://api.polygon.io/v2/aggs/ticker/C:XAUUSD/range/1/day/{today}/{today}" try: async with httpx.AsyncClient() as client: r = await client.get(url, params={"adjusted": "true", "apiKey": POLYGON_API_KEY}) r.raise_for_status() result = r.json().get("results", [])[0] high = result["h"] low = result["l"] close = result["c"] pivot = round((high + low + close) / 3, 2) r1 = round((2 * pivot) - low, 2) r2 = round(pivot + (high - low), 2) r3 = round(high + 2 * (pivot - low), 2) s1 = round((2 * pivot) - high, 2) s2 = round(pivot - (high - low), 2) s3 = round(low - 2 * (high - pivot), 2)

seuils = [
            ("pivot", pivot), ("résistance", r1), ("résistance", r2), ("résistance", r3),
            ("support", s1), ("support", s2), ("support", s3)
        ]

        try:
            old_pages = notion.databases.query(
                database_id=SEUILS_DATABASE_ID,
                filter={"property": "Date", "date": {"equals": today}}
            ).get("results", [])
            for page in old_pages:
                notion.pages.update(page_id=page["id"], archived=True)
            print(f"🗑️ Anciennes valeurs supprimées ({len(old_pages)})", flush=True)
        except Exception as e:
            print(f"❌ Erreur suppression anciennes valeurs : {e}", flush=True)

        for (type_, valeur) in seuils:
            notion.pages.create(parent={"database_id": SEUILS_DATABASE_ID}, properties={
                "Type": {"select": {"name": type_}},
                "Valeur": {"number": valeur},
                "Date": {"date": {"start": today}}
            })
        print("✅ Seuils journaliers mis à jour dans Notion", flush=True)
except Exception as e:
    print(f"❌ Erreur mise à jour seuils auto : {e}", flush=True)

async def fetch_gold_data(): now = datetime.utcnow() print(f"[fetch_gold_data] ⏳ Début de la récupération à {now.isoformat()}", flush=True)

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
            if seuil_type == "résistance" and last_price > seuil_val + 0.5:
                signal_type = f"SIGNAL (hausse) - 📈 Cassure {get_nom_seuil(seuil_val)} (achat)"
                seuil_casse = seuil_val
                break
            elif seuil_type == "support" and last_price < seuil_val - 0.5:
                signal_type = f"SIGNAL (baisse) - 📉 Cassure {get_nom_seuil(seuil_val)} (short)"
                seuil_casse = seuil_val
                break

        if signal_type is None:
            pivot = next((s["valeur"] for s in SEUILS_MANUELS if s["type"] == "pivot"), None)
            r1 = sorted([s["valeur"] for s in SEUILS_MANUELS if s["type"] == "résistance"])[0] if any(s["type"] == "résistance" for s in SEUILS_MANUELS) else None
            s1 = sorted([s["valeur"] for s in SEUILS_MANUELS if s["type"] == "support"])[-1] if any(s["type"] == "support" for s in SEUILS_MANUELS) else None

            if pivot and r1 and pivot < last_price < r1:
                signal_type = "SIGNAL (hausse) - 🚧 Entre Pivot et R1 📈"
            elif pivot and s1 and s1 < last_price < pivot:
                signal_type = "SIGNAL (baisse) - 🚧 Entre Pivot et S1 📉"

        if not signal_type:
            print("❌ Aucun signal détecté (zone neutre)", flush=True)
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
            if "hausse" in signal_type:
                props["SL"] = {"number": round(seuil_casse - 1, 2)}
                props["SL suiveur"] = {"number": round(last_price - 3, 2)}
            else:
                props["SL"] = {"number": round(seuil_casse + 1, 2)}
                props["SL suiveur"] = {"number": round(last_price + 3, 2)}

        notion.pages.create(parent={"database_id": NOTION_DATABASE_ID}, properties=props)
        print("✅ Signal ajouté à Notion", flush=True)

    except Exception as e:
        print(f"❌ Erreur attrapée dans fetch_gold_data : {e}", flush=True)

async def main_loop(): while True: now = datetime.utcnow() print("\n🔁 Tick exécuté ", now.isoformat(), flush=True) if est_heure_de_mise_a_jour_solide(): await mettre_a_jour_seuils_auto() await fetch_gold_data() print("🔕 Tick terminé, pause de 60s\n", flush=True) await asyncio.sleep(60)

if name == "main": print("\n🚀 Bot en exécution", datetime.utcnow().isoformat(), flush=True) try: asyncio.run(main_loop()) except Exception as e: print(f"❌ Erreur critique dans le bot principal : {e}", flush=True)

