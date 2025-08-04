# Copyright @ISmartCoder
# Updates Channel t.me/TheSmartDev
import re
import os
import asyncio
import aiofiles
from pyrogram import Client, filters
from pyrogram.errors import (
    UserAlreadyParticipant,
    InviteHashExpired,
    InviteHashInvalid,
    PeerIdInvalid,
    InviteRequestSent
)
from urllib.parse import urlparse
from user import user
from config import (
    SUDO_CCSCR_LIMIT,
    OWNER_ID,
    CC_SCRAPPER_LIMIT,
    COMMAND_PREFIX,
    MULTI_CCSCR_LIMIT,
    BAN_REPLY
)
from utils import LOGGER
from core import banned_users

async def scrape_messages(client, channel_username, limit, start_number=None, bank_name=None):
    messages = []
    count = 0
    pattern = r'\d{16}\D*\d{2}\D*\d{2,4}\D*\d{3,4}'
    bin_pattern = re.compile(r'^\d{6}') if start_number else None
    LOGGER.info(f"Starting to scrape messages from {channel_username} with limit {limit}")
    async for message in user.search_messages(channel_username):
        if count >= limit:
            break
        text = message.text or message.caption
        if text:
            if bank_name and bank_name.lower() not in text.lower():
                continue
            matched_messages = re.findall(pattern, text)
            if matched_messages:
                formatted_messages = []
                for matched_message in matched_messages:
                    extracted_values = re.findall(r'\d+', matched_message)
                    if len(extracted_values) == 4:
                        card_number, mo, year, cvv = extracted_values
                        year = year[-2:]
                        if start_number:
                            if card_number.startswith(start_number[:6]):
                                formatted_messages.append(f"{card_number}|{mo}|{year}|{cvv}")
                        else:
                            formatted_messages.append(f"{card_number}|{mo}|{year}|{cvv}")
                messages.extend(formatted_messages)
                count += len(formatted_messages)
    LOGGER.info(f"Scraped {len(messages)} messages from {channel_username}")
    return messages[:limit]

def remove_duplicates(messages):
    unique_messages = list(set(messages))
    duplicates_removed = len(messages) - len(unique_messages)
    LOGGER.info(f"Removed {duplicates_removed} duplicates")
    return unique_messages, duplicates_removed

async def send_results(client, message, unique_messages, duplicates_removed, source_name, bin_filter=None, bank_filter=None):
    if unique_messages:
        file_name = f"x{len(unique_messages)}_{source_name.replace(' ', '_')}.txt"
        async with aiofiles.open(file_name, mode='w') as f:
            await f.write("\n".join(unique_messages))
       
        async with aiofiles.open(file_name, mode='rb') as f:
            user_link = await get_user_link(message)
            caption = (
                f"<b>CC Scrapped Successful ✅</b>\n"
                f"<b>━━━━━━━━━━━━━━━━</b>\n"
                f"<b>Source:</b> <code>{source_name} 🌐</code>\n"
                f"<b>Amount:</b> <code>{len(unique_messages)} 📝</code>\n"
                f"<b>Duplicates Removed:</b> <code>{duplicates_removed} 🗑️</code>\n"
            )
            if bin_filter:
                caption += f"<b>📝 BIN Filter:</b> <code>{bin_filter}</code>\n"
            if bank_filter:
                caption += f"<b>📝 Bank Filter:</b> <code>{bank_filter}</code>\n"
            caption += (
                f"<b>━━━━━━━━━━━━━━━━</b>\n"
                f"<b>✅ Card-Scrapped By: {user_link}</b>\n"
            )
            await message.delete()
            await client.send_document(message.chat.id, file_name, caption=caption)
        os.remove(file_name)
        LOGGER.info(f"Results sent successfully for {source_name}")
    else:
        await message.edit_text("<b>Sorry Bro ❌ No Credit Card Found</b>")
        LOGGER.info("No credit cards found")

async def get_user_link(message):
    if message.from_user is None:
        return '<a href="https://t.me/ItsSmartToolBot">Smart Tool</a>'
    else:
        user_first_name = message.from_user.first_name
        user_last_name = message.from_user.last_name or ""
        user_full_name = f"{user_first_name} {user_last_name}".strip()
        return f'<a href="tg://user?id={message.from_user.id}">{user_full_name}</a>'

