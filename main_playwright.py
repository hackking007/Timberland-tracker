import os
import re
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']
MAX_PRICE = 300
SIZE_TEXT = "43"

def send_telegram_message(message: str):
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
        page.goto('https://www.timberland.co.il/men?size=794', timeout=60000)

        # גלילה עד שלא מתווספים יותר מוצרים (או מקסימום 50 נסיונות)
        previous_height = 0
        same_count = 0
        for _ in range(50):
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(2000)
            current_height = page.evaluate("document.body.scrollHeight")
            if current_height == previous_height:
                same_count += 1
                if same_count >= 3:
                    break
            else:
                same_count = 0
                previous_height = current_height

        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, 'html.parser')
    found = []

    for product in soup.select('div.product'):
        link_tag = product.select_one("a")
        img_tag = product.select_one("img")
        price_tags = product.select("span.price")

        title = img_tag['alt'].strip() if img_tag and img_tag.has_attr('alt') else "ללא שם"
        link = link_tag['href'] if link_tag and link_tag.has_attr('href') else "#"
        img_url = img_tag['src'] if img_tag and img_tag.has_attr('src') else None

        prices = []
        for tag in price_tags:
            try:
                text = re.sub(r'[^\d.]', '', tag.text)
                price_val = float(text)
                if price_val > 0:
                    prices.append(price_val)
            except:
                continue

        if not prices:
            continue

        price = min(prices)

        # תנאי סינון מחיר בלבד (אין לנו את המידע על המידות ישירות בדף הזה)
        if price <= MAX_PRICE:
            message = f'*{title}* - ₪{price}\n[View Product]({link})'
            if img_url:
                message += f'\n{img_url}'
            found.append(message)

    if found:
        full_message = f'👟 *Shoes with size {SIZE_TEXT} under ₪{MAX_PRICE}*\n\n' + '\n\n'.join(found)
        send_telegram_message(full_message)
    else:
        send_telegram_message(f"🤷‍♂️ No matching shoes found with size {SIZE_TEXT}.")

if __name__ == '__main__':
    check_shoes()
