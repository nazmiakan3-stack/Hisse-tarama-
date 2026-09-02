#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import re
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import feedparser
from tradingview_ta import TA_Handler, Interval

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
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=start_health_check_server, daemon=True).start()

# ============================================================
# TELEGRAM VE PARAMETRE AYARLARI
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1734551753")

# Takip Edilecek Popüler Kripto Çiftleri
CRYPTO_LIST = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT", "NEARUSDT", 
    "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LINKUSDT", "DOTUSDT",
    "BNBUSDT", "APTUSDT", "SUIUSDT", "PEPEUSDT", "SHIBUSDT"
]

BIST_30_SET = {
    "AKBNK", "ALARK", "ASELS", "ASTOR", "BIMAS", "BRSAN", "DOAS", "EKGYO",
    "ENKAI", "EREGL", "FROTO", "GARAN", "GUBRF", "HEKTS", "ISCTR", "KCHOL",
    "KONTR", "KOZAL", "KRDMD", "ODAS", "OYAKC", "PETKM", "PGSUS", "SAHOL",
    "SASA", "SISE", "TCELL", "THYAO", "TOASO", "TUPRS"
}

TARGET_SCAN_TIMES = ["09:50", "10:10", "17:45"]

# Akşam Analizi Hafızası
CANDIDATES_1745 = {}   # {symbol: {price, change, rsi, rec}}
EVENING_KAP_NEWS = []  # [{symbol, title, link, stars, category}]
PROCESSED_KAP_LINKS = set()
SCANNED_TIMES_TODAY = set()

KAP_STAR_MAP = {
    "bedelsiz": ("⭐⭐⭐⭐⭐", "Yüksek Oranlı Bedelsiz / Sermaye Artırımı"),
    "yeni iş ilişkisi": ("⭐⭐⭐⭐⭐", "Yeni İş İlişkisi / Dev İhale"),
    "ortaklık": ("⭐⭐⭐⭐⭐", "Stratejik İş Ortaklığı / M&A"),
    "ihale": ("⭐⭐⭐⭐", "İhale Sözleşmesi / Dev Sipariş"),
    "pay alım": ("⭐⭐⭐⭐", "Şirket Pay Geri Alımı")
}

