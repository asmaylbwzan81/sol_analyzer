def vote(scores):
    total = sum(scores.values())
    return total / len(scores)

def decision(score):
    if score >= 0.70:
        return "ENTER", "LONG"
    elif score <= 0.30:
        return "ENTER", "SHORT"
    return "SKIP", "NEUTRAL"
