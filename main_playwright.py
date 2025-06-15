import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
STATE_FILE = "shoes_state.json"
USER_DATA_FILE = "user_data.json"

def send_telegram_message(text, chat_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

def send_photo_with_caption(image_url, caption, chat_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {"chat_id": chat_id, "photo": image_url, "caption": caption, "parse_mode": "Markdown"}
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

def parse_price_tag(tag):
    try:
        text = tag.text.strip().replace('\xa0', '').replace('₪', '').replace(',', '')
        return float(text)
    except:
        return None

def build_url(gender, price_range, size_code):
    gender_map = {
        "men": "https://www.timberland.co.il/men/footwear",
        "women": "https://www.timberland.co.il/women",
        "kids": "https://www.timberland.co.il/kids"
    }
    base_url = gender_map.get(gender)
    return f"{base_url}?price={price_range.replace('-', '_')}&size={size_code}"

def check_shoes():
    previous_state = load_previous_state()
    current_state = {}

    if not os.path.exists(USER_DATA_FILE):
        print("user_data.json not found.")
        return

    with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
        user_data = json.load(f)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale='he-IL')

        for user_id, prefs in user_data.items():
            gender = prefs["gender"]
            size = prefs["size"]
            price_range = prefs["price"]
            url = build_url(gender, price_range, size)
            chat_id = user_id

            page = context.new_page()
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

            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            product_cards = soup.select('div.product')

            new_items = []
            removed_items = []
            current_user_state = {}

            for card in product_cards:
                link_tag = card.select_one("a")
                img_tag = card.select_one("img")
                price_tags = card.select("span.price")

                title = img_tag['alt'].strip() if img_tag and img_tag.has_attr('alt') else "ללא שם"
                link = link_tag['href'] if link_tag and link_tag.has_attr('href') else None
                if not link or not link.startswith("http"):
                    link = "https://www.timberland.co.il" + link

                img_url = img_tag['src'] if img_tag and img_tag.has_attr('src') else None
                prices = [parse_price_tag(tag) for tag in price_tags]
                prices = [p for p in prices if p and p > 0]

                if not prices:
                    continue

                price = min(prices)
                key = f"{user_id}|{link}"
                current_user_state[key] = {
                    "title": title,
                    "link": link,
                    "price": price,
                    "img_url": img_url
                }

                if key not in previous_state:
                    caption = f'*{title}* - ₪{price}\n[לצפייה במוצר]({link})'
                    send_photo_with_caption(img_url or "https://via.placeholder.com/300", caption, chat_id)
                    new_items.append(title)

            for key in previous_state:
                if key.startswith(user_id) and key not in current_user_state:
                    removed_title = previous_state[key]["title"]
                    send_telegram_message(f"❌ הנעל '{removed_title}' כבר לא זמינה באתר.", chat_id)
                    removed_items.append(removed_title)

            if not new_items and not removed_items:
                send_telegram_message("🔄 כל הנעליים ששלחנו לך בעבר עדיין זמינות באתר.", chat_id)

            send_telegram_message(get_coupon_text(), chat_id)
            current_state.update(current_user_state)

        browser.close()
        save_current_state(current_state)

if __name__ == '__main__':
    check_shoes()