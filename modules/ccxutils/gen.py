import re
import os
import random
import aiohttp
import asyncio
import pycountry
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from config import BIN_KEY, COMMAND_PREFIX, CC_GEN_LIMIT, MULTI_CCGEN_LIMIT, BAN_REPLY
from core import banned_users
from utils import notify_admin, LOGGER

def is_amex_bin(bin_str):
    clean_bin = bin_str.replace('x', '').replace('X', '')
    if len(clean_bin) >= 2:
        return clean_bin[:2] in ['34', '37']
    return False

def extract_bin_from_text(text):
    if not text:
        return None
    text = text.strip()
    for prefix in COMMAND_PREFIX:
        if text.lower().startswith(f'{prefix}gen'):
            text = text[len(f'{prefix}gen'):].strip()
            break
    digits_x_pattern = r'(?:[0-9xX][a-zA-Z0-9!@#$%^&*()_+\-=\[\]{};:\'",.<>/?\\|]*)+(?:[|:/][\d]{2}|xx|xxx|xxxx]+(?:[|:/][\d]{2,4}|xx|xxx|xxxx]+(?:[|:/][\d]{3,4}|xxx|xxxx]+)?)?)?'
    matches = re.findall(digits_x_pattern, text, re.IGNORECASE)
    if matches:
        for match in matches:
            parts = re.split(r'[|:/]', match)
            bin_part = ''.join(filter(lambda x: x.isdigit() or x in 'xX', parts[0]))
            digits_only = re.sub(r'[^0-9]', '', bin_part)
            if 6 <= len(digits_only) <= 16:
                if len(parts) > 1:
                    full_match = bin_part + '|' + '|'.join(parts[1:])
                    LOGGER.info(f"Extracted BIN with format: {full_match}")
                    return full_match
                LOGGER.info(f"Extracted BIN: {digits_only}")
                return digits_only
    return None

async def get_bin_info(bin, client, message):
    headers = {'x-api-key': BIN_KEY}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://data.handyapi.com/bin/{bin}", headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_msg = f"API returned status code {response.status}"
                    LOGGER.error(error_msg)
                    await client.send_message(message.chat.id, f"**Invalid Bin Provided ❌**")
                    return None
    except Exception as e:
        error_msg = f"Error fetching BIN info: {str(e)}"
        LOGGER.error(error_msg)
        await client.send_message(message.chat.id, f"**Invalid Bin Provided ❌**")
        await notify_admin(client, "/gen", e, message)
        return None

def luhn_algorithm(card_number):
    digits = [int(d) for d in str(card_number) if d.isdigit()]
    if not digits or len(digits) < 13:
        return False
    checksum = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:
            doubled = digit * 2
            if doubled > 9:
                doubled = doubled // 10 + doubled % 10
            checksum += doubled
        else:
            checksum += digit
    return checksum % 10 == 0

def calculate_luhn_check_digit(partial_card_number):
    digits = [int(d) for d in str(partial_card_number) if d.isdigit()]
    if not digits:
        return 0
    checksum = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 0:
            doubled = digit * 2
            if doubled > 9:
                doubled = doubled // 10 + doubled % 10
            checksum += doubled
        else:
            checksum += digit
    check_digit = (10 - (checksum % 10)) % 10
    return check_digit

def generate_credit_card(bin, amount, month=None, year=None, cvv=None):
    cards = []
    is_amex = is_amex_bin(bin)
    target_length = 15 if is_amex else 16
    cvv_length = 4 if is_amex else 3
    bin_digits = re.sub(r'[^0-9]', '', bin)
    if len(bin_digits) >= target_length:
        LOGGER.error(f"BIN too long: {len(bin_digits)} digits for target length {target_length}")
        return []
    for _ in range(amount):
        card_body = bin_digits
        remaining_digits = target_length - len(card_body) - 1
        if remaining_digits < 0:
            LOGGER.error(f"Invalid BIN length for card type")
            continue
        for _ in range(remaining_digits):
            card_body += str(random.randint(0, 9))
        check_digit = calculate_luhn_check_digit(card_body)
        card_number = card_body + str(check_digit)
        if not luhn_algorithm(card_number):
            LOGGER.error(f"Generated invalid card: {card_number}")
            continue
        card_month = month if month is not None else f"{random.randint(1, 12):02d}"
        card_year = year if year is not None else str(random.randint(2025, 2035))
        card_cvv = cvv if cvv is not None else ''.join([str(random.randint(0, 9)) for _ in range(cvv_length)])
        formatted_card = f"{card_number}|{card_month}|{card_year}|{card_cvv}"
        cards.append(formatted_card)
        LOGGER.debug(f"Generated valid card: {formatted_card}")
    return cards

