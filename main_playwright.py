
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
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto('https://www.timberland.co.il/men/footwear', timeout=60000)
        page.wait_for_selector('.product-item-info', timeout=60000)
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

        # Fetch product detail page to get sizes
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            detail_page = browser.new_page()
            detail_page.goto(link, timeout=60000)
            detail_page.wait_for_selector('.swatch-option.text', timeout=60000)
            detail_html = detail_page.content()
            browser.close()

        detail_soup = BeautifulSoup(detail_html, 'html.parser')
        size_buttons = detail_soup.select('.swatch-attribute-options .swatch-option.text')
        sizes = [btn.text.strip() for btn in size_buttons]

        if SIZE in sizes and price < MAX_PRICE:
            found.append(f'*{title}*\n₪{price} - [View Product]({link})')

    if found:
        message = f'👟 *Shoes Found ({SIZE}) under ₪{MAX_PRICE}*\n\n' + '\n\n'.join(found)
        send_telegram_message(message)
    else:
        send_telegram_message("🤷‍♂️ No matching shoes found at this time.")

if __name__ == '__main__':
    check_shoes()
