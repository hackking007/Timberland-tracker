import os
import json
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)

USER_DATA_FILE = "user_data.json"
START, GENDER, SIZE, PRICE = range(4)

if os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, "r") as f:
        user_data = json.load(f)
else:
    user_data = {}

def save_user_data():
    with open(USER_DATA_FILE, "w") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["גברים", "נשים", "ילדים"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text("👋 שלום! באיזו קטגוריה אתה מעוניין?", reply_markup=reply_markup)
    return GENDER

async def gender_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    category_map = {"גברים": "men", "נשים": "women", "ילדים": "kids"}
    gender_input = update.message.text.strip()
    gender = category_map.get(gender_input, "men")
    user_data[user_id] = {"gender": gender}
    save_user_data()
    await update.message.reply_text("📏 מה המידה שלך?")
    return SIZE

async def size_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    size = update.message.text.strip()
    user_data[user_id]["size"] = size
    save_user_data()
    await update.message.reply_text("💰 מהו טווח המחירים? (לדוג׳: 100-300)")
    return PRICE

async def price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    price = update.message.text.strip()
    user_data[user_id]["price"] = price
    save_user_data()
    await update.message.reply_text("✅ מעולה! ההעדפות נשמרו 🎯 תקבל התראות החל מהריצה הבאה")
    return ConversationHandler.END

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
    app.run_polling()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
