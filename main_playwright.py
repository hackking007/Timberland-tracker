import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
STATE_FILE = "shoes_state.json"
USER_DATA_FILE = "user_data.json"

# שליחת הודעה פשוטה
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

# שליחת תמונה עם כיתוב
def send_photo_with_caption(image_url, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {"chat_id": CHAT_ID, "photo": image_url, "caption": caption, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

# טעינת מצב קודם
def load_previous_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# שמירת מצב נוכחי
def save_current_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# טעינת פרטי משתמש
def load_user_data():
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# משיכת קופונים מאתר FreeCoupon
def get_coupons_from_freecoupon():
    url = "https://www.freecoupon.co.il/coupons/timberland"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        coupon_blocks = soup.select("div.single-coupon")
        coupons = []

        for block in coupon_blocks[:3]:
            title = block.select_one("div.title a")
            code = block.select_one("div.coupon-code span")

            if not title or not code:
                continue

            title_text = title.get_text(strip=True)
            code_text = code.get_text(strip=True)

            coupons.append(f"- *{title_text}* | קוד: `{code_text}`")

        if not coupons:
            return "❌ לא נמצאו קופונים באתר FreeCoupon כרגע."

        return "🎟️ *קופונים מתוך FreeCoupon:*
"""
" + "\n".join(coupons)

    except Exception as e:
        return f"⚠️ שגיאה במשיכת קופונים מ-FreeCoupon: {e}"

# קוד ראשי
def check_shoes():
    user_data = load_user_data()
    if not user_data:
        send_telegram_message("⚠️ לא הוגדרו משתמשים. אנא השתמש ב־/start בבוט.")
        return

    previous_state = load_previous_state()
    current_state = {}

    found_any = False
    all_new_items = []
    all_removed_items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale='he-IL')
        page = context.new_page()

        for user_id, prefs in user_data.items():
            size = prefs.get("size")
            price = prefs.get("price").replace("-", "_")
            category = prefs.get("gender", "men")

            size_code_map = {
                "43": "794",
                "37": "799"
            }
            size_code = size_code_map.get(size, "794")

            category_url_map = {
                "men": "https://www.timberland.co.il/men/footwear",
                "women": "https://www.timberland.co.il/women",
                "kids": "https://www.timberland.co.il/kids"
            }
            base_url = category_url_map.get(category, "https://www.timberland.co.il/men/footwear")

            url = f"{base_url}?price={price}&size={size_code}&product_list_order=low_to_high"
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
                        text = tag.text.strip().replace(' ', '').replace('₪', '').replace(',', '')
                        price_val = float(text)
                        if price_val > 0:
                            prices.append(price_val)
                    except:
                        continue

                if not prices:
                    continue

                price = min(prices)
                key = f"{user_id}_{link}"
                current_state[key] = {
                    "title": title,
                    "link": link,
                    "price": price,
                    "img_url": img_url
                }

                if key not in previous_state:
                    caption = f'*{title}* - ₪{price}\n[לצפייה במוצר]({link})'
                    send_photo_with_caption(img_url or "https://via.placeholder.com/300", caption)
                    new_items.append(title)

            for old_key in list(previous_state.keys()):
                if old_key.startswith(user_id + "_") and old_key not in current_state:
                    removed_title = previous_state[old_key]["title"]
                    removed_items.append(removed_title)
                    send_telegram_message(f"❌ הנעל '{removed_title}' כבר לא זמינה")

            if not new_items and not removed_items:
                send_telegram_message("🔄 כל הנעליים שנשלחו בעבר עדיין רלוונטיות באתר.")

            all_new_items.extend(new_items)
            all_removed_items.extend(removed_items)

        save_current_state(current_state)
        send_telegram_message(get_coupons_from_freecoupon())

        browser.close()

if __name__ == "__main__":
    check_shoes()
