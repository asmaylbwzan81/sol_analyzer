import os
import json
from dotenv import load_dotenv
from upstash_redis import Redis

load_dotenv()

redis_client = Redis(
    url=os.environ.get("UPSTASH_REDIS_REST_URL", ""),
    token=os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
)

KEY = "best_strategy"

def save_best(strategy, stats):
    try:
        data = json.dumps({"strategy": strategy, "stats": stats})
        redis_client.set(KEY, data)
        print(f"💾 Save: OK")
    except Exception as e:
        print(f"❌ Save error: {e}")

def load_best():
    try:
        result = redis_client.get(KEY)
        if not result:
            print("⚠️ Redis فارغ")
            return None
        data = json.loads(str(result))
        if "value" in data:
            data = json.loads(data["value"])
        if "strategy" in data and "stats" in data:
            print("✅ تم التحميل من Redis")
            return data
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def clear_best():
    redis_client.delete(KEY)
    print("🗑️ تم مسح Redis ✅")

