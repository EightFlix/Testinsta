import logging
import logging.config

# Logging Setup
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logging.getLogger('hydrogram').setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

import os
import time
import asyncio
import uvloop
from hydrogram import Client, idle
from aiohttp import web
from web import web_app
from info import (
    API_ID, API_HASH, BOT_TOKEN, PORT, 
    LOG_CHANNEL, ADMINS
)
from utils import temp, check_premium
from database.users_chats_db import db

# Install uvloop for faster async execution
uvloop.install()

class Bot(Client):
    def __init__(self):
        super().__init__(
            name='Auto_Filter_Bot',
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            plugins={"root": "plugins"} # ✅ यह लाइन सबसे जरुरी है, इससे insta.py लोड होगा
        )

    async def start(self):
        await super().start()
        temp.START_TIME = time.time()
        
        # Load Banned Users/Chats
        b_users, b_chats = await db.get_banned()
        temp.BANNED_USERS = b_users
        temp.BANNED_CHATS = b_chats

        # Restart Handler logic
        if os.path.exists('restart.txt'):
            with open("restart.txt") as file:
                chat_id, msg_id = map(int, file)
            try:
                await self.edit_message_text(chat_id=chat_id, message_id=msg_id, text='Restarted Successfully!')
            except:
                pass
            os.remove('restart.txt')

        temp.BOT = self
        me = await self.get_me()
        temp.ME = me.id
        temp.U_NAME = me.username
        temp.B_NAME = me.first_name
        
        # Web Server Setup (For Health Check/Koyeb)
        app = web.AppRunner(web_app)
        await app.setup()
        await web.TCPSite(app, "0.0.0.0", PORT).start()

        asyncio.create_task(check_premium(self))
        
        # Log Channel Notification
        try:
            await self.send_message(chat_id=LOG_CHANNEL, text=f"<b>{me.mention} Restarted! 🤖</b>")
        except Exception as e:
            logger.error(f"Make sure bot admin in LOG_CHANNEL: {e}")
            
        logger.info(f"@{me.username} is started now ✓")

    async def stop(self, *args):
        await super().stop()
        logger.info("Bot Stopped! Bye...")

async def main():
    app = Bot()
    await app.start()
    await idle()
    await app.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Error occurred: {e}")

