#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BIST Bot — Tek Dosya
- Ana liste (Dip + BB + düşük PD/DD)
- %5+ yükselenler
- Hacim ≥20M + RVOL ≥1
- 23:00 Gece Bülteni (yarının tavan adayları kaydedilir)
- Ertesi gün 23:00: dün gece adaylarının kapanış % performans raporu
"""

import os
import json
import time
import threading
import logging
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, HTTPServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
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

# ============================================================
# HEALTH CHECK
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
    logger.info(f"Health-check port {port}")
    server.serve_forever()


threading.Thread(target=start_health_check_server, daemon=True).start()

# ============================================================
# AYARLAR
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1734551753")

TZ = ZoneInfo("Europe/Istanbul")
TARGET_SCAN_TIMES = ["09:50", "10:10", "17:45", "23:00"]

NIGHT_CANDIDATES_FILE = Path("night_candidates.json")

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
    "ZRGYO",
]

PROCESSED_KAP_LINKS = set()
SCANNED_TIMES_TODAY = set()

# ============================================================
# YARDIMCI
# ============================================================
def send_telegram_msg(message: str):
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
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
        requests.post(url, json=payload, timeout=12)
    except Exception as e:
        logger.warning(f"Telegram hata: {e}")


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
                logger.info(f"Canlı liste: {len(filtered)} hisse")
                return filtered
    except Exception as e:
        logger.warning(f"Canlı liste alınamadı: {e}")
    return sorted(list(set(FULL_BIST_LIST) | BIST_30_SET))


# ============================================================
# KAP
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
        logger.debug(f"KAP RSS: {e}")


def get_kap_news_api(symbol: str):
    onemli = [
        "yeni iş ilişkisi", "ihale", "finansal rapor", "bilanço", "kar payı",
        "sermaye artırımı", "pay alım", "birleşme", "bedelsiz",
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
                is_important = any(k in full_text for k in onemli)
                return f"{baslik}: {ozet[:55]}...", is_important
    except Exception:
        pass
    return "Aktif bildirim yok", False


# ============================================================
# GECE ADAYLARI (JSON)
# ============================================================
def load_night_candidates():
    try:
        if NIGHT_CANDIDATES_FILE.exists():
            with open(NIGHT_CANDIDATES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"night_candidates okunamadı: {e}")
    return {}


def save_night_candidates(candidates: dict):
    try:
        payload = {
            "date": datetime.now(TZ).strftime("%Y-%m-%d"),
            "saved_at": datetime.now(TZ).isoformat(),
            "items": candidates,
        }
        with open(NIGHT_CANDIDATES_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.info(f"Gece adayları kaydedildi: {len(candidates)} hisse")
    except Exception as e:
        logger.error(f"night_candidates yazılamadı: {e}")


def fetch_close_snapshot(symbol: str):
    try:
        t = yf.Ticker(f"{symbol}.IS")
        df = t.history(period="1mo", interval="1d", auto_adjust=True)
        if df is None or len(df) < 12:
            return None

        close = float(df["Close"].iloc[-1])
        vol = float(df["Volume"].iloc[-1])
        hacim_tl = vol * close
        avg10 = float(df["Volume"].iloc[-11:-1].mean())
        rvol = (vol / avg10) if avg10 > 0 else 0.0

        atr = df.ta.atr(length=14)
        atr_val = float(atr.iloc[-1]) if atr is not None and not atr.empty else close * 0.02
        sl = max(0.01, close - 1.5 * atr_val)
        tp = close + 3.0 * atr_val

        return {
            "fiyat": round(close, 2),
            "hacim_tl": format_compact_volume(hacim_tl),
            "rvol": round(rvol, 2),
            "sl": round(sl, 2),
            "tp": round(tp, 2),
        }
    except Exception as e:
        logger.debug(f"snapshot {symbol}: {e}")
        return None


def send_previous_night_performance_report():
    """Dün 23:00 tavan adaylarının bugün kapanış performansı."""
    data = load_night_candidates()
    items = data.get("items") or {}
    source_date = data.get("date", "?")
    today = datetime.now(TZ).strftime("%Y-%m-%d")

    if not items:
        send_telegram_msg(
            "📋 <b>DÜN GECE TAVAN ADAYLARI — PERFORMANS</b>\n"
            "Önceki geceden kayıtlı aday yok."
        )
        return

    if source_date == today:
        logger.info("Gece adayları bugüne ait; performans yarın raporlanacak.")
        return

    logger.info(f"Dün gece ({source_date}) adayları raporlanıyor: {len(items)}")
    rows = []

    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(fetch_close_snapshot, s): s for s in items.keys()}
        for fut in as_completed(futures):
            sym = futures[fut]
            snap = fut.result()
            entry = items[sym]
            entry_price = float(entry.get("fiyat", 0))
            if not snap or entry_price <= 0:
                continue
            pct = ((snap["fiyat"] - entry_price) / entry_price) * 100
            rows.append({
                "symbol": sym,
                "entry": entry_price,
                "fiyat": snap["fiyat"],
                "pct": round(pct, 2),
                "hacim_tl": snap["hacim_tl"],
                "rvol": snap["rvol"],
                "sl": snap["sl"],
                "tp": snap["tp"],
                "night_sl": entry.get("sl"),
                "night_tp": entry.get("tp"),
            })

    if not rows:
        send_telegram_msg(
            f"📋 <b>DÜN GECE TAVAN ADAYLARI — PERFORMANS</b>\n"
            f"📅 Kaynak: {source_date}\nGüncel fiyat alınamadı."
        )
        return

    rows.sort(key=lambda x: x["pct"], reverse=True)
    tarih = datetime.now(TZ).strftime("%d.%m.%Y - %H:%M")

    msg = (
        f"📋 <b>DÜN GECE TAVAN ADAYLARI — GÜN SONU PERFORMANS</b>\n"
        f"📅 Rapor: <i>{tarih}</i>\n"
        f"📌 Kaynak gece: <b>{source_date} 23:00</b>\n"
        f"🔢 Adet: <b>{len(rows)}</b>\n"
        f"───────────────────\n\n"
    )

    for r in rows:
        emoji = "🟢" if r["pct"] >= 0 else "🔴"
        msg += (
            f"{emoji} <b>#{r['symbol']}</b>\n"
            f"├ Dün gece: <b>{r['entry']} TL</b> → Bugün: <b>{r['fiyat']} TL</b>\n"
            f"├ <b>Getiri: %{r['pct']:+.2f}</b>\n"
            f"├ Hacim: {r['hacim_tl']} TL | RVOL: {r['rvol']}x\n"
            f"├ 🛑 SL: {r['sl']} | 🎯 TP: {r['tp']}\n"
        )
        if r.get("night_sl") and r.get("night_tp"):
            msg += f"└ (Dün gece SL/TP: {r['night_sl']} / {r['night_tp']})\n\n"
        else:
            msg += "\n"

        if len(msg) > 3500:
            send_telegram_msg(msg)
            msg = ""
            time.sleep(1)

    if msg.strip():
        send_telegram_msg(msg)

    poz = sum(1 for r in rows if r["pct"] > 0)
    neg = sum(1 for r in rows if r["pct"] < 0)
    ort = sum(r["pct"] for r in rows) / len(rows)
    send_telegram_msg(
        f"📊 <b>Özet ({source_date} → bugün)</b>\n"
        f"• Yeşil: {poz} | Kırmızı: {neg}\n"
        f"• Ortalama getiri: <b>%{ort:+.2f}</b>"
    )


def send_night_summary_table(ana_liste, yuzde5_liste, hacim_liste):
    """23:00 kompakt özet: Hisse | Fiyat | Günlük % | Hacim"""
    merged = {}
    for lst in (ana_liste, yuzde5_liste, hacim_liste):
        for it in lst:
            sym = it["symbol"]
            if sym not in merged or it["change_pct"] > merged[sym]["change_pct"]:
                merged[sym] = it

    if not merged:
        send_telegram_msg("📋 <b>23:00 ÖZET TABLO</b>\nListelenecek hisse yok.")
        return

    rows = sorted(merged.values(), key=lambda x: x["change_pct"], reverse=True)
    tarih = datetime.now(TZ).strftime("%d.%m.%Y - %H:%M")

    msg = (
        f"📋 <b>23:00 GECE BÜLTENİ — ÖZET LİSTE</b>\n"
        f"📅 <i>{tarih}</i>\n"
        f"───────────────────\n"
        f"<pre>"
        f"{'Hisse':<8} {'Fiyat':>8} {'Günlük %':>9} {'Hacim':>10}\n"
        f"{'-'*8} {'-'*8} {'-'*9} {'-'*10}\n"
    )
    for it in rows:
        msg += (
            f"{it['symbol']:<8} "
            f"{it['fiyat']:>7.2f} "
            f"%{it['change_pct']:>+7.2f} "
            f"{it['hacim_tl']:>10}\n"
        )
        if len(msg) > 3500:
            msg += "</pre>"
            send_telegram_msg(msg)
            msg = "<pre>"
            time.sleep(0.8)
    msg += "</pre>"
    send_telegram_msg(msg)


# ============================================================
# ANALİZ
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

        avg_vol_5 = df_daily["Volume"].iloc[-6:-1].mean()
        rvol_5 = last_volume / avg_vol_5 if avg_vol_5 > 0 else 0
        avg_vol_10 = df_daily["Volume"].iloc[-11:-1].mean()
        rvol = last_volume / avg_vol_10 if avg_vol_10 > 0 else 0

        rsi_daily = df_daily.ta.rsi(length=14)
        rsi_weekly = df_weekly.ta.rsi(length=14)
        if rsi_daily is None or rsi_weekly is None:
            return None
        rsi_d = float(rsi_daily.iloc[-1])
        rsi_w = float(rsi_weekly.iloc[-1])

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

        bb = df_daily.ta.bbands(length=20, std=2)
        bb_destek = False
        if bb is not None and not bb.empty:
            lower_col = next((c for c in bb.columns if "BBL" in c), None)
            if lower_col:
                bb_lower = float(bb[lower_col].iloc[-1])
                bb_destek = last_close <= (bb_lower * 1.03) and last_close >= (bb_lower * 0.97)

        atr = df_daily.ta.atr(length=14)
        if atr is None:
            return None
        atr_val = float(atr.iloc[-1])
        stop_loss = max(0.01, last_close - (1.5 * atr_val))
        take_profit = last_close + (3.0 * atr_val)

        pb_ratio = None
        try:
            info = ticker.info
            pb_ratio = info.get("priceToBook") or info.get("priceToBookRatio")
            if pb_ratio:
                pb_ratio = float(pb_ratio)
        except Exception:
            pass

        close_5d_ago = float(df_daily["Close"].iloc[-6]) if len(df_daily) >= 6 else last_close
        change_5d = ((last_close - close_5d_ago) / close_5d_ago) * 100
        asiri_zarar_yok = change_5d > -12

        avg_vol_20 = df_daily["Volume"].iloc[-20:].mean()
        tahta_durumu = "⚠️ Sığ Tahta" if avg_vol_20 < 400_000 else "🟢 Likit Tahta"

        kap_ozeti, kap_onemli = get_kap_news_api(symbol)

        strateji_a = (
            rsi_d < 30 and rsi_w < 32 and stoch_alimda
            and hacim_tl >= 20_000_000 and rvol >= 1.0 and change_pct > 0
        )
        strateji_b = (
            bb_destek and (pb_ratio is not None and pb_ratio < 1.5)
            and rvol_5 >= 1.2 and asiri_zarar_yok
            and hacim_tl >= 8_000_000 and change_pct > -1
        )
        yuzde_5_ustu = change_pct >= 5.0 and hacim_tl >= 5_000_000
        hacim_patlamasi = hacim_tl >= 20_000_000 and rvol >= 1.0

        if not (strateji_a or strateji_b or yuzde_5_ustu or hacim_patlamasi):
            return None

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
            trend_kirilimi = (
                last_close > float(ema9.iloc[-1])
                and prev_close <= float(ema9.iloc[-2])
            )

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
            "tahta_durumu": tahta_durumu,
            "sl": round(stop_loss, 2),
            "tp": round(take_profit, 2),
            "kap_ozeti": kap_ozeti,
            "kap_onemli": kap_onemli,
            "trend_kirilimi": trend_kirilimi,
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


# ============================================================
# TARAMA
# ============================================================
def scan_bist_stocks(symbol_list, scan_time: str):
    now_str = datetime.now(TZ).strftime("%H:%M:%S")
    logger.info(f"[{now_str}] Tarama → {scan_time} | {len(symbol_list)} hisse")

    ana_liste = []
    yuzde5_liste = []
    hacim_liste = []

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(analyze_ticker, sym): sym for sym in symbol_list}
        for future in as_completed(futures):
            res = future.result()
            if res:
                if res["strateji_a"] or res["strateji_b"]:
                    ana_liste.append(res)
                if res["yuzde_5_ustu"]:
                    yuzde5_liste.append(res)
                if res["hacim_patlamasi"]:
                    hacim_liste.append(res)

    ana_liste.sort(key=lambda x: (x["kap_onemli"], x["rvol"]), reverse=True)
    yuzde5_liste.sort(key=lambda x: x["change_pct"], reverse=True)
    hacim_liste.sort(key=lambda x: x["hacim_tl_raw"], reverse=True)

    baslik_ek = "🌙 GECE BÜLTENİ" if scan_time == "23:00" else "GÜN İÇİ TARAMASI"
    tarih = datetime.now(TZ).strftime("%d.%m.%Y - %H:%M")

    # 1) Ana liste
    if ana_liste:
        mesaj = f"🎯 <b>[DİP + BB + DÜŞÜK PD/DD | {baslik_ek}]</b>\n📅 <i>{tarih}</i>\n\n"
        for item in ana_liste:
            uyari = "🚨" if item["kap_onemli"] else ""
            durum = (
                f"🚀 <b>Durum:</b> DÜŞEN KIRILIMI ONAYLANDI {item['yildizlar']}"
                if item["trend_kirilimi"]
                else f"📊 <b>Durum:</b> Dipte Güç Topluyor {item['yildizlar']}"
            )
            strateji_adi = "Klasik Dip" if item["strateji_a"] else "BB Alt + Düşük PD/DD"
            hisse_str = (
                f"🔹 <b>#{item['symbol']}</b> | <b>{item['fiyat']} TL</b> (%+{item['change_pct']}) {uyari}\n"
                f"├ {durum}\n"
                f"├ <b>Strateji:</b> {strateji_adi}\n"
                f"├ <b>Hacim:</b> {item['hacim_tl']} TL | RVOL10: {item['rvol']}x | RVOL5: {item['rvol_5']}x\n"
                f"├ <b>RSI:</b> {item['rsi_d']} | Stoch: {item['stoch_k']} | {item['tahta_durumu']}\n"
            )
            if item.get("pb_ratio"):
                hisse_str += f"├ <b>PD/DD:</b> {item['pb_ratio']}\n"
            hisse_str += (
                f"├ 🛑 <b>SL:</b> {item['sl']} TL | 🎯 <b>TP:</b> {item['tp']} TL\n"
                f"└ 📢 <b>KAP:</b> <i>{item['kap_ozeti']}</i>\n\n"
            )
            if len(mesaj) + len(hisse_str) > 3800:
                send_telegram_msg(mesaj)
                mesaj = ""
                time.sleep(1)
            mesaj += hisse_str
        if mesaj.strip():
            send_telegram_msg(mesaj)
    else:
        send_telegram_msg(f"ℹ️ <b>{scan_time}</b> — Ana stratejiye uyan hisse yok.")

    # 2) %5+
    if yuzde5_liste:
        mesaj = f"🚀 <b>[%5 VE ÜZERİ YÜKSELENLER | {baslik_ek}]</b>\n📅 <i>{tarih}</i>\n\n"
        for item in yuzde5_liste[:15]:
            mesaj += (
                f"🔹 <b>#{item['symbol']}</b> | <b>{item['fiyat']} TL</b> <b>(%+{item['change_pct']})</b>\n"
                f"├ Hacim: {item['hacim_tl']} | RVOL: {item['rvol']}x\n"
                f"└ KAP: <i>{item['kap_ozeti']}</i>\n\n"
            )
            if len(mesaj) > 3800:
                send_telegram_msg(mesaj)
                mesaj = ""
        if mesaj.strip():
            send_telegram_msg(mesaj)

    # 3) Hacim patlaması
    if hacim_liste:
        mesaj = f"💥 <b>[HACİM ≥20M + RVOL≥1 | {baslik_ek}]</b>\n📅 <i>{tarih}</i>\n\n"
        for item in hacim_liste[:15]:
            mesaj += (
                f"🔹 <b>#{item['symbol']}</b> | {item['fiyat']} TL (%+{item['change_pct']})\n"
                f"├ Hacim: <b>{item['hacim_tl']}</b> | RVOL: <b>{item['rvol']}x</b>\n"
                f"└ KAP: <i>{item['kap_ozeti']}</i>\n\n"
            )
            if len(mesaj) > 3800:
                send_telegram_msg(mesaj)
                mesaj = ""
        if mesaj.strip():
            send_telegram_msg(mesaj)

    # 4) 23:00 özel akış
    if scan_time == "23:00":
        # Önce dün gece adaylarının bugünkü performansı
        send_previous_night_performance_report()

        # Özet tablo (bu gece çıkanlar)
        send_night_summary_table(ana_liste, yuzde5_liste, hacim_liste)

        # Bu gece adaylarını kaydet → yarın raporlanacak
        night_items = {}
        for lst in (ana_liste, yuzde5_liste, hacim_liste):
            for it in lst:
                sym = it["symbol"]
                if sym not in night_items:
                    night_items[sym] = {
                        "fiyat": it["fiyat"],
                        "sl": it["sl"],
                        "tp": it["tp"],
                        "rvol": it["rvol"],
                        "hacim_tl": it["hacim_tl"],
                        "change_pct": it["change_pct"],
                    }
        save_night_candidates(night_items)

        if night_items:
            send_telegram_msg(
                f"💾 <b>Yarının tavan adayları kaydedildi</b>\n"
                f"Adet: <b>{len(night_items)}</b>\n"
                f"Yarın 23:00’da kapanış performansı raporlanacak."
            )

    logger.info(
        f"Bitti → Ana:{len(ana_liste)} | %5+:{len(yuzde5_liste)} | Hacim:{len(hacim_liste)}"
    )


# ============================================================
# ANA DÖNGÜ
# ============================================================
def main():
    now = datetime.now(TZ)
    current_time_str = now.strftime("%H:%M")

    send_telegram_msg(
        "🤖 <b>BİST BOTU — TEK DOSYA</b>\n"
        "⏰ 09:50 | 10:10 | 17:45 | 23:00\n"
        "📋 Listeler:\n"
        "• Dip + BB + düşük PD/DD\n"
        "• %5+ yükselenler\n"
        "• Hacim ≥20M + RVOL ≥1\n"
        "• 23:00 Gece bülteni + özet tablo\n"
        "• Ertesi gün 23:00: dün gece adaylarının % performans\n"
        "🚀 Sistem aktif..."
    )

    try:
        check_kap_news()
        hedef = get_all_bist_tickers()
        scan_bist_stocks(hedef, f"İLK AÇILIŞ TESTİ ({current_time_str})")
        send_telegram_msg("✅ Açılış testi tamamlandı. Alarm saatleri bekleniyor.")
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
                    # night_candidates.json SİLİNMEZ — yarınki rapor için kalır

            time.sleep(25)
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Döngü hatası: {e}")
            time.sleep(30)


if __name__ == "__main__":
    main()
