import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

USER_DATA_FILE = "user_data.json"
STATE_FILE = "shoes_state.json"

# שליחת הודעה
def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

# שליחת תמונה עם כיתוב
def send_photo_with_caption(chat_id, image_url, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {
        "chat_id": chat_id,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

# טען את הגדרות המשתמש
def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# טען את מצב ההיסטוריה של הנעליים
def load_previous_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# שמור את המצב החדש
def save_current_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# טקסט קופונים
def get_coupon_text():
    return (
        "🎁 *קופונים רלוונטיים:*\n\n"
        "- 10% הנחה בקנייה ראשונה | קוד: FIRST10  \n  (מקור: Cashyo)\n\n"
        "- 50 ש\"ח הנחה בקנייה מעל 300 ש\"ח | קוד: TIMBER50  \n  (מקור: FreeCoupon)"
    )

# צור URL מותאם לפי העדפות
def build_url(gender, price_range, size):
    base = {
        "men": "https://www.timberland.co.il/men/footwear",
        "women": "https://www.timberland.co.il/women",
        "kids": "https://www.timberland.co.il/kids"
    }[gender]

    size_code = {
        "men": "794",  # מידה 43
        "women": "10",  # לדוגמה
        "kids": "234"   # לדוגמה
    }[gender]

    return f"{base}?price={price_range.replace('-', '_')}&size={size_code}&product_list_order=low_to_high"

# פונקציית הבדיקה הראשית
def check_shoes():
    user_data = load_user_data()
    previous_state = load_previous_state()
    current_state = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale='he-IL')

        for user_id, prefs in user_data.items():
            gender = prefs.get("gender", "men")  # ברירת מחדל: גברים
            price_range = prefs.get("price", "0-300")
            size = prefs.get("size", "43")
            chat_id = int(user_id)

            url = build_url(gender, price_range, size)
            page = context.new_page()
            try:
                page.goto(url, timeout=60000)
            except:
                send_telegram_message(chat_id, "⚠️ לא הצלחנו לטעון את האתר.")
                continue

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

            current_user_state = {}
            previous_user_state = previous_state.get(user_id, {})
            new_items = []
            removed_items = []

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
                key = link
                current_user_state[key] = {
                    "title": title,
                    "link": link,
                    "price": price,
                    "img_url": img_url
                }

                # חדש או שינוי במחיר
                if key not in previous_user_state or previous_user_state[key]["price"] != price:
                    caption = f'*{title}* - ₪{price}\n[View Product]({link})'
                    send_photo_with_caption(chat_id, img_url or "https://via.placeholder.com/300", caption)
                    new_items.append(title)

            # נעליים שנמחקו
            for old_key in previous_user_state:
                if old_key not in current_user_state:
                    removed_items.append(previous_user_state[old_key]["title"])
                    send_telegram_message(chat_id, f"❌ הנעל '{previous_user_state[old_key]['title']}' כבר לא זמינה.")

            # אם לא השתנה כלום
            if not new_items and not removed_items:
                send_telegram_message(chat_id, "🔄 הנעליים שנשלחו בעבר עדיין רלוונטיות.")

            # קופונים
            send_telegram_message(chat_id, get_coupon_text())

            # שמור למצב כולל
            current_state[user_id] = current_user_state

        save_current_state(current_state)
        browser.close()

if __name__ == '__main__':
    check_shoes()