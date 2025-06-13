import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']
MAX_PRICE = 300
SIZE_TO_MATCH = "43"

STATE_DIR = ".data"
STATE_FILE = os.path.join(STATE_DIR, "shoes_state.json")

def send_photo_with_caption(image_url, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {
        "chat_id": CHAT_ID,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

def send_text_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

def load_previous_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_current_state(state):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def check_shoes():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale='he-IL')
        page = context.new_page()
        page.goto("https://www.timberland.co.il/men/footwear?price=198_305&product_list_order=low_to_high&size=794", timeout=60000)

        while True:
            try:
                load_more = page.query_selector("a.action.more")
                if load_more:
                    load_more.click()
                    page.wait_for_timeout(1500)
                else:
                    break
            except:
                break

        html = page.content()
        soup = BeautifulSoup(html, 'html.parser')
        product_cards = soup.select('div.product')

        current_items = {}

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

            price = min(prices)

            product_page = context.new_page()
            product_page.goto(link, timeout=30000)
            product_html = product_page.content()
            if SIZE_TO_MATCH not in product_html:
                continue

            key = f"{title}|{link}"
            current_items[key] = {
                'title': title,
                'price': price,
                'link': link,
                'img_url': img_url
            }

        browser.close()

        previous_state = load_previous_state()
        new_keys = set(current_items.keys()) - set(previous_state.keys())
        removed_keys = set(previous_state.keys()) - set(current_items.keys())
        price_changed = [
            key for key in current_items if key in previous_state and current_items[key]['price'] != previous_state[key]['price']
        ]

        if new_keys or removed_keys or price_changed:
            for key in new_keys:
                item = current_items[key]
                send_photo_with_caption(item['img_url'], f"🆕 *{item['title']}* - ₪{item['price']}\n[View Product]({item['link']})")

            for key in price_changed:
                item = current_items[key]
                old_price = previous_state[key]['price']
                send_photo_with_caption(item['img_url'], f"🔄 *{item['title']}*\nמחיר השתנה: ₪{old_price} ➜ ₪{item['price']}\n[View Product]({item['link']})")

            for key in removed_keys:
                item = previous_state[key]
                send_text_message(f"❌ *{item['title']}* כבר לא זמינה\n[View Product]({item['link']})")
        else:
            send_text_message("✅ הנעליים ששלחנו בעבר עדיין זמינות ורלוונטיות.")

        save_current_state(current_items)

if __name__ == '__main__':
    check_shoes()