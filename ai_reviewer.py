"""
# ============================================================
# 🧠 AI Advisors System (v2 - Observer Mode)
# ============================================================
# Groq = Short-Term Risk Monitor
# Llama = Trade Quality Reviewer
#
# ✅ مستشارين فقط — لا يمنعون الصفقة
# ✅ يرجعون adjustments صغيرة لـ confidence
# ✅ Observer Mode في البداية لجمع البيانات
# ============================================================
"""

import requests
import os
import time
import json
import sqlite3
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MIN_CONFIDENCE_FOR_REVIEW = 0.75
DB = "ai_feedback.db"

# ✅ Observer Mode — لما True، AI يعطي رأيه بس ما يأثر على القرار
OBSERVER_MODE = True

# ✅ حدود التأثير على confidence
MAX_RISK_ADJUSTMENT = 0.10 # Groq: -0.10 إلى +0.10
MAX_QUALITY_ADJUSTMENT = 0.10 # Llama: -0.10 إلى +0.10

# ══════════════════════════════
# DB INIT
# ══════════════════════════════
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS ai_feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        groq_adjustment REAL,
        llama_adjustment REAL,
        base_confidence REAL,
        final_confidence REAL,
        groq_risk_level TEXT,
        llama_setup_quality TEXT,
        profit REAL,
        correct INTEGER,
        timestamp INTEGER
    )
    """)
    conn.commit()
    conn.close()

# ══════════════════════════════
# تسجيل قرار AI
# ══════════════════════════════
def log_ai_decision(groq_adj, llama_adj, base_conf, final_conf,
                     groq_risk, llama_quality, profit=None, correct=None):
    """يسجل قرار AI للتعلم لاحقاً"""
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("""INSERT INTO ai_feedback 
                     (groq_adjustment, llama_adjustment, base_confidence, final_confidence,
                      groq_risk_level, llama_setup_quality, profit, correct, timestamp)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (groq_adj, llama_adj, base_conf, final_conf,
                   groq_risk, llama_quality, profit, correct, int(time.time())))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ AI log error: {e}")

# ══════════════════════════════
# تجهيز البيانات من Features
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
# Prompt لـ Groq (Risk Monitor)
# ══════════════════════════════
def _build_groq_prompt(price, direction, features):
    f1 = features["1m"]
    f5 = features["5m"]

    return f"""أنت Risk Monitor لصفقة تداول. مهمتك تقييم المخاطر اللحظية فقط.

السعر: {price}
الاتجاه المقترح: {direction}

📊 Features 1m:
- Volatility: {f1['volatility']} | Vol Ratio: {f1['vol_ratio']}
- Entropy: {f1['entropy']} | Z-Score: {f1['zscore']}

📊 Features 5m:
- Volatility: {f5['volatility']} | Z-Score: {f5['zscore']}

⚠️ مهمتك: تقييم المخاطر فقط (لست متخذ قرار)

أجب بصيغة JSON فقط:
{{
  "risk_adjustment": -0.10 إلى +0.10,
  "risk_level": "low" أو "medium" أو "high",
  "comment": "تعليق قصير بالعربي"
}}

قواعد:
- مخاطر عالية (vol_ratio > 1.5, entropy > 0.7) → risk_adjustment سالب
- مخاطر منخفضة (entropy < 0.4, vol مستقر) → risk_adjustment موجب
- متوسط → 0.0
- لا تتجاوز ±0.10
"""

