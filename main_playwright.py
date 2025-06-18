import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# הגדרות
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

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def get_timberland_coupon():
    try:
        res = requests.get("https://www.timberland.co.il/")
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            promo = soup.select_one("div.desktop-header__promo span")
            if promo:
                return f"🛍️ *קופון מהאתר הרשמי:*\n\n{promo.get_text(strip=True)}"
    except Exception as e:
        print(f"Error fetching Timberland coupon: {e}")
    return "🛍️ *לא נמצאו קופונים מהאתר הרשמי כרגע.*"

def get_coupon_text():
    timberland_coupon = get_timberland_coupon()
    freecoupon_text = (
        "🎟️ *קופונים מתוך FreeCoupon:*\n\n"
        "- קוד: `FIRST10` – 10% הנחה בקנייה ראשונה\n"
        "- קוד: `TIMBER50` – 50 ש\"ח הנחה בקנייה מעל 300 ש\"ח\n"
    )
    return f"{timberland_coupon}\n\n{freecoupon_text}"

def category_to_url(category, size, price):
    base_urls = {
        "men": "https://www.timberland.co.il/men/footwear",
        "women": "https://www.timberland.co.il/women",
        "kids": "https://www.timberland.co.il/kids"
    }

    size_map = {
        "43": "794",
        "37": "799"
    }
    size_code = size_map.get(size, size)
    url = f"{base_urls[category]}?price={price}&size={size_code}&product_list_order=low_to_high"
    return url

def check_shoes():
    previous_state = load_state()
    current_state = {}
    found = 0

    if not os.path.exists(USER_DATA_FILE):
        print("No user_data.json found.")
        return

    with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
        user_data = json.load(f)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale='he-IL')
        page = context.new_page()

        for user_id, prefs in user_data.items():
            category = prefs.get("gender", "men")
            size = prefs.get("size", "43")
            price = prefs.get("price", "0-300")

            try:
                url = category_to_url(category, size, price)
            except KeyError:
                send_telegram_message(user_id, "⚠️ לא נמצאה קטגוריה מתאימה, ודא שהזנת גברים / נשים / ילדים באנגלית.")
                continue

            print(f"Checking URL for user {user_id}: {url}")
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
            user_current = {}

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

                user_current[key] = {
                    "title": title,
                    "link": link,
                    "price": price,
                    "img_url": img_url
                }

                prev = previous_state.get(key)
                if not prev or prev["price"] != price:
                    caption = f'*{title}* - ₪{price}\n[לינק למוצר]({link})'
                    send_photo_with_caption(user_id, img_url or "https://via.placeholder.com/300", caption)

            # בדיקת מוצרים שהוסרו
            removed = []
            for old_key in previous_state:
                if old_key.startswith(user_id) and old_key not in user_current:
                    removed_title = previous_state[old_key]["title"]
                    removed.append(removed_title)
                    send_telegram_message(user_id, f"❌ הנעל '{removed_title}' הוסרה מהאתר")

            if not user_current and not removed:
                send_telegram_message(user_id, "🔄 כל הנעליים שנשלחו בעבר עדיין רלוונטיות.")

            # שמור למצב כללי
            current_state.update(user_current)

            # שלח קופונים
            send_telegram_message(user_id, get_coupon_text())

        save_state(current_state)
        browser.close()

if __name__ == '__main__':
    check_shoes()
