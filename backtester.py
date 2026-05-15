import numpy as np
import pandas as pd
from collections import defaultdict

# ══════════════════════════════
# إعدادات
# ══════════════════════════════
SL_PCT = 0.0020
TP_PCT = 0.0050
FEE = 0.0005
TOTAL_FEE = FEE * 2
MIN_TRADES = 200
MAX_CANDLES_WAIT = 30
SLIPPAGE = 0.0002
SPREAD = 0.0001
COOLDOWN_PERIOD = 3
EXECUTION_DELAY = 2 # شموع تأخير تنفيذ

# Walk Forward
TRAIN_RATIO = 0.60
TEST_RATIO = 0.20
PURGE_GAP = 0.05 # منع تسرب البيانات

# ══════════════════════════════
# Regime Detection - Z-Score Adaptive
# ══════════════════════════════
def detect_regime(df):
    close = df["close"].values
    regimes = []
    window = 20

    for i in range(len(close)):
        if i < window:
            regimes.append("ranging")
            continue

        chunk = close[i-window:i]
        returns = np.diff(chunk) / chunk[:-1]
        volatility = np.std(returns)
        trend = (chunk[-1] - chunk[0]) / chunk[0]

        vol_history = []
        for k in range(max(0, i-100), i):
            if k < window:
                continue
            c = close[k-window:k]
            r = np.diff(c) / c[:-1]
            vol_history.append(np.std(r))

        if len(vol_history) < 5:
            regimes.append("ranging")
            continue

        vol_mean = np.mean(vol_history)
        vol_std = np.std(vol_history)
        z_score = (volatility - vol_mean) / (vol_std + 1e-10)

        if z_score > 2:
            regimes.append("high_volatility")
        elif z_score < -1:
            regimes.append("low_volatility")
        elif abs(trend) > 0.005:
            regimes.append("trending")
        else:
            regimes.append("ranging")

    return regimes

# ══════════════════════════════
# Execution Simulator - Dynamic + Delay
# ══════════════════════════════
def simulate_execution(entry, direction, volatility=0.001):
    dynamic_slippage = SLIPPAGE * (1 + volatility * 10)
    if direction == "LONG":
        return entry * (1 + dynamic_slippage + SPREAD)
    else:
        return entry * (1 - dynamic_slippage - SPREAD)

# ══════════════════════════════
# Failure Memory - Bucketed Analysis
# ══════════════════════════════
def analyze_failures(failures):
    if not failures or len(failures) < 5:
        return {}

    df = pd.DataFrame(failures)

    vol_mean = df["volatility"].mean()
    vol_buckets = {
        "low_vol_losses": len(df[df["volatility"] < vol_mean * 0.5]),
        "mid_vol_losses": len(df[(df["volatility"] >= vol_mean * 0.5) & (df["volatility"] < vol_mean * 1.5)]),
        "high_vol_losses": len(df[df["volatility"] >= vol_mean * 1.5]),
    }

    return {
        "high_vol_loss_ratio": len(df[df["volatility"] > vol_mean]) / len(df),
        "regime_weakness": df["regime"].value_counts().to_dict(),
        "vol_buckets": vol_buckets,
        "total_failures": len(df),
    }

# ══════════════════════════════
# Dynamic Risk Engine - Market Based
# ══════════════════════════════
def dynamic_risk(trades, market_volatility=None, max_consecutive_losses=5, daily_loss_limit=-0.02):
    if not trades:
        return True

    trades_arr = np.array(trades)

    # Market volatility kill switch
    if market_volatility and market_volatility > 0.02:
        return False

    # Consecutive losses
    consecutive = 0
    for t in trades_arr:
        if t < 0:
            consecutive += 1
            if consecutive >= max_consecutive_losses:
                return False
        else:
            consecutive = 0

    # Daily loss limit
    if trades_arr.sum() < daily_loss_limit:
        return False

    # Max exposure
    if len(trades_arr) > 0:
        recent = trades_arr[-20:] if len(trades_arr) >= 20 else trades_arr
        if recent.sum() < -0.01:
            return False

    return True

# ══════════════════════════════
# Monte Carlo - Real Equity Curve
# ══════════════════════════════
def monte_carlo(real_trades, n_simulations=200):
    if len(real_trades) < MIN_TRADES:
        return False

    trades = np.array(real_trades)
    stable_count = 0

    for _ in range(n_simulations):
        shuffled = np.random.permutation(trades)
        random_slippage = np.random.uniform(-0.0002, 0.0002, len(shuffled))
        simulated = shuffled + random_slippage

        equity = np.cumsum(simulated)
        win_rate = len(simulated[simulated > 0]) / len(simulated)
        peak = np.maximum.accumulate(equity)
        dd = ((peak - equity) / (np.abs(peak) + 1e-10)).max()

        if win_rate > 0.48 and dd < 0.20:
            stable_count += 1

    return (stable_count / n_simulations) > 0.70

