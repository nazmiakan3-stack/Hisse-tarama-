#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import threading
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, HTTPServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
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

# ==================== AYARLAR ====================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1734551753")

TZ = ZoneInfo("Europe/Istanbul")
TARGET_SCAN_TIMES = ["09:50", "10:10", "17:45", "23:00"]

TRACKING_FILE = "gunluk_takip.json"
PROCESSED_NEWS_FILE = "islenen_haberler.json"

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

SCANNED_TIMES_TODAY = set()


def send_telegram_msg(message: str, sound_alert: bool = False):
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print(f"\n[TELEGRAM MESAJI]:\n{message}\n")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "disable_notification": not sound_alert
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
    except:
        return "0"


def get_all_bist_tickers():
    try:
        url = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/HisseTeknikVeriler"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json().get("d", [])
            fetched = {item.get("code") for item in data if item.get("code") and len(item.get("code", "")) <= 5}
            filtered = sorted(list(fetched))
            if len(filtered) >= 300:
                return filtered
    except Exception as e:
        logger.warning(f"Canlı liste alınamadı: {e}")
    return sorted(list(set(FULL_BIST_LIST) | BIST_30_SET))


def check_important_market_news_background():
    processed_links = set()
    if os.path.exists(PROCESSED_NEWS_FILE):
        try:
            with open(PROCESSED_NEWS_FILE, "r", encoding="utf-8") as f:
                processed_links = set(json.load(f))
        except:
            pass

    while True:
        try:
            feed = feedparser.parse("https://www.kap.org.tr/tr/rss")
            for entry in feed.entries[:12]:
                link = getattr(entry, "link", "")
                if not link or link in processed_links:
                    continue

                title = entry.title or ""
                summary = getattr(entry, "summary", "") or ""
                text_lower = (title + " " + summary).lower()

                kritik_kelimeler = [
                    "faiz", "enflasyon", "tcmb", "fed", "kripto", "bitcoin", "btc",
                    "sermaye artırımı", "bedelsiz", "ortaklık", "ihale", "olağanüstü",
                    "spk", "yasak", "açığa satış", "temettü", "kar payı"
                ]

                if any(k in text_lower for k in kritik_kelimeler):
                    processed_links.add(link)
                    with open(PROCESSED_NEWS_FILE, "w", encoding="utf-8") as f:
                        json.dump(list(processed_links)[-250:], f)

                    alert_msg = (
                        f"🚨 <b>[KRİTİK PİYASA / HABER UYARISI]</b> 🚨\n\n"
                        f"📌 <b>Başlık:</b> {title}\n"
                        f"🔗 <a href='{link}'>Haber Detayı İçin Tıklayın</a>"
                    )
                    send_telegram_msg(alert_msg, sound_alert=True)
                    time.sleep(1.2)
        except Exception as e:
            logger.debug(f"Haber tarama hatası: {e}")

        time.sleep(600)


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
        except:
            pass

        close_5d_ago = float(df_daily["Close"].iloc[-6]) if len(df_daily) >= 6 else last_close
        change_5d = ((last_close - close_5d_ago) / close_5d_ago) * 100
        asiri_zarar_yok = change_5d > -12

        avg_vol_20 = df_daily["Volume"].iloc[-20:].mean()
        tahta_durumu = "⚠️ Sığ Tahta" if avg_vol_20 < 400_000 else "🟢 Likit Tahta"

        # Stratejiler
        strateji_a = (
            rsi_d < 30 and rsi_w < 32 and stoch_alimda and
            hacim_tl >= 20_000_000 and rvol >= 1.0 and change_pct > 0
        )
        strateji_b = (
            bb_destek and (pb_ratio is not None and pb_ratio < 1.5) and
            rvol_5 >= 1.2 and asiri_zarar_yok and hacim_tl >= 8_000_000 and change_pct > 0
        )

        yuzde_5_ustu = change_pct >= 5.0 and hacim_tl >= 5_000_000
        hacim_patlamasi = hacim_tl >= 20_000_000 and rvol >= 1.5

        if not (strateji_a or strateji_b or yuzde_5_ustu or hacim_patlamasi):
            return None

        yildiz = 3
        if rvol >= 2.0 or rvol_5 >= 2.0:
            yildiz += 1
        if bb_destek:
            yildiz += 1
        if pb_ratio and pb_ratio < 1.0:
            yildiz += 1
        yildizlar = "⭐" * min(yildiz, 5)

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


