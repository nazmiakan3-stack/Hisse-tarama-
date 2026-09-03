#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

# ============================================================
# KÜTÜPHANE KONTROLÜ
# ============================================================
try:
    import requests
    import feedparser
    from tradingview_ta import Interval, get_multiple_analysis
except ModuleNotFoundError as e:
    print(f"\n❌ EKSİK KÜTÜPHANE TESPİT EDİLDİ: {e}")
    print("👉 Lütfen terminale şu komutu yazarak gerekli paketleri yükleyin:")
    print("pip install requests feedparser tradingview-ta\n")
    exit(1)

# ============================================================
# RENDER & UPTIMEROBOT İÇİN DAHİLİ HTTP SUNUCUSU
# ============================================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        return

def start_health_check_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=start_health_check_server, daemon=True).start()

# ============================================================
# TELEGRAM VE STRATEJİ PARAMETRELERİ
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1734551753")

TARGET_SCAN_TIMES = ["09:50", "10:10", "17:45"]

RSI_DIP_LIMIT = 30             
RSI_MOMENTUM_LIMIT = 50        
CHANGE_MOMENTUM_LIMIT = 2.5    
TOP_GAINER_LIMIT = 5.0         

# ⚠️ YENİ: Maksimum "Sığ Tahta" Lot Sınırı
# O günkü işlem gören lot adedi 500.000'den az ise bot bunu "az lotlu/sığ" kabul eder.
# Bu sayıyı kendi stratejine göre değiştirebilirsin (Örn: 1000000)
LOW_VOLUME_LIMIT = 500000 

KAP_STAR_MAP = {
    "bedelsiz": ("⭐⭐⭐⭐⭐", "Yüksek Oranlı Bedelsiz / Sermaye Artırımı"),
    "yeni iş ilişkisi": ("⭐⭐⭐⭐⭐", "Yeni İş İlişkisi / Dev İhale"),
    "ortaklık": ("⭐⭐⭐⭐⭐", "Stratejik İş Ortaklığı / M&A"),
    "ihale": ("⭐⭐⭐⭐", "İhale Sözleşmesi / Dev Sipariş"),
    "pay alım": ("⭐⭐⭐⭐", "Şirket Pay Geri Alımı"),
}

BIST_30_SET = {
    "AKBNK", "ALARK", "ASELS", "ASTOR", "BIMAS", "BRSAN", "DOAS", "EKGYO",
    "ENKAI", "EREGL", "FROTO", "GARAN", "GUBRF", "HEKTS", "ISCTR", "KCHOL",
    "KONTR", "KOZAL", "KRDMD", "ODAS", "OYAKC", "PETKM", "PGSUS", "SAHOL",
    "SASA", "SISE", "TCELL", "THYAO", "TOASO", "TUPRS",
}

FULL_BIST_LIST = [
    "AAVTUR", "ACSEL", "ADEL", "ADESE", "ADGYO", "AEFES", "AFYON", "AGESA", "AGHOL", "AGROT",
    "AHGAZ", "AKBNK", "AKCNS", "ALARK", "ALFAS", "ASTOR", "BIMAS", "BRSAN", "CUSAN", "CWENE", 
    "DOAS", "EGEEN", "EKGYO", "ENKAI", "EREGL", "FROTO", "GARAN", "GESAN", "GUBRF", "HEKTS", 
    "ISCTR", "KCHOL", "KONTR", "KOZAL", "KRDMD", "MIATK", "ODAS", "OYAKC", "PETKM", "PGSUS", 
    "SAHOL", "SASA", "SISE", "SMRTG", "TCELL", "THYAO", "TOASO", "TUPRS", "YEOTK", "YKBNK"
    # Buraya kendi tam listeni yapıştırabilirsin.
]

PROCESSED_KAP_LINKS = set()
SCANNED_TIMES_TODAY = set()
ACTIVE_KAP_SIGNALS = {} 

# ============================================================
# YARDIMCI FONKSİYONLAR
# ============================================================
def send_telegram_msg(message):
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN" or not TELEGRAM_BOT_TOKEN:
        print(f"\n[TELEGRAM MESAJI]:\n{message}\n")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        pass

def get_all_bist_tickers():
    try:
        url = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/HisseTeknikVeriler"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json().get("d", [])
            fetched = {item.get("code") for item in data if item.get("code") and len(item.get("code")) <= 5}
            filtered = sorted(list(fetched - BIST_30_SET))
            if len(filtered) >= 400: return filtered
    except Exception:
        pass
    return sorted(list(set(FULL_BIST_LIST) - BIST_30_SET))

