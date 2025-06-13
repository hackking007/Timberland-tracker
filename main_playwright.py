import requests

TELEGRAM_TOKEN = "הכנס_כאן_את_הטוקן"
CHAT_ID = "הכנס_כאן_את_הצ׳אט_ID"

msg = "בדיקה ידנית: הבוט פעיל?"
url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
payload = {'chat_id': CHAT_ID, 'text': msg}

r = requests.post(url, data=payload)
print(r.status_code, r.text)