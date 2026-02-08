import requests
import json
import os
from bs4 import BeautifulSoup

# ================= CONFIG =================

URL = "https://aniruddha-sonawane.github.io/SPPU-Result-Clone/"
DATA_FILE = "known_results.json"

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# ================= TELEGRAM =================

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    r = requests.post(url, json=payload, timeout=20)

    # DEBUG OUTPUT (CRITICAL)
    print("Telegram status:", r.status_code)
    print("Telegram response:", r.text)

# ================= SCRAPER =================

def fetch_results():
    response = requests.get(URL, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", id="tblRVList")

    if not table:
        raise Exception("Results table not found")

    results = []

    for row in table.tbody.find_all("tr"):
        cols = [c.get_text(strip=True) for c in row.find_all("td")]
        if len(cols) >= 3:
            results.append({
                "id": cols[0],
                "course": cols[1],
                "date": cols[2]
            })

    return results

# ================= STORAGE =================

def load_old():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_current(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ================= MAIN =================

def main():
    print("Checking SPPU results page...")

    # 🚨 TELEGRAM CONNECTIVITY TEST (DO NOT REMOVE YET)
    send_telegram("🧪 GitHub Actions → Telegram test message")

    current = fetch_results()
    old = load_old()

    if not old:
        print("Baseline created.")
        save_current(current)
        return

    old_ids = {r["id"] for r in old}
    new = [r for r in current if r["id"] not in old_ids]

    if new:
        msg = "🚨 *NEW SPPU RESULT(S) ADDED*\n\n"
        for r in new:
            msg += f"• *{r['course']}*\n  `{r['date']}`\n\n"
        msg += f"[View Results]({URL})"

        send_telegram(msg)
        save_current(current)
    else:
        print("No new results.")

if __name__ == "__main__":
    main()
