import os
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# משתנים סודיים מהסביבה
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']

# סינון
MAX_PRICE = 300
SIZE_TO_MATCH = "43"

# שליחת תמונה עם כיתוב לטלגרם
def send_photo_with_caption(image_url, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {
        "chat_id": CHAT_ID,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

# הרצת בדיקה
def check_shoes():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale='he-IL')
        page = context.new_page()

        page.goto("https://www.timberland.co.il/men/footwear?price=198_305&product_list_order=low_to_high&size=794", timeout=60000)

        # טעינת כל המוצרים ע"י לחיצה על כפתור 'טען עוד'
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

        found = 0

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

            price = min(prices)

            # בדיקת הופעת מידה 43
            product_page = context.new_page()
            product_page.goto(link, timeout=30000)
            product_html = product_page.content()
            if SIZE_TO_MATCH not in product_html:
                continue

            caption = f'*{title}* - ₪{price}\n[View Product]({link})'
            if img_url:
                send_photo_with_caption(img_url, caption)
            else:
                send_photo_with_caption("https://via.placeholder.com/300", caption)
            found += 1

        if found == 0:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={
                'chat_id': CHAT_ID,
                'text': f"🤷‍♂️ לא נמצאו נעליים תואמות במידה {SIZE_TO_MATCH}.",
                'parse_mode': 'Markdown'
            })

        # שליחת קופונים רלוונטיים
        coupon_text = (
            "🎁 *קופונים רלוונטיים:*\n\n"
            "- 10% הנחה בקנייה ראשונה | קוד: FIRST10  \n  (מקור: Cashyo)\n\n"
            "- 50 ש\"ח הנחה בקנייה מעל 300 ש\"ח | קוד: TIMBER50  \n  (מקור: FreeCoupon)"
        )
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={
            'chat_id': CHAT_ID,
            'text': coupon_text,
            'parse_mode': 'Markdown'
        })

        browser.close()

# הרצה
if __name__ == '__main__':
    check_shoes()