import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
STATE_FILE = "shoes_state.json"
USER_DATA_FILE = "user_data.json"

GENDER_URLS = {
    "גברים": "https://www.timberland.co.il/men/footwear",
    "נשים": "https://www.timberland.co.il/women",
    "ילדים": "https://www.timberland.co.il/kids"
}

SIZE_IDS = {
    "43": "794",
    "42": "793",
    "41": "792",
    "44": "795",
    "45": "796",
    "46": "797",
    "47": "798",
    "37": "799",
    "38": "800",
    # תוכל להוסיף כאן עוד לפי הצורך
}

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    })

def send_photo(chat_id, image_url, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    requests.post(url, data={
        "chat_id": chat_id,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "Markdown"
    })

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_coupon_text():
    return (
        "🎁 *קופונים רלוונטיים:*\n\n"
        "- 10% הנחה בקנייה ראשונה | קוד: FIRST10  \n  (מקור: Cashyo)\n\n"
        "- 50 ש\"ח הנחה בקנייה מעל 300 ש\"ח | קוד: TIMBER50  \n  (מקור: FreeCoupon)"
    )

def check_shoes():
    user_data = load_json(USER_DATA_FILE)
    previous_state = load_json(STATE_FILE)
    current_state = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="he-IL")
        page = context.new_page()

        for user_id, prefs in user_data.items():
            gender = prefs.get("gender", "").lower()
            size = prefs.get("size", "")
            price_range = prefs.get("price", "0-300")

            gender_url = GENDER_URLS.get(gender)
            size_param = SIZE_IDS.get(size)

            if not gender_url or not size_param:
                continue

            full_url = f"{gender_url}?price={price_range.replace('-', '_')}&size={size_param}&product_list_order=low_to_high"
            page.goto(full_url, timeout=60000)

            # לחץ על "טען עוד" אם קיים
            while True:
                try:
                    more = page.query_selector("a.action.more")
                    if more:
                        more.click()
                        page.wait_for_timeout(1500)
                    else:
                        break
                except:
                    break

            soup = BeautifulSoup(page.content(), "html.parser")
            products = soup.select("div.product")

            found_items = {}
            for card in products:
                link_tag = card.select_one("a")
                img_tag = card.select_one("img")
                price_tags = card.select("span.price")

                title = img_tag['alt'].strip() if img_tag and img_tag.has_attr("alt") else "ללא שם"
                link = link_tag['href'] if link_tag and link_tag.has_attr("href") else ""
                if not link.startswith("http"):
                    link = "https://www.timberland.co.il" + link

                image_url = img_tag['src'] if img_tag and img_tag.has_attr("src") else ""
                prices = []
                for p in price_tags:
                    try:
                        val = p.text.replace("₪", "").replace(",", "").strip()
                        prices.append(float(val))
                    except:
                        continue

                if not prices:
                    continue

                price = min(prices)
                key = f"{user_id}_{link}"
                found_items[key] = {"title": title, "price": price, "img": image_url, "link": link}

                if key not in previous_state:
                    caption = f"*{title}* - ₪{price}\n[לצפייה במוצר]({link})"
                    send_photo(user_id, image_url or "https://via.placeholder.com/300", caption)

            # נעליים שהוסרו
            for key in list(previous_state.keys()):
                if key.startswith(user_id + "_") and key not in found_items:
                    send_telegram_message(user_id, f"❌ הנעל '{previous_state[key]['title']}' כבר לא זמינה")

            # אם לא השתנה כלום – שלח הודעה ניטרלית
            previous_keys = {k for k in previous_state if k.startswith(user_id + "_")}
            current_keys = set(found_items.keys())
            if previous_keys == current_keys:
                send_telegram_message(user_id, "🔄 כל הנעליים ששלחנו לך בעבר עדיין זמינות באתר.")

            # שלח קופונים תמיד
            send_telegram_message(user_id, get_coupon_text())

            current_state.update(found_items)

        save_json(STATE_FILE, current_state)
        browser.close()

if __name__ == "__main__":
    check_shoes()