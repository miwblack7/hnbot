import os
import logging
import requests
from flask import Flask, request, jsonify, abort
from threading import Thread

# ====== تنظیمات logging ======
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ====== Flask App ======
app = Flask(__name__)

# ====== متغیرهای محیطی ======
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise RuntimeError("لطفاً متغیر محیطی TELEGRAM_TOKEN را ست کنید")

SECRET = os.environ.get("WEBHOOK_SECRET", "changeme")  # تغییر بده برای امنیت
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

# ====== تابع ارسال پیام آسنکرون ======
def send_message_async(chat_id, text):
    def task():
        try:
            requests.post(
                f"{TELEGRAM_API}/sendMessage",
                json={"chat_id": chat_id, "text": text}
            )
        except Exception as e:
            logger.exception("Failed to send message: %s", e)
    Thread(target=task).start()

# ذخیره پیام‌های کاربران و بات
user_messages = {}  # chat_id : {"user": [msg_id], "bot": [msg_id]}

def store_message(chat_id, msg_id, sender="bot"):
    user_messages.setdefault(chat_id, {"user": [], "bot": []})
    user_messages[chat_id][sender].append(msg_id)

def send_message_and_store(chat_id, text):
    resp = requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={"chat_id": chat_id, "text": text}
    )
    if resp.ok:
        msg_id = resp.json()["result"]["message_id"]
        store_message(chat_id, msg_id, "bot")

def delete_last_messages(chat_id, count=5):
    for sender in ["bot", "user"]:
        last_msgs = user_messages.get(chat_id, {}).get(sender, [])[-count:]
        for msg_id in last_msgs:
            try:
                requests.post(
                    f"{TELEGRAM_API}/deleteMessage",
                    json={"chat_id": chat_id, "message_id": msg_id}
                )
            except Exception as e:
                logger.exception("Failed to delete message: %s", e)
        # حذف از لیست
        if user_messages.get(chat_id):
            user_messages[chat_id][sender] = user_messages[chat_id][sender][:-count]


# ====== تابع ریست وبهوک ======
def reset_webhook():
    base_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not base_url:
        logger.warning("RENDER_EXTERNAL_URL تعریف نشده؛ احتمالاً روی لوکال اجرا می‌کنید.")
        return {"ok": False, "error": "No RENDER_EXTERNAL_URL found"}

    webhook_url = f"{base_url}/webhook"

    try:
        # حذف وبهوک قبلی
        requests.post(f"{TELEGRAM_API}/deleteWebhook")
        # ست کردن وبهوک جدید
        set_resp = requests.post(f"{TELEGRAM_API}/setWebhook", json={"url": webhook_url})
        if not set_resp.ok:
            return {"ok": False, "error": set_resp.text}
        return {"ok": True, "url": webhook_url}
    except Exception as e:
        logger.exception("Error while resetting webhook: %s", e)
        return {"ok": False, "error": str(e)}

# ====== Routes ======
@app.route("/", methods=["GET"])
def index():
    return "Bot is running", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(force=True, silent=True)
    logger.info("Received update: %s", update)

    message = update.get("message")
    
    if not message:
        return jsonify(ok=True)

    if message:
        chat_id = message["chat"]["id"]
        message_id = message["message_id"]
        text = message.get("text", "")

        # ذخیره پیام کاربر
        store_message(chat_id, message_id, "user")
    
        if text == "حذف پیام ها":
            delete_last_messages(chat_id, count=5)
            send_message_and_store(chat_id, "تمام پیام‌ها حذف شدند ✅")
        else:
            send_message_and_store(chat_id, f"دریافت شد: {text}")

        return jsonify(ok=True)

@app.route("/reset-webhook", methods=["POST"])
def reset_webhook_route():
    token = request.headers.get("X-Auth-Token")
    if token != SECRET:
        logger.warning("Unauthorized reset-webhook attempt!")
        abort(403, description="Forbidden: Invalid token")

    result = reset_webhook()
    return jsonify(result)

# ====== ست کردن وبهوک در Startup ======
with app.app_context():
    reset_webhook()
