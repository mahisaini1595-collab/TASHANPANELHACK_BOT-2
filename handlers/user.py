import os
import time
import logging
from glob import glob

from aiogram import Router, F, types, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import FSInputFile, ChatJoinRequest, ChatMemberUpdated
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import DATABASE_NAME, CHANNEL_ID, SUPPORT_GROUP_ID, WELCOME_VIDEO_FILE_ID
from database import Database
from handlers.support import ensure_user_topic

router = Router()
db = Database(DATABASE_NAME)
logger = logging.getLogger(__name__)

# File paths (absolute to avoid cwd issues)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO_CANDIDATE_PATHS = [
    os.path.join(BASE_DIR, "IMG_2717-top.mp4"),
    os.path.join(BASE_DIR, "IMG_2717-top.MP4"),
]
DOWN_VIDEO_CANDIDATE_PATHS = [
    os.path.join(BASE_DIR, "video_down.mp4"),
    os.path.join(BASE_DIR, "video_down.MP4"),
]

# In-memory file ID cache to speed up media sending
FILE_ID_CACHE = {
    "video": WELCOME_VIDEO_FILE_ID,
    "video_down": None,
    "apk": None,
}

# Avoid duplicate welcomes when both join-request and chat_member fire
_recent_welcomes = {}
_WELCOME_DEDUP_SECONDS = 180


def get_existing_path(candidate_paths, fallback_path):
    for path in candidate_paths:
        if os.path.exists(path):
            return path
    return fallback_path


def get_video_path():
    return get_existing_path(VIDEO_CANDIDATE_PATHS, VIDEO_CANDIDATE_PATHS[0])


def get_down_video_path():
    return get_existing_path(
        DOWN_VIDEO_CANDIDATE_PATHS,
        DOWN_VIDEO_CANDIDATE_PATHS[0],
    )


def get_apk_path():
    apk_files = glob(os.path.join(BASE_DIR, "*.apk"))
    if apk_files:
        return max(apk_files, key=os.path.getmtime)
    return os.path.join(BASE_DIR, "RUDRA_ARMY.apk")


def get_welcome_kb():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="TASHAN GAMES OFFICIAL LINK 🚀",
            url="https://www.tswgg.co/#/register?invitationCode=377675460579",
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="⚡ Number Prediction",
            url="https://t.me/+z-VeYV2I6MoxNDhl",
        ),
        types.InlineKeyboardButton(
            text="🆘 Loss recover DM ME",
            url="https://t.me/m/WB4IElulZmY5",
        ),
    )
    builder.row(
        types.InlineKeyboardButton(
            text="💬 FAST MESSAGE KRO 24/7",
            url="https://t.me/m/WB4IElulZmY5",
        )
    )
    return builder.as_markup()


def get_apk_kb():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="📈 LOSS RECOVERY CHANNEL 🧾",
            url="https://t.me/+ROCUgzQGHd8yODhl",
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="💬 FAST MESSAGE KRO 24/7",
            url="https://t.me/m/WB4IElulZmY5",
        )
    )
    return builder.as_markup()


def build_leave_group_warning(user) -> str:
    username_line = f"@{user.username}" if getattr(user, "username", None) else "No username"
    return f"🚨 <b>User Left</b>\n🔗 {username_line}"


def build_leave_user_warning() -> str:
    return (
        "⚠️ Aap channel se nikal gaye.\n"
        "📌 Wapas join kijiye: https://t.me/+z-VeYV2I6MoxNDhl"
    )


