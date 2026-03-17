import asyncio
import re

from aiogram import Router, F, types, Bot
from aiogram.types import ReactionTypeEmoji
from aiogram.types import Message
from config import DATABASE_NAME, SUPPORT_GROUP_ID
from database import Database
import logging

logger = logging.getLogger(__name__)
router = Router()
db = Database(DATABASE_NAME)

SUPPORT_USER_ID_MARKER = "SUPPORT_USER_ID"
USER_ID_PATTERN = re.compile(
    rf"tg://user\?id=(\d+)|\b(?:User ID|Support User ID|{SUPPORT_USER_ID_MARKER}|UID)\s*[:=#-]?\s*(\d+)",
    re.IGNORECASE,
)
ALLOWED_SUPPORT_REPLY_STATUSES = {"administrator", "creator"}

async def ensure_user_topic(bot: Bot, user: types.User):
    # Return existing topic id if present
    existing = await db.get_user_topic(user.id)
    if existing:
        return existing

    title = f"{(user.full_name or 'User')[:60]} | {user.id}"
    try:
        topic = await bot.create_forum_topic(chat_id=SUPPORT_GROUP_ID, name=title)
        thread_id = getattr(topic, "message_thread_id", None)
        if thread_id:
            await db.set_user_topic(user.id, thread_id)
            return thread_id
    except Exception as e:
        logger.error(f"Failed to create forum topic for user {user.id}: {e}")
    return None


def build_support_header(user: types.User) -> str:
    mention = f'<a href="tg://user?id={user.id}">{user.full_name}</a>'
    return f"👤 <b>From:</b> {mention}"


async def delete_message_after_delay(message: Message, delay_seconds: int = 3):
    await asyncio.sleep(delay_seconds)
    try:
        await message.delete()
    except Exception as e:
        logger.debug(f"Could not auto-delete transient message: {e}")


def schedule_message_deletion(message: Message, delay_seconds: int = 3):
    asyncio.create_task(delete_message_after_delay(message, delay_seconds))


def extract_user_id_from_message(message: Message):
    if not message:
        return None

    quote = getattr(message, "quote", None)
    entity_groups = [
        getattr(message, "entities", None) or [],
        getattr(message, "caption_entities", None) or [],
        getattr(quote, "entities", None) or [],
    ]

    for entities in entity_groups:
        for entity in entities:
            if entity.type == "text_link" and entity.url and entity.url.startswith("tg://user?id="):
                try:
                    return int(entity.url.split("=")[1])
                except (ValueError, IndexError):
                    continue

    text_to_scan = "\n".join(
        filter(
            None,
            [
                getattr(message, "text", None),
                getattr(message, "caption", None),
                getattr(quote, "text", None),
            ],
        )
    )
    match = USER_ID_PATTERN.search(text_to_scan)
    if not match:
        return None

    for group in match.groups():
        if group:
            return int(group)

    return None


def iter_support_resolution_messages(message: Message):
    queue = []
    seen = set()

    for attr_name in ("reply_to_message", "external_reply"):
        nested = getattr(message, attr_name, None)
        if nested is not None:
            queue.append(nested)

    while queue:
        current = queue.pop(0)
        unique_key = (type(current).__name__, getattr(current, "message_id", None), id(current))
        if unique_key in seen:
            continue
        seen.add(unique_key)
        yield current

        for attr_name in ("reply_to_message", "external_reply"):
            nested = getattr(current, attr_name, None)
            if nested is not None:
                queue.append(nested)


async def resolve_support_user_id(message: Message):
    for current in iter_support_resolution_messages(message):
        current_message_id = getattr(current, "message_id", None)
        if current_message_id is not None:
            user_id = await db.get_support_user_id(current_message_id)
            if user_id:
                return user_id

        fallback_user_id = extract_user_id_from_message(current)
        if fallback_user_id:
            return fallback_user_id

    return None

