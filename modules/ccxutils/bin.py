# Copyright @ISmartCoder
# Channel t.me/TheSmartDev

import asyncio
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from config import BIN_KEY, COMMAND_PREFIX, UPDATE_CHANNEL_URL, BAN_REPLY
from utils import notify_admin, LOGGER
from core import banned_users
import pycountry

async def get_bin_info(bin, client, message):
    headers = {'x-api-key': BIN_KEY}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://data.handyapi.com/bin/{bin}", headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    LOGGER.error(f"API returned status code {response.status}")
                    raise Exception(f"API returned status code {response.status}")
    except Exception as e:
        LOGGER.error(f"Error fetching BIN info: {str(e)}")
        asyncio.create_task(notify_admin(client, "/bin", e, message))
        return None

def get_flag(country_code):
    country = pycountry.countries.get(alpha_2=country_code)
    if not country:
        raise ValueError("Invalid country code")
    country_name = country.name
    flag_emoji = chr(0x1F1E6 + ord(country_code[0]) - ord('A')) + chr(0x1F1E6 + ord(country_code[1]) - ord('A'))
    return country_name, flag_emoji

def setup_bin_handler(app: Client):
    @app.on_message(filters.command(["bin"], prefixes=COMMAND_PREFIX) & (filters.private | filters.group))
    async def bin_handler(client: Client, message: Message):
        user_id = message.from_user.id if message.from_user else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await client.send_message(
                message.chat.id, 
                BAN_REPLY, 
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Join For Updates", url=UPDATE_CHANNEL_URL)]]
                )
            )
            return

        user_input = message.text.split(maxsplit=1)
        if len(user_input) == 1:
            await client.send_message(
                message.chat.id, 
                "**Provide a valid BIN❌**", 
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Join For Updates", url=UPDATE_CHANNEL_URL)]]
                )
            )
            return

        bin = user_input[1]
        progress_message = await client.send_message(
            message.chat.id, 
            "**Fetching Bin Details...**", 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Join For Updates", url=UPDATE_CHANNEL_URL)]]
            )
        )
        bin_info = await get_bin_info(bin[:6], client, message)
        await progress_message.delete()

        if not bin_info or bin_info.get("Status") != "SUCCESS":
            await client.send_message(
                message.chat.id, 
                "**Invalid BIN provided ❌**", 
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Join For Updates", url=UPDATE_CHANNEL_URL)]]
                )
            )
            return

        bank = bin_info.get("Issuer", "Unknown")
        card_type = bin_info.get("Type", "Unknown")
        card_scheme = bin_info.get("Scheme", "Unknown")
        bank_text = bank.upper() if bank else "Unknown"
        country_code = bin_info["Country"]["A2"]
        try:
            country_name, flag_emoji = get_flag(country_code)
        except:
            country_name, flag_emoji = "Unknown", ""

        bin_info_text = (
            f"**🔍 BIN Details From Smart Database 📋**\n"
            f"**━━━━━━━━━━━━━━━━━━**\n"
            f"**• BIN:** {bin}\n"
            f"**• INFO:** {card_scheme.upper()} - {card_type.upper()}\n"
            f"**• BANK:** {bank_text}\n"
            f"**• COUNTRY:** {country_name.upper()} {flag_emoji}\n"
            f"**━━━━━━━━━━━━━━━━━━**\n"
            f"**🔍 Smart Bin Checker → Activated  ✅**"
        )
        await client.send_message(
            message.chat.id, 
            bin_info_text, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Join For Updates", url=UPDATE_CHANNEL_URL)]]
            )
        )
