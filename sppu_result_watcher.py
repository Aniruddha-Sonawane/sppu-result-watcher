import requests
from bs4 import BeautifulSoup
import json
import os
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL = "https://aniruddha-sonawane.github.io/SPPU-Result-Clone/"
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


def load_old():
    if not os.path.exists(DATA_FILE):
        return None
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_current(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": message,
        "disable_web_page_preview": True
    })


def main():
    current = fetch_results()
    old = load_old()

    # FIRST RUN: no file → send everything
    if old is None:
        msg = "📢 *SPPU RESULTS INITIAL SNAPSHOT*\n\n"
        for r in current:
            msg += f"• {r['course']}\n  {r['date']}\n\n"

        msg += "🔗 https://onlineresults.unipune.ac.in/SPPU"
        send_telegram(msg)
        save_current(current)
        return

    # Build sets and maps
    old_set = {(r["course"], r["date"]) for r in old}
    new_set = {(r["course"], r["date"]) for r in current}

    old_course_map = {r["course"]: r["date"] for r in old}
    new_course_map = {r["course"]: r["date"] for r in current}

    added = new_set - old_set
    deleted = old_set - new_set

    updated = []
    for course in old_course_map:
        if course in new_course_map:
            if old_course_map[course] != new_course_map[course]:
                updated.append((course, old_course_map[course], new_course_map[course]))

    if not added and not deleted and not updated:
        save_current(current)
        return

    # Build message
    msg = "📢 *SPPU RESULTS UPDATED*\n\n"

    if added:
        msg += "🆕 *New Results Added:*\n"
        for course, date in added:
            msg += f"• {course}\n  {date}\n"
        msg += "\n"

    if updated:
        msg += "✏️ *Results Updated:*\n"
        for course, old_d, new_d in updated:
            msg += f"• {course}\n  {old_d} → {new_d}\n"
        msg += "\n"

    if deleted:
        msg += "❌ *Results Removed:*\n"
        for course, date in deleted:
            msg += f"• {course}\n  {date}\n"
        msg += "\n"

    msg += "🔗 https://onlineresults.unipune.ac.in/SPPU"

    send_telegram(msg)
    save_current(current)


if __name__ == "__main__":
    main()
