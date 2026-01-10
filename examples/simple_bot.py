from telegram import Bot
import dotenv
import os
import asyncio

dotenv.load_dotenv()

me = os.getenv("TELYDL_WHITELIST").split(",")[0]


async def send_notification():
    bot = Bot(os.getenv("TELYDL_BOT_TOKEN"))
    await bot.send_message(chat_id=me, text="🚨 Notification from bot!")


asyncio.run(send_notification())
