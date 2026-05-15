import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL", "")
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")
HEADERS = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}

SIGNAL_KEY = "signal:pending"
RESULT_KEY = "signal:result"


def _redis_set(key, value):
    try:
        requests.post(
            f"{UPSTASH_URL}/set/{key}",
            headers=HEADERS,
            json={"value": json.dumps(value)}
        )
    except Exception as e:
        print(f"❌ Redis set error: {e}")


def _redis_get(key):
    try:
        r = requests.get(f"{UPSTASH_URL}/get/{key}", headers=HEADERS)
        result = r.json().get("result")
        if result:
            return json.loads(result)
    except Exception as e:
        print(f"❌ Redis get error: {e}")
    return None


def _redis_delete(key):
    try:
        requests.get(f"{UPSTASH_URL}/del/{key}", headers=HEADERS)
    except Exception as e:
        print(f"❌ Redis delete error: {e}")


def send_signal(signal_id, symbol, direction, score, price, ai_advice, groq_reason, llama_reason, features, sl, tp):
    try:
        confidence = int(score * 100)

        if score >= 0.60:
            market_state = "trending"
        elif score <= 0.40:
            market_state = "ranging"
        else:
            market_state = "neutral"

        signal = {
            "signal_id": signal_id,
            "symbol": f"{symbol}-USDT",
            "direction": direction,
            "confidence": confidence,
            "price": price,
            "sl": sl,
            "tp": tp,
            "market_state": market_state,
            "score": round(score, 2),
            "ai_advice": ai_advice,
            "groq_reason": groq_reason,
            "llama_reason": llama_reason,
            "status": "pending",
            # Features الإحصائية بدل المؤشرات القديمة
            "zscore_1m": features.get("1m_zscore", 0),
            "momentum_1m": features.get("1m_momentum_pct", 0),
            "volatility_1m": features.get("1m_volatility", 0),
            "hist_prob_up_1m": features.get("1m_hist_prob_up", 0),
        }

        _redis_set(SIGNAL_KEY, signal)
        print(f"✅ Signal sent: {signal_id} | {direction} | Confidence: {confidence}%")

    except Exception as e:
        print(f"❌ Signal Error: {e}")


def send_startup():
    try:
        _redis_set("bot:startup", {"msg": "🤖 بوت التحليل شغال وجاهز!"})
        print("✅ Startup message sent")
    except Exception as e:
        print(f"❌ Startup Error: {e}")


def check_result():
    try:
        data = _redis_get(RESULT_KEY)
        if not data:
            return

        result = data.get("result", "")
        print(f"📊 نتيجة الصفقة: {result}")

        _redis_delete(RESULT_KEY)

    except Exception as e:
        print(f"❌ Result Check Error: {e}")
