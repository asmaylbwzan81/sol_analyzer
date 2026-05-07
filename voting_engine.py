voting_engine.py
================
Weighted Voting Engine
- يستخدم الأوزان الديناميكية من strategy_weights.py
- نفس الـ interface: vote() و decision()
"""

from strategy_weights import weighted_score, init_db

# import تهيئة قاعدة البيانات عند أول تشغيل
init_db()


def vote(scores: dict) -> float:
    """
    النهائي باستخدام الأوزان الديناميكية يحسب الـ score.
    scores : dict {strategy_name: signal_value}
    """
    return weighted_score(scores)


def decision(score: float, scores: dict = None):
    """
    يحدد قرار الدخول بناءً على الـ score والأغلبية الديناميكية.
    Returns: ("ENTER", "LONG") | ("ENTER", "SHORT") | ("SKIP", "NEUTRAL")
    """
    if scores:
        total = len(scores)
        bullish = len([v for v in scores.values() if v >= 0.65])
        bearish = len([v for v in scores.values() if v <= 0.35])

        if score >= 0.60:
            if bullish > total * 0.5: # أكثر من النص متفقين على صعود
                return "ENTER", "LONG"
            return "SKIP", "NEUTRAL"

        elif score <= 0.40:
            if bearish > total * 0.5: # أكثر من النص متفقين على نزول
                return "ENTER", "SHORT"
            return "SKIP", "NEUTRAL"

    # fallback للطريقة القديمة لو ما مررنا scores
    if score >= 0.60:
        return "ENTER", "LONG"
    elif score <= 0.40:
        return "ENTER", "SHORT"
    return "SKIP", "NEUTRAL"

