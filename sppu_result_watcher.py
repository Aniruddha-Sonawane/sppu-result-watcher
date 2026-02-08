import requests
from bs4 import BeautifulSoup
import json
import os
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL = "https://onlineresults.unipune.ac.in/SPPU"
DATA_FILE = "known_results.json"

BOT_TOKEN = os.environ["BOT_TOKEN"] 
CHAT_ID = os.environ["CHAT_ID"]


# -------------------- SCRAPER --------------------

def fetch_results():
    r = requests.get(URL, timeout=20, verify=False)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    rows = soup.select("#tblRVList tbody tr")

    results = []
    for row in rows:
        cols = row.find_all("td")
        if len(cols) >= 3:
            results.append({
                "course": cols[1].get_text(strip=True),
                "date": cols[2].get_text(strip=True)
            })
    return results


# -------------------- STORAGE --------------------

def load_old():
    if not os.path.exists(DATA_FILE):
        return None
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_current(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# -------------------- TELEGRAM --------------------

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    })


def send_long_message(text):
    MAX = 4000  # Telegram hard limit is 4096
    for i in range(0, len(text), MAX):
        send_telegram(text[i:i + MAX])


# -------------------- MAIN LOGIC --------------------

def main():
    current = fetch_results()
    old = load_old()

    current_set = {(r["course"], r["date"]) for r in current}

    # ---------- FIRST RUN ----------
    if old is None:
        msg = "📢 *SPPU RESULTS – INITIAL SNAPSHOT*\n\n"
        for r in current:
            msg += f"• {r['course']}\n  {r['date']}\n\n"
        msg += "🔗 https://onlineresults.unipune.ac.in/SPPU"

        send_long_message(msg)
        save_current(current)
        return

    # ---------- DIFF LOGIC ----------
    old_set = {(r["course"], r["date"]) for r in old}

    added = current_set - old_set
    removed = old_set - current_set

    if not added and not removed:
        save_current(current)
        return

    # ---------- MESSAGE ----------
    msg = "📢 *SPPU RESULTS CHANGED*\n\n"

    if added:
        msg += "🆕 *Results Added:*\n"
        for course, date in added:
            msg += f"• {course}\n  {date}\n"
        msg += "\n"

    if removed:
        msg += "❌ *Results Removed:*\n"
        for course, date in removed:
            msg += f"• {course}\n  {date}\n"
        msg += "\n"

    msg += "🔗 https://onlineresults.unipune.ac.in/SPPU"

    send_long_message(msg)
    save_current(current)


if __name__ == "__main__":
    main()
