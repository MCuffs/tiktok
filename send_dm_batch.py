import asyncio
import json
import os
from send_dm import send_dm_batch, log

BATCH_FILE = "dm_batch.json"

async def main():
    if not os.path.exists(BATCH_FILE):
        log("No batch file found")
        return

    try:
        with open(BATCH_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        log(f"Error reading batch file: {e}")
        return

    creators = data.get("creators", [])
    lang = data.get("lang", "kr")

    if not creators:
        log("No creators in batch file")
        return

    log(f"Starting batch DM for {len(creators)} creators (lang={lang})")
    results = await send_dm_batch(creators, lang=lang, delay=5)

    log(f"Batch complete!")
    log(f"  Success: {len(results['success'])}")
    log(f"  Failed: {len(results['failed'])}")

    # Clean up batch file
    os.remove(BATCH_FILE)


if __name__ == "__main__":
    asyncio.run(main())
