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

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("BISTBot")

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
    print(f"\n❌ EKSİK KÜTÜPHANE: {e}")
    print("👉 pip install requests feedparser yfinance pandas pandas-ta\n")
    exit(1)

# ============================================================
# SAĞLIK KONTROLÜ
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
    logger.info(f"Health-check sunucusu port {port} üzerinde başladı")
    server.serve_forever()

threading.Thread(target=start_health_check_server, daemon=True).start()

# ============================================================
# AYARLAR
# ============================================================
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

FULL_BIST_LIST = [
    "A1CAP", "AAVTUR", "ACSEL", "ADEL", "ADESE", "AEFES", "AFYON", "AGESA", "AGHOL",
    "AGROT", "AHGAZ", "AKCNS", "AKENR", "AKFGY", "AKFYE", "AKGRT", "AKMGY", "AKSA",
    "AKSEN", "AKSGY", "ALBRK", "ALCAR", "ALCTL", "ALFAS", "ALGYO", "ALKA", "ALKIM",
    "ALMAD", "ALTNY", "ALVES", "ANELE", "ANGEN", "ANHYT", "ANSGR", "ARASE", "ARCLK",
    "ARDYZ", "ARENA", "ARSAN", "ARTMS", "ARZUM", "ASGYO", "ASUZU", "ATAGY", "ATAKP",
    "ATATP", "ATEKS", "ATLAS", "ATSYH", "AVGYO", "AVHOL", "AVOD", "AVPGY", "AYCES",
    "AYDEM", "AYEN", "AYES", "AYGAZ", "AZTEK", "BAGFS", "BAKAB", "BALAT", "BANVT",
    "BARMA", "BASGZ", "BAYRK", "BEAYO", "BEYAZ", "BFREN", "BIENY", "BIGCH", "BINHO",
    "BIOEN", "BIZIM", "BJKAS", "BLCYT", "BMSCH", "BMSTL", "BNTAS", "BOBET", "BORLS",
    "BORSK", "BOSSA", "BRISA", "BRKO", "BRKSN", "BRKVY", "BRLSM", "BRMEN", "BRYAT",
    "BSOKE", "BTCIM", "BUCIM", "BURCE", "BURVA", "BVSAN", "BYDNR", "CANTE", "CASA",
    "CATES", "CCOLA", "CELHA", "CEMAS", "CEMTS", "CEOEM", "CIMSA", "CLEBI", "CMBTN",
    "CMENT", "CONSE", "COSMO", "CRDFA", "CRFSA", "CUSAN", "CVKMD", "CWENE", "DAGHL",
    "DAGI", "DAPGM", "DARDL", "DATA", "DEFVA", "DERHL", "DERIM", "DESA", "DESPC",
    "DEVA", "DGNMO", "DIRIT", "DITAS", "DMRGD", "DMSAS", "DOBUR", "DOCO", "DOFER",
    "DOGUB", "DOHOL", "DOKTA", "DURDO", "DYOBY", "DZGYO", "EBEBK", "ECILC", "ECZYT",
    "EDATA", "EDIP", "EGEEN", "EGEPO", "EGERT", "EGPRO", "EGSER", "EKIZ", "EKOS",
    "EKSUN", "ELITE", "EMKEL", "ENERY", "ENJSA", "ENTRA", "EPLAS", "ERBOS", "ERCAN",
    "ERSU", "ESCAR", "ESCOM", "ESEN", "ETILR", "ETYAT", "EUHOL", "EUREN", "EUYO",
    "EYGYO", "FADE", "FENER", "FLAP", "FMIZP", "FONET", "FORMT", "FORTE", "FRIGO",
    "FSYGM", "FZLGY", "GARFA", "GENTS", "GEREL", "GESAN", "GIPTA", "GLBMD", "GLCVY",
    "GLRYH", "GLYHO", "GMTAS", "GOKNR", "GOLTS", "GOODY", "GOZDE", "GRNYO", "GRSEL",
    "GRTRK", "GSDDE", "GSDHO", "GSRAY", "GWIND", "GZNMI", "HALKB", "HATEK", "HATSN",
    "HDFGS", "HEDEF", "HKTM", "HLGYO", "HRZNO", "HSCSM", "HUBVC", "HUNER", "HURGZ",
    "ICBCT", "ICUGS", "IDGYO", "IEYHO", "IHAAS", "IHEVA", "IHGZT", "IHLAS", "IHLGM",
    "IHYAY", "IMASM", "INDES", "INFO", "INGRM", "INTEM", "INVEO", "INVES", "IPEKE",
    "ISATR", "ISBIR", "ISBTR", "ISDMR", "ISFIN", "ISGSY", "ISGYO", "ISKPL", "ISKUR",
    "ISMEN", "ISSEN", "ISYAT", "ITTFH", "IZENR", "IZFAS", "IZINV", "IZMDC", "JANTS",
    "KALES", "KALEK", "KARSN", "KARTN", "KARYE", "KATMR", "KCAER", "KENT", "KERVN",
    "KERVT", "KFEIN", "KGYO", "KIMMR", "KLGYO", "KLKIM", "KLMSN", "KLNMA", "KLRHO",
    "KLSYN", "KMPUR", "KNFRT", "KOCMT", "KONKA", "KONYA", "KOPOL", "KORDS", "KOZAA",
    "KRDMA", "KRDMB", "KRGYO", "KRONT", "KRPLS", "KRSTL", "KRTEK", "KRVGD", "KSTUR",
    "KTLEV", "KTSKR", "KUTPO", "KUVVA", "KUYAS", "KZBGY", "KZGYO", "LIDER", "LIDFA",
    "LINK", "LKMNH", "LOGO", "LRSHO", "LUKSK", "MAALT", "MACKO", "MACRO", "MAGEN",
    "MAKIM", "MAKTK", "MANAS", "MARKA", "MARTI", "MAVI", "MAXOT", "MEDTR", "MEGAP",
    "MEKAG", "MEPET", "MERCN", "MERIT", "MERKO", "METRO", "METUR", "MGROS", "MHRGY",
    "MIATK", "MIPAZ", "MMCAS", "MNDRS", "MNDTR", "MOBTL", "MOGAN", "MPARK", "MRGYO",
    "MRSHL", "MSGYO", "MTRKS", "MTRYO", "MUHAL", "MUREN", "NASHQ", "NATEN", "NETAS",
    "NIBAS", "NTGAZ", "NTHOL", "NUGYO", "NUHCM", "OBASE", "OBAMS", "ODINE", "OFSYM",
    "ONCSM", "ORCAY", "ORGE", "ORMA", "OSMEN", "OSTIM", "OTKAR", "OTTO", "OYAYO",
    "OYLUM", "OYYAT", "OZGYO", "OZKGY", "OZRDN", "OZSUB", "PAGYO", "PAMEL", "PAPIL",
    "PARSN", "PASEU", "PATEK", "PCILT", "PEGYO", "PEKGY", "PENGD", "PENTA", "PETUN",
    "PINSU", "PKART", "PKENT", "PLTUR", "PNLSN", "PNSUT", "POLHO", "POLTK", "PRDGS",
    "PRKAB", "PRKME", "PRZMA", "PSDTC", "PSGYO", "QNBFL", "QUAGR", "RALYH", "RAYSG",
    "REEDR", "RNPOL", "RODRG", "ROYAL", "RTALB", "RUBNS", "RYGYO", "RYSAS", "SAMAT",
    "SANEL", "SANFM", "SANKO", "SARKY", "SAYAS", "SDTTR", "SEGYO", "SEKFK", "SEKUR",
    "SELEC", "SELGD", "SELVA", "SEYKM", "SILVR", "SKBNK", "SKTAS", "SMART", "SMRTG",
    "SNGYO", "SNICA", "SNKRN", "SNPAM", "SNTCD", "SOKE", "SOKM", "SONME", "SRVGY",
    "SUMAS", "SUNTK", "SURGY", "SUWEN", "TABGD", "TARKM", "TATEN", "TATGD", "TAVHL",
    "TBORG", "TDGYO", "TEKTU", "TERA", "TETMT", "TEZOL", "TGSAS", "TKFEN", "TKNSA",
    "TLMAN", "TMPOL", "TMSN", "TRCAS", "TRGYO", "TRILC", "TSGYO", "TSKB", "TSPOR",
    "TTKOM", "TTRAK", "TUCLK", "TUKAS", "TUREX", "TURGG", "TURSG", "UFUK", "ULAS",
    "ULKER", "ULUFA", "ULUSE", "ULUUN", "UMPAS", "UNLU", "USAK", "UZERB", "VAKBN",
    "VAKFN", "VAKKO", "VANGD", "VBTYZ", "VERTU", "VERUS", "VESBE", "VESTL", "VKFYO",
    "VKGYO", "VKING", "VRGYO", "YAPRK", "YATAS", "YAYLA", "YBTAS", "YEOTK", "YESIL",
    "YGGYO", "YGYO", "YKBNK", "YKSLN", "YONGA", "YUNSA", "YYAPI", "ZEDUR", "ZOREN",
    "ZRGYO"
]

