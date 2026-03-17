import aiohttp
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("BOT_TOKEN")

async def check():
    url = f"https://api.telegram.org/bot{token}/getMe"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            print(f"Status: {response.status}")
            print(f"Text: {await response.text()}")

if __name__ == "__main__":
    asyncio.run(check())
