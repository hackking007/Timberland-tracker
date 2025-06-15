import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
STATE_FILE = "shoes_state.json"
USER_DATA_FILE = "user_data.json"
SIZE_MAP_FILE = "size_map.json"

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

def load_json_file(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_json_file(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_coupon_text():
    return (
        "🎁 *קופונים רלוונטיים:*\n\n"
        "- 10% הנחה בקנייה ראשונה | קוד: FIRST10  \n  (מקור: Cashyo)\n\n"
        "- 50 ש\"ח הנחה בקנייה מעל 300 ש\"ח | קוד: TIMBER50  \n  (מקור: FreeCoupon)"
    )

def get_category_url(gender, size_id, price_range):
    base_urls = {
        "men": "https://www.timberland.co.il/men/footwear",
        "women": "https://www.timberland.co.il/women",
        "kids": "https://www.timberland.co.il/kids"
    }
    return f"{base_urls[gender]}?price={price_range.replace('-', '_')}&size={size_id}&product_list_order=low_to_high"

def check_shoes():
    users = load_json_file(USER_DATA_FILE)
    size_map = load_json_file(SIZE_MAP_FILE)
    state = load_json_file(STATE_FILE)

    new_state = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale='he-IL')
        page = context.new_page()

        for chat_id, prefs in users.items():
            gender = prefs["gender"]
            size = prefs["size"]
            price_range = prefs["price"]

            size_id = str(size_map.get(gender, {}).get(size))
            if not size_id:
                send_telegram_message(chat_id, f"⚠️ לא נמצא מזהה למידה {size} בקטגוריה {gender}.")
                continue

            url = get_category_url(gender, size_id, price_range)
            page.goto(url, timeout=60000)

            # טען את כל המוצרים
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
            cards = soup.select('div.product')
            found_urls = {}

            for card in cards:
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
                        val = float(tag.text.replace("₪", "").replace(",", "").strip())
                        prices.append(val)
                    except:
                        continue

                if not prices:
                    continue

                price = min(prices)
                found_urls[link] = {
                    "title": title,
                    "link": link,
                    "price": price,
                    "img_url": img_url
                }

            # בדיקת שינויים
            prev = state.get(chat_id, {})
            curr = found_urls
            new_items = [k for k in curr if k not in prev]
            removed_items = [k for k in prev if k not in curr]

            for k in new_items:
                data = curr[k]
                caption = f"*{data['title']}* - ₪{data['price']}\n[צפייה במוצר]({data['link']})"
                send_photo_with_caption(chat_id, data['img_url'] or "https://via.placeholder.com/300", caption)

            for k in removed_items:
                data = prev[k]
                send_telegram_message(chat_id, f"❌ הנעל '{data['title']}' כבר לא זמינה בטווח המחירים או המידה שלך.")

            if not new_items and not removed_items:
                send_telegram_message(chat_id, "🔁 כל הנעליים ששלחנו לך בעבר עדיין זמינות.")

            send_telegram_message(chat_id, get_coupon_text())
            new_state[chat_id] = curr

        browser.close()
        save_json_file(STATE_FILE, new_state)

if __name__ == "__main__":
    check_shoes()