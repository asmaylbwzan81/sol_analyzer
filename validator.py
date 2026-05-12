import numpy as np
import pandas as pd
from features import extract_features
from backtester import backtest_strategy
from redis_store import load_best

# ══════════════════════════════
# نختبر على BTC 1h — فريم مختلف
# ══════════════════════════════
SYMBOL = "BTC-USDT"
INTERVAL = "1h"

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
    print("🔍 بدء التحقق على BTC 1h...")
    print("━" * 40)

    saved = load_best()
    if not saved:
        print("❌ ما في استراتيجية في Redis!")
        return

    strategy = saved["strategy"]
    train_stats = saved["stats"]

    print(f"📂 الاستراتيجية (تعلّمت على BTC 5m):")
    for cond in strategy["conditions"]:
        print(f" {cond['feature']} {cond['operator']} {cond['threshold']}")
    print(f" Direction: {strategy['direction']}")
    print(f"\n📊 نتائج التدريب (5m):")
    print(f" Win Rate: {train_stats['win_rate']*100:.1f}%")
    print(f" Profit: {train_stats['total_profit']*100:.1f}%")
    print(f" Drawdown: {train_stats['drawdown']*100:.1f}%")

    print(f"\n📥 جلب 5000 شمعة BTC 1h...")
    new_candles = load_new_data(5000)
    print(f"✅ {len(new_candles)} شمعة")

    df = pd.DataFrame(new_candles)
    df = extract_features(df)
    print(f"✅ Features: {len(df)} صف")

    print(f"\n⚙️ اختبار على BTC 1h...")
    stats = backtest_strategy(strategy, df)

    if not stats:
        print("❌ ما في صفقات كافية على 1h!")
        print("⚠️ الاستراتيجية مرتبطة بـ 5m فقط = Overfitting")
        return

    print(f"\n{'═'*40}")
    print(f"📊 نتائج BTC 1h:")
    print(f" Win Rate: {stats['win_rate']*100:.1f}%")
    print(f" Total Profit: {stats['total_profit']*100:.1f}%")
    print(f" Profit Factor: {stats['profit_factor']}")
    print(f" Drawdown: {stats['drawdown']*100:.1f}%")
    print(f" Sharpe: {stats['sharpe']:.2f}")
    print(f" Trades: {stats['trades']}")

    diff = abs(train_stats['win_rate'] - stats['win_rate'])

    print(f"\n{'═'*40}")
    print(f"📋 المقارنة:")
    print(f" 5m: Win={train_stats['win_rate']*100:.1f}%")
    print(f" 1h: Win={stats['win_rate']*100:.1f}%")
    print(f" الفرق: {diff*100:.1f}%")

    if stats['win_rate'] > 0.55 and diff < 0.20:
        print(f"\n✅ الاستراتيجية حقيقية! تعمل على 5m و 1h 🏆")
        print(f"🚀 جاهزة للتنفيذ!")
    else:
        print(f"\n❌ Overfitting! تعمل على 5m فقط")
        print(f"🔄 نكمل التطوير...")

if __name__ == "__main__":
    validate()
