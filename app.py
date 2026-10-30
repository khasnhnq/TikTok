import os
import asyncio
from dotenv import load_dotenv
import httpx
import shutil
import yt_dlp
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Tải file .env nếu chạy local trên máy tính
load_dotenv()

# Lấy token từ biến môi trường
TOKEN = os.environ.get("TOKEN", "").strip()
PORT = int(os.environ.get("PORT", "8000"))
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

app = FastAPI()
telegram_app = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    await update.message.reply_text(
        "🎬 *Bot Tải TikTok & Nhạc YouTube Đa Năng*\n"
        "👤 Username: `@nqk_tiktok_bot`\n\n"
        "👇 Hãy gửi đường link TikTok hoặc YouTube vào đây!",
        parse_mode="Markdown"
    )

# 1. Hàm xử lý riêng cho TikTok
async def process_tiktok(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    status_msg = await update.message.reply_text("🔍 Đang phân tích link TikTok, đợi xíu nhé...")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post("https://www.tikwm.com/api/", data={"url": url}, timeout=30.0)
            res_data = response.json()

        if res_data.get("code") != 0:
            await status_msg.edit_text("❌ Không thể lấy dữ liệu TikTok!")
            return

        data = res_data["data"]
        context.user_data["tiktok_data"] = {
            "title": data.get("title", "TikTok Media")[:100],
            "video": data.get("play"),
            "music": data.get("music"),
            "images": data.get("images", [])
        }

        keyboard = []
        if context.user_data["tiktok_data"]["images"]:
            so_anh = len(context.user_data["tiktok_data"]["images"])
            keyboard.append([InlineKeyboardButton(f"🖼️ Tải bộ {so_anh} Ảnh (Không Logo)", callback_data="dl_images")])
        else:
            keyboard.append([InlineKeyboardButton("🎬 Tải Video MP4 (Không Logo)", callback_data="dl_video")])
        
        keyboard.append([InlineKeyboardButton("🎵 Tách nhạc MP3", callback_data="dl_audio")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await status_msg.edit_text(
            "✅ *Đã tìm thấy nội dung TikTok!*\n\n"
            "👇 Hãy chọn định dạng bạn muốn tải về:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ Lỗi: {e}")

# Hàm phụ tải âm thanh YouTube có dùng Cookie
def download_youtube_audio(url: str):
    ydl_opts = {
        'format': 'best[ext=m4a]/best/bestaudio', # Mở rộng dải tìm kiếm format linh hoạt hơn
        'outtmpl': '/tmp/%(id)s.%(ext)s',
        'max_filesize': 50 * 1024 * 1024,
        'noplaylist': True,
        'quiet': True,
        # Giả lập client để không bị kén định dạng stream
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web']
            }
        }
    }
    
    # Nạp file cookies.txt từ Secret Files của Render
    secret_cookie = '/etc/secrets/cookies.txt'
    tmp_cookie = '/tmp/cookies.txt'
    if os.path.exists(secret_cookie):
        shutil.copyfile(secret_cookie, tmp_cookie)
        ydl_opts['cookiefile'] = tmp_cookie

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = ydl.prepare_filename(info)
        title = info.get('title', 'YouTube Audio')
        return file_path, title

# 2. Hàm xử lý riêng cho YouTube (Tách nhạc)
async def process_youtube(update: Update, url: str):
    status_msg = await update.message.reply_text("🔍 Đang trích xuất âm thanh từ YouTube, đợi chút nhé...")
    file_path = None

    try:
        # Chạy yt-dlp trong thread riêng để không làm treo FastAPI
        file_path, title = await asyncio.to_thread(download_youtube_audio, url)

        if not file_path or not os.path.exists(file_path):
            await status_msg.edit_text("❌ Không thể tải file âm thanh (Có thể file nặng quá 50MB)!")
            return

        await status_msg.edit_text("⏳ Đang gửi file âm thanh lên Telegram...")

        with open(file_path, 'rb') as audio_file:
            await update.message.reply_audio(
                audio=audio_file,
                title=title[:60],
                performer="YouTube Audio",
                caption=f"🎧 {title}\n🤖 Tải bởi @nqk_tiktok_bot"
            )

        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"❌ Lỗi khi tải YouTube: {e}")
    finally:
        # Luôn xóa file tạm sau khi gửi xong để tránh đầy bộ nhớ Render
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

# 3. Hàm điều hướng chính khi người dùng gửi tin nhắn
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if "tiktok.com" in url:
        await process_tiktok(update, context, url)
    elif "youtube.com" in url or "youtu.be" in url:
        await process_youtube(update, url)
    else:
        await update.message.reply_text("⚠️ Vui lòng gửi đường link TikTok hoặc YouTube hợp lệ!")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    tiktok_data = context.user_data.get("tiktok_data")
    if not tiktok_data:
        await query.edit_message_text("⚠️ Phiên làm việc đã hết hạn. Vui lòng gửi lại link!")
        return

    choice = query.data
    status_msg = await query.message.reply_text("⏳ Đang tải file và gửi lên Telegram...")

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
            if choice == "dl_video":
                try:
                    await query.message.reply_video(video=tiktok_data["video"], supports_streaming=True)
                except Exception:
                    video_res = await client.get(tiktok_data["video"])
                    await query.message.reply_video(video=video_res.content, supports_streaming=True)
            elif choice == "dl_audio":
                audio_res = await client.get(tiktok_data["music"])
                await query.message.reply_audio(audio=audio_res.content, filename="tiktok_audio.mp3")
            elif choice == "dl_images":
                images = tiktok_data["images"]
                for i in range(0, len(images), 10):
                    chunk = images[i:i+10]
                    media_group = [InputMediaPhoto(media=img_url) for img_url in chunk]
                    await query.message.reply_media_group(media=media_group)
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"❌ Lỗi khi gửi file: {e}")

@app.on_event("startup")
async def startup_event():
    global telegram_app
    if not TOKEN:
        raise ValueError("❌ Biến TOKEN chưa được cấu hình hoặc đang bị rỗng!")
    
    telegram_app = (
        Application.builder()
        .token(TOKEN)
        .read_timeout(120)
        .write_timeout(120)
        .connect_timeout(60)
        .build()
    )

    # Đăng ký các handler (Đã đổi sang gọi hàm handle_link)
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    telegram_app.add_handler(CallbackQueryHandler(button_callback))

    await telegram_app.initialize()
    if RENDER_EXTERNAL_URL:
        await telegram_app.bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/webhook")

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"status": "Bot is running!"}