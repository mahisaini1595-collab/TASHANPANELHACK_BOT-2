import aiosqlite
import os
from datetime import datetime

class Database:
    def __init__(self, db_name):
        self.db_name = db_name

    async def create_tables(self):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    is_active INTEGER DEFAULT 1,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS broadcasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_type TEXT,
                    content TEXT,
                    sent_to INTEGER,
                    failed_to INTEGER,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS support_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    message TEXT,
                    role TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS support_message_map (
                    group_message_id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_topics (
                    user_id INTEGER PRIMARY KEY,
                    thread_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    async def add_user(self, user_id, username, full_name):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
                (user_id, username, full_name)
            )
            await db.commit()

    async def update_user_status(self, user_id, is_active):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (is_active, user_id))
            await db.commit()

    async def get_all_users(self):
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute("SELECT user_id FROM users WHERE is_active = 1") as cursor:
                return [row[0] for row in await cursor.fetchall()]

    async def get_stats(self):
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                total_users = (await cursor.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM users WHERE is_active = 1") as cursor:
                active_users = (await cursor.fetchone())[0]
            return {"total_users": total_users, "active_users": active_users}

    async def add_broadcast(self, message_type, content, sent_to, failed_to):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "INSERT INTO broadcasts (message_type, content, sent_to, failed_to) VALUES (?, ?, ?, ?)",
                (message_type, content, sent_to, failed_to)
            )
            await db.commit()

    async def add_support_log(self, user_id, message, role):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "INSERT INTO support_logs (user_id, message, role) VALUES (?, ?, ?)",
                (user_id, message, role)
            )
            await db.commit()

    async def add_support_message_map(self, group_message_id, user_id):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "INSERT OR REPLACE INTO support_message_map (group_message_id, user_id) VALUES (?, ?)",
                (group_message_id, user_id)
            )
            await db.commit()

    async def get_support_user_id(self, group_message_id):
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute(
                "SELECT user_id FROM support_message_map WHERE group_message_id = ?",
                (group_message_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def set_user_topic(self, user_id, thread_id):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "INSERT OR REPLACE INTO user_topics (user_id, thread_id) VALUES (?, ?)",
                (user_id, thread_id)
            )
            await db.commit()

    async def get_user_topic(self, user_id):
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute(
                "SELECT thread_id FROM user_topics WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def get_user_by_topic(self, thread_id):
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute(
                "SELECT user_id FROM user_topics WHERE thread_id = ?",
                (thread_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
