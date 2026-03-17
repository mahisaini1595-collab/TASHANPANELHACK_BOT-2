import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

from database import Database
from handlers import user


class UserChannelEventTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.original_db = user.db
        self.original_send_welcome_dm = user.send_welcome_dm
        self.test_db = Database(self.db_path)
        await self.test_db.create_tables()
        user.db = self.test_db

    async def asyncTearDown(self):
        user.db = self.original_db
        user.send_welcome_dm = self.original_send_welcome_dm
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def test_join_request_approves_and_sends_same_welcome(self):
        user.send_welcome_dm = AsyncMock()
        bot = SimpleNamespace(approve_chat_join_request=AsyncMock())
        request = SimpleNamespace(
            chat=SimpleNamespace(id=user.CHANNEL_ID),
            from_user=SimpleNamespace(id=111, username="tester", full_name="Test User"),
        )

        await user.auto_welcome_join_request(request, bot)

        bot.approve_chat_join_request.assert_awaited_once_with(chat_id=user.CHANNEL_ID, user_id=111)
        user.send_welcome_dm.assert_awaited_once_with(111, bot, "Test User")

    async def test_join_request_other_chat_is_ignored(self):
        user.send_welcome_dm = AsyncMock()
        bot = SimpleNamespace(approve_chat_join_request=AsyncMock())
        request = SimpleNamespace(
            chat=SimpleNamespace(id=999999),
            from_user=SimpleNamespace(id=111, username="tester", full_name="Test User"),
        )

        await user.auto_welcome_join_request(request, bot)

        bot.approve_chat_join_request.assert_not_awaited()
        user.send_welcome_dm.assert_not_awaited()

    async def test_leave_sends_group_alert_and_user_warning(self):
        bot = SimpleNamespace(send_message=AsyncMock())
        leaving_user = SimpleNamespace(id=111, username="tester", full_name="Test User")
        update = SimpleNamespace(
            chat=SimpleNamespace(id=user.CHANNEL_ID),
            old_chat_member=SimpleNamespace(status="member"),
            new_chat_member=SimpleNamespace(status="left", user=leaving_user),
        )

        await user.on_chat_member_update(update, bot)

        self.assertEqual(bot.send_message.await_count, 2)
        first_call = bot.send_message.await_args_list[0]
        second_call = bot.send_message.await_args_list[1]
        self.assertEqual(first_call.args[0], user.SUPPORT_GROUP_ID)
        self.assertIn("USER LEFT CHANNEL", first_call.args[1])
        self.assertEqual(second_call.args[0], 111)
        self.assertIn("Important Notice", second_call.args[1])


if __name__ == "__main__":
    unittest.main()