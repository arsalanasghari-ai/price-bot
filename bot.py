import requests
import os
import time
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
GOLDAPI_KEY = os.environ.get("GOLDAPI_KEY", "")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# ===================== قیمت‌ها =====================

def get_gold_price():
    try:
        headers = {"x-access-token": GOLDAPI_KEY}
        r = requests.get("https://www.goldapi.io/api/XAU/IRR", headers=headers, timeout=15)
        data = r.json()
        price_18k = float(data.get('price_gram_24k', 0)) * 0.75
        if 50_000_000 < price_18k < 600_000_000:
            return int(price_18k)
    except Exception as e:
        print(f"خطا طلا: {e}")
    return None

def get_usd_to_rial():
    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=15)
        data = r.json()
        rate = data['rates'].get('IRR', 0)
        if rate > 100000:
            return rate
    except Exception as e:
        print(f"خطا نرخ دلار: {e}")
    return 1_100_000

def get_crypto_prices_usd():
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin,tether", "vs_currencies": "usd"},
            timeout=15
        )
        data = r.json()
        btc = data.get('bitcoin', {}).get('usd')
        usdt = data.get('tether', {}).get('usd')
        return btc, usdt
    except Exception as e:
        print(f"خطا CoinGecko: {e}")
    return None, None

def build_price_message():
    gold = get_gold_price()
    usd_rial = get_usd_to_rial()
    btc_usd, usdt_usd = get_crypto_prices_usd()

    lines = ["💰 <b>قیمت لحظه‌ای بازار</b>\n"]

    if gold:
        lines.append(f"🟡 طلای ۱۸ عیار: <b>{gold:,} ریال</b>")
    else:
        lines.append("🟡 طلا: دریافت نشد")

    if btc_usd:
        lines.append(f"₿ بیت‌کوین: <b>{btc_usd:,.0f} دلار</b>")
    else:
        lines.append("₿ بیت‌کوین: دریافت نشد")

    if usdt_usd:
        tether_rial = int(usdt_usd * usd_rial)
        lines.append(f"💵 تتر: <b>{tether_rial:,} ریال</b>")
    else:
        lines.append("💵 تتر: دریافت نشد")

    lines.append(f"\n🕐 {time.strftime('%Y-%m-%d %H:%M')}")
    return "\n".join(lines)

# ===================== تلگرام =====================

def send_telegram(chat_id, message):
    url = f"{TELEGRAM_API}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)

@app.route("/", methods=["GET"])
def home():
    return "Bot is running!", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()
    print(f"Update: {update}")

    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")

        if text == "/price":
            msg = build_price_message()
            send_telegram(chat_id, msg)
        elif text == "/start":
            send_telegram(chat_id, "🤖 سلام! برای دریافت قیمت لحظه‌ای بازار دستور /price رو بفرست.")

    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
