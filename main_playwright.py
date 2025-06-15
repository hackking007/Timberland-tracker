import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

USER_DATA_FILE = "user_data.json"
STATE_FILE = "shoes_state.json"
SIZE_MAP_FILE = "size_map.json"
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

def send_photo_with_caption(chat_id, image_url, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {"chat_id": chat_id, "photo": image_url, "caption": caption, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

def get_coupon_text():
    return (
        "🎁 *קופונים רלוונטיים:*\n\n"
        "- 10% הנחה בקנייה ראשונה | קוד: FIRST10  \n  (מקור: Cashyo)\n\n"
        "- 50 ש\"ח הנחה בקנייה מעל 300 ש\"ח | קוד: TIMBER50  \n  (מקור: FreeCoupon)"
    )

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def parse_price(text):
    text = text.replace('\xa0', '').replace('₪', '').replace(',', '').strip()
    try:
        return float(text)
    except:
        return None

def build_url(gender, size, price_range):
    gender_path = {
        "men": "men/footwear",
        "women": "women",
        "kids": "kids"
    }[gender]
    return f"https://www.timberland.co.il/{gender_path}?price={price_range.replace('-', '_')}&size={size}"

def check_shoes():
    user_data = load_json(USER_DATA_FILE)
    all_states = load_json(STATE_FILE)
    size_map = load_json(SIZE_MAP_FILE)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale='he-IL')
        page = context.new_page()

        for user_id, prefs in user_data.items():
            gender = prefs.get("gender")
            size = prefs.get("size")
            price_range = prefs.get("price")
            size_code = size_map.get(size)

            if not (gender and size_code and price_range):
                continue

            url = build_url(gender, size_code, price_range)
            page.goto(url, timeout=60000)

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

            soup = BeautifulSoup(page.content(), 'html.parser')
            product_cards = soup.select('div.product')
            current_state = {}
            previous_state = all_states.get(user_id, {})
            new_items = []
            removed_items = []

            for card in product_cards:
                link_tag = card.select_one("a")
                img_tag = card.select_one("img")
                price_tags = card.select("span.price")

                title = img_tag['alt'].strip() if img_tag and img_tag.has_attr('alt') else "ללא שם"
                link = link_tag['href'] if link_tag and link_tag.has_attr('href') else None
                img_url = img_tag['src'] if img_tag and img_tag.has_attr('src') else None
                if not link:
                    continue
                if not link.startswith("http"):
                    link = "https://www.timberland.co.il" + link

                prices = [parse_price(tag.text) for tag in price_tags]
                prices = [p for p in prices if p is not None and p > 0]

                if not prices:
                    continue

                price = min(prices)
                current_state[link] = {
                    "title": title,
                    "link": link,
                    "price": price,
                    "img_url": img_url
                }

                if link not in previous_state:
                    caption = f'*{title}* - ₪{price}\n[צפייה במוצר]({link})'
                    send_photo_with_caption(user_id, img_url or "https://via.placeholder.com/300", caption)
                    new_items.append(link)

            for old_link in previous_state:
                if old_link not in current_state:
                    removed_items.append(old_link)
                    title = previous_state[old_link]["title"]
                    send_telegram_message(user_id, f"❌ הנעל '{title}' כבר לא זמינה במידה או במחיר שביקשת.")

            if not new_items and not removed_items:
                send_telegram_message(user_id, "🔄 כל הנעליים ששלחנו לך בעבר עדיין זמינות באתר.")

            send_telegram_message(user_id, get_coupon_text())
            all_states[user_id] = current_state

        save_json(STATE_FILE, all_states)
        browser.close()

if __name__ == '__main__':
    check_shoes()