import asyncio
from data_engine import pipeline_init_all
from live_bot import main as live_main

async def main():
    print("🚀 نظام التداول الكمي — بدء التشغيل")
    print("━" * 40)
    
    # تهيئة البيانات أولاً
    await pipeline_init_all()
    
    print("\n✅ البيانات جاهزة — تشغيل live_bot...")
    
    # تشغيل live_bot
    await live_main()

if __name__ == "__main__":
    asyncio.run(main())
