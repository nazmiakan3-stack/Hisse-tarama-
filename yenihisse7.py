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
    import yfinance as yf  # BİLANÇO VE DEFTER DEĞERİ İÇİN
    from tradingview_ta import Interval, get_multiple_analysis
    from gtts import gTTS  # BOTA KONUŞMA YETENEĞİ VEREN KÜTÜPHANE
except ModuleNotFoundError as e:
    print(f"\n❌ EKSİK KÜTÜPHANE TESPİT EDİLDİ: {e}")
    print("👉 Lütfen terminale şu komutu yazarak gerekli paketleri yükleyin:")
    print("pip install requests feedparser tradingview-ta gTTS yfinance\n")
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

TARGET_SCAN_TIMES = ["09:50", "10:10", "17:45", "23:00"]

RSI_DIP_LIMIT = 30             
TOP_GAINER_LIMIT = 5.0         
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
    "A1CAP", "AAVTUR", "ACSEL", "ADEL", "ADESE", "ADGYO", "AEFES", "AFYON", "AGESA", "AGHOL", 
    "AGROT", "AHGAZ", "AKBNK", "AKCNS", "AKENR", "AKFGY", "AKFYE", "AKGRT", "AKMGY", "AKSA", 
    "AKSEN", "AKSGY", "ALARK", "ALBRK", "ALCAR", "ALCTL", "ALFAS", "ALGYO", "ALKA", "ALKIM", 
    "ALMAD", "ALTNY", "ALVES", "ANELE", "ANGEN", "ANHYT", "ANSGR", "ARASE", "ARCLK", "ARDYZ", 
    "ARENA", "ARSAN", "ARTMS", "ARZUM", "ASELS", "ASGYO", "ASTOR", "ASUZU", "ATAGY", "ATAKP", 
    "ATATP", "ATEKS", "ATLAS", "ATSYH", "AVGYO", "AVHOL", "AVOD", "AVPGY", "AYCES", "AYDEM", 
    "AYEN", "AYES", "AYGAZ", "AZTEK", "BAGFS", "BAKAB", "BALAT", "BANVT", "BARMA", "BASGZ", 
    "BAYRK", "BEAYO", "BEYAZ", "BFREN", "BIENY", "BIGCH", "BIMAS", "BINHO", "BIOEN", "BIZIM", 
    "BJKAS", "BLCYT", "BMSCH", "BMSTL", "BNTAS", "BOBET", "BORLS", "BORSK", "BOSSA", "BRISA", 
    "BRKO", "BRKSN", "BRKVY", "BRLSM", "BRMEN", "BRSAN", "BRYAT", "BSOKE", "BTCIM", "BUCIM", 
    "BURCE", "BURVA", "BVSAN", "BYDNR", "CANTE", "CASA", "CATES", "CCOLA", "CELHA", "CEMAS", 
    "CEMTS", "CEOEM", "CIMSA", "CLEBI", "CMBTN", "CMENT", "CONSE", "COSMO", "CRDFA", "CRFSA", 
    "CUSAN", "CVKMD", "CWENE", "DAGHL", "DAGI", "DAPGM", "DARDL", "DATA", "DEFVA", "DERHL", 
    "DERIM", "DESA", "DESPC", "DEVA", "DGNMO", "DIRIT", "DITAS", "DMRGD", "DMSAS", "DOAS", 
    "DOBUR", "DOCO", "DOFER", "DOGUB", "DOHOL", "DOKTA", "DURDO", "DYOBY", "DZGYO", "EBEBK", 
    "ECILC", "ECZYT", "EDATA", "EDIP", "EGEEN", "EGEPO", "EGERT", "EGPRO", "EGSER", "EKGYO", 
    "EKIZ", "EKOS", "EKSUN", "ELITE", "EMKEL", "ENERY", "ENJSA", "ENKAI", "ENTRA", "EPLAS", 
    "ERBOS", "ERCAN", "EREGL", "ERSU", "ESCAR", "ESCOM", "ESEN", "ETILR", "ETYAT", "EUHOL", 
    "EUREN", "EUYO", "EYGYO", "FADE", "FENER", "FLAP", "FMIZP", "FONET", "FORMT", "FORTE", 
    "FRIGO", "FROTO", "FSYGM", "FZLGY", "GARAN", "GARFA", "GENTS", "GEREL", "GESAN", "GIPTA", 
    "GLBMD", "GLCVY", "GLRYH", "GLYHO", "GMTAS", "GOKNR", "GOLTS", "GOODY", "GOZDE", "GRNYO", 
    "GRSEL", "GRTRK", "GSDDE", "GSDHO", "GSRAY", "GUBRF", "GWIND", "GZNMI", "HALKB", "HATEK", 
    "HATSN", "HDFGS", "HEDEF", "HEKTS", "HKTM", "HLGYO", "HRZNO", "HSCSM", "HUBVC", "HUNER", 
    "HURGZ", "ICBCT", "ICUGS", "IDGYO", "IEYHO", "IHAAS", "IHEVA", "IHGZT", "IHLAS", "IHLGM", 
    "IHYAY", "IMASM", "INDES", "INFO", "INGRM", "INTEM", "INVEO", "INVES", "IPEKE", "ISATR", 
    "ISBIR", "ISBTR", "ISCTR", "ISDMR", "ISFIN", "ISGSY", "ISGYO", "ISKPL", "ISKUR", "ISMEN", 
    "ISSEN", "ISYAT", "ITTFH", "IZENR", "IZFAS", "IZINV", "IZMDC", "JANTS", "KALES", "KALEK", 
    "KARSN", "KARTN", "KARYE", "KATMR", "KCAER", "KCHOL", "KENT", "KERVN", "KERVT", "KFEIN", 
    "KGYO", "KIMMR", "KLGYO", "KLKIM", "KLMSN", "KLNMA", "KLRHO", "KLSYN", "KMPUR", "KNFRT", 
    "KOCMT", "KONKA", "KONTR", "KONYA", "KOPOL", "KORDS", "KOZAA", "KOZAL", "KRDMA", "KRDMB", 
    "KRDMD", "KRGYO", "KRONT", "KRPLS", "KRSTL", "KRTEK", "KRVGD", "KSTUR", "KTLEV", "KTSKR", 
    "KUTPO", "KUVVA", "KUYAS", "KZBGY", "KZGYO", "LIDER", "LIDFA", "LINK", "LKMNH", "LOGO", 
    "LRSHO", "LUKSK", "MAALT", "MACKO", "MACRO", "MAGEN", "MAKIM", "MAKTK", "MANAS", "MARKA", 
    "MARTI", "MAVI", "MAXOT", "MEDTR", "MEGAP", "MEKAG", "MEPET", "MERCN", "MERIT", "MERKO", 
    "METRO", "METUR", "MGROS", "MHRGY", "MIATK", "MIPAZ", "MMCAS", "MNDRS", "MNDTR", "MOBTL", 
    "MOGAN", "MPARK", "MRGYO", "MRSHL", "MSGYO", "MTRKS", "MTRYO", "MUHAL", "MUREN", "NASHQ", 
    "NATEN", "NETAS", "NIBAS", "NTGAZ", "NTHOL", "NUGYO", "NUHCM", "OBASE", "OBAMS", "ODAS", 
    "ODINE", "OFSYM", "ONCSM", "ORCAY", "ORGE", "ORMA", "OSMEN", "OSTIM", "OTKAR", "OTTO", 
    "OYAKC", "OYAYO", "OYLUM", "OYYAT", "OZGYO", "OZKGY", "OZRDN", "OZSUB", "PAGYO", "PAMEL", 
    "PAPIL", "PARSN", "PASEU", "PATEK", "PCILT", "PEGYO", "PEKGY", "PENGD", "PENTA", "PETKM", 
    "PETUN", "PGSUS", "PINSU", "PKART", "PKENT", "PLTUR", "PNLSN", "PNSUT", "POLHO", "POLTK", 
    "PRDGS", "PRKAB", "PRKME", "PRZMA", "PSDTC", "PSGYO", "QNBFL", "QUAGR", "RALYH", "RAYSG", 
    "REEDR", "RNPOL", "RODRG", "ROYAL", "RTALB", "RUBNS", "RYGYO", "RYSAS", "SAHOL", "SAMAT", 
    "SANEL", "SANFM", "SANKO", "SARKY", "SASA", "SAYAS", "SDTTR", "SEGYO", "SEKFK", "SEKUR", 
    "SELEC", "SELGD", "SELVA", "SEYKM", "SILVR", "SISE", "SKBNK", "SKTAS", "SMART", "SMRTG", 
    "SNGYO", "SNICA", "SNKRN", "SNPAM", "SNTCD", "SOKE", "SOKM", "SONME", "SRVGY", "SUMAS", 
    "SUNTK", "SURGY", "SUWEN", "TABGD", "TARKM", "TATEN", "TATGD", "TAVHL", "TBORG", "TCELL", 
    "TDGYO", "TEKTU", "TERA", "TETMT", "TEZOL", "TGSAS", "THYAO", "TKFEN", "TKNSA", "TLMAN", 
    "TMPOL", "TMSN", "TOASO", "TRCAS", "TRGYO", "TRILC", "TSGYO", "TSKB", "TSPOR", "TTKOM", 
    "TTRAK", "TUCLK", "TUKAS", "TUPRS", "TUREX", "TURGG", "TURSG", "UFUK", "ULAS", "ULKER", 
    "ULUFA", "ULUSE", "ULUUN", "UMPAS", "UNLU", "USAK", "UZERB", "VAKBN", "VAKFN", "VAKKO", 
    "VANGD", "VBTYZ", "VERTU", "VERUS", "VESBE", "VESTL", "VKFYO", "VKGYO", "VKING", "VRGYO", 
    "YAPRK", "YATAS", "YAYLA", "YBTAS", "YEOTK", "YESIL", "YGGYO", "YGYO", "YKBNK", "YKSLN", 
    "YONGA", "YUNSA", "YYAPI", "ZEDUR", "ZOREN", "ZRGYO"
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
    except Exception:
        pass

