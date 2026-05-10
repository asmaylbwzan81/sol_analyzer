import requests
import os
import time

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

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
            "chop": ind.get("chop", 0.5), # ✅ بدل adx
            "hma": ind.get("hma", 0.5), # ✅ بدل ema
            "macd": ind.get("macd", 0.5),
            "volume": ind.get("volume", 0.5),
        }

    return extract(ind_1h), extract(ind_4h), extract(ind_1d)


# ══════════════════════════════════════════════════════════════
# 📝 بناء الـ Prompt
# ══════════════════════════════════════════════════════════════
def _build_prompt(price, direction, final_score, tf_1h, tf_4h, tf_1d, pattern_stats=None, second_layer=False):
    note = "(هذه المراجعة الثانية — Groq وافق بالفعل، أنت الحكم الأخير)\n" if second_layer else ""

    if pattern_stats and pattern_stats.get("total", 0) > 0:
        history_line = f"📊 السجل التاريخي: {pattern_stats['text']} — خذه بعين الاعتبار مع التحليل"
        history_rule = "- إذا كان السجل التاريخي إيجابياً (فوق 60%) = عامل داعم للدخول"
        history_rule += "\n- إذا كان السجل التاريخي سلبياً (تحت 40%) = عامل ضد الدخول"
    else:
        history_line = "📊 السجل التاريخي: لا يوجد سجل بعد — قرر بناءً على المؤشرات فقط ولا ترفض بسبب غياب التاريخ"
        history_rule = "- لا يوجد سجل تاريخي — ركز على المؤشرات التقنية فقط"

    return f"""أنت محلل تداول خبير ومتحفظ. مهمتك مراجعة صفقة اجتازت فلاتر صارمة.
{note}
السعر: {price}
الاتجاه: {direction}
ثقة النظام: {round(final_score * 100)}%

{history_line}

📊 مؤشرات الساعة (1H):
- RSI: {tf_1h['rsi']} | CHOP: {tf_1h['chop']}
- HMA: {tf_1h['hma']} | MACD: {tf_1h['macd']}
- Volume: {tf_1h['volume']}

📊 مؤشرات 4 ساعات (4H):
- RSI: {tf_4h['rsi']} | CHOP: {tf_4h['chop']}
- HMA: {tf_4h['hma']} | MACD: {tf_4h['macd']}

📊 مؤشرات يومي (1D):
- RSI: {tf_1d['rsi']} | CHOP: {tf_1d['chop']}
- HMA: {tf_1d['hma']} | MACD: {tf_1d['macd']}

قواعد (القيم بين 0-1):
- RSI < 0.35 = تشبع بيع → LONG | RSI > 0.65 = تشبع شراء → SHORT
- HMA > 0.5 = صاعد | HMA < 0.5 = هابط
- CHOP > 0.6 = ترند قوي | CHOP < 0.4 = سوق متذبذب
- MACD > 0.5 = زخم صاعد | MACD < 0.5 = هابط
{history_rule}

يجب أن تجيب بهذا الشكل بالضبط (3 أسطر فقط باللغة العربية):
VERDICT: APPROVE أو REJECT
REASON: سبب قصير بالعربي
ADVICE: نصيحة واحدة بالعربي

قواعد القرار:
- APPROVE: 3 إطارات متوافقة والاتجاه واضح
- REJECT: تضارب بين الإطارات أو CHOP ضعيف
- كن صارماً — حماية الرصيد أولاً
- أجب بالعربية فقط
"""


