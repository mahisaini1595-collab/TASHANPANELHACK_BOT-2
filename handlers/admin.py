import asyncio
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from config import ADMIN_ID, DATABASE_NAME
from database import Database

router = Router()
db = Database(DATABASE_NAME)

@router.message(Command("stats"), F.from_user.id == ADMIN_ID)
async def cmd_stats(message: types.Message):
    stats = await db.get_stats()
    await message.answer(
        f"📊 Bot Statistics:\n\n"
        f"👥 Total Users: {stats['total_users']}\n"
        f"✅ Active Users: {stats['active_users']}"
    )

@router.message(Command("users"), F.from_user.id == ADMIN_ID)
async def cmd_users(message: types.Message):
    users = await db.get_all_users()
    await message.answer(f"📋 Total Active Users: {len(users)}")

@router.message(F.from_user.id == ADMIN_ID, F.video)
async def get_video_file_id(message: types.Message):
    """Utility to get file_id of a video for use in config"""
    file_id = message.video.file_id
    await message.answer(
        f"✅ <b>Video File ID received!</b>\n\n"
        f"<code>{file_id}</code>\n\n"
        f"Copy this ID and send it to me here in chat."
    )

@router.message(Command("broadcast"), F.from_user.id == ADMIN_ID, F.chat.type == "private")
async def cmd_broadcast_prompt(message: types.Message):
    await message.answer("📢 Please reply to this message with the content (text, photo, video, or file) you want to broadcast.")

@router.message(F.reply_to_message, F.from_user.id == ADMIN_ID, F.chat.type == "private")
async def process_broadcast(message: types.Message, bot: Bot):
    # Only process if the replied message was the broadcast prompt
    if not message.reply_to_message.text or "broadcast" not in message.reply_to_message.text.lower():
        return

    users = await db.get_all_users()
    sent_count = 0
    failed_count = 0
    
    status_msg = await message.answer(f"🚀 Starting broadcast to {len(users)} users...")

    for user_id in users:
        try:
            if message.text:
                await bot.send_message(user_id, message.text)
            elif message.photo:
                await bot.send_photo(user_id, message.photo[-1].file_id, caption=message.caption)
            elif message.video:
                await bot.send_video(user_id, message.video.file_id, caption=message.caption)
            elif message.document:
                await bot.send_document(user_id, message.document.file_id, caption=message.caption)
            
            sent_count += 1
            # Throttling to avoid hitting limits (approx 30 msgs per second)
            if sent_count % 20 == 0:
                await asyncio.sleep(1)
        
        except TelegramForbiddenError:
            # User blocked the bot
            await db.update_user_status(user_id, 0)
            failed_count += 1
        except TelegramRetryAfter as e:
            # Hit rate limits
            await asyncio.sleep(e.retry_after)
            # Retry one more time (simple version)
            try:
                if message.text: await bot.send_message(user_id, message.text)
                sent_count += 1
            except:
                failed_count += 1
        except Exception:
            failed_count += 1
            
        # Update progress every 50 users
        if (sent_count + failed_count) % 50 == 0:
            await status_msg.edit_text(f"🚀 Broadcasting... {sent_count + failed_count}/{len(users)}")

    await status_msg.edit_text(
        f"✅ Broadcast Completed!\n\n"
        f"📊 Success: {sent_count}\n"
        f"❌ Failed/Blocked: {failed_count}"
    )
    
    # Save broadcast to history
    content_type = "text"
    if message.photo: content_type = "photo"
    elif message.video: content_type = "video"
    elif message.document: content_type = "document"
    
    await db.add_broadcast(content_type, message.text or message.caption or "[Media]", sent_count, failed_count)
