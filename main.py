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
DERNIER_SEUIL_CASSE = None
COMPTEUR_APRES_CASSURE = 0

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


✅ Mise à jour effectuée. Le chargement des seuils ne prend désormais en compte que les seuils du jour actuel, ce qui empêche l’apparition des anciens Seuil8. Toutes les autres fonctionnalités sont conservées. Tu peux relancer l’exécution en toute confiance.

