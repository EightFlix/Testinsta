from hydrogram import filters, Client
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton # <--- 1. Imported here
import aiohttp
import os
import time
import random
import asyncio
import re
from info import INSTA_CHANNEL 

# Constants
MAX_FILE_SIZE = 50 * 1024 * 1024

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
    "Mozilla/5.0 (Android 10; Mobile; rv:91.0) Gecko/91.0 Firefox/91.0"
]

# --- Helper Functions ---

async def get_instagram_shortcode(link):
    """Extracts the Instagram shortcode from the link."""
    match = re.search(r'instagram.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)', link)
    if match:
        return match.group(1)
    return None

async def method1_instagram_embed(shortcode):
    """Attempts to extract video URL using Instagram's embed endpoint."""
    try:
        url = f"https://www.instagram.com/p/{shortcode}/embed/captioned/"
        async with aiohttp.ClientSession() as session:
            headers = {'User-Agent': random.choice(USER_AGENTS)}
            async with session.get(url, headers=headers, timeout=15) as response:
                if response.status == 200:
                    html = await response.text()
                    # Priority 1: Video URL (for Reels/Videos)
                    match = re.search(r'"video_url":"([^"]+)"', html)
                    if match:
                        return match.group(1).replace('\\u0026', '&')
                    # Priority 2: Display URL (for Images/Carousel)
                    match = re.search(r'"display_url":"([^"]+)"', html)
                    if match:
                        return match.group(1).replace('\\u0026', '&')
    except Exception as e:
        print(f"Embed Method 1 failed for shortcode {shortcode}: {e}")
    return None

