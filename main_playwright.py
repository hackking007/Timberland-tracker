import os
import json
import re
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
STATE_FILE = "shoes_state.json"
USER_DATA_FILE = "user_data.json"


def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
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


def load_json_file(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json_file(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_coupon_from_timberland_site():
    try:
        resp = requests.get("https://www.timberland.co.il", timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        img_tag = soup.select_one('div.fls-image-popup.visible-both img[alt]')
        if img_tag and "קוד קופון" in img_tag["alt"]:
            alt_text = img_tag["alt"]
            code_match = re.search(r'\b[A-Z0-9]{5,}\b', alt_text)
            if code_match:
                code = code_match.group()
                return f"- {alt_text.strip()} | קוד: *{code}*  \n  (מקור: Timberland.co.il)"
    except:
        return None


def get_coupon_text():
    coupons = [
        "- 10% הנחה בקנייה ראשונה | קוד: *FIRST10*  \n  (מקור: Cashyo)",
        "- 50 ש\"ח הנחה בקנייה מעל 300 ש\"ח | קוד: *TIMBER50*  \n  (מקור: FreeCoupon)"
    ]
    site_coupon = get_coupon_from_timberland_site()
    if site_coupon:
        coupons.append(site_coupon)

    return "🎁 *קופונים רלוונטיים:*\n\n" + "\n\n".join(coupons)


def category_to_url(category, size, price):
    base_urls = {
        "men": "https://www.timberland.co.il/men/footwear",
        "women": "https://www.timberland.co.il/women",
        "kids": "https://www.timberland.co.il/kids"
    }
    size_map = {
        "43": "794",  # גברים
        "37": "799",  # נשים
        "30": "234"   # ילדים
    }
    size_code = size_map.get(size, "794")
    url = f"{base_urls[category]}?price={price}&size={size_code}&product_list_order=low_to_high"
    return url


def check_shoes():
    user_data = load_json_file(USER_DATA_FILE)
    all_previous = load_json_file(STATE_FILE)
    all_current = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale='he-IL')
        page = context.new_page()

        for user_id, prefs in user_data.items():
            category = prefs.get("gender", "men")
            size = prefs.get("size", "43")
            price = prefs.get("price", "0-300")

            url = category_to_url(category, size, price)
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

            soup = BeautifulSoup(page.content(), 'html.parser')
            product_cards = soup.select('div.product')

            current_state = {}
            previous_state = all_previous.get(user_id, {})
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
                        text = tag.get_text(strip=True).replace('₪', '').replace(',', '')
                        price_val = float(text)
                        if price_val > 0:
                            prices.append(price_val)
                    except:
                        continue

                if not prices or min(prices) > float(price.split("-")[1]):
                    continue

                price_val = min(prices)
                key = link
                current_state[key] = {
                    "title": title,
                    "link": link,
                    "price": price_val,
                    "img_url": img_url
                }

                if key not in previous_state:
                    caption = f'*{title}* - ₪{price_val}\n[צפייה במוצר]({link})'
                    send_photo_with_caption(user_id, img_url or "https://via.placeholder.com/300", caption)
                    new_items.append(title)

            for key in previous_state:
                if key not in current_state:
                    removed_items.append(previous_state[key]["title"])
                    send_telegram_message(user_id, f"❌ הנעל '{previous_state[key]['title']}' כבר לא רלוונטית.")

            all_current[user_id] = current_state

            if not new_items and not removed_items:
                send_telegram_message(user_id, "🔄 כל הנעליים שנשלחו בעבר עדיין רלוונטיות.")

            send_telegram_message(user_id, get_coupon_text())

        browser.close()
    save_json_file(STATE_FILE, all_current)


if __name__ == "__main__":
    check_shoes()