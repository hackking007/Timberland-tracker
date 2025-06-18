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
    payload = {"chat_id": CHAT_ID, "photo": image_url, "caption": caption, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

def load_previous_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_current_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def get_coupon_text():
    try:
        url = "https://promocode.co.il/coupon-store/timberland/"
        res = requests.get(url, timeout=30)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        coupons = []
        for item in soup.select(".coupon-item"):
            title = item.select_one(".coupon-title")
            code = item.select_one(".coupon-code")

            if title and code:
                title_text = title.get_text(strip=True)
                code_text = code.get_text(strip=True)
                coupons.append(f"- {title_text} | קוד: `{code_text}`")

        if coupons:
            return "🎁 *קופונים רלוונטיים מהאתר:*\n\n" + "\n".join(coupons)
        else:
            return "🎁 לא נמצאו קופונים אקטואליים באתר Promocode."

    except Exception as e:
        return f"⚠️ שגיאה בקבלת קופונים: {e}"

def category_to_url(category, size, price):
    base_urls = {
        "men": "https://www.timberland.co.il/men/footwear",
        "women": "https://www.timberland.co.il/women",
        "kids": "https://www.timberland.co.il/kids"
    }

    size_map = {
        "men": {
            "43": "794",
            "42": "793",
            "41": "792",
        },
        "women": {
            "37": "799",
            "38": "800",
        },
        "kids": {
            "31": "234",
            "32": "235"
        }
    }

    size_code = size_map.get(category, {}).get(size)
    if not size_code:
        raise ValueError(f"Size {size} לא נתמכת עבור קטגוריה {category}")

    url = f"{base_urls[category]}?price={price}&size={size_code}&product_list_order=low_to_high"
    return url

def check_shoes():
    previous_state = load_previous_state()
    current_state = {}
    new_items = []
    removed_items = []

    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            user_data = json.load(f)
    except FileNotFoundError:
        send_telegram_message("⚠️ לא נמצאו העדפות משתמש בקובץ user_data.json")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale='he-IL')
        page = context.new_page()

        for user_id, prefs in user_data.items():
            category = prefs["gender"]
            size = prefs["size"]
            price = prefs["price"]

            try:
                url = category_to_url(category, size, price)
            except Exception as e:
                send_telegram_message(f"שגיאה עבור משתמש {user_id}: {e}")
                continue

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

                product_price = min(prices)
                key = f"{user_id}_{link}"
                current_state[key] = {
                    "title": title,
                    "link": link,
                    "price": product_price,
                    "img_url": img_url
                }

                if key not in previous_state:
                    caption = f'*{title}* - ₪{product_price}\n[לצפייה במוצר]({link})'
                    send_photo_with_caption(img_url or "https://via.placeholder.com/300", caption)
                    new_items.append(title)

        # בדיקת מוצרים שהוסרו
        for old_key in previous_state:
            if old_key not in current_state:
                removed_title = previous_state[old_key]["title"]
                removed_items.append(removed_title)
                send_telegram_message(f"❌ הנעל '{removed_title}' כבר לא זמינה")

        save_current_state(current_state)

        if not new_items and not removed_items:
            send_telegram_message("🔄 כל הנעליים הקודמות עדיין זמינות 👟")

        # שליחת קופונים
        send_telegram_message(get_coupon_text())

        browser.close()

if __name__ == '__main__':
    check_shoes()