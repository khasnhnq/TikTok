import os
from dotenv import load_dotenv # 1. Import thư viện
load_dotenv()
import httpx
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = os.environ.get("TOKEN", "9146193201:AAFwMReGr51ZkrtbNNoR1sHi08Mi0mgay38")
PORT = int(os.environ.get("PORT", "8000"))
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://nqk-tiktok-bot.onrender.com")

app = FastAPI()

# Khởi tạo Telegram Bot Application
telegram_app = (
    Application.builder()
    .token(TOKEN)
    .read_timeout(120)
    .write_timeout(120)
    .connect_timeout(60)
    .build()
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 **Bot Tải TikTok Đa Năng (@nqk_tiktok_bot)**\n\n"
        "Hãy gửi bất kỳ đường link TikTok vào đây!",
        parse_mode="Markdown"
    )

async def handle_tiktok_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if "tiktok.com" not in url:
        await update.message.reply_text("⚠️ Vui lòng gửi một đường link TikTok hợp lệ!")
        return

    status_msg = await update.message.reply_text("🔍 Đang phân tích link TikTok, đợi xíu nhé...")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post("https://www.tikwm.com/api/", data={"url": url}, timeout=30.0)
            res_data = response.json()

        if res_data.get("code") != 0:
            await status_msg.edit_text("❌ Không thể lấy dữ liệu!")
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
            f"✅ **Đã tìm thấy nội dung TikTok!**\n\n"
            f"👇 Hãy chọn định dạng bạn muốn tải về:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ Lỗi: {e}")

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

# Đăng ký các handler
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_tiktok_link))
telegram_app.add_handler(CallbackQueryHandler(button_callback))

@app.on_event("startup")
async def startup_event():
    await telegram_app.initialize()
    # Kích hoạt Webhook với Telegram
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