@router.message(F.chat.type == "private", ~F.text.startswith("/"))
async def user_to_group(message: Message, bot: Bot):
    """Forward user message to the support group"""
    user = message.from_user

    header = build_support_header(user)
    thread_id = await ensure_user_topic(bot, user)
    send_kwargs = {"message_thread_id": thread_id} if thread_id else {}
    
    try:
        sent_message = None

        if message.text:
            sent_message = await bot.send_message(
                SUPPORT_GROUP_ID, f"{header}\n{message.text}", **send_kwargs
            )
        elif message.photo:
            sent_message = await bot.send_photo(
                SUPPORT_GROUP_ID,
                message.photo[-1].file_id,
                caption=f"{header}\n{message.caption or ''}",
                **send_kwargs
            )
        elif message.video:
            sent_message = await bot.send_video(
                SUPPORT_GROUP_ID,
                message.video.file_id,
                caption=f"{header}\n{message.caption or ''}",
                **send_kwargs
            )
        elif message.document:
            sent_message = await bot.send_document(
                SUPPORT_GROUP_ID,
                message.document.file_id,
                caption=f"{header}\n{message.caption or ''}",
                **send_kwargs
            )
        elif message.voice:
            sent_message = await bot.send_voice(
                SUPPORT_GROUP_ID,
                message.voice.file_id,
                caption=f"{header}\n{message.caption or ''}",
                **send_kwargs
            )
        else:
            await message.answer("❌ <b>This message type is not supported for support forwarding.</b>")
            return

        await db.add_support_message_map(sent_message.message_id, user.id)

        # React to user's original message (visual acknowledgement)
        try:
            await bot.set_message_reaction(
                chat_id=message.chat.id,
                message_id=message.message_id,
                reaction=[ReactionTypeEmoji(emoji="❤️")],
                is_big=False,
            )
        except Exception as e:
            logger.debug(f"Reaction failed: {e}")

        status_message = await message.answer("📤 Message sent to admin. We'll reply soon.", parse_mode=None)
        schedule_message_deletion(status_message, delay_seconds=3)
    except Exception as e:
        logger.error(f"Error forwarding to group: {e}")
        await message.answer("❌ <b>Sorry, there was an error sending your message. Please try again later.</b>")

@router.message(F.chat.id == SUPPORT_GROUP_ID)
async def group_reply_to_user(message: Message, bot: Bot):
    """Admin/Support replies in the support group"""
    
    if not message.reply_to_message:
        # In forums, message_thread_id is enough
        if not getattr(message, "message_thread_id", None):
            return

    target_user_id = None

    # Ignore service/system messages that have no deliverable payload
    has_payload = any(
        [
            message.text,
            getattr(message, "photo", None),
            getattr(message, "video", None),
            getattr(message, "document", None),
            getattr(message, "voice", None),
            getattr(message, "audio", None),
            getattr(message, "animation", None),
            getattr(message, "sticker", None),
        ]
    )
    if not has_payload:
        return

    # 0) If topic is mapped to a user (forum mode)
    thread_id = getattr(message, "message_thread_id", None)
    if thread_id:
        target_user_id = await db.get_user_by_topic(thread_id)

    # 1) If this is a reply to a forwarded user message
    if not target_user_id and message.reply_to_message and message.reply_to_message.forward_from:
        target_user_id = message.reply_to_message.forward_from.id

    # 2) Try resolving from stored map or embedded ID markers
    if not target_user_id and message.reply_to_message:
        target_user_id = await resolve_support_user_id(message)

    # 3) Last-resort: parse an explicit "User ID" marker from the replied message
    if not target_user_id and message.reply_to_message:
        match = re.search(r"User ID: (\d+)", (message.reply_to_message.text or ""))
        if match:
            target_user_id = int(match.group(1))

    # If still unresolved, silently ignore to avoid noisy errors in the group
    if not target_user_id:
        return

    if target_user_id:
        try:
            # Send the reply to the user
            reply_header = "👨‍💻 <b>Support Reply:</b>\n\n"
            sent_to_user = False

            if message.text:
                await bot.send_message(target_user_id, f"{reply_header}{message.text}")
                sent_to_user = True
            elif message.photo:
                await bot.send_photo(target_user_id, message.photo[-1].file_id, caption=f"{reply_header}{message.caption or ''}")
                sent_to_user = True
            elif message.video:
                await bot.send_video(target_user_id, message.video.file_id, caption=f"{reply_header}{message.caption or ''}")
                sent_to_user = True
            elif message.document:
                await bot.send_document(target_user_id, message.document.file_id, caption=f"{reply_header}{message.caption or ''}")
                sent_to_user = True
            elif message.voice:
                await bot.send_voice(target_user_id, message.voice.file_id, caption=f"{reply_header}{message.caption or ''}")
                sent_to_user = True
            elif message.audio:
                await bot.send_audio(target_user_id, message.audio.file_id, caption=f"{reply_header}{message.caption or ''}")
                sent_to_user = True
            elif message.animation:
                await bot.send_animation(target_user_id, message.animation.file_id, caption=f"{reply_header}{message.caption or ''}")
                sent_to_user = True
            elif message.sticker:
                await bot.send_sticker(target_user_id, message.sticker.file_id)
                sent_to_user = True
            else:
                # Unsupported types: silently ignore to avoid noisy errors in topics
                return

            if sent_to_user:
                if getattr(message, "message_id", None) is not None:
                    await db.add_support_message_map(message.message_id, target_user_id)
                status_message = await message.reply("✅ <b>Reply sent to user</b>")
                schedule_message_deletion(status_message, delay_seconds=3)
                
        except Exception as e:
            logger.error(f"Error sending reply to user {target_user_id}: {e}")
            await message.reply(f"❌ <b>Failed to send reply:</b> {e}")
    else:
        return
