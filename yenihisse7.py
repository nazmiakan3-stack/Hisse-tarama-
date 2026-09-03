#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import html
import requests
import feedparser
from datetime import datetime
from tradingview_ta import TA_Handler, Interval

# ============================================================
# TELEGRAM
# ============================================================
# Güvenlik: gerçek tokenı kod içine yazmak yerine ortam değişkeni kullan.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ============================================================
# TARAMA AYARLARI
# ============================================================
SCAN_MINUTES = 15

# Artık BIST 30 da taranıyor.
BIST_30_SET = {
    "AKBNK", "ALARK", "ASELS", "ASTOR", "BIMAS", "BRSAN", "DOAS", "EKGYO",
    "ENKAI", "EREGL", "FROTO", "GARAN", "GUBRF", "HEKTS", "ISCTR", "KCHOL",
    "KONTR", "KOZAL", "KRDMD", "ODAS", "OYAKC", "PETKM", "PGSUS", "SAHOL",
    "SASA", "SISE", "TCELL", "THYAO", "TOASO", "TUPRS"
}

TARGET_STOCKS = [
    "MAGEN", "ALFAS", "EUPWR", "CWENE", "MIATK", "SMRTG", "SDTTR", "REEDR",
    "GESAN", "PENTA", "YEOTK", "KOTON", "AGROT", "TABGD", "FORTE", "ATAKP",
    "GOKNR", "BINBN", "ENERY", "TETMT", "MOBTL", "BARMA", "KBORU", "KAYSE",
    "CVMEK", "BOBET", "PLTUR"
]

ALL_STOCKS = sorted(BIST_30_SET | set(TARGET_STOCKS))

# ============================================================
# STRATEJİ PARAMETRELERİ
# ============================================================
RSI_DIP_LIMIT = 30
RSI_DEEP_DIP = 25

RSI_MOMENTUM_MIN = 55
CHANGE_MOMENTUM_MIN = 2.0

# Hacim / ortalama hacim oranı
VOLUME_SPIKE_MIN = 1.20
VOLUME_STRONG_MIN = 1.80

# Çoklu zaman dilimi
TIMEFRAMES = {
    "1H": Interval.INTERVAL_1_HOUR,
    "4H": Interval.INTERVAL_4_HOURS,
    "1D": Interval.INTERVAL_1_DAY,
}

# Aynı hisse için aynı sinyali tekrar tekrar Telegram'a göndermeyi azaltır.
LAST_ALERTS = {}

