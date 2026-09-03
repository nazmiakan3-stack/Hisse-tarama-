#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import requests
import feedparser
import yfinance as yf
from datetime import datetime, timezone, timedelta
from tradingview_ta import TA_Handler, Interval

# ============================================================
# TELEGRAM & PARAMETRELER
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1734551753")

BIST_30_SET = {
    "AKBNK", "ALARK", "ASELS", "ASTOR", "BIMAS", "BRSAN", "DOAS", "EKGYO",
    "ENKAI", "EREGL", "FROTO", "GARAN", "GUBRF", "HEKTS", "ISCTR", "KCHOL",
    "KONTR", "KOZAL", "KRDMD", "ODAS", "OYAKC", "PETKM", "PGSUS", "SAHOL",
    "SASA", "SISE", "TCELL", "THYAO", "TOASO", "TUPRS"
}

TARGET_SCAN_TIMES = {"09:50", "10:10", "17:45"}

# Teknik parametreler
RSI_DIP_LIMIT = 35
RSI_MOMENTUM_LIMIT = 50
CHANGE_MOMENTUM_LIMIT = 3.0          # %3 ve üzeri

# Temel analiz parametreleri
MAX_PRICE_TO_BOOK = 1.50             # Defter değeri düşük
MIN_PROFIT = 0                       # Zarar etmeyen

KAP_STAR_MAP = {
    "bedelsiz": ("⭐⭐⭐⭐⭐", "Yüksek Oranlı Bedelsiz / Sermaye Artırımı"),
    "yeni iş ilişkisi": ("⭐⭐⭐⭐⭐", "Yeni İş İlişkisi / Dev İhale"),
    "ortaklık": ("⭐⭐⭐⭐⭐", "Stratejik İş Ortaklığı / M&A"),
    "ihale": ("⭐⭐⭐⭐", "İhale Sözleşmesi / Dev Sipariş"),
    "pay alım": ("⭐⭐⭐⭐", "Şirket Pay Geri Alımı"),
    "pay geri alım": ("⭐⭐⭐⭐", "Şirket Pay Geri Alımı"),
}

