import os
import requests

TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']

def send_test_message():
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    payload = {
        'chat_id': CHAT_ID,
        'text': '✅ בדיקת חיבור: הבוט עובד ומוכן לשליחה!',
        'parse_mode': 'Markdown'
    }
    response = requests.post(url, data=payload)
    print("Status Code:", response.status_code)
    print("Response:", response.text)

if __name__ == '__main__':
    send_test_message()