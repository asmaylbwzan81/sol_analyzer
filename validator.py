import sqlite3
import numpy as np
import pandas as pd
from features import extract_features
from backtester import backtest_strategy
from redis_store import load_best

DB_PATH = "market_data.db"
SYMBOL = "BTC-USDT"
INTERVAL = "5m"

# ══════════════════════════════
# تحميل بيانات جديدة من BingX
# ══════════════════════════════
def load_new_data(limit=5000):
    """يجيب أحدث 5000 شمعة = بيانات جديدة"""
    import requests
    import time

    BINGX_BASE = "https://open-api.bingx.com"
    all_candles = []
    end_time = None
    target = limit
    MAX_PER_REQUEST = 1440

    while len(all_candles) < target:
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

    return all_candles[:target]

# ══════════════════════════════
# التحقق
# ══════════════════════════════
def validate():
    print("🔍 بدء التحقق من الاستراتيجية...")
    print("━" * 40)

    # تحميل الاستراتيجية من Redis
    saved = load_best()
    if not saved:
        print("❌ ما في استراتيجية محفوظة في Redis!")
        return

    strategy = saved["strategy"]
    train_stats = saved["stats"]

    print(f"📂 الاستراتيجية المحفوظة:")
    for cond in strategy["conditions"]:
        print(f" {cond['feature']} {cond['operator']} {cond['threshold']}")
    print(f" Direction: {strategy['direction']}")
    print(f"\n📊 نتائج التدريب:")
    print(f" Win Rate: {train_stats['win_rate']*100:.1f}%")
    print(f" Profit: {train_stats['total_profit']*100:.1f}%")
    print(f" Drawdown: {train_stats['drawdown']*100:.1f}%")

    # جلب بيانات جديدة
    print(f"\n📥 جلب 5000 شمعة جديدة...")
    new_candles = load_new_data(5000)
    print(f"✅ {len(new_candles)} شمعة")

    # تحويل لـ DataFrame
    df = pd.DataFrame(new_candles)
    df = extract_features(df)
    print(f"✅ Features جاهزة: {len(df)} صف")

    # اختبار الاستراتيجية
    print(f"\n⚙️ اختبار على البيانات الجديدة...")
    stats = backtest_strategy(strategy, df)

    if not stats:
        print("❌ ما في صفقات كافية على البيانات الجديدة!")
        return

    print(f"\n{'═'*40}")
    print(f"📊 نتائج التحقق (Out-of-sample):")
    print(f" Win Rate: {stats['win_rate']*100:.1f}%")
    print(f" Total Profit: {stats['total_profit']*100:.1f}%")
    print(f" Profit Factor: {stats['profit_factor']}")
    print(f" Drawdown: {stats['drawdown']*100:.1f}%")
    print(f" Sharpe: {stats['sharpe']:.2f}")
    print(f" Trades: {stats['trades']}")

    print(f"\n{'═'*40}")
    print(f"📋 المقارنة:")
    print(f" التدريب: Win={train_stats['win_rate']*100:.1f}% | Profit={train_stats['total_profit']*100:.1f}%")
    print(f" التحقق: Win={stats['win_rate']*100:.1f}% | Profit={stats['total_profit']*100:.1f}%")

    diff = abs(train_stats['win_rate'] - stats['win_rate'])

    if stats['win_rate'] > 0.55 and diff < 0.15:
        print(f"\n✅ الاستراتيجية حقيقية! الفرق={diff*100:.1f}% — جاهزة للتنفيذ 🚀")
    else:
        print(f"\n❌ Overfitting! الفرق={diff*100:.1f}% — تحتاج مزيد من التطوير")

if __name__ == "__main__":
    validate()
