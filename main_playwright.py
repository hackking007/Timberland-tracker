import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# בדיקה - האם משתני סביבה קיימים
print("TELEGRAM_TOKEN found:", "TELEGRAM_TOKEN" in os.environ)
print("CHAT_ID found:", "CHAT_ID" in os.environ)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
STATE_FILE = "shoes_state.json"
USER_DATA_FILE = "user_data.json"
SIZE_MAP_FILE = "size_map.json"

# שליחת הודעה לטלגרם
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
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

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_coupon_text():
    coupons = [
        "- 10% הנחה בקנייה ראשונה | קוד: FIRST10  \n  (מקור: Cashyo)",
        "- 50 ש\"ח הנחה בקנייה מעל 300 ש\"ח | קוד: TIMBER50  \n  (מקור: FreeCoupon)"
    ]
    # קופון מתוך האתר (אם נרצה להוסיף בהמשך)
    try:
        r = requests.get("https://www.timberland.co.il")
        if "EXTRA15" in r.text:
            coupons.append("- 15% הנחה עם קוד EXTRA15  \n  (מקור: אתר טימברלנד)")
    except:
        pass
    return "🎁 *קופונים רלוונטיים:*\n\n" + "\n\n".join(coupons)

def category_to_url(category, size, price):
    base_urls = {
        "men": "https://www.timberland.co.il/men/footwear",
        "women": "https://www.timberland.co.il/women",
        "kids": "https://www.timberland.co.il/kids",
    }
    size_map = load_json(SIZE_MAP_FILE)
    size_code = size_map.get(size, "")
    url = f"{base_urls[category]}?price={price}&size={size_code}&product_list_order=low_to_high"
    return url

def check_shoes():
    state = load_json(STATE_FILE)
    users = load_json(USER_DATA_FILE)
    new_state = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale='he-IL')
        page = context.new_page()

        for user_id, prefs in users.items():
            category = prefs["gender"]
            size = prefs["size"]
            price = prefs["price"]

            url = category_to_url(category, size, price)
            print("🔗", url)
            page.goto(url, timeout=60000)

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
            user_new = {}

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
                user_new[key] = {
                    "title": title,
                    "link": link,
                    "price": price,
                    "img_url": img_url
                }

                if key not in state.get(user_id, {}):
                    caption = f'*{title}* - ₪{price}\n[קישור למוצר]({link})'
                    send_photo_with_caption(img_url or "https://via.placeholder.com/300", caption)

            # בדיקת נעליים שהוסרו
            removed = []
            for old_key in state.get(user_id, {}):
                if old_key not in user_new:
                    removed.append(state[user_id][old_key]["title"])
                    send_telegram_message(f"❌ הנעל '{state[user_id][old_key]['title']}' הוסרה מהאתר")

            if not user_new and not removed:
                send_telegram_message("🔄 כל הנעליים שנשלחו בעבר עדיין זמינות באתר.")

            new_state[user_id] = user_new

        browser.close()

    save_json(STATE_FILE, new_state)
    send_telegram_message(get_coupon_text())

if __name__ == '__main__':
    check_shoes()