async def send_welcome_dm(user_id: int, bot: Bot, full_name: str):
    """Send welcome video + APK sequentially."""
    welcome_caption = (
        "Hᴇʟʟᴏ Dᴇᴀʀ, Mᴀɪ RUDRA BHAI Hᴜ Aᴀᴘᴋᴇ Rᴇǫᴜᴇsᴛ Cʜᴀɴɴᴇʟ "
        "Mᴀɪ Aᴄᴄᴇᴘᴛ Hᴏ Jᴀʏᴀɢɪ ❤️\n\n"
        "Aɴᴅ Aɢᴀʀ Aᴀᴘᴋᴀ Bʜɪ Cᴏʟᴏᴜʀ Tʀᴀᴅɪɴɢ Mᴀɪ 10ᴋ Sᴇ Jᴀᴅᴀ "
        "Lᴏss Hᴜᴀ Tʜᴏ Is Iᴅ Pᴇ Mᴇssᴇɢᴇ Kᴀʀᴏ 😍 Rᴇᴄᴏᴠᴇʀ Kᴀʀᴠᴀ Dᴜɴɢᴀ\n\n"
        "https://t.me/+bN5NtJIt9bs1NDA1\n"
        "https://t.me/+8MC66Wka4-w1NmNl\n\n"
        "USERNAME: @rudraarmy0\n\n"
        "Yᴇ Lᴏ Vɪᴘ Sᴜʙ Mᴇᴍʙᴇʀ Jᴏɪɴ Mᴀʀ Lᴏ Yᴀʜᴀ Nᴜᴍʙᴇʀ "
        "Bᴇᴛ MɪʟLLᴇɢᴀ ✅"
    )

    apk_caption = (
        "📦 CLICK AND INSTALL NOW\n"
        "⚠️ IMPORTANT: Pahle Video Dekho Uske Baad Use Karo!\n"
        "✅ 100% ACCURATE NUMBER SHOTS\n"
        "💎 VIP PANEL ACTIVATED"
    )

    feedback_msg = (
        "𝗣𝗔𝗡𝗘𝗟 𝗙𝗘𝗘𝗗𝗕𝗔𝗖𝗞𝗦 ❤️‍🔥❤️‍🔥..\n\n"
        "❤️‍🔥Members Winning Feedback🚀"
    )

    # Send top video with caption
    video_sent = False
    video_path = get_video_path()

    if FILE_ID_CACHE["video"]:
        try:
            await bot.send_video(
                user_id,
                FILE_ID_CACHE["video"],
                caption=welcome_caption,
                reply_markup=get_welcome_kb(),
                supports_streaming=True,
            )
            video_sent = True
        except Exception as e:
            logger.error(f"Error sending cached video to {user_id}: {e}")
            FILE_ID_CACHE["video"] = None

    if not video_sent and os.path.exists(video_path):
        try:
            sent = await bot.send_video(
                user_id,
                FSInputFile(video_path),
                caption=welcome_caption,
                reply_markup=get_welcome_kb(),
                supports_streaming=True,
            )
            FILE_ID_CACHE["video"] = sent.video.file_id
            video_sent = True
        except Exception as e:
            logger.error(f"Error sending local video to {user_id}: {e}")

    if not video_sent:
        try:
            await bot.send_message(
                user_id,
                welcome_caption,
                reply_markup=get_welcome_kb(),
            )
        except Exception:
            pass

    # Send APK with caption (before down video)
    try:
        apk_path = get_apk_path()
        if FILE_ID_CACHE["apk"]:
            await bot.send_document(
                user_id,
                FILE_ID_CACHE["apk"],
                caption=apk_caption,
                reply_markup=get_apk_kb(),
            )
        elif os.path.exists(apk_path):
            sent_doc = await bot.send_document(
                user_id,
                FSInputFile(apk_path),
                caption=apk_caption,
                reply_markup=get_apk_kb(),
            )
            FILE_ID_CACHE["apk"] = sent_doc.document.file_id
        else:
            logger.error(f"APK file NOT FOUND at: {os.path.abspath(apk_path)}")
    except Exception as e:
        logger.error(f"Error sending APK to {user_id}: {e}")

    # Send down video after APK (no buttons)
    try:
        down_video_path = get_down_video_path()
        down_msg = None
        if FILE_ID_CACHE["video_down"]:
            down_msg = await bot.send_video(
                user_id,
                FILE_ID_CACHE["video_down"],
                supports_streaming=True,
                reply_markup=None,
            )
        elif os.path.exists(down_video_path):
            down_msg = await bot.send_video(
                user_id,
                FSInputFile(down_video_path),
                supports_streaming=True,
                reply_markup=None,
            )
            FILE_ID_CACHE["video_down"] = down_msg.video.file_id
        if down_msg:
            try:
                await bot.edit_message_reply_markup(
                    chat_id=user_id,
                    message_id=down_msg.message_id,
                    reply_markup=None,
                )
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Error sending down video to {user_id}: {e}")

    # Feedback message below the down video (no buttons)
    try:
        await bot.send_message(user_id, feedback_msg, reply_markup=None)
    except Exception as e:
        logger.debug(f"Could not send feedback message to {user_id}: {e}")

    _recent_welcomes[user_id] = time.monotonic()


