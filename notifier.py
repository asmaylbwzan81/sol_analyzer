from upstash_redis import Redis
import os
import json
from strategy_weights import update_weights

UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL", "")
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")

SIGNAL_KEY = "signal:pending"
RESULT_KEY = "signal:result"


def send_signal(signal_id, symbol, direction, score, price, ai_advice, groq_reason, or_reason, scores, sl, tp):
    try:
        r = Redis(url=UPSTASH_URL, token=UPSTASH_TOKEN)

        # تحويل score (0.0-1.0) إلى confidence (0-100)
        confidence = int(score * 100)

        # تحديد trend من الـ scores
        if score >= 0.60:
            trend = "UPTREND"
        elif score <= 0.40:
            trend = "DOWNTREND"
        else:
            trend = "RANGING"

        signal = {
            # ── حقول بوت التنفيذ ──
            "signal_id": signal_id,
            "symbol": f"{symbol}-USDT",
            "direction": direction,
            "confidence": confidence,
            "price": price,
            "sl": sl,
            "tp1": tp,
            "rsi": round(scores.get("rsi", 0.5) * 100, 1),
            "adx": round(scores.get("adx", 0.5) * 100, 1),
            "trend": trend,
            "atr": abs(price - sl) if sl else 0,
            "market_state": "trending" if score >= 0.65 or score <= 0.35 else "ranging",

            # ── حقول إضافية ──
            "score": round(score, 2),
            "ai_advice": ai_advice,
            "groq_reason": groq_reason, # ✅ جديد
            "or_reason": or_reason, # ✅ جديد
            "status": "pending",
            "strategies_used": list(scores.keys()),
        }

        r.set(SIGNAL_KEY, json.dumps(signal))
        print(f"✅ Signal sent to Redis: {signal_id} | Confidence: {confidence}%")

    except Exception as e:
        print(f"❌ Redis Error: {e}")


def send_startup():
    """يرسل رسالة على Redis عند بداية تشغيل بوت التحليل."""
    try:
        r = Redis(url=UPSTASH_URL, token=UPSTASH_TOKEN)
        r.set("bot:startup", json.dumps({
            "msg": "🤖 بوت التحليل الجديد شغال وجاهز!"
        }))
        print("✅ Startup message sent to Redis")
    except Exception as e:
        print(f"❌ Startup Error: {e}")


def check_result():
    """
    يقرأ نتيجة الصفقة من Redis ويحدث أوزان الاستراتيجيات.
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