FULL_BIST_LIST = [
    "AAVTUR", "ACSEL", "ADEL", "ADESE", "ADGYO", "AEFES", "AFYON", "AGESA", "AGHOL", "AGROT",
    "AHGAZ", "AKBNK", "AKCNS", "AKFGY", "AKFYE", "AKMGY", "AKSA", "AKSEN", "AKSGY", "AKSUE",
    "ALARK", "ALBRK", "ALCAR", "ALCTL", "ALFAS", "ALGYO", "ALKA", "ALKIM", "ALMAD", "ALTNY",
    "ALVES", "ANELE", "ANGEN", "ANHYT", "ANSGR", "ARASE", "ARCLK", "ARDYZ", "ARENA", "ARSAN",
    "ARTMS", "ARZUM", "ASELS", "ASGYO", "ASTOR", "ASUZU", "ATAGY", "ATAKP", "ATATP", "ATEKS",
    "AVGYO", "AVHOL", "AVOD", "AYCES", "AYDEM", "AYEN", "AYGAZ", "AZTEK", "BAGFS", "BAKAB",
    "BANVT", "BARMA", "BATIS", "BTCIM", "BYDNR", "BEGYO", "BERA", "BEYAZ", "BFREN", "BIENP",
    "BIGCHE", "BIMAS", "BINBN", "BIOEN", "BIZIM", "BJKAS", "BLCYO", "BMTKS", "BNTAS", "BOBET",
    "BORLS", "BORSK", "BOSSA", "BRCVN", "BRISA", "BRKO", "BRKSN", "BRSAN", "BRYAT", "BSOKE",
    "BUCIM", "BURCE", "BURVA", "BVSAN", "CANTE", "CCOLA", "CELHA", "CEMAS", "CEMTS", "CMBTN",
    "CONSE", "COSMO", "CRDFA", "CRFSA", "CUSAN", "CVMEK", "CWENE", "DAGI", "DAPGM", "DARDL",
    "DGATE", "DGGYO", "DITAS", "DMRGD", "DMSAS", "DNISI", "DOAS", "DOBUR", "DOCTA", "DOGUB",
    "DOHOL", "DURDO", "DYOBY", "EDATA", "EDIP", "EGEEN", "EGEPO", "EGGUB", "EGPRO", "EGSER",
    "EKGYO", "EKOS", "EKSUN", "ELITE", "EMKEL", "ENERY", "ENKAI", "ENSRI", "EPLAS", "ERCB",
    "EREGL", "ERSU", "ESCAR", "ESCOM", "ESEN", "ETILR", "EUPWR", "EYGYO", "FADE", "FENER",
    "FLAP", "FMIZP", "FONET", "FORTE", "FORMT", "FRIGO", "FROTO", "FZLGY", "GARAN", "GARFA",
    "GEDIK", "GEDZA", "GENKE", "GENTS", "GEREL", "GESAN", "GIPTA", "GLBMD", "GLYHO", "GMTAS",
    "GOKNR", "GOLTS", "GOODY", "GOZDE", "GRSEL", "GRTRK", "GSDHO", "GSDDE", "GSRAY", "GUBRF",
    "GWIND", "HALKB", "HATEK", "HATSN", "HDFGS", "HEDEF", "HEKTS", "HKTM", "HLGYO", "HOROZ",
    "HUBVC", "HUNER", "HURGZ", "ICBCT", "IDEAS", "IDGYO", "IEYHO", "IHAAS", "IHEVA", "IHGZT",
    "IHLGM", "IHLAS", "INGRM", "INTEM", "INVEO", "INVES", "IPEKE", "ISATR", "ISBTR", "ISCTR",
    "ISDMR", "ISFIN", "ISGSY", "ISGYO", "ISKPL", "ISMEN", "ISSEN", "IZMDC", "JANTS", "KAREL",
    "KARSN", "KARTN", "KATMR", "KAYSE", "KBORU", "KCAER", "KCHOL", "KENT", "KRVGD", "KGYO",
    "KIMMR", "KLGYO", "KLMSN", "KLNMA", "KLSER", "KLSYN", "KNFRT", "KONKA", "KONTR", "KONYA",
    "KOTON", "KOZAL", "KOZAA", "KRDMD", "KRDMA", "KRDMB", "KRPLS", "KRSTL", "KRTEK", "KTLEV",
    "KTSKR", "KUTPO", "LIDER", "LIDFA", "LINK", "LKMNH", "LMKDC", "LOGO", "LUKSK", "MAALT",
    "MACKO", "MAGEN", "MAKIM", "MAKTK", "MANAS", "MARKA", "MAVI", "MEDTR", "MEGAP", "MEGMT",
    "MEPET", "MERCN", "MERIT", "MERKO", "METRO", "METUR", "MHRGY", "MIATK", "MIPAZ", "MMCAS",
    "MNDTR", "MOBTL", "MOGAN", "MPARK", "MRGYO", "MRSHL", "MSGYO", "MTRKS", "MTRYO", "NATEN",
    "NETAS", "NIBAS", "NTHOL", "NUGYO", "NUHCM", "OBAMS", "OBASE", "ODAS", "OFSYM", "ONCSM",
    "ORGE", "ORMA", "OSMEN", "OSTIM", "OTKAR", "OTTO", "OYAKC", "OYAYO", "OYLUM", "OYYAT",
    "OZKGY", "OZRDN", "OZSUB", "PAGYO", "PAMEL", "PAPIL", "PARSN", "PASEU", "PATEK", "PCILT",
    "PEKGY", "PENTA", "PETKM", "PETUN", "PGSUS", "PINAR", "PKENT", "PKART", "PLTUR", "PNLSN",
    "PNSUT", "POLHO", "POLTK", "PRDGS", "PRKAB", "PRKME", "PRZMA", "PSDTC", "PSGYO", "QUAGR",
    "RALYH", "RAYSG", "REEDR", "RGYAS", "RHEAG", "RNPOL", "RODRG", "ROYAL", "RUBNS", "RYGYO",
    "RYSAS", "SAHOL", "SAMAT", "SANEL", "SANFM", "SANKO", "SARKY", "SASA", "SAYAS", "SDTTR",
    "SEGMN", "SEKFK", "SEKUR", "SELEC", "SELVA", "SEYKM", "SILVR", "SISE", "SKBNK", "SKTAS",
    "SMART", "SMRTG", "SODSN", "SOKE", "SOKM", "SONME", "SRVGY", "SUMAS", "SUNTK", "SURGY",
    "SUWEN", "TABGD", "TARKM", "TATEN", "TATGD", "TAVHL", "TBORG", "TCELL", "TDGYO", "TEKTN",
    "TERA", "TETMT", "TEZOL", "TGSAS", "THYAO", "TIRE", "TKFEN", "TKNSA", "TLMAN", "TMPOL",
    "TMSN", "TNZTP", "TOASO", "TRGYO", "TRILC", "TSKB", "TSPOR", "TUCLK", "TUPRS", "TUREKS",
    "TURGG", "TURSG", "UFUK", "ULAS", "ULKER", "ULUFA", "ULUSE", "UNLU", "USAK", "VAKBN",
    "VAKFN", "VAKKO", "VERUS", "VESBE", "VESTL", "VKFYO", "VKGYO", "YAPRK", "YATAS", "YAYLA",
    "YEOTK", "YGGYO", "YGYO", "YKBNK", "YNKGY", "YONGA", "YYLGD", "ZEDUR", "ZOREN", "ZRGYO"
]