def parse_input(user_input):
    bin = None
    month = None
    year = None
    cvv = None
    amount = 10
    if not user_input:
        return None, None, None, None, None
    input_parts = user_input.strip().split()
    if len(input_parts) > 1 and input_parts[-1].isdigit():
        potential_amount = int(input_parts[-1])
        if 1 <= potential_amount <= 9999:
            amount = potential_amount
            user_input = ' '.join(input_parts[:-1])
    extracted_bin = extract_bin_from_text(user_input)
    if not extracted_bin:
        return None, None, None, None, None
    parts = re.split(r'[|:/]', extracted_bin)
    bin_part = parts[0] if parts else ""
    digits_only = re.sub(r'[^0-9]', '', bin_part)
    if digits_only:
        if 6 <= len(digits_only) <= 16:
            bin = digits_only
        else:
            return None, None, None, None, None
    else:
        return None, None, None, None, None
    if len(parts) > 1:
        if parts[1].lower() == 'xx':
            month = None
        elif parts[1].isdigit() and len(parts[1]) == 2:
            month_val = int(parts[1])
            if 1 <= month_val <= 12:
                month = f"{month_val:02d}"
    if len(parts) > 2:
        if parts[2].lower() == 'xx':
            year = None
        elif parts[2].isdigit():
            year_str = parts[2]
            if len(year_str) == 2:
                year_int = int(year_str)
                if year_int >= 25:
                    year = f"20{year_str}"
                else:
                    year = f"20{year_str}"
            elif len(year_str) == 4:
                year_int = int(year_str)
                if 2025 <= year_int <= 2099:
                    year = year_str
    if len(parts) > 3 and parts[3]:
        if parts[3].lower() in ['xxx', 'xxxx']:
            cvv = None
        elif parts[3].isdigit():
            cvv = parts[3]
    return bin, month, year, cvv, amount

def generate_custom_cards(bin, amount, month=None, year=None, cvv=None):
    return generate_credit_card(bin, amount, month, year, cvv)

def get_flag(country_code, client=None, message=None):
    try:
        country = pycountry.countries.get(alpha_2=country_code)
        if not country:
            raise ValueError("Invalid country code")
        country_name = country.name
        flag_emoji = chr(0x1F1E6 + ord(country_code[0]) - ord('A')) + chr(0x1F1E6 + ord(country_code[1]) - ord('A'))
        return country_name, flag_emoji
    except Exception as e:
        error_msg = f"Error in get_flag: {str(e)}"
        LOGGER.error(error_msg)
        if client and message:
            asyncio.create_task(notify_admin(client, "/gen", e, message))
        return "Unknown", "🚨"

def get_country_code_from_name(country_name, client=None, message=None):
    try:
        country = pycountry.countries.lookup(country_name)
        return country.alpha_2
    except Exception as e:
        error_msg = f"Error in get_country_code_from_name: {str(e)}"
        LOGGER.error(error_msg)
        if client and message:
            asyncio.create_task(notify_admin(client, "/gen", e, message))
        return None

def contains_bin_pattern(_, __, message):
    if not message.text and not message.caption:
        return False
    text = message.text or message.caption
    extracted_bin = extract_bin_from_text(text)
    return extracted_bin is not None

bin_pattern_filter = filters.create(contains_bin_pattern)

