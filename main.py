import asyncio
from datetime import datetime

async def fetch_gold_data():
    print(f"[{datetime.utcnow()}] ✅ fetch_gold_data exécutée")

async def main():
    print("✅ Bot démarré")
    while True:
        try:
            await fetch_gold_data()
            print("🔁 Tick terminé, en attente...")
        except Exception as e:
            print(f"❌ Erreur dans main loop : {e}")
        await asyncio.sleep(30)  # pour éviter une boucle infinie ultra-rapide

if __name__ == "__main__":
    asyncio.run(main())
