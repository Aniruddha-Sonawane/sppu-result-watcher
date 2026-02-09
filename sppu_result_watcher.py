import requests
from bs4 import BeautifulSoup
import json
import os
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Suppress only the insecure SSL warning (safe for public scraping)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL = "https://onlineresults.unipune.ac.in/SPPU"
DATA_FILE = "known_results.json"

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]


# -------------------- SESSION WITH RETRY --------------------

def create_session():
    session = requests.Session()

    retry = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )

    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    })

    return session


session = create_session()


# -------------------- SCRAPER --------------------

def fetch_results():
    try:
        r = session.get(
            URL,
            timeout=(10, 60),
            verify=False   # Required due to broken SSL chain on SPPU server
        )
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("⚠ Fetch failed:", e)
        return None

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

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_current(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# -------------------- TELEGRAM --------------------

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        session.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            },
            timeout=(5, 20)
        )
    except requests.exceptions.RequestException as e:
        print("⚠ Telegram send failed:", e)


def send_long_message(text):
    MAX = 4000  # Telegram hard limit is 4096
    for i in range(0, len(text), MAX):
        send_telegram(text[i:i + MAX])


# -------------------- MAIN LOGIC --------------------

def main():
    current = fetch_results()

    # If fetch failed, do NOT crash workflow
    if current is None:
        print("⚠ Skipping update due to fetch failure.")
        return

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
        print("No changes detected.")
        save_current(current)
        return

    # ---------- MESSAGE ----------
    msg = "📢 *SPPU RESULTS UPDATED*\n\n"

    if added:
        msg += "🆕 *Results Added:*\n"
        for course, date in sorted(added):
            msg += f"• {course}\n  {date}\n"
        msg += "\n"

    if removed:
        msg += "❌ *Results Removed:*\n"
        for course, date in sorted(removed):
            msg += f"• {course}\n  {date}\n"
        msg += "\n"

    msg += "🔗 https://onlineresults.unipune.ac.in/SPPU"

    send_long_message(msg)
    save_current(current)


if __name__ == "__main__":
    main()
