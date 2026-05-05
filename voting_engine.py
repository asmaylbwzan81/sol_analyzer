def vote(scores):
    values = list(scores.values())
    total = sum(values)
    return total / len(values)

def decision(score):
    if score >= 0.70:
        return "ENTER", "LONG"
    elif score <= 0.30:
        return "ENTER", "SHORT"
    return "SKIP", "NEUTRAL"
