import os
import requests
from bs4 import BeautifulSoup
import re

TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']
MAX_PRICE = 300

BASE_URL = "https://www.timberland.co.il/men"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest"
}

def send_telegram_message(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    requests.post(url, data=payload)

def fetch_page_html(page):
    url = f"{BASE_URL}?p={page}&size=794&ajax=1"
    res = requests.get(url, headers=HEADERS)
    if res.status_code == 200 and "product" in res.text:
        return res.text
    return ""

def parse_products(html):
    soup = BeautifulSoup(html, "html.parser")
    products = soup.select("div.product")
    results = []

    for product in products:
        link_tag = product.select_one("a")
        img_tag = product.select_one("img")
        price_tags = product.select("span.price")

        title = img_tag['alt'].strip() if img_tag and img_tag.has_attr('alt') else "ללא שם"
        link = link_tag['href'] if link_tag and link_tag.has_attr('href') else "#"
        img_url = img_tag['src'] if img_tag and img_tag.has_attr('src') else None

        prices = []
        for tag in price_tags:
            try:
                # מסיר כל תו שהוא לא ספרה או נקודה
                text = re.sub(r'[^\d.]', '', tag.text)
                price_val = float(text)
                if price_val > 0:
                    prices.append(price_val)
            except:
                continue

        if not prices:
            continue

        price = min(prices)

        if price <= MAX_PRICE:
            message = f'*{title}* - ₪{price}\n[View Product]({link})'
            if img_url:
                message += f'\n{img_url}'
            results.append(message)

    return results

def main():
    page = 1
    found = []

    while True:
        print(f"🔄 Fetching page {page}...")
        html = fetch_page_html(page)
        if not html:
            break

        products = parse_products(html)
        if not products:
            break

        found.extend(products)
        page += 1

    if found:
        full_message = f'👟 *Shoes up to ₪{MAX_PRICE} with size 43*\n\n' + '\n\n'.join(found)
        send_telegram_message(full_message)
    else:
        send_telegram_message("🤷‍♂️ No matching shoes found with size 43.")

if __name__ == '__main__':
    main()