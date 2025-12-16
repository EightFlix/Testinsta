from hydrogram import filters, Client
import aiohttp
import os
import time
import random
import asyncio
import re
import json
from info import INSTA_CHANNEL 

MAX_FILE_SIZE = 50 * 1024 * 1024

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
    "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36",
]

# --- Instagram के लिए Multiple Methods ---

async def get_instagram_shortcode(link):
    """Instagram link से shortcode निकालें"""
    patterns = [
        r'instagram.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)',
        r'instagram.com/([A-Za-z0-9_-]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            return match.group(1)
    return None

async def method1_instagram_embed(shortcode):
    """Instagram Embed API से download करें (सबसे reliable)"""
    try:
        url = f"https://www.instagram.com/p/{shortcode}/embed/captioned/"
        async with aiohttp.ClientSession() as session:
            headers = {
                'User-Agent': random.choice(USER_AGENTS),
                'Accept': 'text/html,application/xhtml+xml',
            }
            async with session.get(url, headers=headers, timeout=15) as response:
                if response.status == 200:
                    html = await response.text()
                    
                    # Video URL ढूंढें
                    video_patterns = [
                        r'"video_url":"([^"]+)"',
                        r'video_url&quot;:&quot;([^&]+)&quot;',
                        r'og:video" content="([^"]+)"',
                    ]
                    
                    for pattern in video_patterns:
                        match = re.search(pattern, html)
                        if match:
                            video_url = match.group(1).replace('\\u0026', '&').replace('&amp;', '&')
                            return video_url
                    
                    # अगर video नहीं मिला, image ढूंढें
                    img_patterns = [
                        r'"display_url":"([^"]+)"',
                        r'og:image" content="([^"]+)"',
                    ]
                    
                    for pattern in img_patterns:
                        match = re.search(pattern, html)
                        if match:
                            img_url = match.group(1).replace('\\u0026', '&')
                            return img_url
                            
    except Exception as e:
        print(f"Embed method failed: {e}")
    return None

async def method2_instagram_api(link):
    """Third-party APIs से try करें"""
    apis = [
        {
            "url": "https://v3.saveig.app/api/ajaxSearch",
            "method": "POST",
            "data": lambda l: {"q": l, "t": "media", "lang": "en"}
        },
        {
            "url": "https://api.downloadgram.org/media",
            "method": "POST", 
            "data": lambda l: {"url": l}
        }
    ]
    
    for api in apis:
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    'User-Agent': random.choice(USER_AGENTS),
                    'Content-Type': 'application/x-www-form-urlencoded',
                }
                
                if api["method"] == "POST":
                    async with session.post(
                        api["url"], 
                        data=api["data"](link),
                        headers=headers,
                        timeout=15
                    ) as response:
                        if response.status == 200:
                            try:
                                data = await response.json()
                                # Different APIs have different response structures
                                video_url = (
                                    data.get('url') or 
                                    data.get('data', {}).get('url') or
                                    data.get('video_url') or
                                    (data.get('data', {}).get('video') if isinstance(data.get('data'), dict) else None)
                                )
                                if video_url:
                                    return video_url
                            except:
                                # HTML response हो सकता है
                                html = await response.text()
                                match = re.search(r'href="([^"]+download[^"]+)"', html)
                                if match:
                                    return match.group(1)
        except Exception as e:
            print(f"API {api['url']} failed: {e}")
            continue
    return None

async def method3_ddinstagram(link):
    """ddInstagram redirect method"""
    try:
        dd_url = link.replace("instagram.com", "ddinstagram.com")
        async with aiohttp.ClientSession() as session:
            headers = {'User-Agent': random.choice(USER_AGENTS)}
            async with session.get(dd_url, headers=headers, allow_redirects=True, timeout=15) as response:
                if response.status == 200:
                    final_url = str(response.url)
                    if 'cdninstagram' in final_url or 'fbcdn' in final_url:
                        return final_url
    except Exception as e:
        print(f"ddInstagram failed: {e}")
    return None

async def download_instagram_smart(link, status_msg):
    """सभी methods को順序 से try करें"""
    
    shortcode = await get_instagram_shortcode(link)
    if not shortcode:
        return None
    
    # Method 1: Instagram Embed (most reliable for public posts)
    await status_msg.edit("🔍 Method 1: Instagram Embed...")
    video_url = await method1_instagram_embed(shortcode)
    
    # Method 2: Third-party APIs
    if not video_url:
        await status_msg.edit("🔍 Method 2: API Services...")
        video_url = await method2_instagram_api(link)
    
    # Method 3: ddInstagram
    if not video_url:
        await status_msg.edit("🔍 Method 3: ddInstagram...")
        video_url = await method3_ddinstagram(link)
    
    if video_url:
        # File download करें
        filename = f"{os.getcwd()}/{int(time.time())}_insta.mp4"
        await status_msg.edit("📥 Downloading...")
        
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

# --- Caption Function ---
async def get_caption_smart(link):
    """Caption निकालें"""
    shortcode = await get_instagram_shortcode(link)
    if not shortcode:
        return ""
    
    try:
        url = f"https://www.instagram.com/p/{shortcode}/embed/captioned/"
        async with aiohttp.ClientSession() as session:
            headers = {'User-Agent': random.choice(USER_AGENTS)}
            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    html = await response.text()
                    caption_match = re.search(r'"caption":"([^"]+)"', html)
                    if caption_match:
                        caption = caption_match.group(1)
                        # Unicode escape sequences को decode करें
                        return caption.encode().decode('unicode_escape')
    except:
        pass
    return ""

# --- Main Handler ---
@Client.on_message(filters.regex(r'https?://(?:www.)?instagram.com/(?:p|reel|tv)/[A-Za-z0-9_-]+') & filters.incoming)
async def instagram_handler(Mbot, message):
    link = message.matches[0].group(0)
    status_msg = await message.reply("🔄 Processing Instagram Post...")
    
    try:
        # Caption निकालें (parallel में)
        caption_task = asyncio.create_task(get_caption_smart(link))
        
        # Download करें
        result = await download_instagram_smart(link, status_msg)
        
        if not result:
            # Fallback: ddInstagram link दें
            dd_url = link.replace("instagram.com", "ddinstagram.com")
            await status_msg.edit(
                f"⚠️ **Download Failed**

"
                f"Try this direct link:
{dd_url}

"
                f"[🔗 Original Post]({link})"
            )
            return
        
        # Caption तैयार करें
        caption = await caption_task
        footer = f"[🔗 Source]({link})"
        final_caption = f"{caption[:900]}

{footer}" if caption else footer
        
        if result["type"] == "file":
            await status_msg.edit("📤 Uploading...")
            sent_msg = await message.reply_video(
                result["path"],
                caption=final_caption
            )
            
            # Channel में forward करें
            if INSTA_CHANNEL:
                try:
                    user_info = f"User: {message.from_user.mention}
Link: {link}"
                    await sent_msg.copy(INSTA_CHANNEL, caption=f"{final_caption}

{user_info}")
                except:
                    pass
            
            await status_msg.delete()
            os.remove(result["path"])
            
        elif result["type"] == "link":
            from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            btn = InlineKeyboardMarkup([[InlineKeyboardButton("📥 Download", url=result["url"])]])
            await status_msg.edit(
                f"⚠️ **File >50MB**

{final_caption}",
                reply_markup=btn,
                disable_web_page_preview=True
            )
    
    except Exception as e:
        print(f"Instagram Handler Error: {e}")
        await status_msg.edit(f"❌ Error: {e}")
