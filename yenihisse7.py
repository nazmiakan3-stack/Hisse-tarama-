#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer

# ============================================================
# KÜTÜPHANE KONTROLÜ
# ============================================================
try:
    import requests
    import feedparser
    import yfinance as yf
    import pandas as pd
    import pandas_ta as ta
except ModuleNotFoundError as e:
    print(f"\n❌ EKSİK KÜTÜPHANE TESPİT EDİLDİ: {e}")
    print("👉 Lütfen terminale şu komutu yazarak gerekli paketleri yükleyin:")
    print("pip install requests feedparser yfinance pandas pandas-ta\n")
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
# KAP İSTİHBARAT MODÜLÜ (ANLIK RSS BİLDİRİMLERİ İÇİN)
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
# YENİ STRATEJİ: DİP, HACİM PATLAMASI VE EMA9 TREND KIRILIMI
# ============================================================
def get_kap_news_api(symbol):
    """Tarama raporu için hisseye özel son KAP verisini çeker."""
    onemli_kategoriler = ["Yeni İş İlişkisi", "İhale", "Finansal Rapor", "Bilanço", "Kar Payı", "Sermaye Artırımı", "Pay Alım", "Birleşme"]
    try:
        url = f"https://www.kap.org.tr/tr/api/disclosures?code={symbol}"
        response = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                son_haber = data[0]
                baslik = son_haber.get("title", "Özel Durum Açıklaması")
                ozet = son_haber.get("summary", "") or baslik
                
                full_text = f"{baslik} {ozet}".lower()
                is_important = any(kat.lower() in full_text for kat in onemli_kategoriler)
                return f"{baslik}: {ozet[:50]}...", is_important
    except Exception:
        pass
    return "Aktif bildirim yok", False

def analyze_ticker(symbol):
    """Pandas-TA ve YFinance kullanarak gelişmiş strateji analizi yapar."""
    try:
        ticker_obj = yf.Ticker(f"{symbol}.IS")
        df_daily = ticker_obj.history(period="6m", interval="1d")
        df_weekly = ticker_obj.history(period="1y", interval="1wk")

        if len(df_daily) < 30 or len(df_weekly) < 14:
            return None

        rsi_daily = df_daily.ta.rsi(length=14).iloc[-1]
        rsi_weekly = df_weekly.ta.rsi(length=14).iloc[-1]
        
        stoch = df_daily.ta.stoch(k=14, d=3, smooth_k=3)
        stoch_k = stoch['STOCHk_14_3_3'].iloc[-1]
        stoch_d = stoch['STOCHd_14_3_3'].iloc[-1]
        stoch_alimda = (stoch_k < 20) or (stoch_k > stoch_d and stoch_k < 35)

        last_close = df_daily['Close'].iloc[-1]
        prev_close = df_daily['Close'].iloc[-2]
        change_pct = ((last_close - prev_close) / prev_close) * 100
        
        last_volume = df_daily['Volume'].iloc[-1]
        hacim_tl = last_volume * last_close

        avg_vol_10 = df_daily['Volume'].iloc[-11:-1].mean()
        rvol = last_volume / avg_vol_10 if avg_vol_10 > 0 else 0

        ema9 = df_daily.ta.ema(length=9)
        trend_kirilimi = (last_close > ema9.iloc[-1]) and (prev_close <= ema9.iloc[-2])

        atr = df_daily.ta.atr(length=14).iloc[-1]
        stop_loss = max(0, last_close - (1.5 * atr))
        take_profit = last_close + (3.0 * atr)

        # Sığ Tahta Uyarısı (20 günlük ortalama hacim lotu < 500K ise)
        tahta_durumu = "⚠️ Sığ Tahta" if df_daily['Volume'].iloc[-20:].mean() < 500_000 else "🟢 Likit Tahta"

        # Strateji Onay Şartları
        teknik_onay = (
            rsi_daily < 30 and
            rsi_weekly < 30 and
            stoch_alimda and
            hacim_tl >= 10_000_000 and  # Min 10M TL hacim (Render için esnetildi)
            rvol >= 1.5 and
            change_pct > 0
        )

        if teknik_onay:
            kap_ozeti, kap_onemli = get_kap_news_api(symbol)
            
            yildiz_sayisi = 3 
            if rvol >= 2.5: yildiz_sayisi += 1 
            if trend_kirilimi: yildiz_sayisi += 1 
            yildizlar = "⭐" * min(yildiz_sayisi, 5)

            return {
                'symbol': symbol,
                'fiyat': round(last_close, 2),
                'change_pct': round(change_pct, 2),
                'rsi_d': round(rsi_daily, 1),
                'stoch_k': round(stoch_k, 1),
                'rvol': round(rvol, 2),
                'hacim_tl': format_compact_volume(hacim_tl),
                'tahta_durumu': tahta_durumu,
                'sl': round(stop_loss, 2),
                'tp': round(take_profit, 2),
                'kap_ozeti': kap_ozeti,
                'kap_onemli': kap_onemli,
                'trend_kirilimi': trend_kirilimi,
                'yildizlar': yildizlar
            }
    except Exception:
        pass
    return None

