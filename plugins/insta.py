from hydrogram import filters, Client
import aiohttp
import os
import time
import random
import asyncio
import re
from info import INSTA_CHANNEL 

MAX_FILE_SIZE = 50 * 1024 * 1024

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
]

async def get_instagram_shortcode(link):
    match = re.search(r'instagram.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)', link)
    if match:
        return match.group(1)
    return None

async def method1_instagram_embed(shortcode):
    try:
        url = f"https://www.instagram.com/p/{shortcode}/embed/captioned/"
        async with aiohttp.ClientSession() as session:
            headers = {'User-Agent': random.choice(USER_AGENTS)}
            async with session.get(url, headers=headers, timeout=15) as response:
                if response.status == 200:
                    html = await response.text()
                    match = re.search(r'"video_url":"([^"]+)"', html)
                    if match:
                        return match.group(1).replace('\\u0026', '&')
                    match = re.search(r'"display_url":"([^"]+)"', html)
                    if match:
                        return match.group(1).replace('\\u0026', '&')
    except Exception as e:
        print(f"Embed failed: {e}")
    return None

async def method2_instagram_api(link):
    try:
        async with aiohttp.ClientSession() as session:
            headers = {'User-Agent': random.choice(USER_AGENTS)}
            data = {"q": link, "t": "media", "lang": "en"}
            async with session.post("https://v3.saveig.app/api/ajaxSearch", data=data, headers=headers, timeout=15) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('url') or result.get('data', {}).get('url')
    except:
        pass
    return None

async def method3_ddinstagram(link):
    try:
        dd_url = link.replace("instagram.com", "ddinstagram.com")
        async with aiohttp.ClientSession() as session:
            headers = {'User-Agent': random.choice(USER_AGENTS)}
            async with session.get(dd_url, headers=headers, allow_redirects=True, timeout=15) as response:
                if response.status == 200:
                    final_url = str(response.url)
                    if 'cdninstagram' in final_url or 'fbcdn' in final_url:
                        return final_url
    except:
        pass
    return None

async def download_instagram_smart(link, status_msg):
    shortcode = await get_instagram_shortcode(link)
    if not shortcode:
        return None
    
    await status_msg.edit("Method 1...")
    video_url = await method1_instagram_embed(shortcode)
    
    if not video_url:
        await status_msg.edit("Method 2...")
        video_url = await method2_instagram_api(link)
    
    if not video_url:
        await status_msg.edit("Method 3...")
        video_url = await method3_ddinstagram(link)
    
    if video_url:
        filename = f"{os.getcwd()}/{int(time.time())}_insta.mp4"
        await status_msg.edit("Downloading...")
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {'User-Agent': random.choice(USER_AGENTS)}
                async with session.get(video_url, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        size = int(response.headers.get('Content-Length', 0))
                        
                        if size > MAX_FILE_SIZE:
                            return {"type": "link", "url": video_url}
                        
                        with open(filename, 'wb') as f:
                            downloaded = 0
                            async for chunk in response.content.iter_chunked(1024 * 1024):
                                downloaded += len(chunk)
                                if downloaded > MAX_FILE_SIZE:
                                    f.close()
                                    os.remove(filename)
                                    return {"type": "link", "url": video_url}
                                f.write(chunk)
                        
                        return {"type": "file", "path": filename}
        except Exception as e:
            print(f"Download error: {e}")
    
    return None

@Client.on_message(filters.regex(r'https?://(?:www.)?instagram.com/(?:p|reel|tv)/[A-Za-z0-9_-]+') & filters.incoming)
async def instagram_handler(Mbot, message):
    link = message.matches[0].group(0)
    status_msg = await message.reply("Processing...")
    
    try:
        result = await download_instagram_smart(link, status_msg)
        
        if not result:
            dd_url = link.replace("instagram.com", "ddinstagram.com")
            await status_msg.edit(f"Failed. Try: {dd_url}")
            return
        
        caption = f"Source: {link}"
        
        if result["type"] == "file":
            await status_msg.edit("Uploading...")
            sent_msg = await message.reply_video(result["path"], caption=caption)
            
            if INSTA_CHANNEL:
                try:
                    user_text = f"User: {message.from_user.mention}
Link: {link}"
                    await sent_msg.copy(INSTA_CHANNEL, caption=f"{caption}

{user_text}")
                except:
                    pass
            
            await status_msg.delete()
            os.remove(result["path"])
            
        elif result["type"] == "link":
            from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            btn = InlineKeyboardMarkup([[InlineKeyboardButton("Download", url=result["url"])]])
            await status_msg.edit(f"File >50MB

{caption}", reply_markup=btn)
    
    except Exception as e:
        print(f"Error: {e}")
        await status_msg.edit(f"Error: {e}")
