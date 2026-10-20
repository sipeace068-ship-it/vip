import os
import json
import logging
import time
import threading
from datetime import datetime
from flask import Flask, jsonify
import requests

# === CONFIGURATION ===
TOKEN = os.environ.get('BOT_TOKEN')
PORT = int(os.environ.get('PORT', 8080))
DATA_FILE = 'cybersafe_users.json'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === STORAGE ===
class Storage:
    def __init__(self, filename=DATA_FILE):
        self.filename = filename
        self.data = self._load_data()

    def _load_data(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_data(self):
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Save error: {e}")

    def get_user(self, user_id):
        if user_id not in self.data:
            self.data[user_id] = {
                'user_id': user_id,
                'joined_at': datetime.now().isoformat(),
                'username': '',
                'first_name': ''
            }
            self._save_data()
        return self.data[user_id]

    def save_user(self, user_id, data):
        self.data[user_id] = data
        self._save_data()

    def get_all_users(self):
        return self.data

storage = Storage()

# === TELEGRAM API ===
def send_message(chat_id, text, parse_mode='Markdown'):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode
        }, timeout=10)
    except Exception as e:
        logger.error(f"Send error: {e}")

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    params = {'timeout': 30}
    if offset:
        params['offset'] = offset
    try:
        r = requests.get(url, params=params, timeout=35)
        if r.status_code == 200:
            return r.json().get('result', [])
    except Exception as e:
        logger.error(f"Get updates error: {e}")
    return []

def delete_webhook():
    try:
        requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook", timeout=10)
    except:
        pass

# === CONTENT ===
TIPS = [
    "🔒 *Use a Password Manager:* Never reuse passwords. Use a manager like Bitwarden to generate strong, unique passwords for every site.",
    "📱 *Enable 2FA:* Turn on Two-Factor Authentication (2FA) for your email, social media, and bank accounts. It blocks 99% of automated attacks.",
    "🎣 *Spot Phishing:* Never click links in unexpected emails or texts. Hover over links to see the real URL before clicking.",
    "🔄 *Update Software:* Always install the latest security updates for your phone and computer. Updates fix known vulnerabilities.",
    "🌐 *Check App Permissions:* Review your phone's app permissions. Does a flashlight app really need access to your contacts? Revoke unnecessary access.",
    "💳 *Shop Securely:* Only enter payment details on websites that have a padlock icon (HTTPS) in the address bar.",
    "📶 *Avoid Public Wi-Fi:* Public Wi-Fi is unencrypted. Use a VPN if you must access sensitive data like banking on public networks.",
    "🧹 *Clear Old Data:* Regularly delete old emails, texts, and files you no longer need to minimize the impact if an account is breached.",
    "👤 *Limit Oversharing:* Be careful what you post on social media. Hackers use birthdays, pet names, and locations to guess passwords or answer security questions.",
    "🔑 *Secure Your Router:* Change the default administrator password on your home Wi-Fi router. Most people never do this."
]

def get_daily_tip():
    day_index = datetime.now().timetuple().tm_yday
    return TIPS[day_index % len(TIPS)]

# === HANDLERS ===
def handle_start(chat_id, user_data):
    user_id = str(chat_id)
    user = storage.get_user(user_id)
    user['username'] = user_data.get('username', '')
    user['first_name'] = user_data.get('first_name', 'Friend')
    storage.save_user(user_id, user)

    welcome = f"""
🛡️ Welcome to *CyberSafe Daily*, {user['first_name']}!

Your daily source for digital security and privacy tips. Stay informed, stay protected.

📌 *Today's Tip:*
{get_daily_tip()}

📋 *Commands:*
/tip - Get today's security tip
/checklist - View your security checklist
/help - Show help menu
    """
    send_message(chat_id, welcome)

def handle_tip(chat_id):
    send_message(
        chat_id,
        f"""
📌 *Today's Cyber Security Tip*

{get_daily_tip()}

Check back tomorrow for a new tip.
        """
    )

def handle_checklist(chat_id):
    send_message(
        chat_id,
        """
✅ *Your Basic Security Checklist*

1. Use a password manager.
2. Enable 2FA everywhere.
3. Update your devices.
4. Review app permissions.
5. Never reuse passwords.
6. Use a VPN on public Wi-Fi.

How many have you completed?
        """
    )

def handle_help(chat_id):
    send_message(
        chat_id,
        """
📚 *CyberSafe Daily — Help*

*Commands:*
/start - Start the bot
/tip - Get today's tip
/checklist - View security checklist
/help - Show this help menu

This bot provides daily digital security awareness tips.
        """
    )

# === POLLING ===
def process_updates():
    last_update_id = 0
    delete_webhook()
    logger.info("Polling started...")

    while True:
        try:
            updates = get_updates(last_update_id + 1 if last_update_id else None)
            for update in updates:
                uid = update.get('update_id')
                if uid:
                    last_update_id = uid

                if 'message' in update:
                    msg = update['message']
                    chat_id = msg['chat']['id']
                    user_data = msg.get('from', {})

                    if 'text' in msg:
                        text = msg['text']

                        if text.startswith('/start'):
                            handle_start(chat_id, user_data)
                        elif text.startswith('/tip'):
                            handle_tip(chat_id)
                        elif text.startswith('/checklist'):
                            handle_checklist(chat_id)
                        elif text.startswith('/help'):
                            handle_help(chat_id)
                        else:
                            send_message(
                                chat_id,
                                "Command not recognized. Use /help to see available commands."
                            )
            time.sleep(2)
        except Exception as e:
            logger.error(f"Process updates error: {e}")
            time.sleep(5)

# === FLASK ===
app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    users = storage.get_all_users()
    return f"<h1>CyberSafe Daily Bot</h1><p>Users: {len(users)}</p><p>Status: Active</p>"

@app.route('/stats', methods=['GET'])
def stats():
    users = storage.get_all_users()
    return jsonify({'users': len(users)})

# === MAIN ===
def main():
    logger.info("Starting CyberSafe Daily Bot...")
    threading.Thread(target=process_updates, daemon=True).start()
    app.run(host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    main()
