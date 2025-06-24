import os
import json
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)

# קובץ הנתונים לשמירת העדפות המשתמשים
USER_DATA_FILE = "user_data.json"

# שלבים בשיחה
START, GENDER, SIZE, PRICE = range(4)

# טעינת נתוני משתמשים מהקובץ (אם קיים)
if os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, "r") as f:
        user_data = json.load(f)
else:
    user_data = {}

# שמירת נתוני המשתמשים לקובץ
def save_user_data():
    with open(USER_DATA_FILE, "w") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)

# התחלת שיחה עם המשתמש
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["גברים", "נשים", "ילדים"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text("👋 שלום! באיזו קטגוריה אתה מעוניין?", reply_markup=reply_markup)
    return GENDER

# בחירת מגדר
async def gender_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    category_map = {"גברים": "men", "נשים": "women", "ילדים": "kids"}
    gender_input = update.message.text.strip()
    if gender_input not in category_map:
        await update.message.reply_text("❌ אנא בחר מגדר תקני: גברים / נשים / ילדים")
        return GENDER
    gender = category_map[gender_input]
    user_data[user_id] = {"gender": gender}
    save_user_data()
    await update.message.reply_text("📏 מה המידה שלך?")
    return SIZE

# בחירת מידה
async def size_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    size = update.message.text.strip()
    if not size.isdigit():
        await update.message.reply_text("❌ אנא הזן מספר תקין (למשל: 43)")
        return SIZE
    user_data[user_id]["size"] = size
    save_user_data()
    await update.message.reply_text("💰 מהו טווח המחירים? (למשל: 100-300)")
    return PRICE

# בחירת טווח מחיר
async def price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    price = update.message.text.strip()
    if "-" not in price or not all(p.strip().isdigit() for p in price.split("-")):
        await update.message.reply_text("❌ אנא כתוב טווח מחיר תקני (למשל: 100-300)")
        return PRICE
    user_data[user_id]["price"] = price
    save_user_data()
    await update.message.reply_text("✅ מעולה! ההעדפות נשמרו 🎯 תקבל התראות החל מהריצה הבאה")
    return ConversationHandler.END

# צפייה בהעדפות המשתמש
async def show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    prefs = user_data.get(user_id)
    if prefs:
        gender_map = {"men": "גברים", "women": "נשים", "kids": "ילדים"}
        gender = gender_map.get(prefs["gender"], "לא נבחר")
        await update.message.reply_text(
            f"👤 ההעדפות שלך:\nקטגוריה: {gender}\nמידה: {prefs['size']}\nטווח מחיר: {prefs['price']}"
        )
    else:
        await update.message.reply_text("אין לך עדיין העדפות מוגדרות. שלח /start כדי להתחיל.")

# איפוס העדפות
async def reset_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in user_data:
        del user_data[user_id]
        save_user_data()
        await update.message.reply_text("✅ ההעדפות שלך נמחקו. תוכל להתחיל מחדש עם /start")
    else:
        await update.message.reply_text("ℹ️ אין לך העדפות שמורות.")

# הגדרת הבוט והפעלה
def main():
    app = ApplicationBuilder().token(os.environ["TELEGRAM_TOKEN"]).build()
    
    # ניהול השיחה לפי השלבים
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, gender_handler)],
            SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, size_handler)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_handler)],
        },
        fallbacks=[]
    )

    # הוספת הפקודות
    app.add_handler(conv)
    app.add_handler(CommandHandler("show", show))
    app.add_handler(CommandHandler("reset", reset_handler))
    app.run_polling()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()