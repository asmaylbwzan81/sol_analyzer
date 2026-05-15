import requests
import os
import time
import sqlite3
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MIN_CONFIDENCE_FOR_REVIEW = 0.75
DB = "ai_feedback.db"

# ══════════════════════════════
# DB INIT
# ══════════════════════════════
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS ai_feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        verdict TEXT,
        profit REAL,
        correct INTEGER
    )
    """)
    conn.commit()
    conn.close()

# ══════════════════════════════
# تسجيل نتيجة AI
# ══════════════════════════════
def log_ai_decision(verdict, profit, expected_direction, actual_direction):
    try:
        profit = float(profit or 0.0)
        correct = 1 if (expected_direction == actual_direction and profit > 0) else 0
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("INSERT INTO ai_feedback (verdict, profit, correct) VALUES (?, ?, ?)",
                  (verdict, profit, correct))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ AI log error: {e}")

# ══════════════════════════════
# دقة AI
# ══════════════════════════════
def get_ai_accuracy(window=100):
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("SELECT correct FROM ai_feedback ORDER BY id DESC LIMIT ?", (window,))
        rows = c.fetchall()
        conn.close()
        if not rows:
            return 0.5
        return float(max(0.0, min(1.0, sum(r[0] for r in rows) / len(rows))))
    except:
        return 0.5

def get_ai_penalty(window=100):
    return max(0.0, min(1.0, 1.0 - get_ai_accuracy(window)))

def adjust_ai_weight(base_weight=0.25, window=100):
    penalty = get_ai_penalty(window)
    return {
        "base_weight": base_weight,
        "accuracy": 1.0 - penalty,
        "penalty": penalty,
        "final_weight": base_weight * (1.0 - penalty * 0.8)
    }

# ══════════════════════════════
# تجهيز البيانات من Features الجديدة
# ══════════════════════════════
def _prepare_features(row):
    def g(key, default=0.5):
        val = row.get(key, default)
        if val is None or (isinstance(val, float) and (val != val)):
            return default
        return round(float(val), 4)

    return {
        "1m": {
            "zscore": g("1m_zscore"),
            "momentum_pct": g("1m_momentum_pct"),
            "volatility": g("1m_volatility"),
            "entropy": g("1m_entropy"),
            "autocorr": g("1m_autocorr_1"),
            "hist_prob_up": g("1m_hist_prob_up"),
            "vol_ratio": g("1m_vol_ratio"),
            "mean_reversion": g("1m_mean_reversion"),
        },
        "5m": {
            "zscore": g("5m_zscore"),
            "momentum_pct": g("5m_momentum_pct"),
            "volatility": g("5m_volatility"),
            "hist_prob_up": g("5m_hist_prob_up"),
        },
        "15m": {
            "zscore": g("15m_zscore"),
            "momentum_pct": g("15m_momentum_pct"),
            "volatility": g("15m_volatility"),
            "hist_prob_up": g("15m_hist_prob_up"),
        },
    }

# ══════════════════════════════
# بناء الـ Prompt
# ══════════════════════════════
def _build_prompt(price, direction, final_score, features, pattern_stats=None, second_layer=False):
    note = "(هذه المراجعة الثانية — الذكاء الأول وافق، أنت الحكم الأخير)\n" if second_layer else ""

    if pattern_stats and pattern_stats.get("total", 0) > 0:
        history_line = f"📊 السجل التاريخي: {pattern_stats['text']}"
        history_rule = "- سجل إيجابي فوق 60% = عامل داعم | سلبي تحت 40% = عامل ضد"
    else:
        history_line = "📊 السجل التاريخي: لا يوجد — قرر بناءً على الـ Features فقط"
        history_rule = "- لا سجل تاريخي — ركز على الـ Features الإحصائية"

    f1 = features["1m"]
    f5 = features["5m"]
    f15 = features["15m"]

    return f"""أنت محلل Quant خبير. مهمتك مراجعة صفقة اجتازت فلاتر إحصائية صارمة.
{note}
السعر: {price}
الاتجاه: {direction}
ثقة النظام: {round(final_score * 100)}%

{history_line}

📊 Features الفريم 1m (الدخول):
- Z-Score: {f1['zscore']} | Mean Reversion: {f1['mean_reversion']}
- Momentum%: {f1['momentum_pct']} | Entropy: {f1['entropy']}
- Volatility: {f1['volatility']} | Vol Ratio: {f1['vol_ratio']}
- Autocorr: {f1['autocorr']} | Hist Prob Up: {f1['hist_prob_up']}

📊 Features الفريم 5m (التأكيد):
- Z-Score: {f5['zscore']} | Momentum%: {f5['momentum_pct']}
- Volatility: {f5['volatility']} | Hist Prob Up: {f5['hist_prob_up']}