# ============================================================
# TELEGRAM
# ============================================================
def send_telegram_msg(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("\n[TELEGRAM KAPALI]\n" + message + "\n")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
    except Exception as exc:
        print(f"Telegram Gönderim Hatası: {exc}")


def send_once(key, message, cooldown_minutes=60):
    now = time.time()
    last = LAST_ALERTS.get(key, 0)

    if now - last >= cooldown_minutes * 60:
        send_telegram_msg(message)
        LAST_ALERTS[key] = now

# ============================================================
# TRADINGVIEW
# ============================================================
def analyze_tv_stock(symbol, interval):
    try:
        handler = TA_Handler(
            symbol=symbol,
            screener="turkey",
            exchange="BIST",
            interval=interval,
        )

        analysis = handler.get_analysis()
        ind = analysis.indicators
        summary = analysis.summary

        close = ind.get("close")
        change = ind.get("change")
        rsi = ind.get("RSI")
        volume = ind.get("volume")

        # TradingView bazı zaman dilimlerinde hacim ortalamasını farklı
        # isimlerle döndürebilir. Bulunamazsa hacim oranı hesaplanmaz.
        vol_ma20 = (
            ind.get("volume_ma")
            or ind.get("volume_sma")
            or ind.get("Volume SMA")
        )

        volume_ratio = None
        if volume is not None and vol_ma20 not in (None, 0):
            volume_ratio = volume / vol_ma20

        return {
            "close": close,
            "change": change,
            "rsi": rsi,
            "volume": volume,
            "volume_ma20": vol_ma20,
            "volume_ratio": volume_ratio,
            "recommendation": summary.get("RECOMMENDATION", "N/A"),
            "buy": summary.get("BUY", 0),
            "sell": summary.get("SELL", 0),
            "neutral": summary.get("NEUTRAL", 0),
        }

    except Exception as exc:
        print(f"{symbol} {interval} veri hatası: {exc}")
        return None


def get_all_timeframes(symbol):
    result = {}

    for name, interval in TIMEFRAMES.items():
        data = analyze_tv_stock(symbol, interval)
        if data:
            result[name] = data

    return result

# ============================================================
# YARDIMCI
# ============================================================
def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def recommendation_score(rec):
    return {
        "STRONG_BUY": 2,
        "BUY": 1,
        "NEUTRAL": 0,
        "SELL": -1,
        "STRONG_SELL": -2,
    }.get(rec, 0)


def volume_text(ratio):
    if ratio is None:
        return "Hacim oranı: veri yok"

    if ratio >= VOLUME_STRONG_MIN:
        return f"Hacim: {ratio:.2f}x ortalama 🔥"
    if ratio >= VOLUME_SPIKE_MIN:
        return f"Hacim: {ratio:.2f}x ortalama 📈"
    return f"Hacim: {ratio:.2f}x ortalama"


def momentum_score(data):
    """
    Tavan tahmini yerine puanlama yapılır.
    Maksimum 10 puan:
      +2 günlük RSI >= 55
      +2 günlük değişim >= %2
      +2 1H BUY/STRONG_BUY
      +2 4H BUY/STRONG_BUY
      +1 1D BUY/STRONG_BUY
      +1 hacim >= 1.2x
    """

    d1 = data.get("1D")
    h4 = data.get("4H")
    h1 = data.get("1H")

    if not d1:
        return 0

    score = 0

    if safe_float(d1.get("rsi")) >= RSI_MOMENTUM_MIN:
        score += 2

    if safe_float(d1.get("change")) >= CHANGE_MOMENTUM_MIN:
        score += 2

    if h1 and recommendation_score(h1.get("recommendation")) > 0:
        score += 2

    if h4 and recommendation_score(h4.get("recommendation")) > 0:
        score += 2

    if recommendation_score(d1.get("recommendation")) > 0:
        score += 1

    ratio = d1.get("volume_ratio")
    if ratio is not None and ratio >= VOLUME_SPIKE_MIN:
        score += 1

    return score


def momentum_stars(score, volume_ratio):
    if score >= 9 and volume_ratio is not None and volume_ratio >= VOLUME_STRONG_MIN:
        return "⭐⭐⭐⭐⭐"
    if score >= 8:
        return "⭐⭐⭐⭐"
    if score >= 6:
        return "⭐⭐⭐"
    if score >= 4:
        return "⭐⭐"
    return "⭐"


def dip_stars(rsi):
    if rsi <= 15:
        return "⭐⭐⭐⭐⭐"
    if rsi <= 20:
        return "⭐⭐⭐⭐"
    if rsi <= 25:
        return "⭐⭐⭐"
    return "⭐⭐"

# ============================================================
# KAP
# ============================================================
KAP_KEYWORDS = {
    "bedelsiz": (5, "Bedelsiz / Sermaye Artırımı"),
    "sermaye artır": (5, "Sermaye Artırımı"),
    "yeni iş ilişkisi": (5, "Yeni İş İlişkisi"),
    "iş ilişkisi": (4, "Yeni İş İlişkisi"),
    "ortaklık": (5, "Ortaklık / Stratejik İş Birliği"),
    "m&a": (5, "Birleşme / Satın Alma"),
    "ihale": (4, "İhale"),
    "sipariş": (4, "Sipariş"),
    "pay alım": (4, "Pay Geri Alımı"),
    "geri alım": (4, "Pay Geri Alımı"),
    "sözleşme": (3, "Sözleşme"),
}

PROCESSED_KAP_LINKS = set()


def kap_score(title, summary):
    text = f"{title} {summary}".lower()
    hits = []

    for key, (score, category) in KAP_KEYWORDS.items():
        if key in text:
            hits.append((score, category))

    if not hits:
        return 0, []

    # Aynı haber içinde tekrarlanan benzer kelimeler puanı sınırsız artırmasın.
    best_by_category = {}
    for score, category in hits:
        best_by_category[category] = max(
            best_by_category.get(category, 0), score
        )

    total = min(sum(best_by_category.values()), 10)
    return total, list(best_by_category.items())


def check_kap_news():
    try:
        feed = feedparser.parse("https://www.kap.org.tr/tr/rss")

        for entry in feed.entries[:30]:
            link = getattr(entry, "link", "")
            if not link or link in PROCESSED_KAP_LINKS:
                continue

            title = getattr(entry, "title", "")
            summary = getattr(entry, "summary", "")

            score, categories = kap_score(title, summary)

            # Yalnızca anlamlı puanı olan haberleri bildir.
            if score < 4:
                continue

            PROCESSED_KAP_LINKS.add(link)

            stars = "⭐" * min(5, max(1, (score + 1) // 2))
            category_text = ", ".join(cat for _, cat in categories)

            msg = (
                f"📰 <b>KAP ÖNEMLİ HABER</b>\n\n"
                f"<b>Etki:</b> {stars} ({score}/10)\n"
                f"<b>Kategori:</b> {html.escape(category_text)}\n"
                f"<b>Başlık:</b> {html.escape(title)}\n"
                f"<a href='{html.escape(link, quote=True)}'>KAP Bildirim Detayı</a>"
            )

            send_once(f"KAP:{link}", msg, cooldown_minutes=1440)

    except Exception as exc:
        print(f"KAP Kontrol Hatası: {exc}")

# ============================================================
# HİSSE TARAMA
# ============================================================
def scan_stock(symbol):
    data = get_all_timeframes(symbol)

    if not data:
        return

    daily = data.get("1D")
    if not daily or daily.get("close") is None or daily.get("rsi") is None:
        return

    price = safe_float(daily.get("close"))
    rsi = safe_float(daily.get("rsi"))
    change = safe_float(daily.get("change"))
    rec = daily.get("recommendation", "N/A")
    volume_ratio = daily.get("volume_ratio")

    # --------------------------------------------------------
    # 1) DİP & DEĞER
    # --------------------------------------------------------
    if rsi <= RSI_DIP_LIMIT:
        stars = dip_stars(rsi)

        msg = (
            f"🛡️ <b>DİP & DEĞER ADAYI</b>\n\n"
            f"<b>Hisse:</b> #{symbol}\n"
            f"<b>Derece:</b> {stars}\n"
            f"<b>Fiyat:</b> {price:.2f} TL\n"
            f"<b>Günlük değişim:</b> %{change:+.2f}\n"
            f"<b>RSI(14):</b> {rsi:.1f}\n"
            f"<b>1D TV:</b> {rec}\n"
            f"<b>{volume_text(volume_ratio)}</b>\n\n"
            f"<b>Strateji:</b> Aşırı satım bölgesi; "
            f"tek başına alım garantisi değildir."
        )

        send_once(f"DIP:{symbol}", msg)

    # --------------------------------------------------------
    # 2) ÇOKLU ZAMAN DİLİMLİ MOMENTUM / TAVAN ADAYI
    # --------------------------------------------------------
    score = momentum_score(data)

    if score >= 6:
        stars = momentum_stars(score, volume_ratio)

        h1rec = data.get("1H", {}).get("recommendation", "N/A")
        h4rec = data.get("4H", {}).get("recommendation", "N/A")

        msg = (
            f"🚀 <b>GÜÇLÜ MOMENTUM / TAVAN ADAYI</b>\n\n"
            f"<b>Hisse:</b> #{symbol}\n"
            f"<b>Skor:</b> {score}/10 {stars}\n"
            f"<b>Fiyat:</b> {price:.2f} TL\n"
            f"<b>Günlük değişim:</b> %{change:+.2f}\n"
            f"<b>1D RSI:</b> {rsi:.1f}\n"
            f"<b>1H TV:</b> {h1rec}\n"
            f"<b>4H TV:</b> {h4rec}\n"
            f"<b>1D TV:</b> {rec}\n"
            f"<b>{volume_text(volume_ratio)}</b>\n\n"
            f"<b>Not:</b> Bu bir olasılık/uyarı skorudur; "
            f"hissenin tavan yapacağını garanti etmez."
        )

        send_once(f"MOM:{symbol}", msg)

# ============================================================
# ANA DÖNGÜ
# ============================================================
def scan_bist_stocks():
    print(
        f"[{datetime.now().strftime('%H:%M:%S')}] "
        f"BIST çoklu zaman dilimli tarama başladı. "
        f"{len(ALL_STOCKS)} hisse."
    )

    for symbol in ALL_STOCKS:
        try:
            scan_stock(symbol)
        except Exception as exc:
            print(f"{symbol} tarama hatası: {exc}")


def main():
    send_telegram_msg(
        "🤖 <b>BIST TARAMA BOTU V7 AKTİF</b>\n"
        "BIST 30 + yan tahtalar | 1H + 4H + 1D | "
        "RSI + momentum + hacim + KAP"
    )

    while True:
        try:
            check_kap_news()
            scan_bist_stocks()

            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] "
                f"Tarama tamamlandı. {SCAN_MINUTES} dakika bekleniyor."
            )

            time.sleep(SCAN_MINUTES * 60)

        except KeyboardInterrupt:
            print("Bot manuel olarak durduruldu.")
            break

        except Exception as exc:
            print(f"Ana döngü hatası: {exc}")
            time.sleep(60)


if __name__ == "__main__":
    main()
