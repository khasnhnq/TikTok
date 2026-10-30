import os
from dotenv import load_dotenv
import httpx
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

# 2. Hàm xử lý riêng cho YouTube (Dùng API trung gian siêu mượt)
async def process_youtube(update: Update, url: str):
    status_msg = await update.message.reply_text("🔍 Đang kết nối API để trích xuất nhạc YouTube...")

    try:
        api_url = "https://co.wuk.sh/api/json"
        payload = {
            "url": url,
            "isAudioOnly": True,
            "dubLang": True
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(api_url, json=payload, headers=headers)
            res_data = response.json()

        if res_data.get("status") in ["error", "rate-limited"]:
            error_text = res_data.get("text", "Không thể xử lý link này.")
            await status_msg.edit_text(f"❌ Lỗi từ API YouTube: {error_text}")
            return

        audio_download_url = res_data.get("url")
        filename = res_data.get("filename", "youtube_audio.mp3")

        if not audio_download_url:
            await status_msg.edit_text("❌ Không tìm thấy link tải âm thanh!")
            return

        await status_msg.edit_text("⏳ Đang tải file nhạc và gửi lên Telegram...")

        async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
            audio_res = await client.get(audio_download_url)
            
            if audio_res.status_code == 200:
                await update.message.reply_audio(
                    audio=audio_res.content,
                    filename=filename,
                    caption="🎧 Đã tải nhạc YouTube thành công bởi @nqk_tiktok_bot"
                )
                await status_msg.delete()
            else:
                await status_msg.edit_text("❌ Không thể tải file âm thanh về bot!")

    except Exception as e:
        await status_msg.edit_text(f"❌ Lỗi kết nối API YouTube: {e}")

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