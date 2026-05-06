import requests
import os
import json

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

def review(scores, final_score, direction, price):
    if not GROQ_API_KEY:
        return "⚠️ No Groq API Key"

    prompt = f"""
أنت مراجع تداول ذكي. مهمتك مراجعة قرار التداول وإعطاء نصيحة قصيرة.

البيانات:
- السعر الحالي: {price}
- الاتجاه المقترح: {direction}
- النتيجة النهائية: {round(final_score, 2)}
- نتائج الاستراتيجيات: {json.dumps(scores, indent=2)}

اعطني:
1. هل القرار منطقي؟
2. ما أبرز نقطة تدعم أو تعارض القرار؟
3. نصيحة واحدة قصيرة

الجواب بـ 3 أسطر فقط بالعربي.
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
            return f"⚠️ Groq: {data.get('error', {}).get('message', 'خطأ غير معروف')}"
        return data["choices"][0]["message"]["content"].strip()

    except Exception as e:
        return f"⚠️ Groq Error: {e}"
