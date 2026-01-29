import asyncio
from typing import Tuple, List, Union
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, MessageNotModified

from .indexing import processor

def get_link_info(link: str) -> Tuple[Union[str, int], int]:
    if "?" in link:
        link = link.split("?")[0]
    
    if "t.me/c/" in link:
        # Private chat link: https://t.me/c/1234567890/100
        parts = link.split("/")
        chat_id = int("-100" + parts.pop(-2))
        msg_id = int(parts.pop())
        return chat_id, msg_id
    elif "t.me/" in link:
        # Public chat link: https://t.me/username/100
        parts = link.split("/")
        chat_id = parts.pop(-2)
        msg_id = int(parts.pop())
        return chat_id, msg_id
    else:
        raise ValueError("Invalid link format")

@Client.on_message(filters.command("index"))
async def manual_indexing(client: Client, message: Message):
    try:
        args = message.command
        if len(args) < 3:
            await message.reply_text("Usage: /index <start_link> <end_link>")
            return

        start_link = args[1]
        end_link = args[2]

        start_chat, start_msg_id = get_link_info(start_link)
        end_chat, end_msg_id = get_link_info(end_link)

        if start_chat != end_chat:
            await message.reply_text("Links must be from the same chat.")
            return

        if start_msg_id > end_msg_id:
            start_msg_id, end_msg_id = end_msg_id, start_msg_id

        total_messages = end_msg_id - start_msg_id + 1
        status_msg = await message.reply_text(f"Indexing {total_messages} messages...")
        
        chunk_size = 100
        msg_ids_to_fetch = list(range(start_msg_id, end_msg_id + 1))
        
        indexed_count = 0

        for i in range(0, len(msg_ids_to_fetch), chunk_size):
            chunk = msg_ids_to_fetch[i : i + chunk_size]
            
            retry = True
            while retry:
                try:
                    messages: List[Message] = await client.get_messages(start_chat, chunk)
                    retry = False # Success
                    
                    for msg in messages:
                        if not msg or msg.empty:
                            continue
                        
                        await processor.add_item((client, msg))
                        indexed_count += 1
                        
                except FloodWait as e:
                    await asyncio.sleep(e.value + 1)
                except Exception as e:
                    print(f"Error fetching chunk {chunk}: {e}")
                    retry = False # Skip this chunk on other errors
            if i % 500 == 0:
                 try:
                    await status_msg.edit_text(f"Processed: {i + len(chunk)} / {total_messages}")
                 except MessageNotModified:
                     pass

        await status_msg.edit_text(f"Indexing completed. Queued {indexed_count} messages.")

    except ValueError:
        await message.reply_text("Invalid link provided.")
    except Exception as e:
        await message.reply_text(f"An error occurred: {str(e)}")
