"""Telegram bot: lắng nghe group, chuyển ảnh/câu hỏi cho agent."""
import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, CommandHandler, filters

load_dotenv()
import agent  # noqa: E402  (sau load_dotenv để đọc env)
import db  # noqa: E402
import tools  # noqa: E402

logging.basicConfig(level=logging.INFO)
ALLOWED = {int(x) for x in os.getenv("ALLOWED_CHAT_IDS", "").split(",") if x.strip()}


def allowed(update: Update) -> bool:
    return update.effective_chat.id in ALLOWED


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.effective_message
    if not m or not allowed(update):
        return
    text = m.text or m.caption or ""
    me = context.bot.username
    private = update.effective_chat.type == "private"
    mentioned = f"@{me}".lower() in text.lower()
    replied_to_bot = bool(m.reply_to_message and m.reply_to_message.from_user
                          and m.reply_to_message.from_user.id == context.bot.id)
    # Ảnh luôn xử lý (quy trình nhập xe); text chỉ khi gọi tên bot / reply bot / chat riêng
    if not (m.photo or private or mentioned or replied_to_bot):
        return
    image = file_id = None
    if m.photo:
        file_id = m.photo[-1].file_id
        image = bytes(await (await context.bot.get_file(file_id)).download_as_bytearray())
    if m.reply_to_message and (m.reply_to_message.text or m.reply_to_message.caption):
        text += f"\n(trả lời tin: {m.reply_to_message.text or m.reply_to_message.caption})"
    ctx = {"user": m.from_user.full_name, "chat_id": update.effective_chat.id, "photo_file_id": file_id or ""}
    await context.bot.send_chat_action(update.effective_chat.id, "typing")
    try:
        reply = await agent.handle(text.replace(f"@{me}", "").strip(), image, ctx)
    except Exception:
        logging.exception("agent error")
        reply = "Lỗi hệ thống, anh/chị thử lại sau ít phút."
    await m.reply_text(reply)


async def cmd_huy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    try:
        bid = int(context.args[0])
    except (IndexError, ValueError):
        return await update.effective_message.reply_text("Dùng: /huy <mã bill>")
    out = tools.run("void_bill", {"bill_id": bid}, {}, agent.DB_PATH)
    await update.effective_message.reply_text(
        f"Đã huỷ bill #{bid}, hoàn tồn kho." if "voided" in out else f"Lỗi: {out['error']}")


async def cmd_homnay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    s = tools.run("today_summary", {}, {}, agent.DB_PATH)
    lines = [f"#{b['id']} {b['plate']} — {b['total']:,}đ" for b in s["bills"]]
    await update.effective_message.reply_text(
        f"Hôm nay: {s['count']} xe, doanh thu {s['revenue_vnd']:,}đ\n" + "\n".join(lines))


def main():
    db.init(agent.DB_PATH)
    app = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
    app.add_handler(CommandHandler("huy", cmd_huy))
    app.add_handler(CommandHandler("homnay", cmd_homnay))
    app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, on_message))
    app.run_polling()


if __name__ == "__main__":
    main()