def send_telegram_voice(text_to_speak):
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN" or not TELEGRAM_BOT_TOKEN:
        print(f"\n[SESLİ UYARI ÇALINIYOR]: {text_to_speak}\n")
        return
    try:
        tts = gTTS(text=text_to_speak, lang='tr')
        audio_filename = "uyari_sesi.ogg"
        tts.save(audio_filename)
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVoice"
        payload = {"chat_id": TELEGRAM_CHAT_ID}
        with open(audio_filename, "rb") as audio_file:
            files = {"voice": audio_file}
            requests.post(url, data=payload, files=files, timeout=15)
            
        if os.path.exists(audio_filename):
            os.remove(audio_filename)
    except Exception as e:
        print(f"Sesli mesaj gönderilirken hata oluştu: {e}")

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

# ============================================================
# UZUN VADE: DEFTER DEĞERİ DÜŞÜK & KAR EDENLERİ TARAMA
# ============================================================
def scan_long_term_stocks(symbol_list):
    send_telegram_msg("📊 <b>[UZUN VADE]</b> Defter değeri uygun ve kar eden şirketler taranıyor...")
    long_term_candidates = []
    
    # Süreci hızlandırmak için örnek bir alt küme veya liste kontrolü (yfinance performans amaçlı ilk 150 hisse taranır)
    for symbol in symbol_list[:150]:
        try:
            ticker = yf.Ticker(f"{symbol}.IS")
            info = ticker.info
            
            pb_ratio = info.get("priceToBook")
            net_income = info.get("netIncomeToCommon")
            
            # Kriter: Defter değeri (PD/DD) 0 ile 2.5 arasında VE net kar pozitif (zarar etmemiş)
            if pb_ratio and net_income:
                if 0.1 <= pb_ratio <= 2.5 and net_income > 0:
                    current_price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
                    long_term_candidates.append({
                        "symbol": symbol,
                        "pb": pb_ratio,
                        "price": current_price
                    })
        except Exception:
            continue
            
    if long_term_candidates:
        # PD/DD oranına göre en ucuzdan en pahalıya sırala
        long_term_candidates.sort(key=lambda x: x["pb"])
        msg = "💎 <b>UZUN VADELİ YATIRIM ADAYLARI (Düşük PD/DD & Karlı)</b>\n\n"
        for item in long_term_candidates[:10]: # En iyi 10 tanesini göster
            msg += f"📌 <b>#{item['symbol']}</b> | Fiyat: {item['price']} TL | <b>PD/DD:</b> {item['pb']:.2f}\n"
        send_telegram_msg(msg)
    else:
        send_telegram_msg("🛡️ <b>[UZUN VADE]:</b> Bu taramada kriterlere tam uyan hisse bulunamadı.")

