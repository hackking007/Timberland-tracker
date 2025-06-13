import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']
MAX_PRICE = 300
SIZE_TO_MATCH = "43"
STATE_FILE = "shoes_state.json"

def send_telegram_message(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    requests.post(url, data=payload)

def load_previous_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_current_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def check_shoes():
    previous_state = load_previous_state()
    current_state = {}

    new_items = []
    removed_items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale='he-IL')
        page = context.new_page()

        url = "https://www.timberland.co.il/men/footwear?price=10_305&product_list_order=low_to_high&size=794"
        page.goto(url, timeout=60000)

        previous_height = 0
        retries = 0
        while retries < 5:
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(1500)
            current_height = page.evaluate("document.body.scrollHeight")
            if current_height == previous_height:
                retries += 1
            else:
                retries = 0
                previous_height = current_height

        soup = BeautifulSoup(page.content(), 'html.parser')
        product_cards = soup.select('div.product')

        for card in product_cards:
            link_tag = card.select_one("a")
            img_tag = card.select_one("img")
            price_tags = card.select("span.price")

            if not link_tag or not link_tag.has_attr("href"):
                continue

            link = link_tag['href']
            if not link.startswith("http"):
                link = "https://www.timberland.co.il" + link

            title = img_tag['alt'].strip() if img_tag and img_tag.has_attr('alt') else "ללא שם"
            image_url = img_tag['src'] if img_tag and img_tag.has_attr('src') else None

            prices = []
            for tag in price_tags:
                try:
                    text = tag.text.strip().replace('\xa0', '').replace('₪', '').replace(',', '')
                    price_val = float(text)
                    if price_val > 0:
                        prices.append(price_val)
                except:
                    continue

            if not prices:
                continue

            price = min(prices)
            product_id = link.split("/")[-1]

            if price <= MAX_PRICE:
                current_state[product_id] = {
                    "title": title,
                    "price": price,
                    "url": link,
                    "img": image_url
                }

                if product_id not in previous_state:
                    new_items.append(current_state[product_id])

        for old_id in previous_state:
            if old_id not in current_state:
                removed_items.append(previous_state[old_id])

        browser.close()

    messages = []

    if new_items:
        for item in new_items:
            m = f'*{item["title"]}* - ₪{item["price"]}\n[View Product]({item["url"]})'
            if item["img"]:
                m += f'\n{item["img"]}'
            messages.append(m)

    if removed_items:
        for item in removed_items:
            m = f'❌ *Removed:* {item["title"]}\n{item["url"]}'
            messages.append(m)

    if messages:
        full_message = f'👟 *Shoes with size {SIZE_TO_MATCH} under ₪{MAX_PRICE}*\n\n' + '\n\n'.join(messages)
        send_telegram_message(full_message)
    else:
        send_telegram_message(f"🤷‍♂️ No new changes found for shoes with size {SIZE_TO_MATCH}.")

    save_current_state(current_state)

if __name__ == "__main__":
    check_shoes()