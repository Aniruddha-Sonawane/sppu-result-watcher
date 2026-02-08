import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# -------------------- CONFIG --------------------

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = os.environ["CHANNEL_ID"]

URL = "https://onlineresults.unipune.ac.in/SPPU"

BUFFER_FILE = "users_buffer.json"
SUBSCRIBERS_FILE = "subscribers.json"
RESULTS_FILE = "known_results.json"

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# -------------------- UTILS --------------------

def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def tg_send(chat_id, text):
    requests.post(f"{TG_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True
    })

def tg_get_updates(offset=None):
    params = {"timeout": 0}
    if offset:
        params["offset"] = offset
    r = requests.get(f"{TG_API}/getUpdates", params=params)
    r.raise_for_status()
    return r.json()["result"]

def tg_get_member(chat_id):
    r = requests.get(f"{TG_API}/getChatMember", params={
        "chat_id": CHANNEL_ID,
        "user_id": chat_id
    })
    r.raise_for_status()
    return r.json()["result"]["status"]

# -------------------- STEP 1: HANDLE /start --------------------

def process_start_commands(buffer):
    updates = tg_get_updates()
    for u in updates:
        msg = u.get("message")
        if not msg:
            continue

        text = msg.get("text", "")
        if text.strip() != "/start":
            continue

        chat_id = str(msg["chat"]["id"])
        username = msg["from"].get("username", "unknown")

        if chat_id in buffer:
            continue

        buffer[chat_id] = {
            "username": username,
            "requested_at": datetime.utcnow().isoformat()
        }

        tg_send(chat_id,
            "👋 Welcome!\n\n"
            "To get SPPU result updates, please join the official channel:\n\n"
            f"{CHANNEL_ID}\n\n"
            "Access will be granted automatically."
        )

# -------------------- STEP 2: VERIFY MEMBERSHIP --------------------

def verify_users(buffer, subscribers):
    # Check buffer → subscribers
    for chat_id in list(buffer.keys()):
        try:
            status = tg_get_member(chat_id)
        except Exception:
            continue

        if status in ("member", "administrator", "creator"):
            subscribers[chat_id] = {
                "username": buffer[chat_id]["username"],
                "joined_at": datetime.utcnow().isoformat()
            }
            tg_send(chat_id, "✅ Access granted. You will now receive SPPU result updates.")
            del buffer[chat_id]

    # Check subscribers → revoke
    for chat_id in list(subscribers.keys()):
        try:
            status = tg_get_member(chat_id)
        except Exception:
            continue

        if status in ("left", "kicked"):
            tg_send(chat_id, "❌ You left the channel. Access revoked.")
            del subscribers[chat_id]

# -------------------- STEP 3: SCRAPE RESULTS --------------------

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

# -------------------- STEP 4: SEND UPDATES --------------------

def send_updates(subscribers, current, old):
    current_set = {(r["course"], r["date"]) for r in current}
    old_set = {(r["course"], r["date"]) for r in old} if old else set()

    added = current_set - old_set
    removed = old_set - current_set

    if not added and not removed:
        return

    msg = "📢 *SPPU RESULTS UPDATED*\n\n"

    if added:
        msg += "🆕 Results Added:\n"
        for c, d in added:
            msg += f"• {c}\n  {d}\n"
        msg += "\n"

    if removed:
        msg += "❌ Results Removed:\n"
        for c, d in removed:
            msg += f"• {c}\n  {d}\n"
        msg += "\n"

    msg += "🔗 https://onlineresults.unipune.ac.in/SPPU"

    for chat_id in subscribers:
        tg_send(chat_id, msg)

# -------------------- MAIN --------------------

def main():
    buffer = load_json(BUFFER_FILE, {})
    subscribers = load_json(SUBSCRIBERS_FILE, {})
    old_results = load_json(RESULTS_FILE, None)

    process_start_commands(buffer)
    verify_users(buffer, subscribers)

    current_results = fetch_results()
    send_updates(subscribers, current_results, old_results)

    save_json(BUFFER_FILE, buffer)
    save_json(SUBSCRIBERS_FILE, subscribers)
    save_json(RESULTS_FILE, current_results)

if __name__ == "__main__":
    main()