FULL_BIST_LIST = [
    "AAVTUR", "ACSEL", "ADEL", "ADESE", "ADGYO", "AEFES", "AFYON", "AGESA", "AGHOL", "AGROT",
    "AHGAZ", "AKBNK", "AKCNS", "AKFGY", "AKFYE", "AKMGY", "AKSA", "AKSEN", "AKSGY", "AKSUE",
    "ALARK", "ALBRK", "ALCAR", "ALCTL", "ALFAS", "ALGYO", "ALKA", "ALKIM", "ALMAD", "ALTNY",
    "ALVES", "ANELE", "ANGEN", "ANHYT", "ANSGR", "ARASE", "ARCLK", "ARDYZ", "ARENA", "ARSAN",
    "ARTMS", "ARZUM", "ASELS", "ASGYO", "ASTOR", "ASUZU", "ATAGY", "ATAKP", "ATATP", "ATEKS",
    "ATSYH", "AVGYO", "AVHOL", "AVOD", "AYCES", "AYDEM", "AYEN", "AYGAZ", "AZTEK", "BAGFS",
    "BAKAB", "BALAT", "BANVT", "BARMA", "BATIS", "BEGYO", "BELEN", "BERA", "BEYAZ", "BFREN",
    "BIENP", "BIGCHE", "BIMAS", "BINBN", "BIOEN", "BIZIM", "BJKAS", "BLCYO", "BMTKS", "BNTAS",
    "BOBET", "BORLS", "BORSK", "BOSSA", "BRCVN", "BRISA", "BRKO", "BRKSN", "BRMEN", "BRSAN",
    "BRYAT", "BSOKE", "BSCVN", "BTCIM", "BUCIM", "BURCE", "BURVA", "BVSAN", "BYDNR", "CANTE",
    "CASA", "CAHIT", "CCOLA", "CELHA", "CEMAS", "CEMTS", "CMBTN", "CMENT", "CONSE", "COSMO",
    "CRDFA", "CRFSA", "CUSAN", "CVMEK", "CWENE", "DAGI", "DAPGM", "DARDL", "DGATE", "DGGYO",
    "DITAS", "DMRGD", "DMSAS", "DNISI", "DOAS", "DOBUR", "DOCTA", "DOGUB", "DOHOL", "DSIOTE",
    "DURDO", "DYOBY", "EDATA", "EDIP", "EGEEN", "EGEPO", "EGGUB", "EGPRO", "EGSER", "EKIZ",
    "EKGYO", "EKOS", "EKSUN", "ELITE", "EMKEL", "EMNIS", "ENERY", "ENKAI", "ENSRI", "EPLAS",
    "ERCB", "EREGL", "ERSU", "ESCAR", "ESCOM", "ESEN", "ETILR", "EUPWR", "EYGYO", "FADE",
    "FENER", "FLAP", "FMIZP", "FONET", "FORTE", "FORMT", "FRIGO", "FROTO", "FZLGY", "GARAN",
    "GARFA", "GEDIK", "GEDZA", "GENKE", "GENTS", "GEREL", "GESAN", "GIPTA", "GLBMD", "GLYHO",
    "GMTAS", "GOKNR", "GOLTS", "GOODY", "GOZDE", "GRSEL", "GRTRK", "GSDHO", "GSDDE", "GSRAY",
    "GUBRF", "GWIND", "GVTUR", "HALKB", "HATEK", "HATSN", "HDFGS", "HEDEF", "HEKTS", "HKTM",
    "HLGYO", "HOROZ", "HUBVC", "HUNER", "HURGZ", "ICBCT", "ICUGS", "IDEAS", "IDGYO", "IEYHO",
    "IHAAS", "IHEVA", "IHGZT", "IHLGM", "IHLAS", "INGRM", "INTEM", "INVEO", "INVES", "IPEKE",
    "ISATR", "ISBTR", "ISCTR", "ISDMR", "ISFIN", "ISGSY", "ISGYO", "ISKPL", "ISKUR", "ISMEN",
    "ISSEN", "ITEKS", "ITZRH", "IYZICO", "IZFAS", "IZINV", "IZMDC", "JANTS", "KAEFA", "KAPLM",
    "KAREL", "KARSN", "KARTN", "KATMR", "KAYSE", "KBORU", "KCAER", "KCHOL", "KENT", "KGYO",
    "KHOL", "KIMMR", "KLGYO", "KLMSN", "KLNMA", "KLRZO", "KLSER", "KLSYN", "KMCOR", "KNFRT",
    "KONKA", "KONTR", "KONYA", "KOTON", "KOZAL", "KOZAA", "KRDMD", "KRDMA", "KRDMB", "KRPLS",
    "KRSTL", "KRTEK", "KRVGD", "KSTUR", "KTLEV", "KTSKR", "KUTPO", "KUZEY", "LIDER", "LIDFA",
    "LINK", "LKMNH", "LMKDC", "LOGAN", "LOGO", "LUKSK", "MAALT", "MACKO", "MAGEN", "MAKIM",
    "MAKTK", "MANAS", "MARKA", "MAVI", "MEDTR", "MEGAP", "MEGMT", "MEPET", "MERCN", "MERIT",
    "MERKO", "METRO", "METUR", "MHRGY", "MIATK", "MIPAZ", "MMCAS", "MNDTR", "MOBTL", "MOGAN",
    "MPARK", "MRGYO", "MRSHL", "MSGYO", "MTRKS", "MTRYO", "MZHLD", "NATEN", "NETAS", "NIBAS",
    "NTHOL", "NUGYO", "NUHCM", "OBAMS", "OBASE", "ODAS", "OFCAD", "OFSYM", "ONCSM", "ORCA",
    "ORGE", "ORMA", "OSMEN", "OSTIM", "OTKAR", "OTTO", "OYAKC", "OYAYO", "OYLUM", "OYYAT",
    "OZKGY", "OZRDN", "OZSUB", "PAGYO", "PAMEL", "PAPIL", "PARSN", "PASEU", "PATEK", "PCILT",
    "PEKGY", "PENTN", "PENTA", "PETKM", "PETUN", "PGSUS", "PINAR", "PKENT", "PKART", "PLTUR",
    "PNLSN", "PNSUT", "POLHO", "POLTK", "PRDGS", "PRKAB", "PRKME", "PRZMA", "PSDTC", "PSGYO",
    "QUAGR", "RALYH", "RAYSG", "REEDR", "RGYAS", "RHEAG", "RISE", "RNPOL", "RODRG", "ROYAL",
    "RUBNS", "RYGYO", "RYSAS", "SAHOL", "SAMAT", "SANEL", "SANFM", "SANKO", "SARKY", "SASA",
    "SAYAS", "SDTTR", "SEGMN", "SEKFK", "SEKUR", "SELEC", "SELVA", "SEYKM", "SILVR", "SISE",
    "SKBNK", "SKTAS", "SMART", "SMRTG", "SMRVA", "SODSN", "SOKE", "SOKM", "SONME", "SRVGY",
    "SUMAS", "SUNTK", "SURGY", "SUWEN", "TABGD", "TARKM", "TATEN", "TATGD", "TAVHL", "TBORG",
    "TCELL", "TDGYO", "TEKTN", "TERA", "TETMT", "TEZOL", "TGSAS", "THYAO", "TIRE", "TKFEN",
    "TKNSA", "TLMAN", "TMPOL", "TMSN", "TNZTP", "TOASO", "TRGYO", "TRILC", "TSKB", "TSPOR",
    "TUCLK", "TUPRS", "TUREKS", "TURGG", "TURSG", "UFUK", "ULAS", "ULKER", "ULUFA", "ULUSE",
    "UNLU", "USAK", "VAKBN", "VAKFN", "VAKKO", "VAPOR", "VERUS", "VESBE", "VESTL", "VKFYO",
    "VKGYO", "YAPRK", "YATAS", "YAYLA", "YEOTK", "YGGYO", "YGYO", "YKBNK", "YNKGY", "YONGA",
    "YBTAS", "YUYAT", "YYLGD", "ZEDUR", "ZOREN", "ZRGYO"
]

