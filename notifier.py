from upstash_redis import Redis
import os
import json
from strategy_weights import update_weights

UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL", "")
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")

SIGNAL_KEY = "signal:pending"
RESULT_KEY = "signal:result"


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
            "status": "pending",
            "strategies_used": list(scores.keys()), # ← جديد
        }

        r.set(SIGNAL_KEY, json.dumps(signal))
        print(f"✅ Signal sent to Redis: {signal_id}")

    except Exception as e:
        print(f"❌ Redis Error: {e}")


def check_result():
    """
    يقرأ نتيجة الصفقة من Redis ويحدث أوزان الاستراتيجيات.
    my_bot_2026 يرسل: {signal_id, result: WIN/LOSS, strategies_used}
    """
    try:
        r = Redis(url=UPSTASH_URL, token=UPSTASH_TOKEN)
        raw = r.get(RESULT_KEY)

        if not raw:
            return

        data = json.loads(raw)
        result = data.get("result", "")
        strategies_used = data.get("strategies_used", [])

        if result in ("WIN", "LOSS") and strategies_used:
            update_weights(strategies_used, result)
            print(f"📊 Weights updated: {result} → {strategies_used}")

            # امسح النتيجة بعد ما قرأناها
            r.delete(RESULT_KEY)

    except Exception as e:
        print(f"❌ Result Check Error: {e}")