@router.message(CommandStart())
async def cmd_start(message: types.Message, bot: Bot):
    user = message.from_user
    await db.add_user(user.id, user.username, user.full_name)
    await send_welcome_dm(user.id, bot, user.full_name)


@router.chat_join_request()
async def auto_welcome_join_request(request: ChatJoinRequest, bot: Bot):
    if request.chat.id != CHANNEL_ID:
        return

    user = request.from_user
    await db.add_user(user.id, user.username, user.full_name)

    try:
        await ensure_user_topic(bot, user)
    except Exception as e:
        logger.debug(f"Failed to pre-create topic on join request for user {user.id}: {e}")

    try:
        await send_welcome_dm(user.id, bot, user.full_name)
    except Exception as e:
        logger.error(f"Failed to send welcome DM after join request for user {user.id}: {e}")


@router.chat_member()
async def on_chat_member_update(update: ChatMemberUpdated, bot: Bot):
    """Handle join + leave events for the channel."""
    if update.chat.id != CHANNEL_ID:
        return

    member_statuses = ["member", "administrator", "creator"]
    leaving_statuses = ["left", "kicked"]

    was_member = update.old_chat_member.status in member_statuses
    is_member = update.new_chat_member.status in member_statuses

    if not was_member and is_member:
        user = update.new_chat_member.user
        last_welcome = _recent_welcomes.get(user.id)
        if last_welcome and (time.monotonic() - last_welcome) < _WELCOME_DEDUP_SECONDS:
            return
        try:
            await send_welcome_dm(user.id, bot, user.full_name)
        except Exception as e:
            logger.error(f"Failed to send welcome DM after join for user {user.id}: {e}")
        try:
            await ensure_user_topic(bot, user)
        except Exception as e:
            logger.debug(f"Failed to pre-create topic on chat_member join for user {user.id}: {e}")
        return

    if was_member and update.new_chat_member.status in leaving_statuses:
        user = update.new_chat_member.user
        await db.update_user_status(user.id, 0)
        group_warning = build_leave_group_warning(user)
        user_warning = build_leave_user_warning()

        try:
            await bot.send_message(SUPPORT_GROUP_ID, group_warning)
        except Exception as e:
            logger.error(f"Failed to send leave warning to group for user {user.id}: {e}")

        try:
            await bot.send_message(user.id, user_warning)
            try:
                await send_welcome_dm(user.id, bot, user.full_name)
            except Exception as e:
                logger.error(f"Failed to send rejoin welcome package to user {user.id}: {e}")
        except Exception as e:
            logger.error(f"Failed to send leave warning to user {user.id}: {e}")


@router.message(Command("support"))
async def cmd_support(message: types.Message):
    await message.answer(
        "💬 To contact support, just send your message here in this chat. "
        "Our team will reply to you as soon as possible."
    )


@router.callback_query(F.data == "number_prediction")
async def number_prediction(callback: types.CallbackQuery):
    await callback.answer("Predicting numbers...")


@router.callback_query(F.data == "loss_recover")
async def loss_recover(callback: types.CallbackQuery):
    await callback.answer("Recovering loss...")
