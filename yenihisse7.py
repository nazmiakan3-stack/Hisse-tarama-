#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import threading
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, HTTPServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("BISTBot")

try:
    import requests
    import feedparser
    import yfinance as yf
    import pandas as pd
    import pandas_ta as ta
except ModuleNotFoundError as e:
    print(f"\n❌ EKSİK KÜTÜPHANE: {e}")
    print("👉 pip install requests feedparser yfinance pandas pandas-ta\n")
    exit(1)

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
    logger.info(f"Health-check sunucusu port {port} üzerinde başladı")
    server.serve_forever()

threading.Thread(target=start_health_check_server, daemon=True).start()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1734551753")

TZ = ZoneInfo("Europe/Istanbul")
TARGET_SCAN_TIMES = ["09:50", "10:10", "17:45", "23:00"]

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

FULL_BIST_LIST = [  # (liste aynı, kısaltıyorum - önceki uzun listeyi kullan)
    "A1CAP", "AAVTUR", "ACSEL", "ADEL", "ADESE", "AEFES", "AFYON", "AGESA", "AGHOL",
    # ... (önceki FULL_BIST_LIST'in tamamını buraya koy)
    "ZRGYO"
]

PROCESSED_KAP_LINKS = set()
SCANNED_TIMES_TODAY = set()

def send_telegram_msg(message: str):
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
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
        requests.post(url, json=payload, timeout=12)
    except Exception as e:
        logger.warning(f"Telegram gönderim hatası: {e}")

def format_compact_volume(v):
    try:
        v = float(v)
        if v >= 1_000_000: return f"{v/1_000_000:.1f}M"
        if v >= 1_000: return f"{v/1_000:.0f}K"
        return str(int(v))
    except: return "0"

def get_all_bist_tickers():
    try:
        url = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/HisseTeknikVeriler"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json().get("d", [])
            fetched = {item.get("code") for item in data if item.get("code") and len(item.get("code", "")) <= 5}
            filtered = sorted(list(fetched))
            if len(filtered) >= 300:
                logger.info(f"Canlı BIST listesi alındı: {len(filtered)} hisse")
                return filtered
    except Exception as e:
        logger.warning(f"Canlı liste alınamadı: {e}")
    return sorted(list(set(FULL_BIST_LIST) | BIST_30_SET))

def check_kap_news():
    global PROCESSED_KAP_LINKS
    try:
        feed = feedparser.parse("https://www.kap.org.tr/tr/rss")
        for entry in feed.entries[:25]:
            if entry.link in PROCESSED_KAP_LINKS: continue
            title = entry.title or ""
            summary = getattr(entry, "summary", "") or ""
            content_lower = (title + " " + summary).lower()
            for key, (stars, category) in KAP_STAR_MAP.items():
                if key in content_lower:
                    PROCESSED_KAP_LINKS.add(entry.link)
                    send_telegram_msg(
                        f"🔥 <b>[YÜKSEK HABER DEĞERİ]</b>\n"
                        f"<b>Etki:</b> {stars}\n"
                        f"<b>Başlık:</b> {title}\n"
                        f"<b>Link:</b> <a href='{entry.link}'>KAP Detayı</a>"
                    )
                    time.sleep(0.4)
                    break
    except Exception as e:
        logger.debug(f"KAP RSS hatası: {e}")

