#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BIST Dip + Hacim Avcısı Botu v2.4
Strateji:
- Günlük Tarih & Cache Kontrolü (Tekrar eden bildirimler engellendi)
- Göreceli Hacim (RVOL): Son 10 günün ortalamasının en az 1.5 katı
- 1. Liste: RSI dip + Haftalık RSI yukarı yönlü hareket (dipten dönüş) + Stochastic Kesişim
- 2. Liste: %5 ve Üzeri Yükselenler
- 3. Liste: Güçlü Hacim (Hacim > 20M TL & RVOL ≥ 1.5 & Artı Pozisyon)
- Yıldız Sistemi: Göreceli Hacim (RVOL) ve KAP haberlerine göre dinamik
- SL: 1.5x ATR | TP: 3x ATR (14 Günlük)
"""

import os
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer

try:
    import requests
    import feedparser
    import yfinance as yf
    import pandas as pd
    import pandas_ta as ta
    import numpy as np
except ModuleNotFoundError as e:
    print(f"\n❌ EKSİK KÜTÜPHANE: {e}")
    print("pip install requests feedparser yfinance pandas pandas-ta numpy\n")
    exit(1)

# ============================================================
# HEALTH CHECK (Render / VPS vb.)
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
# AYARLAR
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1734551753")

TARGET_SCAN_TIMES = ["09:50", "10:10", "17:45", "23:00"]

KAP_STAR_MAP = {
    "bedelsiz": ("⭐⭐⭐⭐⭐", "Yüksek Oranlı Bedelsiz / Sermaye Artırımı", 5),
    "yeni iş ilişkisi": ("⭐⭐⭐⭐⭐", "Yeni İş İlişkisi / Dev İhale", 5),
    "ortaklık": ("⭐⭐⭐⭐⭐", "Stratejik İş Ortaklığı / M&A", 5),
    "ihale": ("⭐⭐⭐⭐", "İhale Sözleşmesi / Dev Sipariş", 4),
    "pay alım": ("⭐⭐⭐⭐", "Şirket Pay Geri Alımı", 4),
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
PROCESSED_NEWS_TITLES = set()
LAST_NEWS_CHECK = 0
CURRENT_ACTIVE_DATE = datetime.now().strftime("%Y-%m-%d")

NEGATIVE_KEYWORDS = [
    "crash", "collapse", "recession", "crisis", "panic", "sell-off", "selloff",
    "market plunge", "stocks fall", "stocks drop", "sharp decline", "tumbling",
    "bear market", "correction", "volatility spike", "risk-off",
    "rate hike", "interest rate increase", "fed hikes", "tcmb faiz", "faiz artırımı",
    "hawkish", "tightening", "quantitative tightening",
    "war", "invasion", "missile", "attack", "escalation", "sanctions", "embargo",
    "savaş", "saldırı", "yaptırım", "gerilim",
    "crypto ban", "bitcoin ban", "sec charges", "exchange hack", "hacked",
    "stablecoin depeg", "ftx", "bankruptcy", "insolvency", "liquidation cascade",
    "kripto yasağı", "borsa hack",
    "inflation surge", "stagflation", "default", "debt ceiling", "bank failure",
    "bankacılık krizi", "enflasyon şoku", "temerrüt",
    "kur şoku", "döviz krizi", "sermaye kontrolü", "yeni vergi", "ek vergi",
    "bakan istifa", "erken seçim", "siyasi kriz",
]

NEWS_FEEDS = [
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.investing.com/rss/news_25.rss",
    "https://www.investing.com/rss/news_301.rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://www.reutersagency.com/feed/?taxonomy=best-topics&post_type=best",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
]

# ============================================================
# YARDIMCI
# ============================================================
def safe_float(value, default=np.nan):
    try:
        if value is None:
            return default
        val = float(value)
        if np.isnan(val) or np.isinf(val):
            return default
        return val
    except (TypeError, ValueError):
        return default

def send_telegram_msg(message):
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN" or not TELEGRAM_BOT_TOKEN:
        print(f"\n[TELEGRAM]:\n{message}\n")
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
        print(f"[Telegram Hata] {e}")

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
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json().get("d", [])
            fetched = {item.get("code") for item in data if item.get("code") and len(item.get("code")) <= 5}
            filtered = sorted(list(fetched - BIST_30_SET))
            if len(filtered) >= 300:
                return filtered
    except Exception as e:
        print(f"[Hisse Listesi] {e}")
    return sorted(list(set(FULL_BIST_LIST) - BIST_30_SET))

# ============================================================
# KAP & HABER MODÜLLERİ
# ============================================================
def check_kap_news():
    global PROCESSED_KAP_LINKS, ACTIVE_KAP_SIGNALS
    try:
        feed = feedparser.parse("https://www.kap.org.tr/tr/rss")
        for entry in feed.entries[:25]:
            if entry.link in PROCESSED_KAP_LINKS:
                continue
            title = getattr(entry, "title", "") or ""
            summary = getattr(entry, "summary", "") or ""
            content_lower = (title + " " + summary).lower()

            for key, (stars, category, score) in KAP_STAR_MAP.items():
                if key in content_lower:
                    PROCESSED_KAP_LINKS.add(entry.link)
                    for symbol in FULL_BIST_LIST:
                        if symbol in title or symbol in summary:
                            ACTIVE_KAP_SIGNALS[symbol] = {
                                "stars": stars, "category": category,
                                "title": title, "link": entry.link, "score": score
                            }
                    send_telegram_msg(
                        f"🔥 <b>[YÜKSEK HABER DEĞERİ]</b>\n"
                        f"<b>Etki:</b> {stars}\n"
                        f"<b>Başlık:</b> {title}\n"
                        f"<b>Link:</b> <a href='{entry.link}'>KAP Detayı</a>"
                    )
                    time.sleep(0.4)
                    break
    except Exception as e:
        print(f"[KAP RSS] {e}")

def get_kap_news_api(symbol):
    onemli = ["yeni iş ilişkisi", "ihale", "finansal rapor", "bilanço",
              "kar payı", "sermaye artırımı", "pay alım", "birleşme", "bedelsiz"]
    try:
        url = f"https://www.kap.org.tr/tr/api/disclosures?code={symbol}"
        r = requests.get(url, timeout=6, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data:
                haber = data[0]
                baslik = haber.get("title") or "Özel Durum"
                ozet = haber.get("summary") or baslik
                full = f"{baslik} {ozet}".lower()
                is_imp = any(k in full for k in onemli)
                return f"{baslik}: {ozet[:55]}...", is_imp
    except Exception:
        pass
    return "Aktif bildirim yok", False

def check_market_news():
    global PROCESSED_NEWS_TITLES, LAST_NEWS_CHECK
    now = time.time()
    if now - LAST_NEWS_CHECK < 55 * 60:
        return
    LAST_NEWS_CHECK = now

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Saatlik piyasa haber taraması...")
    negative_found = []

    for feed_url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:12]:
                title = getattr(entry, "title", "") or ""
                summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
                link = getattr(entry, "link", "") or ""

                title_key = title.strip().lower()[:120]
                if not title_key or title_key in PROCESSED_NEWS_TITLES:
                    continue

                if any(kw in (title + " " + summary).lower() for kw in NEGATIVE_KEYWORDS):
                    PROCESSED_NEWS_TITLES.add(title_key)
                    negative_found.append({"title": title, "summary": summary[:180] if summary else "", "link": link})
        except Exception:
            pass

    if len(PROCESSED_NEWS_TITLES) > 400:
        PROCESSED_NEWS_TITLES = set(list(PROCESSED_NEWS_TITLES)[-200:])

    if not negative_found:
        return

    for item in negative_found[:5]:
        msg = (f"🚨🚨 <b>ACİL PİYASA UYARISI</b> 🚨🚨\n━━━━━━━━━━━━━━━━━━━━\n"
               f"⚠️ <b>Hisse ve Kripto piyasalarını olumsuz etkileyebilecek haber tespit edildi!</b>\n\n"
               f"📰 <b>{item['title']}</b>\n")
        if item["link"]:
            msg += f"\n🔗 <a href='{item['link']}'>Haberi Oku</a>\n"
        msg += f"\n━━━━━━━━━━━━━━━━━━━━\n🔇 <i>Pozisyonlarınızı gözden geçirin. Risk yönetimi uygulayın.</i>\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        send_telegram_msg(msg)
        time.sleep(1.5)

    if len(negative_found) > 5:
        send_telegram_msg(f"⚠️ Bu saatte toplam <b>{len(negative_found)}</b> negatif haber tespit edildi. İlk 5 tanesi gönderildi.")

# ============================================================
# ANALİZ MODÜLÜ (GÜNCELLENDİ)
# ============================================================
def analyze_ticker(symbol):
    try:
        t = yf.Ticker(f"{symbol}.IS")
        df_d = t.history(period="6mo", interval="1d")
        df_w = t.history(period="1y", interval="1wk")

        if df_d is None or df_w is None or len(df_d) < 30 or len(df_w) < 10:
            return None

        close = safe_float(df_d["Close"].iloc[-1])
        prev = safe_float(df_d["Close"].iloc[-2])
        if np.isnan(close) or np.isnan(prev) or prev <= 0:
            return None

        # TEMEL ŞART: Gün içi mutlaka pozitif olmalı
        change_pct = ((close - prev) / prev) * 100
        if change_pct <= 0:
            return None 

        vol = safe_float(df_d["Volume"].iloc[-1], 0)
        hacim_tl = vol * close
        
        # GÖRECELİ HACİM (RVOL): Son 10 günlük ortalama hacme oranı (En az 1.5 katı olmalı)
        avg10 = safe_float(df_d["Volume"].iloc[-11:-1].mean(), 0)
        rvol = (vol / avg10) if avg10 > 0 else 0

        # ATR 14 Günlük ve TP/SL Hesaplaması (SL: 1.5x ATR, TP: 3x ATR)[span_2](start_span)[span_2](end_span)
        atr_series = df_d.ta.atr(length=14)
        if atr_series is None or atr_series.empty:
            atr = close * 0.02
        else:
            atr = safe_float(atr_series.iloc[-1], close * 0.02)
        
        sl = max(0.01, close - 1.5 * atr)
        tp = close + 3.0 * atr

        # İndikatör Hesaplamaları
        rsi_d_series = df_d.ta.rsi(length=14)
        rsi_w_series = df_w.ta.rsi(length=14)
        
        rsi_d = safe_float(rsi_d_series.iloc[-1]) if rsi_d_series is not None else 50
        
        rsi_w_now = safe_float(rsi_w_series.iloc[-1]) if rsi_w_series is not None else 50
        rsi_w_prev = safe_float(rsi_w_series.iloc[-2]) if rsi_w_series is not None else 50
        
        # Haftalık RSI dipten yukarı hareket ediyor mu? (Dipten toparlanma)
        is_weekly_rsi_recovering = rsi_w_now > rsi_w_prev

        stoch = df_d.ta.stoch(k=14, d=3, smooth_k=3)
        stoch_dip, stoch_cross, k_now = False, False, 50
        
        if stoch is not None and not stoch.empty and len(stoch) >= 2:
            k_col = next((c for c in stoch.columns if "STOCHk" in c.upper()), None)
            d_col = next((c for c in stoch.columns if "STOCHd" in c.upper()), None)
            if k_col and d_col:
                k_now = safe_float(stoch[k_col].iloc[-1])
                d_now = safe_float(stoch[d_col].iloc[-1])
                k_prev = safe_float(stoch[k_col].iloc[-2])
                d_prev = safe_float(stoch[d_col].iloc[-2])
                stoch_dip = (k_now < 30 and d_now < 35)
                stoch_cross = (k_prev <= d_prev) and (k_now > d_now)

        avg20 = safe_float(df_d["Volume"].iloc[-20:].mean(), 0)
        tahta = "⚠️ Sığ Tahta" if avg20 < 500_000 else "🟢 Likit Tahta"

        kap_ozeti, kap_onemli = get_kap_news_api(symbol)

        # ----------------------------------------------------
        # KATEGORİ BAYRAKLARI (RVOL ŞARTI: >= 1.5)
        # ----------------------------------------------------
        is_hacimli = (hacim_tl >= 20_000_000) and (rvol >= 1.5)
        is_yukari5 = (change_pct >= 5.0) and (rvol >= 1.5)
        is_dip_stoch = (rsi_d < 40 and is_weekly_rsi_recovering and rvol >= 1.5) and (stoch_dip or stoch_cross)

        if not (is_yukari5 or is_dip_stoch or is_hacimli):
            return None

        # YILDIZ SİSTEMİ (Göreceli Hacim [RVOL] ve KAP Haberlerine Göre)
        star_score = 1
        if rvol >= 1.5: star_score += 1
        if rvol >= 2.5: star_score += 1
        if rvol >= 4.0: star_score += 1
        if kap_onemli: star_score += 1
        
        # Aktif KAP sinyallerinden ekstra skor kontrolü
        if symbol in ACTIVE_KAP_SIGNALS:
            star_score += 1

        star_count = min(star_score, 5)
        yildizlar = "⭐" * star_count

        return {
            "symbol": symbol,
            "fiyat": round(close, 2),
            "change_pct": round(change_pct, 2),
            "rsi_d": round(rsi_d, 1),
            "rsi_w": round(rsi_w_now, 1),
            "stoch_k": round(k_now, 1),
            "rvol": round(rvol, 2),
            "hacim_tl": format_compact_volume(hacim_tl),
            "tahta": tahta,
            "sl": round(sl, 2),
            "tp": round(tp, 2),
            "kap_ozeti": kap_ozeti,
            "kap_onemli": kap_onemli,
            "yildizlar": yildizlar,
            "is_yukari5": is_yukari5,
            "is_dip_stoch": is_dip_stoch,
            "is_hacimli": is_hacimli
        }

    except Exception:
        return None

# ============================================================
# TARAMA + ÜÇ LİSTE KONTROLÜ
# ============================================================
def scan_bist_stocks(symbol_list, scan_time):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Tarama başladı → {scan_time}")

    sonuclar = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for res in ex.map(analyze_ticker, symbol_list):
            if res:
                sonuclar.append(res)

    if not sonuclar:
        send_telegram_msg(f"ℹ️ <b>{scan_time}</b>: Kriterlere uyan hisse bulunamadı.")
        return

    yukari5_listesi = [x for x in sonuclar if x["is_yukari5"]]
    dip_listesi = [x for x in sonuclar if x["is_dip_stoch"] and not x["is_yukari5"]]
    hacim_listesi = [x for x in sonuclar if x["is_hacimli"] and not x["is_yukari5"] and not x["is_dip_stoch"]]

    yukari5_listesi.sort(key=lambda x: x["change_pct"], reverse=True)
    dip_listesi.sort(key=lambda x: (x["kap_onemli"], x["rvol"]), reverse=True)
    hacim_listesi.sort(key=lambda x: x["rvol"], reverse=True)

    baslik = "🌙 GECE BÜLTENİ" if scan_time == "23:00" else "GÜN İÇİ TARAMA"

    # LİSTE 1: %5 ÜZERİ YÜKSELENLER
    if yukari5_listesi:
        msg = f"🚀 <b>[%5+ YÜKSELENLER | {baslik}]</b>\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n🔢 Adet: <b>{len(yukari5_listesi)}</b>\n\n"
        for it in yukari5_listesi:
            kap_emoji = "🚨" if it["kap_onemli"] else ""
            msg += (
                f"🔹 <b>#{it['symbol']}</b> | <b>{it['fiyat']} TL</b> <b>(%+{it['change_pct']})</b> {kap_emoji} {it['yildizlar']}\n"
                f"├ RVOL (10g): {it['rvol']}x | Hacim: {it['hacim_tl']} TL\n"
                f"├ 🛑 SL (-1.5x ATR): <code>{it['sl']} TL</code>\n"
                f"├ 🎯 TP (+3x ATR): <code>{it['tp']} TL</code>\n"
                f"└ KAP: <i>{it['kap_ozeti']}</i>\n\n"
            )
            if len(msg) > 3800:
                send_telegram_msg(msg)
                msg = ""
                time.sleep(1)
        if msg.strip(): send_telegram_msg(msg)

    # LİSTE 2: DİPTEN DÖNÜŞ
    if dip_listesi:
        msg = f"🎯 <b>[DİP DÖNÜŞÜ & KESİŞİM | {baslik}]</b>\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n🔢 Adet: <b>{len(dip_listesi)}</b>\n\n"
        for it in dip_listesi:
            kap_emoji = "🚨" if it["kap_onemli"] else ""
            msg += (
                f"🔹 <b>#{it['symbol']}</b> | <b>{it['fiyat']} TL</b> (%+{it['change_pct']}) {kap_emoji} {it['yildizlar']}\n"
                f"├ Günlük RSI: {it['rsi_d']} | Haftalık RSI Toparlanma ✓ | RVOL: {it['rvol']}x\n"
                f"├ 🛑 SL (-1.5x ATR): <code>{it['sl']} TL</code>\n"
                f"├ 🎯 TP (+3x ATR): <code>{it['tp']} TL</code>\n"
                f"└ KAP: <i>{it['kap_ozeti']}</i>\n\n"
            )
            if len(msg) > 3800:
                send_telegram_msg(msg)
                msg = ""
                time.sleep(1)
        if msg.strip(): send_telegram_msg(msg)

    # LİSTE 3: GÜÇLÜ HACİM AVCISI
    if hacim_listesi:
        msg = f"🌊 <b>[GÜÇLÜ HACİM (20M+ & RVOL 1.5+) | {baslik}]</b>\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n🔢 Adet: <b>{len(hacim_listesi)}</b>\n\n"
        for it in hacim_listesi:
            kap_emoji = "🚨" if it["kap_onemli"] else ""
            msg += (
                f"🔹 <b>#{it['symbol']}</b> | <b>{it['fiyat']} TL</b> (%+{it['change_pct']}) {kap_emoji} {it['yildizlar']}\n"
                f"├ RVOL: {it['rvol']}x | Hacim: {it['hacim_tl']} TL | {it['tahta']}\n"
                f"├ 🛑 SL (-1.5x ATR): <code>{it['sl']} TL</code>\n"
                f"├ 🎯 TP (+3x ATR): <code>{it['tp']} TL</code>\n"
                f"└ KAP: <i>{it['kap_ozeti']}</i>\n\n"
            )
            if len(msg) > 3800:
                send_telegram_msg(msg)
                msg = ""
                time.sleep(1)
        if msg.strip(): send_telegram_msg(msg)

    send_telegram_msg(
        f"📊 <b>Tarama Özeti ({scan_time})</b>\n"
        f"• Toplam sinyal: {len(sonuclar)}\n"
        f"• %5 üzeri: {len(yukari5_listesi)}\n"
        f"• Dip Dönüşü: {len(dip_listesi)}\n"
        f"• Güçlü Hacim: {len(hacim_listesi)}"
    )

# ============================================================
# ANA DÖNGÜ
# ============================================================
def main():
    send_telegram_msg(
        "🤖 <b>BİST BOTU v2.4 BAŞLATILDI</b>\n"
        "📌 Strateji:\n"
        "• Günlük Tarih & Cache Kontrolü Aktif\n"
        "• Göreceli Hacim (RVOL): Son 10 günün ortalamasının en az 1.5 katı\n"
        "• 1. Liste: Dip + Haftalık RSI Toparlanma + Stoch\n"
        "• 2. Liste: %5+ Yükselenler (RVOL >= 1.5)\n"
        "• 3. Liste: Hacim > 20M TL & RVOL ≥ 1.5\n"
        "• ⭐ Yıldızlar: Göreceli Hacim (RVOL) ve KAP'a göre verilir\n"
        "• 🛑 SL: -1.5x ATR[span_3](start_span)[span_3](end_span) | 🎯 TP: +3x ATR[span_4](start_span)[span_4](end_span)\n"
        "⏰ Tarama: 09:50 | 10:10 | 17:45 | 23:00"
    )

    try:
        check_kap_news()
        check_market_news()
        hisseler = get_all_bist_tickers()
        scan_bist_stocks(hisseler[:10], "AÇILIŞ TESTİ")
        send_telegram_msg("✅ Açılış testi bitti. Saatler bekleniyor.")
    except Exception as e:
        send_telegram_msg(f"❌ Açılış hatası: {e}")

    global CURRENT_ACTIVE_DATE, SCANNED_TIMES_TODAY, PROCESSED_NEWS_TITLES
    while True:
        try:
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            
            # GÜN DEĞİŞTİYSE CACHE VE TARAMA LİSTELERİNİ SIFIRLA
            if today_str != CURRENT_ACTIVE_DATE:
                CURRENT_ACTIVE_DATE = today_str
                SCANNED_TIMES_TODAY.clear()
                PROCESSED_NEWS_TITLES.clear()
                print(f"[{now.strftime('%H:%M:%S')}] Yeni güne geçildi. Önbellekler sıfırlandı.")

            t = now.strftime("%H:%M")
            key = f"{today_str}_{t}"

            check_kap_news()
            check_market_news()

            if t in TARGET_SCAN_TIMES and key not in SCANNED_TIMES_TODAY:
                hisseler = get_all_bist_tickers()
                scan_bist_stocks(hisseler, t)
                SCANNED_TIMES_TODAY.add(key)

                if t == "23:00":
                    ACTIVE_KAP_SIGNALS.clear()
                    PROCESSED_KAP_LINKS.clear()

            time.sleep(30)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[Döngü] {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
