import os
import json
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    filters, ConversationHandler
)

USER_DATA_FILE = "user_data.json"
SELECT_CATEGORY, ENTER_SIZE, ENTER_PRICE = range(3)

if os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
        user_data = json.load(f)
else:
    user_data = {}

def save_user_data():
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = [['גברים', 'נשים', 'ילדים']]
    await update.message.reply_text(
        "👋 ברוך הבא לבוט טימברלנד!\n\n"
        "באילו קטגוריות אתה מעוניין לקבל עדכונים? (ניתן לבחור יותר מאחת, הפרד בפסיקים)",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return SELECT_CATEGORY

async def category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    categories = update.message.text.strip().replace(" ", "").lower().split(',')

    category_map = {
        'גברים': 'men',
        'נשים': 'women',
        'ילדים': 'kids'
    }

    selected = [category_map.get(cat, "") for cat in categories if category_map.get(cat)]
    if not selected:
        await update.message.reply_text("אנא בחר לפחות קטגוריה אחת מתוך: גברים, נשים, ילדים.")
        return SELECT_CATEGORY

    user_data[user_id] = {"categories": selected}
    save_user_data()
    await update.message.reply_text("✅ מעולה! מהי המידה הרצויה שלך?", reply_markup=ReplyKeyboardRemove())
    return ENTER_SIZE

async def size_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    size = update.message.text.strip()
    user_data[user_id]["size"] = size
    save_user_data()
    await update.message.reply_text("💰 נהדר! מהו טווח המחירים הרצוי? (לדוגמה: 200-300)")
    return ENTER_PRICE

async def price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    price = update.message.text.strip()
    user_data[user_id]["price"] = price
    save_user_data()
    await update.message.reply_text("🎉 ההעדפות נשמרו! מהריצה הקרובה תקבל עדכונים מותאמים אישית.")
    return ConversationHandler.END

async def show_preferences(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    prefs = user_data.get(user_id)
    if prefs:
        categories = ', '.join(prefs["categories"])
        size = prefs["size"]
        price = prefs["price"]
        await update.message.reply_text(
            f"🔧 ההעדפות שלך:\n• קטגוריות: {categories}\n• מידה: {size}\n• טווח מחירים: {price}"
        )
    else:
        await update.message.reply_text("לא הגדרת עדיין העדפות. שלח /start כדי להתחיל.")

def main():
    app = ApplicationBuilder().token(os.environ["TELEGRAM_TOKEN"]).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, category_handler)],
            ENTER_SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, size_handler)],
            ENTER_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_handler)],
        },
        fallbacks=[],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("show", show_preferences))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()