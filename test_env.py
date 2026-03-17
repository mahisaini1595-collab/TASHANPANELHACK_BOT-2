import os
from dotenv import load_dotenv

load_dotenv()

bot_token = os.getenv("BOT_TOKEN")
admin_id = os.getenv("ADMIN_ID")

print(f"BOT_TOKEN: {bot_token[:10] if bot_token else 'None'}")
print(f"ADMIN_ID: {admin_id}")
