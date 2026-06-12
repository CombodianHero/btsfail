"""
app.py
======
Single entrypoint for Koyeb: runs the Flask API (for health checks /
HTTP access) AND the Telegram bot (long polling) in the same process.

Koyeb Web Services require something listening on $PORT, so the Flask
app runs in a background thread while the Telegram bot polling runs
on the main thread.

Environment variables:
  TELEGRAM_BOT_TOKEN - your bot token from @BotFather (required)
  PORT               - set automatically by Koyeb
"""

import os
import logging
import threading

import main as flask_app
import bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("bridgetosuccess.app")


def run_flask():
    port = int(os.environ.get("PORT", 8000))
    flask_app.app.run(host="0.0.0.0", port=port, use_reloader=False)


def main():
    # Start the Flask health-check server in the background
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    log.info("Flask health server started on port %s", os.environ.get("PORT", 8000))

    # Run the Telegram bot on the main thread (blocking)
    bot.run_polling()


if __name__ == "__main__":
    main()
