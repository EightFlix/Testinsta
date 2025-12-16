from hydrogram import filters, Client
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url) as resp:
                if 'Content-Length' in resp.headers:
                    return int(resp.headers['Content-Length'])
    except: pass
    return 0

async def get_caption_smart(link):
    """yt-dlp से ओरिजिनल कैप्शन निकालता है (बिना डाउनलोड किए)"""
    opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'geo_bypass': True,
        'user_agent': random.choice(USER_AGENTS),
    }
    
    def _extract():
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=False)
                return info.get('description') or info.get('title') or ""
        except Exception as e:
            return None

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _extract)

async def download_file_smart(url, filename, status_msg):
    try:
        size = await get_file_size(url)
        if size > MAX_FILE_SIZE: return "TOO_BIG"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                downloaded = 0
                with open(filename, 'wb') as f:
                    async for chunk in resp.content.iter_chunked(1024 * 1024):
                        downloaded += len(chunk)
                        if downloaded > MAX_FILE_SIZE:
                            f.close()
                            os.remove(filename)
                            return "TOO_BIG"
                        f.write(chunk)
                return "DOWNLOADED"
    except Exception as e:
        print(f"DL Error: {e}")
        return "ERROR"

async def try_cobalt(link):
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {"url": link, "vCodec": "h264", "vQuality": "720", "aFormat": "mp3", "filenamePattern": "classic"}
    for api_url in COBALT_INSTANCES:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('status') in ['stream', 'redirect']: return data.get('url')
                        elif data.get('status') == 'picker': return data.get('picker')[0]['url']
        except: continue 
    return None

async def try_ytdlp_smart(link):
    opts = {'format': 'best[ext=mp4]', 'quiet': True, 'noplaylist': True, 'geo_bypass': True, 'user_agent': random.choice(USER_AGENTS)}
    loop = asyncio.get_running_loop()
    
    def get_info():
        with YoutubeDL(opts) as ydl:
            return ydl.extract_info(link, download=False)

    try:
        info = await loop.run_in_executor(None, get_info)
        filesize = info.get('filesize') or info.get('filesize_approx') or 0
        direct_url = info.get('url')
        caption = info.get('description') or info.get('title')

        if filesize > MAX_FILE_SIZE:
            return {"type": "link", "url": direct_url, "size": filesize, "caption": caption}
        else:
            filename = f"{os.getcwd()}/{int(time.time())}_{random.randint(100,999)}.mp4"
            opts['outtmpl'] = filename
            await loop.run_in_executor(None, lambda: YoutubeDL(opts).download([link]))
            return {"type": "file", "path": filename, "caption": caption}
    except Exception as e:
        print(f"yt-dlp Error: {e}")
        return None

# --- 3. MAIN BOT HANDLER ---

@Client.on_message(filters.regex(r'https?://.*(instagram|youtu\.be|youtube|facebook|fb\.watch|tiktok)[^\s]+') & filters.incoming)
async def link_handler(Mbot, message):
    link = message.matches[0].group(0)
    status_msg = await message.reply("🔄 Fetching Content...")
    
    # कैप्शन निकालना शुरू करें
    original_caption_task = asyncio.create_task(get_caption_smart(link))
    
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
                direct_link_to_send = direct_url

        # --- METHOD 2: yt-dlp ---
        if not final_file_path and not direct_link_to_send:
            if "youtu" in link: await status_msg.edit("🐢 Using yt-dlp...")
            ytdlp_result = await try_ytdlp_smart(link)
            if ytdlp_result:
                if ytdlp_result["type"] == "file":
                    final_file_path = ytdlp_result["path"]
                elif ytdlp_result["type"] == "link":
                    direct_link_to_send = ytdlp_result["url"]
        
        # --- CAPTION CONSTRUCTION (With Hyperlink) ---
        original_caption = await original_caption_task
        
        # सिर्फ हाइपरलिंक वाला फूटर
        footer_text = f"[🔗 Source Link]({link}) | Downloaded By @{Mbot.me.username}"
        
        if original_caption:
            # कैप्शन को 800 शब्दों तक सीमित रखें ताकि टेलीग्राम एरर न दे
            truncated_caption = (original_caption[:800] + '...') if len(original_caption) > 800 else original_caption
            final_caption = f"{truncated_caption}\n\n{footer_text}"
        else:
            final_caption = footer_text

        # --- ACTION: Upload ---

        if final_file_path and os.path.exists(final_file_path):
            await status_msg.edit("📤 Uploading...")
            
            # मैंने यहाँ बटन भी रखा है (आप चाहे तो reply_markup वाली लाइन हटा सकते हैं)
            # लेकिन बटन + हाइपरलिंक दोनों होना बेस्ट होता है।
            source_btn = InlineKeyboardMarkup([[InlineKeyboardButton("↗️ Open Post", url=link)]])

            sent_msg = await message.reply_video(
                final_file_path, 
                caption=final_caption,
                reply_markup=source_btn
            )
            
            # Insta Channel में कॉपी
            if INSTA_CHANNEL:
                try:
                    user_link = f"User: {message.from_user.mention}\nLink: {link}"
                    await sent_msg.copy(INSTA_CHANNEL, caption=f"{final_caption}\n\n{user_link}")
                except: pass
            
            await status_msg.delete()
            os.remove(final_file_path)

        elif direct_link_to_send:
            text = (
                f"⚠️ **File >50MB.**\n"
                f"📥 **Direct Link:**\n[Click to Download]({direct_link_to_send})\n\n"
                f"🔗 [Original Post]({link})"
            )
            btn = InlineKeyboardMarkup([[InlineKeyboardButton("📥 Download", url=direct_link_to_send)]])
            await status_msg.edit(text, reply_markup=btn, disable_web_page_preview=True)
            
        else:
            if "instagram.com" in link:
                dd_url = link.replace("instagram.com", "ddinstagram.com")
                await status_msg.edit(f"⚠️ Failed. Try Direct:\n{dd_url}")
            else:
                await status_msg.edit("❌ Unable to fetch content.")

    except Exception as e:
        print(f"Global Error: {e}")
        await status_msg.edit(f"Error: {e}")
    
    finally:
        if final_file_path and os.path.exists(final_file_path):
            os.remove(final_file_path)

