from pyrogram import filters, Client
import aiohttp
import os
import time
import random
import asyncio
from yt_dlp import YoutubeDL
from info import INSTA_CHANNEL 

# --- 1. CONFIGURATION ---

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB Limit

COBALT_INSTANCES = [
    "https://co.wuk.sh/api/json",
    "https://api.cobalt.tools/api/json",
    "https://cobalt.kwiatekmiki.pl/api/json"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
]

# --- 2. HELPER FUNCTIONS ---

async def get_file_size(url):
    """URL से फाइल का साइज पता करने की कोशिश करता है"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url) as resp:
                if 'Content-Length' in resp.headers:
                    return int(resp.headers['Content-Length'])
    except:
        pass
    return 0

async def download_file_smart(url, filename, status_msg):
    """
    अगर फाइल <50MB है तो डाउनलोड करेगा।
    अगर >50MB है तो False रिटर्न करेगा (ताकि हम लिंक भेज सकें)।
    """
    try:
        # Step 1: पहले हेड चेक करें (बिना डाउनलोड किये)
        size = await get_file_size(url)
        if size > MAX_FILE_SIZE:
            return "TOO_BIG"

        # Step 2: अगर हेड में साइज नहीं मिला, तो डाउनलोड करते समय चेक करें
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                downloaded = 0
                with open(filename, 'wb') as f:
                    async for chunk in resp.content.iter_chunked(1024 * 1024): # 1MB chunks
                        downloaded += len(chunk)
                        if downloaded > MAX_FILE_SIZE:
                            f.close()
                            os.remove(filename)
                            return "TOO_BIG" # 50MB होते ही रोक दो
                        f.write(chunk)
                return "DOWNLOADED"
    except Exception as e:
        print(f"DL Error: {e}")
        return "ERROR"

async def try_cobalt(link):
    """Cobalt API से डायरेक्ट लिंक लाता है"""
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {"url": link, "vCodec": "h264", "vQuality": "720", "aFormat": "mp3", "filenamePattern": "classic"}
    
    for api_url in COBALT_INSTANCES:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('status') in ['stream', 'redirect']:
                            return data.get('url')
                        elif data.get('status') == 'picker':
                            return data.get('picker')[0]['url']
        except:
            continue 
    return None

async def try_ytdlp_smart(link):
    """
    yt-dlp से पहले Info निकालता है, अगर साइज कम है तो डाउनलोड करता है,
    अगर ज्यादा है तो डायरेक्ट URL देता है।
    """
    opts = {
        'format': 'best[ext=mp4]',
        'quiet': True,
        'noplaylist': True,
        'geo_bypass': True,
        'user_agent': random.choice(USER_AGENTS),
    }

    loop = asyncio.get_running_loop()
    
    def get_info():
        with YoutubeDL(opts) as ydl:
            # download=False का मतलब सिर्फ डेटा लाओ, डाउनलोड मत करो
            return ydl.extract_info(link, download=False)

    try:
        info = await loop.run_in_executor(None, get_info)
        
        # साइज चेक करें
        filesize = info.get('filesize') or info.get('filesize_approx') or 0
        direct_url = info.get('url')

        if filesize > MAX_FILE_SIZE:
            return {"type": "link", "url": direct_url, "size": filesize}
        else:
            # अगर फाइल छोटी है, तो डाउनलोड करें
            filename = f"{os.getcwd()}/{int(time.time())}_{random.randint(100,999)}.mp4"
            # हमें आउटपुट फाइलनेम सेट करना होगा
            opts['outtmpl'] = filename
            await loop.run_in_executor(None, lambda: YoutubeDL(opts).download([link]))
            return {"type": "file", "path": filename}
            
    except Exception as e:
        print(f"yt-dlp Error: {e}")
        return None

# --- 3. MAIN BOT HANDLER ---

@Client.on_message(filters.regex(r'https?://.*(instagram|youtu\.be|youtube|facebook|fb\.watch|tiktok)[^\s]+') & filters.incoming)
async def link_handler(Mbot, message):
    link = message.matches[0].group(0)
    status_msg = await message.reply("🔄 Analyzing Link & Size...")
    
    caption = f"Downloaded By @{Mbot.me.username}"
    final_file_path = None
    direct_link_to_send = None
    
    try:
        # --- METHOD 1: Cobalt API ---
        direct_url = await try_cobalt(link)
        
        if direct_url:
            temp_path = f"{os.getcwd()}/{int(time.time())}_cobalt.mp4"
            result = await download_file_smart(direct_url, temp_path, status_msg)
            
            if result == "DOWNLOADED":
                final_file_path = temp_path
            elif result == "TOO_BIG":
                direct_link_to_send = direct_url # फाइल बड़ी है, डायरेक्ट लिंक सेव कर लो
            # अगर ERROR आया तो अगला मेथड ट्राई करेंगे

        # --- METHOD 2: yt-dlp (अगर Cobalt फेल हुआ या Cobalt ने लिंक नहीं दिया) ---
        if not final_file_path and not direct_link_to_send:
            if "youtu" in link: await status_msg.edit("🐢 Checking YouTube Data...")
            
            ytdlp_result = await try_ytdlp_smart(link)
            
            if ytdlp_result:
                if ytdlp_result["type"] == "file":
                    final_file_path = ytdlp_result["path"]
                elif ytdlp_result["type"] == "link":
                    direct_link_to_send = ytdlp_result["url"]

        # --- ACTION: Upload or Send Link ---

        if final_file_path and os.path.exists(final_file_path):
            # CASE A: फाइल 50MB से छोटी है -> अपलोड करो
            await status_msg.edit("📤 Uploading (Size < 50MB)...")
            sent_msg = await message.reply_video(final_file_path, caption=caption)
            
            if INSTA_CHANNEL:
                try:
                    user_link = f"User: {message.from_user.mention}\nLink: {link}"
                    await sent_msg.copy(INSTA_CHANNEL, caption=f"{caption}\n\n{user_link}")
                except: pass
            
            await status_msg.delete()
            os.remove(final_file_path)

        elif direct_link_to_send:
            # CASE B: फाइल 50MB से बड़ी है -> लिंक भेजो
            size_mb = "50MB+" 
            
            # YouTube लिंक्स के साथ कभी-कभी IP issue होता है, तो हम ओरिजिनल लिंक भी दे देते हैं
            text = (
                f"⚠️ **File is too large (>50MB).**\n"
                f"I cannot upload it to Telegram.\n\n"
                f"📥 **Direct Download Link:**\n[Click Here to Download]({direct_link_to_send})\n\n"
                f"🔗 _If above link fails, use source:_ {link}"
            )
            # लिंक बटन के साथ भेजें
            from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            btn = InlineKeyboardMarkup([[InlineKeyboardButton("📥 Download Video", url=direct_link_to_send)]])
            
            await status_msg.edit(text, reply_markup=btn, disable_web_page_preview=True)
            
        else:
            # CASE C: कुछ नहीं मिला
            if "instagram.com" in link:
                dd_url = link.replace("instagram.com", "ddinstagram.com")
                await status_msg.edit(f"⚠️ Failed or Too Big. Try Direct:\n{dd_url}")
            else:
                await status_msg.edit("❌ Unable to fetch video or extract link.")

    except Exception as e:
        print(f"Global Error: {e}")
        await status_msg.edit(f"Error: {e}")
    
    finally:
        # अगर कोई कचरा बचा है तो साफ़ करो
        if final_file_path and os.path.exists(final_file_path):
            os.remove(final_file_path)
