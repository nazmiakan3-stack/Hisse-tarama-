#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=========================================================
BIST + KRİPTO TABAN DÖNÜŞ SİNYAL BOTU
=========================================================

ANA SİNYAL:

1) Günlük değişim > %0
2) Hacim >= 20.000
3) RVOL(10) >= 1.50
4) RSI(14) dipten yukarı dönüyor
   - Önceki RSI <= 35
   - Güncel RSI > Önceki RSI
5) Stochastic %K, %D'yi ALTTAN YUKARI kesiyor
6) Fiyat 20 günlük dibe yakın
7) ATR(14)
8) ATR bazlı TP1 / TP2 / TP3 / SL
9) KAP katalizörü varsa göster
10) TradingView yönünü göster

AYRICA:

- Her dakika negatif hisse/kripto haber taraması
- Aynı haberin tekrar gönderilmesini engelleyen SQLite
- Telegram bildirimleri
- Render health server
- Günlük otomatik taramalar

=========================================================
"""

import os
import re
import time
import html
import hashlib
import sqlite3
import threading
import requests
import feedparser
import pandas as pd
import numpy as np

from datetime import datetime, date
from flask import Flask
from tradingview_ta import TA_Handler, Interval


# =========================================================
# 1. AYARLAR
# =========================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

PORT = int(os.getenv("PORT", "10000"))

DB_FILE = os.getenv("DB_FILE", "bot_data.db")

# ---------------------------------------------------------
# SİNYAL AYARLARI
# ---------------------------------------------------------

MIN_VOLUME = 20_000

RVOL_PERIOD = 10
MIN_RVOL = 1.50

RSI_PERIOD = 14
RSI_BOTTOM_LEVEL = 35

STOCH_PERIOD = 14
STOCH_SMOOTH_K = 3
STOCH_SMOOTH_D = 3

ATR_PERIOD = 14

# Fiyatın son 20 günlük dibe maksimum uzaklığı
BOTTOM_LOOKBACK = 20
MAX_BOTTOM_DISTANCE_PCT = 8.0

# ATR TP / SL
SL_ATR_MULT = 1.0
TP1_ATR_MULT = 1.0
TP2_ATR_MULT = 2.0
TP3_ATR_MULT = 3.0

# Ana tarama aralığı
MAIN_SCAN_INTERVAL = 60

# Negatif haber kontrolü
NEWS_SCAN_INTERVAL = 60


# =========================================================
# 2. BIST LİSTESİ
# =========================================================

# İstersen buraya daha geniş BIST listesini ekleyebilirsin.
# Program TradingView formatına otomatik olarak çevirir.

BIST_SYMBOLS = [
    "AKBNK", "ALARK", "ARCLK", "ASELS", "ASTOR",
    "BIMAS", "BRSAN", "CCOLA", "DOAS", "EKGYO",
    "ENKAI", "EREGL", "FROTO", "GARAN", "GUBRF",
    "HEKTS", "ISCTR", "KCHOL", "KONTR", "KOZAA",
    "KOZAL", "KRDMD", "MGROS", "ODAS", "OYAKC",
    "PETKM", "PGSUS", "SAHOL", "SASA", "SISE",
    "SKBNK", "SMRTG", "SOKM", "TAVHL", "TCELL",
    "THYAO", "TKFEN", "TOASO", "TSKB", "TUPRS",
    "ULKER", "VAKBN", "YKBNK", "ZOREN",

    "AHGAZ", "AKSA", "AKSEN", "ALFAS", "AYDEM",
    "BIOEN", "CANTE", "CWENE", "GESAN", "GWIND",
    "KCAER", "KLSER", "KONYA", "MIATK", "NUHCM",
    "OTKAR", "PENTA", "QUAGR", "REEDR", "TABGD",
    "YEOTK", "ZRGYO"
]


# =========================================================
# 3. KRİPTO LİSTESİ
# =========================================================

CRYPTO_SYMBOLS = [
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
    "BNB-USD",
    "XRP-USD",
    "DOGE-USD",
    "ADA-USD",
    "AVAX-USD",
    "LINK-USD",
    "DOT-USD"
]


# =========================================================
# 4. KAP RSS
# =========================================================

KAP_RSS_URL = "https://www.kap.org.tr/tr/rss"


# =========================================================
# 5. KRİPTO HABER RSS
# =========================================================

CRYPTO_NEWS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
]


# =========================================================
# 6. NEGATİF HABER KELİMELERİ
# =========================================================

NEGATIVE_TR_KEYWORDS = [
    "zarar",
    "net zarar",
    "soruşturma",
    "ceza",
    "dava",
    "iflas",
    "konkordato",
    "temerrüt",
    "borç",
    "borç yapılandırma",
    "üretim durdu",
    "üretim durduruldu",
    "yangın",
    "patlama",
    "grev",
    "işten çıkarma",
    "sözleşme iptal",
    "iptal edildi",
    "geri çekildi",
    "geri çekilme",
    "sermaye kaybı",
    "denetim",
    "dolandırıcılık",
    "sahtecilik",
    "yaptırım",
    "ambargo",
    "çöküş",
    "hack",
    "siber saldırı",
]

NEGATIVE_EN_KEYWORDS = [
    "loss",
    "net loss",
    "investigation",
    "fine",
    "lawsuit",
    "bankruptcy",
    "insolvency",
    "default",
    "debt",
    "production halted",
    "production stopped",
    "fire",
    "explosion",
    "strike",
    "layoffs",
    "contract cancelled",
    "contract canceled",
    "withdrawal",
    "capital loss",
    "fraud",
    "sanction",
    "sanctions",
    "ban",
    "hack",
    "hacked",
    "exploit",
    "security breach",
    "delisting",
    "delisted",
    "depeg",
    "outage",
    "lawsuit",
    "sec",
]


# =========================================================
# 7. KAP KATALİZÖR KELİMELERİ
# =========================================================

KAP_KEYWORDS = {
    "bedelsiz": 5,
    "yeni iş ilişkisi": 5,
    "ortaklık": 5,
    "ihale": 4,
    "pay alım": 4,
    "geri alım": 4,
    "yatırım": 4,
    "kapasite": 3,
    "sözleşme": 3,
    "sipariş": 3,
    "anlaşma": 3,
}


# =========================================================
# 8. GLOBAL
# =========================================================

app = Flask(__name__)

news_lock = threading.Lock()

last_main_scan = None

# TradingView analiz cache
TV_CACHE = {}

# Günlük gönderilmiş ana sinyaller
SENT_SIGNALS = set()


# =========================================================
# 9. SQLITE
# =========================================================

def init_database():
    conn = sqlite3.connect(DB_FILE)

    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS processed_news (
            id TEXT PRIMARY KEY,
            title TEXT,
            url TEXT,
            source TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sent_signals (
            signal_key TEXT PRIMARY KEY,
            symbol TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def news_already_processed(news_id):
    conn = sqlite3.connect(DB_FILE)

    cur = conn.cursor()

    cur.execute(
        "SELECT id FROM processed_news WHERE id = ?",
        (news_id,)
    )

    result = cur.fetchone()

    conn.close()

    return result is not None


def save_processed_news(news_id, title, url, source):
    conn = sqlite3.connect(DB_FILE)

    conn.execute("""
        INSERT OR IGNORE INTO processed_news
        (id, title, url, source, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        news_id,
        title,
        url,
        source,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


# =========================================================
# 10. TELEGRAM
# =========================================================

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram ayarları bulunamadı.")
        return False

    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_TOKEN}/sendMessage"
    )

    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(
            url,
            data=data,
            timeout=15
        )

        if response.status_code != 200:
            print(
                "Telegram hatası:",
                response.status_code,
                response.text[:300]
            )
            return False

        return True

    except Exception as e:
        print("Telegram bağlantı hatası:", e)
        return False


