import requests
import os
import json

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

MIN_CONFIDENCE_FOR_REVIEW = 0.75

def review_openrouter(scores, final_score, direction, price, scores_1d=None, scores_4h=None, scores_1h=None):
    """
    Llama 3.1 70B يراجع الصفقة كطبقة ذكاء ثانية
    أقوى من Groq (70B vs 8B)
    """

    if final_score < MIN_CONFIDENCE_FOR_REVIEW:
        return "APPROVE", f"⏭️ ثقة منخفضة ({round(final_score,2)}) — تم القبول التلقائي"

    if direction not in ("LONG", "SHORT"):
        return "REJECT", "⏭️ اتجاه غير واضح"

    if not OPENROUTER_API_KEY:
        return "APPROVE", "⚠️ No OpenRouter API Key"

    # ── إذا ما في 3 إطارات، استخدم combined ──
    if not scores_1d or not scores_4h or not scores_1h:
        ind_1h = ind_4h = ind_1d = {k: round(v, 2) for k, v in scores.items()}
    else:
        ind_1h = {k: round(v, 2) for k, v in scores_1h.items()}
        ind_4h = {k: round(v, 2) for k, v in scores_4h.items()}
        ind_1d = {k: round(v, 2) for k, v in scores_1d.items()}

    def extract(ind):
        return {
            "rsi": ind.get("rsi", 0.5),
            "adx": ind.get("adx", 0.5),
            "ema": ind.get("ema", 0.5),
            "macd": ind.get("macd", 0.5),
            "volume": ind.get("volume", 0.5),
        }

    tf_1h = extract(ind_1h)
    tf_4h = extract(ind_4h)
    tf_1d = extract(ind_1d)

    prompt = f"""أنت محلل تداول خبير ومتحفظ. راجع هذه الصفقة بدقة.

السعر: {price}
الاتجاه: {direction}
ثقة النظام: {round(final_score * 100)}%

📊 مؤشرات الساعة (1H):
- RSI: {tf_1h['rsi']} | ADX: {tf_1h['adx']}
- EMA: {tf_1h['ema']} | MACD: {tf_1h['macd']}
- Volume: {tf_1h['volume']}

📊 مؤشرات 4 ساعات (4H):
- RSI: {tf_4h['rsi']} | ADX: {tf_4h['adx']}
- EMA: {tf_4h['ema']} | MACD: {tf_4h['macd']}

📊 مؤشرات يومي (1D):
- RSI: {tf_1d['rsi']} | ADX: {tf_1d['adx']}
- EMA: {tf_1d['ema']} | MACD: {tf_1d['macd']}

قواعد (القيم بين 0-1):
- RSI < 0.35 = تشبع بيع → LONG | RSI > 0.65 = تشبع شراء → SHORT
- EMA > 0.5 = صاعد | EMA < 0.5 = هابط
- ADX > 0.6 = ترند قوي | ADX < 0.4 = ضعيف
- MACD > 0.5 = زخم صاعد | MACD < 0.5 = هابط

أجب بهذا الشكل بالضبط (3 أسطر فقط):
VERDICT: APPROVE أو REJECT
REASON: سبب قصير
ADVICE: نصيحة واحدة

قواعد القرار:
- APPROVE: 3 إطارات متوافقة والاتجاه واضح
- REJECT: تضارب بين الإطارات أو ADX ضعيف
- كن صارماً — حماية الرصيد أولاً
"""

    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/smart_analyzer",
            },
            json={
                "model": "meta-llama/llama-3.1-70b-instruct:free",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 150
            },
            timeout=15
        )
        data = res.json()

        if "choices" not in data:
            print(f"⚠️ OpenRouter Error: {data}")
            return "APPROVE", "⚠️ OpenRouter خطأ — تم القبول التلقائي"

        text = data["choices"][0]["message"]["content"].strip()
        verdict = "APPROVE"
        advice = text

        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("VERDICT:"):
                v = line.replace("VERDICT:", "").strip().upper()
                verdict = "REJECT" if "REJECT" in v else "APPROVE"
            elif line.startswith("ADVICE:"):
                advice = line.replace("ADVICE:", "").strip()

        print(f"🦙 OpenRouter → {verdict} | {advice}")
        return verdict, advice

    except Exception as e:
        return "APPROVE", f"⚠️ OpenRouter Error: {e}"

