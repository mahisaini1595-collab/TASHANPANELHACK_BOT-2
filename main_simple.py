import asyncio
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN, DATABASE_NAME
from database import Database
from handlers import user, admin, support

async def main():
    print("S1")
    db = Database(DATABASE_NAME)
    await db.create_tables()
    print("S2")
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    print("S3")
    
    dp.include_router(user.router)
    dp.include_router(admin.router)
    dp.include_router(support.router)
    print("S4")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    print("S0")
    asyncio.run(main())
