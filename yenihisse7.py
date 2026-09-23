#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BIST Bot — Tek Dosya
+ 10 dk'da bir negatif haber taraması (hisse + kripto)
+ Haberde sesli / acil Telegram uyarısı
+ 23:00 gece adayları + ertesi gün performans raporu
"""

import os
import re
import json
import time
import hashlib
import threading
import logging
import subprocess
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

NEWS_CHECK_SECONDS = 10 * 60          # 10 dakika
NIGHT_CANDIDATES_FILE = Path("night_candidates.json")
PROCESSED_NEWS_FILE = Path("processed_news.json")

# Negatif / piyasa bozucu anahtar kelimeler
NEGATIVE_KEYWORDS = [
    # TR
    "çöküş", "kriz", "panik", "satış dalgası", "sert düşüş", "çarşaf",
    "faiz artırımı", "tcmb faiz", "kur şoku", "döviz krizi", "sermaye kontrolü",
    "yeni vergi", "ek vergi", "bakan istifa", "erken seçim", "siyasi kriz",
    "bankacılık krizi", "enflasyon şoku", "temerrüt", "iflas", "konkordato",
    "soruşturma", "ceza", "yaptırım", "ambargo", "savaş", "saldırı", "gerilim",
    "üretim durdu", "grev", "yangın", "patlama",
    # EN
    "crash", "collapse", "recession", "crisis", "panic", "sell-off", "selloff",
    "market plunge", "stocks fall", "stocks drop", "sharp decline", "tumbling",
    "bear market", "rate hike", "fed hikes", "hawkish", "tightening",
    "war", "invasion", "missile", "attack", "escalation", "sanctions", "embargo",
    "bank failure", "default", "debt ceiling", "stagflation", "inflation surge",
    "bankruptcy", "insolvency", "hack", "hacked", "exploit", "depeg", "delisting",
    "crypto ban", "bitcoin ban", "exchange hack", "liquidation cascade", "ftx",
]

NEWS_FEEDS = [
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.investing.com/rss/news_25.rss",
    "https://www.investing.com/rss/news_301.rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://www.kap.org.tr/tr/rss",
]

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
LAST_NEWS_CHECK = 0

# ============================================================
# SESLİ UYARI
# ============================================================
def play_alert_sound(times: int = 3):
    """Sunucuda bip / zil sesi (mümkünse). Telefon Telegram bildirimi ile uyanır."""
    for _ in range(times):
        # Terminal bell
        print("\a", end="", flush=True)
        # Linux speaker-test (varsa)
        try:
            subprocess.run(
                ["speaker-test", "-t", "sine", "-f", "880", "-l", "1"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
        except Exception:
            pass
        # paplay / aplay ile kısa bip (varsa)
        try:
            subprocess.run(
                ["timeout", "0.4", "speaker-test", "-c1", "-t", "sine", "-f", "1000"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1,
            )
        except Exception:
            pass
        time.sleep(0.35)


# ============================================================
# TELEGRAM
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
        "disable_notification": False,  # sesli bildirim açık
    }
    try:
        requests.post(url, json=payload, timeout=12)
    except Exception as e:
        logger.warning(f"Telegram hata: {e}")


def send_urgent_alert(message: str):
    """Acil haber — Telegram (bildirim sesi) + sunucu bip."""
    play_alert_sound(times=4)
    send_telegram_msg(message)
    # İkinci mesaj: sessiz değil, dikkat çeksin
    time.sleep(0.5)
    send_telegram_msg("🚨🚨 <b>ACİL — YUKARIDAKİ HABERİ KONTROL ET</b> 🚨🚨")


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


# ============================================================
# HABER MOTORU (10 dk)
# ============================================================
def load_processed_news() -> set:
    try:
        if PROCESSED_NEWS_FILE.exists():
            with open(PROCESSED_NEWS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data.get("ids", []))
    except Exception:
        pass
    return set()


def save_processed_news(ids: set):
    try:
        # Son 500 id tut
        trimmed = list(ids)[-500:]
        with open(PROCESSED_NEWS_FILE, "w", encoding="utf-8") as f:
            json.dump({"ids": trimmed}, f)
    except Exception as e:
        logger.debug(f"processed_news yazılamadı: {e}")


def make_news_id(title: str, link: str) -> str:
    raw = f"{title}|{link}".lower().strip()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def is_negative_news(title: str, summary: str):
    text = f"{title} {summary}".lower()
    text = re.sub(r"\s+", " ", text)
    matched = [kw for kw in NEGATIVE_KEYWORDS if kw.lower() in text]
    return matched


def check_negative_market_news():
    """Her 10 dakikada hisse + kripto bozucu haber taraması."""
    global LAST_NEWS_CHECK
    now = time.time()
    if now - LAST_NEWS_CHECK < NEWS_CHECK_SECONDS:
        return
    LAST_NEWS_CHECK = now

    logger.info("Negatif haber taraması (10 dk)...")
    processed = load_processed_news()
    found = []

    for feed_url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            source = feed.feed.get("title", feed_url) if hasattr(feed, "feed") else feed_url
            for entry in feed.entries[:15]:
                title = (getattr(entry, "title", "") or "").strip()
                summary = (
                    getattr(entry, "summary", "")
                    or getattr(entry, "description", "")
                    or ""
                ).strip()
                link = (getattr(entry, "link", "") or "").strip()
                if not title:
                    continue

                nid = make_news_id(title, link)
                if nid in processed:
                    continue

                matched = is_negative_news(title, summary)
                processed.add(nid)

                if matched:
                    found.append({
                        "title": title,
                        "summary": summary[:200],
                        "link": link,
                        "keywords": matched[:6],
                        "source": str(source)[:60],
                    })
        except Exception as e:
            logger.debug(f"Feed hatası {feed_url}: {e}")

    save_processed_news(processed)

    if not found:
        logger.info("Negatif haber yok.")
        return

    logger.warning(f"⚠️ {len(found)} negatif haber!")
    for item in found[:5]:
        kw = ", ".join(item["keywords"])
        msg = (
            "🚨🚨 <b>ACİL PİYASA / KRİPTO UYARISI</b> 🚨🚨\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ Hisse veya kripto piyasasını olumsuz etkileyebilecek haber!\n\n"
            f"📰 <b>{item['title']}</b>\n"
            f"🔎 İfadeler: <code>{kw}</code>\n"
            f"🌐 Kaynak: {item['source']}\n"
        )
        if item["link"]:
            msg += f"🔗 <a href='{item['link']}'>Haberi oku</a>\n"
        msg += (
            f"\n⏰ {datetime.now(TZ).strftime('%d.%m.%Y %H:%M')}\n"
            "🔇 Pozisyonları gözden geçirin. Risk yönetimi uygulayın."
        )
        send_urgent_alert(msg)
        time.sleep(1.2)

    if len(found) > 5:
        send_telegram_msg(
            f"⚠️ Bu turda toplam <b>{len(found)}</b> negatif haber. İlk 5 gönderildi."
        )


# ============================================================
# HİSSE LİSTESİ
# ============================================================
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
        logger.warning(f"Canlı liste: {e}")
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
        logger.debug(f"KAP: {e}")


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
                baslik = son.get("title", "Özel Durum")
                ozet = son.get("summary") or baslik
                full_text = f"{baslik} {ozet}".lower()
                is_important = any(k in full_text for k in onemli)
                return f"{baslik}: {ozet[:55]}...", is_important
    except Exception:
        pass
    return "Aktif bildirim yok", False


# ============================================================
# GECE ADAYLARI
# ============================================================
def load_night_candidates():
    try:
        if NIGHT_CANDIDATES_FILE.exists():
            with open(NIGHT_CANDIDATES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"night_candidates: {e}")
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
        logger.info(f"Gece adayları kaydedildi: {len(candidates)}")
    except Exception as e:
        logger.error(f"night yazılamadı: {e}")


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
        return {
            "fiyat": round(close, 2),
            "hacim_tl": format_compact_volume(hacim_tl),
            "rvol": round(rvol, 2),
            "sl": round(max(0.01, close - 1.5 * atr_val), 2),
            "tp": round(close + 3.0 * atr_val, 2),
        }
    except Exception:
        return None


def send_previous_night_performance_report():
    data = load_night_candidates()
    items = data.get("items") or {}
    source_date = data.get("date", "?")
    today = datetime.now(TZ).strftime("%Y-%m-%d")

    if not items:
        send_telegram_msg(
            "📋 <b>DÜN GECE TAVAN ADAYLARI — PERFORMANS</b>\nKayıtlı aday yok."
        )
        return
    if source_date == today:
        logger.info("Gece adayları bugüne ait; performans yarın.")
        return

    rows = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(fetch_close_snapshot, s): s for s in items}
        for fut in as_completed(futures):
            sym = futures[fut]
            snap = fut.result()
            entry = items[sym]
            ep = float(entry.get("fiyat", 0))
            if not snap or ep <= 0:
                continue
            pct = ((snap["fiyat"] - ep) / ep) * 100
            rows.append({
                "symbol": sym,
                "entry": ep,
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
        send_telegram_msg(f"📋 Performans ({source_date}): veri alınamadı.")
        return

    rows.sort(key=lambda x: x["pct"], reverse=True)
    tarih = datetime.now(TZ).strftime("%d.%m.%Y - %H:%M")
    msg = (
        f"📋 <b>DÜN GECE TAVAN ADAYLARI — GÜN SONU PERFORMANS</b>\n"
        f"📅 {tarih} | Kaynak: <b>{source_date} 23:00</b>\n"
        f"🔢 {len(rows)} hisse\n───────────────────\n\n"
    )
    for r in rows:
        emoji = "🟢" if r["pct"] >= 0 else "🔴"
        msg += (
            f"{emoji} <b>#{r['symbol']}</b>\n"
            f"├ Dün gece: <b>{r['entry']} TL</b> → Bugün: <b>{r['fiyat']} TL</b>\n"
            f"├ <b>Getiri: %{r['pct']:+.2f}</b>\n"
            f"├ Hacim: {r['hacim_tl']} | RVOL: {r['rvol']}x\n"
            f"├ 🛑 SL: {r['sl']} | 🎯 TP: {r['tp']}\n"
        )
        if r.get("night_sl"):
            msg += f"└ (Dün SL/TP: {r['night_sl']} / {r['night_tp']})\n\n"
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
        f"• Ortalama: <b>%{ort:+.2f}</b>"
    )


def send_night_summary_table(ana_liste, yuzde5_liste, hacim_liste):
    merged = {}
    for lst in (ana_liste, yuzde5_liste, hacim_liste):
        for it in lst:
            s = it["symbol"]
            if s not in merged or it["change_pct"] > merged[s]["change_pct"]:
                merged[s] = it
    if not merged:
        send_telegram_msg("📋 <b>23:00 ÖZET</b>\nHisse yok.")
        return
    rows = sorted(merged.values(), key=lambda x: x["change_pct"], reverse=True)
    tarih = datetime.now(TZ).strftime("%d.%m.%Y - %H:%M")
    msg = (
        f"📋 <b>23:00 GECE BÜLTENİ — ÖZET</b>\n📅 {tarih}\n───────────────────\n<pre>"
        f"{'Hisse':<8} {'Fiyat':>8} {'Günlük %':>9} {'Hacim':>10}\n"
        f"{'-'*8} {'-'*8} {'-'*9} {'-'*10}\n"
    )
    for it in rows:
        msg += f"{it['symbol']:<8} {it['fiyat']:>7.2f} %{it['change_pct']:>+7.2f} {it['hacim_tl']:>10}\n"
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
        stop_loss = max(0.01, last_close - 1.5 * atr_val)
        take_profit = last_close + 3.0 * atr_val

        pb_ratio = None
        try:
            info = ticker.info
            pb_ratio = info.get("priceToBook") or info.get("priceToBookRatio")
            if pb_ratio:
                pb_ratio = float(pb_ratio)
        except Exception:
            pass

        close_5d = float(df_daily["Close"].iloc[-6]) if len(df_daily) >= 6 else last_close
        asiri_zarar_yok = ((last_close - close_5d) / close_5d) * 100 > -12
        avg_vol_20 = df_daily["Volume"].iloc[-20:].mean()
        tahta = "⚠️ Sığ Tahta" if avg_vol_20 < 400_000 else "🟢 Likit Tahta"
        kap_ozeti, kap_onemli = get_kap_news_api(symbol)

        strateji_a = (
            rsi_d < 30 and rsi_w < 32 and stoch_alimda
            and hacim_tl >= 20_000_000 and rvol >= 1.0 and change_pct > 0
        )
        strateji_b = (
            bb_destek and pb_ratio is not None and pb_ratio < 1.5
            and rvol_5 >= 1.2 and asiri_zarar_yok
            and hacim_tl >= 8_000_000 and change_pct > -1
        )
        yuzde_5 = change_pct >= 5.0 and hacim_tl >= 5_000_000
        hacim_pat = hacim_tl >= 20_000_000 and rvol >= 1.0
        if not (strateji_a or strateji_b or yuzde_5 or hacim_pat):
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

        ema9 = df_daily.ta.ema(length=9)
        trend = False
        if ema9 is not None:
            trend = last_close > float(ema9.iloc[-1]) and prev_close <= float(ema9.iloc[-2])

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
            "tahta_durumu": tahta,
            "sl": round(stop_loss, 2),
            "tp": round(take_profit, 2),
            "kap_ozeti": kap_ozeti,
            "kap_onemli": kap_onemli,
            "trend_kirilimi": trend,
            "yildizlar": "⭐" * min(yildiz, 5),
            "pb_ratio": round(pb_ratio, 2) if pb_ratio else None,
            "strateji_a": strateji_a,
            "strateji_b": strateji_b,
            "yuzde_5_ustu": yuzde_5,
            "hacim_patlamasi": hacim_pat,
        }
    except Exception as e:
        logger.debug(f"{symbol}: {e}")
        return None


# ============================================================
# TARAMA
# ============================================================
def scan_bist_stocks(symbol_list, scan_time: str):
    logger.info(f"Tarama → {scan_time} | {len(symbol_list)} hisse")
    ana, y5, hac = [], [], []

    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(analyze_ticker, s): s for s in symbol_list}
        for f in as_completed(futs):
            r = f.result()
            if not r:
                continue
            if r["strateji_a"] or r["strateji_b"]:
                ana.append(r)
            if r["yuzde_5_ustu"]:
                y5.append(r)
            if r["hacim_patlamasi"]:
                hac.append(r)

    ana.sort(key=lambda x: (x["kap_onemli"], x["rvol"]), reverse=True)
    y5.sort(key=lambda x: x["change_pct"], reverse=True)
    hac.sort(key=lambda x: x["hacim_tl_raw"], reverse=True)

    baslik = "🌙 GECE BÜLTENİ" if scan_time == "23:00" else "GÜN İÇİ"
    tarih = datetime.now(TZ).strftime("%d.%m.%Y - %H:%M")

    if ana:
        msg = f"🎯 <b>[DİP + BB + PD/DD | {baslik}]</b>\n📅 {tarih}\n\n"
        for it in ana:
            u = "🚨" if it["kap_onemli"] else ""
            st = "Klasik Dip" if it["strateji_a"] else "BB + PD/DD"
            d = (
                f"🚀 KIRILIM {it['yildizlar']}"
                if it["trend_kirilimi"]
                else f"📊 Dip {it['yildizlar']}"
            )
            block = (
                f"🔹 <b>#{it['symbol']}</b> | <b>{it['fiyat']} TL</b> (%+{it['change_pct']}) {u}\n"
                f"├ {d} | {st}\n"
                f"├ Hacim: {it['hacim_tl']} | RVOL: {it['rvol']}x\n"
                f"├ RSI: {it['rsi_d']} | Stoch: {it['stoch_k']} | {it['tahta_durumu']}\n"
                f"├ 🛑 SL: {it['sl']} | 🎯 TP: {it['tp']}\n"
                f"└ KAP: <i>{it['kap_ozeti']}</i>\n\n"
            )
            if len(msg) + len(block) > 3800:
                send_telegram_msg(msg)
                msg = ""
                time.sleep(1)
            msg += block
        if msg.strip():
            send_telegram_msg(msg)
    else:
        send_telegram_msg(f"ℹ️ <b>{scan_time}</b> — Ana listede hisse yok.")

    if y5:
        msg = f"🚀 <b>[%5+ | {baslik}]</b>\n📅 {tarih}\n\n"
        for it in y5[:15]:
            msg += (
                f"🔹 <b>#{it['symbol']}</b> | {it['fiyat']} TL (%+{it['change_pct']})\n"
                f"├ Hacim: {it['hacim_tl']} | RVOL: {it['rvol']}x\n"
                f"└ KAP: <i>{it['kap_ozeti']}</i>\n\n"
            )
            if len(msg) > 3800:
                send_telegram_msg(msg)
                msg = ""
        if msg.strip():
            send_telegram_msg(msg)

    if hac:
        msg = f"💥 <b>[HACİM ≥20M + RVOL≥1 | {baslik}]</b>\n📅 {tarih}\n\n"
        for it in hac[:15]:
            msg += (
                f"🔹 <b>#{it['symbol']}</b> | {it['fiyat']} TL (%+{it['change_pct']})\n"
                f"├ Hacim: <b>{it['hacim_tl']}</b> | RVOL: <b>{it['rvol']}x</b>\n"
                f"└ KAP: <i>{it['kap_ozeti']}</i>\n\n"
            )
            if len(msg) > 3800:
                send_telegram_msg(msg)
                msg = ""
        if msg.strip():
            send_telegram_msg(msg)

    if scan_time == "23:00":
        send_previous_night_performance_report()
        send_night_summary_table(ana, y5, hac)
        night = {}
        for lst in (ana, y5, hac):
            for it in lst:
                if it["symbol"] not in night:
                    night[it["symbol"]] = {
                        "fiyat": it["fiyat"],
                        "sl": it["sl"],
                        "tp": it["tp"],
                        "rvol": it["rvol"],
                        "hacim_tl": it["hacim_tl"],
                        "change_pct": it["change_pct"],
                    }
        save_night_candidates(night)
        if night:
            send_telegram_msg(
                f"💾 <b>Yarının tavan adayları kaydedildi</b> ({len(night)} hisse)\n"
                "Yarın 23:00’da performans raporu gelecek."
            )

    logger.info(f"Bitti Ana:{len(ana)} %5:{len(y5)} Hacim:{len(hac)}")


# ============================================================
# ANA
# ============================================================
def main():
    send_telegram_msg(
        "🤖 <b>BİST BOTU AKTİF</b>\n"
        "⏰ Tarama: 09:50 | 10:10 | 17:45 | 23:00\n"
        "📰 Negatif haber: her <b>10 dakika</b>\n"
        "🔊 Acil haberde sesli uyarı + Telegram\n"
        "📋 23:00 → gece adayları + ertesi gün % performans\n"
        "🚀 Başlıyor..."
    )

    try:
        check_kap_news()
        check_negative_market_news()
        hedef = get_all_bist_tickers()
        scan_bist_stocks(hedef, f"İLK AÇILIŞ ({datetime.now(TZ).strftime('%H:%M')})")
        send_telegram_msg("✅ Açılış testi tamam. Saatler + 10 dk haber döngüsü aktif.")
    except Exception as e:
        send_telegram_msg(f"❌ Açılış hatası: {e}")

    while True:
        try:
            now = datetime.now(TZ)
            t = now.strftime("%H:%M")
            d = now.strftime("%Y-%m-%d")

            check_kap_news()
            check_negative_market_news()  # 10 dk throttle içeride

            key = f"{d}_{t}"
            if t in TARGET_SCAN_TIMES and key not in SCANNED_TIMES_TODAY:
                hedef = get_all_bist_tickers()
                scan_bist_stocks(hedef, t)
                SCANNED_TIMES_TODAY.add(key)
                if t == "23:00":
                    PROCESSED_KAP_LINKS.clear()
                    SCANNED_TIMES_TODAY.clear()

            time.sleep(25)
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Döngü: {e}")
            time.sleep(30)


if __name__ == "__main__":
    main()