📊 Features الفريم 15m (الاتجاه العام):
- Z-Score: {f15['zscore']} | Momentum%: {f15['momentum_pct']}
- Volatility: {f15['volatility']} | Hist Prob Up: {f15['hist_prob_up']}

قواعد التحليل:
- Z-Score > 2 = تشبع شراء → SHORT | Z-Score < -2 = تشبع بيع → LONG
- Mean Reversion < -1 = السعر تحت المتوسط → LONG محتمل
- Momentum% > 0 = زخم صاعد | < 0 = زخم هابط
- Hist Prob Up > 0.55 = احتمال صعود تاريخي عالي
- Entropy عالي = سوق فوضوي → تحذير
- Vol Ratio > 1.5 = تقلب غير طبيعي → تحذير
{history_rule}

أجب بهذا الشكل بالضبط (3 أسطر فقط):
VERDICT: APPROVE أو REJECT
REASON: سبب قصير بالعربي
ADVICE: نصيحة واحدة بالعربي

قواعد القرار:
- APPROVE: الـ Features متوافقة مع الاتجاه في الفريمات الثلاثة
- REJECT: تضارب بين الفريمات أو entropy عالي أو vol ratio مرتفع جداً
- كن صارماً — حماية الرصيد أولاً
"""

# ══════════════════════════════
# تحليل الرد
# ══════════════════════════════
def _parse_response(text):
    if not text:
        return "REJECT", "رد فارغ", ""
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

# ══════════════════════════════
# Groq - Llama 3.1 8B
# ══════════════════════════════
def _review_groq(price, direction, final_score, features, pattern_stats=None):
    if not GROQ_API_KEY:
        return "REJECT", "لا يوجد Groq API Key", ""

    prompt = _build_prompt(price, direction, final_score, features, pattern_stats, second_layer=False)
    deadline = time.time() + 30

    while time.time() < deadline:
        try:
            res = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}], "max_tokens": 150},
                timeout=min(deadline - time.time(), 10)
            )
            if res.status_code == 429:
                time.sleep(5)
                continue
            data = res.json()
            if "choices" not in data:
                return "REJECT", f"خطأ: {data.get('error', {}).get('message', '')}", ""
            text = data["choices"][0]["message"]["content"]
            verdict, reason, advice = _parse_response(text)
            print(f"🤖 Groq → {verdict} | {reason}")
            return verdict, reason, advice
        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            return "REJECT", f"خطأ Groq: {e}", ""

    return "REJECT", "Groq timeout", ""

# ══════════════════════════════
# Groq - Llama 3.3 70B
# ══════════════════════════════
def _review_llama70(price, direction, final_score, features, pattern_stats=None):
    if not GROQ_API_KEY:
        return "REJECT", "لا يوجد Groq API Key", ""

    prompt = _build_prompt(price, direction, final_score, features, pattern_stats, second_layer=True)
    deadline = time.time() + 40

    while time.time() < deadline:
        try:
            res = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "max_tokens": 150},
                timeout=min(deadline - time.time(), 15)
            )
            if res.status_code == 429:
                time.sleep(5)
                continue
            data = res.json()
            if "choices" not in data:
                return "REJECT", "خطأ Llama 70B", ""
            text = data["choices"][0]["message"]["content"]
            verdict, reason, advice = _parse_response(text)
            print(f"🦙 Llama70B → {verdict} | {reason}")
            return verdict, reason, advice
        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            return "REJECT", f"خطأ Llama70B: {e}", ""

    return "REJECT", "Llama70B timeout", ""

# ══════════════════════════════
# الدالة الرئيسية
# ══════════════════════════════
def review(row, final_score, direction, price, pattern_stats=None):
    if final_score < MIN_CONFIDENCE_FOR_REVIEW:
        return "APPROVE", f"ثقة منخفضة ({round(final_score,2)}) — قبول تلقائي", "", ""

    if direction not in ("LONG", "SHORT"):
        return "REJECT", "اتجاه غير واضح", "", ""

    features = _prepare_features(row)

    groq_verdict, groq_reason, _ = _review_groq(price, direction, final_score, features, pattern_stats)

    if groq_verdict == "REJECT":
        return "REJECT", f"🤖 Groq رفض: {groq_reason}", groq_reason, ""

    llama_verdict, llama_reason, _ = _review_llama70(price, direction, final_score, features, pattern_stats)

    if llama_verdict == "REJECT":
        return "REJECT", f"🦙 Llama رفض: {llama_reason}", groq_reason, llama_reason

    return "APPROVE", "✅ Groq + Llama وافقا", groq_reason, llama_reason
