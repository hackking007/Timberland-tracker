import os
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']
MAX_PRICE = 299
SIZE = '43'

def send_telegram_message(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    requests.post(url, data=payload)

def check_shoes():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # נשתמש בדפדפן עם GUI
        context = browser.new_context(locale='he-IL', user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36')
        page = context.new_page()
        page.goto('https://www.timberland.co.il/men/footwear', timeout=60000)
        page.screenshot(path="screenshot.png", full_page=True)  # צילום מסך לעיון

        try:
            page.wait_for_selector('.product-item-info', timeout=60000)
        except:
            send_telegram_message("❌ לא נמצאו מוצרים בדף. אולי נחסם על ידי האתר.")
            return

        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, 'html.parser')
    found = []
    for product in soup.select('.product-item-info'):
        title_tag = product.select_one('.product-item-name a')
        price_tag = product.select_one('.price-wrapper .price')
        if not title_tag or not price_tag:
            continue

        title = title_tag.text.strip()
        link = title_tag['href']
        price = float(price_tag.text.replace('₪', '').replace(',', '').strip())

        if SIZE in title and price < MAX_PRICE:
            found.append(f'*{title}*\\n₪{price} - [View Product]({link})')

    if found:
        message = f'👟 *Shoes Found ({SIZE}) under ₪{MAX_PRICE}*\\n\\n' + '\\n\\n'.join(found)
        send_telegram_message(message)
    else:
        send_telegram_message("🤷‍♂️ No matching shoes found.")

if __name__ == '__main__':
    check_shoes()
