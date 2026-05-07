from strategy_weights import weighted_score, init_db

init_db()

def vote(scores: dict) -> float:
    return weighted_score(scores)

def decision(score: float, scores: dict = None):
    if scores:
        total = len(scores)
        bullish = len([v for v in scores.values() if v >= 0.65])
        bearish = len([v for v in scores.values() if v <= 0.35])

        if score >= 0.60:
            if bullish > total * 0.5:
                return "ENTER", "LONG"
            return "SKIP", "NEUTRAL"

        elif score <= 0.40:
            if bearish > total * 0.5:
                return "ENTER", "SHORT"
            return "SKIP", "NEUTRAL"

    if score >= 0.60:
        return "ENTER", "LONG"
    elif score <= 0.40:
        return "ENTER", "SHORT"
    return "SKIP", "NEUTRAL"
