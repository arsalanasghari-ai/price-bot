import requests
import os
import time
import xml.etree.ElementTree as ET
from flask import Flask, request

app = Flask(__name__)

VERSION = "2.0-no-goldapi"   # ← برای تشخیص اینکه کدام نسخه روی Render هست

TELEGRAM_TOKEN      = os.environ.get("TELEGRAM_TOKEN", "")
GOLDAPI_KEY         = os.environ.get("GOLDAPI_KEY", "")
METAL_PRICE_API_KEY = os.environ.get("METAL_PRICE_API_KEY", "")
COMMODITIES_API_KEY = os.environ.get("COMMODITIES_API_KEY", "")
TELEGRAM_API        = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

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

TROY_OUNCE_TO_GRAM = 31.1035
KARAT_18_FACTOR    = 0.75

print(f"[STARTUP] app.py version {VERSION} loaded")

# ===================== نرخ دلار =====================

def get_usd_to_rial():
    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=15)
        rate = r.json()['rates'].get('IRR', 0)
        if rate > 100000:
            print(f"[USD/IRR] {rate:,.0f}")
            return float(rate)
    except Exception as e:
        print(f"[USD/IRR] خطا: {e}")
    return 1_100_000

# ===================== دریافت اونس طلا — چند منبع =====================

def _xau_metals_live():
    try:
        r = requests.get("https://api.metals.live/v1/spot/gold", timeout=10)
        if r.status_code == 200:
            data = r.json()
            price = (data[0].get("price") or data[0].get("gold")) if isinstance(data, list) \
                    else (data.get("price") or data.get("gold"))
            if price and 500 < float(price) < 20000:
                print(f"[metals.live] ${float(price):,.2f}")
                return float(price)
    except Exception as e:
        print(f"[metals.live] خطا: {e}")
    return None

def _xau_metalpriceapi():
    if not METAL_PRICE_API_KEY:
        return None
    try:
        r = requests.get(
            f"https://api.metalpriceapi.com/v1/latest"
            f"?api_key={METAL_PRICE_API_KEY}&base=XAU&currencies=USD",
            timeout=10
        )
        if r.status_code == 200:
            price = float(r.json()["rates"]["USD"])
            if 500 < price < 20000:
                print(f"[metalpriceapi] ${price:,.2f}")
                return price
    except Exception as e:
        print(f"[metalpriceapi] خطا: {e}")
    return None

def _xau_commodities():
    if not COMMODITIES_API_KEY:
        return None
    try:
        r = requests.get(
            f"https://commodities-api.com/api/latest"
            f"?access_key={COMMODITIES_API_KEY}&base=USD&symbols=XAU",
            timeout=10
        )
        if r.status_code == 200:
            xau_per_usd = r.json()["data"]["rates"].get("XAU")
            if xau_per_usd:
                price = 1.0 / float(xau_per_usd)
                if 500 < price < 20000:
                    print(f"[commodities-api] ${price:,.2f}")
                    return price
    except Exception as e:
        print(f"[commodities-api] خطا: {e}")
    return None

def _xau_goldapi():
    if not GOLDAPI_KEY:
        return None
    try:
        r = requests.get(
            "https://www.goldapi.io/api/XAU/USD",
            headers={"x-access-token": GOLDAPI_KEY},
            timeout=15
        )
        if r.status_code == 200:
            price = float(r.json().get("price", 0))
            if 500 < price < 20000:
                print(f"[goldapi] ${price:,.2f}")
                return price
        else:
            print(f"[goldapi] {r.status_code}")
    except Exception as e:
        print(f"[goldapi] خطا: {e}")
    return None

def _xau_coingecko():
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=pax-gold&vs_currencies=usd",
            timeout=10
        )
        if r.status_code == 200:
            price = r.json().get("pax-gold", {}).get("usd")
            if price and 500 < float(price) < 20000:
                print(f"[PAXG/CoinGecko] ${float(price):,.2f}")
                return float(price)
    except Exception as e:
        print(f"[PAXG] خطا: {e}")
    return None

