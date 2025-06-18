import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
STATE_FILE = "shoes_state.json"
USER_DATA_FILE = "user_data.json"

def send_message(chat_id, text):
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

def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_coupon_text(soup):
    external_coupons = [
        "- 10% הנחה בקנייה ראשונה | קוד: FIRST10  \n  (מקור: Cashyo)",
        "- 50 ש\"ח הנחה בקנייה מעל 300 ש\"ח | קוד: TIMBER50  \n  (מקור: FreeCoupon)"
    ]

    internal_coupon = ""
    try:
        img = soup.find("img", alt=True)
        alt = img['alt']
        if "קופון" in alt or "הנחה" in alt:
            internal_coupon = f"- {alt}  \n  (מקור: Timberland.co.il)"
    except:
        pass

    combined = external_coupons
    if internal_coupon:
        combined.append(internal_coupon)

    return "🎁 *קופונים רלוונטיים:*\n\n" + '\n\n'.join(combined)

def build_url(gender, size_code, price_min, price_max):
    base = "https://www.timberland.co.il"
    if gender == "men":
        return f"{base}/men/footwear?price={price_min}_{price_max}&size={size_code}"
    elif gender == "women":
        return f"{base}/women?price={price_min}_{price_max}&size={size_code}"
    elif gender == "kids":
        return f"{base}/kids?price={price_min}_{price_max}&size={size_code}"
    return ""

def size_code_for(gender, size):
    if gender == "men":
        return "794" if size == "43" else ""
    elif gender == "women":
        return "799" if size == "37" else ""
    elif gender == "kids":
        return "234"
    return ""

def check_shoes():
    user_data = load_json(USER_DATA_FILE)
    state_data = load_json(STATE_FILE)
    updated_state = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="he-IL")
        page = context.new_page()

        for user_id, prefs in user_data.items():
            gender = prefs.get("gender")
            size = prefs.get("size")
            price = prefs.get("price", "0-300")
            price_min, price_max = price.split("-")
            size_code = size_code_for(gender, size)

            if not size_code:
                continue

            url = build_url(gender, size_code, price_min, price_max)
            page.goto(url, timeout=60000)

            # טעינת כל המוצרים
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
            soup = BeautifulSoup(html, "html.parser")
            product_cards = soup.select("div.product")

            user_items = {}
            new_items = []
            removed_items = []
            price_changed = []

            previous_user_items = state_data.get(user_id, {})

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

                if not prices or min(prices) > float(price_max):
                    continue

                price = min(prices)
                key = link

                user_items[key] = {
                    "title": title,
                    "link": link,
                    "price": price,
                    "img_url": img_url
                }

                if key not in previous_user_items:
                    caption = f'*{title}* - ₪{price}\n[View Product]({link})'
                    send_photo(user_id, img_url or "https://via.placeholder.com/300", caption)
                    new_items.append(title)
                elif previous_user_items[key]["price"] != price:
                    caption = f'*{title}*\nמחיר עודכן: ₪{previous_user_items[key]["price"]} ➜ ₪{price}\n[View Product]({link})'
                    send_photo(user_id, img_url or "https://via.placeholder.com/300", caption)
                    price_changed.append(title)

            removed_keys = set(previous_user_items.keys()) - set(user_items.keys())
            for rk in removed_keys:
                removed_title = previous_user_items[rk]["title"]
                send_message(user_id, f"❌ הנעל '{removed_title}' כבר לא רלוונטית יותר באתר.")
                removed_items.append(removed_title)

            # שליחת עדכון אם אין שינויים
            if not new_items and not removed_items and not price_changed:
                send_message(user_id, "✅ כל הנעליים ששלחנו בעבר עדיין רלוונטיות.")

            # שליחת קופונים
            send_message(user_id, get_coupon_text(soup))

            updated_state[user_id] = user_items

        browser.close()
        save_json(STATE_FILE, updated_state)

if __name__ == "__main__":
    check_shoes()
