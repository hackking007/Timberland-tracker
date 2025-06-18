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

def load_previous_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_current_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def get_internal_coupon_text(page):
    try:
        coupon_banner = page.query_selector(".home-coupon-code")
        if coupon_banner:
            return f"🎟️ *קופון מהאתר:*\n- קוד: {coupon_banner.inner_text().strip()}"
    except:
        pass
    return None

def get_cashyo_coupons():
    url = "https://www.cashyo.co.il/coupons/timberland"
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        items = soup.select(".coupon-item")
        return [
            f"- {item.select_one('.coupon-title').text.strip()} | קוד: {item.select_one('.coupon-code').text.strip()}"
            for item in items if item.select_one(".coupon-title") and item.select_one(".coupon-code")
        ]
    except:
        return []

def get_pelecard_coupons():
    url = "https://www.pelecard.co.il/coupons"
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        matches = soup.find_all(string=lambda t: "טימברלנד" in t or "Timberland" in t)
        return [f"- {m.strip()}" for m in matches]
    except:
        return []

def get_groo_coupons():
    url = "https://www.groo.co.il/"
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        matches = soup.find_all(string=lambda t: "טימברלנד" in t or "Timberland" in t)
        return [f"- {m.strip()}" for m in matches]
    except:
        return []

def get_couponyashir_coupons():
    url = "https://www.couponyashir.co.il/coupons/timberland"
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        boxes = soup.select(".couponbox")
        return [
            f"- {box.select_one('h3').text.strip()} | קוד: {box.select_one('.coupon-code').text.strip()}"
            for box in boxes if box.select_one("h3") and box.select_one(".coupon-code")
        ]
    except:
        return []

def get_all_external_coupons():
    coupons = []
    coupons.extend(get_cashyo_coupons())
    coupons.extend(get_pelecard_coupons())
    coupons.extend(get_groo_coupons())
    coupons.extend(get_couponyashir_coupons())
    if not coupons:
        return None
    return "🎁 *קופונים מאתרים חיצוניים:*\n" + "\n".join(coupons)

def check_shoes():
    previous_state = load_previous_state()
    current_state = {}
    new_items, removed_items, changed_items = [], [], []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale='he-IL')
        page = context.new_page()

        # כתובת עם סינון מדויק למידה 43
        page.goto("https://www.timberland.co.il/men/footwear?price=10_304&size=794&product_list_order=low_to_high", timeout=60000)

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

            price = min(prices)
            key = link
            current_state[key] = {
                "title": title,
                "link": link,
                "price": price,
                "img_url": img_url
            }

            if key not in previous_state:
                send_photo_with_caption(img_url or "https://via.placeholder.com/300", f"*{title}* - ₪{price}\n[לינק למוצר]({link})")
                new_items.append(title)
            elif previous_state[key]["price"] != price:
                send_photo_with_caption(img_url or "https://via.placeholder.com/300", f"*{title}*\n🔄 מחיר השתנה: ₪{previous_state[key]['price']} ➝ ₪{price}\n[לינק למוצר]({link})")
                changed_items.append(title)

        # הסרות
        for old_key in previous_state:
            if old_key not in current_state:
                send_telegram_message(f"❌ הנעל '{previous_state[old_key]['title']}' הוסרה מהאתר")
                removed_items.append(previous_state[old_key]["title"])

        save_current_state(current_state)

        if not new_items and not removed_items and not changed_items:
            send_telegram_message("🔁 כל הנעליים ששלחנו בעבר עדיין זמינות ומעודכנות ✅")

        # קופון פנימי מהאתר
        internal_coupon = get_internal_coupon_text(page)
        if internal_coupon:
            send_telegram_message(internal_coupon)

        # קופונים חיצוניים
        external_coupons = get_all_external_coupons()
        if external_coupons:
            send_telegram_message(external_coupons)

        browser.close()

if __name__ == '__main__':
    check_shoes()