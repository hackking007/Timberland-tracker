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
        browser = p.chromium.launch(
            headless=False,  # Try non-headless to bypass CloudFlare
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--start-maximized'
            ]
        )
        context = browser.new_context(
            locale='he-IL',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'he-IL,he;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
        )
        page = context.new_page()
        
        # Remove automation indicators
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['he-IL', 'he', 'en-US', 'en'],
            });
        """)
        
        try:
            page.goto(url, timeout=60000)
            page.wait_for_load_state('domcontentloaded')
            
            # Wait for CloudFlare/loading to finish - much longer wait
            page.wait_for_timeout(10000)
            
            # Check multiple times for CloudFlare bypass
            for attempt in range(5):
                current_title = page.title()
                if 'רק רגע' not in current_title and 'Just a moment' not in current_title:
                    break
                print(f"CloudFlare attempt {attempt + 1}, waiting...")
                page.wait_for_timeout(5000)
                
            # Simulate human interaction
            page.mouse.move(500, 300)
            page.wait_for_timeout(2000)
            page.mouse.click(500, 300)
            page.wait_for_timeout(3000)
                
            # Wait for products to load
            try:
                page.wait_for_selector('.products, .product-items, [data-role="product"], .catalog-product-view', timeout=20000)
            except:
                pass
            
            page.wait_for_timeout(5000)
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            page.wait_for_timeout(5000)
            
        except Exception as e:
            send_telegram_message(f"❌ שגיאה בטעינת הדף: {str(e)}")
            browser.close()
            return

        # Try to load more products
        load_attempts = 0
        while load_attempts < 3:
            try:
                load_more = page.query_selector("a.action.more")
                if load_more and load_more.is_visible():
                    load_more.click()
                    page.wait_for_timeout(2000)
                    load_attempts += 1
                else:
                    break
            except:
                break

        soup = BeautifulSoup(page.content(), 'html.parser')
        
        # Try multiple selectors for products
        product_cards = (soup.select('li.item.product.product-item') or 
                       soup.select('.product-item') or 
                       soup.select('li.product-item') or
                       soup.select('.products .product') or
                       soup.select('ol.products li') or
                       soup.select('.product-items li') or
                       soup.select('div[data-role="product"]') or
                       soup.select('.product') or
                       soup.select('[class*="product-"]') or
                       soup.select('article') or
                       soup.select('.item'))
        
        # Debug info
        page_title = soup.select_one('title')
        current_url = page.url
        debug_info = f"Page title: {page_title.text if page_title else 'No title'}\nCurrent URL: {current_url}\nFound {len(product_cards)} products"
        print(debug_info)
        
        # Check if we're still on a loading/error page
        if page_title and ('רק רגע' in page_title.text or 'Just a moment' in page_title.text or 'Access denied' in page_title.text):
            send_telegram_message(f"⚠️ נתקלנו בדף טעינה/חסימה: {page_title.text}")
            browser.close()
            return
        
        if not product_cards:
            # Try even more selectors
            product_cards = (soup.select('li[class*="product"]') or
                           soup.select('div[class*="product"]') or
                           soup.select('[data-product]') or
                           soup.select('.grid-item') or
                           soup.select('.catalog-item'))
            
            if not product_cards:
                # Save HTML and screenshot for debugging
                html_debug = "debug.html"
                with open(html_debug, 'w', encoding='utf-8') as f:
                    f.write(page.content())
                
                screenshot_path = "debug.png"
                page.screenshot(path=screenshot_path, full_page=True)
                send_local_photo(screenshot_path, f"📸 *Debug Screenshot:* לא נמצאו מוצרים\n{debug_info}")
                browser.close()
                return

        for card in product_cards:
            link_tag = card.select_one("a.product-item-link") or card.select_one("a")
            img_tag = (card.select_one(".product-image-main img") or 
                      card.select_one(".product-item-photo img") or
                      card.select_one("img"))
            price_tags = (card.select(".price-box .price") or
                         card.select(".regular-price .price") or 
                         card.select("span.price") or 
                         card.select(".price"))

            title = ""
            if img_tag and img_tag.get('alt'):
                title = img_tag.get('alt').strip()
            else:
                title_tag = (card.select_one('.product-item-name a') or 
                            card.select_one('.product-name a') or
                            card.select_one('h3 a') or
                            card.select_one('h2 a'))
                title = title_tag.text.strip() if title_tag else "ללא שם"
            
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
                    send_telegram_message(f"מוצר חדש: {caption}\n(שגיאה בתמונה: {str(e)})")

        browser.close()

    save_current_state(current_state)

if __name__ == "__main__":
    check_shoes()l": img_url
            }

            if key not in previous_state:
                caption = f"*{title}* - ₪{price_val}\n[לינק למוצר]({link})"
                try:
                    send_photo_with_caption(img_url or "https://via.placeholder.com/300", caption)
                except Exception as e:
                    send_telegram_message(f"מוצר חדש: {caption}\n(שגיאה בתמונה: {str(e)})")

        browser.close()

    save_current_state(current_state)

if __name__ == "__main__":
    check_shoes()
