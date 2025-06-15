import os
import json
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
)

USER_DATA_FILE = "user_data.json"
START, GENDER, SIZE, PRICE = range(4)

# טען נתונים קיימים
if os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
        user_data = json.load(f)
else:
    user_data = {}

def save_user_data():
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in user_data:
        await update.message.reply_text("🔁 כבר הגדרת העדפות. שלח /show כדי לצפות בהן או /reset כדי להתחיל מחדש.")
        return ConversationHandler.END
    reply_markup = ReplyKeyboardMarkup([["גברים", "נשים", "ילדים"]], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("👟 שלום! איזה סוג נעליים אתה מחפש?", reply_markup=reply_markup)
    return GENDER

async def gender_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gender = update.message.text.strip()
    if gender not in ["גברים", "נשים", "ילדים"]:
        await update.message.reply_text("❗ אנא בחר אחת מהאפשרויות: גברים, נשים או ילדים.")
        return GENDER
    user_id = str(update.effective_user.id)
    user_data[user_id] = {"gender": gender}
    save_user_data()
    await update.message.reply_text("📏 מעולה! מה המידה שלך?")
    return SIZE

async def size_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    size = update.message.text.strip()
    user_id = str(update.effective_user.id)
    user_data[user_id]["size"] = size
    save_user_data()
    await update.message.reply_text("💰 מצוין! ומה טווח המחירים שתרצה? (לדוגמה: 0-300)")
    return PRICE

async def price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price_range = update.message.text.strip()
    user_id = str(update.effective_user.id)
    user_data[user_id]["price"] = price_range
    save_user_data()
    await update.message.reply_text("✅ שמרתי את ההעדפות שלך! תתחיל לקבל התראות מותאמות אישית 🎯")
    return ConversationHandler.END

async def show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in user_data:
        prefs = user_data[user_id]
        await update.message.reply_text(
            f"🔧 ההעדפות שלך:\n• סוג: {prefs['gender']}\n• מידה: {prefs['size']}\n• טווח מחיר: {prefs['price']}"
        )
    else:
        await update.message.reply_text("לא הגדרת העדפות. שלח /start כדי להתחיל.")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_data.pop(user_id, None)
    save_user_data()
    await update.message.reply_text("🔄 ההעדפות שלך אופסו. שלח /start כדי להתחיל מחדש.")

def main():
    app = ApplicationBuilder().token(os.environ["TELEGRAM_TOKEN"]).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, gender_handler)],
            SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, size_handler)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_handler)],
        },
        fallbacks=[]
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("show", show))
    app.add_handler(CommandHandler("reset", reset))

    logging.basicConfig(level=logging.INFO)
    app.run_polling()

if __name__ == '__main__':
    main()