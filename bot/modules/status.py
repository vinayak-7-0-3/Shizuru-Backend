from pyrogram import Client, filters
from pyrogram.types import Message
from .indexing import processor

@Client.on_message(filters.command("queue"))
async def queue_status(client: Client, message: Message):
    size = processor.queue.qsize()
    await message.reply_text(f"Queue size: {size}")