# =========================================================
# 11. YAHOO TICKER
# =========================================================

def yahoo_symbol(symbol):
    if symbol.endswith(".IS"):
        return symbol

    if symbol in BIST_SYMBOLS:
        return symbol + ".IS"

    return symbol


# =========================================================
# 12. TARİHSEL VERİ
# =========================================================

def get_history(symbol, period="3mo", interval="1d"):
    """
    Yahoo Finance chart endpoint kullanılır.
    Böylece ayrıca yfinance paketine gerek kalmaz.
    """

    ticker = yahoo_symbol(symbol)

    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + ticker
    )

    params = {
        "range": period,
        "interval": interval,
        "events": "history",
        "includeAdjustedClose": "true",
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=15,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        response.raise_for_status()

        data = response.json()

        result = data["chart"]["result"][0]

        timestamps = result.get("timestamp", [])

        quote = result["indicators"]["quote"][0]

        df = pd.DataFrame({
            "timestamp": timestamps,
            "open": quote.get("open", []),
            "high": quote.get("high", []),
            "low": quote.get("low", []),
            "close": quote.get("close", []),
            "volume": quote.get("volume", []),
        })

        if df.empty:
            return None

        df["datetime"] = pd.to_datetime(
            df["timestamp"],
            unit="s"
        )

        df = df.dropna(
            subset=["open", "high", "low", "close"]
        )

        df = df.reset_index(drop=True)

        return df

    except Exception as e:
        print(
            f"{symbol} veri alınamadı:",
            e
        )
        return None


# =========================================================
# 13. RSI
# =========================================================

def calculate_rsi(series, period=14):
    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    rsi = 100 - (
        100 / (1 + rs)
    )

    return rsi


# =========================================================
# 14. STOCHASTIC
# =========================================================

def calculate_stochastic(
    df,
    period=14,
    smooth_k=3,
    smooth_d=3
):

    lowest_low = (
        df["low"]
        .rolling(period)
        .min()
    )

    highest_high = (
        df["high"]
        .rolling(period)
        .max()
    )

    denominator = (
        highest_high - lowest_low
    ).replace(0, np.nan)

    raw_k = (
        100 *
        (
            df["close"] - lowest_low
        ) / denominator
    )

    k = (
        raw_k
        .rolling(smooth_k)
        .mean()
    )

    d = (
        k
        .rolling(smooth_d)
        .mean()
    )

    return k, d


# =========================================================
# 15. ATR
# =========================================================

def calculate_atr(
    df,
    period=14
):

    previous_close = df["close"].shift(1)

    tr1 = (
        df["high"] - df["low"]
    )

    tr2 = (
        df["high"] - previous_close
    ).abs()

    tr3 = (
        df["low"] - previous_close
    ).abs()

    true_range = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    atr = (
        true_range
        .ewm(
            alpha=1 / period,
            adjust=False,
            min_periods=period
        )
        .mean()
    )

    return atr


# =========================================================
# 16. TEKNİK ANALİZ
# =========================================================

def calculate_indicators(df):

    df = df.copy()

    df["rsi"] = calculate_rsi(
        df["close"],
        RSI_PERIOD
    )

    df["stoch_k"], df["stoch_d"] = (
        calculate_stochastic(
            df,
            STOCH_PERIOD,
            STOCH_SMOOTH_K,
            STOCH_SMOOTH_D
        )
    )

    df["atr"] = calculate_atr(
        df,
        ATR_PERIOD
    )

    df["avg_volume_10"] = (
        df["volume"]
        .rolling(RVOL_PERIOD)
        .mean()
        .shift(1)
    )

    df["rvol"] = (
        df["volume"] /
        df["avg_volume_10"]
    )

    df["low_20"] = (
        df["low"]
        .rolling(BOTTOM_LOOKBACK)
        .min()
    )

    df["bottom_distance_pct"] = (
        (
            df["close"] -
            df["low_20"]
        ) /
        df["low_20"]
    ) * 100

    return df


# =========================================================
# 17. TABANDAN DÖNÜŞ KONTROLÜ
# =========================================================

def check_bottom_reversal(df):

    if len(df) < 50:
        return None

    current = df.iloc[-1]
    previous = df.iloc[-2]

    # -----------------------------------------------------
    # 1. Günlük değişim pozitif
    # -----------------------------------------------------

    daily_change_pct = (
        (
            current["close"] -
            previous["close"]
        )
        /
        previous["close"]
    ) * 100

    if daily_change_pct <= 0:
        return None

    # -----------------------------------------------------
    # 2. Hacim >= 20.000
    # -----------------------------------------------------

    if pd.isna(current["volume"]):
        return None

    if current["volume"] < MIN_VOLUME:
        return None

    # -----------------------------------------------------
    # 3. RVOL >= 1.50
    # -----------------------------------------------------

    if pd.isna(current["rvol"]):
        return None

    if current["rvol"] < MIN_RVOL:
        return None

    # -----------------------------------------------------
    # 4. RSI DİPTEN YUKARI DÖNÜYOR
    #
    # Önceki RSI <= 35
    # Mevcut RSI > önceki RSI
    # -----------------------------------------------------

    if (
        pd.isna(current["rsi"]) or
        pd.isna(previous["rsi"])
    ):
        return None

    rsi_reversal = (
        previous["rsi"] <= RSI_BOTTOM_LEVEL
        and
        current["rsi"] > previous["rsi"]
    )

    if not rsi_reversal:
        return None

    # -----------------------------------------------------
    # 5. STOCHASTIC ALTTAN YUKARI KESİŞİM
    #
    # Önce:
    # K <= D
    #
    # Şimdi:
    # K > D
    # -----------------------------------------------------

    if (
        pd.isna(current["stoch_k"]) or
        pd.isna(current["stoch_d"]) or
        pd.isna(previous["stoch_k"]) or
        pd.isna(previous["stoch_d"])
    ):
        return None

    stochastic_cross = (
        previous["stoch_k"] <=
        previous["stoch_d"]
        and
        current["stoch_k"] >
        current["stoch_d"]
    )

    if not stochastic_cross:
        return None

    # -----------------------------------------------------
    # 6. Fiyat 20 günlük dibe yakın
    # -----------------------------------------------------

    if pd.isna(
        current["bottom_distance_pct"]
    ):
        return None

    if (
        current["bottom_distance_pct"]
        > MAX_BOTTOM_DISTANCE_PCT
    ):
        return None

    # -----------------------------------------------------
    # 7. ATR
    # -----------------------------------------------------

    if (
        pd.isna(current["atr"]) or
        current["atr"] <= 0
    ):
        return None

    return {
        "price": float(current["close"]),

        "change_pct": float(
            daily_change_pct
        ),

        "volume": float(
            current["volume"]
        ),

        "avg_volume_10": float(
            current["avg_volume_10"]
        ),

        "rvol": float(
            current["rvol"]
        ),

        "rsi": float(
            current["rsi"]
        ),

        "previous_rsi": float(
            previous["rsi"]
        ),

        "stoch_k": float(
            current["stoch_k"]
        ),

        "stoch_d": float(
            current["stoch_d"]
        ),

        "previous_stoch_k": float(
            previous["stoch_k"]
        ),

        "previous_stoch_d": float(
            previous["stoch_d"]
        ),

        "atr": float(
            current["atr"]
        ),

        "bottom_distance_pct": float(
            current["bottom_distance_pct"]
        ),
    }


# =========================================================
# 18. ATR TP / SL
# =========================================================

def calculate_tp_sl(price, atr):

    sl = (
        price -
        atr * SL_ATR_MULT
    )

    tp1 = (
        price +
        atr * TP1_ATR_MULT
    )

    tp2 = (
        price +
        atr * TP2_ATR_MULT
    )

    tp3 = (
        price +
        atr * TP3_ATR_MULT
    )

    return {
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
    }


# =========================================================
# 19. KAP HABERLERİ
# =========================================================

def get_kap_news():

    try:
        response = requests.get(
            KAP_RSS_URL,
            timeout=15,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        response.raise_for_status()

        feed = feedparser.parse(
            response.content
        )

        return feed.entries

    except Exception as e:
        print(
            "KAP RSS hatası:",
            e
        )
        return []


# =========================================================
# 20. KAP KATALİZÖRÜ BUL
# =========================================================

def find_kap_catalyst(symbol):

    entries = get_kap_news()

    symbol_upper = symbol.upper()

    best = None
    best_score = 0

    for entry in entries:

        title = html.unescape(
            entry.get("title", "")
        )

        summary = html.unescape(
            entry.get("summary", "")
        )

        text = (
            title + " " + summary
        ).lower()

        # Basit sembol kontrolü
        if symbol_upper.lower() not in text:
            continue

        score = 0
        matched = []

        for keyword, points in KAP_KEYWORDS.items():

            if keyword in text:
                score += points
                matched.append(keyword)

        if score > best_score:

            best_score = score

            best = {
                "title": title,
                "url": entry.get(
                    "link",
                    ""
                ),
                "score": score,
                "keywords": matched,
            }

    return best


# =========================================================
# 21. TRADINGVIEW YÖNÜ
# =========================================================

def get_tradingview_direction(symbol):

    try:

        handler = TA_Handler(
            symbol=symbol,
            screener="turkey",
            exchange="BIST",
            interval=Interval.INTERVAL_1_DAY,
            timeout=10
        )

        analysis = handler.get_analysis()

        summary = analysis.summary

        recommendation = (
            summary.get(
                "RECOMMENDATION",
                "N/A"
            )
        )

        buy = summary.get(
            "BUY",
            0
        )

        sell = summary.get(
            "SELL",
            0
        )

        neutral = summary.get(
            "NEUTRAL",
            0
        )

        return {
            "recommendation": recommendation,
            "buy": buy,
            "sell": sell,
            "neutral": neutral,
        }

    except Exception as e:

        print(
            f"TradingView {symbol}:",
            e
        )

        return {
            "recommendation": "N/A",
            "buy": 0,
            "sell": 0,
            "neutral": 0,
        }


# =========================================================
# 22. KAP YAZISI
# =========================================================

def format_kap(catalyst):

    if not catalyst:
        return (
            "📰 <b>KAP:</b> "
            "Katalizör bulunamadı"
        )

    stars = "⭐" * min(
        catalyst["score"],
        5
    )

    keywords = ", ".join(
        catalyst["keywords"]
    )

    return (
        f"📰 <b>KAP:</b> "
        f"{html.escape(catalyst['title'])}\n"
        f"⭐ <b>KAP Etkisi:</b> "
        f"{stars}\n"
        f"🔎 <b>Kelimeler:</b> "
        f"{html.escape(keywords)}"
    )


# =========================================================
# 23. ANA SİNYAL MESAJI
# =========================================================

def build_signal_message(
    symbol,
    signal,
    catalyst,
    tv
):

    price = signal["price"]

    levels = calculate_tp_sl(
        price,
        signal["atr"]
    )

    direction = tv["recommendation"]

    message = (
        "🚀 <b>TABANDAN YÜKSELİŞ SİNYALİ</b>\n"
        "\n"
        f"📌 <b>#{symbol}</b>\n"
        f"💰 Fiyat: <b>{price:.2f}</b>\n"
        f"📈 Günlük: <b>+{signal['change_pct']:.2f}%</b>\n"
        "\n"

        "📊 <b>RSI(14)</b>\n"
        f"├ Önceki: {signal['previous_rsi']:.2f}\n"
        f"├ Şimdi: <b>{signal['rsi']:.2f}</b>\n"
        "└ 🟢 <b>DİPTEN YUKARI DÖNÜYOR</b>\n"
        "\n"

        "📊 <b>STOCHASTIC</b>\n"
        f"├ Önceki K: {signal['previous_stoch_k']:.2f}\n"
        f"├ Önceki D: {signal['previous_stoch_d']:.2f}\n"
        f"├ Şimdi K: <b>{signal['stoch_k']:.2f}</b>\n"
        f"├ Şimdi D: <b>{signal['stoch_d']:.2f}</b>\n"
        "└ 🟢 <b>ALTTAN YUKARI KESİŞİM</b>\n"
        "\n"

        "💧 <b>HACİM</b>\n"
        f"├ Hacim: <b>{signal['volume']:,.0f}</b>\n"
        f"├ 10G Ortalama: {signal['avg_volume_10']:,.0f}\n"
        f"└ 🔥 RVOL: <b>{signal['rvol']:.2f}x</b>\n"
        "\n"

        f"📐 <b>ATR(14):</b> "
        f"{signal['atr']:.2f}\n"
        f"📍 <b>20G Dip Mesafesi:</b> "
        f"%{signal['bottom_distance_pct']:.2f}\n"
        "\n"

        "🎯 <b>ATR HEDEFLERİ</b>\n"
        f"├ TP1: <b>{levels['tp1']:.2f}</b>\n"
        f"├ TP2: <b>{levels['tp2']:.2f}</b>\n"
        f"├ TP3: <b>{levels['tp3']:.2f}</b>\n"
        f"└ 🛑 SL: <b>{levels['sl']:.2f}</b>\n"
        "\n"

        f"📡 <b>TradingView:</b> "
        f"{html.escape(str(direction))}\n"
        "\n"
        f"{format_kap(catalyst)}\n"
        "\n"
        "🟢 <b>SİNYAL:</b> "
        "RSI + STOCHASTIC + HACİM + RVOL "
        "TABAN DÖNÜŞÜ"
    )

    return message


# =========================================================
# 24. ANA BIST TARAMASI
# =========================================================

def scan_bist():

    global last_main_scan

    last_main_scan = datetime.now()

    print(
        "\n" +
        "=" * 60
    )

    print(
        "BIST TARAMASI:",
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    print(
        "=" * 60
    )

    found = 0

    for symbol in BIST_SYMBOLS:

        try:

            print(
                "Taranıyor:",
                symbol
            )

            df = get_history(
                symbol,
                period="6mo",
                interval="1d"
            )

            if df is None:
                continue

            df = calculate_indicators(
                df
            )

            signal = check_bottom_reversal(
                df
            )

            if not signal:
                continue

            # Aynı gün aynı hisseden tekrar mesaj gönderme
            signal_key = (
                f"{date.today().isoformat()}_"
                f"{symbol}"
            )

            if signal_key in SENT_SIGNALS:
                continue

            catalyst = find_kap_catalyst(
                symbol
            )

            tv = get_tradingview_direction(
                symbol
            )

            message = build_signal_message(
                symbol,
                signal,
                catalyst,
                tv
            )

            if send_telegram(message):

                SENT_SIGNALS.add(
                    signal_key
                )

                found += 1

                print(
                    "SİNYAL:",
                    symbol
                )

        except Exception as e:

            print(
                f"{symbol} tarama hatası:",
                e
            )

    print(
        "Tarama tamamlandı.",
        "Sinyal:",
        found
    )


# =========================================================
# 25. NEGATİF HABER ANALİZİ
# =========================================================

def get_news_id(title, url):

    raw = (
        str(title) +
        "|" +
        str(url)
    )

    return hashlib.sha256(
        raw.encode(
            "utf-8",
            errors="ignore"
        )
    ).hexdigest()


def negative_news_score(text):

    text_lower = text.lower()

    score = 0
    matched = []

    for keyword in (
        NEGATIVE_TR_KEYWORDS +
        NEGATIVE_EN_KEYWORDS
    ):

        if keyword.lower() in text_lower:

            score += 1

            matched.append(
                keyword
            )

    return score, matched


# =========================================================
# 26. KRİPTO/HİSSE SEMBOLÜ BUL
# =========================================================

def detect_assets(text):

    text_upper = text.upper()

    assets = []

    for symbol in BIST_SYMBOLS:

        pattern = (
            r"\b" +
            re.escape(symbol) +
            r"\b"
        )

        if re.search(
            pattern,
            text_upper
        ):
            assets.append(
                symbol
            )

    crypto_map = {
        "BTC": "BTC",
        "BITCOIN": "BTC",
        "ETH": "ETH",
        "ETHEREUM": "ETH",
        "SOL": "SOL",
        "SOLANA": "SOL",
        "BNB": "BNB",
        "XRP": "XRP",
        "DOGE": "DOGE",
        "DOGECOIN": "DOGE",
        "ADA": "ADA",
        "CARDANO": "ADA",
        "AVAX": "AVAX",
        "AVALANCHE": "AVAX",
        "LINK": "LINK",
        "CHAINLINK": "LINK",
        "DOT": "DOT",
        "POLKADOT": "DOT",
    }

    for key, value in crypto_map.items():

        if re.search(
            r"\b" +
            re.escape(key) +
            r"\b",
            text_upper
        ):
            assets.append(
                value
            )

    return sorted(
        set(assets)
    )


# =========================================================
# 27. KAP NEGATİF HABERLERİ
# =========================================================

def scan_kap_negative_news():

    entries = get_kap_news()

    for entry in entries:

        title = html.unescape(
            entry.get(
                "title",
                ""
            )
        )

        summary = html.unescape(
            entry.get(
                "summary",
                ""
            )
        )

        url = entry.get(
            "link",
            ""
        )

        text = (
            title + " " + summary
        )

        news_id = get_news_id(
            title,
            url
        )

        if news_already_processed(
            news_id
        ):
            continue

        score, matched = (
            negative_news_score(text)
        )

        assets = detect_assets(
            text
        )

        # Haberde negatif kelime yoksa
        # kaydet ama Telegram'a gönderme
        if score <= 0:

            save_processed_news(
                news_id,
                title,
                url,
                "KAP"
            )

            continue

        save_processed_news(
            news_id,
            title,
            url,
            "KAP"
        )

        asset_text = (
            ", ".join(
                assets
            )
            if assets
            else "Belirli varlık bulunamadı"
        )

        message = (
            "🚨 <b>NEGATİF HABER UYARISI</b>\n"
            "\n"
            "🇹🇷 <b>Kaynak:</b> KAP\n"
            f"🎯 <b>Varlık:</b> "
            f"{html.escape(asset_text)}\n"
            "\n"
            f"📰 <b>{html.escape(title)}</b>\n"
            "\n"
            f"⚠️ <b>Negatif eşleşmeler:</b> "
            f"{html.escape(', '.join(matched))}\n"
            "\n"
            "ℹ️ Bu mesaj otomatik haber "
            "sınıflandırmasıdır. Haber etkisinin "
            "kesin olduğu anlamına gelmez.\n"
        )

        if url:
            message += (
                f"\n🔗 <a href=\"{html.escape(url)}\">"
                "Haberi Aç</a>"
            )

        send_telegram(
            message
        )


# =========================================================
# 28. KRİPTO NEGATİF HABERLER
# =========================================================

def scan_crypto_negative_news():

    for feed_url in CRYPTO_NEWS_FEEDS:

        try:

            feed = feedparser.parse(
                feed_url
            )

            for entry in feed.entries:

                title = html.unescape(
                    entry.get(
                        "title",
                        ""
                    )
                )

                summary = html.unescape(
                    entry.get(
                        "summary",
                        ""
                    )
                )

                url = entry.get(
                    "link",
                    ""
                )

                text = (
                    title + " " + summary
                )

                news_id = get_news_id(
                    title,
                    url
                )

                if news_already_processed(
                    news_id
                ):
                    continue

                score, matched = (
                    negative_news_score(
                        text
                    )
                )

                assets = detect_assets(
                    text
                )

                # Kripto ile ilgili olmadığı
                # açıkça anlaşılıyorsa atla.
                crypto_words = [
                    "bitcoin",
                    "btc",
                    "ethereum",
                    "eth",
                    "crypto",
                    "cryptocurrency",
                    "token",
                    "blockchain",
                    "exchange",
                    "defi",
                    "stablecoin",
                    "solana",
                    "xrp",
                    "bnb",
                    "dogecoin",
                    "cardano",
                    "avalanche",
                    "chainlink",
                    "polkadot",
                ]

                crypto_related = any(
                    word in text.lower()
                    for word in crypto_words
                )

                if not crypto_related:

                    save_processed_news(
                        news_id,
                        title,
                        url,
                        feed_url
                    )

                    continue

                if score <= 0:

                    save_processed_news(
                        news_id,
                        title,
                        url,
                        feed_url
                    )

                    continue

                save_processed_news(
                    news_id,
                    title,
                    url,
                    feed_url
                )

                asset_text = (
                    ", ".join(assets)
                    if assets
                    else "Kripto piyasası"
                )

                message = (
                    "🚨 <b>KRİPTO NEGATİF HABER UYARISI</b>\n"
                    "\n"
                    f"🪙 <b>Varlık:</b> "
                    f"{html.escape(asset_text)}\n"
                    f"📰 <b>{html.escape(title)}</b>\n"
                    "\n"
                    f"⚠️ <b>Eşleşmeler:</b> "
                    f"{html.escape(', '.join(matched))}\n"
                    "\n"
                    "ℹ️ Bu mesaj otomatik haber "
                    "sınıflandırmasıdır. Piyasa etkisinin "
                    "kesin olduğu anlamına gelmez.\n"
                )

                if url:
                    message += (
                        f"\n🔗 <a href=\"{html.escape(url)}\">"
                        "Haberi Aç</a>"
                    )

                send_telegram(
                    message
                )

        except Exception as e:

            print(
                "Kripto haber hatası:",
                e
            )


# =========================================================
# 29. HER DAKİKA HABER MOTORU
# =========================================================

def news_worker():

    print(
        "📰 Haber motoru başlatıldı."
    )

    while True:

        try:

            print(
                "\nHaber kontrolü:",
                datetime.now().strftime(
                    "%H:%M:%S"
                )
            )

            scan_kap_negative_news()

            scan_crypto_negative_news()

        except Exception as e:

            print(
                "Haber worker hatası:",
                e
            )

        time.sleep(
            NEWS_SCAN_INTERVAL
        )


# =========================================================
# 30. GÜNLÜK ANA TARAMA ZAMANLARI
# =========================================================

SCAN_TIMES = {
    "09:50",
    "10:10",
    "17:45",
    "23:00",
}


def main_scan_worker():

    print(
        "📊 Ana tarama motoru başlatıldı."
    )

    already_scanned = set()

    while True:

        now = datetime.now()

        current_time = now.strftime(
            "%H:%M"
        )

        scan_key = (
            now.strftime("%Y-%m-%d") +
            "_" +
            current_time
        )

        if (
            current_time in SCAN_TIMES
            and
            scan_key not in already_scanned
        ):

            already_scanned.add(
                scan_key
            )

            scan_bist()

        # Eski kayıtları temizle
        if len(already_scanned) > 100:
            already_scanned = {
                scan_key
            }

        time.sleep(20)


# =========================================================
# 31. HEALTH SERVER
# =========================================================

@app.route("/")
def home():

    return (
        "BIST + Crypto Signal Bot ACTIVE | "
        f"Last scan: {last_main_scan}"
    )


@app.route("/health")
def health():

    return {
        "status": "ok",
        "last_scan": str(
            last_main_scan
        ),
        "time": datetime.now().isoformat()
    }


def start_health_server():

    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        use_reloader=False
    )


# =========================================================
# 32. BAŞLANGIÇ
# =========================================================

def main():

    print(
        "\n" +
        "=" * 65
    )

    print(
        "🚀 BIST + KRİPTO TABAN DÖNÜŞ BOTU"
    )

    print(
        "=" * 65
    )

    print(
        "RSI dip seviyesi:",
        RSI_BOTTOM_LEVEL
    )

    print(
        "Minimum hacim:",
        MIN_VOLUME
    )

    print(
        "Minimum RVOL:",
        MIN_RVOL
    )

    print(
        "Stochastic:",
        "ALTTAN YUKARI KESİŞİM"
    )

    print(
        "Bottom lookback:",
        BOTTOM_LOOKBACK
    )

    print(
        "Bottom max distance:",
        MAX_BOTTOM_DISTANCE_PCT,
        "%"
    )

    print(
        "=" * 65
    )

    init_database()

    # Health server
    threading.Thread(
        target=start_health_server,
        daemon=True
    ).start()

    # Haber motoru
    threading.Thread(
        target=news_worker,
        daemon=True
    ).start()

    # Ana tarama motoru
    threading.Thread(
        target=main_scan_worker,
        daemon=True
    ).start()

    # Program kapanmasın
    while True:

        time.sleep(60)


# =========================================================
# ÇALIŞTIR
# =========================================================

if __name__ == "__main__":
    main()
