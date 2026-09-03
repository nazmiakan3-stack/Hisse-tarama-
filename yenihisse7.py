#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import requests
import feedparser
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

# Normal tarama saatleri
TARGET_SCAN_TIMES = {"09:50", "10:10", "17:45"}

RSI_DIP_LIMIT = 30
RSI_MOMENTUM_LIMIT = 50
CHANGE_MOMENTUM_LIMIT = 2.5

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

# Gün içinde bulunan adaylar (23:00 raporu için)
DAILY_DIP_CANDIDATES = []
DAILY_MOMENTUM_CANDIDATES = []
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
        return "⭐⭐⭐⭐⭐ (Tarihi Dip / Aşırı Satım)"
    elif rsi <= 20:
        return "⭐⭐⭐⭐ (Derin Dip Bölgesi)"
    elif rsi <= 25:
        return "⭐⭐⭐ (Güçlü Dip Seviyesi)"
    return "⭐⭐ (Kademeli Giriş Bölgesi)"


def get_momentum_stars(rsi: float, change: float, rec: str) -> str:
    if rec == "STRONG_BUY" and change >= 4.0 and rsi >= 65:
        return "⭐⭐⭐⭐⭐ (Yüksek Tavan / Hacim Potansiyeli)"
    elif rec == "STRONG_BUY" and change >= 2.5:
        return "⭐⭐⭐⭐ (Güçlü Momentum Sinyali)"
    return "⭐⭐⭐ (Pozitif Yükseliş Trendi)"


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


def check_kap_news(intensive=False):
    """intensive=True → 17:45-22:00 arası daha sık kontrol"""
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
                        f"🔥 <b>[YÜKSEK HABER DEĞERİ - KAP İSTİHBARATI]</b>\n\n"
                        f"<b>Etki Gücü:</b> {stars}\n"
                        f"<b>Kategori:</b> {category}\n"
                        f"<b>Başlık:</b> {title}\n"
                        f"<b>Link:</b> <a href='{link}'>KAP Bildirim Detayı</a>"
                    )
                    send_telegram_msg(msg)

                    # 23:00 raporu için kaydet
                    DAILY_KAP_NEWS.append({
                        "title": title,
                        "stars": stars,
                        "category": category,
                        "link": link
                    })
                    break
    except Exception as e:
        print(f"KAP kontrol hatası: {e}")


def scan_bist_stocks(symbol_list: list, scan_time: str, is_evening=False):
    print(f"[{get_tr_now().strftime('%H:%M:%S')}] {len(symbol_list)} hisse için {scan_time} taraması başladı...")

    match_count = 0
    local_dip = []
    local_momentum = []

    for symbol in symbol_list:
        data = analyze_tv_stock(symbol)
        if not data or data.get("rsi") is None or data.get("close") is None:
            continue

        price = data["close"]
        rsi = data["rsi"]
        change = data.get("change") or 0.0
        rec = data.get("recommendation") or "N/A"

        # Dip Avcısı
        if rsi <= RSI_DIP_LIMIT:
            stars = get_dip_stars(rsi)
            msg = (
                f"🛡️ <b>[DİP & DEĞER AVCISI - {scan_time}]</b>\n\n"
                f"<b>Hisse:</b> #{symbol}\n"
                f"<b>Derece:</b> {stars}\n"
                f"<b>Fiyat / Değişim:</b> {price:.2f} TL (%{change:+.2f})\n"
                f"<b>RSI (14):</b> {rsi:.1f}\n"
                f"<b>TV Sinyali:</b> {rec}\n"
                f"<b>Strateji:</b> Kademeli Dip Alımı"
            )
            send_telegram_msg(msg)
            match_count += 1
            local_dip.append({"symbol": symbol, "rsi": rsi, "change": change, "price": price, "stars": stars})

        # Momentum / Tavan Adayı
        if (rsi >= RSI_MOMENTUM_LIMIT and
                change >= CHANGE_MOMENTUM_LIMIT and
                rec in ("STRONG_BUY", "BUY")):
            stars = get_momentum_stars(rsi, change, rec)
            msg = (
                f"🚀 <b>[GÜNLÜK TAVAN ADAYI - {scan_time}]</b>\n\n"
                f"<b>Hisse:</b> #{symbol}\n"
                f"<b>Derece:</b> {stars}\n"
                f"<b>Fiyat / Değişim:</b> {price:.2f} TL (%{change:+.2f})\n"
                f"<b>RSI (14):</b> {rsi:.1f}\n"
                f"<b>TV Sinyali:</b> {rec} 🔥\n"
                f"<b>Strateji:</b> Günlük Momentum / Trade"
            )
            send_telegram_msg(msg)
            match_count += 1
            local_momentum.append({"symbol": symbol, "rsi": rsi, "change": change, "price": price, "stars": stars, "rec": rec})

        time.sleep(0.07)

    # Günlük listeye ekle
    DAILY_DIP_CANDIDATES.extend(local_dip)
    DAILY_MOMENTUM_CANDIDATES.extend(local_momentum)

    print(f"[{get_tr_now().strftime('%H:%M:%S')}] {scan_time} taraması bitti. {match_count} fırsat bildirildi.")


