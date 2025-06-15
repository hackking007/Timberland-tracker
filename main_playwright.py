import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
STATE_FILE = "shoes_state.json"
USER_DATA_FILE = "user_data.json"

# שליחת הודעת טקסט
def send_telegram_message(chat_id, text):
    print(f"📤 שולח הודעה ל- {chat_id}")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

# שליחת תמונה עם כיתוב
def send_photo_with_caption(chat_id, image_url, caption):
    print(f"🖼️ שולח תמונה ל- {chat_id}")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {
        "chat_id": chat_id,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

# טעינת מצב קודם
def load_previous_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# שמירת מצב נוכחי
def save_current_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# טעינת העדפות משתמשים
def load_user_data():
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("⚠️ לא נמצא user_data.json")
        return {}

# קופונים
def get_coupon_text():
    return (
        "🎁 *קופונים רלוונטיים:*\n\n"
        "- 10% הנחה בקנייה ראשונה | קוד: FIRST10  \n  (מקור: Cashyo)\n\n"
        "- 50 ש\"ח הנחה בקנייה מעל 300 ש\"ח | קוד: TIMBER50  \n  (מקור: FreeCoupon)"
    )

def build_url(gender, price_range, size):
    price_from, price_to = price_range.split("-")
    if gender == "men":
        return f"https://www.timberland.co.il/men/footwear?price={price_from}_{price_to}&size=794"
    elif gender == "women":
        return f"https://www.timberland.co.il/women?price={price_from}_{price_to}&size=10"
    elif gender == "kids":
        return f"https://www.timberland.co.il/kids?price={price_from}_{price_to}&size=234"
    return None

def check_shoes():
    print("▶️ התחלת ריצה")
    user_data = load_user_data()
    print("📂 תוכן user_data.json:", user_data)

    previous_state = load_previous_state()
    current_state = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale='he-IL')
        page = context.new_page()

        for user_id, prefs in user_data.items():
            print(f"👤 בודק את המשתמש {user_id} עם העדפות {prefs}")
            gender = prefs.get("gender")
            size = prefs.get("size")
            price_range = prefs.get("price")

            url = build_url(gender, price_range, size)
            if not url:
                print(f"⚠️ לא נבנה URL תקין עבור {user_id}")
                continue

            print(f"🌐 גולש לכתובת: {url}")
            try:
                page.goto(url, timeout=60000)
            except Exception as e:
                print(f"❌ שגיאה בטעינת דף: {e}")
                continue

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

            user_found_items = {}
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

                if not prices or min(prices) > float(price_range.split("-")[1]):
                    continue

                price = min(prices)
                key = f"{user_id}|{link}"
                user_found_items[key] = {
                    "title": title,
                    "link": link,
                    "price": price,
                    "img_url": img_url
                }

                if key not in previous_state:
                    caption = f'*{title}* - ₪{price}\n[לצפייה במוצר]({link})'
                    send_photo_with_caption(user_id, img_url or "https://via.placeholder.com/300", caption)
                    new_items.append(title)

            # נעליים שהוסרו
            for key in previous_state:
                if key.startswith(f"{user_id}|") and key not in user_found_items:
                    removed_title = previous_state[key]["title"]
                    send_telegram_message(user_id, f"❌ הנעל '{removed_title}' כבר לא רלוונטית")
                    removed_items.append(removed_title)

            # עדכון סטייט כולל
            current_state.update(user_found_items)

            if not new_items and not removed_items:
                send_telegram_message(user_id, "🔄 כל הנעליים שנשלחו בעבר עדיין רלוונטיות.")
            
            send_telegram_message(user_id, get_coupon_text())

        save_current_state(current_state)
        browser.close()

    print("✅ סיום ריצה")

if __name__ == '__main__':
    check_shoes()