# ============================================================
# ÖZEL SEANS TARAMASI KONTROLÜ
# ============================================================
def scan_bist_stocks(symbol_list, scan_time):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Yeni Strateji Taraması Başlatıldı ({scan_time})...")
    
    eslesenler = []
    
    # ThreadPool ile hızlı yfinance taraması (Render sunucusunu yormamak için max_workers=10)
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(analyze_ticker, symbol_list)
        for res in results:
            if res:
                eslesenler.append(res)

    if eslesenler:
        # Hisseleri Sıralama: Önce KAP önemi (True olanlar üstte), sonra Göreceli Hacim
        eslesenler.sort(key=lambda x: (x['kap_onemli'], x['rvol']), reverse=True)
        
        baslik_ek = "🌙 GECE BÜLTENİ" if scan_time == "23:00" else "GÜN İÇİ TARAMASI"
        mesaj = f"🎯 <b>[DİP + HACİM PATLAMASI AVCISI | {baslik_ek}]</b>\n"
        mesaj += f"📅 <i>{datetime.now().strftime('%d.%m.%Y - %H:%M')}</i>\n\n"
        
        for item in eslesenler:
            uyari_simgesi = "🚨" if item['kap_onemli'] else ""
            
            if item['trend_kirilimi']:
                durum_etiketi = f"🚀 <b>Durum:</b> DÜŞEN KIRILIMI ONAYLANDI {item['yildizlar']}"
            else:
                durum_etiketi = f"📊 <b>Durum:</b> Dipte Güç Topluyor {item['yildizlar']}"
            
            hisse_str = (
                f"🔹 <b>#{item['symbol']}</b> | <b>{item['fiyat']} TL</b> (%+{item['change_pct']}) {uyari_simgesi}\n"
                f"├ {durum_etiketi}\n"
                f"├ <b>Göreceli Hacim:</b> {item['rvol']}x | <b>Hacim:</b> {item['hacim_tl']} TL\n"
                f"├ <b>RSI:</b> {item['rsi_d']} | <b>Stoch:</b> {item['stoch_k']} | {item['tahta_durumu']}\n"
                f"├ 🛑 <b>SL:</b> {item['sl']} TL | 🎯 <b>TP:</b> {item['tp']} TL\n"
                f"└ 📢 <b>KAP:</b> <i>{item['kap_ozeti']}</i>\n\n"
            )
            
            if len(mesaj) + len(hisse_str) > 4000:
                send_telegram_msg(mesaj)
                mesaj = ""
                time.sleep(1)
                
            mesaj += hisse_str
            
        if mesaj:
            send_telegram_msg(mesaj)
    else:
        # Eğer stratejiye uyan hisse yoksa bilgi verilir
        send_telegram_msg(f"ℹ️ <b>{scan_time} Taraması:</b> Strateji kriterlerimize (Dip + Yüksek Hacim + Kırılım) uyan hisse bulunamadı.")

# ============================================================
# ANA ÇALIŞMA DÖNGÜSÜ
# ============================================================
def main():
    now = datetime.now()
    current_time_str = now.strftime("%H:%M")
    
    send_telegram_msg(
        "🤖 <b>BİST BOTU (YENİ STRATEJİ) BAŞLATILDI</b>\n"
        "⏰ Gün İçi: <b>09:50, 10:10, 17:45</b> | Gece: <b>23:00</b>\n"
        "🚀 <i>Sistem aktif, GitHub/Render bağlantısı devrede...</i>"
    )

    # İlk açılış testi (Sadece ilk 10 hisseyi test et ki Render açılışta timeout yemesin)
    try:
        check_kap_news()
        hedef_hisseler = get_all_bist_tickers()
        test_listesi = hedef_hisseler[:10] 
        scan_bist_stocks(test_listesi, f"İLK AÇILIŞ TESTİ ({current_time_str})")
        send_telegram_msg("✅ <b>Açılış testi tamamlandı!</b> Alarm saatleri bekleniyor.")
    except Exception as e:
        send_telegram_msg(f"❌ <b>İlk Taramada Hata:</b> {e}")

    # Zamanlayıcı Döngüsü
    while True:
        try:
            loop_now = datetime.now()
            loop_time = loop_now.strftime("%H:%M")
            loop_date = loop_now.strftime("%Y-%m-%d")

            # Arka planda anlık KAP haberlerini takip et (RSS üzerinden)
            check_kap_news()
            
            scan_key = f"{loop_date}_{loop_time}"

            # Eğer anki saat hedef saatlerden biriyse ve bugün henüz taranmadıysa:
            if loop_time in TARGET_SCAN_TIMES and scan_key not in SCANNED_TIMES_TODAY:
                hedef_hisseler = get_all_bist_tickers()
                scan_bist_stocks(hedef_hisseler, loop_time)
                SCANNED_TIMES_TODAY.add(scan_key)
                
                # Gece bülteni sonrasında günlük listeleri sıfırla
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
