import os
import logging
import requests
from flask import Flask, request, jsonify, abort
from threading import Thread

# ===== Logging =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== Flask App =====
app = Flask(__name__)

# ===== Environment Variables =====
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise RuntimeError("لطفاً متغیر محیطی TELEGRAM_TOKEN را ست کنید")

SECRET = os.environ.get("WEBHOOK_SECRET")
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

# ===== ذخیره پیام‌ها =====
user_messages = {}  # chat_id : {"user": [msg_id], "bot": [msg_id]}

def store_message(chat_id, msg_id, sender="bot"):
    user_messages.setdefault(chat_id, {"user": [], "bot": []})
    user_messages[chat_id][sender].append(msg_id)

# ===== ارسال پیام بات =====
def send_message(chat_id, text):
    def task():
        try:
            resp = requests.post(
                f"{TELEGRAM_API}/sendMessage",
                json={"chat_id": chat_id, "text": text}
            )
            if resp.ok:
                msg_id = resp.json()["result"]["message_id"]
                store_message(chat_id, msg_id, "bot")
        except Exception as e:
            logger.exception("Failed to send message: %s", e)
    Thread(target=task).start()

# ===== ارسال پنل با دکمه شیشه‌ای =====
def send_panel(chat_id):
    keyboard = {
        "inline_keyboard": [
             [{"text": " ", "callback_data": "noop"}],  # فاصله بالا
             [{"text": "❌ بستن", "callback_data": "close_panel"}],
             [{"text": " ", "callback_data": "noop"}],  # فاصله پایین
        ]
    }
    panel_text = "\n\n\n" + "پنل مدیریت" + "\n\n\n"  # چند خط خالی برای ایجاد فاصله
    photo_url = "https://ibb.co/6RnvrnHT"  # لینک عکس
    try:
        resp = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "photo": photo_url,
                "text": panel_text,
                "reply_markup": keyboard
            }
        )
        if resp.ok:
            msg_id = resp.json()["result"]["message_id"]
            store_message(chat_id, msg_id, "bot")
    except Exception as e:
        logger.exception("Failed to send panel: %s", e)

# ===== حذف پیام‌ها =====
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

# ===== ریست وبهوک =====
def reset_webhook():
    if not RENDER_URL:
        logger.warning("RENDER_EXTERNAL_URL تعریف نشده؛ احتمالاً روی لوکال اجرا می‌کنید.")
        return {"ok": False, "error": "No RENDER_EXTERNAL_URL found"}

    webhook_url = f"{RENDER_URL}/webhook"

    try:
        requests.post(f"{TELEGRAM_API}/deleteWebhook")
        set_resp = requests.post(f"{TELEGRAM_API}/setWebhook", json={"url": webhook_url})
        if not set_resp.ok:
            return {"ok": False, "error": set_resp.text}
        return {"ok": True, "url": webhook_url}
    except Exception as e:
        logger.exception("Error while resetting webhook: %s", e)
        return {"ok": False, "error": str(e)}

# ===== Routes =====
@app.route("/", methods=["GET"])
def index():
    return "Bot is running", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = request.get_json(force=True, silent=True)
        if not update:
            return jsonify(ok=True)

        # پیام معمولی
        if "message" in update:
            message = update["message"]
            chat_id = message["chat"]["id"]
            message_id = message["message_id"]
            text = message.get("text", "")

            # ذخیره پیام کاربر
            store_message(chat_id, message_id, "user")

            # دستورات
            if text == "حذف پیام ها":
                delete_last_messages(chat_id, count=5)
                send_message(chat_id, "تمام پیام‌ها حذف شدند ✅")
            elif text == "پنل":
                send_panel(chat_id)
            else:
                send_message(chat_id, f"دریافت شد: {text}")

        # callback از دکمه شیشه‌ای
        elif "callback_query" in update:
            callback = update["callback_query"]
            data = callback.get("data")
            if not data:
                return jsonify(ok=True)
            chat_id = callback["message"]["chat"]["id"]
            message_id = callback["message"]["message_id"]

            if data == "close_panel":
                try:
                    requests.post(
                        f"{TELEGRAM_API}/deleteMessage",
                        json={"chat_id": chat_id, "message_id": message_id}
                    )
                except Exception as e:
                    logger.exception("Failed to delete panel message: %s", e)

        return jsonify(ok=True)

    except Exception as e:
        logger.exception("Exception in /webhook: %s", e)
        return jsonify(ok=False), 500

@app.route("/reset-webhook", methods=["POST"])
def reset_webhook_route():
    token = request.headers.get("X-Auth-Token")
    if token != SECRET:
        abort(403, description="Forbidden: Invalid token")
    result = reset_webhook()
    return jsonify(result)

# ===== ست کردن وبهوک هنگام شروع =====
with app.app_context():
    reset_webhook()
