def check_shoes():
    url = 'https://www.timberland.co.il/men/footwear'
    response = requests.get(url, headers=headers)

    # שמור את תוכן ה-HTML לקובץ כדי לבדוק אותו
    with open("timberland_output.html", "w", encoding="utf-8") as f:
        f.write(response.text)

    # שלח הודעה רק כדי לוודא שרץ
    send_telegram_message("📄 HTML page saved. Check content.")
