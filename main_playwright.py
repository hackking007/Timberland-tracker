import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
STATE_FILE = "shoes_state.json"
USER_DATA_FILE = "user_data.json"

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
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

def load_json_file(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_json_file(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_coupon_text():
    return (
        "🎁 *קופונים רלוונטיים:*\n\n"
        "- 10% הנחה בקנייה ראשונה | קוד: FIRST10  \n  (מקור: Cashyo)\n\n"
        "- 50 ש\"ח הנחה בקנייה מעל 300 ש\"ח | קוד: TIMBER50  \n  (מקור: FreeCoupon)"
    )

def build_url(gender, size_code, price_from, price_to):
    base_urls = {
        "גברים": "https://www.timberland.co.il/men/footwear",
        "נשים": "https://www.timberland.co.il/women",
        "ילדים": "https://www.timberland.co.il/kids",
        "men": "https://www.timberland.co.il/men/footwear",
        "women": "https://www.timberland.co.il/women",
        "kids": "https://www.timberland.co.il/kids",
    }
    base = base_urls.get(gender, base_urls["men"])
    return f"{base}?price={price_from}_{price_to}&product_list_order=low_to_high&size={size_code}"

def get_size_code(size_text, gender):
    mapping = {
        "גברים": {
            "43": "794",
        },
        "נשים": {
            "37": "799",
            "38": "800",
        },
        "ילדים": {
            "30": "234"
        },
        "men": {
            "43": "794",
        },
        "women": {
            "37": "799",
            "38": "800",
        },
        "kids": {
            "30": "234"
        }
    }
    return mapping.get(gender, {}).get(size_text, "794")

def check_shoes():
    user_data = load_json_file(USER_DATA_FILE)
    all_states = load_json_file(STATE_FILE)
    updated_states = {}

    for user_id, prefs in user_data.items():
        gender = prefs.get("gender", "גברים")
        size = prefs.get("size", "43")
        price_range = prefs.get("price", "0-300")
        price_from, price_to = price_range.split("-")

        size_code = get_size_code(size, gender)
        url = build_url(gender, size_code, price_from, price_to)
        previous_state = all_states.get(user_id, {})
        current_state = {}
        new_items = []
        removed_items = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(locale="he-IL")
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

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            product_cards = soup.select("div.product")

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

                if not prices or min(prices) > float(price_to):
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
                    caption = f'*{title}* - ₪{price}\n[View Product]({link})'
                    send_photo_with_caption(user_id, img_url or "https://via.placeholder.com/300", caption)
                    new_items.append(title)

            for old_key in previous_state:
                if old_key not in current_state:
                    removed_title = previous_state[old_key]["title"]
                    removed_items.append(removed_title)
                    send_telegram_message(user_id, f"❌ הנעל '{removed_title}' כבר לא רלוונטית")

            if not new_items and not removed_items:
                send_telegram_message(user_id, "🔄 כל הנעליים ששלחנו לך בעבר עדיין זמינות באתר.")

            send_telegram_message(user_id, get_coupon_text())

            browser.close()

        updated_states[user_id] = current_state

    save_json_file(updated_states, STATE_FILE)

if __name__ == "__main__":
    check_shoes()