# ══════════════════════════════
# Strategy Correlation Filter
# ══════════════════════════════
def filter_correlated(results, max_correlation=0.80):
    if len(results) <= 1:
        return results

    # نبني signals لكل استراتيجية
    signals_list = []
    for r in results:
        sig = r.get("signals", [])
        signals_list.append(sig)

    if not any(signals_list):
        return results

    # نحذف الاستراتيجيات المتشابهة
    kept = [results[0]]
    for i in range(1, len(results)):
        is_correlated = False
        for j in range(len(kept)):
            s1 = np.array(signals_list[i], dtype=float)
            s2 = np.array(signals_list[results.index(kept[j])], dtype=float)
            min_len = min(len(s1), len(s2))
            if min_len < 10:
                continue
            corr = np.corrcoef(s1[:min_len], s2[:min_len])[0, 1]
            if abs(corr) > max_correlation:
                is_correlated = True
                break
        if not is_correlated:
            kept.append(results[i])

    return kept

# ══════════════════════════════
# Score Function - Normalized
# ══════════════════════════════
def calc_score(stats):
    pf = stats["profit_factor"]
    wr = stats["win_rate"]
    dd = stats["drawdown"]
    sharpe = stats["sharpe"]
    stability = stats["stability"]
    trades = stats["trades"]

    raw_score = (
        np.log1p(pf) * 40 +
        wr * 25 -
        (dd ** 1.5) * 50 +
        sharpe * 10 -
        stability * 20 +
        np.log1p(trades)
    )

    return round(raw_score, 4)

def normalize_scores(results):
    if not results:
        return results

    scores = [r["stats"]["score"] for r in results]
    mean_s = np.mean(scores)
    std_s = np.std(scores) + 1e-10

    for r in results:
        r["stats"]["normalized_score"] = round((r["stats"]["score"] - mean_s) / std_s, 4)

    return results

