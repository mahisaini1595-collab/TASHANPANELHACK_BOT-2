print("Importing asyncio...")
import asyncio
print("Importing logging...")
import logging
print("Importing sys...")
import sys
print("Importing os...")
import os
print("Importing aiogram...")
from aiogram import Bot, Dispatcher
print("Importing config...")
from config import BOT_TOKEN, DATABASE_NAME
print("Importing database...")
from database import Database
print("Importing handlers...")
from handlers import user, admin, support
print("All imports done.")
