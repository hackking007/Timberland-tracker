import os
import json
import re
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# קורא את הטוקן וה-CHAT ID מה־ENV (מוגדרים ב-GitHub Secrets)
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

STATE_FILE = "shoes_state.json"
USER_DATA_FILE = "user_data.json"


def send_telegram_message(text: str) -> None:
    """
    שולח הודעת טקסט רגילה לטלגרם.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, data=payload)


def send_photo_with_caption(image_url: str, caption: str) -> None:
    """
    שולח תמונה + כיתוב (caption) לטלגרם.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {
        "chat_id": CHAT_ID,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "Markdown",
    }
    requests.post(url, data=payload)


def load_previous_state():
    """
    טוען מצב קודם מקובץ shoes_state.json.
    (כרגע לא משתמשים בזה לסינון, רק לשמירה לעתיד.)
    """
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_current_state(state: dict) -> None:
    """
    שומר מצב נוכחי לקובץ shoes_state.json.
    """
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_user_preferences():
    """
    טוען את העדפות המשתמשים מקובץ user_data.json.
    """
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def size_to_code(size: str) -> str:
    """
    ממיר מידה (למשל '43') לקוד המידה באתר טימברלנד.
    """
    mapping = {
        "43": "794",
        "42": "793",
        "41": "792",
        "40": "791",
        "39": "790",
        "38": "789",
        "37": "799",
    }
    return mapping.get(size, "")


def category_to_url(category: str, size: str, price: str) -> str | None:
    """
    בונה URL לפי קטגוריה, מידה וטווח מחיר.
    לדוגמה:
    https://www.timberland.co.il/men/footwear?price=10_299&size=794
    """
    base_urls = {
        "men": "https://www.timberland.co.il/men/footwear",
        "women": "https://www.timberland.co.il/women/%D7%94%D7%A0%D7%A2%D7%9C%D7%94",
        "kids": "https://www.timberland.co.il/kids/toddlers-0-5y",
    }

    size_code = size_to_code(size)
    if not size_code or category not in base_urls:
        return None

    # באתר טווח המחיר נכתב כ-0_300 ולא 0-300
    price_param = price.replace("-", "_")

    return (
        f"{base_urls[category]}"
        f"?price={price_param}&size={size_code}&product_list_order=low_to_high"
    )


def extract_products_from_html(soup: BeautifulSoup) -> list[dict]:
    """
    במקום להסתמך על class ספציפי (שמשתנה כל הזמן),
    אנחנו מאתרים מוצרים לפי:
    - לינקים ל-/men/footwear/ (או women/kids)
    - טקסט 'מחיר מוצר XXX ₪' שנמצא באותו בלוק.
    מחזיר רשימת מוצרים בפורמט:
    {title, link, price, img_url}
    """
    products: list[dict] = []

    # כל הלינקים שיכולים להיות מוצרים
    candidate_links = soup.select(
        "a[href*='/men/footwear/'], a[href*='/women/'], a[href*='/kids/']"
    )

    seen_links: set[str] = set()

    for a in candidate_links:
        href = a.get("href")
        if not href:
            continue

        # מסדרים לינק מלא
        if not href.startswith("http"):
            href_full = "https://www.timberland.co.il" + href
        else:
            href_full = href

        # אם כבר טיפלנו בלינק הזה – דלג
        if href_full in seen_links:
            continue

        title = a.get_text(strip=True)
        if not title:
            # אם אין טקסט, אולי זה לינק של תמונה – לא חובה, נמשיך
            continue

        # עולים קצת למעלה בהיררכיה כדי לתפוס את כל הבלוק של המוצר
        container = a
        for _ in range(4):  # עד 4 רמות למעלה
            if container.parent:
                container = container.parent
            else:
                break

        block_text = container.get_text(" ", strip=True)

        # מחפשים "מחיר מוצר XXX"
        m = re.search(r"מחיר מוצר\s*([\d\.]+)", block_text)
        if not m:
            # כלומר זה כנראה לינק בתפריט/פילטר, לא מוצר
            continue

        try:
            price_val = float(m.group(1))
        except ValueError:
            continue

        # חיפוש תמונה באזור הבלוק
        img_tag = container.find("img")
        img_url = None
        if img_tag and img_tag.get("src"):
            img_url = img_tag["src"]
            if not img_url.startswith("http"):
                img_url = "https://www.timberland.co.il" + img_url

        products.append(
            {
                "title": title,
                "link": href_full,
                "price": price_val,
                "img_url": img_url,
            }
        )
        seen_links.add(href_full)

    return products


def check_shoes() -> None:
    """
    סורק לכל המשתמשים:
    - בונה URL לפי ההעדפות
    - טוען את הדף (אין הסתמכות על div.product בכלל)
    - מנתח את ה-HTML לפי 'מחיר מוצר XXX' ולינקים של המוצרים
    - שולח *כל* מוצר שנמצא בתור תמונה+טקסט
    - בסוף שולח הודעת סיכום
    """
    previous_state = load_previous_state()  # לשימוש עתידי
    current_state: dict[str, dict] = {}
    user_data = load_user_preferences()

    if not user_data:
        send_telegram_message("⚠️ אין משתמשים רשומים.")
        print("⚠️ No users found.")
        return

    total_items_sent = 0

    for user_id, prefs in user_data.items():
        category = prefs.get("gender", "men")
        size = prefs.get("size", "43")
        price = prefs.get("price", "0-300")

        url = category_to_url(category, size, price)

        debug_msg = (
            f"🔍 *בודק למשתמש:* `{user_id}`\n"
            f"קטגוריה: {category} | מידה: {size} | טווח: {price}\n"
            f"{url}"
        )
        print(debug_msg)

        if not url:
            send_telegram_message(f"❌ שגיאה ב-URL למשתמש `{user_id}`")
            continue

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(locale="he-IL")
            page = context.new_page()
            page.goto(url, timeout=60000)
            page.wait_for_timeout(2000)  # נותן לדף להיטען

            soup = BeautifulSoup(page.content(), "html.parser")
            products = extract_products_from_html(soup)

            print(f"➡️ נמצאו {len(products)} מוצרים גולמיים עבור המשתמש {user_id}")

            for prod in products:
                title = prod["title"]
                link = prod["link"]
                price_val = prod["price"]
                img_url = prod["img_url"]

                key = f"{user_id}_{link}"
                current_state[key] = prod

                caption = f"*{title}* - ₪{price_val}\n[לינק למוצר]({link})"
                send_photo_with_caption(
                    img_url or "https://via.placeholder.com/300", caption
                )
                total_items_sent += 1

            browser.close()

    save_current_state(current_state)

    if total_items_sent == 0:
        summary = "ℹ️ הבוט רץ בהצלחה — לא נמצאו מוצרים בטווח ההגדרות."
    else:
        summary = f"✅ הבוט רץ בהצלחה — נשלחו {total_items_sent} מוצרים."

    send_telegram_message(summary)
    print(summary)


if __name__ == "__main__":
    check_shoes()
