import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
MAX_PRICE = 300
SIZE_TO_MATCH = "43"
STATE_FILE = "shoes_state.json"

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

def send_photo_with_caption(image_url, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {
        "chat_id": CHAT_ID,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

def load_previous_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_current_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def get_coupon_text():
    return (
        "🎁 *קופונים רלוונטיים:*\n\n"
        "- 10% הנחה בקנייה ראשונה | קוד: FIRST10  \n  (מקור: Cashyo)\n\n"
        "- 50 ש\"ח הנחה בקנייה מעל 300 ש\"ח | קוד: TIMBER50  \n  (מקור: FreeCoupon)"
    )

def check_shoes():
    previous_state = load_previous_state()
    current_state = {}
    found = 0
    new_items = []
    removed_items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale='he-IL')
        page = context.new_page()
        page.goto("https://www.timberland.co.il/men/footwear?price=198_305&product_list_order=low_to_high&size=794", timeout=60000)

        # לחץ על "טען עוד"
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
            key = link
            current_state[key] = {
                "title": title,
                "link": link,
                "price": price,
                "img_url": img_url
            }

            if key not in previous_state:
                caption = f'*{title}* - ₪{price}\n[View Product]({link})'
                send_photo_with_caption(img_url or "https://via.placeholder.com/300", caption)
                new_items.append(title)

            found += 1

        # בדיקת מוצרים שהוסרו
        for old_key in previous_state:
            if old_key not in current_state:
                removed_title = previous_state[old_key]["title"]
                removed_items.append(removed_title)
                send_telegram_message(f"❌ הנעל '{removed_title}' כבר לא רלוונטית")

        # עדכון מצב לקובץ
        save_current_state(current_state)

        # אם לא השתנה כלום – שלח הודעת מצב
        if not new_items and not removed_items:
            send_telegram_message("🔄 *הנעליים שנשלחו בעבר עדיין רלוונטיות.*")

        # שלח קופונים תמיד
        send_telegram_message(get_coupon_text())

        browser.close()

if __name__ == '__main__':
    check_shoes()