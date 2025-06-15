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
START, CATEGORY, PRICE = range(3)

# טען משתמשים קיימים
if os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, "r") as f:
        user_data = json.load(f)
else:
    user_data = {}

# שמירה לקובץ
def save_user_data():
    with open(USER_DATA_FILE, "w") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)

# התחלה
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["גברים", "נשים", "ילדים"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("👋 שלום וברוך הבא!

איזה סוג נעליים אתה מחפש? תוכל לבחור יותר מאפשרות אחת בהמשך.", reply_markup=reply_markup)
    return CATEGORY

# קבלת קטגוריה
async def category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    category = update.message.text.strip()

    if user_id not in user_data:
        user_data[user_id] = {}

    user_data[user_id]["category"] = category
    save_user_data()
    await update.message.reply_text("💰 מצוין! מהו טווח המחירים הרצוי? (לדוגמה: 100-300)")
    return PRICE

# קבלת טווח מחיר
async def price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    price_range = update.message.text.strip()
    user_data[user_id]["price"] = price_range
    save_user_data()

    await update.message.reply_text("✅ ההעדפות שלך נשמרו! מהריצה הבאה תקבל התראות מותאמות 🎯")
    return ConversationHandler.END

# פקודה לצפייה בהעדפות
async def show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in user_data:
        data = user_data[user_id]
        category = data.get("category", "לא נבחר")
        price = data.get("price", "לא נבחר")
        await update.message.reply_text(f"🔧 ההעדפות שלך:\n• קטגוריה: {category}\n• טווח מחירים: {price}")
    else:
        await update.message.reply_text("לא הגדרת עדיין העדפות. שלח /start כדי להתחיל.")

# פונקציה ליצירת URL מותאם
# (נשתמש בה מאוחר יותר בתוך GitHub Actions כדי להריץ לפי ההעדפות)
def build_url(category, price_range):
    category_map = {
        "גברים": "men/footwear",
        "נשים": "women",
        "ילדים": "kids"
    }
    size_map = {
        "גברים": "794",
        "נשים": "10",
        "ילדים": "234"
    }
    if category not in category_map:
        return None

    base = "https://www.timberland.co.il/"
    category_path = category_map[category]
    size = size_map[category]
    price_range = price_range.replace(" ", "").replace("₪", "")
    return f"{base}{category_path}?price={price_range}&size={size}"

# רישום הבוט
def main():
    app = ApplicationBuilder().token(os.environ["TELEGRAM_TOKEN"]).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, category_handler)],
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