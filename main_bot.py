import os
import json
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    filters, ConversationHandler
)

# קבצים קבועים
USER_DATA_FILE = "user_data.json"
START, SIZE, PRICE, GENDER = range(4)

# טען משתמשים קיימים
if os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
        user_data = json.load(f)
else:
    user_data = {}

# שמירה לקובץ
def save_user_data():
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)

# התחלה
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👟 ברוך הבא! אילו נעליים מעניינות אותך?\n\n"
        "בחר אחת או יותר: גברים / נשים / ילדים"
    )
    return GENDER

# קבלת קטגוריה (גברים/נשים/ילדים)
async def gender_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    gender = update.message.text.strip().lower()
    if user_id not in user_data:
        user_data[user_id] = {}

    user_data[user_id]["gender"] = gender
    save_user_data()

    await update.message.reply_text("📏 מצוין! איזו מידה אתה מחפש?")
    return SIZE

# קבלת מידה
async def size_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    size = update.message.text.strip()
    user_data[user_id]["size"] = size
    save_user_data()
    await update.message.reply_text("💰 ומה טווח המחירים הרצוי? (לדוג׳: 200-300)")
    return PRICE

# קבלת טווח מחיר
async def price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    price_range = update.message.text.strip()
    user_data[user_id]["price"] = price_range
    save_user_data()

    await update.message.reply_text("✅ ההעדפות שלך נשמרו! מהריצה הבאה תקבל התראות מותאמות אישית 🎯")
    return ConversationHandler.END

# פקודת צפייה בהעדפות
async def show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in user_data:
        data = user_data[user_id]
        await update.message.reply_text(
            f"🔧 ההעדפות שלך:\n"
            f"• קטגוריה: {data.get('gender', 'לא הוזן')}\n"
            f"• מידה: {data.get('size', 'לא הוזן')}\n"
            f"• טווח מחירים: {data.get('price', 'לא הוזן')}"
        )
    else:
        await update.message.reply_text("לא הגדרת עדיין העדפות. שלח /start כדי להתחיל.")

# פקודת איפוס העדפות
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in user_data:
        del user_data[user_id]
        save_user_data()
        await update.message.reply_text("🔄 ההעדפות שלך אופסו.\nשלח /start כדי להזין אותן מחדש.")
    else:
        await update.message.reply_text("🤔 אין לך העדפות שמורות.\nשלח /start כדי להתחיל.")

# הרשמה והרצה
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
    app.add_handler(CommandHandler("show", show))
    app.add_handler(CommandHandler("reset", reset))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()