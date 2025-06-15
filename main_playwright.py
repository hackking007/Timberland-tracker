import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
STATE_FILE = "shoes_state.json"
USER_DATA_FILE = "user_data.json"

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

def send_photo_with_caption(chat_id, image_url, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {
        "chat_id": chat_id,
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

def build_url(category, size, price_range):
    base_urls = {
        "men": "https://www.timberland.co.il/men/footwear",
        "women": "https://www.timberland.co.il/women",
        "kids": "https://www.timberland.co.il/kids"
    }
    if category not in base_urls:
        return None

    price_range = price_range.replace(" ", "").replace("₪", "")
    return f"{base_urls[category]}?price={price_range}&size={size}&product_list_order=low_to_high"

def check_user_preferences(user_id, prefs):
    all_found_items = {}
    new_items = []
    removed_items = []
    current_state = {}
    previous_state = load_previous_state()
    chat_id = user_id

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale='he-IL')
        page = context.new_page()

        for category in prefs.get("categories", []):
            url = build_url(category, prefs["size"], prefs["price"])
            if not url:
                continue

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

                if not prices:
                    continue

                price = min(prices)
                key = f"{user_id}_{link}"
                current_state[key] = {
                    "title": title,
                    "link": link,
                    "price": price,
                    "img_url": img_url
                }

                if key not in previous_state:
                    caption = f'*{title}* - ₪{price}\n[צפייה במוצר]({link})'
                    send_photo_with_caption(chat_id, img_url or "https://via.placeholder.com/300", caption)
                    new_items.append(title)

        for key in list(previous_state.keys()):
            if key.startswith(user_id + "_") and key not in current_state:
                removed_title = previous_state[key]["title"]
                removed_items.append(removed_title)
                send_telegram_message(chat_id, f"❌ הנעל '{removed_title}' כבר לא רלוונטית יותר.")

        previous_state.update(current_state)
        save_current_state(previous_state)

        if not new_items and not removed_items:
            send_telegram_message(chat_id, "🔄 אין עדכונים. כל הנעליים שנשלחו בעבר עדיין רלוונטיות.")

        send_telegram_message(chat_id, get_coupon_text())

        browser.close()

def check_all_users():
    if not os.path.exists(USER_DATA_FILE):
        print("user_data.json לא נמצא.")
        return

    with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
        all_users = json.load(f)

    for user_id, prefs in all_users.items():
        check_user_preferences(user_id, prefs)

if __name__ == '__main__':
    check_all_users()