def scan_bist_stocks(symbol_list, scan_time: str):
    logger.info(f"Tarama başladı → {scan_time} | {len(symbol_list)} hisse")

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

    ana_liste.sort(key=lambda x: x["rvol"], reverse=True)
    yuzde5_liste.sort(key=lambda x: x["change_pct"], reverse=True)
    hacim_liste.sort(key=lambda x: x["hacim_tl_raw"], reverse=True)

    baslik_ek = "🌙 GECE BÜLTENİ" if scan_time == "23:00" else "GÜN İÇİ TARAMASI"
    tarih = datetime.now(TZ).strftime('%d.%m.%Y - %H:%M')

    # ========== 1. ANA LİSTE (DİP + BB + DÜŞÜK PD/DD) ==========
    if ana_liste:
        mesaj = f"🎯 <b>[DİP + BB + DÜŞÜK PD/DD AVCISI | {baslik_ek}]</b>\n📅 <i>{tarih}</i>\n\n"
        for item in ana_liste:
            strateji_adi = "Klasik Dip" if item["strateji_a"] else "BB Alt + Düşük PD/DD"
            hisse_str = (
                f"🔹 <b>#{item['symbol']}</b> | <b>{item['fiyat']} TL</b> (%+{item['change_pct']})\n"
                f"├ <b>Strateji:</b> {strateji_adi} {item['yildizlar']}\n"
                f"├ <b>Hacim:</b> {item['hacim_tl']} TL | RVOL: {item['rvol']}x\n"
                f"├ <b>RSI:</b> {item['rsi_d']} | Stoch: {item['stoch_k']} | {item['tahta_durumu']}\n"
            )
            if item.get("pb_ratio"):
                hisse_str += f"├ <b>PD/DD:</b> {item['pb_ratio']}\n"
            hisse_str += f"└ 🛑 <b>SL:</b> {item['sl']} TL | 🎯 <b>TP:</b> {item['tp']} TL\n\n"

            if len(mesaj) + len(hisse_str) > 3800:
                send_telegram_msg(mesaj)
                mesaj = ""
                time.sleep(1)
            mesaj += hisse_str

        if mesaj.strip():
            send_telegram_msg(mesaj)

    # ========== 2. 24 SAATLİK PERFORMANS RAPORU (ÖNCE ESKİ VERİYİ OKU) ==========
    if scan_time == "23:00" and os.path.exists(TRACKING_FILE):
        try:
            with open(TRACKING_FILE, "r", encoding="utf-8") as f:
                old_data = json.load(f)

            if old_data:
                report_msg = (
                    "📋 <b>24 SAATLİK PERFORMANS KARŞILAŞTIRMA RAPORU</b>\n"
                    "<i>(Dün 23:00 → Bugün 23:00)</i>\n\n"
                    "<code>Hisse | Fiyat | Hacim | Eski RVOL | % Değişim</code>\n"
                    "<code>------------------------------------------------</code>\n"
                )

                for sym, old_info in old_data.items():
                    try:
                        curr_ticker = yf.Ticker(f"{sym}.IS")
                        df_c = curr_ticker.history(period="5d", interval="1d", auto_adjust=True)
                        if df_c is not None and not df_c.empty:
                            curr_price = float(df_c["Close"].iloc[-1])
                            curr_vol = float(df_c["Volume"].iloc[-1]) * curr_price
                            curr_vol_str = format_compact_volume(curr_vol)

                            old_price = old_info.get("fiyat", 0)
                            old_rvol = old_info.get("rvol", 0)

                            change_24h = ((curr_price - old_price) / old_price * 100) if old_price > 0 else 0.0
                            sign = "+" if change_24h >= 0 else ""

                            report_msg += (
                                f"• <b>{sym}</b> | {curr_price:.2f} TL | {curr_vol_str} | "
                                f"{old_rvol}x | <b>{sign}{change_24h:.2f}%</b>\n"
                            )
                    except Exception as e:
                        logger.debug(f"{sym} 24s hesaplama hatası: {e}")

                send_telegram_msg(report_msg)
        except Exception as e:
            logger.error(f"24 saatlik rapor hatası: {e}")

    # ========== 3. YENİ GECE LİSTESİNİ KAYDET (RAPORDAN SONRA) ==========
    if scan_time == "23:00" and ana_liste:
        night_data = {
            item["symbol"]: {
                "fiyat": item["fiyat"],
                "hacim": item["hacim_tl"],
                "rvol": item["rvol"]
            }
            for item in ana_liste
        }
        try:
            with open(TRACKING_FILE, "w", encoding="utf-8") as f:
                json.dump(night_data, f, ensure_ascii=False, indent=4)
            logger.info(f"Gece takip listesi kaydedildi → {len(night_data)} hisse")
        except Exception as e:
            logger.error(f"Takip dosyası kayıt hatası: {e}")

    # ========== 4. %5 VE ÜZERİ YÜKSELENLER ==========
    if yuzde5_liste:
        mesaj = f"🚀 <b>[%5 VE ÜZERİ YÜKSELENLER | {baslik_ek}]</b>\n📅 <i>{tarih}</i>\n\n"
        for item in yuzde5_liste[:18]:
            mesaj += f"🔹 <b>#{item['symbol']}</b> | <b>{item['fiyat']} TL</b> (%+{item['change_pct']}) | Hacim: {item['hacim_tl']}\n"
            if len(mesaj) > 3800:
                send_telegram_msg(mesaj)
                mesaj = ""
                time.sleep(1)
        if mesaj.strip():
            send_telegram_msg(mesaj)

    # ========== 5. HACİM PATLAMASI ==========
    if hacim_liste:
        mesaj = f"💥 <b>[HACİM PATLAMASI | {baslik_ek}]</b>\n📅 <i>{tarih}</i>\n\n"
        for item in hacim_liste[:15]:
            mesaj += (
                f"🔹 <b>#{item['symbol']}</b> | <b>{item['fiyat']} TL</b> (%+{item['change_pct']})\n"
                f"├ Hacim: {item['hacim_tl']} TL | RVOL: {item['rvol']}x\n"
                f"└ RSI: {item['rsi_d']} | Stoch: {item['stoch_k']}\n\n"
            )
            if len(mesaj) > 3800:
                send_telegram_msg(mesaj)
                mesaj = ""
                time.sleep(1)
        if mesaj.strip():
            send_telegram_msg(mesaj)

    logger.info(
        f"Tarama bitti → Ana: {len(ana_liste)} | %5+: {len(yuzde5_liste)} | Hacim: {len(hacim_liste)}"
    )


