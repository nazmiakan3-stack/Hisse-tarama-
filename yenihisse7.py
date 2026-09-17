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

TARGET_SCAN_TIMES = ["09:50", "10:10", "17:45", "23:00"]

MIN_VOLUME_LIMIT = 20_000_000   # Günlük Hacim > 20 Milyon TL/Lot
MIN_REL_VOLUME_LIMIT = 1.5      # Günlük Göreceli Hacim > 1.5x
WEEKLY_RSI_DIP_LIMIT = 35       # Haftalık RSI Dip Limiti

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

def format_compact_volume(v):
    try:
        v = float(v)
        if v >= 1_000_000:
            return f"{v/1_000_000:.1f}M"
        elif v >= 1_000:
            return f"{v/1_000:.0f}K"
        return str(int(v))
    except Exception:
        return "0"

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
# TRADINGVIEW TOPLU TARAMA (GÜNLÜK VE HAFTALIK)
# ============================================================
def analyze_tv_stocks_bulk(symbol_list):
    formatted_symbols = [f"BIST:{sym}" for sym in symbol_list]
    results = {}
    chunk_size = 20

    for i in range(0, len(formatted_symbols), chunk_size):
        chunk = formatted_symbols[i:i + chunk_size]
        try:
            # Günlük Veriler
            daily_analysis = get_multiple_analysis(screener="turkey", interval=Interval.INTERVAL_1_DAY, symbols=chunk)
            # Haftalık Veriler
            weekly_analysis = get_multiple_analysis(screener="turkey", interval=Interval.INTERVAL_1_WEEK, symbols=chunk)

            for key in chunk:
                clean_sym = key.replace("BIST:", "")
                d_data = daily_analysis.get(key)
                w_data = weekly_analysis.get(key)

                if d_data and hasattr(d_data, 'indicators') and w_data and hasattr(w_data, 'indicators'):
                    d_ind = d_data.indicators
                    w_ind = w_data.indicators

                    results[clean_sym] = {
                        # Günlük Değerler
                        "close": d_ind.get("close"),
                        "change": d_ind.get("change"),
                        "rsi_daily": d_ind.get("RSI"),
                        "volume": d_ind.get("volume", 0),
                        "volume_avg10": d_ind.get("average_volume_10d_calc", 0),
                        "atr_14": d_ind.get("ATR"),  # 14 Günlük ATR
                        
                        # Haftalık Değerler (Dip ve Stokastik Kesişimi)
                        "rsi_weekly": w_ind.get("RSI"),
                        "stoch_k_weekly": w_ind.get("Stoch.K"),
                        "stoch_d_weekly": w_ind.get("Stoch.D")
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
                    time.sleep(0.5)
                    break
    except Exception:
        pass

# ============================================================
# ÖZEL SEANS TARAMASI KONTROLÜ
# ============================================================
def scan_bist_stocks(symbol_list, scan_time):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Taraması Başlatıldı ({scan_time})...")
    
    tv_data_map = analyze_tv_stocks_bulk(symbol_list)
    top_gainers = []
    gece_bulteni_adaylari = []
    ozel_katalizor_adaylari = []

    for symbol in symbol_list:
        data = tv_data_map.get(symbol)
        if not data or data["close"] is None or data["rsi_weekly"] is None:
            continue

        price = data["close"]
        change = data["change"] or 0.0
        volume = data["volume"] or 0
        volume_avg10 = data["volume_avg10"] or 0
        rsi_w = data["rsi_weekly"]
        stoch_k_w = data["stoch_k_weekly"]
        stoch_d_w = data["stoch_d_weekly"]
        atr = data["atr_14"] or (price * 0.03) # ATR Yoksa varsayılan %3 tolerans

        # ATR BAZLI HESAPLAMALAR
        sl_price = price - (1.5 * atr)
        tp_price = price + (3.0 * atr)

        # ----------------------------------------------------
        # KATI STRATEJİ FİLTRELERİ
        # ----------------------------------------------------
        # 1. Günü Artı Kapatacak / Artıda Olacak
        if change <= 0:
            continue

        # 2. Günlük Hacim Mutlaka 20 Milyon Üstü Olacak
        if volume < MIN_VOLUME_LIMIT:
            continue

        # 3. Günlük Göreceli Hacim (10 Günlük Ort.) >= 1.5 Olacak
        rel_volume = (volume / volume_avg10) if volume_avg10 > 0 else 0
        if rel_volume < MIN_REL_VOLUME_LIMIT:
            continue

        # 4. Haftalık RSI Dip Bölgesinde (<= 35)
        if rsi_w > WEEKLY_RSI_DIP_LIMIT:
            continue

        # 5. Haftalık Stokastik Kesişimi (Stoch K > Stoch D -> Al Sinyali)
        is_stoch_crossed = (stoch_k_w is not None and stoch_d_w is not None and stoch_k_w > stoch_d_w)
        if not is_stoch_crossed:
            continue

        # ----------------------------------------------------
        # FİLTRELERİ GEÇEN HİSSELERE 5 YILDIZ PUANLAMA
        # ----------------------------------------------------
        rating = "⭐⭐⭐⭐⭐"
        strategy_desc = f"Haftalık Dip Dönüşü (RSI: {rsi_w:.1f} | RelVol: {rel_volume:.1f}x)"

        has_kap = symbol in ACTIVE_KAP_SIGNALS
        if has_kap:
            strategy_desc += f" + KAP: {ACTIVE_KAP_SIGNALS[symbol]['category']}"

        # Gece Bülteni için Toplama
        if scan_time == "23:00":
            gece_bulteni_adaylari.append({
                "symbol": symbol, "price": price, "change": change, 
                "volume": volume, "rel_vol": rel_volume, "rsi_w": rsi_w,
                "sl": sl_price, "tp": tp_price,
                "rating": rating, "strategy": strategy_desc
            })
        else:
            ozel_katalizor_adaylari.append({
                "symbol": symbol, "price": price, "change": change, 
                "volume": volume, "rel_vol": rel_volume, "rsi_w": rsi_w,
                "sl": sl_price, "tp": tp_price,
                "rating": rating, "strategy": strategy_desc,
                "link": ACTIVE_KAP_SIGNALS[symbol]['link'] if has_kap else None
            })

        if change >= 3.0 and scan_time != "23:00":
            top_gainers.append((symbol, change, price, volume, rel_volume, rsi_w, sl_price, tp_price))

    # 🌙 23:00 GECE BÜLTENİ
    if scan_time == "23:00":
        if gece_bulteni_adaylari:
            gece_bulteni_adaylari.sort(key=lambda x: x["change"], reverse=True)
            bulten_msg = "🌙 <b>GECE BÜLTENİ: YARININ TAVAN SERİSİ ADAYLARI (5 YILDIZ)</b>\n───────────────────\n\n"
            for aday in gece_bulteni_adaylari:
                vol_str = format_compact_volume(aday['volume'])
                bulten_msg += f"🚀 <b>#{aday['symbol']}</b> | <b>{aday['price']:.2f} TL</b> (<b>%{aday['change']:+.2f}</b>) {aday['rating']}\n"
                bulten_msg += f"├ <b>Hacim:</b> {vol_str} | <b>RelVol:</b> {aday['rel_vol']:.1f}x\n"
                bulten_msg += f"├ <b>🎯 TP (Kar):</b> <code>{aday['tp']:.2f} TL</code> (+3x ATR)\n"
                bulten_msg += f"├ <b>🛑 SL (Stop):</b> <code>{aday['sl']:.2f} TL</code> (-1.5x ATR)\n"
                bulten_msg += f"└ <b>Strateji:</b> {aday['strategy']}\n\n"
            bulten_msg += "📌 <i>Bol kazançlar dilerim. Yatırım tavsiyesi değildir.</i>"
            send_telegram_msg(bulten_msg)
        else:
            send_telegram_msg("🌙 <b>GECE BÜLTENİ:</b> Bugün tavan serisi kriterini (Haftalık Dip + Stoch Kesişimi + Güçlü Hacim) sağlayan hisse bulunamadı.")

    # 💎 ÖZEL KATALİZÖR AVCISI (GÜN İÇİ SEANS)
    if ozel_katalizor_adaylari and scan_time != "23:00":
        ozel_katalizor_adaylari.sort(key=lambda x: x["change"], reverse=True)
        chunk_size = 8
        for i in range(0, len(ozel_katalizor_adaylari), chunk_size):
            chunk = ozel_katalizor_adaylari[i:i + chunk_size]
            msg = f"💎 <b>[TAVAN SERİSİ / DİP DÖNÜŞ AVCISI - {scan_time}]</b>\n───────────────────\n\n"
            for aday in chunk:
                vol_str = format_compact_volume(aday['volume'])
                msg += f"🔹 <b>#{aday['symbol']}</b> | <b>{aday['price']:.2f} TL</b> (<b>%{aday['change']:+.2f}</b>)\n"
                msg += f"├ <b>Hacim:</b> {vol_str} | <b>RelVol:</b> {aday['rel_vol']:.1f}x\n"
                msg += f"├ <b>🎯 TP:</b> <code>{aday['tp']:.2f} TL</code> | <b>🛑 SL:</b> <code>{aday['sl']:.2f} TL</code>\n"
                msg += f"└ <b>Sinyal:</b> {aday['strategy']}\n"
                if aday['link']:
                    msg += f"   🔗 <a href='{aday['link']}'>KAP Haberine Git</a>\n"
                msg += "\n"
            send_telegram_msg(msg)
            time.sleep(1)

    # 📊 YÜKSELEN HACİMLİ HİSSELERE GENEL BAKIŞ
    if top_gainers and scan_time != "23:00":
        top_gainers.sort(key=lambda x: x[1], reverse=True)
        chunk_size = 25
        for i in range(0, len(top_gainers), chunk_size):
            chunk = top_gainers[i:i + chunk_size]
            gainer_msg = f"🌟 <b>[DİPTEN KALKAN HACİMLİLER - {scan_time}]</b>\n───────────────────\n\n"
            for sym, chg, prc, vol, rel_vol, rsi_w, sl, tp in chunk:
                vol_str = format_compact_volume(vol)
                gainer_msg += f"📈 <b>#{sym}</b> | <b>{prc:.2f} TL</b> (+%{chg:.2f})\n"
                gainer_msg += f"  └ 🎯 TP: <code>{tp:.2f}</code> | 🛑 SL: <code>{sl:.2f}</code> | Vol: <b>{vol_str}</b>\n"
            send_telegram_msg(gainer_msg)
            time.sleep(1)

# ============================================================
# ANA ÇALIŞMA DÖNGÜSÜ
# ============================================================
def main():
    now = datetime.now()
    current_time_str = now.strftime("%H:%M")
    
    send_telegram_msg(
        "🤖 <b>BİST BOTU BAŞLATILDI (ATR SEVİYELERİ EKLENDİ)</b>\n"
        "🎯 Filtreler:\n"
        " ├ 1. Günü Artı Kapatma\n"
        " ├ 2. Hacim > 20M TL\n"
        " ├ 3. Göreceli Hacim > 1.5x\n"
        " ├ 4. Haftalık RSI Dip (<=35)\n"
        " ├ 5. Haftalık Stokastik Kesişimi (K > D)\n"
        " └ 6. 🛑 SL: -1.5x ATR | 🎯 TP: +3x ATR\n"
        "⏰ Alarm Saatleri: <b>09:50, 10:10, 17:45, 23:00</b>\n"
        "🚀 <i>Anlık piyasa taranıyor... Lütfen bekleyin.</i>"
    )

    try:
        check_kap_news()
        hedef_hisseler = get_all_bist_tickers()
        scan_bist_stocks(hedef_hisseler, f"İLK AÇILIŞ ({current_time_str})")
        send_telegram_msg("✅ <b>Açılış taraması tamamlandı!</b> Bot sorunsuz çalışıyor. Alarm saatleri beklenecek.")
    except Exception as e:
        send_telegram_msg(f"❌ <b>İlk Taramada Hata:</b> {e}")

    while True:
        try:
            loop_now = datetime.now()
            loop_time = loop_now.strftime("%H:%M")
            loop_date = loop_now.strftime("%Y-%m-%d")

            check_kap_news()
            scan_key = f"{loop_date}_{loop_time}"

            if loop_time in TARGET_SCAN_TIMES and scan_key not in SCANNED_TIMES_TODAY:
                hedef_hisseler = get_all_bist_tickers()
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
