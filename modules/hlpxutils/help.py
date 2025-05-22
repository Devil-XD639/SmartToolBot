#Copyright @ISmartDevs
#Channel t.me/TheSmartDev
from pyrogram import Client, filters
from pyrogram.enums import ParseMode, ChatType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from config import UPDATE_CHANNEL_URL, COMMAND_PREFIX

def setup_help_handler(app: Client):
    @app.on_message(filters.command(["help", "tutorial"], prefixes=COMMAND_PREFIX) & (filters.private | filters.group))
    async def help_message(client: Client, message: Message):
        if message.chat.type == ChatType.PRIVATE:
            # Extract full name in private chat
            full_name = "User"
            if message.from_user:
                first_name = message.from_user.first_name or ""
                last_name = message.from_user.last_name or ""
                full_name = f"{first_name} {last_name}".strip()

            # Private Chat Message
            response_text = (
                f"<b>Hi {full_name}! Welcome To This Bot</b>\n"
                "<b>━━━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                "<b>Smart Tool 💥</b>: The ultimate toolkit on Telegram, offering education, AI, downloaders, temp mail, credit card tool, and more. Simplify your tasks with ease!\n"
                "<b>━━━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                "<b>Don't Forget To <a href='{UPDATE_CHANNEL_URL}'>Join Here</a> For Updates!</b>".format(UPDATE_CHANNEL_URL=UPDATE_CHANNEL_URL)
            )
        elif message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            # Default to group name if user is anonymous admin
            group_name = message.chat.title if message.chat.title else "this group"

            # Check if user data is available (not anonymous admin)
            if message.from_user:
                first_name = message.from_user.first_name or ""
                last_name = message.from_user.last_name or ""
                full_name = f"{first_name} {last_name}".strip()

                # Personalized response for non-anonymous users
                response_text = (
                    f"<b>Hi {full_name}! Welcome To This Bot</b>\n"
                    "<b>━━━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                    "<b>Smart Tool 💥</b>: The ultimate toolkit on Telegram, offering education, AI, downloaders, temp mail, credit card tool, and more. Simplify your tasks with ease!\n"
                    "<b>━━━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                    "<b>Don't Forget To <a href='{UPDATE_CHANNEL_URL}'>Join Here</a> For Updates!</b>".format(UPDATE_CHANNEL_URL=UPDATE_CHANNEL_URL)
                )
            else:
                # If user is an anonymous admin, use group name only
                response_text = (
                    f"<b>Hi! Welcome  {group_name} To This Bot</b>\n"
                    "<b>━━━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                    "<b>Smart Tool 💥</b>: The ultimate toolkit on Telegram, offering education, AI, downloaders, temp mail, credit card tool, and more. Simplify your tasks with ease!\n"
                    "<b>━━━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                    "<b>Don't Forget To <a href='{UPDATE_CHANNEL_URL}'>Join Here</a> For Updates!</b>".format(UPDATE_CHANNEL_URL=UPDATE_CHANNEL_URL)
                )

        # Send message with inline buttons
        await client.send_message(
            chat_id=message.chat.id,
            text=response_text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ Main Menu", callback_data="main_menu")],
                [InlineKeyboardButton("ℹ️ About Me", callback_data="about_me"),
                 InlineKeyboardButton("📄 Policy & Terms", callback_data="policy_terms")]
            ]),
            disable_web_page_preview=True,
        )
