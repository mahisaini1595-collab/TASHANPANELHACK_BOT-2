import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from database import Database
from handlers import support


class SupportReplyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.original_db = support.db
        self.original_schedule_message_deletion = support.schedule_message_deletion
        self.test_db = Database(self.db_path)
        await self.test_db.create_tables()
        support.db = self.test_db

    async def asyncTearDown(self):
        support.db = self.original_db
        support.schedule_message_deletion = self.original_schedule_message_deletion
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def test_support_message_map_round_trip(self):
        await self.test_db.add_support_message_map(555, 111)
        user_id = await self.test_db.get_support_user_id(555)
        self.assertEqual(user_id, 111)

    async def test_user_message_to_group_stores_mapping(self):
        status_message = SimpleNamespace(delete=AsyncMock())
        support.schedule_message_deletion = Mock()
        bot = SimpleNamespace(
            send_message=AsyncMock(return_value=SimpleNamespace(message_id=555))
        )
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=111, full_name="Test User"),
            text="hello support",
            photo=None,
            video=None,
            document=None,
            voice=None,
            answer=AsyncMock(return_value=status_message),
        )

        await support.user_to_group(message, bot)

        bot.send_message.assert_awaited_once_with(
            support.SUPPORT_GROUP_ID,
            '👤 <b>From:</b> <a href="tg://user?id=111">Test User</a>\nhello support',
        )
        message.answer.assert_awaited_once()
        support.schedule_message_deletion.assert_called_once_with(status_message, delay_seconds=3)
        self.assertEqual(await self.test_db.get_support_user_id(555), 111)

    async def test_group_reply_uses_stored_mapping(self):
        await self.test_db.add_support_message_map(555, 111)
        bot = SimpleNamespace(
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status="administrator")),
            send_message=AsyncMock(),
            send_photo=AsyncMock(),
            send_video=AsyncMock(),
            send_document=AsyncMock(),
            send_voice=AsyncMock(),
        )
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=222),
            message_id=666,
            reply_to_message=SimpleNamespace(message_id=555, entities=None, caption_entities=None),
            text="Support reply",
            photo=None,
            video=None,
            document=None,
            voice=None,
            reply=AsyncMock(return_value=SimpleNamespace(message_id=777)),
        )

        await support.group_reply_to_user(message, bot)

        bot.send_message.assert_awaited_once_with(
            111,
            "<b>💬 Support Team Reply:</b>\n\nSupport reply",
        )
        message.reply.assert_awaited_once()

    async def test_group_reply_stores_mapping_for_follow_up_replies(self):
        await self.test_db.add_support_message_map(555, 111)
        status_message = SimpleNamespace(message_id=777)
        bot = SimpleNamespace(
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status="administrator")),
            send_message=AsyncMock(),
            send_photo=AsyncMock(),
            send_video=AsyncMock(),
            send_document=AsyncMock(),
            send_voice=AsyncMock(),
        )
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=222),
            message_id=666,
            reply_to_message=SimpleNamespace(message_id=555, entities=None, caption_entities=None),
            text="Second support reply",
            photo=None,
            video=None,
            document=None,
            voice=None,
            reply=AsyncMock(return_value=status_message),
        )

        await support.group_reply_to_user(message, bot)

        self.assertEqual(await self.test_db.get_support_user_id(666), 111)
        self.assertEqual(await self.test_db.get_support_user_id(777), 111)

    async def test_follow_up_reply_to_previous_support_message_reaches_same_user(self):
        await self.test_db.add_support_message_map(666, 111)
        bot = SimpleNamespace(
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status="administrator")),
            send_message=AsyncMock(),
            send_photo=AsyncMock(),
            send_video=AsyncMock(),
            send_document=AsyncMock(),
            send_voice=AsyncMock(),
        )
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=222),
            message_id=888,
            reply_to_message=SimpleNamespace(message_id=666, entities=None, caption_entities=None, text=None, caption=None, reply_to_message=None),
            text="Follow-up reply",
            photo=None,
            video=None,
            document=None,
            voice=None,
            reply=AsyncMock(return_value=SimpleNamespace(message_id=999)),
        )

        await support.group_reply_to_user(message, bot)

        bot.send_message.assert_awaited_once_with(
            111,
            "<b>💬 Support Team Reply:</b>\n\nFollow-up reply",
        )

    async def test_group_reply_can_fallback_to_user_link_in_message(self):
        bot = SimpleNamespace(
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status="administrator")),
            send_message=AsyncMock(),
            send_photo=AsyncMock(),
            send_video=AsyncMock(),
            send_document=AsyncMock(),
            send_voice=AsyncMock(),
        )
        original_msg = SimpleNamespace(
            message_id=555,
            entities=[SimpleNamespace(type="text_link", url="tg://user?id=111")],
            caption_entities=None,
            text='👤 <b>From:</b> <a href="tg://user?id=111">Test User</a>',
            caption=None,
            reply_to_message=None,
        )
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=222),
            message_id=666,
            reply_to_message=original_msg,
            text="Reply via fallback",
            photo=None,
            video=None,
            document=None,
            voice=None,
            reply=AsyncMock(return_value=SimpleNamespace(message_id=777)),
        )

        await support.group_reply_to_user(message, bot)

        bot.send_message.assert_awaited_once_with(
            111,
            "<b>💬 Support Team Reply:</b>\n\nReply via fallback",
        )

    async def test_group_reply_can_fallback_to_plain_support_user_id_marker(self):
        bot = SimpleNamespace(
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status="administrator")),
            send_message=AsyncMock(),
            send_photo=AsyncMock(),
            send_video=AsyncMock(),
            send_document=AsyncMock(),
            send_voice=AsyncMock(),
        )
        original_msg = SimpleNamespace(
            message_id=555,
            entities=None,
            caption_entities=None,
            text="👤 From: Test User\n🔖 SUPPORT_USER_ID:111",
            caption=None,
            reply_to_message=None,
            external_reply=None,
            quote=None,
        )
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=222),
            message_id=666,
            reply_to_message=original_msg,
            external_reply=None,
            text="Reply via marker",
            photo=None,
            video=None,
            document=None,
            voice=None,
            reply=AsyncMock(return_value=SimpleNamespace(message_id=777)),
        )

        await support.group_reply_to_user(message, bot)

        bot.send_message.assert_awaited_once_with(
            111,
            "<b>💬 Support Team Reply:</b>\n\nReply via marker",
        )

    async def test_group_reply_can_resolve_from_external_reply_payload(self):
        bot = SimpleNamespace(
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status="administrator")),
            send_message=AsyncMock(),
            send_photo=AsyncMock(),
            send_video=AsyncMock(),
            send_document=AsyncMock(),
            send_voice=AsyncMock(),
        )
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=222),
            message_id=666,
            reply_to_message=SimpleNamespace(
                message_id=555,
                entities=None,
                caption_entities=None,
                text=None,
                caption=None,
                reply_to_message=None,
                external_reply=None,
                quote=None,
            ),
            external_reply=SimpleNamespace(
                message_id=None,
                entities=None,
                caption_entities=None,
                text="SUPPORT_USER_ID=111",
                caption=None,
                reply_to_message=None,
                external_reply=None,
                quote=None,
            ),
            text="Reply via external reply",
            photo=None,
            video=None,
            document=None,
            voice=None,
            reply=AsyncMock(return_value=SimpleNamespace(message_id=777)),
        )

        await support.group_reply_to_user(message, bot)

        bot.send_message.assert_awaited_once_with(
            111,
            "<b>💬 Support Team Reply:</b>\n\nReply via external reply",
        )

    async def test_group_reply_blocks_non_admin_member(self):
        await self.test_db.add_support_message_map(555, 111)
        bot = SimpleNamespace(
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status="member")),
            send_message=AsyncMock(),
            send_photo=AsyncMock(),
            send_video=AsyncMock(),
            send_document=AsyncMock(),
            send_voice=AsyncMock(),
        )
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=333),
            message_id=666,
            reply_to_message=SimpleNamespace(message_id=555, entities=None, caption_entities=None),
            text="Blocked reply",
            photo=None,
            video=None,
            document=None,
            voice=None,
            reply=AsyncMock(),
        )

        await support.group_reply_to_user(message, bot)

        bot.send_message.assert_not_awaited()
        message.reply.assert_awaited_once_with("❌ <b>Only support group owner/admin can reply to users.</b>")


if __name__ == "__main__":
    unittest.main()