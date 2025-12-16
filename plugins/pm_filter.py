import asyncio
import re
import math
import os
import qrcode
import random
from datetime import datetime, timedelta
from hydrogram.errors import ListenerTimeout
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
from hydrogram import Client, filters, enums
from Script import script
from info import (
    IS_PREMIUM, PICS, ADMINS, MAX_BTN, DELETE_TIME, LOG_CHANNEL, 
    SUPPORT_GROUP, SUPPORT_LINK, UPDATES_LINK, 
    RECEIPT_SEND_USERNAME, UPI_ID, UPI_NAME, PRE_DAY_AMOUNT, 
    LANGUAGES, QUALITY, SHORTLINK_URL, SHORTLINK_API, TUTORIAL
)
from utils import (
    is_premium, get_size, is_subscribed, is_check_admin, 
    get_wish, get_shortlink, get_readable_time, temp, 
    get_settings, save_group_settings
)
from database.users_chats_db import db
from database.ia_filterdb import get_search_results, delete_files, db_count_documents
from plugins.commands import get_grp_stg

BUTTONS = {}
CAP = {}

@Client.on_message(filters.private & filters.text & filters.incoming)
async def pm_search(client, message):
    if message.text.startswith("/"):
        return
    stg = db.get_bot_sttgs()
    if stg and not stg.get('PM_SEARCH'):
        return await message.reply_text('PM search was disabled!')
    if await is_premium(message.from_user.id, client):
        if stg and not stg.get('AUTO_FILTER'):
            return await message.reply_text('Auto filter was disabled!')
        s = await message.reply(f"<b><i>⚠️ `{message.text}` searching...</i></b>", quote=True)
        await auto_filter(client, message, s)
    else:
        files, n_offset, total = await get_search_results(message.text)
        btn = [[InlineKeyboardButton('🤑 Buy Premium', url=f"https://t.me/{temp.U_NAME}?start=premium")]]
        if int(total) != 0:
            await message.reply_text(f'<b><i>🤗 ᴛᴏᴛᴀʟ <code>{total}</code> ʀᴇꜱᴜʟᴛꜱ ꜰᴏᴜɴᴅ 👇</i></b>\n\nBuy Premium to access files.', reply_markup=InlineKeyboardMarkup(btn))

