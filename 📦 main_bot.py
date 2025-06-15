import os
import json
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    filters, ConversationHandler
)

# הגדרת שלבים לשיחה
CATEGORY, SIZE, PRICE = range(3)

# קובץ שמירה
USER_DATA_FILE = "user_data.json"

# טען נתונים קיימים אם קיימים
if os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, "r") as f:
        user_data = json.load(f)
else:
    user_data = {}

def save_user_data():
    with open(USER_DATA_FILE, "w") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)

# התחלה
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        KeyboardButton("גברים"),
        KeyboardButton("נשים"),
        KeyboardButton("ילדים")
    ]]
    await update.message.reply_text(
        "👋 ברוך הבא! באילו קטגוריות נעליים אתה מעוניין?\n(שלח הודעה עם אחת או יותר, מופרדות בפסיקים, לדוגמה: גברים, ילדים)",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return CATEGORY

# קבלת קטגוריות
async def category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text.strip().replace(" ", "")
    categories = text.lower().split(",")
    
    # המרה לערכים לוגיים
    selected = []
    for cat in categories:
        if "גברים" in cat:
            selected.append("men")
        if "נשים" in cat:
            selected.append("women")
        if "ילדים" in cat:
            selected.append("kids")
    
    if not selected:
        await update.message.reply_text("❌ לא זיהיתי קטגוריות תקינות. נסה שוב.")
        return CATEGORY

    user_data[user_id] = {"categories": selected}
    save_user_data()

    await update.message.reply_text("✅ נרשם! עכשיו, באיזו מידה אתה מחפש?")
    return SIZE

# קבלת מידה
async def size_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    size = update.message.text.strip()
    user_data[user_id]["size"] = size
    save_user_data()

    await update.message.reply_text("🔢 ומה טווח המחירים שלך? (לדוגמה: 200-300)")
    return PRICE

# קבלת טווח מחירים
async def price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    price = update.message.text.strip()
    user_data[user_id]["price"] = price
    save_user_data()

    await update.message.reply_text("🎉 ההעדפות שלך נשמרו! מהריצה הקרובה תקבל התראות מותאמות אישית 👟")
    return ConversationHandler.END

# פקודה לצפייה בהעדפות
async def show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in user_data:
        data = user_data[user_id]
        cat_text = ", ".join(data.get("categories", []))
        size = data.get("size", "לא הוגדר")
        price = data.get("price", "לא הוגדר")
        await update.message.reply_text(f"👤 ההעדפות שלך:\n• קטגוריות: {cat_text}\n• מידה: {size}\n• טווח מחירים: {price}")
    else:
        await update.message.reply_text("לא הגדרת עדיין העדפות. שלח /start כדי להתחיל.")

# אתחול האפליקציה
def main():
    app = ApplicationBuilder().token(os.environ["TELEGRAM_TOKEN"]).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, category_handler)],
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