def get_kap_news_api(symbol: str):
    onemli = ["yeni iş ilişkisi", "ihale", "finansal rapor", "bilanço", "kar payı", "sermaye artırımı", "pay alım", "birleşme", "bedelsiz"]
    try:
        url = f"https://www.kap.org.tr/tr/api/disclosures?code={symbol}"
        response = requests.get(url, timeout=6, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            data = response.json()
            if data and isinstance(data, list) and len(data) > 0:
                son = data[0]
                baslik = son.get("title", "Özel Durum Açıklaması")
                ozet = son.get("summary") or baslik
                full_text = f"{baslik} {ozet}".lower()
                is_important = any(k in full_text for k in onemli)
                return f"{baslik}: {ozet[:55]}...", is_important
    except: pass
    return "Aktif bildirim yok", False

def analyze_ticker(symbol: str):
    try:
        ticker = yf.Ticker(f"{symbol}.IS")
        df = ticker.history(period="6mo", interval="1d", auto_adjust=True)
        if df is None or len(df) < 35: return None

        last_close = float(df["Close"].iloc[-1])
        prev_close = float(df["Close"].iloc[-2])
        change_pct = ((last_close - prev_close) / prev_close) * 100

        last_volume = float(df["Volume"].iloc[-1])
        hacim_tl = last_volume * last_close

        avg_vol_5 = df["Volume"].iloc[-6:-1].mean()
        rvol_5 = last_volume / avg_vol_5 if avg_vol_5 > 0 else 0
        avg_vol_10 = df["Volume"].iloc[-11:-1].mean()
        rvol = last_volume / avg_vol_10 if avg_vol_10 > 0 else 0

        # RSI
        rsi = df.ta.rsi(length=14)
        rsi_d = float(rsi.iloc[-1]) if rsi is not None else 50

        # Stochastic
        stoch = df.ta.stoch(k=14, d=3, smooth_k=3)
        stoch_k = 50
        stoch_alimda = False
        if stoch is not None and not stoch.empty:
            k_col = next((c for c in stoch.columns if "STOCHk" in c), None)
            d_col = next((c for c in stoch.columns if "STOCHd" in c), None)
            if k_col and d_col:
                stoch_k = float(stoch[k_col].iloc[-1])
                stoch_d = float(stoch[d_col].iloc[-1])
                stoch_alimda = (stoch_k < 20) or (stoch_k > stoch_d and stoch_k < 35)

        # Bollinger
        bb = df.ta.bbands(length=20, std=2)
        bb_destek = False
        if bb is not None and not bb.empty:
            lower_col = next((c for c in bb.columns if "BBL" in c), None)
            if lower_col:
                bb_lower = float(bb[lower_col].iloc[-1])
                bb_destek = last_close <= (bb_lower * 1.03) and last_close >= (bb_lower * 0.97)

        # PD/DD
        pb_ratio = None
        try:
            info = ticker.info
            pb_ratio = info.get("priceToBook") or info.get("priceToBookRatio")
            if pb_ratio: pb_ratio = float(pb_ratio)
        except: pass

        # 5 günlük değişim
        close_5d = float(df["Close"].iloc[-6]) if len(df) >= 6 else last_close
        change_5d = ((last_close - close_5d) / close_5d) * 100
        asiri_zarar_yok = change_5d > -12

        kap_ozeti, kap_onemli = get_kap_news_api(symbol)

        # === STRATEJİLER ===
        strateji_a = (rsi_d < 30 and stoch_alimda and hacim_tl >= 20_000_000 and rvol >= 1.0 and change_pct > 0)
        strateji_b = (bb_destek and pb_ratio is not None and pb_ratio < 1.5 and rvol_5 >= 1.2 and asiri_zarar_yok and hacim_tl >= 8_000_000)

        # Yeni: %5+ yükselenler
        yuzde_5_ustu = change_pct >= 5.0 and hacim_tl >= 5_000_000

        # Yeni: Saf hacim patlaması listesi
        hacim_patlamasi = hacim_tl >= 20_000_000 and rvol >= 1.0

        if not (strateji_a or strateji_b or yuzde_5_ustu or hacim_patlamasi):
            return None

        yildiz = 3
        if rvol >= 2.0 or rvol_5 >= 2.0: yildiz += 1
        if bb_destek: yildiz += 1
        if kap_onemli: yildiz += 1
        if pb_ratio and pb_ratio < 1.0: yildiz += 1
        if change_pct >= 5: yildiz += 1
        yildizlar = "⭐" * min(yildiz, 5)

        return {
            "symbol": symbol,
            "fiyat": round(last_close, 2),
            "change_pct": round(change_pct, 2),
            "rsi_d": round(rsi_d, 1),
            "stoch_k": round(stoch_k, 1),
            "rvol": round(rvol, 2),
            "rvol_5": round(rvol_5, 2),
            "hacim_tl": format_compact_volume(hacim_tl),
            "hacim_tl_raw": hacim_tl,
            "kap_ozeti": kap_ozeti,
            "kap_onemli": kap_onemli,
            "yildizlar": yildizlar,
            "pb_ratio": round(pb_ratio, 2) if pb_ratio else None,
            "strateji_a": strateji_a,
            "strateji_b": strateji_b,
            "yuzde_5_ustu": yuzde_5_ustu,
            "hacim_patlamasi": hacim_patlamasi,
        }
    except Exception as e:
        logger.debug(f"{symbol} hata: {e}")
        return None

def scan_bist_stocks(symbol_list, scan_time: str):
    now_str = datetime.now(TZ).strftime("%H:%M:%S")
    logger.info(f"[{now_str}] Tarama başladı → {scan_time} | {len(symbol_list)} hisse")

    strateji_list = []
    yuzde5_list = []
    hacim_list = []

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(analyze_ticker, sym): sym for sym in symbol_list}
        for future in as_completed(futures):
            res = future.result()
            if res:
                if res["strateji_a"] or res["strateji_b"]:
                    strateji_list.append(res)
                if res["yuzde_5_ustu"]:
                    yuzde5_list.append(res)
                if res["hacim_patlamasi"]:
                    hacim_list.append(res)

    # Sıralamalar
    strateji_list.sort(key=lambda x: (x["kap_onemli"], x["rvol"]), reverse=True)
    yuzde5_list.sort(key=lambda x: x["change_pct"], reverse=True)
    hacim_list.sort(key=lambda x: x["hacim_tl_raw"], reverse=True)

    baslik_ek = "🌙 GECE BÜLTENİ" if scan_time == "23:00" else "GÜN İÇİ TARAMASI"
    tarih = datetime.now(TZ).strftime('%d.%m.%Y - %H:%M')

    # 1. Ana Strateji Listesi
    if strateji_list:
        mesaj = f"🎯 <b>[ANA STRATEJİ | {baslik_ek}]</b>\n📅 <i>{tarih}</i>\n\n"
        for item in strateji_list[:15]:
            tip = "Klasik Dip" if item["strateji_a"] else "BB + Düşük PD/DD"
            mesaj += (
                f"🔹 <b>#{item['symbol']}</b> | {item['fiyat']} TL (%+{item['change_pct']}) {'🚨' if item['kap_onemli'] else ''}\n"
                f"├ {tip} {item['yildizlar']}\n"
                f"├ Hacim: {item['hacim_tl']} | RVOL: {item['rvol']}x\n"
                f"├ RSI: {item['rsi_d']} | Stoch: {item['stoch_k']}\n"
                f"└ KAP: <i>{item['kap_ozeti']}</i>\n\n"
            )
            if len(mesaj) > 3500:
                send_telegram_msg(mesaj)
                mesaj = ""
        if mesaj.strip():
            send_telegram_msg(mesaj)
    else:
        send_telegram_msg(f"ℹ️ <b>{scan_time}</b> - Ana stratejiye uyan hisse yok.")

    # 2. %5 ve üzeri yükselenler
    if yuzde5_list:
        mesaj = f"🚀 <b>[%5 VE ÜZERİ YÜKSELENLER | {baslik_ek}]</b>\n📅 <i>{tarih}</i>\n\n"
        for item in yuzde5_list[:12]:
            mesaj += (
                f"🔹 <b>#{item['symbol']}</b> | {item['fiyat']} TL <b>(%+{item['change_pct']})</b>\n"
                f"├ Hacim: {item['hacim_tl']} | RVOL: {item['rvol']}x\n"
                f"└ KAP: <i>{item['kap_ozeti']}</i>\n\n"
            )
            if len(mesaj) > 3500:
                send_telegram_msg(mesaj)
                mesaj = ""
        if mesaj.strip():
            send_telegram_msg(mesaj)

    # 3. Hacim Patlaması Listesi (20M+ ve RVOL≥1)
    if hacim_list:
        mesaj = f"💥 <b>[HACİM PATLAMASI ≥20M + RVOL≥1 | {baslik_ek}]</b>\n📅 <i>{tarih}</i>\n\n"
        for item in hacim_list[:15]:
            mesaj += (
                f"🔹 <b>#{item['symbol']}</b> | {item['fiyat']} TL (%+{item['change_pct']})\n"
                f"├ Hacim: <b>{item['hacim_tl']}</b> | RVOL: <b>{item['rvol']}x</b>\n"
                f"└ KAP: <i>{item['kap_ozeti']}</i>\n\n"
            )
            if len(mesaj) > 3500:
                send_telegram_msg(mesaj)
                mesaj = ""
        if mesaj.strip():
            send_telegram_msg(mesaj)

    logger.info(f"Tarama bitti → Strateji:{len(strateji_list)} | %5+:{len(yuzde5_list)} | Hacim:{len(hacim_list)}")

