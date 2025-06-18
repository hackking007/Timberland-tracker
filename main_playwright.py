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
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
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

def get_coupon_text():
    return (
        "🎁 *קופונים רלוונטיים:*\n\n"
        "- 10% הנחה בקנייה ראשונה | קוד: FIRST10  \n  (מקור: Cashyo)\n\n"
        "- 50 ש\"ח הנחה בקנייה מעל 300 ש\"ח | קוד: TIMBER50  \n  (מקור: FreeCoupon)\n\n"
        "- 10% הנחה בהרשמה לניוזלטר | קוד: TIMBER10  \n  (מקור: Timberland.co.il)"
    )

def load_user_data():
    if not os.path.exists(USER_DATA_FILE):
        return {}
    with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_previous_state():
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_current_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def category_to_url(category, size, price):
    # מיפוי בין עברית לאנגלית
    hebrew_to_english = {
        "גברים": "men",
        "נשים": "women",
        "ילדים": "kids"
    }

    category = hebrew_to_english.get(category, category)  # אם כבר באנגלית - לא נוגעים

    base_urls = {
        "men": "https://www.timberland.co.il/men/footwear",
        "women": "https://www.timberland.co.il/women",
        "kids": "https://www.timberland.co.il/kids"
    }

    size_map = {
        "men": "794",    # לדוגמה: מידה 43
        "women": "10",   # לעדכן בהתאם
        "kids": "234"    # לעדכן בהתאם
    }

    size_code = size_map.get(category, "794")  # ברירת מחדל

    url = f"{base_urls[category]}?price={price}&size={size_code}&product_list_order=low_to_high"
    return url

def check_shoes():
    user_data = load_user_data()
    previous_state = load_previous_state()
    current_state = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="he-IL")

        for user_id, prefs in user_data.items():
            category = prefs.get("gender", "men")
            size = prefs.get("size", "43")
            price = prefs.get("price", "0-300")

            url = category_to_url(category, size, price)
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

            soup = BeautifulSoup(page.content(), "html.parser")
            cards = soup.select("div.product")

            user_key = f"{user_id}_{category}_{size}_{price}"
            current_state[user_key] = {}
            new_items, removed_items = [], []

            for card in cards:
                link_tag = card.select_one("a")
                img_tag = card.select_one("img")
                price_tags = card.select("span.price")

                title = img_tag.get("alt", "ללא שם").strip()
                link = link_tag["href"]
                if not link.startswith("http"):
                    link = "https://www.timberland.co.il" + link

                img_url = img_tag["src"]
                prices = [
                    float(tag.text.strip().replace("₪", "").replace(",", "").replace("\xa0", ""))
                    for tag in price_tags if tag.text.strip()
                ]
                if not prices:
                    continue
                min_price = min(prices)
                key = link
                current_state[user_key][key] = {
                    "title": title, "link": link, "price": min_price, "img_url": img_url
                }

                if key not in previous_state.get(user_key, {}):
                    caption = f'*{title}* - ₪{min_price}\n[לצפייה במוצר]({link})'
                    send_photo_with_caption(user_id, img_url, caption)
                    new_items.append(title)

            old_items = previous_state.get(user_key, {})
            for old_key in old_items:
                if old_key not in current_state[user_key]:
                    removed_title = old_items[old_key]["title"]
                    send_telegram_message(user_id, f"❌ הנעל '{removed_title}' כבר לא זמינה באתר.")
                    removed_items.append(removed_title)

            if not new_items and not removed_items:
                send_telegram_message(user_id, "🔄 כל הנעליים הקודמות עדיין זמינות במידה ובטווח המחירים שלך.")

            send_telegram_message(user_id, get_coupon_text())

        browser.close()
        save_current_state(current_state)

if __name__ == "__main__":
    check_shoes()