# ══════════════════════════════
# حساب الإحصاء
# ══════════════════════════════
def calc_stats(trades):
    if len(trades) < MIN_TRADES:
        return None

    trades = np.array(trades)
    wins = trades[trades > 0]
    losses = trades[trades < 0]

    if len(losses) == 0:
        return None

    win_rate = len(wins) / len(trades)
    total_profit = trades.sum()
    profit_factor = wins.sum() / (abs(losses.sum()) + 1e-10)

    cumulative = np.cumsum(trades)
    peak = np.maximum.accumulate(cumulative)
    drawdown = ((peak - cumulative) / (np.abs(peak) + 1e-10)).max()

    sharpe = trades.mean() / (trades.std() + 1e-10) * np.sqrt(len(trades))
    avg_profit = trades.mean()

    chunk_size = max(10, len(trades) // 5)
    chunks = [trades[i:i+chunk_size] for i in range(0, len(trades), chunk_size)]
    chunk_wr = [len(c[c>0])/len(c) for c in chunks if len(c) > 5]
    stability = np.std(chunk_wr) if chunk_wr else 1.0

    stats = {
        "trades": len(trades),
        "win_rate": round(win_rate, 4),
        "total_profit": round(total_profit, 4),
        "profit_factor": round(profit_factor, 4),
        "drawdown": round(drawdown, 4),
        "sharpe": round(sharpe, 4),
        "avg_profit": round(avg_profit, 6),
        "stability": round(stability, 4),
        "score": 0,
        "normalized_score": 0,
    }

    stats["score"] = calc_score(stats)
    return stats

# ══════════════════════════════
# اختبار استراتيجية واحدة
# ══════════════════════════════
def backtest_strategy(strategy, df):
    from strategy_generator import apply_strategy

    trades = []
    failures = []
    signals = []
    rows = df.to_dict("records")
    regimes = detect_regime(df)
    last_trade_index = -COOLDOWN_PERIOD

    for i in range(len(rows) - 1 - EXECUTION_DELAY):
        row = rows[i]
        regime = regimes[i]

        if i - last_trade_index < COOLDOWN_PERIOD:
            continue

        if regime == "high_volatility":
            signals.append(0)
            continue

        signal = apply_strategy(strategy, row)
        signals.append(1 if signal else 0)

        if not signal:
            continue

        # Execution Delay - دخول بعد EXECUTION_DELAY شموع
        exec_index = i + EXECUTION_DELAY
        if exec_index >= len(rows):
            continue

        entry = rows[exec_index]["close"]
        direction = strategy["direction"]
        volatility = row.get("1m_volatility", 0.001)

        real_entry = simulate_execution(entry, direction, volatility)

        if direction == "LONG":
            sl = real_entry * (1 - SL_PCT)
            tp = real_entry * (1 + TP_PCT)
        else:
            sl = real_entry * (1 + SL_PCT)
            tp = real_entry * (1 - TP_PCT)

        result = None
        for j in range(exec_index + 1, min(exec_index + MAX_CANDLES_WAIT + 1, len(rows))):
            high = rows[j]["high"]
            low = rows[j]["low"]

            if direction == "LONG":
                if low <= sl:
                    result = -SL_PCT - TOTAL_FEE - SLIPPAGE - SPREAD
                    break
                if high >= tp:
                    result = TP_PCT - TOTAL_FEE - SLIPPAGE - SPREAD
                    break
            else:
                if high >= sl:
                    result = -SL_PCT - TOTAL_FEE - SLIPPAGE - SPREAD
                    break
                if low <= tp:
                    result = TP_PCT - TOTAL_FEE - SLIPPAGE - SPREAD
                    break

        if result is not None:
            trades.append(result)
            last_trade_index = i
            if result < 0:
                failures.append({
                    "regime": regime,
                    "volatility": volatility,
                    "volume": row.get("1m_volume_change", 0),
                })

    return calc_stats(trades), failures, trades, signals

# ══════════════════════════════
# Walk Forward - Rolling + Purge Gap
# ══════════════════════════════
def walk_forward_test(strategy, df):
    n = len(df)
    train_size = int(n * TRAIN_RATIO)
    test_size = int(n * TEST_RATIO)
    purge_size = int(n * PURGE_GAP)
    step = int(n * 0.10)

    all_window_stats = []
    passed = 0
    total = 0

    for start in range(0, n - train_size - purge_size - test_size, step):
        train_df = df.iloc[start:start+train_size]
        # Purge Gap - منع تسرب البيانات
        test_start = start + train_size + purge_size
        test_df = df.iloc[test_start:test_start+test_size]

        if len(train_df) < 100 or len(test_df) < 50:
            continue

        train_stats, _, _, _ = backtest_strategy(strategy, train_df)
        if not train_stats or train_stats["win_rate"] < 0.52:
            total += 1
            continue

        test_stats, failures, _, _ = backtest_strategy(strategy, test_df)
        if not test_stats:
            total += 1
            continue

        total += 1
        if test_stats["win_rate"] > 0.50:
            passed += 1
            all_window_stats.append(test_stats)

    if total == 0 or passed / total < 0.60:
        return None

    if not all_window_stats:
        return None

    avg_wr = np.mean([s["win_rate"] for s in all_window_stats])
    avg_pf = np.mean([s["profit_factor"] for s in all_window_stats])
    avg_dd = np.mean([s["drawdown"] for s in all_window_stats])
    avg_sharpe = np.mean([s["sharpe"] for s in all_window_stats])
    total_trades = sum([s["trades"] for s in all_window_stats])
    avg_profit = np.mean([s["avg_profit"] for s in all_window_stats])

    combined = {
        "trades": total_trades,
        "win_rate": round(avg_wr, 4),
        "total_profit": round(sum([s["total_profit"] for s in all_window_stats]), 4),
        "profit_factor": round(avg_pf, 4),
        "drawdown": round(avg_dd, 4),
        "sharpe": round(avg_sharpe, 4),
        "avg_profit": round(avg_profit, 6),
        "stability": round(np.std([s["win_rate"] for s in all_window_stats]), 4),
        "score": 0,
        "normalized_score": 0,
    }
    combined["score"] = calc_score(combined)
    return combined

# ══════════════════════════════
# Ensemble Signal - Weighted
# ══════════════════════════════
def ensemble_signal(strategies, row, weights=None):
    from strategy_generator import apply_strategy

    if weights is None:
        weights = [1.0] * len(strategies)

    total_weight = sum(weights)
    confidence = 0

    for strategy, weight in zip(strategies, weights):
        if apply_strategy(strategy, row):
            confidence += weight / total_weight

    return confidence, confidence > 0.5

# ══════════════════════════════
# اختبار كل الاستراتيجيات
# ══════════════════════════════
def run_backtest(population, df):
    results = []

    for i, strategy in enumerate(population):
        if i % 100 == 0:
            print(f"⚙️ اختبار {i}/{len(population)}...")

        wf_stats = walk_forward_test(strategy, df)
        if not wf_stats:
            continue

        raw_stats, failures, real_trades, signals = backtest_strategy(strategy, df)
        if not raw_stats or not real_trades:
            continue

        # Monte Carlo على الصفقات الحقيقية
        if not monte_carlo(real_trades):
            continue

        # Dynamic Risk
        market_vol = df["1m_volatility"].mean() if "1m_volatility" in df.columns else None
        if not dynamic_risk(real_trades, market_volatility=market_vol):
            continue

        failure_analysis = analyze_failures(failures)

        results.append({
            "strategy": strategy,
            "stats": wf_stats,
            "failure_analysis": failure_analysis,
            "signals": signals,
        })

    # Normalize scores
    results = normalize_scores(results)

    # Filter correlated strategies
    results = filter_correlated(results)

    return results

# ══════════════════════════════
# فلترة الأفضل
# ══════════════════════════════
def filter_best(results, top_n=10):
    qualified = [
        r for r in results
        if r["stats"]["win_rate"] > 0.50
        and r["stats"]["drawdown"] < 0.15
        and r["stats"]["profit_factor"] > 1.2
        and r["stats"]["avg_profit"] > TOTAL_FEE
        and r["stats"]["trades"] >= MIN_TRADES
    ]

    qualified.sort(key=lambda x: x["stats"].get("normalized_score", 0), reverse=True)
    return qualified[:top_n]