def send_evening_report():
    """23:00'da yarın için tavan adayları özeti"""
    global EVENING_REPORT_SENT

    if EVENING_REPORT_SENT:
        return

    msg_parts = ["🌙 <b>GECE RAPORU - YARIN TAVAN POTANSİYELİ</b>\n"]
    msg_parts.append(f"Tarih: {get_tr_now().strftime('%d.%m.%Y %H:%M')}\n")

    # Momentum adayları
    if DAILY_MOMENTUM_CANDIDATES:
        msg_parts.append("\n🚀 <b>Güçlü Momentum / Tavan Adayları:</b>")
        # Tekrarları temizle
        seen = set()
        for item in sorted(DAILY_MOMENTUM_CANDIDATES, key=lambda x: x["change"], reverse=True):
            if item["symbol"] not in seen:
                seen.add(item["symbol"])
                msg_parts.append(
                    f"• #{item['symbol']} | %{item['change']:+.2f} | RSI:{item['rsi']:.1f} | {item['stars']}"
                )
    else:
        msg_parts.append("\n🚀 Bugün güçlü momentum adayı bulunamadı.")

    # Dip adayları
    if DAILY_DIP_CANDIDATES:
        msg_parts.append("\n\n🛡️ <b>Dip Bölgesindeki Hisseler:</b>")
        seen = set()
        for item in sorted(DAILY_DIP_CANDIDATES, key=lambda x: x["rsi"]):
            if item["symbol"] not in seen:
                seen.add(item["symbol"])
                msg_parts.append(
                    f"• #{item['symbol']} | RSI:{item['rsi']:.1f} | %{item['change']:+.2f}"
                )
    else:
        msg_parts.append("\n\n🛡️ Bugün dip adayı bulunamadı.")

    # KAP haberleri
    if DAILY_KAP_NEWS:
        msg_parts.append("\n\n🔥 <b>Bugünün Yüksek Değerli KAP Haberleri:</b>")
        for news in DAILY_KAP_NEWS[-8:]:  # Son 8 haber
            msg_parts.append(f"• {news['stars']} {news['title'][:60]}...")
    else:
        msg_parts.append("\n\n🔥 Bugün yüksek değerli KAP haberi yakalanmadı.")

    msg_parts.append("\n\n📌 <i>Bu liste yarın sabah tavan avı için referans niteliğindedir.</i>")

    full_msg = "\n".join(msg_parts)
    send_telegram_msg(full_msg)
    EVENING_REPORT_SENT = True
    print("🌙 23:00 Gece raporu gönderildi.")


def clean_daily_state():
    global SCANNED_TIMES_TODAY, LAST_CLEAN_DATE, INITIAL_SCAN_DONE
    global EVENING_REPORT_SENT, DAILY_DIP_CANDIDATES, DAILY_MOMENTUM_CANDIDATES, DAILY_KAP_NEWS

    today = get_tr_now().strftime("%Y-%m-%d")
    if LAST_CLEAN_DATE != today:
        SCANNED_TIMES_TODAY.clear()
        INITIAL_SCAN_DONE = False
        EVENING_REPORT_SENT = False
        DAILY_DIP_CANDIDATES.clear()
        DAILY_MOMENTUM_CANDIDATES.clear()
        DAILY_KAP_NEWS.clear()
        LAST_CLEAN_DATE = today
        print(f"🧹 Günlük state temizlendi: {today}")


def main():
    global INITIAL_SCAN_DONE

    send_telegram_msg(
        "🤖 <b>TRADINGVIEW 470 YAN TAHTA BİST BOTU V10 AKTİF!</b>\n\n"
        "⏰ Tarama Saatleri:\n"
        "• Bot açılır açılmaz\n"
        "• 09:50\n"
        "• 10:10\n"
        "• 17:45\n\n"
        "🌙 23:00 → Yarın tavan adayları özeti\n"
        "🔥 KAP: 17:45-22:00 arası yoğun takip"
    )

    while True:
        try:
            clean_daily_state()
            now = get_tr_now()
            current_time = now.strftime("%H:%M")
            current_date = now.strftime("%Y-%m-%d")
            current_hour = now.hour

            # --- KAP Kontrolü ---
            # 17:45 - 22:00 arası daha sık (her döngüde)
            intensive = 17 <= current_hour < 22
            check_kap_news(intensive=intensive)

            # --- İlk açılış taraması ---
            if not INITIAL_SCAN_DONE:
                symbols = get_all_bist_tickers()
                send_telegram_msg(f"🚀 <b>[İLK AÇILIŞ TARAMASI BAŞLADI]</b>\nToplam {len(symbols)} yan tahta taranıyor...")
                scan_bist_stocks(symbols, "İlk Açılış")
                INITIAL_SCAN_DONE = True
                send_telegram_msg("✅ <b>[İLK AÇILIŞ TARAMASI TAMAMLANDI]</b>")

            # --- Saatlik taramalar ---
            scan_key = f"{current_date}_{current_time}"
            if current_time in TARGET_SCAN_TIMES and scan_key not in SCANNED_TIMES_TODAY:
                symbols = get_all_bist_tickers()
                send_telegram_msg(
                    f"⏰ <b>[{current_time} SEANS TARAMASI BAŞLADI]</b>\n"
                    f"Toplam {len(symbols)} yan tahta taranıyor..."
                )
                is_evening = current_time == "17:45"
                scan_bist_stocks(symbols, current_time, is_evening=is_evening)
                SCANNED_TIMES_TODAY.add(scan_key)
                send_telegram_msg(f"✅ <b>[{current_time} SEANS TARAMASI TAMAMLANDI]</b>")

            # --- 23:00 Gece Raporu ---
            if current_time == "23:00" and not EVENING_REPORT_SENT:
                send_evening_report()

            # Döngü süresi
            if intensive:
                time.sleep(20)   # 17:45-22:00 arası daha sık
            else:
                time.sleep(30)

        except KeyboardInterrupt:
            print("Bot manuel olarak durduruldu.")
            break
        except Exception as e:
            print(f"Ana döngü hatası: {e}")
            time.sleep(30)


if __name__ == "__main__":
    main()
