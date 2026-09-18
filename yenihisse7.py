#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BIST Dip + Hacim Avcısı Botu v2
Strateji:
- RSI dip (Günlük < 35 + Haftalık < 42)  → 2-3 günlük kâr potansiyeli için
- Stochastic hem dipte hem kesişim (K, D'yi yukarı kesiyor)
- Hacim ≥ 20 Milyon TL
- Gün içi mutlaka pozitif (%)
- RVOL ≥ 1.5
- KAP haberi varsa eklenir
- %5 üzeri yükselenler ayrı listelenir
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
# HEALTH CHECK (Render / UptimeRobot)
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
# KAP
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

            for key, (stars, category) in KAP_STAR_MAP.items():
                if key in content_lower:
                    PROCESSED_KAP_LINKS.add(entry.link)
                    for symbol in FULL_BIST_LIST:
                        if symbol in title or symbol in summary:
                            ACTIVE_KAP_SIGNALS[symbol] = {
                                "stars": stars, "category": category,
                                "title": title, "link": entry.link
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
    except Exception as e:
        print(f"[KAP API {symbol}] {e}")
    return "Aktif bildirim yok", False


# ============================================================
# ANALİZ (KESİN KURALLAR)
# ============================================================
def analyze_ticker(symbol):
    try:
        t = yf.Ticker(f"{symbol}.IS")
        df_d = t.history(period="6mo", interval="1d")
        df_w = t.history(period="1y", interval="1wk")

        if df_d is None or df_w is None or len(df_d) < 30 or len(df_w) < 14:
            return None

        # RSI
        rsi_d = safe_float(df_d.ta.rsi(length=14).iloc[-1])
        rsi_w = safe_float(df_w.ta.rsi(length=14).iloc[-1])
        if np.isnan(rsi_d) or np.isnan(rsi_w):
            return None

        # Stochastic
        stoch = df_d.ta.stoch(k=14, d=3, smooth_k=3)
        if stoch is None or stoch.empty:
            return None

        k_col = next((c for c in stoch.columns if "STOCHk" in c.upper()), None)
        d_col = next((c for c in stoch.columns if "STOCHd" in c.upper()), None)
        if not k_col or not d_col:
            return None

        k_now = safe_float(stoch[k_col].iloc[-1])
        d_now = safe_float(stoch[d_col].iloc[-1])
        k_prev = safe_float(stoch[k_col].iloc[-2])
        d_prev = safe_float(stoch[d_col].iloc[-2])

        if any(np.isnan(x) for x in [k_now, d_now, k_prev, d_prev]):
            return None

        # Stochastic: hem dipte hem kesişim (K, D'yi yukarı kesiyor)
        stoch_dip = k_now < 25 and d_now < 30
        stoch_cross = (k_prev <= d_prev) and (k_now > d_now)

        if not (stoch_dip and stoch_cross):
            return None

        # Fiyat
        close = safe_float(df_d["Close"].iloc[-1])
        prev = safe_float(df_d["Close"].iloc[-2])
        if np.isnan(close) or np.isnan(prev) or prev <= 0:
            return None

        change_pct = ((close - prev) / prev) * 100
        if change_pct <= 0:                    # Gün içi mutlaka pozitif
            return None

        # Hacim
        vol = safe_float(df_d["Volume"].iloc[-1], 0)
        hacim_tl = vol * close
        if hacim_tl < 20_000_000:              # 20 Milyon TL altı elenir
            return None

        avg10 = safe_float(df_d["Volume"].iloc[-11:-1].mean(), 0)
        rvol = (vol / avg10) if avg10 > 0 else 0
        if rvol < 1.5:
            return None

        # RSI dip şartı (2-3 günlük kâr potansiyeli için)
        if not (rsi_d < 35 and rsi_w < 42):
            return None

        # ATR & SL/TP
        atr = safe_float(df_d.ta.atr(length=14).iloc[-1], close * 0.02)
        sl = max(0.01, close - 1.5 * atr)
        tp = close + 3.0 * atr

        # Tahta
        avg20 = safe_float(df_d["Volume"].iloc[-20:].mean(), 0)
        tahta = "⚠️ Sığ Tahta" if avg20 < 500_000 else "🟢 Likit Tahta"

        # KAP
        kap_ozeti, kap_onemli = get_kap_news_api(symbol)

        # Yıldız
        yildiz = 3
        if rvol >= 2.5: yildiz += 1
        if rsi_d < 25: yildiz += 1
        if kap_onemli: yildiz += 1
        yildizlar = "⭐" * min(yildiz, 5)

        return {
            "symbol": symbol,
            "fiyat": round(close, 2),
            "change_pct": round(change_pct, 2),
            "rsi_d": round(rsi_d, 1),
            "stoch_k": round(k_now, 1),
            "rvol": round(rvol, 2),
            "hacim_tl": format_compact_volume(hacim_tl),
            "tahta": tahta,
            "sl": round(sl, 2),
            "tp": round(tp, 2),
            "kap_ozeti": kap_ozeti,
            "kap_onemli": kap_onemli,
            "yildizlar": yildizlar,
            "yukari5": change_pct >= 5.0
        }

    except Exception as e:
        print(f"[Analiz {symbol}] {type(e).__name__}: {e}")
        return None


# ============================================================
# TARAMA + İKİ LİSTE
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

    # İki ayrı liste
    dip_listesi = [x for x in sonuclar if not x["yukari5"]]
    yukari5_listesi = [x for x in sonuclar if x["yukari5"]]

    # Sıralama
    dip_listesi.sort(key=lambda x: (x["kap_onemli"], x["rvol"]), reverse=True)
    yukari5_listesi.sort(key=lambda x: x["change_pct"], reverse=True)

    baslik = "🌙 GECE BÜLTENİ" if scan_time == "23:00" else "GÜN İÇİ TARAMA"

    # ---------- 1) %5 ÜZERİ LİSTESİ ----------
    if yukari5_listesi:
        msg = f"🚀 <b>[%5+ YÜKSELENLER | {baslik}]</b>\n"
        msg += f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        msg += f"🔢 Adet: <b>{len(yukari5_listesi)}</b>\n\n"

        for it in yukari5_listesi:
            kap_emoji = "🚨" if it["kap_onemli"] else ""
            msg += (
                f"🔹 <b>#{it['symbol']}</b> | <b>{it['fiyat']} TL</b> "
                f"<b>(%+{it['change_pct']})</b> {kap_emoji} {it['yildizlar']}\n"
                f"├ RSI: {it['rsi_d']} | Stoch: {it['stoch_k']} | RVOL: {it['rvol']}x\n"
                f"├ Hacim: {it['hacim_tl']} TL | {it['tahta']}\n"
                f"├ 🛑 SL: {it['sl']} | 🎯 TP: {it['tp']}\n"
                f"└ KAP: <i>{it['kap_ozeti']}</i>\n\n"
            )
            if len(msg) > 3800:
                send_telegram_msg(msg)
                msg = ""
                time.sleep(1)
        if msg.strip():
            send_telegram_msg(msg)

    # ---------- 2) DİP + STOCH KESİŞİM LİSTESİ ----------
    if dip_listesi:
        msg = f"🎯 <b>[DİP + STOCH KESİŞİM | {baslik}]</b>\n"
        msg += f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        msg += f"🔢 Adet: <b>{len(dip_listesi)}</b>\n\n"

        for it in dip_listesi:
            kap_emoji = "🚨" if it["kap_onemli"] else ""
            msg += (
                f"🔹 <b>#{it['symbol']}</b> | <b>{it['fiyat']} TL</b> "
                f"(%+{it['change_pct']}) {kap_emoji} {it['yildizlar']}\n"
                f"├ RSI: {it['rsi_d']} | Stoch K/D kesişim ✓ | RVOL: {it['rvol']}x\n"
                f"├ Hacim: {it['hacim_tl']} TL | {it['tahta']}\n"
                f"├ 🛑 SL: {it['sl']} | 🎯 TP: {it['tp']}\n"
                f"└ KAP: <i>{it['kap_ozeti']}</i>\n\n"
            )
            if len(msg) > 3800:
                send_telegram_msg(msg)
                msg = ""
                time.sleep(1)
        if msg.strip():
            send_telegram_msg(msg)

    # Özet
    send_telegram_msg(
        f"📊 <b>Tarama Özeti ({scan_time})</b>\n"
        f"• Toplam sinyal: {len(sonuclar)}\n"
        f"• %5 üzeri: {len(yukari5_listesi)}\n"
        f"• Dip + Stoch kesişim: {len(dip_listesi)}"
    )


# ============================================================
# ANA DÖNGÜ
# ============================================================
def main():
    send_telegram_msg(
        "🤖 <b>BİST BOTU v2 BAŞLATILDI</b>\n"
        "📌 Strateji:\n"
        "• RSI dip (Günlük < 35 + Haftalık < 42) → 2-3 günlük kâr potansiyeli\n"
        "• Stochastic dip + kesişim\n"
        "• Hacim ≥ 20M TL | RVOL ≥ 1.5\n"
        "• Gün içi mutlaka pozitif\n"
        "• %5 üzeri hisseler ayrı listelenir\n"
        "• KAP haberi varsa eklenir\n"
        "⏰ 09:50 | 10:10 | 17:45 | 23:00"
    )

    try:
        check_kap_news()
        hisseler = get_all_bist_tickers()
        scan_bist_stocks(hisseler[:10], "AÇILIŞ TESTİ")
        send_telegram_msg("✅ Açılış testi bitti. Saatler bekleniyor.")
    except Exception as e:
        send_telegram_msg(f"❌ Açılış hatası: {e}")

    while True:
        try:
            now = datetime.now()
            t = now.strftime("%H:%M")
            d = now.strftime("%Y-%m-%d")
            key = f"{d}_{t}"

            check_kap_news()

            if t in TARGET_SCAN_TIMES and key not in SCANNED_TIMES_TODAY:
                hisseler = get_all_bist_tickers()
                scan_bist_stocks(hisseler, t)
                SCANNED_TIMES_TODAY.add(key)

                if t == "23:00":
                    ACTIVE_KAP_SIGNALS.clear()
                    PROCESSED_KAP_LINKS.clear()
                    SCANNED_TIMES_TODAY.clear()

            time.sleep(30)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[Döngü] {e}")
            time.sleep(30)


if __name__ == "__main__":
    main()
