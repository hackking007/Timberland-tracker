import os
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']
MAX_PRICE = 300

def send_telegram_message(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    requests.post(url, data=payload)

def has_size_43(html):
    soup = BeautifulSoup(html, 'html.parser')
    size_tags = soup.select("div.swatch-option.text")
    for tag in size_tags:
        if "43" in tag.text.strip() and "disabled" not in tag.get("class", []):
            return True
    return False

def get_product_price(soup):
    price_tags = soup.select("span.price")
    prices = []
    for tag in price_tags:
        try:
            clean = tag.text.replace("₪", "").replace(",", "").replace("\xa0", "").strip()
            price = float(clean)
            if price > 0:
                prices.append(price)
        except:
            continue
    return min(prices) if prices else None

def check_shoes():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale='he-IL',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        page.goto('https://www.timberland.co.il/men?size=794', timeout=60000)

        for _ in range(10):
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(1000)

        html = page.content()
        soup = BeautifulSoup(html, 'html.parser')
        products = soup.select("div.product")
        found = []

        for product in products:
            link_tag = product.select_one("a")
            img_tag = product.select_one("img")

            title = img_tag['alt'].strip() if img_tag and img_tag.has_attr('alt') else "ללא שם"
            link = link_tag['href'] if link_tag and link_tag.has_attr('href') else None
            img_url = img_tag['src'] if img_tag and img_tag.has_attr('src') else None

            if not link:
                continue

            product_page = context.new_page()
            product_page.goto(link, timeout=30000)
            product_html = product_page.content()
            product_soup = BeautifulSoup(product_html, 'html.parser')

            if not has_size_43(product_html):
                product_page.close()
                continue

            price = get_product_price(product_soup)
            if price and price <= MAX_PRICE:
                message = f'*{title}* - ₪{price}\n[View Product]({link})'
                if img_url:
                    message += f'\n{img_url}'
                found.append(message)

            product_page.close()

        browser.close()

        if found:
            full_message = f'👟 *Shoes with size 43 under ₪{MAX_PRICE}*\n\n' + '\n\n'.join(found)
            send_telegram_message(full_message)
        else:
            send_telegram_message("🤷‍♂️ No matching shoes found with size 43.")

if __name__ == '__main__':
    check_shoes()