def get_dip_stars(rsi):
    if rsi <= 15: return "⭐⭐⭐⭐⭐ (Tarihi Dip)"
    elif rsi <= 20: return "⭐⭐⭐⭐ (Derin Dip)"
    elif rsi <= 25: return "⭐⭐⭐ (Güçlü Dip)"
    else: return "⭐⭐ (Kademeli Giriş)"

# ============================================================
# TRADINGVIEW TOPLU TARAMA (HACİM EKLENDİ)
# ============================================================
def analyze_tv_stocks_bulk(symbol_list):
    formatted_symbols = [f"BIST:{sym}" for sym in symbol_list]
    results = {}
    chunk_size = 20

    for i in range(0, len(formatted_symbols), chunk_size):
        chunk = formatted_symbols[i:i + chunk_size]
        try:
            analysis_chunk = get_multiple_analysis(screener="turkey", interval=Interval.INTERVAL_1_DAY, symbols=chunk)
            for key, analysis in analysis_chunk.items():
                clean_sym = key.replace("BIST:", "")
                if analysis and hasattr(analysis, 'indicators') and analysis.indicators:
                    ind = analysis.indicators
                    rec = analysis.summary.get("RECOMMENDATION") if hasattr(analysis, 'summary') and analysis.summary else "N/A"
                    results[clean_sym] = {
                        "close": ind.get("close"),
                        "change": ind.get("change"),
                        "rsi": ind.get("RSI"),
                        "volume": ind.get("volume", 0), # YENİ: Anlık lot sayısı verisi çekiliyor
                        "recommendation": rec
                    }
        except Exception:
            pass
    return results

# ============================================================
# KAP İSTİHBARAT MODÜLÜ
# ============================================================
def check_kap_news():
    global PROCESSED_KAP_LINKS, ACTIVE_KAP_SIGNALS
    try:
        kap_url = "https://www.kap.org.tr/tr/rss"
        feed = feedparser.parse(kap_url)

        for entry in feed.entries[:20]:
            if entry.link in PROCESSED_KAP_LINKS:
                continue

            title = entry.title
            summary = entry.summary if "summary" in entry else ""
            content_lower = (title + " " + summary).lower()

            for key, (stars, category) in KAP_STAR_MAP.items():
                if key in content_lower:
                    PROCESSED_KAP_LINKS.add(entry.link)
                    for symbol in FULL_BIST_LIST:
                        if symbol in title or symbol in summary:
                            ACTIVE_KAP_SIGNALS[symbol] = {
                                "stars": stars, "category": category,
                                "title": title, "link": entry.link
                            }
                    send_telegram_msg(f"🔥 <b>[YÜKSEK HABER DEĞERİ]</b>\n<b>Etki:</b> {stars}\n<b>Başlık:</b> {title}\n<b>Link:</b> <a href='{entry.link}'>KAP Detayı</a>")
                    break
    except Exception:
        pass

