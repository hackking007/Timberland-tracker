import os
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# הגדרות בסיסיות
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']
MAX_PRICE = 299
SIZE = '43'

# שליחת הודעה בטלגרם
def send_telegram_message(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    requests.post(url, data=payload)

# פונקציית הבדיקה
def check_shoes():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale='he-IL',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        page.goto('https://www.timberland.co.il/men/footwear', timeout=60000)

        # גלילה למטה כדי לטעון מוצרים
        for i in range(5):
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(1000)

        # צילום מסך
        page.screenshot(path="screenshot.png", full_page=True)

        # המתנה לטעינת מוצרים
        try:
            page.wait_for_selector('.product-item-info', timeout=30000)
        except:
            send_telegram_message("❌ לא נמצאו מוצרים בדף (גם לאחר גלילה).")
            return

        # שמירת HTML לניתוח
        html = page.content()
        with open("after_scroll.html", "w", encoding="utf-8") as f:
            f.write(html)

        browser.close()

    # ניתוח HTML עם BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    found = []

    for product in soup.select('.product-item-info'):
        title_tag = product.select_one('.product-item-name a')
        price_tag = product.select_one('.price-wrapper .price')
        if not title_tag or not price_tag:
            continue

        title = title_tag.text.strip()
        link = title_tag['href']
        price = float(price_tag.text.replace('₪', '').replace(',', '').strip())

        if price < MAX_PRICE:
            found.append(f'*{title}*\\n₪{price} - [View Product]({link})')

    # שליחת התוצאה
    if found:
        message = f'👟 *Shoes Found under ₪{MAX_PRICE}*\\n\\n' + '\\n\\n'.join(found)
        send_telegram_message(message)
    else:
        send_telegram_message("🤷‍♂️ No matching shoes found.")

# הפעלת הסקריפט
if __name__ == '__main__':
    check_shoes()
