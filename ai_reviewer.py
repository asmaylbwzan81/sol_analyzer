import requests
import os
import json

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# ── تصنيف الموشرات ──────────────────────────
STRONG_BASE = {"rsi", "bollinger", "stochastic", "fibonacci", "support_resistance"}
MEDIUM_BASE = {"adx", "supertrend"}
WEAK_BASE = {"momentum", "macd", "ema"}

def review(scores, final_score, direction, price):
    """
    يراجع قرار التداول ويرجع:
    - verdict: "APPROVE" أو "REJECT"
    - advice: نص قصير بالعربي

    ⚡ لا يحلل إذا السكور بين 0.40 و 0.60 — توفير رصيد Groq
    """
    # ── فلتر السكور: بس الصفقات الجدية ──────
    if 0.40 < final_score < 0.60:
        return "REJECT", "⏭️ السكور في المنطقة الرمادية، تم التخطي"

    if not GROQ_API_KEY:
        return "APPROVE", "⚠️ No Groq API Key"

    # ── تصنيف الموشرات للبرومبت ─────────────
    strong_scores = {k: v for k, v in scores.items() if k in STRONG_BASE}
    medium_scores = {k: v for k, v in scores.items() if k in MEDIUM_BASE}
    weak_scores = {k: v for k, v in scores.items() if k in WEAK_BASE}

    strongest = max(scores, key=scores.get)
    weakest = min(scores, key=scores.get)

    prompt = f"""
أنت مراجع تداول ذكي. مهمتك مراجعة قرار التداول.

البيانات:
- السعر الحالي: {price}
- الاتجاه المقترح: {direction}
- النتيجة النهائية: {round(final_score, 2)}
- أقوى مؤشر: {strongest} = {round(scores[strongest], 2)}
- أضعف مؤشر: {weakest} = {round(scores[weakest], 2)}

🟢 الموشرات القوية (وزنها عالي، رأيها مهم):
{json.dumps(strong_scores, indent=2)}

🟡 الموشرات المتوسطة:
{json.dumps(medium_scores, indent=2)}

🔴 الموشرات الضعيفة (وزنها منخفض، لا تعتمد عليها):
{json.dumps(weak_scores, indent=2)}

أجب بهذا الشكل بالضبط (3 أسطر فقط):
VERDICT: APPROVE أو REJECT
REASON: سبب قصير جداً
ADVICE: نصيحة واحدة قصيرة

قواعد القرار:
- APPROVE: إذا الموشرات القوية متوافقة والقرار منطقي
- REJECT: إذا الموشرات القوية متضاربة أو السوق غير واضح أو يوجد خطر عالي
- تجاهل رأي الموشرات الضعيفة في قرارك
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
                "max_tokens": 200
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

        return verdict, advice

    except Exception as e:
        return "APPROVE", f"⚠️ Groq Error: {e}"
