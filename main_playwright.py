import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# טוקן וצ'אט מה-ENV (מוגדרים ב-GitHub Secrets)
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

STATE_FILE = "shoes_state.json"
USER_DATA_FILE = "user_data.json"


def send_telegram_message(text: str) -> None:
    """שולח הודעת טקסט לטלגרם."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, data=payload)


def send_photo_with_caption(image_url: str, caption: str) -> None:
    """שולח תמונה לפי URL + כיתוב."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {
        "chat_id": CHAT_ID,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "Markdown",
    }
    requests.post(url, data=payload)


def send_local_photo(path: str, caption: str) -> None:
    """שולח קובץ תמונה מקומי (למשל screenshot) לטלגרם."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    with open(path, "rb") as f:
        files = {"photo": f}
        data = {"chat_id": CHAT_ID, "caption": caption}
        requests.post(url, data=data, files=files)


def load_previous_state():
    """טוען מצב קודם מקובץ shoes_state.json (לשימוש עתידי)."""
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_current_state(state: dict) -> None:
    """שומר מצב נוכחי לקובץ shoes_state.json."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_user_preferences():
    """טוען את העדפות המשתמשים מקובץ user_data.json."""
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def size_to_code(size: str) -> str:
    """ממיר מידה (למשל '43') לקוד המידה באתר טימברלנד."""
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
    https://www.timberland.co.il/men/footwear?price=0_300&size=794
    """
    base_urls = {
        "men": "https://www.timberland.co.il/men/footwear",
        "women": "https://www.timberland.co.il/women/%D7%94%D7%A0%D7%A2%D7%9C%D7%94",
        "kids": "https://www.timberland.co.il/kids/toddlers-0-5y",
    }

    size_code = size_to_code(size)
    if not size_code or category not in base_urls:
        return None

    price_param = price.replace("-", "_")

    return (
        f"{base_urls[category]}"
        f"?price={price_param}&size={size_code}&product_list_order=low_to_high"
    )


def close_popups(page) -> None:
    """מנסה לסגור פופאפים (Black Friday / מבצעים) אם קיימים."""
    selectors = [
        "button.action-close",
        "div.modal-popup .action-close",
        "button[aria-label='Close']",
        ".popup .close",
    ]
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                el.click()
                page.wait_for_timeout(500)
        except Exception:
            continue


def human_like_actions(page) -> None:
    """
    קצת "התנהגות אנושית":
    תזמונים, תנועת עכבר, גלילה, PageDown.
    המטרה היא להיראות פחות כמו בוט.
    """
    try:
        page.wait_for_timeout(1000)
        page.mouse.move(100, 200)
        page.wait_for_timeout(300)
        page.mouse.move(400, 500)
        page.wait_for_timeout(300)
        page.mouse.move(800, 600)
        page.wait_for_timeout(300)

        # גלילה למטה
        page.mouse.wheel(0, 600)
        page.wait_for_timeout(500)
        page.keyboard.press("PageDown")
        page.wait_for_timeout(500)
    except Exception:
        pass


def check_shoes() -> None:
    """
    סורק לכל המשתמשים:
    - בונה URL לפי ההעדפות
    - טוען את העמוד (עם ניסיון להיראות כמו משתמש אמיתי)
    - מנסה לסגור פופאפ
    - לוחץ על "Load more" אם קיים
    - לכל מוצר שנמצא – שולח תמונה + מחיר + לינק
    - אם לא נמצאו מוצרים → שולח screenshot כדי שנראה מה קורה
    - בסוף שולח הודעת סיכום.
    """
    previous_state = load_previous_state()
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
            # דפדפן headless אבל "מתחזים" לכרום רגיל
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )

            context = browser.new_context(
                locale="he-IL",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
                java_script_enabled=True,
            )

            page = context.new_page()

            # מסתיר את navigator.webdriver
            page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"
            )

            page.goto(url, wait_until="networkidle", timeout=60000)

            human_like_actions(page)
            close_popups(page)
            page.wait_for_timeout(1500)

            # לוחץ על "Load more" אם קיים (כמו בקוד המקורי שלך)
            while True:
                try:
                    load_more = page.query_selector("a.action.more")
                    if load_more:
                        load_more.click()
                        page.wait_for_timeout(1200)
                    else:
                        break
                except Exception:
                    break

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            # הסלקטור המקורי + fallback
            product_cards = soup.select("div.product")
            if not product_cards:
                product_cards = soup.select("li.item.product.product-item")

            print(
                f"➡️ נמצאו {len(product_cards)} כרטיסי מוצרים עבור המשתמש {user_id}"
            )

            if not product_cards:
                # אין מוצרים – נצלם Screenshot ונשלח לטלגרם כדי לראות מה Playwright רואה
                screenshot_path = f"debug_{user_id}.png"
                try:
                    page.screenshot(path=screenshot_path, full_page=True)
                    send_local_photo(
                        screenshot_path,
                        "🖼 Screenshot Debug – לא נמצאו מוצרים, כך הדף נראה ל־Playwright.",
                    )
                except Exception as e:
                    print(f"Failed to take/send screenshot: {e}")
                browser.close()
                continue

            for card in product_cards:
                link_tag = card.select_one("a")
                img_tag = card.select_one("img")
                price_tags = card.select("span.price")

                title = (
                    img_tag["alt"].strip()
                    if img_tag and img_tag.has_attr("alt")
                    else "ללא שם"
                )

                link = (
                    link_tag["href"]
                    if link_tag and link_tag.has_attr("href")
                    else None
                )
                if not link:
                    continue
                if not link.startswith("http"):
                    link = "https://www.timberland.co.il" + link

                img_url = (
                    img_tag["src"] if img_tag and img_tag.has_attr("src") else None
                )

                prices: list[float] = []
                for tag in price_tags:
                    try:
                        text = (
                            tag.text.strip()
                            .replace("\xa0", "")
                            .replace("₪", "")
                            .replace(",", "")
                        )
                        price_val = float(text)
                        if price_val > 0:
                            prices.append(price_val)
                    except Exception:
                        continue

                if not prices:
                    continue

                price_val = min(prices)

                key = f"{user_id}_{link}"
                current_state[key] = {
                    "title": title,
                    "link": link,
                    "price": price_val,
                    "img_url": img_url,
                }

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