def get_gold_price_and_ounce():
    """اونس را از چند منبع می‌گیره، طلای ۱۸ عیار ریالی محاسبه می‌کنه"""
    print("[gold] شروع دریافت قیمت اونس...")
    xau_usd = (
        _xau_metals_live()   or
        _xau_metalpriceapi() or
        _xau_commodities()   or
        _xau_goldapi()       or
        _xau_coingecko()
    )
    if not xau_usd:
        print("[gold] ❌ هیچ منبعی کار نکرد")
        return None, None

    usd_rial = get_usd_to_rial()
    gold_18k = int((xau_usd / TROY_OUNCE_TO_GRAM) * KARAT_18_FACTOR * usd_rial)
    print(f"[gold] اونس=${xau_usd} | دلار={usd_rial:,.0f} | ۱۸ع={gold_18k:,}")

    if not (50_000_000 < gold_18k < 600_000_000):
        print(f"[gold] ⚠️ خارج از بازه: {gold_18k:,}")
        gold_18k = None

    return gold_18k, round(xau_usd, 2)

# ===================== کریپتو =====================

import requests
import os
import time
import xml.etree.ElementTree as ET
from flask import Flask, request

app = Flask(__name__)

VERSION = "2.0-no-goldapi"   # ← برای تشخیص اینکه کدام نسخه روی Render هست

TELEGRAM_TOKEN      = os.environ.get("TELEGRAM_TOKEN", "")
GOLDAPI_KEY         = os.environ.get("GOLDAPI_KEY", "")
METAL_PRICE_API_KEY = os.environ.get("METAL_PRICE_API_KEY", "")
COMMODITIES_API_KEY = os.environ.get("COMMODITIES_API_KEY", "")
TELEGRAM_API        = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

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

TROY_OUNCE_TO_GRAM = 31.1035
KARAT_18_FACTOR    = 0.75

print(f"[STARTUP] app.py version {VERSION} loaded")

# ===================== نرخ دلار =====================

def get_usd_to_rial():
    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=15)
        rate = r.json()['rates'].get('IRR', 0)
        if rate > 100000:
            print(f"[USD/IRR] {rate:,.0f}")
            return float(rate)
    except Exception as e:
        print(f"[USD/IRR] خطا: {e}")
    return 1_100_000

# ===================== دریافت اونس طلا — چند منبع =====================

def _xau_metals_live():
    try:
        r = requests.get("https://api.metals.live/v1/spot/gold", timeout=10)
        if r.status_code == 200:
            data = r.json()
            price = (data[0].get("price") or data[0].get("gold")) if isinstance(data, list) \
                    else (data.get("price") or data.get("gold"))
            if price and 500 < float(price) < 20000:
                print(f"[metals.live] ${float(price):,.2f}")
                return float(price)
    except Exception as e:
        print(f"[metals.live] خطا: {e}")
    return None

def _xau_metalpriceapi():
    if not METAL_PRICE_API_KEY:
        return None
    try:
        r = requests.get(
            f"https://api.metalpriceapi.com/v1/latest"
            f"?api_key={METAL_PRICE_API_KEY}&base=XAU&currencies=USD",
            timeout=10
        )
        if r.status_code == 200:
            price = float(r.json()["rates"]["USD"])
            if 500 < price < 20000:
                print(f"[metalpriceapi] ${price:,.2f}")
                return price
    except Exception as e:
        print(f"[metalpriceapi] خطا: {e}")
    return None

def _xau_commodities():
    if not COMMODITIES_API_KEY:
        return None
    try:
        r = requests.get(
            f"https://commodities-api.com/api/latest"
            f"?access_key={COMMODITIES_API_KEY}&base=USD&symbols=XAU",
            timeout=10
        )
        if r.status_code == 200:
            xau_per_usd = r.json()["data"]["rates"].get("XAU")
            if xau_per_usd:
                price = 1.0 / float(xau_per_usd)
                if 500 < price < 20000:
                    print(f"[commodities-api] ${price:,.2f}")
                    return price
    except Exception as e:
        print(f"[commodities-api] خطا: {e}")
    return None

def _xau_goldapi():
    if not GOLDAPI_KEY:
        return None
    try:
        r = requests.get(
            "https://www.goldapi.io/api/XAU/USD",
            headers={"x-access-token": GOLDAPI_KEY},
            timeout=15
        )
        if r.status_code == 200:
            price = float(r.json().get("price", 0))
            if 500 < price < 20000:
                print(f"[goldapi] ${price:,.2f}")
                return price
        else:
            print(f"[goldapi] {r.status_code}")
    except Exception as e:
        print(f"[goldapi] خطا: {e}")
    return None

