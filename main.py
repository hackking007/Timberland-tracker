import requests
import os

# קריאה לערכים מתוך משתני סביבה (מוגדרים ב-GitHub Secrets)
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']

def send_telegram_message(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    response = requests.post(url, data=payload)
    print("Status code:", response.status_code)
    print("Response:", response.text)

if __name__ == '__main__':
    send_telegram_message("✅ *בדיקה - ההודעה נשלחה בהצלחה!*")