def main():
    now = datetime.now(TZ)
    current_time_str = now.strftime("%H:%M")

    send_telegram_msg(
        "🤖 <b>BİST BOTU - SON VERSİYON</b>\n"
        "• Ana Strateji (RSI + BB + PD/DD)\n"
        "• %5 ve üzeri yükselenler\n"
        "• Hacim ≥20M + RVOL ≥1 listesi\n"
        "🚀 Sistem aktif..."
    )

    try:
        check_kap_news()
        hedef = get_all_bist_tickers()
        scan_bist_stocks(hedef, f"İLK AÇILIŞ TESTİ ({current_time_str})")
        send_telegram_msg("✅ Açılış testi tamamlandı! Alarm saatleri bekleniyor.")
    except Exception as e:
        send_telegram_msg(f"❌ Açılış hatası: {e}")

    while True:
        try:
            now = datetime.now(TZ)
            loop_time = now.strftime("%H:%M")
            loop_date = now.strftime("%Y-%m-%d")
            check_kap_news()
            scan_key = f"{loop_date}_{loop_time}"
            if loop_time in TARGET_SCAN_TIMES and scan_key not in SCANNED_TIMES_TODAY:
                hedef = get_all_bist_tickers()
                scan_bist_stocks(hedef, loop_time)
                SCANNED_TIMES_TODAY.add(scan_key)
                if loop_time == "23:00":
                    PROCESSED_KAP_LINKS.clear()
                    SCANNED_TIMES_TODAY.clear()
            time.sleep(25)
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Döngü hatası: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