# ══════════════════════════════════════════════════════════════
# 🔍 تحليل الرد (مشترك)
# ══════════════════════════════════════════════════════════════
def _parse_response(text):
    if not text:
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
# 🤖 الذكاء الأول: Groq — Llama 3.1 8B (سريع)
# ══════════════════════════════════════════════════════════════
def _review_groq(price, direction, final_score, tf_1h, tf_4h, tf_1d, pattern_stats=None):
    if not GROQ_API_KEY:
        return "REJECT", "لا يوجد Groq API Key", ""

    prompt = _build_prompt(price, direction, final_score, tf_1h, tf_4h, tf_1d, pattern_stats=pattern_stats, second_layer=False)
    deadline = time.time() + 30

    while time.time() < deadline:
        try:
            remaining = deadline - time.time()
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
                timeout=min(remaining, 10)
            )

            if res.status_code == 429:
                print("⏳ Groq: rate limit — انتظار 5 ثواني...")
                time.sleep(5)
                continue

            data = res.json()
            if "choices" not in data:
                return "REJECT", f"خطأ: {data.get('error', {}).get('message', 'خطأ غير معروف')}", ""

            text = data["choices"][0]["message"]["content"]
            verdict, reason, advice = _parse_response(text)
            print(f"🤖 Groq → {verdict} | {reason}")
            return verdict, reason, advice

        except requests.exceptions.Timeout:
            print("⏰ Groq timeout — إعادة المحاولة...")
            continue
        except Exception as e:
            print(f"❌ Groq Error: {e}")
            return "REJECT", f"خطأ في Groq: {e}", ""

    print("⏰ Groq انتهى وقته — رُفضت الصفقة")
    return "REJECT", "لم يرد Groq خلال 30 ثانية", ""


# ══════════════════════════════════════════════════════════════
# 🦙 الذكاء الثاني: Groq — Llama 3.3 70B (أقوى)
# ══════════════════════════════════════════════════════════════
def _review_llama70(price, direction, final_score, tf_1h, tf_4h, tf_1d, pattern_stats=None):
    if not GROQ_API_KEY:
        return "REJECT", "لا يوجد Groq API Key", ""

    prompt = _build_prompt(price, direction, final_score, tf_1h, tf_4h, tf_1d, pattern_stats=pattern_stats, second_layer=True)
    deadline = time.time() + 40

    while time.time() < deadline:
        try:
            remaining = deadline - time.time()
            res = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150
                },
                timeout=min(remaining, 15)
            )

            if res.status_code == 429:
                print("⏳ Llama70B: rate limit — انتظار 5 ثواني...")
                time.sleep(5)
                continue

            data = res.json()
            if "choices" not in data:
                print(f"⚠️ Llama70B Error: {data}")
                return "REJECT", "خطأ في Llama 70B", ""

            text = data["choices"][0]["message"]["content"]
            verdict, reason, advice = _parse_response(text)
            print(f"🦙 Llama70B → {verdict} | {reason}")
            return verdict, reason, advice

        except requests.exceptions.Timeout:
            print("⏰ Llama70B timeout — إعادة المحاولة...")
            continue
        except Exception as e:
            print(f"❌ Llama70B Error: {e}")
            return "REJECT", f"خطأ في Llama 70B: {e}", ""

    print("⏰ Llama70B انتهى وقته — رُفضت الصفقة")
    return "REJECT", "لم يرد Llama 70B خلال 40 ثانية", ""


# ══════════════════════════════════════════════════════════════
# 🚀 الدالة الرئيسية — تسلسل ✅
# ══════════════════════════════════════════════════════════════
def review(scores, final_score, direction, price,
           scores_1d=None, scores_4h=None, scores_1h=None, pattern_stats=None):
    if final_score < MIN_CONFIDENCE_FOR_REVIEW:
        print(f"⏭️ AI Review تخطى — confidence={round(final_score,2)} أقل من {MIN_CONFIDENCE_FOR_REVIEW}")
        return "APPROVE", f"ثقة منخفضة ({round(final_score,2)}) — تم القبول التلقائي", "", ""

    if direction not in ("LONG", "SHORT"):
        return "REJECT", "اتجاه غير واضح", "", ""

    tf_1h, tf_4h, tf_1d = _prepare_timeframes(scores, scores_1d, scores_4h, scores_1h)

    # ── الذكاء الأول: Groq ───────────────────
    groq_verdict, groq_reason, _ = _review_groq(price, direction, final_score, tf_1h, tf_4h, tf_1d, pattern_stats=pattern_stats)

    if groq_verdict == "REJECT":
        print(f"🤖 Groq رفض — ما يوصل Llama 70B")
        return "REJECT", f"🤖 Groq رفض: {groq_reason}", groq_reason, ""

    # ── الذكاء الثاني: Llama 70B ─────────────
    or_verdict, or_reason, _ = _review_llama70(price, direction, final_score, tf_1h, tf_4h, tf_1d, pattern_stats=pattern_stats)

    if or_verdict == "REJECT":
        return "REJECT", f"🦙 Llama رفض: {or_reason}", groq_reason, or_reason

    return "APPROVE", "✅ Groq + Llama وافقا", groq_reason, or_reason