def send_telegram_msg(message):
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN" or not TELEGRAM_BOT_TOKEN:
        print(f"\n[TELEGRAM MESAJI]:\n{message}\n")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram Gönderim Hatası: {e}")

def get_all_bist_tickers():
    try:
        url = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/HisseTeknikVeriler"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json().get('d', [])
            fetched = {item.get('code') for item in data if item.get('code') and len(item.get('code')) <= 5}
            filtered = sorted(list(fetched - BIST_30_SET))
            if len(filtered) >= 400:
                return filtered
    except Exception:
        pass
    return sorted(list(set(FULL_BIST_LIST) - BIST_30_SET))

def analyze_tv_stock(symbol):
    try:
        handler = TA_Handler(
            symbol=symbol,
            screener="turkey",
            exchange="BIST",
            interval=Interval.INTERVAL_1_DAY
        )
        analysis = handler.get_analysis()
        ind = analysis.indicators
        return {
            "close": ind.get("close"),
            "change": ind.get("change"),
            "rsi": ind.get("RSI"),
            "recommendation": analysis.summary.get("RECOMMENDATION")
        }
    except Exception:
        return None

def analyze_tv_crypto(symbol):
    try:
        handler = TA_Handler(
            symbol=symbol,
            screener="crypto",
            exchange="BINANCE",
            interval=Interval.INTERVAL_1_DAY
        )
        analysis = handler.get_analysis()
        ind = analysis.indicators
        return {
            "close": ind.get("close"),
            "change": ind.get("change"),
            "rsi": ind.get("RSI"),
            "recommendation": analysis.summary.get("RECOMMENDATION")
        }
    except Exception:
        return None

def scan_crypto():
    found_count = 0
    for coin in CRYPTO_LIST:
        data = analyze_tv_crypto(coin)
        if not data or data["rsi"] is None or data["close"] is None:
            continue
            
        price = data["close"]
        rsi = data["rsi"]
        change = data["change"] or 0.0
        rec = data["recommendation"] or "N/A"

        if rsi <= 30:
            send_telegram_msg(f"🪙 <b>[KRİPTO DİP AVCISI]</b>\n<b>#{coin}</b> - ${price:.4f} (%{change:+.2f}) | RSI: {rsi:.1f}")
            found_count += 1
        elif rsi >= 65 and change >= 4.0 and rec in ["STRONG_BUY", "BUY"]:
            send_telegram_msg(f"⚡ <b>[KRİPTO MOMENTUM]</b>\n<b>#{coin}</b> - ${price:.4f} (%{change:+.2f}) | RSI: {rsi:.1f}")
            found_count += 1

        time.sleep(0.05)
    return found_count

