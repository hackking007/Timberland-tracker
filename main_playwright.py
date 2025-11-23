import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
STATE_FILE = "shoes_state.json"
USER_DATA_FILE = "user_data.json"

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
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

# ✨ פונקציה חדשה לשליחת תמונה מקומית (Screenshot)
def send_local_photo(path, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    with open(path, "rb") as f:
        files = {"photo": f}
        data = {"chat_id": CHAT_ID, "caption": caption}
        requests.post(url, data=data, files=files)

def load_previous_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_current_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def load_user_preferences():
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def size_to_code(size):
    mapping = {
        "43": "794", "42": "793", "41": "792", "40": "791",
        "39": "790", "38": "789", "37": "799"
    }
    return mapping.get(size, "")

def category_to_url(category, size, price):
    base_urls = {
        "men": "https://www.timberland.co.il/men/footwear",
        "women": "https://www.timberland.co.il/women/%D7%94%D7%A0%D7%A2%D7%9C%D7%94",
        "kids": "https://www.timberland.co.il/kids/toddlers-0-5y"
    }
    size_code = size_to_code(size)
    if not size_code or category not in base_urls:
        return None
    return f"{base_urls[category]}?price={price.replace('-', '_')}&size={size_code}&product_list_order=low_to_high"

def check_shoes():
    previous_state = load_previous_state()
    current_state = {}
    user_data = load_user_preferences()

    if not user_data:
        send_telegram_message("⚠️ אין משתמשים רשומים.")
        return

    for user_id, prefs in user_data.items():
        category = prefs.get("gender", "men")
        size = prefs.get("size", "43")
        price = prefs.get("price", "0-300")

        url = category_to_url(category, size, price)

        debug_msg = f"🔍 *בודק למשתמש:* `{user_id}`\nקטגוריה: {category} | מידה: {size} | טווח: {price}\n\n{url}"
        send_telegram_message(debug_msg)
        print(debug_msg)

        if not url:
            send_telegram_message(f"❌ שגיאה ב-URL למשתמש `{user_id}`")
            continue

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(locale='he-IL')
            page = context.new_page()
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

            soup = BeautifulSoup(page.content(), 'html.parser')
            product_cards = soup.select('div.product')

            # ✨ אם לא נמצאו מוצרים → צלמו ושילחו Screenshot
            if not product_cards:
                screenshot_path = f"debug_{user_id}.png"
                page.screenshot(path=screenshot_path, full_page=True)
                send_local_photo(screenshot_path, "📸 *Debug Screenshot:* לא נמצאו מוצרים")
                browser.close()
                continue

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

                price_val = min(prices)
                key = f"{user_id}_{link}"
                current_state[key] = {
                    "title": title, "link": link,
                    "price": price_val, "img_url": img_url
                }

                if key not in previous_state:
                    caption = f"*{title}* - ₪{price_val}\n[לינק למוצר]({link})"
                    send_photo_with_caption(img_url or "https://via.placeholder.com/300", caption)

            browser.close()

    save_current_state(current_state)

if __name__ == "__main__":
    check_shoes()
