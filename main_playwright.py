import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# הגדרות
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
MAX_PRICE = 300
STATE_FILE = "shoes_state.json"
URL = "https://www.timberland.co.il/men/footwear?price=198_305&product_list_order=low_to_high&size=794"

# שליחת הודעת טקסט בטלגרם
def send_telegram_message(text):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    )

# שליחת תמונה עם טקסט
def send_photo_with_caption(image_url, caption):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
        data={
            "chat_id": CHAT_ID,
            "photo": image_url,
            "caption": caption,
            "parse_mode": "Markdown"
        }
    )

# טען מצב קודם
def load_previous_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# שמור מצב נוכחי
def save_current_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# טקסט קופונים
def get_coupon_text():
    return (
        "🎁 *קופונים רלוונטיים:*\n\n"
        "- 10% הנחה בקנייה ראשונה | קוד: FIRST10  \n  (מקור: Cashyo)\n\n"
        "- 50 ש\"ח הנחה בקנייה מעל 300 ש\"ח | קוד: TIMBER50  \n  (מקור: FreeCoupon)"
    )

# פונקציית בדיקת נעליים
def check_shoes():
    previous = load_previous_state()
    current = {}
    new_items = []
    removed_items = []
    updated_items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, timeout=60000)

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
        cards = soup.select("div.product")

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

            if not prices or min(prices) > MAX_PRICE:
                continue

            price = min(prices)
            key = link
            current[key] = {"title": title, "link": link, "price": price, "img_url": img_url}

            if key not in previous:
                new_items.append(key)
                caption = f'*{title}* - ₪{price}\n[לינק למוצר]({link})'
                send_photo_with_caption(img_url or "https://via.placeholder.com/300", caption)
            elif previous[key]["price"] != price:
                updated_items.append(key)
                caption = f'*{title}* - ₪{price} (עודכן)\n[לינק למוצר]({link})'
                send_photo_with_caption(img_url or "https://via.placeholder.com/300", caption)

        # זיהוי נעליים שהוסרו
        for old_key in previous:
            if old_key not in current:
                removed_items.append(old_key)
                send_telegram_message(f"❌ הנעל '{previous[old_key]['title']}' כבר לא זמינה")

        save_current_state(current)

        if not new_items and not removed_items and not updated_items:
            send_telegram_message("🔄 *הנעליים שנשלחו בעבר עדיין רלוונטיות.*")

        send_telegram_message(get_coupon_text())
        browser.close()

if __name__ == "__main__":
    check_shoes()