async def join_private_chat(client, invite_link):
    try:
        await client.join_chat(invite_link)
        LOGGER.info(f"Joined chat via invite link: {invite_link}")
        return True
    except UserAlreadyParticipant:
        LOGGER.info(f"Already a participant in the chat: {invite_link}")
        return True
    except InviteRequestSent:
        LOGGER.info(f"Join request sent to the chat: {invite_link}")
        return False
    except (InviteHashExpired, InviteHashInvalid) as e:
        LOGGER.error(f"Failed to join chat {invite_link}: {e}")
        return False

async def send_join_request(client, invite_link, message):
    try:
        await client.join_chat(invite_link)
        LOGGER.info(f"Sent join request to chat: {invite_link}")
        return True
    except PeerIdInvalid as e:
        LOGGER.error(f"Failed to send join request to chat {invite_link}: {e}")
        return False
    except InviteRequestSent:
        LOGGER.info(f"Join request sent to the chat: {invite_link}")
        await message.edit_text("<b>Hey Bro I Have Sent Join Request✅</b>")
        return False

def setup_scr_handler(app):
    @app.on_message(filters.command(["scr", "ccscr", "scrcc"], prefixes=COMMAND_PREFIX) & (filters.group | filters.private))
    async def scr_cmd(client, message):
        user_id = message.from_user.id if message.from_user else None
        if user_id and await banned_users.banned_users.find_one({"user_id": user_id}):
            await client.send_message(message.chat.id, BAN_REPLY, parse_mode=ParseMode.MARKDOWN)
            return
        args = message.text.split()[1:]
        user_id = message.from_user.id if message.from_user else None
        if len(args) < 2:
            await client.send_message(message.chat.id, "<b>⚠️ Provide channel username and amount to scrape ❌</b>")
            LOGGER.warning("Invalid command: Missing arguments")
            return
        channel_identifier = args[0]
        chat = None
        channel_name = ""
        channel_username = ""
        if channel_identifier.lstrip("-").isdigit():
            chat_id = int(channel_identifier)
            try:
                chat = await user.get_chat(chat_id)
                channel_name = chat.title
                LOGGER.info(f"Scraping from private channel: {channel_name} (ID: {chat_id})")
            except Exception as e:
                await client.send_message(message.chat.id, "<b>Hey Bro! 🥲 Invalid chat ID ❌</b>")
                LOGGER.error(f"Failed to fetch private channel: {e}")
                return
        else:
            if channel_identifier.startswith("https://t.me/+"):
                invite_link = channel_identifier
                temporary_msg = await client.send_message(message.chat.id, "<b>Checking Username...✨</b>")
                joined = await join_private_chat(user, invite_link)
                if not joined:
                    request_sent = await send_join_request(user, invite_link, temporary_msg)
                    if not request_sent:
                        return
                else:
                    await temporary_msg.delete()
                    chat = await user.get_chat(invite_link)
                    channel_name = chat.title
                    LOGGER.info(f"Joined private channel via link: {channel_name}")
            elif channel_identifier.startswith("https://t.me/"):
                channel_username = channel_identifier[13:]
            elif channel_identifier.startswith("t.me/"):
                channel_username = channel_identifier[5:]
            else:
                channel_username = channel_identifier
            if not chat:
                try:
                    chat = await user.get_chat(channel_username)
                    channel_name = chat.title
                    LOGGER.info(f"Scraping from public channel: {channel_name} (Username: {channel_username})")
                except Exception as e:
                    await client.send_message(message.chat.id, "<b>Hey Bro! 🥲 Incorrect username or chat ID ❌</b>")
                    LOGGER.error(f"Failed to fetch public channel: {e}")
                    return
        try:
            limit = int(args[1])
            LOGGER.info(f"Scraping limit set to: {limit}")
        except ValueError:
            await client.send_message(message.chat.id, "<b>⚠️ Invalid limit value. Please provide a valid number ❌</b>")
            LOGGER.warning("Invalid limit value provided")
            return
        start_number = None
        bank_name = None
        bin_filter = None
        if len(args) > 2:
            if args[2].isdigit():
                start_number = args[2]
                bin_filter = args[2][:6]
                LOGGER.info(f"BIN filter applied: {bin_filter}")
            else:
                bank_name = " ".join(args[2:])
                LOGGER.info(f"Bank filter applied: {bank_name}")
        max_lim = SUDO_CCSCR_LIMIT if user_id in (OWNER_ID if isinstance(OWNER_ID, (list, tuple)) else [OWNER_ID]) else CC_SCRAPPER_LIMIT
        if limit > max_lim:
            await client.send_message(message.chat.id, f"<b>Sorry Bro! Amount over Max limit is {max_lim} ❌</b>")
            LOGGER.warning(f"Limit exceeded: {limit} > {max_lim}")
            return
        temporary_msg = await client.send_message(message.chat.id, "<b>Checking The Username...✨</b>")
        await asyncio.sleep(1.5)
        await temporary_msg.edit_text("<b>Scraping In Progress✨</b>")
        scrapped_results = await scrape_messages(user, chat.id, limit, start_number=start_number, bank_name=bank_name)
        unique_messages, duplicates_removed = remove_duplicates(scrapped_results)
        if not unique_messages:
            await temporary_msg.edit_text("<b>Sorry Bro ❌ No Credit Card Found</b>")
        else:
            await send_results(client, temporary_msg, unique_messages, duplicates_removed, channel_name, bin_filter=bin_filter, bank_filter=bank_name)

    @app.on_message(filters.command(["mc", "multiscr", "mscr"], prefixes=COMMAND_PREFIX) & (filters.group | filters.private))
    async def mc_cmd(client, message):
        user_id = message.from_user.id if message.from_user else None
        if user_id and await banned_users.banned_users.find_one({"user_id": user_id}):
            await client.send_message(message.chat.id, BAN_REPLY, parse_mode=ParseMode.MARKDOWN)
            return
        args = message.text.split()[1:]
        if len(args) < 2:
            await client.send_message(message.chat.id, "<b>⚠️ Provide at least one channel username</b>")
            LOGGER.warning("Invalid command: Missing arguments")
            return
        channel_identifiers = args[:-1]
        try:
            limit = int(args[-1])
        except ValueError:
            await client.send_message(message.chat.id, "<b>⚠️ Invalid limit value. Please provide a valid number ❌</b>")
            LOGGER.warning("Invalid limit value provided")
            return
        user_id = message.from_user.id if message.from_user else None
        max_lim = SUDO_CCSCR_LIMIT if user_id in (OWNER_ID if isinstance(OWNER_ID, (list, tuple)) else [OWNER_ID]) else MULTI_CCSCR_LIMIT
        if limit > max_lim:
            await client.send_message(message.chat.id, f"<b>Sorry Bro! Amount over Max limit is {max_lim} ❌</b>")
            LOGGER.warning(f"Limit exceeded: {limit} > {max_lim}")
            return
        temporary_msg = await client.send_message(message.chat.id, "<b>Scraping In Progress✨</b>")
        all_messages = []
        tasks = []
        for channel_identifier in channel_identifiers:
            parsed_url = urlparse(channel_identifier)
            channel_username = parsed_url.path.lstrip('/') if parsed_url.scheme else channel_identifier
            tasks.append(scrape_messages_task(user, channel_username, limit, client, message))
        results = await asyncio.gather(*tasks)
        for result in results:
            all_messages.extend(result)
        unique_messages, duplicates_removed = remove_duplicates(all_messages)
        unique_messages = unique_messages[:limit]
        if not unique_messages:
            await temporary_msg.edit_text("<b>Sorry Bro ❌ No Credit Card Found</b>")
        else:
            await send_results(client, temporary_msg, unique_messages, duplicates_removed, "Multiple Chats")

async def scrape_messages_task(client, channel_username, limit, bot_client, message):
    try:
        chat = None
        if channel_username.startswith("https://t.me/+"):
            invite_link = channel_username
            temporary_msg = await bot_client.send_message(message.chat.id, "<b>Checking Username...</b>")
            joined = await join_private_chat(client, invite_link)
            if not joined:
                request_sent = await send_join_request(client, invite_link, temporary_msg)
                if not request_sent:
                    return []
            else:
                await temporary_msg.delete()
                chat = await client.get_chat(invite_link)
        else:
            chat = await client.get_chat(channel_username)
        return await scrape_messages(client, chat.id, limit)
    except Exception as e:
        await bot_client.send_message(message.chat.id, f"<b>Hey Bro! 🥲 Incorrect username for {channel_username} ❌</b>")
        LOGGER.error(f"Failed to scrape from {channel_username}: {e}")
        return []
