import requests
import os
import time
import xml.etree.ElementTree as ET
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
GOLDAPI_KEY = os.environ.get("GOLDAPI_KEY", "")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# آدرس فایل تاریخچه قیمت در repo دیگر (gold-monitor) -- این فایل توسط
# GitHub Action هر ساعت آپدیت و commit می‌شود
TREND_URL = "https://raw.githubusercontent.com/arsalanasghari-ai/gold-monitor/main/price_history.json"

RSS_FEEDS = [
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.investing.com/rss/news_25.rss",
]
KEYWORDS = [
    "federal reserve", "fed", "interest rate", "rate hike", "rate cut",
    "oil", "crude", "opec", "gold", "inflation", "cpi",
    "recession", "gdp", "dollar", "bitcoin", "crypto"
]

# ===================== قیمت‌های لحظه‌ای =====================

def get_gold_price_and_ounce():
    """طلای ۱۸ عیار به ریال + اونس جهانی به دلار"""
    gold_18k = None
    ounce_usd = None
    try:
        headers = {"x-access-token": GOLDAPI_KEY}
        r = requests.get("https://www.goldapi.io/api/XAU/IRR", headers=headers, timeout=15)
        data = r.json()
        price_18k = float(data.get('price_gram_24k', 0)) * 0.75
        if 50_000_000 < price_18k < 600_000_000:
            gold_18k = int(price_18k)
    except Exception as e:
        print(f"خطا طلا (ریال): {e}")

    try:
        headers = {"x-access-token": GOLDAPI_KEY}
        r2 = requests.get("https://www.goldapi.io/api/XAU/USD", headers=headers, timeout=15)
        data2 = r2.json()
        ounce_usd = float(data2.get('price', 0))
        if not (500 < ounce_usd < 20000):
            ounce_usd = None
    except Exception as e:
        print(f"خطا اونس (دلار): {e}")

    return gold_18k, ounce_usd

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

# ===================== خواندن تاریخچه از GitHub =====================

def get_trend_label(key, current_price):
    """
    تاریخچه قیمت 30 ساعت اخیر را از GitHub می‌خواند و روند 24 ساعته را
    نسبت به قیمت فعلی محاسبه می‌کند.
    """
    try:
        r = requests.get(TREND_URL, timeout=10)
        if r.status_code != 200:
            return "داده تاریخچه هنوز در دسترس نیست"
        data = r.json()
        entries = data.get(key, [])
        if not entries:
            return "داده کافی برای روند ۲۴ ساعته هنوز ثبت نشده"

        now = time.time()
        old_price = None
        for ts, price in entries:
            if now - ts >= 20 * 3600:
                old_price = price
            else:
                break

        if old_price is None:
            # هنوز رکورد ۲۰+ ساعته نداریم، قدیمی‌ترین رکورد موجود را به کار ببریم
            old_price = entries[0][1]

        change = ((current_price - old_price) / old_price) * 100
        if change > 1:
            return f"📈 روند صعودی (نسبت به ~۲۴ ساعت قبل {change:+.2f}%)"
        elif change < -1:
            return f"📉 روند نزولی (نسبت به ~۲۴ ساعت قبل {change:+.2f}%)"
        else:
            return f"➡️ روند نسبتاً خنثی ({change:+.2f}%)"

    except Exception as e:
        print(f"خطا خواندن تاریخچه: {e}")
        return "محاسبه روند ممکن نشد"

# ===================== اخبار =====================

POSITIVE_WORDS = [
    "rise", "rises", "rising", "rose", "surge", "surges", "jump", "jumps",
    "gain", "gains", "rally", "rallies", "soar", "soars", "climb", "climbs",
    "boost", "boosts", "higher", "up", "increase", "increases", "strengthen",
    "record high", "advance", "advances"
]
NEGATIVE_WORDS = [
    "fall", "falls", "falling", "fell", "drop", "drops", "plunge", "plunges",
    "sink", "sinks", "slump", "slumps", "decline", "declines", "tumble",
    "tumbles", "lower", "down", "decrease", "decreases", "weaken", "cut",
    "cuts", "crash", "crashes", "worst", "loss", "losses"
]