def main():
    now = datetime.now(TZ)
    current_time_str = now.strftime("%H:%M")

    # Arka plan haber tarayıcısını başlat
    threading.Thread(target=check_important_market_news_background, daemon=True).start()

    send_telegram_msg(
        "🤖 <b>BİST BOTU - 24 SAATLİK TAKİP & SESLİ HABER SİSTEMİ AKTİF</b>\n"
        "• Gece 23:00 Kriterleri (Hacim, RSI, Stoch, Artıda Kapanış)\n"
        "• Ertesi gün 23:00'te % Değişim Raporu\n"
        "• 10 dk bir Akıllı Haber ve Sesli Uyarı Modülü\n"
        "• Hacim Patlaması + %5+ Yükselenler\n"
        "🚀 Sistem çalışıyor..."
    )

    try:
        hedef = get_all_bist_tickers()
        scan_bist_stocks(hedef, f"İLK AÇILIŞ TESTİ ({current_time_str})")
        send_telegram_msg("✅ Açılış testi tamamlandı!")
    except Exception as e:
        send_telegram_msg(f"❌ Açılış hatası: {e}")

    while True:
        try:
            now = datetime.now(TZ)
            loop_time = now.strftime("%H:%M")
            loop_date = now.strftime("%Y-%m-%d")
            scan_key = f"{loop_date}_{loop_time}"

            if loop_time in TARGET_SCAN_TIMES and scan_key not in SCANNED_TIMES_TODAY:
                hedef = get_all_bist_tickers()
                scan_bist_stocks(hedef, loop_time)
                SCANNED_TIMES_TODAY.add(scan_key)

                if loop_time == "23:00":
                    SCANNED_TIMES_TODAY.clear()

            time.sleep(25)
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Döngü hatası: {e}")
            time.sleep(30)


if __name__ == "__main__":
    main()
