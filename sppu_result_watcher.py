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
OFFSET_FILE = "tg_offset.json"

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

MAX_MSG = 4000  # Telegram hard limit

# -------------------- JSON UTILS --------------------

def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# -------------------- MARKDOWN HELPERS --------------------

def md_escape(text):
    return (
        text.replace("\\", "\\\\")
        .replace("_", "\\_")
        .replace("*", "\\*")
        .replace("[", "\\[")
        .replace("`", "\\`")
    )

# -------------------- TELEGRAM --------------------

def tg_send(chat_id, text):
    requests.post(f"{TG_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    })

def send_long_message(chat_id, text):
    for i in range(0, len(text), MAX_MSG):
        tg_send(chat_id, text[i:i + MAX_MSG])

def tg_get_updates(offset):
    r = requests.get(f"{TG_API}/getUpdates", params={
        "timeout": 0,
        "offset": offset
    })
    r.raise_for_status()
    return r.json()["result"]

def tg_get_member(chat_id):
    r = requests.get(f"{TG_API}/getChatMember", params={
        "chat_id": CHANNEL_ID,
        "user_id": chat_id
    })
    r.raise_for_status()
    return r.json()["result"]["status"]

# -------------------- /start STATUS HANDLER --------------------

def is_channel_match(chat):
    if not chat:
        return False
    channel_id = str(CHANNEL_ID)
    chat_id = str(chat.get("id"))
    if channel_id == chat_id:
        return True
    if channel_id.startswith("@"):
        return channel_id[1:] == (chat.get("username") or "")
    return False

def add_subscriber(subscribers, chat_id, username):
    if chat_id in subscribers:
        return False
    subscribers[chat_id] = {
        "username": username or "unknown",
        "joined_at": datetime.utcnow().isoformat()
    }
    return True

def process_updates(subscribers, offset_state):
    last_offset = offset_state.get("last_update_id", 0)
    updates = tg_get_updates(last_offset + 1)

    for u in updates:
        offset_state["last_update_id"] = u["update_id"]

        msg = u.get("message")
        if msg and msg.get("text", "").strip().startswith("/start"):
            chat_id = str(msg["chat"]["id"])
            channel_safe = md_escape(CHANNEL_ID)

            try:
                status = tg_get_member(chat_id)
            except Exception:
                status = "left"

            if status in ("member", "administrator", "creator"):
                added = add_subscriber(
                    subscribers,
                    chat_id,
                    msg["from"].get("username")
                )
                if added:
                    send_long_message(
                        chat_id,
                        "✅ *Access granted.* You will now receive SPPU result updates."
                    )
                else:
                    send_long_message(
                        chat_id,
                        "✅ *Access granted.* You already have access."
                    )
            else:
                send_long_message(
                    chat_id,
                    "👋 *Welcome!*\n\n"
                    "To get *SPPU result updates*, please join the official channel:\n\n"
                    f"{channel_safe}\n\n"
                    "Access will be granted automatically."
                )

        chat_member = u.get("chat_member")
        if chat_member and is_channel_match(chat_member.get("chat")):
            new_member = chat_member.get("new_chat_member", {})
            user = new_member.get("user", {})
            status = new_member.get("status")
            if status in ("member", "administrator", "creator"):
                chat_id = str(user.get("id"))
                added = add_subscriber(subscribers, chat_id, user.get("username"))
                if added:
                    send_long_message(
                        chat_id,
                        "✅ *Access granted.* You will now receive SPPU result updates."
                    )

# -------------------- MEMBERSHIP VERIFICATION --------------------

def verify_subscribers(subscribers):
    for chat_id in list(subscribers.keys()):
        try:
            status = tg_get_member(chat_id)
        except Exception:
            continue

        if status in ("left", "kicked"):
            send_long_message(
                chat_id,
                "❌ *Access revoked.* You left the channel.\n\n"
                "To regain access, please join the official channel:\n\n"
                f"{md_escape(CHANNEL_ID)}\n\n"
                "Then send /start again."
            )
            del subscribers[chat_id]

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

# -------------------- DIFF MESSAGES ONLY --------------------

def send_diffs(subscribers, current, old):
    if not old:
        return

    current_set = {(r["course"], r["date"]) for r in current}
    old_set = {(r["course"], r["date"]) for r in old}

    added = current_set - old_set
    removed = old_set - current_set

    if not added and not removed:
        return

    msg = "📢 *SPPU RESULTS UPDATED*\n\n"

    if added:
        msg += "🆕 *Added:*\n"
        for c, d in added:
            msg += f"• {c}\n  {d}\n"
        msg += "\n"

    if removed:
        msg += "❌ *Removed:*\n"
        for c, d in removed:
            msg += f"• {c}\n  {d}\n"
        msg += "\n"

    msg += "🔗 https://onlineresults.unipune.ac.in/SPPU"

    for chat_id in subscribers:
        send_long_message(chat_id, msg)

# -------------------- MAIN --------------------

def main():
    subscribers = load_json(SUBSCRIBERS_FILE, {})
    old_results = load_json(RESULTS_FILE, None)
    offset_state = load_json(OFFSET_FILE, {"last_update_id": 0})

    process_updates(subscribers, offset_state)
    verify_subscribers(subscribers)

    current_results = fetch_results()
    send_diffs(subscribers, current_results, old_results)

    save_json(SUBSCRIBERS_FILE, subscribers)
    save_json(RESULTS_FILE, current_results)
    save_json(OFFSET_FILE, offset_state)

if __name__ == "__main__":
    main()
