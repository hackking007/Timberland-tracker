import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
STATE_FILE = "shoes_state.json"

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

def send_photo_with_caption(image_url, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {
        "chat_id": CHAT_ID,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

def send_local_photo(path, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    with open(path, "rb") as f:
        files = {"photo": f}
        data = {"chat_id": CHAT_ID, "caption": caption}
        requests.post(url, data=data, files=files)

def load_previous_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_current_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def check_shoes():
    previous_state = load_previous_state()
    current_state = {}
    
    url = "https://www.timberland.co.il/men/footwear?price=78_301&size=794"
    
    send_telegram_message(f"🔍 *בודק נעליים:*\n{url}")
    print(f"Checking: {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        try:
            page.goto(url, timeout=60000)
            page.wait_for_timeout(15000)  # Wait 15 seconds for CloudFlare
            
            # Check if CloudFlare is still active
            current_title = page.title()
            if 'רק רגע' in current_title:
                send_telegram_message("⚠️ CloudFlare עדיין חוסם - מנסה שוב")
                page.wait_for_timeout(20000)  # Wait another 20 seconds
            
        except Exception as e:
            send_telegram_message(f"❌ שגיאה בטעינת הדף: {str(e)}")
            browser.close()
            return

        soup = BeautifulSoup(page.content(), 'html.parser')
        
        # Try multiple selectors for products
        product_cards = (soup.select('li.item.product.product-item') or 
                       soup.select('.product-item') or 
                       soup.select('li.product-item') or
                       soup.select('.products .product') or
                       soup.select('ol.products li') or
                       soup.select('.product-items li') or
                       soup.select('.product') or
                       soup.select('article') or
                       soup.select('.item'))
        
        # Debug info
        page_title = soup.select_one('title')
        debug_info = f"Page title: {page_title.text if page_title else 'No title'}\nFound {len(product_cards)} products"
        print(debug_info)
        
        # Check if still blocked
        if page_title and 'רק רגע' in page_title.text:
            send_telegram_message(f"⚠️ עדיין חסום: {page_title.text}")
            browser.close()
            return
        
        if not product_cards:
            screenshot_path = "debug.png"
            page.screenshot(path=screenshot_path, full_page=True)
            send_local_photo(screenshot_path, f"📸 *Debug:* לא נמצאו מוצרים\n{debug_info}")
            browser.close()
            return

        for card in product_cards:
            link_tag = card.select_one("a")
            img_tag = card.select_one("img")
            price_tags = card.select(".price")

            title = img_tag.get('alt', 'ללא שם').strip() if img_tag else "ללא שם"
            link = link_tag.get('href') if link_tag else None
            
            if not link:
                continue
            if not link.startswith("http"):
                link = "https://www.timberland.co.il" + link

            img_url = img_tag.get('src') if img_tag else None
            if img_url and not img_url.startswith('http'):
                img_url = "https://www.timberland.co.il" + img_url
                
            prices = []
            for tag in price_tags:
                try:
                    import re
                    text = tag.text.strip().replace('\xa0', '').replace('₪', '').replace(',', '')
                    numbers = re.findall(r'\d+(?:\.\d+)?', text)
                    for num in numbers:
                        price_val = float(num)
                        if price_val > 0:
                            prices.append(price_val)
                except:
                    continue

            if not prices:
                continue

            price_val = min(prices)
            key = link
            current_state[key] = {
                "title": title, "link": link,
                "price": price_val, "img_url": img_url
            }

            if key not in previous_state:
                caption = f"*{title}* - ₪{price_val}\n[לינק למוצר]({link})"
                try:
                    send_photo_with_caption(img_url or "https://via.placeholder.com/300", caption)
                except Exception as e:
                    send_telegram_message(f"מוצר חדש: {caption}")

        browser.close()

    save_current_state(current_state)

if __name__ == "__main__":
    check_shoes()
