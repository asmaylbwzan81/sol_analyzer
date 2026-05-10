import requests
import os

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

MIN_CONFIDENCE_FOR_REVIEW = 0.75


# ══════════════════════════════════════════════════════════════
# 🧠 الدالة المشتركة: تجهيز البيانات
# ══════════════════════════════════════════════════════════════
def _prepare_timeframes(scores, scores_1d, scores_4h, scores_1h):
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

    return extract(ind_1h), extract(ind_4h), extract(ind_1d)


# ══════════════════════════════════════════════════════════════
# 📝 بناء الـ Prompt (مشترك بين الاثنين)
# ══════════════════════════════════════════════════════════════
def _build_prompt(price, direction, final_score, tf_1h, tf_4h, tf_1d, pattern_stats=None, second_layer=False):
    note = "(هذه المراجعة الثانية — Groq وافق بالفعل، أنت الحكم الأخير)\n" if second_layer else ""

    if pattern_stats and pattern_stats.get("total", 0) > 0:
        history_line = f"📊 السجل التاريخي: {pattern_stats['text']}"
    else:
        history_line = "📊 السجل التاريخي: لا يوجد سجل كافٍ بعد"

    return f"""أنت محلل تداول خبير ومتحفظ. مهمتك مراجعة صفقة اجتازت فلاتر صارمة.
{note}
السعر: {price}
الاتجاه: {direction}
ثقة النظام: {round(final_score * 100)}%

{history_line}

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

أجب بهذا الشكل بالضبط (3 أسطر):
VERDICT: APPROVE أو REJECT
REASON: سبب قصير بالعربي
ADVICE: نصيحة واحدة بالعربي

قواعد القرار:
- APPROVE: 3 إطارات متوافقة والاتجاه واضح والسجل التاريخي إيجابي
- REJECT: تضارب بين الإطارات أو ADX ضعيف أو السجل التاريخي سلبي
- كن صارماً — حماية الرصيد أولاً
"""


# ══════════════════════════════════════════════════════════════
# 🔍 تحليل الرد (مشترك)
# ══════════════════════════════════════════════════════════════
def _parse_response(text):
    if not text: # ✅ فحص None أو فاضي
        return "REJECT", "رد فارغ من الذكاء", ""
    verdict = "APPROVE"
    reason = ""
    advice = ""
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("VERDICT:"):
            v = line.replace("VERDICT:", "").strip().upper()
            verdict = "REJECT" if "REJECT" in v else "APPROVE"
        elif line.startswith("REASON:"):
            reason = line.replace("REASON:", "").strip()
        elif line.startswith("ADVICE:"):
            advice = line.replace("ADVICE:", "").strip()
    return verdict, reason, advice


# ══════════════════════════════════════════════════════════════
# 🤖 الذكاء الأول: Groq (8B — سريع)
# ══════════════════════════════════════════════════════════════
def _review_groq(price, direction, final_score, tf_1h, tf_4h, tf_1d, pattern_stats=None):
    if not GROQ_API_KEY:
        return "REJECT", "لا يوجد Groq API Key", ""

    prompt = _build_prompt(price, direction, final_score, tf_1h, tf_4h, tf_1d, pattern_stats=pattern_stats, second_layer=False)

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
            timeout=30
        )
        data = res.json()
        if "choices" not in data:
            return "REJECT", f"خطأ: {data.get('error', {}).get('message', 'خطأ غير معروف')}", ""

        text = data["choices"][0]["message"]["content"]
        verdict, reason, advice = _parse_response(text)
        print(f"🤖 Groq → {verdict} | {reason} | {advice}")
        return verdict, reason, advice

    except requests.exceptions.Timeout:
        print("⏰ Groq تجاوز مهلة 30 ثانية — رُفضت الصفقة")
        return "REJECT", "لم يرد Groq خلال 30 ثانية", ""

    except Exception as e:
        print(f"❌ Groq Error: {e}")
        return "REJECT", f"خطأ في Groq: {e}", ""


# ══════════════════════════════════════════════════════════════
# 🦙 الذكاء الثاني: OpenRouter
# ══════════════════════════════════════════════════════════════
def _review_openrouter(price, direction, final_score, tf_1h, tf_4h, tf_1d, pattern_stats=None):
    if not OPENROUTER_API_KEY:
        return "REJECT", "لا يوجد OpenRouter API Key", ""

    prompt = _build_prompt(price, direction, final_score, tf_1h, tf_4h, tf_1d, pattern_stats=pattern_stats, second_layer=True)

    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/smart_analyzer",
            },
            json={
                "model": "openrouter/free",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 150
            },
            timeout=40
        )
        data = res.json()
        if "choices" not in data:
            print(f"⚠️ OpenRouter Error: {data}")
            return "REJECT", "خطأ في OpenRouter", ""

        text = data["choices"][0]["message"]["content"]
        verdict, reason, advice = _parse_response(text)
        print(f"🦙 OpenRouter → {verdict} | {reason} | {advice}")
        return verdict, reason, advice

    except requests.exceptions.Timeout:
        print("⏰ OpenRouter تجاوز مهلة 40 ثانية — رُفضت الصفقة")
        return "REJECT", "لم يرد OpenRouter خلال 40 ثانية", ""

    except Exception as e:
        print(f"❌ OpenRouter Error: {e}")
        return "REJECT", f"خطأ في OpenRouter: {e}", ""


# ══════════════════════════════════════════════════════════════
# 🚀 الدالة الرئيسية
# ══════════════════════════════════════════════════════════════
def review(scores, final_score, direction, price,
           scores_1d=None, scores_4h=None, scores_1h=None, pattern_stats=None):
    """
    طبقة مزدوجة: Groq أولاً ثم OpenRouter
    كلاهم لازم يوافقون — وإلا REJECT
    يرجع: (verdict, ai_advice, groq_reason, or_reason)
    """

    if final_score < MIN_CONFIDENCE_FOR_REVIEW:
        print(f"⏭️ AI Review تخطى — confidence={round(final_score,2)} أقل من {MIN_CONFIDENCE_FOR_REVIEW}")
        return "APPROVE", f"ثقة منخفضة ({round(final_score,2)}) — تم القبول التلقائي", "", ""

    if direction not in ("LONG", "SHORT"):
        return "REJECT", "اتجاه غير واضح", "", ""

    tf_1h, tf_4h, tf_1d = _prepare_timeframes(scores, scores_1d, scores_4h, scores_1h)

    groq_verdict, groq_reason, groq_advice = _review_groq(price, direction, final_score, tf_1h, tf_4h, tf_1d, pattern_stats=pattern_stats)

    if groq_verdict == "REJECT":
        return "REJECT", f"🤖 Groq رفض: {groq_reason}", groq_reason, ""

    or_verdict, or_reason, or_advice = _review_openrouter(price, direction, final_score, tf_1h, tf_4h, tf_1d, pattern_stats=pattern_stats)

    if or_verdict == "REJECT":
        return "REJECT", f"🦙 OpenRouter رفض: {or_reason}", groq_reason, or_reason

    return "APPROVE", "✅ Groq + OpenRouter وافقا", groq_reason, or_reason

