import requests
import os
import json

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# ── الحد الأدنى للثقة عشان Groq يشتغل ──────
MIN_CONFIDENCE_FOR_REVIEW = 0.75

def review(scores, final_score, direction, price):
    """
    يراجع قرار التداول ويرجع:
    - verdict: "APPROVE" أو "REJECT"
    - advice: نص قصير بالعربي

    ⚡ يشتغل فقط إذا confidence >= 0.70 وaction=ENTER
    """

    # ── فلتر 1: بس الصفقات القوية ──────────
    if final_score < MIN_CONFIDENCE_FOR_REVIEW:
        print(f"⏭️ Groq تخطى — confidence={round(final_score,2)} أقل من {MIN_CONFIDENCE_FOR_REVIEW}")
        return "APPROVE", f"⏭️ ثقة منخفضة ({round(final_score,2)}) — تم القبول التلقائي"

    # ── فلتر 2: بس LONG أو SHORT ────────────
    if direction not in ("LONG", "SHORT"):
        return "REJECT", "⏭️ اتجاه غير واضح"

    if not GROQ_API_KEY:
        return "APPROVE", "⚠️ No Groq API Key"

    # ── طبقات المؤشرات حسب النظام الجديد ───
    TREND_LAYER = {"ema", "supertrend", "adx"}
    MOMENTUM_LAYER = {"rsi", "macd", "stochastic", "momentum"}
    LIQUIDITY_LAYER = {"volume", "vwap"}
    STRUCTURE_LAYER = {"fibonacci", "support_resistance", "pattern"}

    trend_scores = {k: round(v,2) for k, v in scores.items() if k in TREND_LAYER}
    momentum_scores = {k: round(v,2) for k, v in scores.items() if k in MOMENTUM_LAYER}
    liquidity_scores= {k: round(v,2) for k, v in scores.items() if k in LIQUIDITY_LAYER}
    structure_scores= {k: round(v,2) for k, v in scores.items() if k in STRUCTURE_LAYER}

    prompt = f"""
أنت مراجع تداول ذكي ومتحفظ. مهمتك مراجعة صفقة قريبة من الدخول.

البيانات:
- السعر: {price}
- الاتجاه: {direction}
- الثقة: {round(final_score, 2)} (من 1.0)

🟢 مؤشرات الاتجاه (الأهم):
{json.dumps(trend_scores, indent=2)}

🟡 مؤشرات الزخم:
{json.dumps(momentum_scores, indent=2)}

🔵 مؤشرات السيولة:
{json.dumps(liquidity_scores, indent=2)}

🟣 مؤشرات الهيكل:
{json.dumps(structure_scores, indent=2)}

أجب بهذا الشكل بالضبط (3 أسطر فقط):
VERDICT: APPROVE أو REJECT
REASON: سبب قصير جداً
ADVICE: نصيحة واحدة قصيرة

قواعد:
- APPROVE: مؤشرات الاتجاه متوافقة والزخم يدعم
- REJECT: تضارب في مؤشرات الاتجاه أو سيولة ضعيفة جداً أو خطر عالي
- كن متحفظاً — الهدف حماية الرصيد
"""

    try:
        res = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 150
            },
            timeout=10
        )
        data = res.json()

        if "choices" not in data:
            return "APPROVE", f"⚠️ Groq: {data.get('error', {}).get('message', 'خطأ غير معروف')}"

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

        print(f"🤖 Groq → {verdict} | {advice}")
        return verdict, advice

    except Exception as e:
        return "APPROVE", f"⚠️ Groq Error: {e}"