@Client.on_message(filters.group & filters.text & filters.incoming)
async def group_search(client, message):
    user_id = message.from_user.id if message.from_user else 0
    stg = db.get_bot_sttgs()
    if stg and stg.get('AUTO_FILTER'):
        if not user_id: return
        if message.text.startswith("/"): return
        elif '@admin' in message.text.lower() or '@admins' in message.text.lower():
            if await is_check_admin(client, message.chat.id, message.from_user.id): return
            admins = []
            async for member in client.get_chat_members(chat_id=message.chat.id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
                if not member.user.is_bot: admins.append(member.user.id)
            hidden_mentions = (f'[\u2064](tg://user?id={user_id})' for user_id in admins)
            await message.reply_text('Report sent!' + ''.join(hidden_mentions))
            return
        elif re.findall(r'https?://\S+|www\.\S+|t\.me/\S+|@\w+', message.text):
            if await is_check_admin(client, message.chat.id, message.from_user.id): return
            await message.delete()
            return await message.reply('Links not allowed here!')
        elif '#request' in message.text.lower():
            if message.from_user.id in ADMINS: return
            await client.send_message(LOG_CHANNEL, f"#Request\n★ User: {message.from_user.mention}\n★ Group: {message.chat.title}\n\n★ Message: {message.text}")
            await message.reply_text("Request sent!")
            return  
        else:
            s = await message.reply(f"<b><i>⚠️ `{message.text}` searching...</i></b>")
            await auto_filter(client, message, s)

@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    ident, req, key, offset = query.data.split("_")
    if int(req) not in [query.from_user.id, 0]:
        return await query.answer("Don't Click Other Results!", show_alert=True)
    try: offset = int(offset)
    except: offset = 0
    search = BUTTONS.get(key)
    cap = CAP.get(key)
    if not search:
        await query.answer("Send New Request Again!", show_alert=True)
        return

    files, n_offset, total = await get_search_results(search, offset=offset)
    try: n_offset = int(n_offset)
    except: n_offset = 0

    if not files: return
    settings = await get_settings(query.message.chat.id)
    del_msg = f"\n\n<b>⚠️ Auto delete after <code>{get_readable_time(DELETE_TIME)}</code></b>" if settings["auto_delete"] else ''
    
    files_link = ''
    for file_num, file in enumerate(files, start=offset+1):
        files_link += f"""<b>\n\n{file_num}. <a href=https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file['_id']}>[{get_size(file['file_size'])}] {file['file_name']}</a></b>"""

    btn = []
    # Filters Restored
    btn.insert(0, [
        InlineKeyboardButton("📰 ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}#{req}#{offset}"),
        InlineKeyboardButton("🔍 ǫᴜᴀʟɪᴛʏ", callback_data=f"quality#{key}#{req}#{offset}")
    ])
    
    if 0 < offset <= MAX_BTN: off_set = 0
    elif offset == 0: off_set = None
    else: off_set = offset - MAX_BTN
        
    if n_offset == 0:
        btn.append([InlineKeyboardButton("« ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{off_set}"), InlineKeyboardButton(f"{math.ceil(int(offset) / MAX_BTN) + 1}/{math.ceil(total / MAX_BTN)}", callback_data="buttons")])
    elif off_set is None:
        btn.append([InlineKeyboardButton(f"{math.ceil(int(offset) / MAX_BTN) + 1}/{math.ceil(total / MAX_BTN)}", callback_data="buttons"), InlineKeyboardButton("ɴᴇxᴛ »", callback_data=f"next_{req}_{key}_{n_offset}")])
    else:
        btn.append([InlineKeyboardButton("« ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{off_set}"), InlineKeyboardButton(f"{math.ceil(int(offset) / MAX_BTN) + 1}/{math.ceil(total / MAX_BTN)}", callback_data="buttons"), InlineKeyboardButton("ɴᴇxᴛ »", callback_data=f"next_{req}_{key}_{n_offset}")])

    btn.append([InlineKeyboardButton('🤑 Buy Premium', url=f"https://t.me/{temp.U_NAME}?start=premium")])
    await query.message.edit_text(cap + files_link + del_msg, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML)

@Client.on_callback_query(filters.regex(r"^languages"))
async def languages_(client: Client, query: CallbackQuery):
    _, key, req, offset = query.data.split("#")
    if int(req) != query.from_user.id: return await query.answer("Don't Click Other Results!", show_alert=True)
    btn = [[InlineKeyboardButton(text=LANGUAGES[i].title(), callback_data=f"lang_search#{LANGUAGES[i]}#{key}#{offset}#{req}"), InlineKeyboardButton(text=LANGUAGES[i+1].title(), callback_data=f"lang_search#{LANGUAGES[i+1]}#{key}#{offset}#{req}")] for i in range(0, len(LANGUAGES)-1, 2)]
    btn.append([InlineKeyboardButton(text="⪻ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{offset}")])  
    await query.message.edit_text("<b>Select Language 👇</b>", reply_markup=InlineKeyboardMarkup(btn))

@Client.on_callback_query(filters.regex(r"^quality"))
async def quality(client: Client, query: CallbackQuery):
    _, key, req, offset = query.data.split("#")
    if int(req) != query.from_user.id: return await query.answer("Don't Click Other Results!", show_alert=True)
    btn = [[InlineKeyboardButton(text=QUALITY[i].title(), callback_data=f"qual_search#{QUALITY[i]}#{key}#{offset}#{req}"), InlineKeyboardButton(text=QUALITY[i+1].title(), callback_data=f"qual_search#{QUALITY[i+1]}#{key}#{offset}#{req}")] for i in range(0, len(QUALITY)-1, 2)]
    btn.append([InlineKeyboardButton(text="⪻ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{offset}")])  
    await query.message.edit_text("<b>Select Quality 👇</b>", reply_markup=InlineKeyboardMarkup(btn))

@Client.on_callback_query(filters.regex(r"^lang_search"))
async def filter_languages_cb_handler(client: Client, query: CallbackQuery):
    _, lang, key, offset, req = query.data.split("#")
    if int(req) != query.from_user.id: return await query.answer("Don't Click Other Results!", show_alert=True)
    search = BUTTONS.get(key)
    cap = CAP.get(key)
    if not search: return await query.answer("Send New Request Again!", show_alert=True)
    files, l_offset, total_results = await get_search_results(search, lang=lang)
    if not files: return await query.answer(f"No files found for '{lang.title()}'", show_alert=1)
    
    settings = await get_settings(query.message.chat.id)
    del_msg = f"\n\n<b>⚠️ Auto delete after <code>{get_readable_time(DELETE_TIME)}</code></b>" if settings["auto_delete"] else ''
    
    files_link = ''
    for file_num, file in enumerate(files, start=1):
        files_link += f"""<b>\n\n{file_num}. <a href=https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file['_id']}>[{get_size(file['file_size'])}] {file['file_name']}</a></b>"""
    
    btn = []
    # No Result Buttons, Only Pagination and Back
    if l_offset != "":
        btn.append([InlineKeyboardButton(text=f"1/{math.ceil(int(total_results) / MAX_BTN)}", callback_data="buttons"), InlineKeyboardButton(text="ɴᴇxᴛ »", callback_data=f"lang_next#{req}#{key}#{lang}#{l_offset}#{offset}")])
    btn.append([InlineKeyboardButton(text="⪻ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{offset}")])
    await query.message.edit_text(cap + files_link + del_msg, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)

@Client.on_callback_query(filters.regex(r"^lang_next"))
async def lang_next_page(bot, query):
    ident, req, key, lang, l_offset, offset = query.data.split("#")
    if int(req) != query.from_user.id: return await query.answer("Don't Click Other Results!", show_alert=True)
    try: l_offset = int(l_offset)
    except: l_offset = 0
    search = BUTTONS.get(key)
    cap = CAP.get(key)
    files, n_offset, total = await get_search_results(search, offset=l_offset, lang=lang)
    try: n_offset = int(n_offset)
    except: n_offset = 0
    
    settings = await get_settings(query.message.chat.id)
    del_msg = f"\n\n<b>⚠️ Auto delete after <code>{get_readable_time(DELETE_TIME)}</code></b>" if settings["auto_delete"] else ''
    
    files_link = ''
    for file_num, file in enumerate(files, start=l_offset+1):
        files_link += f"""<b>\n\n{file_num}. <a href=https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file['_id']}>[{get_size(file['file_size'])}] {file['file_name']}</a></b>"""

    btn = []
    if 0 < l_offset <= MAX_BTN: b_offset = 0
    elif l_offset == 0: b_offset = None
    else: b_offset = l_offset - MAX_BTN
    
    if n_offset == 0:
        btn.append([InlineKeyboardButton("« ʙᴀᴄᴋ", callback_data=f"lang_next#{req}#{key}#{lang}#{b_offset}#{offset}"), InlineKeyboardButton(f"{math.ceil(int(l_offset) / MAX_BTN) + 1}/{math.ceil(total / MAX_BTN)}", callback_data="buttons")])
    elif b_offset is None:
        btn.append([InlineKeyboardButton(f"{math.ceil(int(l_offset) / MAX_BTN) + 1}/{math.ceil(total / MAX_BTN)}", callback_data="buttons"), InlineKeyboardButton("ɴᴇxᴛ »", callback_data=f"lang_next#{req}#{key}#{lang}#{n_offset}#{offset}")])
    else:
        btn.append([InlineKeyboardButton("« ʙᴀᴄᴋ", callback_data=f"lang_next#{req}#{key}#{lang}#{b_offset}#{offset}"), InlineKeyboardButton(f"{math.ceil(int(l_offset) / MAX_BTN) + 1}/{math.ceil(total / MAX_BTN)}", callback_data="buttons"), InlineKeyboardButton("ɴᴇxᴛ »", callback_data=f"lang_next#{req}#{key}#{lang}#{n_offset}#{offset}")])
    btn.append([InlineKeyboardButton(text="⪻ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{offset}")])
    await query.message.edit_text(cap + files_link + del_msg, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML)

@Client.on_callback_query(filters.regex(r"^qual_search"))
async def quality_search(client: Client, query: CallbackQuery):
    _, qual, key, offset, req = query.data.split("#")
    if int(req) != query.from_user.id: return await query.answer("Don't Click Other Results!", show_alert=True)
    search = BUTTONS.get(key)
    cap = CAP.get(key)
    if not search: return await query.answer("Send New Request Again!", show_alert=True)
    files, l_offset, total_results = await get_search_results(search, lang=qual)
    if not files: return await query.answer(f"No files found for '{qual.title()}'", show_alert=1)
    
    settings = await get_settings(query.message.chat.id)
    del_msg = f"\n\n<b>⚠️ Auto delete after <code>{get_readable_time(DELETE_TIME)}</code></b>" if settings["auto_delete"] else ''
    
    files_link = ''
    for file_num, file in enumerate(files, start=1):
        files_link += f"""<b>\n\n{file_num}. <a href=https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file['_id']}>[{get_size(file['file_size'])}] {file['file_name']}</a></b>"""
    
    btn = []
    if l_offset != "":
        btn.append([InlineKeyboardButton(text=f"1/{math.ceil(int(total_results) / MAX_BTN)}", callback_data="buttons"), InlineKeyboardButton(text="ɴᴇxᴛ »", callback_data=f"qual_next#{req}#{key}#{qual}#{l_offset}#{offset}")])
    btn.append([InlineKeyboardButton(text="⪻ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{offset}")])
    await query.message.edit_text(cap + files_link + del_msg, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)

@Client.on_callback_query(filters.regex(r"^qual_next"))
async def quality_next_page(bot, query):
    ident, req, key, qual, l_offset, offset = query.data.split("#")
    if int(req) != query.from_user.id: return await query.answer("Don't Click Other Results!", show_alert=True)
    try: l_offset = int(l_offset)
    except: l_offset = 0
    search = BUTTONS.get(key)
    cap = CAP.get(key)
    files, n_offset, total = await get_search_results(search, offset=l_offset, lang=qual)
    try: n_offset = int(n_offset)
    except: n_offset = 0
    
    settings = await get_settings(query.message.chat.id)
    del_msg = f"\n\n<b>⚠️ Auto delete after <code>{get_readable_time(DELETE_TIME)}</code></b>" if settings["auto_delete"] else ''
    
    files_link = ''
    for file_num, file in enumerate(files, start=l_offset+1):
        files_link += f"""<b>\n\n{file_num}. <a href=https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file['_id']}>[{get_size(file['file_size'])}] {file['file_name']}</a></b>"""

    btn = []
    if 0 < l_offset <= MAX_BTN: b_offset = 0
    elif l_offset == 0: b_offset = None
    else: b_offset = l_offset - MAX_BTN
    
    if n_offset == 0:
        btn.append([InlineKeyboardButton("« ʙᴀᴄᴋ", callback_data=f"qual_next#{req}#{key}#{qual}#{b_offset}#{offset}"), InlineKeyboardButton(f"{math.ceil(int(l_offset) / MAX_BTN) + 1}/{math.ceil(total / MAX_BTN)}", callback_data="buttons")])
    elif b_offset is None:
        btn.append([InlineKeyboardButton(f"{math.ceil(int(l_offset) / MAX_BTN) + 1}/{math.ceil(total / MAX_BTN)}", callback_data="buttons"), InlineKeyboardButton("ɴᴇxᴛ »", callback_data=f"qual_next#{req}#{key}#{qual}#{n_offset}#{offset}")])
    else:
        btn.append([InlineKeyboardButton("« ʙᴀᴄᴋ", callback_data=f"qual_next#{req}#{key}#{qual}#{b_offset}#{offset}"), InlineKeyboardButton(f"{math.ceil(int(l_offset) / MAX_BTN) + 1}/{math.ceil(total / MAX_BTN)}", callback_data="buttons"), InlineKeyboardButton("ɴᴇxᴛ »", callback_data=f"qual_next#{req}#{key}#{qual}#{n_offset}#{offset}")])
    btn.append([InlineKeyboardButton(text="⪻ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{offset}")])
    await query.message.edit_text(cap + files_link + del_msg, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML)

async def auto_filter(client, msg, s, spoll=False):
    if not spoll:
        message = msg
        settings = await get_settings(message.chat.id)
        search = re.sub(r"\s+", " ", re.sub(r"[-:\"';!]", " ", message.text)).strip()
        files, offset, total_results = await get_search_results(search)
        if not files:
            await s.edit(f'I cant find {search}')
            return
    else:
        settings = await get_settings(msg.message.chat.id)
        message = msg.message.reply_to_message 
        search, files, offset, total_results = spoll

    req = message.from_user.id if message and message.from_user else 0
    key = f"{message.chat.id}-{message.id}"
    temp.FILES[key] = files
    BUTTONS[key] = search
    
    files_link = ""
    for file_num, file in enumerate(files, start=1):
        files_link += f"""<b>\n\n{file_num}. <a href=https://t.me/{temp.U_NAME}?start=file_{message.chat.id}_{file['_id']}>[{get_size(file['file_size'])}] {file['file_name']}</a></b>"""
    
    btn = []
    # Filters Restored
    btn.insert(0, [
        InlineKeyboardButton("📰 ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}#{req}#{offset}"),
        InlineKeyboardButton("🔍 ǫᴜᴀʟɪᴛʏ", callback_data=f"quality#{key}#{req}#{offset}")
    ])

    if offset != "":
        btn.append([InlineKeyboardButton(text=f"1/{math.ceil(int(total_results) / MAX_BTN)}", callback_data="buttons"), InlineKeyboardButton(text="ɴᴇxᴛ »", callback_data=f"next_{req}_{key}_{offset}")])

    btn.append([InlineKeyboardButton('🤑 Buy Premium', url=f"https://t.me/{temp.U_NAME}?start=premium")])
    
    cap = f"<b>👋 ʜᴇʀᴇ ɪ ꜰᴏᴜɴᴅ ꜰᴏʀ ʏᴏᴜʀ sᴇᴀʀᴄʜ {search}...</b>"
    CAP[key] = cap
    del_msg = f"\n\n<b>⚠️ Auto delete after <code>{get_readable_time(DELETE_TIME)}</code></b>" if settings["auto_delete"] else ''
    
    k = await s.edit_text(cap + files_link + del_msg, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML)
    
    if settings["auto_delete"]:
        await asyncio.sleep(DELETE_TIME)
        await k.delete()
        try: await message.delete()
        except: pass

@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    if query.data == "close_data":
        await query.message.delete()
  
    elif query.data.startswith("file"):
        ident, file_id = query.data.split("#")
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file_id}")

    elif query.data == "buttons":
        await query.answer()

    # --- START / HELP / ABOUT / STATS ---
    elif query.data == "start":
        buttons = [[
            InlineKeyboardButton("+ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ +", url=f'http://t.me/{temp.U_NAME}?startgroup=start')
        ],[
            InlineKeyboardButton('ℹ️ ᴜᴘᴅᴀᴛᴇs', url=UPDATES_LINK),
            InlineKeyboardButton('🧑‍💻 ꜱᴜᴘᴘᴏʀᴛ', url=SUPPORT_LINK)
        ],[
            InlineKeyboardButton('👨‍🚒 ʜᴇʟᴘ', callback_data='help'),
            InlineKeyboardButton('📚 ᴀʙᴏᴜᴛ', callback_data='about')
        ],[
            InlineKeyboardButton('🤑 Buy Premium', url=f"https://t.me/{temp.U_NAME}?start=premium")
        ]]
        await query.edit_message_media(InputMediaPhoto(random.choice(PICS), caption=script.START_TXT.format(query.from_user.mention, get_wish())), reply_markup=InlineKeyboardMarkup(buttons))
        
    elif query.data == "about":
        buttons = [[InlineKeyboardButton('📊 sᴛᴀᴛᴜs 📊', callback_data='stats'), InlineKeyboardButton('🤖 sᴏᴜʀᴄᴇ ᴄᴏᴅᴇ', callback_data='source')], [InlineKeyboardButton('🧑‍💻 ʙᴏᴛ ᴏᴡɴᴇʀ', callback_data='owner')], [InlineKeyboardButton('« ʙᴀᴄᴋ', callback_data='start')]]
        await query.edit_message_media(InputMediaPhoto(random.choice(PICS), caption=script.MY_ABOUT_TXT), reply_markup=InlineKeyboardMarkup(buttons))

    elif query.data == "stats":
        if query.from_user.id not in ADMINS: return await query.answer("ADMINS Only!", show_alert=True)
        files = db_count_documents()
        users = await db.total_users_count()
        chats = await db.total_chat_count()
        prm = db.get_premium_count()
        uptime = get_readable_time(time_now() - temp.START_TIME)
        buttons = [[InlineKeyboardButton('« ʙᴀᴄᴋ', callback_data='about')]]
        await query.edit_message_media(InputMediaPhoto(random.choice(PICS), caption=script.STATUS_TXT.format(users, prm, chats, "N/A", files, "N/A", "N/A", "N/A", uptime)), reply_markup=InlineKeyboardMarkup(buttons))
    
    elif query.data == "source":
        buttons = [[InlineKeyboardButton('≼ ʙᴀᴄᴋ', callback_data='about')]]
        await query.edit_message_media(InputMediaPhoto(random.choice(PICS), caption=script.SOURCE_TXT), reply_markup=InlineKeyboardMarkup(buttons))

    elif query.data == "owner":
        buttons = [[InlineKeyboardButton('« ʙᴀᴄᴋ', callback_data='about')]]
        await query.edit_message_media(InputMediaPhoto(random.choice(PICS), caption=script.MY_OWNER_TXT), reply_markup=InlineKeyboardMarkup(buttons))
        
    elif query.data == "help":
        buttons = [[InlineKeyboardButton('User Cmd', callback_data='user_command'), InlineKeyboardButton('Admin Cmd', callback_data='admin_command')], [InlineKeyboardButton('« ʙᴀᴄᴋ', callback_data='start')]]
        await query.edit_message_media(InputMediaPhoto(random.choice(PICS), caption=script.HELP_TXT.format(query.from_user.mention)), reply_markup=InlineKeyboardMarkup(buttons))

    elif query.data == "user_command":
        buttons = [[InlineKeyboardButton('« ʙᴀᴄᴋ', callback_data='help')]]
        await query.edit_message_media(InputMediaPhoto(random.choice(PICS), caption=script.USER_COMMAND_TXT), reply_markup=InlineKeyboardMarkup(buttons))
        
    elif query.data == "admin_command":
        if query.from_user.id not in ADMINS: return await query.answer("ADMINS Only!", show_alert=True)
        buttons = [[InlineKeyboardButton('« ʙᴀᴄᴋ', callback_data='help')]]
        await query.edit_message_media(InputMediaPhoto(random.choice(PICS), caption=script.ADMIN_COMMAND_TXT), reply_markup=InlineKeyboardMarkup(buttons))

    # --- PREMIUM & PAYMENT ---
    elif query.data == 'activate_plan':
        q = await query.message.edit('How many days you need premium plan?\nSend days as number (e.g., 30)')
        msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id)
        try: d = int(msg.text)
        except: return await query.message.reply('Invalid number')
        
        transaction_note = f'{d} days premium for {query.from_user.id}'
        amount = d * PRE_DAY_AMOUNT
        upi_uri = f"upi://pay?pa={UPI_ID}&pn={UPI_NAME}&am={amount}&cu=INR&tn={transaction_note}"
        qr = qrcode.make(upi_uri)
        p = f"upi_qr_{query.from_user.id}.png"
        qr.save(p)
        await q.delete()
        await query.message.reply_photo(p, caption=f"Pay {amount} INR\nScan QR & Send Receipt to {RECEIPT_SEND_USERNAME}\n(Timeout 10 mins)")
        os.remove(p)

    elif query.data.startswith("checksub"):
        ident, mc = query.data.split("#")
        btn = await is_subscribed(client, query)
        if btn:
            await query.answer("Please join updates channel!", show_alert=True)
            btn.append([InlineKeyboardButton("🔁 Try Again 🔁", callback_data=f"checksub#{mc}")])
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
            return
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start={mc}")
        await query.message.delete()

    # --- ADMIN SETTINGS TOGGLES ---
    elif query.data.startswith("bool_setgs"):
        ident, set_type, status, grp_id = query.data.split("#")
        userid = query.from_user.id if query.from_user else None
        if not await is_check_admin(client, int(grp_id), userid):
            await query.answer("You not admin!", show_alert=True)
            return
        await save_group_settings(int(grp_id), set_type, False if status == "True" else True)
        btn = await get_grp_stg(int(grp_id))
        await query.message.edit_reply_markup(InlineKeyboardMarkup(btn))
        
    elif query.data == "open_group_settings":
        userid = query.from_user.id if query.from_user else None
        if not await is_check_admin(client, query.message.chat.id, userid):
            return await query.answer("Not Admin", show_alert=True)
        btn = await get_grp_stg(query.message.chat.id)
        await query.message.edit(text=f"Settings for <b>'{query.message.chat.title}'</b>", reply_markup=InlineKeyboardMarkup(btn))

    # --- WELCOME / SHORTLINK / CAPTION SETTINGS ---
    elif query.data.startswith("welcome_setgs"):
        _, grp_id = query.data.split("#")
        userid = query.from_user.id if query.from_user else None
        if not await is_check_admin(client, int(grp_id), userid): return await query.answer("Not Admin", show_alert=True)
        settings = await get_settings(int(grp_id))
        btn = [[InlineKeyboardButton('Set Welcome', callback_data=f'set_welcome#{grp_id}')],[InlineKeyboardButton('Default', callback_data=f'default_welcome#{grp_id}')],[InlineKeyboardButton('Back', callback_data=f'back_setgs#{grp_id}')]]
        await query.message.edit(f'Current Welcome:\n{settings["welcome_text"]}', reply_markup=InlineKeyboardMarkup(btn))

    elif query.data.startswith("set_welcome"):
        _, grp_id = query.data.split("#")
        userid = query.from_user.id if query.from_user else None
        if not await is_check_admin(client, int(grp_id), userid): return await query.answer("Not Admin", show_alert=True)
        m = await query.message.edit('Send Welcome text:')
        msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id)
        await save_group_settings(int(grp_id), 'welcome_text', msg.text)
        await m.delete()
        await query.message.reply('Welcome changed!', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Back', callback_data=f'welcome_setgs#{grp_id}')]]))

    elif query.data.startswith("default_welcome"):
        _, grp_id = query.data.split("#")
        if not await is_check_admin(client, int(grp_id), query.from_user.id): return await query.answer("Not Admin", show_alert=True)
        await save_group_settings(int(grp_id), 'welcome_text', script.WELCOME_TEXT)
        await query.message.edit('Welcome reset to default.', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Back', callback_data=f'welcome_setgs#{grp_id}')]]))

    # Shortlink Settings
    elif query.data.startswith("shortlink_setgs"):
        _, grp_id = query.data.split("#")
        if not await is_check_admin(client, int(grp_id), query.from_user.id): return await query.answer("Not Admin", show_alert=True)
        settings = await get_settings(int(grp_id))
        btn = [[InlineKeyboardButton('Set Shortlink', callback_data=f'set_shortlink#{grp_id}')],[InlineKeyboardButton('Default', callback_data=f'default_shortlink#{grp_id}')],[InlineKeyboardButton('Back', callback_data=f'back_setgs#{grp_id}')]]
        await query.message.edit(f'Current Shortlink:\n{settings["url"]}', reply_markup=InlineKeyboardMarkup(btn))

    elif query.data.startswith("set_shortlink"):
        _, grp_id = query.data.split("#")
        if not await is_check_admin(client, int(grp_id), query.from_user.id): return await query.answer("Not Admin", show_alert=True)
        m = await query.message.edit('Send Shortlink URL:')
        url_msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id)
        await m.delete()
        k = await query.message.reply('Send API Key:')
        key_msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id)
        await save_group_settings(int(grp_id), 'url', url_msg.text)
        await save_group_settings(int(grp_id), 'api', key_msg.text)
        await k.delete()
        await query.message.reply('Shortlink Updated!', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Back', callback_data=f'shortlink_setgs#{grp_id}')]]))

    elif query.data.startswith("default_shortlink"):
        _, grp_id = query.data.split("#")
        if not await is_check_admin(client, int(grp_id), query.from_user.id): return await query.answer("Not Admin", show_alert=True)
        await save_group_settings(int(grp_id), 'url', SHORTLINK_URL)
        await save_group_settings(int(grp_id), 'api', SHORTLINK_API)
        await query.message.edit('Shortlink reset.', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Back', callback_data=f'shortlink_setgs#{grp_id}')]]))
    
    elif query.data.startswith("back_setgs"):
        _, grp_id = query.data.split("#")
        userid = query.from_user.id if query.from_user else None
        if not await is_check_admin(client, int(grp_id), userid): return await query.answer("Not Admin", show_alert=True)
        btn = await get_grp_stg(int(grp_id))
        await query.message.edit(text=f"Settings for <b>Group</b>", reply_markup=InlineKeyboardMarkup(btn))

