import json
import numpy as np
import pandas as pd
from features import extract_features
from backtester import backtest_strategy

# ══════════════════════════════
# نختبر استراتيجية BTC على SOL 5m
# ══════════════════════════════
SYMBOL = "SOL-USDT"
INTERVAL = "5m"

def load_strategy_from_file():
    return {
        "strategy": {
            "conditions": [
                {"feature": "std_50", "operator": "<", "threshold": 0.0019},
                {"feature": "std_50", "operator": ">", "threshold": 0.001769},
                {"feature": "mean_reversion", "operator": "<", "threshold": -1.103387}
            ],
            "direction": "LONG"
        },
        "stats": {
            "trades": 55,
            "win_rate": 0.8364,
            "total_profit": 1.245,
            "profit_factor": 10.2222,
            "drawdown": 0.0568,
            "sharpe": 10.0841
        }
    }

def load_new_data(limit=5000):
    import requests
    import time

    BINGX_BASE = "https://open-api.bingx.com"
    all_candles = []
    end_time = None
    MAX_PER_REQUEST = 1440

    while len(all_candles) < limit:
        try:
            params = {
                "symbol": SYMBOL,
                "interval": INTERVAL,
                "limit": MAX_PER_REQUEST
            }
            if end_time:
                params["endTime"] = end_time

            response = requests.get(
                f"{BINGX_BASE}/openApi/swap/v2/quote/klines",
                params=params,
                timeout=10
            ).json()

            candles = response.get("data", [])
            if not candles:
                break

            candles = sorted(candles, key=lambda x: x["time"])
            batch = [{
                "timestamp": int(c["time"]),
                "open": float(c["open"]),
                "high": float(c["high"]),
                "low": float(c["low"]),
                "close": float(c["close"]),
                "volume": float(c["volume"])
            } for c in candles]

            all_candles = batch + all_candles
            end_time = candles[0]["time"] - 1
            time.sleep(0.3)

        except Exception as e:
            print(f"❌ خطأ: {e}")
            break

    return all_candles[:limit]

def validate():
    print("🔍 بدء التحقق — استراتيجية BTC على SOL 1h...")
    print("━" * 40)

    saved = load_strategy_from_file()
    if not saved:
        print("❌ ما في استراتيجية في Redis!")
        return

    strategy = saved["strategy"]
    train_stats = saved["stats"]

    print(f"📂 الاستراتيجية (تعلّمت على BTC 5m):")
    for cond in strategy["conditions"]:
        print(f" {cond['feature']} {cond['operator']} {cond['threshold']}")
    print(f" Direction: {strategy['direction']}")
    print(f"\n📊 نتائج التدريب على BTC (5m):")
    print(f" Win Rate: {train_stats['win_rate']*100:.1f}%")
    print(f" Profit: {train_stats['total_profit']*100:.1f}%")
    print(f" Drawdown: {train_stats['drawdown']*100:.1f}%")

    print(f"\n📥 جلب 5000 شمعة SOL 1h...")
    new_candles = load_new_data(5000)
    print(f"✅ {len(new_candles)} شمعة")

    df = pd.DataFrame(new_candles)
    df = extract_features(df)
    print(f"✅ Features: {len(df)} صف")

    print(f"\n⚙️ اختبار استراتيجية BTC على SOL 5m...")
    stats, failures, trades, signals = backtest_strategy(strategy, df)

    if not stats:
        print("❌ ما في صفقات كافية على SOL!")
        print("⚠️ الاستراتيجية مرتبطة بـ BTC فقط")
        return

    print(f"\n{'═'*40}")
    print(f"📊 نتائج SOL 1h:")
    print(f" Win Rate: {stats['win_rate']*100:.1f}%")
    print(f" Total Profit: {stats['total_profit']*100:.1f}%")
    print(f" Profit Factor: {stats['profit_factor']}")
    print(f" Drawdown: {stats['drawdown']*100:.1f}%")
    print(f" Sharpe: {stats['sharpe']:.2f}")
    print(f" Trades: {stats['trades']}")

    diff = abs(train_stats['win_rate'] - stats['win_rate'])

    print(f"\n{'═'*40}")
    print(f"📋 المقارنة:")
    print(f" BTC 5m: Win={train_stats['win_rate']*100:.1f}%")
    print(f" SOL 1h: Win={stats['win_rate']*100:.1f}%")
    print(f" الفرق: {diff*100:.1f}%")

    if stats['win_rate'] > 0.55 and diff < 0.20:
        print(f"\n✅ الاستراتيجية تعمل على SOL أيضاً! 🏆")
        print(f"🚀 يمكن تطبيقها على SOL!")
    else:
        print(f"\n❌ الاستراتيجية مرتبطة بـ BTC فقط")
        print(f"🔄 SOL يحتاج استراتيجية خاصة")

if __name__ == "__main__":
    validate()

