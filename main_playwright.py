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
        page.goto("https://www.timberland.co.il/men?size=794", timeout=60000)

        # גלילה עד שכל הכרטיסים נטענו
        prev_count = 0
        same_count_retries = 0

        while same_count_retries < 5:
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(2000)
            current_html = page.content()
            soup = BeautifulSoup(current_html, 'html.parser')
            products = soup.select('div.product')
            if len(products) == prev_count:
                same_count_retries += 1
            else:
                prev_count = len(products)
                same_count_retries = 0

        with open("after_scroll.html", "w", encoding="utf-8") as f:
            f.write(current_html)

        page.screenshot(path="screenshot.png", full_page=True)

        found = []

        for card in products:
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

            # בדיקת זמינות מידה 43
            product_page = context.new_page()
            product_page.goto(link, timeout=30000)
            product_html = product_page.content()
            if SIZE_TO_MATCH not in product_html:
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