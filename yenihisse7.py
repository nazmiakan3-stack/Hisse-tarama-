#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import feedparser
from tradingview_ta import TA_Handler, Interval

# ============================================================
# SUNUCU & RENDER UPTIME SERVISI (Port 10000 - GET & HEAD Desteği)
# ============================================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"BIST Full Star Scanner Bot Active!")

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
# PARAMETRELER VE LİSTELER
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1734551753")

BIST_30_SET = {
    "AKBNK", "ALARK", "ASELS", "ASTOR", "BIMAS", "BRSAN", "DOAS", "EKGYO",
    "ENKAI", "EREGL", "FROTO", "GARAN", "GUBRF", "HEKTS", "ISCTR", "KCHOL",
    "KONTR", "KOZAL", "KRDMD", "ODAS", "OYAKC", "PETKM", "PGSUS", "SAHOL",
    "SASA", "SISE", "TCELL", "THYAO", "TOASO", "TUPRS"
}

TARGET_SCAN_TIMES = ["09:50", "10:10", "17:45"]

CANDIDATES_1745 = {}   
LATEST_KAP_NEWS = {}   # {symbol: {title, stars, category, link}}
PROCESSED_KAP_LINKS = set()
SCANNED_TIMES_TODAY = set()
IS_BOT_STARTED = False
BIST_FUNDAMENTALS = {} # {symbol: pddd_ratio}