def news_sentiment_score(news_titles, asset_key):
    """
    عناوین خبری مرتبط با یک دارایی را برای کلمات مثبت/منفی بررسی می‌کند.
    خروجی عددی است: مثبت = اخبار به سمت رشد اشاره دارند، منفی = به سمت کاهش.
    این صرفاً شمارش کلمات کلیدی ساده است، نه تحلیل واقعی معنایی.
    """
    keyword_map = {
        "gold_18k": ["gold"],
        "bitcoin": ["bitcoin", "crypto"],
        "tether": ["dollar", "fed", "inflation"],
    }
    kws = keyword_map.get(asset_key, [])
    score = 0
    matched_any = False

    for t in news_titles:
        t_lower = t.lower()
        if any(k in t_lower for k in kws):
            matched_any = True
            if any(pw in t_lower for pw in POSITIVE_WORDS):
                score += 1
            if any(nw in t_lower for nw in NEGATIVE_WORDS):
                score -= 1

    return score, matched_any

def get_momentum(key):
    """
    شتاب روند را با مقایسه تغییر ۱۲ ساعت اخیر نسبت به ۱۲ ساعت قبل از آن می‌سنجد.
    خروجی عددی است: مثبت = شتاب صعودی در حال افزایش، منفی = شتاب نزولی در حال افزایش.
    """
    try:
        r = requests.get(TREND_URL, timeout=10)
        if r.status_code != 200:
            return 0
        data = r.json()
        entries = data.get(key, [])
        if len(entries) < 3:
            return 0

        now = time.time()
        recent = [p for ts, p in entries if now - ts <= 12 * 3600]
        older = [p for ts, p in entries if 12 * 3600 < now - ts <= 24 * 3600]

        if len(recent) < 2 or len(older) < 2:
            return 0

        recent_change = (recent[-1] - recent[0]) / recent[0] * 100
        older_change = (older[-1] - older[0]) / older[0] * 100

        return recent_change - older_change
    except Exception as e:
        print(f"خطا محاسبه شتاب: {e}")
        return 0