# State
PROCESSED_KAP_LINKS = set()
SCANNED_TIMES_TODAY = set()
LAST_CLEAN_DATE = None
INITIAL_SCAN_DONE = False
EVENING_REPORT_SENT = False

DAILY_DIP_CANDIDATES = []
DAILY_MOMENTUM_CANDIDATES = []
DAILY_VALUE_CANDIDATES = []
DAILY_KAP_NEWS = []

TR_TZ = timezone(timedelta(hours=3))


def get_tr_now():
    return datetime.now(TR_TZ)


def send_telegram_msg(message: str):
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
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
        resp = requests.post(url, json=payload, timeout=12)
        if resp.status_code != 200:
            print(f"Telegram API hatası: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"Telegram gönderim hatası: {e}")


def get_all_bist_tickers() -> list:
    try:
        url = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/HisseTeknikVeriler"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(url, headers=headers, timeout=10)

        if res.status_code == 200:
            data = res.json().get("d", [])
            fetched = {item.get("code") for item in data if item.get("code") and len(item.get("code", "")) <= 5}
            filtered = sorted(list(fetched - BIST_30_SET))
            if len(filtered) >= 400:
                print(f"✅ Canlı veriden {len(filtered)} yan tahta çekildi.")
                return filtered
    except Exception as e:
        print(f"İş Yatırım API hatası: {e}")

    fallback = sorted(list(set(FULL_BIST_LIST) - BIST_30_SET))
    print(f"ℹ️ Yerel listeden {len(fallback)} yan tahta yüklendi.")
    return fallback


def get_dip_stars(rsi: float) -> str:
    if rsi <= 15:
        return "⭐⭐⭐⭐⭐ (Tarihi Dip)"
    elif rsi <= 20:
        return "⭐⭐⭐⭐ (Derin Dip)"
    elif rsi <= 25:
        return "⭐⭐⭐ (Güçlü Dip)"
    return "⭐⭐ (Kademeli Giriş)"


def get_momentum_stars(change: float) -> str:
    if change >= 8.0:
        return "⭐⭐⭐⭐⭐ (Tavana Yakın / Çok Güçlü)"
    elif change >= 5.0:
        return "⭐⭐⭐⭐ (Güçlü Yükseliş)"
    elif change >= 3.0:
        return "⭐⭐⭐ (Pozitif Momentum)"
    return "⭐⭐"


def analyze_tv_stock(symbol: str):
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


def get_fundamentals(symbol: str):
    """Yahoo Finance üzerinden temel verileri çeker"""
    try:
        ticker = yf.Ticker(f"{symbol}.IS")
        info = ticker.info

        pb = info.get("priceToBook")
        net_income = info.get("netIncomeToCommon")
        profit_margin = info.get("profitMargins")

        # Net kâr bilgisi yoksa profitMargins'e bak
        is_profitable = False
        if net_income is not None:
            is_profitable = net_income > 0
        elif profit_margin is not None:
            is_profitable = profit_margin > 0

        return {
            "price_to_book": pb,
            "is_profitable": is_profitable,
            "net_income": net_income
        }
    except Exception:
        return None


def check_kap_news(intensive=False):
    global PROCESSED_KAP_LINKS, DAILY_KAP_NEWS
    try:
        feed = feedparser.parse("https://www.kap.org.tr/tr/rss")

        for entry in feed.entries[:30]:
            link = getattr(entry, "link", None)
            if not link or link in PROCESSED_KAP_LINKS:
                continue

            title = getattr(entry, "title", "")
            summary = getattr(entry, "summary", "")
            content = (title + " " + summary).lower()

            for key, (stars, category) in KAP_STAR_MAP.items():
                if key in content:
                    PROCESSED_KAP_LINKS.add(link)
                    msg = (
                        f"🔥 <b>[YÜKSEK HABER DEĞERİ - KAP]</b>\n\n"
                        f"<b>Etki:</b> {stars}\n"
                        f"<b>Kategori:</b> {category}\n"
                        f"<b>Başlık:</b> {title}\n"
                        f"<b>Link:</b> <a href='{link}'>KAP Detayı</a>"
                    )
                    send_telegram_msg(msg)
                    DAILY_KAP_NEWS.append({
                        "title": title,
                        "stars": stars,
                        "category": category
                    })
                    break
    except Exception as e:
        print(f"KAP hatası: {e}")


def scan_bist_stocks(symbol_list: list, scan_time: str):
    print(f"[{get_tr_now().strftime('%H:%M:%S')}] {len(symbol_list)} hisse taranıyor ({scan_time})...")

    match_count = 0

    for symbol in symbol_list:
        data = analyze_tv_stock(symbol)
        if not data or data.get("rsi") is None or data.get("close") is None:
            continue

        price = data["close"]
        rsi = data["rsi"]
        change = data.get("change") or 0.0

        # 1. Dip Avcısı
        if rsi <= RSI_DIP_LIMIT:
            stars = get_dip_stars(rsi)
            msg = (
                f"🛡️ <b>[DİP AVCISI - {scan_time}]</b>\n\n"
                f"<b>Hisse:</b> #{symbol}\n"
                f"<b>Derece:</b> {stars}\n"
                f"<b>Fiyat:</b> {price:.2f} TL (%{change:+.2f})\n"
                f"<b>RSI:</b> {rsi:.1f}"
            )
            send_telegram_msg(msg)
            match_count += 1
            DAILY_DIP_CANDIDATES.append({"symbol": symbol, "rsi": rsi, "change": change, "price": price})

        # 2. Tavan / Momentum (gevşetilmiş)
        if rsi >= RSI_MOMENTUM_LIMIT and change >= CHANGE_MOMENTUM_LIMIT:
            stars = get_momentum_stars(change)
            msg = (
                f"🚀 <b>[TAVAN / MOMENTUM - {scan_time}]</b>\n\n"
                f"<b>Hisse:</b> #{symbol}\n"
                f"<b>Derece:</b> {stars}\n"
                f"<b>Fiyat:</b> {price:.2f} TL (%{change:+.2f})\n"
                f"<b>RSI:</b> {rsi:.1f}"
            )
            send_telegram_msg(msg)
            match_count += 1
            DAILY_MOMENTUM_CANDIDATES.append({"symbol": symbol, "rsi": rsi, "change": change, "price": price})

        time.sleep(0.06)

    print(f"[{get_tr_now().strftime('%H:%M:%S')}] Teknik tarama bitti. {match_count} sinyal.")


def scan_value_stocks(symbol_list: list, scan_time: str):
    """Defter değeri düşük + kârlı hisseleri tarar (daha yavaş)"""
    print(f"[{get_tr_now().strftime('%H:%M:%S')}] Değer taraması başlıyor ({len(symbol_list)} hisse)...")

    found = 0
    for i, symbol in enumerate(symbol_list):
        fund = get_fundamentals(symbol)
        if not fund:
            continue

        pb = fund.get("price_to_book")
        profitable = fund.get("is_profitable", False)

        if pb is not None and pb <= MAX_PRICE_TO_BOOK and profitable:
            msg = (
                f"💎 <b>[DEĞER AVCISI - {scan_time}]</b>\n\n"
                f"<b>Hisse:</b> #{symbol}\n"
                f"<b>Fiyat/Defter:</b> {pb:.2f}\n"
                f"<b>Durum:</b> Kârlı ✅\n"
                f"<b>Kriter:</b> Düşük PD/DD + Zarar Etmiyor"
            )
            send_telegram_msg(msg)
            found += 1
            DAILY_VALUE_CANDIDATES.append({"symbol": symbol, "pb": pb})

        # Her 15 hissede bir kısa bekle (rate limit)
        if i % 15 == 0:
            time.sleep(1.2)
        else:
            time.sleep(0.25)

    print(f"[{get_tr_now().strftime('%H:%M:%S')}] Değer taraması bitti. {found} hisse bulundu.")


def send_evening_report():
    global EVENING_REPORT_SENT
    if EVENING_REPORT_SENT:
        return

    parts = ["🌙 <b>GECE RAPORU - YARIN İÇİN ADAYLAR</b>\n"]
    parts.append(f"{get_tr_now().strftime('%d.%m.%Y %H:%M')}\n")

    if DAILY_MOMENTUM_CANDIDATES:
        parts.append("\n🚀 <b>Güçlü Momentum / Tavan Adayları:</b>")
        seen = set()
        for item in sorted(DAILY_MOMENTUM_CANDIDATES, key=lambda x: x["change"], reverse=True):
            if item["symbol"] not in seen:
                seen.add(item["symbol"])
                parts.append(f"• #{item['symbol']} | %{item['change']:+.2f} | RSI {item['rsi']:.1f}")
    else:
        parts.append("\n🚀 Bugün güçlü momentum adayı yok.")

    if DAILY_VALUE_CANDIDATES:
        parts.append("\n\n💎 <b>Düşük Defter Değeri + Kârlı:</b>")
        seen = set()
        for item in DAILY_VALUE_CANDIDATES:
            if item["symbol"] not in seen:
                seen.add(item["symbol"])
                parts.append(f"• #{item['symbol']} | PD/DD: {item['pb']:.2f}")
    else:
        parts.append("\n\n💎 Bugün değer adayı bulunamadı.")

    if DAILY_DIP_CANDIDATES:
        parts.append("\n\n🛡️ <b>Dip Bölgesi:</b>")
        seen = set()
        for item in sorted(DAILY_DIP_CANDIDATES, key=lambda x: x["rsi"]):
            if item["symbol"] not in seen:
                seen.add(item["symbol"])
                parts.append(f"• #{item['symbol']} | RSI {item['rsi']:.1f}")

    if DAILY_KAP_NEWS:
        parts.append("\n\n🔥 <b>Önemli KAP Haberleri:</b>")
        for n in DAILY_KAP_NEWS[-6:]:
            parts.append(f"• {n['stars']} {n['title'][:55]}...")

    parts.append("\n\n📌 <i>Yarın sabah için referans listesidir.</i>")
    send_telegram_msg("\n".join(parts))
    EVENING_REPORT_SENT = True


def clean_daily_state():
    global SCANNED_TIMES_TODAY, LAST_CLEAN_DATE, INITIAL_SCAN_DONE
    global EVENING_REPORT_SENT, DAILY_DIP_CANDIDATES, DAILY_MOMENTUM_CANDIDATES
    global DAILY_VALUE_CANDIDATES, DAILY_KAP_NEWS

    today = get_tr_now().strftime("%Y-%m-%d")
    if LAST_CLEAN_DATE != today:
        SCANNED_TIMES_TODAY.clear()
        INITIAL_SCAN_DONE = False
        EVENING_REPORT_SENT = False
        DAILY_DIP_CANDIDATES.clear()
        DAILY_MOMENTUM_CANDIDATES.clear()
        DAILY_VALUE_CANDIDATES.clear()
        DAILY_KAP_NEWS.clear()
        LAST_CLEAN_DATE = today
        print(f"🧹 State temizlendi: {today}")


def main():
    global INITIAL_SCAN_DONE

    send_telegram_msg(
        "🤖 <b>BİST BOT V11 AKTİF!</b>\n\n"
        "⏰ Tarama: Açılış + 09:50 + 10:10 + 17:45\n"
        "🚀 Tavan Filtresi: RSI≥50 + Değişim ≥%3\n"
        "💎 Değer Filtresi: PD/DD ≤1.50 + Kârlı\n"
        "🌙 23:00 Gece Özeti"
    )

    while True:
        try:
            clean_daily_state()
            now = get_tr_now()
            current_time = now.strftime("%H:%M")
            current_date = now.strftime("%Y-%m-%d")
            current_hour = now.hour

            intensive = 17 <= current_hour < 22
            check_kap_news(intensive=intensive)

            # İlk açılış taraması
            if not INITIAL_SCAN_DONE:
                symbols = get_all_bist_tickers()
                send_telegram_msg(f"🚀 <b>İLK AÇILIŞ TARAMASI</b>\n{len(symbols)} hisse taranıyor...")
                scan_bist_stocks(symbols, "İlk Açılış")
                # Değer taraması daha yavaş olduğu için sadece ilk açılış ve 17:45'te yapıyoruz
                scan_value_stocks(symbols, "İlk Açılış")
                INITIAL_SCAN_DONE = True
                send_telegram_msg("✅ <b>İLK AÇILIŞ TARAMASI BİTTİ</b>")

            # Saatlik taramalar
            scan_key = f"{current_date}_{current_time}"
            if current_time in TARGET_SCAN_TIMES and scan_key not in SCANNED_TIMES_TODAY:
                symbols = get_all_bist_tickers()
                send_telegram_msg(f"⏰ <b>{current_time} TARAMASI BAŞLADI</b>")
                scan_bist_stocks(symbols, current_time)

                if current_time == "17:45":
                    scan_value_stocks(symbols, current_time)

                SCANNED_TIMES_TODAY.add(scan_key)
                send_telegram_msg(f"✅ <b>{current_time} TARAMASI BİTTİ</b>")

            # 23:00 raporu
            if current_time == "23:00" and not EVENING_REPORT_SENT:
                send_evening_report()

            time.sleep(20 if intensive else 30)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Hata: {e}")
            time.sleep(30)


if __name__ == "__main__":
    main()
