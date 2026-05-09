"""
layer_decision.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
نظام القرار الطبقي الجديد
بديل عن vote_engine.py القديم
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ══════════════════════════════════════════════════
# 🏗️ تعريف الطبقات
# ══════════════════════════════════════════════════

# 🟢 طبقة الاتجاه — تحدد LONG/SHORT/NO_TRADE
TREND_LAYER = {"ema", "supertrend", "adx"}

# 🟡 طبقة الزخم — تؤكد أو تضعف الدخول
MOMENTUM_LAYER = {"rsi", "macd", "stochastic", "momentum"}

# 🔵 طبقة السيولة — تتحقق من قوة الحركة
LIQUIDITY_LAYER = {"volume", "vwap", "atr"}

# 🟣 طبقة الهيكل — تحدد أفضل مناطق الدخول
STRUCTURE_LAYER = {"fibonacci", "support_resistance", "pattern"}

# 🟠 طبقة التقلب — حالة السوق فقط
VOLATILITY_LAYER = {"bollinger"}

# 🤖 طبقة الذكاء — فلتر نهائي (news + memory)
AI_LAYER = {"news", "memory"}


def _classify(name: str) -> str:
    """يرجع اسم الطبقة لأي مؤشر"""
    n = name.lower()
    if n in TREND_LAYER: return "trend"
    if n in MOMENTUM_LAYER: return "momentum"
    if n in LIQUIDITY_LAYER: return "liquidity"
    if n in STRUCTURE_LAYER: return "structure"
    if n in VOLATILITY_LAYER: return "volatility"
    if n in AI_LAYER: return "ai"
    return "unknown"


def _score_to_signal(score: float) -> str:
    """تحويل رقم (0-1) إلى إشارة نصية"""
    if score >= 0.62: return "LONG"
    if score <= 0.38: return "SHORT"
    return "NEUTRAL"


# ══════════════════════════════════════════════════
# 🟢 STEP 1: طبقة الاتجاه
# ══════════════════════════════════════════════════

def _analyze_trend(combined: dict) -> dict:
    """
    يحلل مؤشرات الاتجاه ويقرر:
    LONG / SHORT / NO_TRADE
    """
    trend_scores = {k: v for k, v in combined.items() if k in TREND_LAYER}

    if not trend_scores:
        return {"direction": "NO_TRADE", "confidence": 0, "details": {}}

    details = {}
    long_votes = 0
    short_votes = 0

    for name, score in trend_scores.items():
        sig = _score_to_signal(score)
        reason = _trend_reason(name, score, sig)
        details[name] = {
            "signal": sig,
            "score": round(score, 3),
            "reason": reason
        }
        if sig == "LONG": long_votes += 1
        if sig == "SHORT": short_votes += 1

    total = len(trend_scores)
    confidence = max(long_votes, short_votes) / total

    if long_votes > short_votes and confidence >= 0.67:
        direction = "LONG"
    elif short_votes > long_votes and confidence >= 0.67:
        direction = "SHORT"
    else:
        direction = "NO_TRADE" # خلاف بين المؤشرات → لا تداول

    return {
        "direction": direction,
        "confidence": round(confidence, 2),
        "long_votes": long_votes,
        "short_votes": short_votes,
        "details": details
    }


def _trend_reason(name: str, score: float, signal: str) -> str:
    if name == "ema":
        if signal == "LONG": return "EMA20 فوق EMA50 — اتجاه صاعد"
        if signal == "SHORT": return "EMA20 تحت EMA50 — اتجاه هابط"
        return "EMA متقاربة — سوق جانبي"
    if name == "supertrend":
        if signal == "LONG": return "Supertrend أخضر — صاعد"
        if signal == "SHORT": return "Supertrend أحمر — هابط"
        return "Supertrend محايد"
    if name == "adx":
        if score >= 0.62: return f"ADX قوي ({round(score,2)}) — اتجاه واضح صاعد"
        if score <= 0.38: return f"ADX قوي ({round(score,2)}) — اتجاه واضح هابط"
        return f"ADX ضعيف ({round(score,2)}) — سوق بدون اتجاه"
    return f"score={round(score,2)}"


# ══════════════════════════════════════════════════
# 🔵 STEP 2: فلتر السيولة
# ══════════════════════════════════════════════════

def _analyze_liquidity(combined: dict) -> dict:
    """
    يتحقق: هل الحركة حقيقية أو وهمية؟
    يرجع: PASS / BLOCK
    """
    liq_scores = {k: v for k, v in combined.items() if k in LIQUIDITY_LAYER}

    if not liq_scores:
        return {"status": "PASS", "reason": "لا بيانات سيولة", "details": {}}

    details = {}
    weak_count = 0

    for name, score in liq_scores.items():
        sig = _score_to_signal(score)
        reason = _liquidity_reason(name, score, sig)
        details[name] = {
            "signal": sig,
            "score": round(score, 3),
            "reason": reason
        }
        if sig == "NEUTRAL":
            weak_count += 1

    # إذا أغلب مؤشرات السيولة محايدة → حركة وهمية
    if weak_count >= 2:
        status = "BLOCK"
        block_reason = "سيولة ضعيفة — الحركة غير مدعومة بفلوس حقيقية"
    else:
        status = "PASS"
        block_reason = "سيولة كافية"

    return {
        "status": status,
        "reason": block_reason,
        "weak_count": weak_count,
        "details": details
    }


def _liquidity_reason(name: str, score: float, signal: str) -> str:
    if name == "volume":
        if signal == "LONG": return "حجم مرتفع — ضغط شراء"
        if signal == "SHORT": return "حجم مرتفع — ضغط بيع"
        return "حجم ضعيف — لا اهتمام"
    if name == "vwap":
        if signal == "LONG": return "السعر فوق VWAP — مشترون مسيطرون"
        if signal == "SHORT": return "السعر تحت VWAP — بائعون مسيطرون"
        return "السعر عند VWAP — توازن"
    if name == "atr":
        if signal == "NEUTRAL": return "تقلب منخفض — سوق هادئ"
        return f"تقلب ATR={round(score,2)}"
    return f"score={round(score,2)}"


# ══════════════════════════════════════════════════
# 🟡 STEP 3: طبقة الزخم
# ══════════════════════════════════════════════════

def _analyze_momentum(combined: dict, direction: str) -> dict:
    """
    يقيس قوة الحركة في اتجاه Trend Layer
    يرجع: score زخم بين 0-1 + تفاصيل
    """
    mom_scores = {k: v for k, v in combined.items() if k in MOMENTUM_LAYER}

    if not mom_scores:
        return {"momentum_score": 0.5, "confirmation": "WEAK", "details": {}}

    details = {}
    confirm_count = 0

    for name, score in mom_scores.items():
        sig = _score_to_signal(score)
        confirms = (sig == direction)
        reason = _momentum_reason(name, score, sig)
        details[name] = {
            "signal": sig,
            "score": round(score, 3),
            "confirms_trend": confirms,
            "reason": reason
        }
        if confirms:
            confirm_count += 1

    ratio = confirm_count / len(mom_scores)
    if ratio >= 0.75: confirmation = "STRONG"
    elif ratio >= 0.50: confirmation = "MODERATE"
    else: confirmation = "WEAK"

    avg_score = sum(mom_scores.values()) / len(mom_scores)

    return {
        "momentum_score": round(avg_score, 4),
        "confirmation": confirmation,
        "confirm_ratio": round(ratio, 2),
        "details": details
    }


def _momentum_reason(name: str, score: float, signal: str) -> str:
    if name == "rsi":
        if score <= 0.35: return f"RSI منطقة تشبع بيع — احتمال ارتداد صاعد"
        if score >= 0.65: return f"RSI منطقة تشبع شراء — احتمال تصحيح"
        return f"RSI منطقة محايدة ({round(score,2)})"
    if name == "macd":
        if signal == "LONG": return "MACD تقاطع صاعد"
        if signal == "SHORT": return "MACD تقاطع هابط"
        return "MACD بدون إشارة واضحة"
    if name == "stochastic":
        if score <= 0.35: return "Stochastic ذروة بيع"
        if score >= 0.65: return "Stochastic ذروة شراء"
        return "Stochastic منطقة وسط"
    if name == "momentum":
        if signal == "LONG": return "زخم إيجابي متصاعد"
        if signal == "SHORT": return "زخم سلبي متراجع"
        return "زخم ضعيف"
    return f"score={round(score,2)}"


# ══════════════════════════════════════════════════
# 🟣 STEP 4: طبقة الهيكل
# ══════════════════════════════════════════════════

def _analyze_structure(combined: dict, direction: str) -> dict:
    """يحدد هل الدخول في منطقة جيدة هيكلياً"""
    str_scores = {k: v for k, v in combined.items() if k in STRUCTURE_LAYER}

    if not str_scores:
        return {"status": "NEUTRAL", "details": {}}

    details = {}
    confirm_count = 0

    for name, score in str_scores.items():
        sig = _score_to_signal(score)
        confirms = (sig == direction)
        reason = _structure_reason(name, score, sig)
        details[name] = {
            "signal": sig,
            "score": round(score, 3),
            "confirms_trend": confirms,
            "reason": reason
        }
        if confirms:
            confirm_count += 1

    ratio = confirm_count / len(str_scores)
    status = "CONFIRM" if ratio >= 0.5 else "WEAK"

    return {
        "status": status,
        "confirm_ratio": round(ratio, 2),
        "details": details
    }


def _structure_reason(name: str, score: float, signal: str) -> str:
    if name == "fibonacci":
        if signal == "LONG": return "السعر عند مستوى Fib دعم — فرصة صعود"
        if signal == "SHORT": return "السعر عند مستوى Fib مقاومة — فرصة هبوط"
        return "السعر بين مستويات Fibonacci"
    if name == "support_resistance":
        if signal == "LONG": return "السعر عند منطقة دعم قوية"
        if signal == "SHORT": return "السعر عند منطقة مقاومة قوية"
        return "السعر في منطقة وسط"
    if name == "pattern":
        if signal == "LONG": return "نمط انعكاسي صاعد مكتشف"
        if signal == "SHORT": return "نمط انعكاسي هابط مكتشف"
        return "لا نمط واضح"
    return f"score={round(score,2)}"


# ══════════════════════════════════════════════════
# 🟠 STEP 5: طبقة التقلب (Bollinger)
# ══════════════════════════════════════════════════

def _analyze_volatility(combined: dict) -> dict:
    """يحدد حالة السوق — لا يعطي اتجاه"""
    bb_score = combined.get("bollinger")

    if bb_score is None:
        return {"state": "UNKNOWN", "action": "ALLOW", "reason": "لا بيانات Bollinger"}

    if 0.45 <= bb_score <= 0.55:
        state = "SQUEEZE"
        action = "WAIT"
        reason = "Bollinger ضيق — سوق هادئ، انتظر كسر"
    elif bb_score >= 0.75 or bb_score <= 0.25:
        state = "EXPANSION"
        action = "ALLOW"
        reason = "Bollinger موسع — بداية حركة قوية"
    elif bb_score >= 0.68:
        state = "OVERBOUGHT"
        action = "CAUTION"
        reason = "Bollinger منطقة تشبع شراء — احذر من LONG"
    elif bb_score <= 0.32:
        state = "OVERSOLD"
        action = "CAUTION"
        reason = "Bollinger منطقة تشبع بيع — احذر من SHORT"
    else:
        state = "MID_RANGE"
        action = "ALLOW"
        reason = "Bollinger منطقة وسط — حركة عادية"

    return {
        "state": state,
        "action": action, # ALLOW / WAIT / CAUTION
        "score": round(bb_score, 3),
        "reason": reason
    }


# ══════════════════════════════════════════════════
# 🤖 STEP 6: طبقة الذكاء (News + Memory)
# ══════════════════════════════════════════════════

def _analyze_ai_layer(combined: dict, direction: str) -> dict:
    """يحلل الأخبار والذاكرة كفلتر أخير"""
    ai_scores = {k: v for k, v in combined.items() if k in AI_LAYER}

    if not ai_scores:
        return {"status": "NEUTRAL", "details": {}}

    details = {}
    risk_count = 0

    for name, score in ai_scores.items():
        sig = _score_to_signal(score)
        against = (sig != direction and sig != "NEUTRAL")
        reason = _ai_reason(name, score, sig)
        details[name] = {
            "signal": sig,
            "score": round(score, 3),
            "against_trend": against,
            "reason": reason
        }
        if against:
            risk_count += 1

    status = "RISK" if risk_count >= 1 else "CLEAR"

    return {
        "status": status,
        "risk_count": risk_count,
        "details": details
    }


def _ai_reason(name: str, score: float, signal: str) -> str:
    if name == "news":
        if signal == "LONG": return "أخبار إيجابية تدعم الصعود"
        if signal == "SHORT": return "أخبار سلبية تضغط للهبوط"
        return "لا أخبار مؤثرة"
    if name == "memory":
        if signal == "LONG": return "تاريخ الصفقات يدعم LONG هنا"
        if signal == "SHORT": return "تاريخ الصفقات يدعم SHORT هنا"
        return "لا ذاكرة كافية"
    return f"score={round(score,2)}"


# ══════════════════════════════════════════════════
# 🧠 القرار النهائي الموحد
# ══════════════════════════════════════════════════

def layer_decision(combined: dict) -> dict:
    """
    النظام الطبقي الكامل
    ━━━━━━━━━━━━━━━━━━━━━
    المدخل: combined scores (dict مؤشر → float 0-1)
    المخرج: قرار كامل مع debug لكل طبقة
    """

    debug = {}

    # ── STEP 1: الاتجاه ──────────────────────────
    trend = _analyze_trend(combined)
    debug["trend_layer"] = trend
    direction = trend["direction"]

    if direction == "NO_TRADE":
        return {
            "action": "SKIP",
            "direction": "NEUTRAL",
            "reason": f"❌ Trend Layer: خلاف بين مؤشرات الاتجاه (confidence={trend['confidence']})",
            "debug": debug
        }

    # ── STEP 2: السيولة ──────────────────────────
    liquidity = _analyze_liquidity(combined)
    debug["liquidity_layer"] = liquidity

    if liquidity["status"] == "BLOCK":
        return {
            "action": "SKIP",
            "direction": direction,
            "reason": f"❌ Liquidity Layer: {liquidity['reason']}",
            "debug": debug
        }

    # ── STEP 3: الزخم ────────────────────────────
    momentum = _analyze_momentum(combined, direction)
    debug["momentum_layer"] = momentum

    if momentum["confirmation"] == "WEAK":
        return {
            "action": "SKIP",
            "direction": direction,
            "reason": f"❌ Momentum Layer: زخم ضعيف لا يؤكد الاتجاه ({direction})",
            "debug": debug
        }

    # ── STEP 4: الهيكل ───────────────────────────
    structure = _analyze_structure(combined, direction)
    debug["structure_layer"] = structure

    # الهيكل لا يمنع الدخول لكن يضعف الثقة
    structure_ok = (structure["status"] == "CONFIRM")

    # ── STEP 5: التقلب ───────────────────────────
    volatility = _analyze_volatility(combined)
    debug["volatility_layer"] = volatility

    if volatility["action"] == "WAIT":
        return {
            "action": "SKIP",
            "direction": direction,
            "reason": f"❌ Volatility Layer: {volatility['reason']}",
            "debug": debug
        }

    # ── STEP 6: طبقة الذكاء ──────────────────────
    ai_layer = _analyze_ai_layer(combined, direction)
    debug["ai_layer"] = ai_layer

    # ── حساب الثقة النهائية ──────────────────────
    confidence_score = _calc_confidence(
        trend, momentum, structure, liquidity, volatility, ai_layer
    )
    debug["final_confidence"] = round(confidence_score, 4)

    # ── القرار النهائي ───────────────────────────
    min_confidence = 0.60

    if confidence_score < min_confidence:
        return {
            "action": "SKIP",
            "direction": direction,
            "reason": f"❌ ثقة منخفضة ({round(confidence_score,2)}) — الحد الأدنى {min_confidence}",
            "debug": debug
        }

    # تحذير AI لكنه لا يمنع الدخول (Groq هو الفلتر الحقيقي)
    ai_warning = ""
    if ai_layer["status"] == "RISK":
        ai_warning = " ⚠️ تحذير AI Layer"

    return {
        "action": "ENTER",
        "direction": direction,
        "confidence": round(confidence_score, 4),
        "reason": f"✅ كل الطبقات اجتازت | {direction} | confidence={round(confidence_score,2)}{ai_warning}",
        "structure_confirmed": structure_ok,
        "debug": debug
    }


def _calc_confidence(trend, momentum, structure, liquidity, volatility, ai_layer) -> float:
    """
    حساب الثقة النهائية من كل الطبقات
    الأوزان:
    - Trend: 40%
    - Momentum: 30%
    - Structure: 15%
    - Liquidity: 10%
    - AI: 5%
    """
    # Trend
    trend_score = trend["confidence"] * 0.40

    # Momentum
    mom_map = {"STRONG": 1.0, "MODERATE": 0.6, "WEAK": 0.2}
    mom_score = mom_map.get(momentum["confirmation"], 0.2) * 0.30

    # Structure
    str_map = {"CONFIRM": 1.0, "WEAK": 0.4, "NEUTRAL": 0.5}
    str_score = str_map.get(structure["status"], 0.5) * 0.15

    # Liquidity
    liq_map = {"PASS": 1.0, "BLOCK": 0.0}
    liq_score = liq_map.get(liquidity["status"], 0.5) * 0.10

    # AI
    ai_map = {"CLEAR": 1.0, "NEUTRAL": 0.7, "RISK": 0.3}
    ai_score = ai_map.get(ai_layer["status"], 0.7) * 0.05

    return trend_score + mom_score + str_score + liq_score + ai_score


# ══════════════════════════════════════════════════
# 📊 Debug Printer
# ══════════════════════════════════════════════════

def print_debug(symbol: str, result: dict):
    """يطبع تقرير واضح لكل طبقة"""
    print(f"\n{'━'*50}")
    print(f"🪙 {symbol} | Action: {result['action']} {result['direction']}")
    print(f"📝 {result['reason']}")

    debug = result.get("debug", {})

    # Trend Layer
    if "trend_layer" in debug:
        t = debug["trend_layer"]
        print(f"\n🟢 Trend Layer → {t['direction']} (confidence={t['confidence']})")
        for name, d in t.get("details", {}).items():
            icon = "✅" if d["signal"] != "NEUTRAL" else "⚪"
            print(f" {icon} {name}: {d['signal']} | {d['reason']}")

    # Liquidity Layer
    if "liquidity_layer" in debug:
        l = debug["liquidity_layer"]
        icon = "✅" if l["status"] == "PASS" else "🚫"
        print(f"\n🔵 Liquidity Layer → {icon} {l['status']} | {l['reason']}")
        for name, d in l.get("details", {}).items():
            print(f" • {name}: {d['signal']} | {d['reason']}")

    # Momentum Layer
    if "momentum_layer" in debug:
        m = debug["momentum_layer"]
        icon = "✅" if m["confirmation"] != "WEAK" else "⚠️"
        print(f"\n🟡 Momentum Layer → {icon} {m['confirmation']} (ratio={m['confirm_ratio']})")
        for name, d in m.get("details", {}).items():
            tick = "✅" if d["confirms_trend"] else "❌"
            print(f" {tick} {name}: {d['signal']} | {d['reason']}")

    # Structure Layer
    if "structure_layer" in debug:
        s = debug["structure_layer"]
        icon = "✅" if s["status"] == "CONFIRM" else "⚠️"
        print(f"\n🟣 Structure Layer → {icon} {s['status']} (ratio={s['confirm_ratio']})")
        for name, d in s.get("details", {}).items():
            tick = "✅" if d["confirms_trend"] else "❌"
            print(f" {tick} {name}: {d['signal']} | {d['reason']}")

    # Volatility Layer
    if "volatility_layer" in debug:
        v = debug["volatility_layer"]
        icon = "✅" if v["action"] == "ALLOW" else ("⏳" if v["action"] == "WAIT" else "⚠️")
        print(f"\n🟠 Volatility Layer → {icon} {v['state']} | {v['reason']}")

    # AI Layer
    if "ai_layer" in debug:
        a = debug["ai_layer"]
        icon = "✅" if a["status"] == "CLEAR" else "⚠️"
        print(f"\n🤖 AI Layer → {icon} {a['status']}")
        for name, d in a.get("details", {}).items():
            print(f" • {name}: {d['signal']} | {d['reason']}")

    # Final
    if "final_confidence" in debug:
        print(f"\n🏆 Final Confidence: {debug['final_confidence']}")

    print(f"{'━'*50}")

