import os
import json
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    filters, ConversationHandler
)

# קבצים קבועים
USER_DATA_FILE = "user_data.json"
START, SIZE, PRICE = range(3)

# טען משתמשים קיימים
if os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, "r") as f:
        user_data = json.load(f)
else:
    user_data = {}

# שמירה לקובץ
def save_user_data():
    with open(USER_DATA_FILE, "w") as f:
        json.dump(user_data, f)

# התחלה
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👟 ברוך הבא! כדי להתחיל, באיזו מידה אתה מחפש נעליים?")
    return SIZE

# קבלת מידה
async def size_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    size = update.message.text.strip()
    user_data[user_id] = {"size": size}
    save_user_data()
    await update.message.reply_text(f"🧮 מצוין! ועכשיו, מהו טווח המחירים הרצוי? (לדוג׳: 200-300)")
    return PRICE

# קבלת טווח מחיר
async def price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    price_range = update.message.text.strip()
    user_data[user_id]["price"] = price_range
    save_user_data()

    await update.message.reply_text("✅ ההעדפות שלך נשמרו! מהריצה הבאה תקבל התראות מותאמות אישית 🎯")
    return ConversationHandler.END

# פקודה לצפייה בהעדפות
async def show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in user_data:
        size = user_data[user_id]["size"]
        price = user_data[user_id]["price"]
        await update.message.reply_text(f"🔧 ההעדפות שלך:\n• מידה: {size}\n• טווח מחירים: {price}")
    else:
        await update.message.reply_text("לא הגדרת עדיין העדפות. שלח /start כדי להתחיל.")

# רישום הבוט
def main():
    app = ApplicationBuilder().token(os.environ["TELEGRAM_TOKEN"]).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, size_handler)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_handler)],
        },
        fallbacks=[],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("show", show))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()