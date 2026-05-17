from data_engine import pipeline_init_all, SYMBOLS, TIMEFRAMES, count_candles
import asyncio
import time

def main():
    print("🚀 نظام التداول الكمي — بدء التشغيل")
    print("━" * 40)
    
    asyncio.run(pipeline_init_all())
    
    print("\n📊 ملخص البيانات:")
    for symbol in SYMBOLS:
        for interval in TIMEFRAMES:
            count = count_candles(symbol, interval)
            print(f" {symbol} | {interval}: {count} شمعة")
    
    print("\n✅ البيانات جاهزة")
    
    while True:
        time.sleep(60)
        print("⏳ النظام شغال...")

if __name__ == "__main__":
    main()
