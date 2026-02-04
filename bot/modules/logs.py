from pyrogram import Client, filters
from pyrogram.types import Message

from config import Config

@Client.on_message(filters.command("logs"))
async def send_log(c, msg:Message):
    if msg.from_user.id not in Config.ADMINS:
        return
    await msg.reply_document(
        "./bot/bot_logs.log",
        caption="Bot Logs"
    )