import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Thay bằng Token của bạn
TOKEN = "9146193201:AAGXhRBVRG4eSalEbniJALlAj_rJMmSKPyI"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 **Bot Tải TikTok Đa Năng (@nqk_tiktok_bot)**\n\n"
        "Hãy gửi bất kỳ đường link TikTok (Video hoặc Album ảnh) vào đây!",
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
            # Dùng bản chuẩn (không ép hd=1 quá nặng) để tốc độ nhanh nhất, nếu muốn HD có thể thêm "hd": 1
            response = await client.post("https://www.tikwm.com/api/", data={"url": url}, timeout=30.0)
            res_data = response.json()

        if res_data.get("code") != 0:
            await status_msg.edit_text("❌ Không thể lấy dữ liệu. Có thể video riêng tư hoặc link lỗi!")
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
            f"✅ **Đã tìm thấy nội dung!**\n"
            f"📝 **Tiêu đề:** {context.user_data['tiktok_data']['title']}\n\n"
            f"👇 Hãy chọn định dạng bạn muốn tải về:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    except Exception as e:
        await status_msg.edit_text(f"❌ Đã xảy ra lỗi khi xử lý: {e}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    tiktok_data = context.user_data.get("tiktok_data")
    if not tiktok_data:
        await query.edit_message_text("⚠️ Phiên làm việc đã hết hạn. Vui lòng gửi lại link TikTok!")
        return

    choice = query.data
    status_msg = await query.message.reply_text("⏳ Đang tải file và gửi lên Telegram...")

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
            
            # 1. XỬ LÝ TẢI VIDEO MP4 KHÔNG LOGO
            if choice == "dl_video":
                try:
                    # Cách 1: Cho Telegram tự tải thẳng từ URL (Cực nhanh, chỉ mất 1-2 giây)
                    await query.message.reply_video(
                        video=tiktok_data["video"],
                        caption=f"🎬 {tiktok_data['title']}",
                        supports_streaming=True,
                        read_timeout=120,
                        write_timeout=120
                    )
                except Exception:
                    # Cách 2 (Dự phòng): Nếu link bị chặn, máy tính sẽ tải về rồi đẩy lên với timeout 120s
                    video_res = await client.get(tiktok_data["video"])
                    await query.message.reply_video(
                        video=video_res.content,
                        caption=f"🎬 {tiktok_data['title']}",
                        supports_streaming=True,
                        read_timeout=120,
                        write_timeout=120
                    )

            # 2. XỬ LÝ TÁCH NHẠC MP3
            elif choice == "dl_audio":
                audio_res = await client.get(tiktok_data["music"])
                await query.message.reply_audio(
                    audio=audio_res.content,
                    title=tiktok_data["title"],
                    filename="tiktok_audio.mp3",
                    caption="🎵 Âm thanh gốc trích xuất từ TikTok",
                    read_timeout=120,
                    write_timeout=120
                )

            # 3. XỬ LÝ TẢI ALBUM ẢNH KHÔNG LOGO
            elif choice == "dl_images":
                images = tiktok_data["images"]
                for i in range(0, len(images), 10):
                    chunk = images[i:i+10]
                    media_group = [InputMediaPhoto(media=img_url) for img_url in chunk]
                    await query.message.reply_media_group(
                        media=media_group,
                        read_timeout=120,
                        write_timeout=120
                    )

        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"❌ Lỗi khi gửi file: {e}")

def main():
    # Tăng giới hạn thời gian chờ (Timeout) toàn cục lên 120 giây
    app = (
        Application.builder()
        .token(TOKEN)
        .read_timeout(120)
        .write_timeout(120)
        .connect_timeout(60)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_tiktok_link))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("🚀 Bot TikTok (Bản nâng cấp chống Timeout) đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()