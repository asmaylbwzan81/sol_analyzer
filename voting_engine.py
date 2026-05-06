"""
voting_engine.py
================
Weighted Voting Engine
- يستخدم الأوزان الديناميكية من strategy_weights.py
- نفس الـ interface القديم: vote() و decision()
"""

from strategy_weights import weighted_score, init_db

# تهيئة قاعدة البيانات عند أول import
init_db()


def vote(scores: dict) -> float:
    """
    يحسب الـ score النهائي باستخدام الأوزان الديناميكية.
    scores : dict {strategy_name: signal_value}
    """
    return weighted_score(scores)


def decision(score: float):
    """
    يحدد قرار الدخول بناءً على الـ score.
    Returns: ("ENTER", "LONG") | ("ENTER", "SHORT") | ("SKIP", "NEUTRAL")
    """
    if score >= 0.65:
        return "ENTER", "LONG"
    elif score <= 0.35:
        return "ENTER", "SHORT"
    return "SKIP", "NEUTRAL"