async def method2_instagram_api(link):
    """Attempts to extract video URL using a third-party API."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {'User-Agent': random.choice(USER_AGENTS)}
            data = {"q": link, "t": "media", "lang": "en"}
            # Note: This API endpoint is subject to change/failure
            async with session.post("https://v3.saveig.app/api/ajaxSearch", data=data, headers=headers, timeout=15) as response:
                if response.status == 200:
                    result = await response.json()
                    # Handling common response structure variations
                    return result.get('url') or result.get('data', {}).get('url')
    except Exception as e: # <--- Improved error handling
        print(f"API Method 2 failed: {e}")
    return None

async def method3_ddinstagram(link):
    """Attempts to extract media URL using ddinstagram (direct content link)."""
    try:
        dd_url = link.replace("instagram.com", "ddinstagram.com")
        async with aiohttp.ClientSession() as session:
            headers = {'User-Agent': random.choice(USER_AGENTS)}
            # Follow redirects to get the final media URL
            async with session.get(dd_url, headers=headers, allow_redirects=True, timeout=15) as response:
                if response.status == 200 or response.status == 302:
                    final_url = str(response.url)
                    # Check if the final URL is a direct CDN link
                    if 'cdninstagram' in final_url or 'fbcdn' in final_url or 'video' in response.content_type:
                        return final_url
    except Exception as e: # <--- Improved error handling
        print(f"ddinstagram Method 3 failed: {e}")
    return None

async def download_instagram_smart(link, status_msg):
    """Tries multiple methods to get the media URL and downloads the file."""
    shortcode = await get_instagram_shortcode(link)
    if not shortcode:
        return None
    
    video_url = None
    
    # 1. Try Method 1 (Embed)
    await status_msg.edit("Trying Method 1 (Embed)...")
    video_url = await method1_instagram_embed(shortcode)
    
    # 2. Try Method 2 (External API)
    if not video_url:
        await status_msg.edit("Trying Method 2 (External API)...")
        video_url = await method2_instagram_api(link)
    
    # 3. Try Method 3 (ddinstagram)
    if not video_url:
        await status_msg.edit("Trying Method 3 (ddinstagram)...")
        video_url = await method3_ddinstagram(link)
    
    if video_url:
        filename = f"{os.getcwd()}/{int(time.time())}_insta_{shortcode}.mp4" # Added shortcode to filename
        await status_msg.edit("Downloading media...")
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {'User-Agent': random.choice(USER_AGENTS)}
                async with session.get(video_url, headers=headers, timeout=45) as response: # Increased timeout
                    if response.status == 200:
                        size = int(response.headers.get('Content-Length', 0))
                        
                        # Check size before starting download
                        if size > MAX_FILE_SIZE * 1.05: # Added 5% buffer
                            return {"type": "link", "url": video_url}
                        
                        with open(filename, 'wb') as f:
                            downloaded = 0
                            # Use a larger chunk size for efficiency
                            async for chunk in response.content.iter_chunked(2 * 1024 * 1024): 
                                downloaded += len(chunk)
                                if downloaded > MAX_FILE_SIZE:
                                    # If file size exceeds limit mid-download, stop and delete
                                    f.close()
                                    os.remove(filename)
                                    return {"type": "link", "url": video_url}
                                f.write(chunk)
                        
                        return {"type": "file", "path": filename}
                    else:
                        await status_msg.edit(f"Download failed: HTTP Status {response.status}")
        except aiohttp.ClientError as e:
            print(f"Aiohttp download error: {e}")
        except Exception as e:
            print(f"General download error: {e}")
            
    return None

# --- Hydrogram Handler ---

@Client.on_message(filters.regex(r'https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/[A-Za-z0-9_-]+') & filters.incoming)
async def instagram_handler(Mbot, message):
    link = message.matches[0].group(0)
    
    # Check for private or self-destructing posts before processing
    if 'stories' in link or 'private' in link:
        await message.reply("❌ Private or Story links cannot be downloaded this way.")
        return

    status_msg = await message.reply("Processing Instagram link...")
    
    try:
        result = await download_instagram_smart(link, status_msg)
        
        if not result:
            dd_url = link.replace("instagram.com", "ddinstagram.com")
            await status_msg.edit(f"❌ Failed to download media from all methods. Try this direct link: `{dd_url}`")
            return
        
        caption = f"💾 Downloaded via Bot\n\n🔗 Source: [Instagram Link]({link})"
        
        if result["type"] == "file":
            await status_msg.edit("✅ Uploading media...")
            
            # Use appropriate method based on file extension (optional, but good practice)
            # Since most are videos/images, reply_video/photo is generally safer
            file_extension = os.path.splitext(result["path"])[1].lower()
            
            if file_extension in ['.mp4', '.mov']:
                sent_msg = await message.reply_video(result["path"], caption=caption, quote=True)
            elif file_extension in ['.jpg', '.jpeg', '.png']:
                sent_msg = await message.reply_photo(result["path"], caption=caption, quote=True)
            else:
                 sent_msg = await message.reply_document(result["path"], caption=caption, quote=True)

            
            # Copy to INSTA_CHANNEL (Improved error handling)
            if INSTA_CHANNEL:
                try:
                    user_text = f"User: {message.from_user.mention}\nLink: {link}"
                    # Use sent_msg.copy instead of message.copy to send the media directly
                    await sent_msg.copy(INSTA_CHANNEL, caption=f"{caption}\n\n--- Log ---\n{user_text}")
                except Exception as copy_err:
                    print(f"Error copying to INSTA_CHANNEL {INSTA_CHANNEL}: {copy_err}")
                    # Log the error but continue
            
            await status_msg.delete()
            os.remove(result["path"])
            
        elif result["type"] == "link":
            # File is > MAX_FILE_SIZE (50MB)
            btn = InlineKeyboardMarkup([[InlineKeyboardButton("⬇️ Direct Download Link", url=result["url"])]])
            await status_msg.edit(f"⚠️ **File too large (>50MB).**\n\n{caption}", reply_markup=btn, disable_web_page_preview=True)
    
    except Exception as e:
        error_text = f"An unexpected error occurred: {type(e).__name__}: {str(e)}"
        print(error_text)
        await status_msg.edit(f"❌ Operation Failed: {error_text[:200]}...")
