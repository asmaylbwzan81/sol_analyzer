from upstash_redis import Redis
import os
import json

UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL", "")
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")

SIGNAL_KEY = "signal:pending"

def send_signal(signal_id, symbol, direction, score, price, ai_advice, scores, sl, tp):
    try:
        r = Redis(url=UPSTASH_URL, token=UPSTASH_TOKEN)

        signal = {
            "signal_id": signal_id,
            "symbol": f"{symbol}-USDT",
            "direction": direction,
            "score": round(score, 2),
            "price": price,
            "sl": sl,
            "tp": tp,
            "ai_advice": ai_advice,
            "status": "pending"
        }

        r.set(SIGNAL_KEY, json.dumps(signal))
        print(f"✅ Signal sent to Redis: {signal_id}")

    except Exception as e:
        print(f"❌ Redis Error: {e}")
