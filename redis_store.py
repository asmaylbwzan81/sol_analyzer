import os
import json
import requests

REDIS_URL = os.environ.get("UPSTASH_REDIS_REST_URL")
REDIS_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN")

HEADERS = {"Authorization": f"Bearer {REDIS_TOKEN}"}

def save_best(strategy, stats):
    data = json.dumps({
        "strategy": strategy,
        "stats": stats
    })
    requests.post(
        f"{REDIS_URL}/set/best_strategy",
        headers=HEADERS,
        json={"value": data}
    )
    print("💾 تم الحفظ في Redis ✅")

def load_best():
    try:
        r = requests.get(
            f"{REDIS_URL}/get/best_strategy",
            headers=HEADERS
        )
        result = r.json().get("result")
        if result:
            data = json.loads(result)
            # تأكد إن عنده strategy و stats
            if "strategy" in data and "stats" in data:
                return data
        return None
    except:
        return None
