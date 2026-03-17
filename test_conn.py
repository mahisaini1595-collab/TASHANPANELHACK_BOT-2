import asyncio
from aiogram import Bot
from config import BOT_TOKEN

async def test_bot():
    print(f"Testing bot with token: {BOT_TOKEN[:10]}...")
    bot = Bot(token=BOT_TOKEN)
    try:
        me = await bot.get_me()
        print(f"Bot authenticated successfully: @{me.username}")
    except Exception as e:
        print(f"Authentication failed: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(test_bot())
