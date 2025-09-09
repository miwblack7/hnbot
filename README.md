# Telegram Bot with Flask on Render

این یک نمونه بات تلگرام ساده با Flask است که روی Render اجرا می‌شود.

## تنظیمات

1. در [@BotFather](https://t.me/botfather) یک بات بسازید و **توکن** را بردارید.
2. در Render یک **Web Service** بسازید:
   - Repository: این پروژه
   - Build Command: `pip install -r requirements.txt`
   - Start Command: از `Procfile` خوانده می‌شود.
3. متغیرهای محیطی را تنظیم کنید:
   - `TELEGRAM_TOKEN`: توکن بات از BotFather
   - `WEBHOOK_SECRET`: یک کلید قوی برای امنیت ریست وبهوک
4. بعد از Deploy، وبهوک به‌صورت خودکار تنظیم می‌شود.

## ریست دستی وبهوک
```bash
curl -X POST https://your-app.onrender.com/reset-webhook \
  -H "X-Auth-Token: YOUR_SECRET"
