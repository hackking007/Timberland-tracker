import os
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']
MAX_PRICE = 300
SIZE_TO_MATCH = "43"
STATE_FILE = "shoes_state.json"

def send_photo_with_caption(image_url, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {
        "chat_id": CHAT_ID,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

def send_text_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

def load_previous_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return set(f.read().splitlines())
    return set()

def save_current_state(keys):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(keys))

def check_shoes():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale='he-IL')
        page = context.new_page()
        page.goto("https://www.timberland.co.il/men/footwear?price=198_305&product_list_order=low_to_high&size=794", timeout=60000)

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

        found_items = {}
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

            if not prices or min(prices) > MAX_PRICE:
                continue

            product_page = context.new_page()
            product_page.goto(link, timeout=30000)
            product_html = product_page.content()
            if SIZE_TO_MATCH not in product_html:
                continue

            price = min(prices)
            key = f"{title}|{link}"
            found_items[key] = {
                'title': title,
                'price': price,
                'link': link,
                'img_url': img_url
            }

        browser.close()

        previous_keys = load_previous_state()
        current_keys = set(found_items.keys())

        new_items = current_keys - previous_keys
        removed_items = previous_keys - current_keys

        if new_items:
            for key in new_items:
                item = found_items[key]
                caption = f"*{item['title']}* - ₪{item['price']}\n[View Product]({item['link']})"
                send_photo_with_caption(item['img_url'] or "https://via.placeholder.com/300", caption)

        if removed_items:
            for key in removed_items:
                title, link = key.split("|")
                send_text_message(f"❌ *{title}* כבר לא זמינה או שהמחיר השתנה.\n[View Product]({link})")

        if not new_items and not removed_items:
            send_text_message("✅ כל הנעליים ששלחנו בעבר עדיין זמינות ורלוונטיות.")

        save_current_state(current_keys)

        send_coupon_update()

# ------------------ קופונים ------------------ #

def get_coupons_cashyo():
    try:
        url = "https://www.cashyo.co.il/retailer/timberland"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, 'html.parser')
        coupons = []
        for box in soup.select("div.coupon-box"):
            title = box.select_one("h3.coupon-title")
            code = box.select_one("div.code-box span.code")
            if title:
                coupons.append({
                    "source": "Cashyo",
                    "title": title.get_text(strip=True),
                    "code": code.get_text(strip=True) if code else "אין קוד"
                })
        return coupons
    except:
        return []

def get_coupons_freecoupon():
    try:
        url = "https://www.freecoupon.co.il/coupons/timberland/"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, 'html.parser')
        coupons = []
        for box in soup.select("div.discount-item"):
            title = box.select_one("h3.entry-title")
            code = box.select_one("div.discount-code span")
            if title:
                coupons.append({
                    "source": "FreeCoupon",
                    "title": title.get_text(strip=True),
                    "code": code.get_text(strip=True) if code else "אין קוד"
                })
        return coupons
    except:
        return []

def get_all_timberland_coupons():
    return get_coupons_cashyo() + get_coupons_freecoupon()

def format_coupons_message(coupons):
    if not coupons:
        return "🎁 *לא נמצאו קופונים זמינים.*"
    message = "🎁 *קופונים רלוונטיים:*\n"
    for c in coupons:
        message += f"\n- {c['title']} | קוד: {c['code']}\n  (מקור: {c['source']})"
    return message

def send_coupon_update():
    coupons = get_all_timberland_coupons()
    message = format_coupons_message(coupons)
    send_text_message(message)

# ------------------- הרצה ------------------- #

if __name__ == '__main__':
    check_shoes()