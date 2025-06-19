import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
STATE_FILE = "shoes_state.json"
USER_DATA_FILE = "user_data.json"

# === פונקציית שליחת הודעה לטלגרם ===
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

# === פונקציית שליחת תמונה עם כיתוב לטלגרם ===
def send_photo_with_caption(image_url, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {
        "chat_id": CHAT_ID,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

# === קריאת מצב קודם של נעליים ===
def load_previous_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# === שמירת מצב חדש של נעליים ===
def save_current_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# === טעינת העדפות משתמשים ===
def load_user_preferences():
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# === המרת מידה לקוד מזהה באתר ===
def size_to_code(size):
    mapping = {
        "43": "794", "42": "793", "41": "792", "40": "791",
        "39": "790", "38": "789", "37": "799"
    }
    return mapping.get(size, "")

# === URL דינמי לפי העדפות ===
def category_to_url(category, size, price):
    base_urls = {
        "men": "https://www.timberland.co.il/men/footwear",
        "women": "https://www.timberland.co.il/women",
        "kids": "https://www.timberland.co.il/kids"
    }
    size_code = size_to_code(size)
    if not size_code or category not in base_urls:
        return None
    return f"{base_urls[category]}?price={price}&size={size_code}&product_list_order=low_to_high"

# === קבלת קופונים מאתר טימברלנד ===
def get_timberland_site_coupon():
    try:
        r = requests.get("https://www.timberland.co.il/")
        soup = BeautifulSoup(r.text, "html.parser")
        banner = soup.select_one(".top-bar .content span")
        if banner:
            return f"🎁 *קופון מהאתר:*\n\n{banner.text.strip()}"
    except Exception:
        return ""
    return ""

# === שליפת קופונים ידניים ===
def get_static_coupons():
    return (
        "🎟️ *קופונים מתוך FreeCoupon:*\n"
        "- קוד: FIRST10 – 10% הנחה לקנייה ראשונה (Cashyo)\n"
        "- קוד: TIMBER50 – 50 ש\"ח בקנייה מעל 300 ש\"ח (CouponYashir)\n"
        "- קוד: GROO15 – 15% הנחה באתר (Groo)\n"
        "- קוד: PAYPEL – 20 ש\"ח בקנייה מעל 200 (Pelecard)"
    )

# === הלוגיקה הראשית ===
def check_shoes():
    previous_state = load_previous_state()
    current_state = {}
    user_data = load_user_preferences()

    if not user_data:
        print("⚠️ אין משתמשים רשומים.")
        return

    for user_id, prefs in user_data.items():
        category = prefs.get("gender", "men").lower()
        size = prefs.get("size", "43")
        price = prefs.get("price", "10-304").replace("-", "_")

        url = category_to_url(category, size, price)
        if not url:
            send_telegram_message("❌ לא הצלחנו לבנות URL למשתמש.")
            continue

        print(f"🔍 בודק: {url}")
        new_items = []
        removed_items = []
        found = 0

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
                    new_items.append(title)
                found += 1

            for old_key in list(previous_state.keys()):
                if old_key.startswith(user_id) and old_key not in current_state:
                    removed_title = previous_state[old_key]["title"]
                    send_telegram_message(f"❌ הנעל '{removed_title}' כבר לא זמינה.")
                    removed_items.append(removed_title)

            browser.close()

        if not new_items and not removed_items:
            send_telegram_message("✅ כל הנעליים שנשלחו בעבר עדיין רלוונטיות באתר.")
        else:
            send_telegram_message("🎯 בדיקה הסתיימה - עודכנת בהצלחה.")

        timberland_coupon = get_timberland_site_coupon()
        static_coupons = get_static_coupons()
        full_coupon_text = f"{timberland_coupon}\n\n{static_coupons}" if timberland_coupon else static_coupons
        send_telegram_message(full_coupon_text)

    save_current_state(current_state)

if __name__ == "__main__":
    check_shoes()