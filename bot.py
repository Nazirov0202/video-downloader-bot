#!/usr/bin/env python3
import os
os.system("apt-get install -y ffmpeg > /dev/null 2>&1")
import asyncio
import logging
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import yt_dlp

BOT_TOKEN = "8781543474:AAEcAD8zRtd2xQzNrBySUjEsJdMuCizqVmU"

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)
MAX_MB = 50

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def is_supported(url):
    return any(x in url for x in ["youtube.com", "youtu.be", "instagram.com"])

def get_info(url):
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
            return ydl.extract_info(url, download=False)
    except:
        return None

def download(url, quality, audio_only):
    out = str(DOWNLOAD_DIR / "%(title).60s.%(ext)s")
    formats = {
        "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "720p": "bestvideo[height<=720][ext=mp4]+bestaudio/best[height<=720]",
        "480p": "bestvideo[height<=480][ext=mp4]+bestaudio/best[height<=480]",
        "360p": "bestvideo[height<=360][ext=mp4]+bestaudio/best[height<=360]",
    }
    if audio_only:
        opts = {
            "format": "bestaudio/best",
            "outtmpl": out,
            "quiet": True,
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        }
    else:
        opts = {"format": formats.get(quality, formats["best"]), "outtmpl": out, "merge_output_format": "mp4", "quiet": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = Path(ydl.prepare_filename(info))
            if audio_only:
                path = path.with_suffix(".mp3")
            return str(path) if path.exists() else None
    except Exception as e:
        logger.error(f"Yuklash xatosi: {e}")
        return None

async def cmd_start(update, ctx):
    await update.message.reply_text(
        "👋 *Salom! Video Downloader Bot*\n\n"
        "📎 YouTube yoki Instagram havolasini yuboring\n\n"
        "✅ Qo'llab-quvvatlanadi:\n"
        "• YouTube — video, shorts\n"
        "• Instagram — reels, post\n"
        "• Sifat tanlash: Best / 720p / 480p / 360p\n"
        "• 🎵 MP3 audio yuklash\n\n"
        "▶️ Havola yuboring va boshlang!",
        parse_mode="Markdown"
    )

async def handle_url(update, ctx):
    url = update.message.text.strip()
    if not url.startswith("http"):
        return
    if not is_supported(url):
        await update.message.reply_text("❌ Faqat *YouTube* va *Instagram* havolalari qabul qilinadi.", parse_mode="Markdown")
        return
    msg = await update.message.reply_text("🔍 Havola tekshirilmoqda...")
    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(None, lambda: get_info(url))
    if not info:
        await msg.edit_text("❌ Video topilmadi yoki havola noto'g'ri.")
        return
    title = info.get("title", "Video")[:55]
    duration = int(info.get("duration") or 0)
    mins, secs = divmod(duration, 60)
    dur_str = f"{mins}:{secs:02d}" if duration else "—"
    keyboard = [
        [InlineKeyboardButton("🏆 Best", callback_data=f"v|best|{url}"), InlineKeyboardButton("📺 720p", callback_data=f"v|720p|{url}")],
        [InlineKeyboardButton("📱 480p", callback_data=f"v|480p|{url}"), InlineKeyboardButton("🔹 360p", callback_data=f"v|360p|{url}")],
        [InlineKeyboardButton("🎵 MP3 Audio", callback_data=f"a|mp3|{url}")],
    ]
    await msg.edit_text(f"🎬 *{title}*\n⏱ Davomiylik: `{dur_str}`\n\n📥 Formatni tanlang:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_callback(update, ctx):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("|", 2)
    if len(parts) < 3:
        return
    mode, quality, url = parts
    audio_only = (mode == "a")
    label = "MP3 Audio" if audio_only else quality
    await query.edit_message_text(f"⏳ *{label}* formatda yuklanmoqda...\nBir necha daqiqa kuting ⏱", parse_mode="Markdown")
    loop = asyncio.get_event_loop()
    filepath = await loop.run_in_executor(None, lambda: download(url, quality, audio_only))
    if not filepath or not Path(filepath).exists():
        await query.edit_message_text("❌ Yuklashda xato yuz berdi. Qayta urinib ko'ring.")
        return
    size_mb = Path(filepath).stat().st_size / (1024 * 1024)
    if size_mb > MAX_MB:
        Path(filepath).unlink(missing_ok=True)
        await query.edit_message_text(f"❌ Fayl {size_mb:.1f}MB — juda katta.\nKichikroq sifat tanlang.")
        return
    await query.edit_message_text("📤 Yuborilmoqda...")
    try:
        with open(filepath, "rb") as f:
            if audio_only:
                await query.message.reply_audio(audio=f, caption="🎵 Mana sizning audiongiz!", read_timeout=120, write_timeout=120)
            else:
                await query.message.reply_video(video=f, caption="🎬 Mana sizning videongiz!", read_timeout=120, write_timeout=120)
        await query.delete_message()
    except Exception as e:
        logger.error(f"Yuborish xatosi: {e}")
        await query.edit_message_text("❌ Yuborishda xato. Qayta urinib ko'ring.")
    finally:
        Path(filepath).unlink(missing_ok=True)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern="^[va]\\|"))
    print("🤖 Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
