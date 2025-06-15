import os
import json
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    filters, ConversationHandler
)

# נתיבי קובץ
USER_DATA_FILE = "user_data.json"

# שלבי השיחה
CATEGORY, SIZE, PRICE = range(3)

# טען מידע קיים
if os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
        user_data = json.load(f)
else:
    user_data = {}

# שמור מידע
def save_user_data():
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)

# התחלה
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("גברים")], [KeyboardButton("נשים")], [KeyboardButton("ילדים")]]
    await update.message.reply_text(
        "👋 ברוך הבא! איזה סוג נעליים אתה מחפש?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return CATEGORY

# קטגוריה
async def category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    category = update.message.text.strip().lower()
    user_data[user_id] = {"gender": category}
    save_user_data()
    await update.message.reply_text("📏 באיזו מידה אתה מעוניין?")
    return SIZE

# מידה
async def size_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    size = update.message.text.strip()
    user_data[user_id]["size"] = size
    save_user_data()
    await update.message.reply_text("💸 מהו טווח המחירים הרצוי? (לדוגמה: 100-300)")
    return PRICE

# טווח מחירים
async def price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    price_range = update.message.text.strip()
    user_data[user_id]["price"] = price_range
    save_user_data()
    await update.message.reply_text("✅ תודה! מעכשיו תקבל התראות מותאמות אישית לפי העדפותיך.")
    return ConversationHandler.END

# פקודה לצפייה בהעדפות
async def show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in user_data:
        data = user_data[user_id]
        await update.message.reply_text(
            f"🔧 ההעדפות שלך:\n• קטגוריה: {data['gender']}\n• מידה: {data['size']}\n• טווח מחירים: {data['price']}"
        )
    else:
        await update.message.reply_text("אין העדפות שמורות. שלח /start כדי להתחיל.")

# איפוס משתמש
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in user_data:
        del user_data[user_id]
        save_user_data()
    await update.message.reply_text("🔁 ההעדפות שלך אופסו. שלח /start כדי להתחיל מחדש.")

# אתחול הבוט
def main():
    app = ApplicationBuilder().token(os.environ["TELEGRAM_TOKEN"]).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, category_handler)],
            SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, size_handler)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_handler)],
        },
        fallbacks=[]
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("show", show))
    app.add_handler(CommandHandler("reset", reset))

    app.run_polling()

if __name__ == "__main__":
    main()