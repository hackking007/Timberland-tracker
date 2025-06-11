import requests
from bs4 import BeautifulSoup
import os

# טוקן ו-Chat ID ייקראו מהסודות ב-GitHub
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']
MAX_PRICE = 299
SIZE = '43'

# הגדרת headers "אמיתיים" של דפדפן מודרני
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
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
    soup = BeautifulSoup(response.text, 'html.parser')

    found = []
    for product in soup.select('.product-item-info'):
        title_tag = product.select_one('.product-item-name a')
        price_tag = product.select_one('.price-wrapper .price')
        if not title_tag or not price_tag:
            continue

        title = title_tag.text.strip()
        link = title_tag['href']
        price = float(price_tag.text.replace('₪', '').replace(',', '').strip())

        # כניסה לעמוד המוצר כדי לבדוק מידות
        prod_response = requests.get(link, headers=headers)
        prod_soup = BeautifulSoup(prod_response.text, 'html.parser')
        size_buttons = prod_soup.select('.swatch-attribute-options .swatch-option.text')
        sizes = [btn.text.strip() for btn in size_buttons]

        if SIZE in sizes and price < MAX_PRICE:
            found.append(f'*{title}*\\n₪{price} - [View Product]({link})')

    if found:
        message = f'👟 *Shoes Found ({SIZE}) under ₪{MAX_PRICE}*\\n\\n' + '\\n\\n'.join(found)
        send_telegram_message(message)

if __name__ == '__main__':
    check_shoes()
