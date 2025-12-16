from hydrogram import filters, Client
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from yt_dlp import YoutubeDL
import asyncio

# --- CONFIGURATION ---
# कुछ साइट्स के लिए User-Agent बहुत जरुरी होता है
USER_AGENTS = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

@Client.on_message(filters.command(["gen", "link", "glink"]))
async def genlink_handler(client, message):
    # 1. चेक करें कि लिंक दिया है या नहीं
    if len(message.command) < 2:
        return await message.reply_text(
            "ℹ️ **इस्तेमाल:**\n`/gen https://example.com/video`\n\nकिसी भी साइट का डायरेक्ट लिंक बनाने के लिए।"
        )

    url = message.command[1]
    status_msg = await message.reply_text("🔄 **कोशिश कर रहा हूँ...**\n_कृपया प्रतीक्षा करें..._")

    try:
        # 2. yt-dlp सेटिंग्स (Universal)
        opts = {
            'quiet': True,
            'no_warnings': True,
            'geo_bypass': True,
            'noplaylist': True,
            'user_agent': USER_AGENTS,
            'allow_unplayable_formats': True, # स्ट्रीम साइट्स के लिए जरुरी
            'check_formats': True,
        }

        # 3. डाटा निकालना (Background Task)
        loop = asyncio.get_running_loop()
        
        def extract_info():
            with YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)

        info = await loop.run_in_executor(None, extract_info)

        # 4. फॉर्मेट्स को छानना (Qualities Filter)
        title = info.get('title', 'Unknown Video')
        formats = info.get('formats', [])
        
        # बटन बनाने के लिए लिस्ट
        buttons = []
        row = []
        
        # अगर अलग-अलग क्वालिटी उपलब्ध हैं (जैसे Youtube, XVideos, XHamster)
        available_qualities = {}
        for fmt in formats:
            video_ext = fmt.get('video_ext')
            height = fmt.get('height')
            
            # सिर्फ सही वीडियो फॉर्मेट लें
            if video_ext != 'none' and height:
                resolution_str = f"{height}p"
                available_qualities[resolution_str] = fmt.get('url')

        # अगर फॉर्मेट्स मिले तो बटन बनाएं
        if available_qualities:
            # हाई क्वालिटी से लो क्वालिटी सॉर्ट करें
            sorted_keys = sorted(available_qualities.keys(), key=lambda x: int(x.replace('p', '')), reverse=True)
            
            for qual in sorted_keys:
                btn_text = f"🎬 {qual}"
                btn_url = available_qualities[qual]
                row.append(InlineKeyboardButton(btn_text, url=btn_url))
                if len(row) == 3: # एक लाइन में 3 बटन
                    buttons.append(row)
                    row = []
            if row: buttons.append(row)
            
        # अगर फॉर्मेट्स नहीं मिले लेकिन एक डायरेक्ट लिंक है (जैसे Streamtape)
        elif info.get('url'):
            direct_url = info.get('url')
            buttons.append([InlineKeyboardButton("▶️ Watch / Download", url=direct_url)])
        
        else:
            # अगर न फॉर्मेट मिला न लिंक
            raise Exception("No direct link found")

        # ओरिजिनल पोस्ट का बटन
        buttons.append([InlineKeyboardButton("↗️ Original Link", url=url)])

        # 5. सफलता का मैसेज
        text = (
            f"✅ **लिंक जेनरेट हो गया!**\n\n"
            f"📂 **Title:** `{title}`\n"
            f"👇 **नीचे दिए गए बटन से देखें या डाउनलोड करें:**"
        )
        
        await status_msg.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    except Exception as e:
        # 6. अगर फेल हुआ तो ये मैसेज आएगा
        print(f"GenLink Error: {e}")
        error_text = (
            "❌ **लिंक जेनरेट नहीं हो सका।**\n\n"
            "संभावित कारण:\n"
            "1. यह साइट समर्थित नहीं है।\n"
            "2. वीडियो प्राइवेट या डिलीट हो चुका है।\n"
            "3. यह DRM (Netflix/Hotstar) प्रोटेक्टेड है।"
        )
        await status_msg.edit_text(error_text)