def _xau_coingecko():
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=pax-gold&vs_currencies=usd",
            timeout=10
        )
        if r.status_code == 200:
            price = r.json().get("pax-gold", {}).get("usd")
            if price and 500 < float(price) < 20000:
                print(f"[PAXG/CoinGecko] ${float(price):,.2f}")
                return float(price)
    except Exception as e:
        print(f"[PAXG] خطا: {e}")
    return None

def get_gold_price_and_ounce():
    """اونس را از چند منبع می‌گیره، طلای ۱۸ عیار ریالی محاسبه می‌کنه"""
    print("[gold] شروع دریافت قیمت اونس...")
    xau_usd = (
        _xau_metals_live()   or
        _xau_metalpriceapi() or
        _xau_commodities()   or
        _xau_goldapi()       or
        _xau_coingecko()
    )
    if not xau_usd:
        print("[gold] ❌ هیچ منبعی کار نکرد")
        return None, None

    usd_rial = get_usd_to_rial()
    gold_18k = int((xau_usd / TROY_OUNCE_TO_GRAM) * KARAT_18_FACTOR * usd_rial)
    print(f"[gold] اونس=${xau_usd} | دلار={usd_rial:,.0f} | ۱۸ع={gold_18k:,}")

    if not (50_000_000 < gold_18k < 600_000_000):
        print(f"[gold] ⚠️ خارج از بازه: {gold_18k:,}")
        gold_18k = None

    return gold_18k, round(xau_usd, 2)

# ===================== کریپتو =====================

def get_crypto_prices_usd():
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin,tether", "vs_currencies": "usd"},
            timeout=15
        )
        data = r.json()
        return data.get('bitcoin', {}).get('usd'), data.get('tether', {}).get('usd')
    except Exception as e:
        print(f"[crypto] خطا: {e}")
    return None, None

# ===================== تاریخچه و روند =====================

def _fetch_trend_entries(key):
    r = requests.get(TREND_URL, timeout=10)
    if r.status_code != 200:
        return []
    return r.json().get(key, [])

def get_trend_label(key, current_price):
    try:
        entries = _fetch_trend_entries(key)
        if not entries:
            return "داده کافی برای روند ۲۴ ساعته هنوز ثبت نشده"
        now = time.time()
        old_price = next((p for ts, p in entries if now - ts >= 20 * 3600), entries[0][1])
        change = ((current_price - old_price) / old_price) * 100
        if change > 1:
            return f"📈 روند صعودی (~۲۴ ساعت: {change:+.2f}%)"
        elif change < -1:
            return f"📉 روند نزولی (~۲۴ ساعت: {change:+.2f}%)"
        else:
            return f"➡️ روند خنثی ({change:+.2f}%)"
    except Exception as e:
        print(f"[trend] خطا: {e}")
        return "محاسبه روند ممکن نشد"

def get_momentum(key):
    try:
        entries = _fetch_trend_entries(key)
        if len(entries) < 3:
            return 0
        now = time.time()
        recent = [p for ts, p in entries if now - ts <= 12 * 3600]
        older  = [p for ts, p in entries if 12 * 3600 < now - ts <= 24 * 3600]
        if len(recent) < 2 or len(older) < 2:
            return 0
        return (recent[-1] - recent[0]) / recent[0] * 100 - \
               (older[-1]  - older[0])  / older[0]  * 100
    except Exception as e:
        print(f"[momentum] خطا: {e}")
        return 0

def get_trend_change_value(key, current_price):
    try:
        entries = _fetch_trend_entries(key)
        if not entries:
            return None
        now = time.time()
        old_price = next((p for ts, p in entries if now - ts >= 20 * 3600), entries[0][1])
        return ((current_price - old_price) / old_price) * 100
    except Exception:
        return None

# ===================== اخبار و پیش‌بینی =====================

POSITIVE_WORDS = ["rise","rises","rising","rose","surge","surges","jump","jumps",
    "gain","gains","rally","rallies","soar","soars","climb","climbs",
    "boost","boosts","higher","up","increase","increases","strengthen",
    "record high","advance","advances"]
NEGATIVE_WORDS = ["fall","falls","falling","fell","drop","drops","plunge","plunges",
    "sink","sinks","slump","slumps","decline","declines","tumble",
    "tumbles","lower","down","decrease","decreases","weaken","cut",
    "cuts","crash","crashes","worst","loss","losses"]