PROCESSED_KAP_LINKS = set()
SCANNED_TIMES_TODAY = set()

# ============================================================
# YARDIMCI FONKSİYONLAR
# ============================================================
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
        if v >= 1_000_000:
            return f"{v/1_000_000:.1f}M"
        if v >= 1_000:
            return f"{v/1_000:.0f}K"
        return str(int(v))
    except Exception:
        return "0"

def get_all_bist_tickers():
    """Tüm BIST hisselerini al (BIST 30 DAHİL)"""
    try:
        url = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/HisseTeknikVeriler"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json().get("d", [])
            fetched = {
                item.get("code")
                for item in data
                if item.get("code") and len(item.get("code", "")) <= 5
            }
            filtered = sorted(list(fetched))
            if len(filtered) >= 300:
                logger.info(f"Canlı BIST listesi alındı: {len(filtered)} hisse")
                return filtered
    except Exception as e:
        logger.warning(f"Canlı liste alınamadı: {e}")

    logger.info("Yedek liste kullanılıyor (BIST 30 dahil)")
    return sorted(list(set(FULL_BIST_LIST) | BIST_30_SET))

# ============================================================
# KAP RSS
# ============================================================
def check_kap_news():
    global PROCESSED_KAP_LINKS
    try:
        feed = feedparser.parse("https://www.kap.org.tr/tr/rss")
        for entry in feed.entries[:25]:
            if entry.link in PROCESSED_KAP_LINKS:
                continue
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
    onemli_kategoriler = [
        "yeni iş ilişkisi", "ihale", "finansal rapor", "bilanço",
        "kar payı", "sermaye artırımı", "pay alım", "birleşme", "bedelsiz"
    ]
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
                is_important = any(k in full_text for k in onemli_kategoriler)
                return f"{baslik}: {ozet[:55]}...", is_important
    except Exception:
        pass
    return "Aktif bildirim yok", False

