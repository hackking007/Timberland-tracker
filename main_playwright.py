import os
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']
MAX_PRICE = 299

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
        context = browser.new_context(
            locale='he-IL',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        page.goto('https://www.timberland.co.il/men/footwear', timeout=60000)

        for _ in range(5):
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(1000)

        page.screenshot(path="screenshot.png", full_page=True)
        html = page.content()

        with open("after_scroll.html", "w", encoding="utf-8") as f:
            f.write(html)

        browser.close()

    soup = BeautifulSoup(html, 'html.parser')
    found = []

    for product in soup.select('div.product'):
        price_tag = product.select_one("span.price")
        link_tag = product.select_one("a")
        img_tag = product.select_one("img")

        title = img_tag['alt'].strip() if img_tag and img_tag.has_attr('alt') else "No title"
        price_text = price_tag.text.strip() if price_tag else None
        link = link_tag['href'] if link_tag and link_tag.has_attr('href') else "#"

        try:
            price = float(price_text.replace('₪', '').replace(',', '').strip())
        except:
            continue

        if price < MAX_PRICE:
            found.append(f'*{title}*\\n₪{price} - [View Product]({link})')

    if found:
        message = f'👟 *Shoes under ₪{MAX_PRICE}*\n\n' + '\n\n'.join(found)
        send_telegram_message(message)
    else:
        send_telegram_message("🤷‍♂️ No matching shoes found.")

if __name__ == '__main__':
    check_shoes()