def news_sentiment_score(news_titles, asset_key):
    keyword_map = {
        "gold_18k": ["gold"],
        "bitcoin":  ["bitcoin", "crypto"],
        "tether":   ["dollar", "fed", "inflation"],
    }
    kws = keyword_map.get(asset_key, [])
    score = 0
    matched_any = False
    for t in news_titles:
        t_lower = t.lower()
        if any(k in t_lower for k in kws):
            matched_any = True
            score += sum(1 for pw in POSITIVE_WORDS if pw in t_lower)
            score -= sum(1 for nw in NEGATIVE_WORDS if nw in t_lower)
    return score, matched_any

def simple_forecast_label(key, current_price, momentum, sentiment_score):
    trend_change = get_trend_change_value(key, current_price)
    if trend_change is not None:
        if trend_change > 1.5:
            return "📈 احتمال نسبی صعودی برای فردا"
        elif trend_change < -1.5:
            return "📉 احتمال نسبی نزولی برای فردا"
    trend_component = max(min(trend_change, 5), -5) / 5 if trend_change is not None else 0
    score = trend_component * 1.0 + momentum * 0.4 + sentiment_score * 0.6
    if score > 0.4:
        return "📈 احتمال نسبی صعودی برای فردا"
    elif score < -0.4:
        return "📉 احتمال نسبی نزولی برای فردا"
    return "➡️ احتمال نسبی خنثی برای فردا"

def get_relevant_news(limit=8):
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
            print(f"[RSS] خطا: {e}")
    return titles[:limit]

def translate_title(title):
    try:
        r = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": title, "langpair": "en|fa"},
            timeout=10
        )
        translated = r.json().get('responseData', {}).get('translatedText', '')
        if translated and translated.lower() != title.lower():
            return translated
    except Exception as e:
        print(f"[translate] خطا: {e}")
    return title

# ===================== ساخت پیام =====================

def build_price_message():
    print("[/price] شروع ساخت پیام...")
    gold_18k, ounce_usd = get_gold_price_and_ounce()
    usd_rial             = get_usd_to_rial()
    btc_usd, usdt_usd   = get_crypto_prices_usd()
    news_titles          = get_relevant_news(limit=8)

    lines = [f"💰 <b>قیمت لحظه‌ای، روند و پیش‌بینی فردا</b>\n"]

    # طلا
    if gold_18k:
        trend    = get_trend_label("gold_18k", gold_18k)
        momentum = get_momentum("gold_18k")
        sentiment, _ = news_sentiment_score(news_titles, "gold_18k")
        forecast = simple_forecast_label("gold_18k", gold_18k, momentum, sentiment)
        lines.append(f"🟡 <b>طلای ۱۸ عیار:</b> {gold_18k:,} ریال")
        if ounce_usd:
            lines.append(f"   (اونس جهانی: {ounce_usd:,.2f} دلار)")
        lines.append(f"   روند: {trend}")
        lines.append(f"   فردا: {forecast}")
    else:
        lines.append("🟡 طلا: دریافت نشد")

    # بیت‌کوین
    if btc_usd:
        trend    = get_trend_label("bitcoin", btc_usd)
        momentum = get_momentum("bitcoin")
        sentiment, _ = news_sentiment_score(news_titles, "bitcoin")
        forecast = simple_forecast_label("bitcoin", btc_usd, momentum, sentiment)
        lines.append(f"\n₿ <b>بیت‌کوین:</b> {btc_usd:,.0f} دلار")
        lines.append(f"   روند: {trend}")
        lines.append(f"   فردا: {forecast}")
    else:
        lines.append("\n₿ بیت‌کوین: دریافت نشد")

    # تتر
    if usdt_usd:
        tether_rial = int(usdt_usd * usd_rial)
        trend    = get_trend_label("tether", tether_rial)
        momentum = get_momentum("tether")
        sentiment, _ = news_sentiment_score(news_titles, "tether")
        forecast = simple_forecast_label("tether", tether_rial, momentum, sentiment)
        lines.append(f"\n💵 <b>تتر:</b> {tether_rial:,} ریال")
        lines.append(f"   روند: {trend}")
        lines.append(f"   فردا: {forecast}")
    else:
        lines.append("\n💵 تتر: دریافت نشد")

    # اخبار
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

    print("[/price] پیام آماده شد")
    return "\n".join(lines)