# ============================================================
# ANA ANALİZ FONKSİYONU
# ============================================================
def analyze_ticker(symbol: str):
    try:
        ticker = yf.Ticker(f"{symbol}.IS")
        df_daily = ticker.history(period="6mo", interval="1d", auto_adjust=True)
        df_weekly = ticker.history(period="1y", interval="1wk", auto_adjust=True)

        if df_daily is None or len(df_daily) < 35:
            return None
        if df_weekly is None or len(df_weekly) < 15:
            return None

        last_close = float(df_daily["Close"].iloc[-1])
        prev_close = float(df_daily["Close"].iloc[-2])
        change_pct = ((last_close - prev_close) / prev_close) * 100

        last_volume = float(df_daily["Volume"].iloc[-1])
        hacim_tl = last_volume * last_close

        # 5 ve 10 günlük hacim
        avg_vol_5 = df_daily["Volume"].iloc[-6:-1].mean()
        rvol_5 = last_volume / avg_vol_5 if avg_vol_5 > 0 else 0
        avg_vol_10 = df_daily["Volume"].iloc[-11:-1].mean()
        rvol = last_volume / avg_vol_10 if avg_vol_10 > 0 else 0

        # RSI
        rsi_daily = df_daily.ta.rsi(length=14)
        rsi_weekly = df_weekly.ta.rsi(length=14)
        if rsi_daily is None or rsi_weekly is None:
            return None
        rsi_d = float(rsi_daily.iloc[-1])
        rsi_w = float(rsi_weekly.iloc[-1])

        # Stochastic
        stoch = df_daily.ta.stoch(k=14, d=3, smooth_k=3)
        if stoch is None or stoch.empty:
            return None
        k_col = next((c for c in stoch.columns if "STOCHk" in c), None)
        d_col = next((c for c in stoch.columns if "STOCHd" in c), None)
        if not k_col or not d_col:
            return None
        stoch_k = float(stoch[k_col].iloc[-1])
        stoch_d = float(stoch[d_col].iloc[-1])
        stoch_alimda = (stoch_k < 20) or (stoch_k > stoch_d and stoch_k < 35)

        # Bollinger Bands
        bb = df_daily.ta.bbands(length=20, std=2)
        if bb is None or bb.empty:
            return None
        lower_col = next((c for c in bb.columns if "BBL" in c), None)
        mid_col = next((c for c in bb.columns if "BBM" in c), None)
        if not lower_col or not mid_col:
            return None
        bb_lower = float(bb[lower_col].iloc[-1])
        bb_destek = last_close <= (bb_lower * 1.03) and last_close >= (bb_lower * 0.97)

        # ATR
        atr = df_daily.ta.atr(length=14)
        if atr is None:
            return None
        atr_val = float(atr.iloc[-1])
        stop_loss = max(0.01, last_close - (1.5 * atr_val))
        take_profit = last_close + (3.0 * atr_val)

        # Defter Değeri (PD/DD)
        pb_ratio = None
        try:
            info = ticker.info
            pb_ratio = info.get("priceToBook") or info.get("priceToBookRatio")
            if pb_ratio:
                pb_ratio = float(pb_ratio)
        except Exception:
            pass

        # Son 5 günde aşırı zarar kontrolü
        close_5d_ago = float(df_daily["Close"].iloc[-6]) if len(df_daily) >= 6 else last_close
        change_5d = ((last_close - close_5d_ago) / close_5d_ago) * 100
        asiri_zarar_yok = change_5d > -12

        avg_vol_20 = df_daily["Volume"].iloc[-20:].mean()
        tahta_durumu = "⚠️ Sığ Tahta" if avg_vol_20 < 400_000 else "🟢 Likit Tahta"

        kap_ozeti, kap_onemli = get_kap_news_api(symbol)

        # =====================================================
        # İKİ STRATEJİ
        # =====================================================
        # Strateji A: Klasik Dip + Hacim
        strateji_a = (
            rsi_d < 30 and
            rsi_w < 32 and
            stoch_alimda and
            hacim_tl >= 20_000_000 and
            rvol >= 1.0 and
            change_pct > 0
        )

        # Strateji B: Bollinger Alt + Düşük PD/DD + 5g Hacim + Zarar yok
        strateji_b = (
            bb_destek and
            (pb_ratio is not None and pb_ratio < 1.5) and
            rvol_5 >= 1.2 and
            asiri_zarar_yok and
            hacim_tl >= 8_000_000 and
            change_pct > -1
        )

        if not (strateji_a or strateji_b):
            return None

        # Yıldız
        yildiz = 3
        if rvol >= 2.0 or rvol_5 >= 2.0:
            yildiz += 1
        if bb_destek:
            yildiz += 1
        if kap_onemli:
            yildiz += 1
        if pb_ratio and pb_ratio < 1.0:
            yildiz += 1
        yildizlar = "⭐" * min(yildiz, 5)

        ema9 = df_daily.ta.ema(length=9)
        trend_kirilimi = False
        if ema9 is not None:
            trend_kirilimi = (last_close > float(ema9.iloc[-1])) and (prev_close <= float(ema9.iloc[-2]))

        return {
            "symbol": symbol,
            "fiyat": round(last_close, 2),
            "change_pct": round(change_pct, 2),
            "rsi_d": round(rsi_d, 1),
            "stoch_k": round(stoch_k, 1),
            "rvol": round(rvol, 2),
            "rvol_5": round(rvol_5, 2),
            "hacim_tl": format_compact_volume(hacim_tl),
            "tahta_durumu": tahta_durumu,
            "sl": round(stop_loss, 2),
            "tp": round(take_profit, 2),
            "kap_ozeti": kap_ozeti,
            "kap_onemli": kap_onemli,
            "trend_kirilimi": trend_kirilimi,
            "yildizlar": yildizlar,
            "pb_ratio": round(pb_ratio, 2) if pb_ratio else None,
            "bb_destek": bb_destek,
            "strateji": "A" if strateji_a else "B"
        }
    except Exception as e:
        logger.debug(f"{symbol} analiz hatası: {e}")
        return None

