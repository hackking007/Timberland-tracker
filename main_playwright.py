import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
USER_DATA_FILE = "user_data.json"
STATE_FILE = "shoes_state.json"

def send_telegram_message(text):
    print(f"📨 שולח טקסט:\n{text}\n")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

def send_photo_with_caption(image_url, caption):
    print(f"🖼️ שולח תמונה: {caption}")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {
        "chat_id": CHAT_ID,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

def get_coupon_text():
    return (
        "🎁 *קופונים רלוונטיים:*\n\n"
        "- 10% הנחה בקנייה ראשונה | קוד: FIRST10  \n  (מקור: Cashyo)\n\n"
        "- 50 ש\"ח הנחה בקנייה מעל 300 ש\"ח | קוד: TIMBER50  \n  (מקור: FreeCoupon)"
    )

def load_state(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        print(f"⚠️ לא נמצא קובץ {path}, משתמשים בערך ריק.")
        return {}

def save_state(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def build_url(gender, price_str, size):
    base = {
        "men": "https://www.timberland.co.il/men/footwear",
        "women": "https://www.timberland.co.il/women",
        "kids": "https://www.timberland.co.il/kids"
    }[gender]

    price_str = price_str.replace(" ", "")
    price_param = f"price={price_str.replace('-', '_')}"
    size_param = f"size={size}"
    return f"{base}?{price_param}&{size_param}&product_list_order=low_to_high"

def check_shoes():
    user_data = load_state(USER_DATA_FILE)
    if not user_data:
        print("⛔ לא קיימים משתמשים, יוצא.")
        return

    for uid, prefs in user_data.items():
        print(f"\n➡️ בודק עבור משתמש {uid}: {prefs}")
        gender = prefs.get("gender", "men")
        size = prefs.get("size", "43")
        price = prefs.get("price", "0-300")
        url = build_url(gender, price, size)

        previous_state = load_state(STATE_FILE).get(uid, {})
        current_state = {}
        new_items = []
        removed_items = []
        changed_price_items = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            print(f"🌐 גולש לכתובת: {url}")
            page.goto(url, timeout=60000)

            while True:
                try:
                    load_more = page.query_selector("a.action.more")
                    if load_more:
                        load_more.click()
                        page.wait_for_timeout(1000)
                    else:
                        break
                except:
                    break

            soup = BeautifulSoup(page.content(), 'html.parser')
            cards = soup.select("div.product")

            for card in cards:
                link_tag = card.select_one("a")
                img_tag = card.select_one("img")
                price_tags = card.select("span.price")

                title = img_tag['alt'].strip() if img_tag else "לא זוהה שם"
                link = link_tag['href'] if link_tag else ""
                if not link.startswith("http"):
                    link = "https://www.timberland.co.il" + link
                img_url = img_tag['src'] if img_tag else ""

                prices = []
                for tag in price_tags:
                    try:
                        prices.append(float(tag.text.strip().replace('₪', '').replace(',', '').replace('\xa0', '')))
                    except:
                        continue

                if not prices:
                    continue

                price_val = min(prices)
                key = link
                current_state[key] = {
                    "title": title,
                    "price": price_val,
                    "img_url": img_url,
                    "link": link
                }

                if key not in previous_state:
                    caption = f"*{title}* - ₪{price_val}\n[לצפייה במוצר]({link})"
                    send_photo_with_caption(img_url or "https://via.placeholder.com/300", caption)
                    new_items.append(title)
                elif previous_state[key]["price"] != price_val:
                    caption = f"*{title}*\n🔻 מחיר עודכן: ₪{previous_state[key]['price']} → ₪{price_val}\n[לצפייה במוצר]({link})"
                    send_photo_with_caption(img_url or "https://via.placeholder.com/300", caption)
                    changed_price_items.append(title)

            for key in previous_state:
                if key not in current_state:
                    removed_title = previous_state[key]["title"]
                    send_telegram_message(f"❌ הנעל '{removed_title}' הוסרה מהאתר.")
                    removed_items.append(removed_title)

            # שמירת מצב לכל משתמש
            all_states = load_state(STATE_FILE)
            all_states[uid] = current_state
            save_state(STATE_FILE, all_states)

            if not new_items and not removed_items and not changed_price_items:
                send_telegram_message("🔄 כל הנעליים שנשלחו עדיין רלוונטיות.")

            send_telegram_message(get_coupon_text())
            browser.close()

if __name__ == '__main__':
    check_shoes()