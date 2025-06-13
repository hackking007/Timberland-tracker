import os
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']
MAX_PRICE = 300
SIZE_TO_MATCH = "43"

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
        context = browser.new_context(locale='he-IL')
        page = context.new_page()

        # גישה לעמוד המסונן לפי מידה 43 ומחיר עד 305
        page.goto("https://www.timberland.co.il/men/footwear?price=198_305&size=794", timeout=60000)

        # גלילה עד סוף הדף כדי לטעון את כל המוצרים
        previous_height = 0
        retries = 0
        while retries < 5:
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(1500)
            current_height = page.evaluate("document.body.scrollHeight")
            if current_height == previous_height:
                retries += 1
            else:
                previous_height = current_height
                retries = 0

        html = page.content()
        soup = BeautifulSoup(html, 'html.parser')
        product_cards = soup.select('div.product')

        found = []

        for card in product_cards:
            link_tag = card.select_one("a")
            img_tag = card.select_one("img")
            price_tags = card.select("span.price")

            title = img_tag['alt'].strip() if img_tag and img_tag.has_attr('alt') else "ללא שם"
            link = link_tag['href'] if link_tag and link_tag.has_attr('href') else None
            if not link:
                continue
            if not link.startswith("http"):
                link = "https://www.timberland.co.il" + link

            img_url = img_tag['src'] if img_tag and img_tag.has_attr('src') else None

            prices = []
            for tag in price_tags:
                try:
                    text = tag.text.strip().replace('\xa0', '').replace('₪', '').replace(',', '')
                    price_val = float(text)
                    if price_val > 0:
                        prices.append(price_val)
                except:
                    continue

            if not prices or min(prices) > MAX_PRICE:
                continue

            # וידוא שמידה 43 זמינה בדף המוצר
            try:
                product_page = context.new_page()
                product_page.goto(link, timeout=10000)
                product_html = product_page.content()
                if SIZE_TO_MATCH not in product_html:
                    continue
            except:
                continue

            price = min(prices)
            message = f'*{title}* - ₪{price}\n[View Product]({link})'
            if img_url:
                message += f'\n{img_url}'
            found.append(message)

        if found:
            full_message = f'👟 *Shoes with size {SIZE_TO_MATCH} under ₪{MAX_PRICE}*\n\n' + '\n\n'.join(found)
            send_telegram_message(full_message)
        else:
            send_telegram_message(f"🤷‍♂️ No matching shoes found with size {SIZE_TO_MATCH}.")

        browser.close()

if __name__ == '__main__':
    check_shoes()