def get_trend_change_value(key, current_price):
    """درصد تغییر نسبت به ~24 ساعت قبل را به‌صورت عددی برمی‌گرداند (نه فقط متن)."""
    try:
        r = requests.get(TREND_URL, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        entries = data.get(key, [])
        if not entries:
            return None

        now = time.time()
        old_price = None
        for ts, price in entries:
            if now - ts >= 20 * 3600:
                old_price = price
            else:
                break

        if old_price is None:
            old_price = entries[0][1]

        return ((current_price - old_price) / old_price) * 100
    except Exception as e:
        print(f"خطا محاسبه تغییر روند: {e}")
        return None

def simple_forecast_label(key, current_price, momentum, sentiment_score):
    """
    پیش‌بینی ساده و غیرقطعی بر اساس ترکیب سه عامل:
    ۱) روند واقعی ۲۴ ساعته (مهم‌ترین وزن)
    ۲) شتاب تغییرات قیمت (آیا روند تشدید یا تضعیف شده)
    ۳) لحن کلمات کلیدی در عناوین خبری مرتبط
    این یک تخمین آماری ضعیف است که دقتش در عمل نزدیک به شانس است، نه پیش‌بینی دقیق.
    """
    trend_change = get_trend_change_value(key, current_price)
    trend_component = 0
    if trend_change is not None:
        trend_component = max(min(trend_change, 5), -5) / 5  # نرمال‌سازی به بازه [-1, 1]

    score = trend_component * 1.0 + momentum * 0.4 + sentiment_score * 0.6

    if score > 0.5:
        return "📈 احتمال نسبی صعودی برای فردا"
    elif score < -0.5:
        return "📉 احتمال نسبی نزولی برای فردا"
    else:
        return "➡️ احتمال نسبی خنثی برای فردا (سیگنال واضحی در داده‌ها دیده نشد)"

def get_relevant_news(limit=2):
    titles = []
    for feed_url in RSS_FEEDS:
        try:
            r = requests.get(feed_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            root = ET.fromstring(r.content)
            for item in root.findall('.//item')[:15]:
                title = item.findtext('title', '')
                if any(kw in title.lower() for kw in KEYWORDS):
                    titles.append(title)
        except Exception as e:
            print(f"خطا RSS: {e}")
    return titles[:limit]

def translate_title(title):
    try:
        r = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": title, "langpair": "en|fa"},
            timeout=10
        )
        data = r.json()
        translated = data.get('responseData', {}).get('translatedText', '')
        if translated and translated.lower() != title.lower():
            return translated
    except Exception as e:
        print(f"خطا ترجمه: {e}")
    return title

# ===================== ساخت پیام =====================

def build_price_message():
    gold_18k, ounce_usd = get_gold_price_and_ounce()
    usd_rial = get_usd_to_rial()
    btc_usd, usdt_usd = get_crypto_prices_usd()
    news_titles = get_relevant_news(limit=8)

    lines = ["💰 <b>قیمت لحظه‌ای، روند و پیش‌بینی فردا</b>\n"]

    if gold_18k:
        trend = get_trend_label("gold_18k", gold_18k)
        momentum = get_momentum("gold_18k")
        sentiment, has_news = news_sentiment_score(news_titles, "gold_18k")
        forecast = simple_forecast_label("gold_18k", gold_18k, momentum, sentiment)
        lines.append(f"🟡 <b>طلای ۱۸ عیار:</b> {gold_18k:,} ریال")
        if ounce_usd:
            lines.append(f"   (اونس جهانی: {ounce_usd:,.2f} دلار)")
        lines.append(f"   روند: {trend}")
        lines.append(f"   فردا: {forecast}")
    else:
        lines.append("🟡 طلا: دریافت نشد")

    if btc_usd:
        trend = get_trend_label("bitcoin", btc_usd)
        momentum = get_momentum("bitcoin")
        sentiment, has_news = news_sentiment_score(news_titles, "bitcoin")
        forecast = simple_forecast_label("bitcoin", btc_usd, momentum, sentiment)
        lines.append(f"\n₿ <b>بیت‌کوین:</b> {btc_usd:,.0f} دلار")
        lines.append(f"   روند: {trend}")
        lines.append(f"   فردا: {forecast}")
    else:
        lines.append("\n₿ بیت‌کوین: دریافت نشد")

    if usdt_usd:
        tether_rial = int(usdt_usd * usd_rial)
        trend = get_trend_label("tether", tether_rial)
        momentum = get_momentum("tether")
        sentiment, has_news = news_sentiment_score(news_titles, "tether")
        forecast = simple_forecast_label("tether", tether_rial, momentum, sentiment)
        lines.append(f"\n💵 <b>تتر:</b> {tether_rial:,} ریال")
        lines.append(f"   روند: {trend}")
        lines.append(f"   فردا: {forecast}")
    else:
        lines.append("\n💵 تتر: دریافت نشد")

    if news_titles:
        lines.append("\n\n📰 <b>اخبار مرتبط با بازار:</b>")
        for n in news_titles[:2]:
            lines.append(f"• {translate_title(n)}")

    lines.append(
        "\n\n⚠️ <i>بخش «فردا» از ترکیب شتاب روند قیمت و لحن کلمات کلیدی در عناوین خبری "
        "محاسبه می‌شود؛ این صرفاً یک تخمین آماری ساده است، نه پیش‌بینی دقیق یا سیگنال معاملاتی. "
        "دقت این نوع تخمین در عمل نزدیک به شانس است و قیمت دارایی‌ها می‌تواند کاملاً خلاف آن "
        "حرکت کند. مسئولیت هر تصمیم خرید/فروش کاملاً با شماست.</i>"
    )
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
            send_telegram(chat_id, "🤖 سلام! برای دریافت قیمت و تحلیل روند بازار، دستور /price رو بفرست.")

    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
