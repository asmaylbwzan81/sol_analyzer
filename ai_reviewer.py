import requests
import os
import json

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")


def review(scores, final_score, direction, price):
    """
    يراجع قرار التداول ويرجع:
    - verdict: "APPROVE" أو "REJECT"
    - advice: نص قصير بالعربي
    """
    if not GROQ_API_KEY:
        return "APPROVE", "⚠️ No Groq API Key"

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
- نتائج الاستراتيجيات: {json.dumps(scores, indent=2)}

أجب بهذا الشكل بالضبط (3 أسطر فقط):
VERDICT: APPROVE أو REJECT
REASON: سبب قصير جداً
ADVICE: نصيحة واحدة قصيرة

قواعد القرار:
- APPROVE: إذا المؤشرات متوافقة والقرار منطقي
- REJECT: إذا المؤشرات متضاربة أو السوق غير واضح أو يوجد خطر عالي
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

        # استخراج VERDICT و ADVICE من الجواب
        verdict = "APPROVE"
        advice = text

        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("VERDICT:"):
                v = line.replace("VERDICT:", "").strip().upper()
                if "REJECT" in v:
                    verdict = "REJECT"
                else:
                    verdict = "APPROVE"
            elif line.startswith("ADVICE:"):
                advice = line.replace("ADVICE:", "").strip()

        return verdict, advice

    except Exception as e:
        return "APPROVE", f"⚠️ Groq Error: {e}"

