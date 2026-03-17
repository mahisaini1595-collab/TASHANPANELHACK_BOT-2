# Tashan-PanelBot 🚀

Advanced Telegram bot with auto join-request handling, welcome DM + media, live support routing, broadcast, and leave monitoring.

## ✨ Features
- 🎥 Auto-playing welcome video + APK delivery
- 🤖 Auto join-request handler (sends welcome DM)
- 💬 Live chat support (admin identity hidden)
- 🚨 Leave monitoring + rejoin prompt
- 🧭 Inline buttons and rich formatting

## Getting Started
1. **Python 3.8+** and `pip install -r requirements.txt`
2. Configure `.env`:
   ```
   BOT_TOKEN=your_token
   ADMIN_ID=your_admin_id
   DATABASE_NAME=bot_database.db
   SUPPORT_GROUP_ID=your_support_group_id
   CHANNEL_ID=your_channel_id
   WELCOME_VIDEO_FILE_ID=optional_cached_file_id
   ```
3. Run: `python main.py` (or Windows: double-click `run_bot.bat`)

## Railway Deploy
1. Connect repo to Railway.
2. Add env vars in dashboard (`BOT_TOKEN`, `ADMIN_ID`, etc.).
3. Railway uses `Procfile` automatically.

## Configuration
See `config.py` for ID defaults; welcome/leave messages are in `handlers/user.py`.

## License
Educational use only. Use at your own risk.
