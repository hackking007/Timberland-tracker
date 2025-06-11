import requests
from bs4 import BeautifulSoup
import os

TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
}

def send_telegram_message(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    requests.post(url, data=payload)

def check_shoes():
    url = 'https://www.timberland.co.il/men/footwear'
    response = requests.get(url, headers=headers)

    with open("timberland_output.html", "w", encoding="utf-8") as f:
        f.write(response.text)

    send_telegram_message("📄 HTML page saved and uploaded.")

if __name__ == '__main__':
    check_shoes()
