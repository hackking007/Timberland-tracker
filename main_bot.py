import os
import json
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    filters, ConversationHandler
)

# קבועים
USER_DATA_FILE = "user_data.json"
GENDER, SIZE, PRICE = range(3)

# טען מידע קיים
if os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
        user_data = json.load(f)
else:
    user_data = {}

def save_user_data():
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)

# התחלה – גם אם המשתמש כבר קיים, נעדכן את ההעדפות
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_data[user_id] = {}
    save_user_data()
    await update.message.reply_text("👟 ברוך הבא! באיזו קטגוריה אתה מעוניין? (גברים / נשים / ילדים)")
    return GENDER

async def gender_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    gender = update.message.text.strip()
    user_data[user_id]["gender"] = gender
    save_user_data()
    await update.message.reply_text("📏 מה המידה שלך?")
    return SIZE

async def size_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    size = update.message.text.strip()
    user_data[user_id]["size"] = size
    save_user_data()
    await update.message.reply_text("💰 ומה טווח המחירים? (למשל: 100-300)")
    return PRICE

async def price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    price = update.message.text.strip()
    user_data[user_id]["price"] = price
    save_user_data()
    await update.message.reply_text("✅ תודה! ההעדפות נשמרו. תקבל התראות בהתאם מהריצה הבאה.")
    return ConversationHandler.END

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in user_data:
        del user_data[user_id]
        save_user_data()
    await update.message.reply_text("♻️ הנתונים שלך אופסו. שלח /start כדי להזין מחדש את ההעדפות.")

def main():
    app = ApplicationBuilder().token(os.environ["TELEGRAM_TOKEN"]).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, gender_handler)],
            SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, size_handler)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_handler)],
        },
        fallbacks=[],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("reset", reset))

    logging.info("🤖 Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()