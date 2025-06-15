import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
USER_DATA_FILE = "user_data.json"

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

def send_photo(chat_id, image_url, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {"chat_id": chat_id, "photo": image_url, "caption": caption, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
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

def build_url(user):
    gender = user.get("gender", "men")
    size = user.get("size", "43")
    price = user.get("price", "200-300").replace(" ", "")
    from_price, to_price = price.split("-")
    urls = {
        "men": f"https://www.timberland.co.il/men/footwear?price={from_price}_{to_price}&size=794",
        "women": f"https://www.timberland.co.il/women?price={from_price}_{to_price}&size=10",
        "kids": f"https://www.timberland.co.il/kids?price={from_price}_{to_price}&size=234",
    }
    return urls.get(gender, urls["men"])

def check_user(user_id, user, playwright):
    chat_id = user_id
    state_file = f"shoes_state_{user_id}.json"
    previous_state = load_json(state_file)
    current_state = {}

    url = build_url(user)
    new_items = []
    removed_items = []
    price_changes = []

    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(locale='he-IL')
    page = context.new_page()
    page.goto(url, timeout=60000)

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

    soup = BeautifulSoup(page.content(), 'html.parser')
    products = soup.select('div.product')

    for card in products:
        title = card.select_one("img")['alt'].strip() if card.select_one("img") else "ללא שם"
        link_tag = card.select_one("a")
        if not link_tag or not link_tag.has_attr('href'):
            continue
        link = "https://www.timberland.co.il" + link_tag['href']
        key = link

        img_url = card.select_one("img")['src'] if card.select_one("img") else None
        price_tags = card.select("span.price")
        prices = []

        for tag in price_tags:
            try:
                price = float(tag.text.strip().replace("₪", "").replace(",", "").replace("\xa0", ""))
                if price > 0:
                    prices.append(price)
            except:
                continue

        if not prices:
            continue

        price = min(prices)
        current_state[key] = {
            "title": title,
            "price": price,
            "link": link,
            "img_url": img_url
        }

        if key not in previous_state:
            send_photo(chat_id, img_url or "https://via.placeholder.com/300", f"*{title}* - ₪{price}\n[לצפייה במוצר]({link})")
            new_items.append(title)
        elif previous_state[key]["price"] != price:
            old_price = previous_state[key]["price"]
            price_changes.append((title, old_price, price))
            send_message(chat_id, f"🔄 *{title}* שינתה מחיר: ₪{old_price} ➜ ₪{price}\n[לינק למוצר]({link})")

    for key in previous_state:
        if key not in current_state:
            removed_items.append(previous_state[key]["title"])
            send_message(chat_id, f"❌ הנעל *{previous_state[key]['title']}* כבר לא זמינה")

    if not new_items and not removed_items and not price_changes:
        send_message(chat_id, "🔄 *הנעליים שנשלחו בעבר עדיין רלוונטיות.*")

    send_message(chat_id, get_coupon_text())
    save_json(state_file, current_state)
    browser.close()

def check_all_users():
    user_data = load_json(USER_DATA_FILE)
    if not user_data:
        print("❗ לא נמצאו משתמשים בקובץ user_data.json")
        return

    with sync_playwright() as p:
        for user_id, prefs in user_data.items():
            check_user(user_id, prefs, p)

if __name__ == "__main__":
    check_all_users()