import os
import json
import requests

REDIS_URL = os.environ.get("UPSTASH_REDIS_REST_URL")
REDIS_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
HEADERS = {"Authorization": f"Bearer {REDIS_TOKEN}"}
KEY = "best_strategy"

# ══════════════════════════════
# حفظ
# ══════════════════════════════
def save_best(strategy, stats):
    data = json.dumps({"strategy": strategy, "stats": stats})
    r = requests.post(
        f"{REDIS_URL}/set/{KEY}",
        headers=HEADERS,
        json={"value": data}
    )
    print(f"💾 Save: {r.json()}")

# ══════════════════════════════
# تحميل
# ══════════════════════════════
def load_best():
    try:
        r = requests.get(f"{REDIS_URL}/get/{KEY}", headers=HEADERS)
        print(f"🔍 Load: {r.json()}")
        result = r.json().get("result")

        if not result:
            print("⚠️ Redis فارغ")
            return None

        # لو result فيه value بالداخل
        try:
            outer = json.loads(result)
            if "value" in outer:
                data = json.loads(outer["value"])
            else:
                data = outer
        except:
            data = json.loads(result)

        if "strategy" in data and "stats" in data:
            print("✅ تم التحميل من Redis")
            return data

        print("⚠️ البيانات غير مكتملة")
        return None

    except Exception as e:
        print(f"❌ Error: {e}")
        return None
