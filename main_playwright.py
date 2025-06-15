import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

USER_DATA_FILE = "user_data.json"
STATE_FILE = "shoes_state.json"
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

CATEGORY_MAP = {
    "גברים": ("men/footwear", "794"),
    "נשים": ("women", "10"),
    "ילדים": ("kids", "234")
}

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    })

def send_photo_with_caption(chat_id, img_url, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    requests.post(url, data={
        "chat_id": chat_id,
        "photo": img_url,
        "caption": caption,
        "parse_mode": "Markdown"
    })

def load_json_file(path):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}

def save_json_file(data, path):
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def build_url(gender, size, price_range):
    path, size_param = CATEGORY_MAP[gender]
    return f"https://www.timberland.co.il/{path}?price={price_range.replace('-', '_')}&size={size_param}"

def get_coupon_text():
    return (
        "🎁 *קופונים רלוונטיים:*\n\n"
        "- 10% הנחה בקנייה ראשונה | קוד: FIRST10  \n  (מקור: Cashyo)\n\n"
        "- 50 ש\"ח הנחה בקנייה מעל 300 ש\"ח | קוד: TIMBER50  \n  (מקור: FreeCoupon)"
    )

def check_shoes():
    user_data = load_json_file(USER_DATA_FILE)
    previous_state = load_json_file(STATE_FILE)
    current_state = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="he-IL")

        for user_id, prefs in user_data.items():
            gender = prefs["gender"]
            size = prefs["size"]
            price_range = prefs["price"]
            url = build_url(gender, size, price_range)

            page = context.new_page()
            page.goto(url, timeout=60000)

            while True:
                try:
                    btn = page.query_selector("a.action.more")
                    if btn:
                        btn.click()
                        page.wait_for_timeout(1200)
                    else:
                        break
                except:
                    break

            soup = BeautifulSoup(page.content(), 'html.parser')
            cards = soup.select("div.product")
            user_items = {}

            for card in cards:
                try:
                    title = card.select_one("img")["alt"].strip()
                    img = card.select_one("img")["src"]
                    link = card.select_one("a")["href"]
                    if not link.startswith("http"):
                        link = "https://www.timberland.co.il" + link
                    price_tags = card.select("span.price")
                    prices = [float(t.text.replace("₪", "").replace(',', '').strip()) for t in price_tags if t.text.strip()]
                    price = min(prices)
                    if price > float(price_range.split("-")[1]):
                        continue

                    # בדיקת מידה
                    prod_page = context.new_page()
                    prod_page.goto(link, timeout=30000)
                    if size not in prod_page.content():
                        continue

                    user_items[link] = {"title": title, "link": link, "price": price, "img_url": img}

                except:
                    continue

            prev_items = previous_state.get(user_id, {})
            new_keys = set(user_items) - set(prev_items)
            removed_keys = set(prev_items) - set(user_items)
            changed_keys = [k for k in user_items if k in prev_items and user_items[k]["price"] != prev_items[k]["price"]]

            if not new_keys and not removed_keys and not changed_keys:
                send_telegram_message(user_id, "✅ כל הנעליים ששלחנו בעבר עדיין רלוונטיות.")
            else:
                for key in new_keys:
                    item = user_items[key]
                    send_photo_with_caption(user_id, item["img_url"], f"🆕 *{item['title']}* - ₪{item['price']}\n[לצפייה]({item['link']})")

                for key in changed_keys:
                    item = user_items[key]
                    old_price = prev_items[key]["price"]
                    send_photo_with_caption(user_id, item["img_url"], f"🔄 *{item['title']}* עודכן מ־₪{old_price} ל־₪{item['price']}\n[לצפייה]({item['link']})")

                for key in removed_keys:
                    item = prev_items[key]
                    send_telegram_message(user_id, f"❌ *{item['title']}* הוסרה או אזלה מהמלאי.\n[לצפייה]({item['link']})")

                send_telegram_message(user_id, get_coupon_text())

            current_state[user_id] = user_items

        browser.close()
        save_json_file(current_state, STATE_FILE)

if __name__ == '__main__':
    check_shoes()