# ===================== تلگرام =====================

def send_telegram(chat_id, message):
    url = f"{TELEGRAM_API}/sendMessage"
    r = requests.post(
        url,
        data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
        timeout=10
    )
    print(f"[telegram] ok={r.json().get('ok')}")

@app.route("/", methods=["GET"])
def home():
    return f"Bot is running! version={VERSION}", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()
    print(f"[webhook] {update}")
    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text    = update["message"].get("text", "")
        if text == "/price":
            send_telegram(chat_id, build_price_message())
        elif text == "/start":
            send_telegram(chat_id,
                "🤖 سلام! برای دریافت قیمت و تحلیل روند بازار، دستور /price رو بفرست.")
        elif text == "/version":
            send_telegram(chat_id, f"🔧 نسخه: {VERSION}")
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# ===================== تاریخچه و روند =====================

def _fetch_trend_entries(key):
    r = requests.get(TREND_URL, timeout=10)
    if r.status_code != 200:
        return []
    return r.json().get(key, [])

def get_trend_label(key, current_price):
    try:
        entries = _fetch_trend_entries(key)
        if not entries:
            return "داده کافی برای روند ۲۴ ساعته هنوز ثبت نشده"
        now = time.time()
        old_price = next((p for ts, p in entries if now - ts >= 20 * 3600), entries[0][1])
        change = ((current_price - old_price) / old_price) * 100
        if change > 1:
            return f"📈 روند صعودی (~۲۴ ساعت: {change:+.2f}%)"
        elif change < -1:
            return f"📉 روند نزولی (~۲۴ ساعت: {change:+.2f}%)"
        else:
            return f"➡️ روند خنثی ({change:+.2f}%)"
    except Exception as e:
        print(f"[trend] خطا: {e}")
        return "محاسبه روند ممکن نشد"

def get_momentum(key):
    try:
        entries = _fetch_trend_entries(key)
        if len(entries) < 3:
            return 0
        now = time.time()
        recent = [p for ts, p in entries if now - ts <= 12 * 3600]
        older  = [p for ts, p in entries if 12 * 3600 < now - ts <= 24 * 3600]
        if len(recent) < 2 or len(older) < 2:
            return 0
        return (recent[-1] - recent[0]) / recent[0] * 100 - \
               (older[-1]  - older[0])  / older[0]  * 100
    except Exception as e:
        print(f"[momentum] خطا: {e}")
        return 0

def get_trend_change_value(key, current_price):
    try:
        entries = _fetch_trend_entries(key)
        if not entries:
            return None
        now = time.time()
        old_price = next((p for ts, p in entries if now - ts >= 20 * 3600), entries[0][1])
        return ((current_price - old_price) / old_price) * 100
    except Exception:
        return None

# ===================== اخبار و پیش‌بینی =====================

POSITIVE_WORDS = ["rise","rises","rising","rose","surge","surges","jump","jumps",
    "gain","gains","rally","rallies","soar","soars","climb","climbs",
    "boost","boosts","higher","up","increase","increases","strengthen",
    "record high","advance","advances"]
NEGATIVE_WORDS = ["fall","falls","falling","fell","drop","drops","plunge","plunges",
    "sink","sinks","slump","slumps","decline","declines","tumble",
    "tumbles","lower","down","decrease","decreases","weaken","cut",
    "cuts","crash","crashes","worst","loss","losses"]

def news_sentiment_score(news_titles, asset_key):
    keyword_map = {
        "gold_18k": ["gold"],
        "bitcoin":  ["bitcoin", "crypto"],
        "tether":   ["dollar", "fed", "inflation"],
    }
    kws = keyword_map.get(asset_key, [])
    score = 0
    matched_any = False
    for t in news_titles:
        t_lower = t.lower()
        if any(k in t_lower for k in kws):
            matched_any = True
            score += sum(1 for pw in POSITIVE_WORDS if pw in t_lower)
            score -= sum(1 for nw in NEGATIVE_WORDS if nw in t_lower)
    return score, matched_any