# ══════════════════════════════
# Prompt لـ Llama (Quality Reviewer)
# ══════════════════════════════
def _build_llama_prompt(price, direction, features):
    f1 = features["1m"]
    f5 = features["5m"]
    f15 = features["15m"]

    return f"""أنت Trade Quality Reviewer. مهمتك تقييم جودة الدخول فقط.

السعر: {price}
الاتجاه المقترح: {direction}

📊 1m: Z={f1['zscore']} | Momentum={f1['momentum_pct']} | MR={f1['mean_reversion']} | HistProb={f1['hist_prob_up']}
📊 5m: Z={f5['zscore']} | Momentum={f5['momentum_pct']} | HistProb={f5['hist_prob_up']}
📊 15m: Z={f15['zscore']} | Momentum={f15['momentum_pct']} | HistProb={f15['hist_prob_up']}

⚠️ مهمتك: تقييم جودة الدخول فقط (لست متخذ قرار)

أجب بصيغة JSON فقط:
{{
  "quality_adjustment": -0.10 إلى +0.10,
  "setup_quality": "poor" أو "fair" أو "good" أو "excellent",
  "comment": "تعليق قصير بالعربي"
}}

قواعد:
- توافق الفريمات الثلاثة → quality_adjustment موجب
- تضارب الفريمات → quality_adjustment سالب
- mean reversion واضح → موجب
- timing سيئ → سالب
- لا تتجاوز ±0.10
"""

# ══════════════════════════════
# تحليل JSON Response
# ══════════════════════════════
def _parse_json_response(text, default_adj=0.0, default_level="medium"):
    """يحاول استخراج JSON من رد الـ AI"""
    try:
        # نحاول نلاقي JSON في النص
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            json_str = text[start:end+1]
            data = json.loads(json_str)
            return data
    except:
        pass

    # fallback
    return {
        "adjustment": default_adj,
        "level": default_level,
        "comment": "تعذر تحليل الرد"
    }

# ══════════════════════════════
# Groq - Risk Monitor
# ══════════════════════════════
def _review_groq(price, direction, features):
    """Groq يرجع risk_adjustment و risk_level"""
    if not GROQ_API_KEY:
        return {"risk_adjustment": 0.0, "risk_level": "unknown", "comment": "لا يوجد API Key"}

    prompt = _build_groq_prompt(price, direction, features)
    deadline = time.time() + 30

    while time.time() < deadline:
        try:
            res = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150
                },
                timeout=min(deadline - time.time(), 10)
            )
            if res.status_code == 429:
                time.sleep(5)
                continue
            data = res.json()
            if "choices" not in data:
                return {"risk_adjustment": 0.0, "risk_level": "unknown", "comment": "خطأ API"}

            text = data["choices"][0]["message"]["content"]
            parsed = _parse_json_response(text)

            # استخراج القيم مع حماية
            risk_adj = float(parsed.get("risk_adjustment", 0.0))
            risk_adj = max(-MAX_RISK_ADJUSTMENT, min(MAX_RISK_ADJUSTMENT, risk_adj))

            risk_level = str(parsed.get("risk_level", "medium")).lower()
            comment = str(parsed.get("comment", ""))[:100]

            print(f"🤖 Groq [Risk] → adj={risk_adj:+.2f} | level={risk_level} | {comment}")

            return {
                "risk_adjustment": risk_adj,
                "risk_level": risk_level,
                "comment": comment
            }

        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            return {"risk_adjustment": 0.0, "risk_level": "unknown", "comment": f"خطأ: {e}"}

    return {"risk_adjustment": 0.0, "risk_level": "unknown", "comment": "Groq timeout"}

