import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
STATE_FILE = "shoes_state.json"
USER_DATA_FILE = "user_data.json"

def send_telegram_message(chat_id, text):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    )

def send_photo_with_caption(chat_id, image_url, caption):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
        data={
            "chat_id": chat_id,
            "photo": image_url,
            "caption": caption,
            "parse_mode": "Markdown"
        }
    )

def get_coupon_text():
    return (
        "🎁 *קופונים רלוונטיים:*\n\n"
        "- 10% הנחה בקנייה ראשונה | קוד: FIRST10  \n  (מקור: Cashyo)\n\n"
        "- 50 ש\"ח הנחה בקנייה מעל 300 ש\"ח | קוד: TIMBER50  \n  (מקור: FreeCoupon)"
    )

def load_previous_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_current_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def load_user_data():
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def size_to_id(size_str):
    size_map = {
        "43": "794", "42": "792", "44": "796",
        "41": "790", "45": "798", "40": "788"
    }
    return size_map.get(size_str, "794")

def check_for_all_users():
    previous = load_previous_state()
    current = {}
    users = load_user_data()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale='he-IL')
        page = context.new_page()

        for uid, prefs in users.items():
            size = prefs.get("size")
            price_range = prefs.get("price", "0-300")
            chat_id = uid

            try:
                price_min, price_max = price_range.replace(" ", "").split("-")
                size_id = size_to_id(size)
                url = f"https://www.timberland.co.il/men/footwear?price={price_min}_{price_max}&size={size_id}&product_list_order=low_to_high"
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
                found_for_user = []

                for card in cards:
                    link_tag = card.select_one("a")
                    img_tag = card.select_one("img")
                    price_tags = card.select("span.price")

                    title = img_tag["alt"].strip() if img_tag else "ללא שם"
                    link = link_tag["href"] if link_tag else ""
                    if not link.startswith("http"):
                        link = "https://www.timberland.co.il" + link
                    img_url = img_tag["src"] if img_tag else ""
                    prices = []

                    for tag in price_tags:
                        try:
                            val = float(tag.text.strip().replace("₪", "").replace(",", "").replace("\xa0", ""))
                            prices.append(val)
                        except:
                            continue

                    if not prices:
                        continue

                    price = min(prices)
                    key = f"{uid}|{link}"
                    current[key] = {"title": title, "link": link, "price": price, "img_url": img_url}

                    if key not in previous:
                        caption = f"*{title}* - ₪{price}\n[לינק למוצר]({link})"
                        send_photo_with_caption(chat_id, img_url or "https://via.placeholder.com/300", caption)
                        found_for_user.append(title)
                    elif previous[key]["price"] != price:
                        caption = f"*{title}* - ₪{price} (עודכן)\n[לינק למוצר]({link})"
                        send_photo_with_caption(chat_id, img_url or "https://via.placeholder.com/300", caption)
                        found_for_user.append(title)

                if not found_for_user:
                    send_telegram_message(chat_id, "🔄 לא נמצאו נעליים חדשות או מעודכנות עבורך.")
                send_telegram_message(chat_id, get_coupon_text())

            except Exception as e:
                send_telegram_message(chat_id, f"שגיאה בבדיקה: {e}")

        save_current_state(current)
        browser.close()

if __name__ == "__main__":
    check_for_all_users()