import os
import requests
import time
from datetime import datetime

# Configuration : API Notion
NOTION_API_KEY = "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"
DATABASE_ID = "1f8e1c1cbab0808e87dce24b8c6315ab"
NOTION_API_URL = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

def fetch_notion_data():
    response = requests.post(NOTION_API_URL, headers=HEADERS)
    if response.status_code != 200:
        print(f"[ERREUR] Récupération Notion : {response.status_code} {response.text}")
        return None

    data = response.json()
    results = []
    for row in data["results"]:
        props = row["properties"]
        try:
            horodatage = props["Horodatage"]["rich_text"][0]["text"]["content"]
            prix = props["Prix"]["number"]
            signal = props["Signal"]["select"]["name"]
            sl = props.get("SL", {}).get("number")
            sl_suiveur = props.get("SL suiveur", {}).get("number")

            results.append({
                "horodatage": horodatage,
                "prix": prix,
                "signal": signal,
                "sl": sl,
                "sl_suiveur": sl_suiveur
            })
        except Exception as e:
            print(f"[ERREUR] Parsing d'une ligne : {e}")
            continue

    return results

def main():
    print(f"[INFO] Lecture Notion à {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
    donnees = fetch_notion_data()
    if donnees:
        print(f"[OK] {len(donnees)} lignes récupérées. Exemple :")
        for d in donnees[:3]:
            print(d)
    else:
        print("[WARN] Aucune donnée récupérée.")

if __name__ == "__main__":
    main()
