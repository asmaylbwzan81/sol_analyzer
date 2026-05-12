import time
from datetime import datetime
from data_engine import init_db, fetch_candles, save_candles, count_candles
from features import load_data, extract_features

TARGET = 20000

def main():
    print("🚀 Quant Bot Started")
    print("━" * 40)

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

    print("\n📐 حساب الـ Features...")
    df = load_data()
    df = extract_features(df)

    features = [c for c in df.columns if c not in
                ["timestamp","open","high","low","close","volume"]]

    print(f"✅ Features جاهزة: {len(features)} Feature على {len(df)} صف")
    print(f"\n📋 الـ Features:\n{features}")
    print(f"\n📊 إحصاء:\n{df[features].describe().round(4)}")
    print("\n━" * 40)
    print("✅ النظام جاهز!")

if __name__ == "__main__":
    main()
