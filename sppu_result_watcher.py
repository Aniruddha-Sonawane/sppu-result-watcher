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


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }
    requests.post(url, json=payload)


def load_old():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_current(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def main():
    current = fetch_results()
    old = load_old()

    if not old:
        save_current(current)
        return

    old_set = {(r["course"], r["date"]) for r in old}
    new_items = [
        r for r in current
        if (r["course"], r["date"]) not in old_set
    ]

    if new_items:
        msg = "📢 *NEW SPPU RESULT ADDED*\n\n"
        for r in new_items:
            msg += f"• {r['course']}\n  {r['date']}\n\n"
        msg += "🔗 https://onlineresults.unipune.ac.in/SPPU"

        send_telegram(msg)
        save_current(current)


if __name__ == "__main__":
    main()
