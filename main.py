import time
from datetime import datetime
from data_engine import init_db, fetch_candles, save_candles, load_candles, count_candles
from features import load_data, extract_features

TARGET = 20000

def main():
    print("🚀 Quant Bot Started")
    print("━" * 40)

    # ══════════════════════════════
    # 1️⃣ تجهيز البيانات
    # ══════════════════════════════
    print("📊 فحص قاعدة البيانات...")
    init_db()

    existing = count_candles()
    if existing < TARGET:
        print(f"📥 جاري جلب البيانات... (موجود: {existing})")
        candles = fetch_candles()
        save_candles(candles)
        print(f"✅ تم الحفظ: {count_candles()} شمعة")
    else:
        print(f"✅ البيانات جاهزة: {existing} شمعة")

    # ══════════════════════════════
    # 2️⃣ استخراج الـ Features
    # ══════════════════════════════
    print("\n📐 حساب الـ Features...")
    df = load_data()
    df = extract_features(df)
    print(f"✅ Features جاهزة: {len(df)} صف")
    print(f"\n📊 إحصاء:\n{df[['zscore','volatility','momentum']].describe().round(4)}")

    print("\n━" * 40)
    print("✅ النظام جاهز للمرحلة القادمة")

if __name__ == "__main__":
    main()