# ============================================================
# TARAMA
# ============================================================
def scan_bist_stocks(symbol_list, scan_time: str):
    now_str = datetime.now(TZ).strftime("%H:%M:%S")
    logger.info(f"[{now_str}] Tarama başladı → {scan_time} | {len(symbol_list)} hisse")

    eslesenler = []

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(analyze_ticker, sym): sym for sym in symbol_list}
        for future in as_completed(futures):
            res = future.result()
            if res:
                eslesenler.append(res)

    if not eslesenler:
        send_telegram_msg(
            f"ℹ️ <b>{scan_time} Taraması:</b> Strateji kriterlerine uyan hisse bulunamadı."
        )
        return

    eslesenler.sort(key=lambda x: (x["kap_onemli"], x["rvol"]), reverse=True)

    baslik_ek = "🌙 GECE BÜLTENİ" if scan_time == "23:00" else "GÜN İÇİ TARAMASI"
    mesaj = (
        f"🎯 <b>[DİP + BB + DÜŞÜK PD/DD AVCISI | {baslik_ek}]</b>\n"
        f"📅 <i>{datetime.now(TZ).strftime('%d.%m.%Y - %H:%M')}</i>\n\n"
    )

    for item in eslesenler:
        uyari = "🚨" if item["kap_onemli"] else ""
        strateji_adi = "Klasik Dip" if item["strateji"] == "A" else "BB Alt + Düşük PD/DD"

        hisse_str = (
            f"🔹 <b>#{item['symbol']}</b> | <b>{item['fiyat']} TL</b> (%+{item['change_pct']}) {uyari}\n"
            f"├ {'🚀 DÜŞEN KIRILIMI' if item['trend_kirilimi'] else '📊 Dipte Güç Topluyor'} {item['yildizlar']}\n"
            f"├ <b>Strateji:</b> {strateji_adi}\n"
            f"├ <b>Hacim:</b> {item['hacim_tl']} TL | RVOL10: {item['rvol']}x | RVOL5: {item['rvol_5']}x\n"
            f"├ <b>RSI:</b> {item['rsi_d']} | Stoch: {item['stoch_k']} | {item['tahta_durumu']}\n"
        )
        if item.get("pb_ratio"):
            hisse_str += f"├ <b>PD/DD:</b> {item['pb_ratio']}\n"
        hisse_str += (
            f"├ 🛑 SL: {item['sl']} TL | 🎯 TP: {item['tp']} TL\n"
            f"└ 📢 KAP: <i>{item['kap_ozeti']}</i>\n\n"
        )

        if len(mesaj) + len(hisse_str) > 3900:
            send_telegram_msg(mesaj)
            mesaj = ""
            time.sleep(1.2)

        mesaj += hisse_str

    if mesaj.strip():
        send_telegram_msg(mesaj)

    logger.info(f"Tarama bitti → {len(eslesenler)} hisse bulundu")