def check_kap_news():
    global PROCESSED_KAP_LINKS, EVENING_KAP_NEWS
    try:
        feed = feedparser.parse("https://www.kap.org.tr/tr/rss")
        for entry in feed.entries[:25]:
            if entry.link in PROCESSED_KAP_LINKS:
                continue

            title = entry.title
            summary = entry.summary if 'summary' in entry else ""
            content = (title + " " + summary).lower()

            for key, (stars, category) in KAP_STAR_MAP.items():
                if key in content:
                    PROCESSED_KAP_LINKS.add(entry.link)
                    
                    found_symbol = "GENEL"
                    for sym in CANDIDATES_1745.keys():
                        if sym.lower() in content:
                            found_symbol = sym
                            break
                    
                    news_data = {
                        "symbol": found_symbol,
                        "title": title,
                        "link": entry.link,
                        "stars": stars,
                        "category": category
                    }

                    msg = (
                        f"🔥 <b>[YÜKSEK HABER DEĞERİ - KAP İSTİHBARATI]</b>\n\n"
                        f"<b>Etki Gücü:</b> {stars}\n"
                        f"<b>Kategori:</b> {category}\n"
                        f"<b>Başlık:</b> {title}\n"
                        f"<b>Link:</b> <a href='{entry.link}'>KAP Detay</a>"
                    )
                    send_telegram_msg(msg)

                    now_hour = datetime.now().hour
                    if 18 <= now_hour < 22:
                        EVENING_KAP_NEWS.append(news_data)
                    break
    except Exception as e:
        print(f"KAP Hatası: {e}")

def scan_bist_stocks(symbol_list, scan_time):
    global CANDIDATES_1745
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {scan_time} BİST Taraması...")
    found_count = 0

    if scan_time == "17:45":
        CANDIDATES_1745.clear()

    for symbol in symbol_list:
        data = analyze_tv_stock(symbol)
        if not data or data["rsi"] is None or data["close"] is None:
            continue

        price = data["close"]
        rsi = data["rsi"]
        change = data["change"] or 0.0
        rec = data["recommendation"] or "N/A"

        if scan_time == "17:45" and 5.0 <= change <= 9.99:
            CANDIDATES_1745[symbol] = {
                "price": price,
                "change": change,
                "rsi": rsi,
                "rec": rec
            }
            found_count += 1

        elif scan_time != "17:45":
            if rsi <= 30:
                send_telegram_msg(f"🛡️ <b>[BİST DİP AVCISI - {scan_time}]</b>\n<b>#{symbol}</b> - {price:.2f} TL (%{change:+.2f}) | RSI: {rsi:.1f}")
                found_count += 1
            elif rsi >= 50 and change >= 2.5 and rec in ["STRONG_BUY", "BUY"]:
                send_telegram_msg(f"🚀 <b>[BİST MOMENTUM - {scan_time}]</b>\n<b>#{symbol}</b> - {price:.2f} TL (%{change:+.2f}) | RSI: {rsi:.1f}")
                found_count += 1

        time.sleep(0.04)
        
    return found_count

def generate_2300_final_report():
    global CANDIDATES_1745, EVENING_KAP_NEWS
    
    if not CANDIDATES_1745:
        send_telegram_msg("🌙 <b>[23:00 YARININ TAVAN ADAYLARI RAPORU]</b>\n\nBugün 17:45 taramasında %5 - %9.99 arası primli hisse tespit edilemedi.")
        return

    msg = (
        "🌙 <b>[23:00 YARININ TAVAN ADAYLARI NİHAİ RAPORU]</b>\n"
        f"📊 17:45 Takibindeki Hisse Sayısı: <b>{len(CANDIDATES_1745)} Adet</b>\n"
        "───────────────────────────\n\n"
    )

    for sym, data in CANDIDATES_1745.items():
        related_news = [news for news in EVENING_KAP_NEWS if news["symbol"] == sym]
        
        kap_status = "Yok"
        star_rating = "⭐⭐⭐"
        
        if related_news:
            kap_status = f"🔥 HABER VAR ({related_news[0]['category']})"
            star_rating = "⭐⭐⭐⭐⭐"
        elif data["change"] >= 8.0:
            star_rating = "⭐⭐⭐⭐"

        msg += (
            f"📌 <b>#{sym}</b> | Derece: {star_rating}\n"
            f"• <b>Kapanış Fiyatı:</b> {data['price']:.2f} TL (%{data['change']:+.2f})\n"
            f"• <b>RSI (14):</b> {data['rsi']:.1f} | <b>Sinyal:</b> {data['rec']}\n"
            f"• <b>Akşam KAP Durumu:</b> {kap_status}\n\n"
        )

    msg += "💡 <i>Not: Akşam KAP haberi ile kapanış primi yüksek olan hisseler yarın tavan açılışı için en güçlü adaylardır.</i>"
    
    send_telegram_msg(msg)
    
    CANDIDATES_1745.clear()
    EVENING_KAP_NEWS.clear()