KAP_STAR_MAP = {
    "bedelsiz": ("⭐⭐⭐⭐⭐", "Bedelsiz / Sermaye Artırımı"),
    "yeni iş ilişkisi": ("⭐⭐⭐⭐⭐", "Yeni İş İlişkisi / İhale"),
    "ortaklık": ("⭐⭐⭐⭐⭐", "Stratejik Ortaklık"),
    "ihale": ("⭐⭐⭐⭐", "İhale Sözleşmesi"),
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
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram Gönderim Hatası: {e}")

def fetch_is_yatirim_data():
    """BİST Verilerini ve Defter Değeri (PD/DD) Oranlarını Çeker"""
    global BIST_FUNDAMENTALS
    try:
        url = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/HisseTeknikVeriler"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json().get('d', [])
            for item in data:
                code = item.get('code')
                pddd = item.get('pd_dd')
                if code and pddd is not None:
                    try:
                        BIST_FUNDAMENTALS[code] = float(pddd)
                    except ValueError:
                        pass
    except Exception as e:
        print(f"İş Yatırım Veri Çekme Hatası: {e}")

def get_all_bist_tickers():
    fetch_is_yatirim_data()
    if BIST_FUNDAMENTALS:
        filtered = sorted(list(set(BIST_FUNDAMENTALS.keys()) - BIST_30_SET))
        if len(filtered) >= 300:
            return filtered
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

def check_kap_news():
    global PROCESSED_KAP_LINKS, LATEST_KAP_NEWS
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
                    for sym in FULL_BIST_LIST:
                        if f"#{sym.lower()}" in content or f" {sym.lower()} " in content:
                            found_symbol = sym
                            break

                    LATEST_KAP_NEWS[found_symbol] = {
                        "title": title,
                        "stars": stars,
                        "category": category,
                        "link": entry.link
                    }

                    msg = (
                        f"🔥 <b>[YÜKSEK HABER DEĞERİ - KAP İSTİHBARATI]</b>\n\n"
                        f"<b>Hisse:</b> #{found_symbol}\n"
                        f"<b>Etki Gücü:</b> {stars}\n"
                        f"<b>Kategori:</b> {category}\n"
                        f"<b>Başlık:</b> {title}\n"
                        f"<b>Link:</b> <a href='{entry.link}'>KAP Detay</a>"
                    )
                    send_telegram_msg(msg)
                    break
    except Exception as e:
        print(f"KAP Hatası: {e}")

def calculate_star_rating(change, rsi, pddd, kap_exists):
    """Dinamik 1-5 Yıldızlı Skorlama Sistemini Çalıştırır"""
    score = 1
    if change >= 9.5:
        score += 3
    elif change >= 5.0:
        score += 2
    elif rsi <= 25:
        score += 2

    if pddd is not None and pddd < 1.0:
        score += 1

    if kap_exists:
        score += 1

    score = min(score, 5)
    return "⭐" * score

# ============================================================
# TARAMA MODÜLÜ
# ============================================================
def scan_bist_stocks(symbol_list, scan_tag):
    global CANDIDATES_1745
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {scan_tag} Taraması Başladı...")
    found_count = 0

    if scan_tag == "17:45":
        CANDIDATES_1745.clear()

    for symbol in symbol_list:
        data = analyze_tv_stock(symbol)
        if not data or data["rsi"] is None or data["close"] is None:
            continue

        price = data["close"]
        rsi = data["rsi"]
        change = data["change"] or 0.0
        rec = data["recommendation"] or "N/A"
        pddd = BIST_FUNDAMENTALS.get(symbol, None)
        kap_data = LATEST_KAP_NEWS.get(symbol, None)

        pddd_str = f"{pddd:.2f}" if pddd is not None else "N/A"
        if pddd is not None and pddd < 1.0:
            pddd_str += " 💎 (Defter Değerinin Altında)"

        star_str = calculate_star_rating(change, rsi, pddd, kap_data is not None)
        kap_str = f"🔥 HABER VAR ({kap_data['category']})" if kap_data else "Yok"

        # 17:45 KAPANIŞ HAFIZALAMA
        if scan_tag == "17:45" and 5.0 <= change <= 9.99:
            CANDIDATES_1745[symbol] = {
                "price": price, "change": change, "rsi": rsi,
                "rec": rec, "pddd": pddd_str, "kap": kap_str,
                "stars": star_str
            }
            found_count += 1

        elif scan_tag != "17:45":
            # 1. TAVAN YAPAN HİSSELER (%9.5+)
            if change >= 9.5:
                msg = (
                    f"🚀 <b>[TAVAN KİLİT - {scan_tag}]</b>\n\n"
                    f"<b>Hisse Adı:</b> #{symbol}\n"
                    f"<b>Derece:</b> {star_str}\n"
                    f"<b>Fiyat / Değişim:</b> {price:.2f} TL (%{change:+.2f})\n"
                    f"<b>RSI (14):</b> {rsi:.1f} | <b>PD/DD:</b> {pddd_str}\n"
                    f"<b>KAP Haberi:</b> {kap_str}\n"
                    f"<b>Strateji:</b> Tavan Takibi / Güçlü Momentum"
                )
                send_telegram_msg(msg)
                found_count += 1

            # 2. %5.0 - %8.0 ARASI PRİMLİ HİSSELER
            elif 5.0 <= change <= 8.0:
                msg = (
                    f"📈 <b>[YÜKSEK PRİMLİ HİSSE (%5-%8) - {scan_tag}]</b>\n\n"
                    f"<b>Hisse Adı:</b> #{symbol}\n"
                    f"<b>Derece:</b> {star_str}\n"
                    f"<b>Fiyat / Değişim:</b> {price:.2f} TL (%{change:+.2f})\n"
                    f"<b>RSI (14):</b> {rsi:.1f} | <b>PD/DD:</b> {pddd_str}\n"
                    f"<b>KAP Haberi:</b> {kap_str}\n"
                    f"<b>Strateji:</b> Günlük Yükseliş Trendi"
                )
                send_telegram_msg(msg)
                found_count += 1

            # 3. DİP & DEFTER DEĞERİ DÜŞÜK HİSSELER (RSI <= 30 veya PD/DD < 0.8)
            elif rsi <= 30 or (pddd is not None and pddd < 0.8):
                msg = (
                    f"🛡️ <b>[DİP & DEĞER AVCISI - {scan_tag}]</b>\n\n"
                    f"<b>Hisse Adı:</b> #{symbol}\n"
                    f"<b>Derece:</b> {star_str}\n"
                    f"<b>Fiyat / Değişim:</b> {price:.2f} TL (%{change:+.2f})\n"
                    f"<b>RSI (14):</b> {rsi:.1f} | <b>PD/DD:</b> {pddd_str}\n"
                    f"<b>KAP Haberi:</b> {kap_str}\n"
                    f"<b>Strateji:</b> Kademeli Dip / Ucuz Defter Değeri Alımı"
                )
                send_telegram_msg(msg)
                found_count += 1

        time.sleep(0.04)

    if scan_tag != "17:45":
        send_telegram_msg(
            f"✅ <b>[{scan_tag} TAMAMLANDI]</b>\n"
            f"Toplam {len(symbol_list)} yan tahta taranıp analiz edildi.\n"
            f"Kriterlere Uyan Sinyal Sayısı: <b>{found_count} Adet</b>"
        )

def generate_2300_final_report():
    global CANDIDATES_1745
    
    if not CANDIDATES_1745:
        send_telegram_msg("🌙 <b>[23:00 YARININ TAVAN ADAYLARI RAPORU]</b>\n\nBugün 17:45 taramasında %5 - %9.99 arası primli hisse tespit edilemedi.")
        return

    msg = (
        "🌙 <b>[23:00 YARININ TAVAN ADAYLARI NİHAİ RAPORU]</b>\n"
        f"📊 17:45 Takibindeki Hisse Sayısı: <b>{len(CANDIDATES_1745)} Adet</b>\n"
        "───────────────────────────\n\n"
    )

    for sym, data in CANDIDATES_1745.items():
        msg += (
            f"📌 <b>#{sym}</b> | Derece: {data['stars']}\n"
            f"• <b>Kapanış Fiyatı:</b> {data['price']:.2f} TL (%{data['change']:+.2f})\n"
            f"• <b>RSI (14):</b> {data['rsi']:.1f} | <b>PD/DD:</b> {data['pddd']}\n"
            f"• <b>KAP Durumu:</b> {data['kap']}\n\n"
        )

    msg += "💡 <i>Not: Akşam KAP haberi olan ve Defter Değeri (PD/DD < 1.0) ucuz kalan hisseler yarın tavan açılışı için en yüksek potansiyele sahiptir.</i>"
    
    send_telegram_msg(msg)
    CANDIDATES_1745.clear()

# ============================================================
# ANA DÖNGÜ
# ============================================================
def main():
    global IS_BOT_STARTED
    symbols = get_all_bist_tickers()
    
    if not IS_BOT_STARTED:
        send_telegram_msg(
            "🤖 <b>TRADINGVIEW BİST YAN TAHTA V10 YILDIZLI BOT AKTİF!</b>\n"
            "⏰ Özel Tarama Saatleri: <b>09:50</b>, <b>10:10</b> ve <b>17:45</b>\n"
            f"📊 Toplam Taranan Yan Tahta: <b>~{len(symbols)} Adet</b>\n"
            "🌟 Derecelendirme: <b>1-5 Yıldızlı Skor Sistemi</b>\n"
            "🔍 Aktif Filtreler: <b>Tavan (%9.5+), %5-%8 Primliler, Defter Değeri (PD/DD < 1.0), KAP Haber Eşleşmesi</b>"
        )
        IS_BOT_STARTED = True

        try:
            send_telegram_msg(
                "🚀 <b>[BOT BAŞLATILDI - İLK KONTROL TARAMASI BAŞLADI]</b>\n"
                f"Toplam {len(symbols)} adet yan tahta taranıyor..."
            )
            scan_bist_stocks(symbols, "İLK BAŞLATMA TARAMASI")
        except Exception as e:
            print(f"Açılış tarama hatası: {e}")

    while True:
        try:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            current_date = now.strftime("%Y-%m-%d")

            check_kap_news()

            scan_key = f"{current_date}_{current_time}"

            if current_time in TARGET_SCAN_TIMES and scan_key not in SCANNED_TIMES_TODAY:
                if current_time == "17:45":
                    send_telegram_msg("⏰ <b>[17:45 KAPANIŞ TARAMASI BAŞLADI]</b>\n%5 - %9.99 arası primli yan tahtalar akşam analizi için hafızaya alınıyor...")
                
                scan_bist_stocks(symbols, current_time)
                SCANNED_TIMES_TODAY.add(scan_key)
                
                if current_time == "17:45":
                    send_telegram_msg(f"✅ <b>[17:45 TARAMASI BİTTİ]</b>\nToplam <b>{len(CANDIDATES_1745)}</b> adet %5-%9.99 arası hisse 23:00 raporu için takibe alındı.")

            if current_time == "23:00" and scan_key not in SCANNED_TIMES_TODAY:
                generate_2300_final_report()
                SCANNED_TIMES_TODAY.add(scan_key)

            time.sleep(30)

        except Exception as e:
            print(f"Döngü Hatası: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