# ============================================================
# ANA DÖNGÜ
# ============================================================
def main():
    now = datetime.now(TZ)
    current_time_str = now.strftime("%H:%M")

    send_telegram_msg(
        "🤖 <b>BİST BOTU - GÜNCEL VERSİYON</b>\n"
        "⏰ 09:50 | 10:10 | 17:45 | 23:00\n"
        "📊 Strateji A: RSI Dip + Hacim 20M+\n"
        "📊 Strateji B: BB Alt + Düşük PD/DD + 5g Hacim\n"
        "🚀 Sistem aktif..."
    )

    try:
        check_kap_news()
        hedef = get_all_bist_tickers()
        scan_bist_stocks(hedef, f"İLK AÇILIŞ TESTİ ({current_time_str})")
        send_telegram_msg("✅ <b>Açılış testi tamamlandı!</b> Alarm saatleri bekleniyor.")
    except Exception as e:
        send_telegram_msg(f"❌ <b>Açılış testinde hata:</b> {e}")
        logger.error(f"Açılış hatası: {e}")

    while True:
        try:
            now = datetime.now(TZ)
            loop_time = now.strftime("%H:%M")
            loop_date = now.strftime("%Y-%m-%d")

            check_kap_news()

            scan_key = f"{loop_date}_{loop_time}"

            if loop_time in TARGET_SCAN_TIMES and scan_key not in SCANNED_TIMES_TODAY:
                hedef_hisseler = get_all_bist_tickers()
                scan_bist_stocks(hedef_hisseler, loop_time)
                SCANNED_TIMES_TODAY.add(scan_key)

                if loop_time == "23:00":
                    PROCESSED_KAP_LINKS.clear()
                    SCANNED_TIMES_TODAY.clear()
                    logger.info("Günlük listeler sıfırlandı")

            time.sleep(25)

        except KeyboardInterrupt:
            logger.info("Bot kapatıldı")
            break
        except Exception as e:
            logger.error(f"Ana döngü hatası: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
