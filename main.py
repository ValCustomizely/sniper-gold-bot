import asyncio
import sys
from datetime import datetime

sys.stdout.reconfigure(line_buffering=True)

async def fetch_gold_data():
    print(f"[{datetime.utcnow()}] ✅ fetch_gold_data exécutée", flush=True)

async def main():
    print("✅ Bot démarré", flush=True)
    while True:
        try:
            await fetch_gold_data()
            print("🔁 Tick terminé, en attente...", flush=True)
        except Exception as e:
            print(f"❌ Erreur dans main loop : {e}", flush=True)
        await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())
