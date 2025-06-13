import os
import json
import logging
from telegram import Update, ForceReply
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# הגדרת שלבים לשיחה
ASK_SIZE, ASK_PRICE = range(2)

# קובץ שמירת המשתמשים
USERS_FILE = 'users.json'

# קריאה או יצירה של קובץ המשתמשים
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

# /start - תחילת תהליך ההרשמה
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("👟 ברוך הבא! נתחיל בהגדרת הפרטים.\nמה המידה שלך?")
    return ASK_SIZE

# קבלת מידה
async def ask_size(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    size = update.message.text.strip()
    context.user_data['size'] = size
    await update.message.reply_text("🪙 מה טווח המחירים שאתה מחפש? לדוגמה: 200-300")
    return ASK_PRICE

# קבלת טווח מחירים ושמירת הנתונים
async def ask_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    price_range = update.message.text.strip()
    user_id = str(update.message.chat_id)

    users = load_users()
    users[user_id] = {
        "size": context.user_data.get('size'),
        "price_range": price_range,
        "username": update.message.from_user.username or "",
        "first_name": update.message.from_user.first_name or ""
    }
    save_users(users)

    await update.message.reply_text("✅ ההגדרה נשמרה! תקבל התראות מותאמות אישית 🎯")
    return ConversationHandler.END

# ביטול
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ ההרשמה בוטלה. תוכל לנסות שוב עם /start")
    return ConversationHandler.END

# קונפיג לוגים
logging.basicConfig(level=logging.INFO)

if __name__ == '__main__':
    TOKEN = os.environ['TELEGRAM_TOKEN']
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ASK_SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_size)],
            ASK_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_price)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    app.add_handler(conv_handler)

    print("🤖 Bot is running...")
    app.run_polling()