def setup_gen_handler(app: Client):
    @app.on_message(filters.command(["gen"], prefixes=COMMAND_PREFIX) & (filters.private | filters.group))
    async def generate_handler(client: Client, message: Message):
        user_id = None
        user_full_name = "Anonymous"
        if message.from_user:
            user_id = message.from_user.id
            user_full_name = message.from_user.first_name or "Anonymous"
            if message.from_user.last_name:
                user_full_name += f" {message.from_user.last_name}"
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await client.send_message(message.chat.id, BAN_REPLY)
            return
        if message.reply_to_message and message.reply_to_message.text:
            user_input = message.reply_to_message.text
            extracted_bin = extract_bin_from_text(user_input)
            if extracted_bin:
                user_input = extracted_bin
                LOGGER.info(f"Using extracted BIN from reply text: {extracted_bin}")
            else:
                user_input = message.reply_to_message.text
        elif message.reply_to_message and message.reply_to_message.caption:
            user_input = message.reply_to_message.caption
            extracted_bin = extract_bin_from_text(user_input)
            if extracted_bin:
                user_input = extracted_bin
                LOGGER.info(f"Using extracted BIN from reply caption: {extracted_bin}")
            else:
                user_input = message.reply_to_message.caption
        else:
            command_text = message.text
            for prefix in COMMAND_PREFIX:
                if command_text.lower().startswith(f'{prefix}gen'):
                    user_input = command_text[len(f'{prefix}gen'):].strip()
                    if not user_input:
                        await client.send_message(message.chat.id, "**Please Provide A Valid Bin ❌**")
                        return
                    break
            else:
                await client.send_message(message.chat.id, "**Please Provide A Valid Bin ❌**")
                return
        bin, month, year, cvv, amount = parse_input(user_input)
        if not bin:
            LOGGER.error(f"Invalid BIN extracted from: {user_input}")
            await client.send_message(message.chat.id, "**Sorry Bin Must Be 6-15 Digits❌**")
            return
        if cvv is not None:
            is_amex = is_amex_bin(bin)
            if is_amex and len(cvv) != 4:
                await client.send_message(message.chat.id, "**Invalid CVV format. CVV must be 4 digits for AMEX ❌**")
                return
        if amount > CC_GEN_LIMIT:
            await client.send_message(message.chat.id, f"**You Can Only Generate Upto {CC_GEN_LIMIT} Credit Cards ❌**")
            return
        clean_bin_for_api = bin[:6]
        bin_info = await get_bin_info(clean_bin_for_api, client, message)
        if not bin_info or bin_info.get("Status") != "SUCCESS" or not isinstance(bin_info.get("Country"), dict):
            return
        bank = bin_info.get("Issuer")
        country_name = bin_info["Country"].get("Name", "Unknown")
        card_type = bin_info.get("Type", "Unknown")
        card_scheme = bin_info.get("Scheme", "Unknown")
        bank_text = bank.upper() if bank else "Unknown"
        country_code = bin_info["Country"]["A2"]
        country_name, flag_emoji = get_flag(country_code, client, message)
        bin_info_text = f"{card_scheme.upper()} - {card_type.upper()}"
        progress_message = await client.send_message(message.chat.id, "**Generating Credit Cards...**")
        LOGGER.info("Generating Credit Cards...")
        cards = generate_credit_card(bin, amount, month, year, cvv)
        if not cards:
            await progress_message.edit_text("**Sorry Bin Must Be 6-15 Digits❌**")
            return
        if amount <= 10:
            card_text = "\n".join([f"`{card}`" for card in cards])
            await progress_message.delete()
            response_text = f"𝗕𝗜𝗡 ⇾ {bin}\n𝗔𝗺𝗼𝘂𝗻𝘁 ⇾ {amount}\n\n{card_text}\n\n𝗕𝗮𝗻𝗸: {bank_text}\n𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country_name} {flag_emoji}\n𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info_text}"
            callback_data = f"regenerate|{bin.replace(' ', '_')}|{month if month else 'xx'}|{year if year else 'xx'}|{cvv if cvv else ('xxxx' if is_amex_bin(bin) else 'xxx')}|{amount}|{user_id if user_id else '0'}"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Re-Generate", callback_data=callback_data)]])
            await client.send_message(message.chat.id, response_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        else:
            file_name = f"{bin} x {amount}.txt"
            try:
                with open(file_name, "w") as file:
                    file.write("\n".join(cards))
                await progress_message.delete()
                caption = f"**🔍 Multiple CC Generate Successful 📋**\n**━━━━━━━━━━━━━━━━**\n𝗕𝗜𝗡: {bin}\n𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info_text}\n𝗕𝗮𝗻𝗸: {bank_text}\n𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country_name} {flag_emoji}\n**━━━━━━━━━━━━━━━━**\n**👁 Thanks For Using Our Tool ✅**"
                await client.send_document(message.chat.id, document=file_name, caption=caption, parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                await client.send_message(message.chat.id, "**Sorry Bro API Response Unavailable**")
                LOGGER.error(f"Error saving cards to file: {str(e)}")
                await notify_admin(client, "/gen", e, message)
            finally:
                if os.path.exists(file_name):
                    os.remove(file_name)

    @app.on_message(filters.reply & bin_pattern_filter & (filters.private | filters.group))
    async def auto_generate_handler(client: Client, message: Message):
        if not message.reply_to_message:
            return
        reply_text = None
        if message.reply_to_message.text:
            reply_text = message.reply_to_message.text
        elif message.reply_to_message.caption:
            reply_text = message.reply_to_message.caption
        if not reply_text:
            return
        gen_command_found = False
        for prefix in COMMAND_PREFIX:
            if f'{prefix}gen' in reply_text.lower():
                gen_command_found = True
                break
        if not gen_command_found:
            return
        user_id = None
        user_full_name = "Anonymous"
        if message.from_user:
            user_id = message.from_user.id
            user_full_name = message.from_user.first_name or "Anonymous"
            if message.from_user.last_name:
                user_full_name += f" {message.from_user.last_name}"
        if user_id and await banned_users.find_one({"user_id": user_id}):
            return
        current_text = message.text or message.caption
        if not current_text:
            return
        extracted_bin = extract_bin_from_text(current_text)
        if not extracted_bin:
            return
        user_input = extracted_bin
        LOGGER.info(f"Auto-extracted BIN from reply: {extracted_bin}")
        bin, month, year, cvv, amount = parse_input(user_input)
        if not bin:
            return
        if cvv is not None:
            is_amex = is_amex_bin(bin)
            if is_amex and len(cvv) != 4:
                return
        if amount > CC_GEN_LIMIT:
            return
        clean_bin_for_api = bin[:6]
        bin_info = await get_bin_info(clean_bin_for_api, client, message)
        if not bin_info or bin_info.get("Status") != "SUCCESS" or not isinstance(bin_info.get("Country"), dict):
            return
        bank = bin_info.get("Issuer")
        country_name = bin_info["Country"].get("Name", "Unknown")
        card_type = bin_info.get("Type", "Unknown")
        card_scheme = bin_info.get("Scheme", "Unknown")
        bank_text = bank.upper() if bank else "Unknown"
        country_code = bin_info["Country"]["A2"]
        country_name, flag_emoji = get_flag(country_code, client, message)
        bin_info_text = f"{card_scheme.upper()} - {card_type.upper()}"
        progress_message = await client.send_message(message.chat.id, "**Generating Credit Cards...**")
        LOGGER.info("Auto-generating Credit Cards...")
        cards = generate_credit_card(bin, amount, month, year, cvv)
        if not cards:
            await progress_message.edit_text("**Sorry Bin Must Be 6-15 Digits❌**")
            return
        if amount <= 10:
            card_text = "\n".join([f"`{card}`" for card in cards])
            await progress_message.delete()
            response_text = f"𝗕𝗜𝗡 ⇾ {bin}\nA𝗺𝗼𝘂𝗻𝘁 ⇾ {amount}\n\n{card_text}\n\n𝗕𝗮𝗻𝗸: {bank_text}\n𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country_name} {flag_emoji}\n𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info_text}"
            callback_data = f"regenerate|{bin.replace(' ', '_')}|{month if month else 'xx'}|{year if year else 'xx'}|{cvv if cvv else ('xxxx' if is_amex_bin(bin) else 'xxx')}|{amount}|{user_id if user_id else '0'}"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Re-Generate", callback_data=callback_data)]])
            await client.send_message(message.chat.id, response_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        else:
            file_name = f"{bin} x {amount}.txt"
            try:
                with open(file_name, "w") as file:
                    file.write("\n".join(cards))
                await progress_message.delete()
                caption = f"**🔍 Multiple CC Generate Successful 📋**\n**━━━━━━━━━━━━━━━━**\n𝗕𝗜𝗡: {bin}\n𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info_text}\n𝗕𝗮𝗻𝗸: {bank_text}\n𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country_name} {flag_emoji}\n**━━━━━━━━━━━━━━━━**\n**👁 Thanks For Using Our Tool ✅**"
                await client.send_document(message.chat.id, document=file_name, caption=caption, parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                await client.send_message(message.chat.id, "**Sorry Bro API Response Unavailable**")
                LOGGER.error(f"Error saving cards to file: {str(e)}")
                await notify_admin(client, "/gen", e, message)
            finally:
                if os.path.exists(file_name):
                    os.remove(file_name)

    @app.on_callback_query(filters.regex(r"regenerate\|(.+)\|(.+)\|(.+)\|(.+)\|(\d+)\|(\d+)"))
    async def regenerate_callback(client: Client, callback_query):
        user_id = None
        user_full_name = "Anonymous"
        if callback_query.from_user:
            user_id = callback_query.from_user.id
            user_full_name = callback_query.from_user.first_name or "Anonymous"
            if callback_query.from_user.last_name:
                user_full_name += f" {callback_query.from_user.last_name}"
        data_parts = callback_query.data.split('|')
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await client.send_message(callback_query.message.chat.id, BAN_REPLY)
            return
        bin = data_parts[1].replace('_', ' ')
        month = data_parts[2] if data_parts[2] != 'xx' else None
        year = data_parts[3] if data_parts[3] != 'xx' else None
        cvv = data_parts[4] if data_parts[4] not in ['xxx', 'xxxx'] else None
        amount = int(data_parts[5])
        if not bin:
            await callback_query.answer("Sorry Bin Must Be 6-15 Digits ❌", show_alert=True)
            return
        if cvv is not None:
            is_amex = is_amex_bin(bin)
            if is_amex and len(cvv) != 4:
                await callback_query.answer("Invalid CVV format. CVV must be 4 digits for AMEX ❌", show_alert=True)
                return
        if amount > CC_GEN_LIMIT:
            await callback_query.answer(f"You can only generate up to {CC_GEN_LIMIT} credit cards ❌", show_alert=True)
            return
        clean_bin_for_api = bin[:6]
        bin_info = await get_bin_info(clean_bin_for_api, client, callback_query.message)
        if not bin_info or bin_info.get("Status") != "SUCCESS" or not isinstance(bin_info.get("Country"), dict):
            return
        bank = bin_info.get("Issuer")
        country_name = bin_info["Country"].get("Name", "Unknown")
        card_type = bin_info.get("Type", "Unknown")
        card_scheme = bin_info.get("Scheme", "Unknown")
        bank_text = bank.upper() if bank else "Unknown"
        country_code = bin_info["Country"]["A2"]
        country_name, flag_emoji = get_flag(country_code, client, callback_query.message)
        bin_info_text = f"{card_scheme.upper()} - {card_type.upper()}"
        cards = generate_credit_card(bin, amount, month, year, cvv)
        if not cards:
            await callback_query.answer("Sorry Bin Must Be 6-15 Digits❌", show_alert=True)
            return
        card_text = "\n".join([f"`{card}`" for card in cards])
        response_text = f"𝗕𝗜𝗡 ⇾ {bin}\n𝗔𝗺𝗼𝘂𝗻𝘁 ⇾ {amount}\n\n{card_text}\n\n𝗕𝗮𝗻𝗸: {bank_text}\n𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country_name} {flag_emoji}\n𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info_text}"
        callback_data = f"regenerate|{bin.replace(' ', '_')}|{month if month else 'xx'}|{year if year else 'xx'}|{cvv if cvv else ('xxxx' if is_amex_bin(bin) else 'xxx')}|{amount}|{user_id if user_id else '0'}"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Re-Generate", callback_data=callback_data)]])
        await callback_query.message.edit_text(response_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
