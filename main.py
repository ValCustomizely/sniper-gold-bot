import asyncio
from datetime import datetime

async def run_worker():
    while True:
        print(f"🟢 Worker actif à {datetime.utcnow().isoformat()} UTC")
        await asyncio.sleep(10)

if __name__ == "__main__":
    print("🚀 Lancement du worker...")
    try:
        asyncio.run(run_worker())
    except Exception as e:
        print(f"❌ Erreur : {e}")
