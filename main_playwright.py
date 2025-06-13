import os
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
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    return set()

def save_current_state(keys):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(keys), f, ensure_ascii=False, indent=2)

def get_coupons_text():
    return (
        "🎁 *קופונים רלוונטיים:*\n\n"
        "- 10% הנחה בקנייה ראשונה | קוד: FIRST10  \n"
        "  (מקור: Cashyo)\n\n"
        "- 50 ש\"ח הנחה בקנייה מעל 300 ש\"ח | קוד: TIMBER50  \n"
        "  (מקור: FreeCoupon)"
    )

def check_shoes():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale='he-IL')
        page = context.new_page()
        page.goto("https://www.timberland.co.il/men/footwear?price=198_305&size=794", timeout=60000)

        # טעינת כל המוצרים
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

        current_keys = set()
        product_data = {}

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

            try:
                product_page = context.new_page()
                product_page.goto(link, timeout=60000)
                product_html = product_page.content()
                if SIZE_TO_MATCH not in product_html:
                    continue
            except:
                continue

            key = f"{title}|{link}"
            current_keys.add(key)
            product_data[key] = {
                "title": title,
                "link": link,
                "price": min(prices),
                "img_url": img_url
            }

        browser.close()

        previous_keys = load_previous_state()
        new_items = current_keys - previous_keys
        removed_items = previous_keys - current_keys

        if new_items or removed_items:
            messages = []

            for key in new_items:
                item = product_data[key]
                caption = f"*{item['title']}* - ₪{item['price']}\n[View Product]({item['link']})"
                if item["img_url"]:
                    send_photo_with_caption(item["img_url"], caption)
                else:
                    send_telegram_message(caption)

            for key in removed_items:
                title = key.split('|')[0]
                send_telegram_message(f"❌ *{title}* כבר לא זמינה יותר בסינון שלנו.")

            # שליחת קופונים בסוף
            send_telegram_message(get_coupons_text())

        else:
            send_telegram_message("✅ כל הנעליים ששלחנו בעבר עדיין זמינות ורלוונטיות.\n\n" + get_coupons_text())

        save_current_state(current_keys)

if __name__ == '__main__':
    import json
    check_shoes()