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

def send_photo(chat_id, image_url, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {
        "chat_id": chat_id,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

def load_json(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_coupon_text():
    return (
        "🎁 *קופונים רלוונטיים:*\n\n"
        "- 10% הנחה בקנייה ראשונה | קוד: FIRST10  \n  (מקור: Cashyo)\n\n"
        "- 50 ש\"ח הנחה בקנייה מעל 300 ש\"ח | קוד: TIMBER50  \n  (מקור: FreeCoupon)"
    )

def build_url(gender, size, price):
    gender_paths = {
        "men": "men/footwear",
        "women": "women",
        "kids": "kids"
    }
    base = f"https://www.timberland.co.il/{gender_paths.get(gender, 'men')}"
    return f"{base}?price={price.replace('-', '_')}&size={size}"

def check_shoes():
    user_data = load_json(USER_DATA_FILE)
    all_state = load_json(STATE_FILE)
    new_state = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale='he-IL')

        for user_id, prefs in user_data.items():
            user_key = str(user_id)
            gender = prefs.get("gender", "men")
            size = prefs.get("size", "43")
            price = prefs.get("price", "0-300")
            max_price = int(price.split("-")[1])

            send_telegram_message(user_id, "🔍 בודק נעליים חדשות בהתאם להעדפות שלך...")

            url = build_url(gender, size, price)
            page = context.new_page()
            try:
                page.goto(url, timeout=60000)
            except:
                send_telegram_message(user_id, "⚠️ שגיאה בטעינת עמוד המוצרים.")
                continue

            while True:
                try:
                    load_more = page.query_selector("a.action.more")
                    if load_more:
                        load_more.click()
                        page.wait_for_timeout(1200)
                    else:
                        break
                except:
                    break

            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            product_cards = soup.select('div.product')

            previous = all_state.get(user_key, {})
            current = {}
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
                        prices.append(float(text))
                    except:
                        continue

                if not prices or min(prices) > max_price:
                    continue

                price_val = min(prices)
                key = link
                current[key] = {
                    "title": title,
                    "link": link,
                    "price": price_val,
                    "img_url": img_url
                }

                if key not in previous or previous[key]["price"] != price_val:
                    caption = f'*{title}* - ₪{price_val}\n[View Product]({link})'
                    send_photo(user_id, img_url or "https://via.placeholder.com/300", caption)
                    new_items.append(title)

            # מוצרים שנמחקו
            for key in previous:
                if key not in current:
                    removed_items.append(previous[key]["title"])
                    send_telegram_message(user_id, f"❌ הנעל '{previous[key]['title']}' הוסרה מהאתר")

            # אם לא השתנה כלום
            if not new_items and not removed_items:
                send_telegram_message(user_id, "🔄 כל הנעליים שנשלחו בעבר עדיין רלוונטיות.")

            # שמירת מצב אישי
            new_state[user_key] = current

            # שליחת קופונים
            send_telegram_message(user_id, get_coupon_text())

        browser.close()

    save_json(STATE_FILE, new_state)

if __name__ == '__main__':
    check_shoes()