def simple_forecast_label(key, current_price, momentum, sentiment_score):
    trend_change = get_trend_change_value(key, current_price)
    if trend_change is not None:
        if trend_change > 1.5:
            return "📈 احتمال نسبی صعودی برای فردا"
        elif trend_change < -1.5:
            return "📉 احتمال نسبی نزولی برای فردا"
    trend_component = max(min(trend_change, 5), -5) / 5 if trend_change is not None else 0
    score = trend_component * 1.0 + momentum * 0.4 + sentiment_score * 0.6
    if score > 0.4:
        return "📈 احتمال نسبی صعودی برای فردا"
    elif score < -0.4:
        return "📉 احتمال نسبی نزولی برای فردا"
    return "➡️ احتمال نسبی خنثی برای فردا"

def get_relevant_news(limit=8):
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
            print(f"[RSS] خطا: {e}")
    return titles[:limit]

def translate_title(title):
    try:
        r = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": title, "langpair": "en|fa"},
            timeout=10
        )
        translated = r.json().get('responseData', {}).get('translatedText', '')
        if translated and translated.lower() != title.lower():
            return translated
    except Exception as e:
        print(f"[translate] خطا: {e}")
    return title

# ===================== ساخت پیام =====================

def build_price_message():
    print("[/price] شروع ساخت پیام...")
    gold_18k, ounce_usd = get_gold_price_and_ounce()
    usd_rial             = get_usd_to_rial()
    btc_usd, usdt_usd   = get_crypto_prices_usd()
    news_titles          = get_relevant_news(limit=8)

    lines = [f"💰 <b>قیمت لحظه‌ای، روند و پیش‌بینی فردا</b>\n"]

    # طلا
    if gold_18k:
        trend    = get_trend_label("gold_18k", gold_18k)
        momentum = get_momentum("gold_18k")
        sentiment, _ = news_sentiment_score(news_titles, "gold_18k")
        forecast = simple_forecast_label("gold_18k", gold_18k, momentum, sentiment)
        lines.append(f"🟡 <b>طلای ۱۸ عیار:</b> {gold_18k:,} ریال")
        if ounce_usd:
            lines.append(f"   (اونس جهانی: {ounce_usd:,.2f} دلار)")
        lines.append(f"   روند: {trend}")
        lines.append(f"   فردا: {forecast}")
    else:
        lines.append("🟡 طلا: دریافت نشد")

    # بیت‌کوین
    if btc_usd:
        trend    = get_trend_label("bitcoin", btc_usd)
        momentum = get_momentum("bitcoin")
        sentiment, _ = news_sentiment_score(news_titles, "bitcoin")
        forecast = simple_forecast_label("bitcoin", btc_usd, momentum, sentiment)
        lines.append(f"\n₿ <b>بیت‌کوین:</b> {btc_usd:,.0f} دلار")
        lines.append(f"   روند: {trend}")
        lines.append(f"   فردا: {forecast}")
    else:
        lines.append("\n₿ بیت‌کوین: دریافت نشد")

    # تتر
    if usdt_usd:
        tether_rial = int(usdt_usd * usd_rial)
        trend    = get_trend_label("tether", tether_rial)
        momentum = get_momentum("tether")
        sentiment, _ = news_sentiment_score(news_titles, "tether")
        forecast = simple_forecast_label("tether", tether_rial, momentum, sentiment)
        lines.append(f"\n💵 <b>تتر:</b> {tether_rial:,} ریال")
        lines.append(f"   روند: {trend}")
        lines.append(f"   فردا: {forecast}")
    else:
        lines.append("\n💵 تتر: دریافت نشد")

    # اخبار
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

    print("[/price] پیام آماده شد")
    return "\n".join(lines)

# ===================== تلگرام =====================

def send_telegram(chat_id, message):
    url = f"{TELEGRAM_API}/sendMessage"
    r = requests.post(
        url,
        data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
        timeout=10
    )
    print(f"[telegram] ok={r.json().get('ok')}")

@app.route("/", methods=["GET"])
def home():
    return f"Bot is running! version={VERSION}", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()
    print(f"[webhook] {update}")
    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text    = update["message"].get("text", "")
        if text == "/price":
            send_telegram(chat_id, build_price_message())
        elif text == "/start":
            send_telegram(chat_id,
                "🤖 سلام! برای دریافت قیمت و تحلیل روند بازار، دستور /price رو بفرست.")
        elif text == "/version":
            send_telegram(chat_id, f"🔧 نسخه: {VERSION}")
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