# ══════════════════════════════
# Llama - Quality Reviewer
# ══════════════════════════════
def _review_llama(price, direction, features):
    """Llama يرجع quality_adjustment و setup_quality"""
    if not GROQ_API_KEY:
        return {"quality_adjustment": 0.0, "setup_quality": "unknown", "comment": "لا يوجد API Key"}

    prompt = _build_llama_prompt(price, direction, features)
    deadline = time.time() + 40

    while time.time() < deadline:
        try:
            res = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150
                },
                timeout=min(deadline - time.time(), 15)
            )
            if res.status_code == 429:
                time.sleep(5)
                continue
            data = res.json()
            if "choices" not in data:
                return {"quality_adjustment": 0.0, "setup_quality": "unknown", "comment": "خطأ API"}

            text = data["choices"][0]["message"]["content"]
            parsed = _parse_json_response(text)

            quality_adj = float(parsed.get("quality_adjustment", 0.0))
            quality_adj = max(-MAX_QUALITY_ADJUSTMENT, min(MAX_QUALITY_ADJUSTMENT, quality_adj))

            setup_quality = str(parsed.get("setup_quality", "fair")).lower()
            comment = str(parsed.get("comment", ""))[:100]

            print(f"🦙 Llama [Quality] → adj={quality_adj:+.2f} | quality={setup_quality} | {comment}")

            return {
                "quality_adjustment": quality_adj,
                "setup_quality": setup_quality,
                "comment": comment
            }

        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            return {"quality_adjustment": 0.0, "setup_quality": "unknown", "comment": f"خطأ: {e}"}

    return {"quality_adjustment": 0.0, "setup_quality": "unknown", "comment": "Llama timeout"}

# ══════════════════════════════
# الدالة الرئيسية (v2 - Advisors Mode)
# ══════════════════════════════
def review(row, final_score, direction, price, pattern_stats=None):
    """
    ✅ الدالة الجديدة — AI كمستشارين فقط
    
    Returns:
        verdict: دائماً "APPROVE" (لأن AI ما يمنع)
        reason: ملخص النتيجة
        groq_comment: تعليق Groq
        llama_comment: تعليق Llama
    """
    if direction not in ("LONG", "SHORT"):
        return "APPROVE", "اتجاه غير واضح — تجاهل AI", "", ""

    # تجهيز Features
    features = _prepare_features(row)

    # ═══ Groq Risk Review ═══
    groq_result = _review_groq(price, direction, features)
    groq_adj = groq_result["risk_adjustment"]
    groq_risk = groq_result["risk_level"]
    groq_comment = groq_result["comment"]

    # ═══ Llama Quality Review ═══
    llama_result = _review_llama(price, direction, features)
    llama_adj = llama_result["quality_adjustment"]
    llama_quality = llama_result["setup_quality"]
    llama_comment = llama_result["comment"]

    # ═══ حساب Confidence النهائي ═══
    base_confidence = float(final_score)
    final_confidence = base_confidence + groq_adj + llama_adj
    final_confidence = max(0.0, min(1.0, final_confidence))

    # ═══ تسجيل القرار للتعلم ═══
    log_ai_decision(
        groq_adj=groq_adj,
        llama_adj=llama_adj,
        base_conf=base_confidence,
        final_conf=final_confidence,
        groq_risk=groq_risk,
        llama_quality=llama_quality
    )

    # ═══ في Observer Mode — AI ما يأثر على القرار ═══
    if OBSERVER_MODE:
        print(f"👁️ [Observer] Base={base_confidence:.2f} | Groq={groq_adj:+.2f} | Llama={llama_adj:+.2f} | Final={final_confidence:.2f}")
        reason = f"🤖 Risk={groq_risk} | 🦙 Quality={llama_quality} | Final={final_confidence:.2f}"
        return "APPROVE", reason, groq_comment, llama_comment

    # ═══ خارج Observer Mode — نتحقق من threshold ═══
    threshold = 0.50 # threshold قابل للتعديل لاحقاً
    if final_confidence >= threshold:
        reason = f"✅ AI Advisors | Final={final_confidence:.2f}"
        return "APPROVE", reason, groq_comment, llama_comment
    else:
        reason = f"❌ Confidence ضعيف ({final_confidence:.2f} < {threshold})"
        return "REJECT", reason, groq_comment, llama_comment

# ══════════════════════════════
# دوال للتوافق مع النظام القديم
# ══════════════════════════════
def get_ai_accuracy(window=100):
    """دقة AI من البيانات المسجلة"""
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("SELECT correct FROM ai_feedback WHERE correct IS NOT NULL ORDER BY id DESC LIMIT ?", (window,))
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