# ============================================================
# ÖZEL SEANS TARAMASI VE DİNAMİK LOT KONTROLÜ
# ============================================================
def scan_bist_stocks(symbol_list, scan_time):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Taraması Başlatıldı...")
    
    tv_data_map = analyze_tv_stocks_bulk(symbol_list)
    top_gainers = []

    for symbol in symbol_list:
        data = tv_data_map.get(symbol)
        if not data or data["rsi"] is None or data["close"] is None:
            continue

        price = data["close"]
        rsi = data["rsi"]
        change = data["change"] or 0.0
        volume = data["volume"] or 0
        rec = data["recommendation"] or "N/A"

        # 🌟 LİSTE İÇİN: +%5 VE ÜZERİ YÜKSELENLER
        if change >= TOP_GAINER_LIMIT:
            top_gainers.append((symbol, change, price, volume))

        # 💎 YENİ STRATEJİ: %5 ile %8 Arası + (Dinamik Az Lot VEYA KAP Haberi)
        if 5.0 <= change <= 8.0:
            # İşlem gören lot 500 binin altındaysa "Sığ Tahta" kabul et
            is_low_volume = (0 < volume < LOW_VOLUME_LIMIT)
            has_kap = symbol in ACTIVE_KAP_SIGNALS
            
            if is_low_volume or has_kap:
                rating = "⭐⭐⭐⭐"
                strategy_desc = ""
                
                if is_low_volume and has_kap:
                    kap_data = ACTIVE_KAP_SIGNALS[symbol]
                    rating = f"⭐⭐⭐⭐⭐ (Mükemmel Kombinasyon)"
                    strategy_desc = f"Lotu Az ({volume:,.0f} Adet) + {kap_data['category']} Haberi. Tavan potansiyeli çok yüksek!"
                elif has_kap:
                    kap_data = ACTIVE_KAP_SIGNALS[symbol]
                    rating = f"{kap_data['stars']} (Haber Katalizörü)"
                    strategy_desc = f"{kap_data['category']} haberi ile yükselişte."
                elif is_low_volume:
                    rating = "⭐⭐⭐⭐ (Sığ Tahta / Az Lot İvmesi)"
                    strategy_desc = f"Lot sayısı kısıtlı işlem görüyor. Kademeler hızlı kalkabilir."
                
                msg = (
                    f"💎 <b>[ÖZEL KATALİZÖR AVCISI - {scan_time}]</b>\n\n"
                    f"<b>Hisse Adı:</b> #{symbol}\n"
                    f"<b>Fiyat / Değişim:</b> {price:.2f} TL (<b>%{change:+.2f}</b>)\n"
                    f"<b>İşlem Gören Lot (Hacim):</b> {volume:,.0f} Adet\n"
                    f"<b>Derece:</b> {rating}\n"
                    f"<b>Strateji:</b> {strategy_desc}\n"
                )
                
                if has_kap:
                    msg += f"\n📰 <b>KAP Detayı:</b> {ACTIVE_KAP_SIGNALS[symbol]['title']}\n"
                    msg += f"🔗 <a href='{ACTIVE_KAP_SIGNALS[symbol]['link']}'>Habere Git</a>"
                
                send_telegram_msg(msg)

        # 🛡️ DİP AVCISI
        if rsi <= RSI_DIP_LIMIT:
            send_telegram_msg(
                f"🛡️ <b>[DİP AVCISI - {scan_time}]</b>\n\n"
                f"<b>Hisse Adı:</b> #{symbol}\n"
                f"<b>Derece:</b> {get_dip_stars(rsi)}\n"
                f"<b>Fiyat:</b> {price:.2f} TL (%{change:+.2f})\n"
                f"<b>RSI (14):</b> {rsi:.1f}"
            )

    # 📊 +%5 LİSTESİNİ TOPLU GÖNDER
    if top_gainers:
        top_gainers.sort(key=lambda x: x[1], reverse=True)
        chunk_size = 30
        for i in range(0, len(top_gainers), chunk_size):
            chunk = top_gainers[i:i + chunk_size]
            gainer_msg = f"🌟 <b>[+%5 VE ÜZERİ YÜKSELENLER - {scan_time}]</b>\n\n"
            for sym, chg, prc, vol in chunk:
                gainer_msg += f"<b>#{sym: <6}</b> | +%{chg:.2f} | <b>Lot:</b> {vol:,.0f}\n"
            gainer_msg += f"\n<i>📌 Toplam: {len(top_gainers)} Hisse Kriteri Sağladı.</i>"
            send_telegram_msg(gainer_msg)

# ============================================================
# ANA ÇALIŞMA DÖNGÜSÜ
# ============================================================
def main():
    send_telegram_msg(
        "🤖 <b>BİST BOTU (OTOMATİK LOT KARŞILAŞTIRMALI AKTİF)</b>\n"
        "⏰ Özel Tarama Saatleri: <b>09:50</b>, <b>10:10</b> ve <b>17:45</b>\n"
        f"💎 Yeni Özellik: %5-%8 arası yükselip o günkü işlemi <b>{LOW_VOLUME_LIMIT:,.0f} lottan az olanlar</b> otomatik avlanıyor!"
    )

    while True:
        try:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            current_date = now.strftime("%Y-%m-%d")

            check_kap_news()
            scan_key = f"{current_date}_{current_time}"

            if current_time in TARGET_SCAN_TIMES and scan_key not in SCANNED_TIMES_TODAY:
                target_symbols = get_all_bist_tickers()
                scan_bist_stocks(target_symbols, current_time)
                SCANNED_TIMES_TODAY.add(scan_key)

            time.sleep(30)
        except KeyboardInterrupt:
            break
        except Exception:
            time.sleep(30)

if __name__ == "__main__":
    main()