def main():
    send_telegram_msg(
        "🤖 <b>BİST + KRİPTO + KAP ANALİZ BOTU AKTİF!</b>\n"
        "⏰ BİST Taramaları: <b>09:50</b>, <b>10:10</b>, <b>17:45</b>\n"
        "🪙 Kripto Takibi: <b>Aktif</b>\n"
        "🌙 Akşam KAP Analiz Raporu: <b>23:00</b>"
    )

    # İlk Başlatma Taramaları (BİST + KRİPTO)
    try:
        send_telegram_msg("🔍 <b>[İLK BAŞLATMA TARAMASI BAŞLADI]</b>\nBİST hisseleri ve Kripto piyasası taranıyor...")
        
        # 1. Kripto Taraması
        crypto_found = scan_crypto()
        
        # 2. BİST Taraması
        init_symbols = get_all_bist_tickers()
        bist_found = scan_bist_stocks(init_symbols, "AÇILIŞ KONTROLÜ")
        
        send_telegram_msg(
            f"✅ <b>[İLK BAŞLATMA TARAMASI BİTTİ]</b>\n"
            f"• Tespit Edilen BİST Sinyali: <b>{bist_found}</b> Adet\n"
            f"• Tespit Edilen Kripto Sinyali: <b>{crypto_found}</b> Adet"
        )
    except Exception as e:
        print(f"Açılış tarama hatası: {e}")
        send_telegram_msg(f"⚠️ <b>İlkleme Taraması Hatası:</b> {e}")

    last_crypto_scan_time = 0

    while True:
        try:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            current_date = now.strftime("%Y-%m-%d")

            # KAP Haberlerini Anlık Kontrol Et
            check_kap_news()

            # Kripto Taramasını Her 30 Dakikada Bir Otomatik Çalıştır
            if time.time() - last_crypto_scan_time > 1800:
                scan_crypto()
                last_crypto_scan_time = time.time()

            scan_key = f"{current_date}_{current_time}"

            # BİST Zamanlı Taramalar (09:50, 10:10, 17:45)
            if current_time in TARGET_SCAN_TIMES and scan_key not in SCANNED_TIMES_TODAY:
                symbols = get_all_bist_tickers()
                if current_time == "17:45":
                    send_telegram_msg("⏰ <b>[17:45 KAPANIŞ TARAMASI BAŞLADI]</b>\n%5 - %9.99 arası primli yan tahtalar akşam analizi için hafızaya alınıyor...")
                
                scan_bist_stocks(symbols, current_time)
                SCANNED_TIMES_TODAY.add(scan_key)
                
                if current_time == "17:45":
                    send_telegram_msg(f"✅ <b>[17:45 TARAMASI BİTTİ]</b>\nToplam <b>{len(CANDIDATES_1745)}</b> adet %5-%9.99 arası hisse 23:00 raporu için takibe alındı.")

            # 23:00 Raporu
            if current_time == "23:00" and scan_key not in SCANNED_TIMES_TODAY:
                generate_2300_final_report()
                SCANNED_TIMES_TODAY.add(scan_key)

            time.sleep(30)

        except Exception as e:
            print(f"Döngü Hatası: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