# ============================================================
# TRADINGVIEW TOPLU TARAMA
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
                    results[clean_sym] = {
                        "close": ind.get("close"),
                        "change": ind.get("change"),
                        "rsi": ind.get("RSI"),
                        "volume": ind.get("volume", 0)
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
# ÖZEL SEANS TARAMASI KONTROLÜ (GÜNLÜK TAVAN / VUR-KAÇ)
# ============================================================
def scan_bist_stocks(symbol_list, scan_time):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Taraması Başlatıldı ({scan_time})...")
    
    tv_data_map = analyze_tv_stocks_bulk(symbol_list)
    top_gainers = []
    tavan_adaylari = []

    for symbol in symbol_list:
        data = tv_data_map.get(symbol)
        if not data or data["rsi"] is None or data["close"] is None:
            continue

        price = data["close"]
        rsi = data["rsi"]
        change = data["change"] or 0.0
        volume = data["volume"] or 0

        if change >= TOP_GAINER_LIMIT:
            top_gainers.append((symbol, change, price, volume))

        # 🚀 GÜNLÜK VUR-KAÇ / TAVAN ADAYI STRATEJİSİ (%5 - %8 + Az Lot Veya KAP)
        if 5.0 <= change <= 8.0:
            is_low_volume = (0 < volume < LOW_VOLUME_LIMIT)
            has_kap = symbol in ACTIVE_KAP_SIGNALS
            
            if is_low_volume or has_kap:
                rating = "⭐⭐⭐⭐"
                strategy_desc = ""
                
                if is_low_volume and has_kap:
                    kap_data = ACTIVE_KAP_SIGNALS[symbol]
                    rating = "⭐⭐⭐⭐⭐ (Mükemmel Kombinasyon)"
                    strategy_desc = f"Lotu Az + {kap_data['category']} Haberi."
                elif has_kap:
                    kap_data = ACTIVE_KAP_SIGNALS[symbol]
                    rating = f"{kap_data['stars']} (Haber Katalizörü)"
                    strategy_desc = f"{kap_data['category']} haberi destekli."
                elif is_low_volume:
                    rating = "⭐⭐⭐⭐ (Sığ Tahta / Az Lot İvmesi)"
                    strategy_desc = "Az lot işlem görüyor. Kademeler hızlı kalkabilir."
                
                tavan_adaylari.append({
                    "symbol": symbol, "price": price, "change": change, 
                    "volume": volume, "rating": rating, "strategy": strategy_desc,
                    "has_kap": has_kap
                })

        # 🛡️ DİP AVCISI
        if rsi <= RSI_DIP_LIMIT:
            dip_stars = "⭐⭐⭐⭐⭐" if rsi <= 15 else "⭐⭐⭐⭐" if rsi <= 20 else "⭐⭐⭐"
            send_telegram_msg(
                f"🛡️ <b>[DİP AVCISI - {scan_time}]</b>\n\n"
                f"<b>Hisse Adı:</b> #{symbol}\n"
                f"<b>Derece:</b> {dip_stars}\n"
                f"<b>Fiyat:</b> {price:.2f} TL\n"
                f"<b>RSI (14):</b> {rsi:.1f}"
            )

    # 🚀 GÜNLÜK TAVAN ADAYLARINI ANINDA GÖNDER
    if tavan_adaylari:
        tavan_adaylari.sort(key=lambda x: x["change"], reverse=True)
        for aday in tavan_adaylari:
            msg = (
                f"🚨 <b>[GÜNLÜK TAVAN ADAYI - {scan_time}]</b> 🚨\n\n"
                f"<b>Hisse Adı:</b> #{aday['symbol']}\n"
                f"<b>Fiyat:</b> {aday['price']:.2f} TL (<b>%{aday['change']:+.2f}</b>)\n"
                f"<b>Hacim:</b> {aday['volume']:,.0f} Lot\n"
                f"<b>Derece:</b> {aday['rating']}\n"
                f"<b>Strateji:</b> {aday['strategy']}\n"
            )
            if aday['has_kap']:
                msg += f"🔗 <a href='{ACTIVE_KAP_SIGNALS[aday['symbol']]['link']}'>Habere Git</a>"
            send_telegram_msg(msg)

    # 📊 +%5 GÜN İÇİ YÜKSELENLER LİSTESİ
    if top_gainers:
        top_gainers.sort(key=lambda x: x[1], reverse=True)
        chunk_size = 30
        for i in range(0, len(top_gainers), chunk_size):
            chunk = top_gainers[i:i + chunk_size]
            gainer_msg = f"🌟 <b>[+%5 VE ÜZERİ YÜKSELENLER - {scan_time}]</b>\n\n"
            for sym, chg, prc, vol in chunk:
                gainer_msg += f"<b>#{sym: <6}</b> | +%{chg:.2f} | <b>Lot:</b> {vol:,.0f}\n"
            send_telegram_msg(gainer_msg)

# ============================================================
# ANA ÇALIŞMA DÖNGÜSÜ
# ============================================================
def main():
    now = datetime.now()
    current_time_str = now.strftime("%H:%M")
    
    send_telegram_msg(
        "🤖 <b>BİST ÇİFT STRATEJİ BOTU BAŞLATILDI</b>\n"
        "💎 <i>Uzun Vade (Düşük PD/DD & Karlı) + Günlük Tavan Adayları Aktif!</i>\n"
        "🚀 İlk açılış taraması ve uzun vade analizi yapılıyor..."
    )

    # 1. İLK AÇILIŞTA UZUN VADE VE ANLIK PİYASA TARAMASI
    try:
        check_kap_news()
        hedef_hisseler = get_all_bist_tickers()
        
        # Uzun vadeli ucuz ve karlı hisseleri ilk açılışta bul
        scan_long_term_stocks(hedef_hisseler)
        
        # Günlük tavan/teknik taramayı başlat
        scan_bist_stocks(hedef_hisseler, f"İLK AÇILIŞ ({current_time_str})")
        send_telegram_msg("✅ <b>Açılış taramaları tamamlandı!</b> Bot artık alarm saatlerini bekliyor.")
    except Exception as e:
        send_telegram_msg(f"❌ <b>İlk Taramada Hata:</b> {e}")

    # 2. STANDART ALARM SAATLERİNİ BEKLEME DÖNGÜSÜ
    while True:
        try:
            loop_now = datetime.now()
            loop_time = loop_now.strftime("%H:%M")
            loop_date = loop_now.strftime("%Y-%m-%d")

            check_kap_news()
            scan_key = f"{loop_date}_{loop_time}"

            if loop_time in TARGET_SCAN_TIMES and scan_key not in SCANNED_TIMES_TODAY:
                
                # 🎙️ 09:50 SESLİ UYARI
                if loop_time == "09:50":
                    send_telegram_msg("🚨 <b>DİKKAT: PİYASA AÇILDI!</b> 🚨\nTavan adayları taranıyor...")
                    send_telegram_voice("Piyasa açıldı.")
                    time.sleep(2)
                    
                hedef_hisseler = get_all_bist_tickers()
                
                # Gece 23:00'te hem uzun vade hem gece bülteni çalışsın
                if loop_time == "23:00":
                    scan_long_term_stocks(hedef_hisseler)
                    
                scan_bist_stocks(hedef_hisseler, loop_time)
                SCANNED_TIMES_TODAY.add(scan_key)
                
                if loop_time == "23:00":
                    ACTIVE_KAP_SIGNALS.clear()
                    PROCESSED_KAP_LINKS.clear()

            time.sleep(30)
        except KeyboardInterrupt:
            break
        except Exception:
            time.sleep(30)

if __name__ == "__main__":
    main()
