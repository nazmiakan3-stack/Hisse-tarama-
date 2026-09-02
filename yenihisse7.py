#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import threading
import time
import feedparser
import requests
from tradingview_ta import Interval, TA_Handler


# ============================================================
# RENDER & UPTIMEROBOT İÇİN DAHİLİ HTTP SUNUCUSU
# ============================================================
class HealthCheckHandler(BaseHTTPRequestHandler):

  def do_GET(self):
    self.send_response(200)
    self.end_headers()
    self.wfile.write(b"Bot is alive!")

  # UptimeRobot'un 501 (Not Implemented) hatası almasını önleyen HEAD yanıtı:
  def do_HEAD(self):
    self.send_response(200)
    self.end_headers()

  def log_message(self, format, *args):
    return  # Konsol loglarını kirletmemek için bastırıyoruz


def start_health_check_server():
  port = int(os.environ.get("PORT", 10000))
  server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
  server.serve_forever()


# Web sunucusunu arka plan izleğinde (thread) başlat
threading.Thread(target=start_health_check_server, daemon=True).start()

# ============================================================
# TELEGRAM BİLGİLERİ VE HESAP PARAMETRELERİ
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1734551753")

# BİST 30 Muafiyet Listesi (Ağır tahtalar taranmaz)
BIST_30_SET = {
    "AKBNK",
    "ALARK",
    "ASELS",
    "ASTOR",
    "BIMAS",
    "BRSAN",
    "DOAS",
    "EKGYO",
    "ENKAI",
    "EREGL",
    "FROTO",
    "GARAN",
    "GUBRF",
    "HEKTS",
    "ISCTR",
    "KCHOL",
    "KONTR",
    "KOZAL",
    "KRDMD",
    "ODAS",
    "OYAKC",
    "PETKM",
    "PGSUS",
    "SAHOL",
    "SASA",
    "SISE",
    "TCELL",
    "THYAO",
    "TOASO",
    "TUPRS",
}

# Özel Tarama Saatleri (Günde 2 Defa)
TARGET_SCAN_TIMES = ["09:50", "10:10"]

# Strateji Parametreleri
RSI_DIP_LIMIT = 30  # Dip Avcısı max RSI (14)
RSI_MOMENTUM_LIMIT = 50  # Günlük Tavan Avcısı min RSI (14)
CHANGE_MOMENTUM_LIMIT = 2.5  # Minimum günlük % değişim

# Yalnızca YÜKSEK HABER DEĞERİ (4 ve 5 Yıldızlı) Olan KAP Kategorileri
KAP_STAR_MAP = {
    "bedelsiz": ("⭐⭐⭐⭐⭐", "Yüksek Oranlı Bedelsiz / Sermaye Artırımı"),
    "yeni iş ilişkisi": ("⭐⭐⭐⭐⭐", "Yeni İş İlişkisi / Dev İhale"),
    "ortaklık": ("⭐⭐⭐⭐⭐", "Stratejik İş Ortaklığı / M&A"),
    "ihale": ("⭐⭐⭐⭐", "İhale Sözleşmesi / Dev Sipariş"),
    "pay alım": ("⭐⭐⭐⭐", "Şirket Pay Geri Alımı"),
}

# BİST ~500 Hisse Tam Listesi (İş Yatırım API Çökse Bile 470 Yan Tahtayı Garanti Eder)
FULL_BIST_LIST = [
    "AAVTUR",
    "ACSEL",
    "ADEL",
    "ADESE",
    "ADGYO",
    "AEFES",
    "AFYON",
    "AGESA",
    "AGHOL",
    "AGROT",
    "AHGAZ",
    "AKBNK",
    "AKCNS",
    "AKFGY",
    "AKFYE",
    "AKMGY",
    "AKSA",
    "AKSEN",
    "AKSGY",
    "AKSUE",
    "ALARK",
    "ALBRK",
    "ALCAR",
    "ALCTL",
    "ALFAS",
    "ALGYO",
    "ALKA",
    "ALKIM",
    "ALMAD",
    "ALTNY",
    "ALVES",
    "ANELE",
    "ANGEN",
    "ANHYT",
    "ANSGR",
    "ARASE",
    "ARCLK",
    "ARDYZ",
    "ARENA",
    "ARSAN",
    "ARTMS",
    "ARZUM",
    "ASELS",
    "ASGYO",
    "ASTOR",
    "ASUZU",
    "ATAGY",
    "ATAKP",
    "ATATP",
    "ATEKS",
    "ATSYH",
    "AVGYO",
    "AVHOL",
    "AVOD",
    "AYCES",
    "AYDEM",
    "AYEN",
    "AYGAZ",
    "AZTEK",
    "BAGFS",
    "BAKAB",
    "BALAT",
    "BANVT",
    "BARMA",
    "BATIS",
    "BTCIM",
    "BYDNR",
    "BEGYO",
    "BELEN",
    "BERA",
    "BEYAZ",
    "BFREN",
    "BIENP",
    "BIGCHE",
    "BIMAS",
    "BINBN",
    "BIOEN",
    "BIZIM",
    "BJKAS",
    "BLCYO",
    "BMTKS",
    "BNTAS",
    "BOBET",
    "BORLS",
    "BORSK",
    "BOSSA",
    "BRCVN",
    "BRISA",
    "BRKO",
    "BRKSN",
    "BRMEN",
    "BRSAN",
    "BRYAT",
    "BSOKE",
    "BSCVN",
    "BTCIM",
    "BUCIM",
    "BURCE",
    "BURVA",
    "BVSAN",
    "BYDNR",
    "CANTE",
    "CASA",
    "CAHIT",
    "CCOLA",
    "CELHA",
    "CEMAS",
    "CEMTS",
    "CMBTN",
    "CMENT",
    "CONSE",
    "COSMO",
    "CRDFA",
    "CRFSA",
    "CUSAN",
    "CVMEK",
    "CWENE",
    "DAGI",
    "DAPGM",
    "DARDL",
    "DGATE",
    "DGGYO",
    "DITAS",
    "DMRGD",
    "DMSAS",
    "DNISI",
    "DOAS",
    "DOBUR",
    "DOCTA",
    "DOGUB",
    "DOHOL",
    "DSIOTE",
    "DURDO",
    "DYOBY",
    "EDATA",
    "EDIP",
    "EGEEN",
    "EGEPO",
    "EGGUB",
    "EGPRO",
    "EGSER",
    "EKIZ",
    "EKGYO",
    "EKOS",
    "EKSUN",
    "ELITE",
    "EMKEL",
    "EMNIS",
    "ENERY",
    "ENKAI",
    "ENSRI",
    "EPLAS",
    "ERCB",
    "EREGL",
    "ERSU",
    "ESCAR",
    "ESCOM",
    "ESEN",
    "ETILR",
    "EUPWR",
    "EYGYO",
    "FADE",
    "FENER",
    "FLAP",
    "FMIZP",
    "FONET",
    "FORTE",
    "FORMT",
    "FRIGO",
    "FROTO",
    "FZLGY",
    "GARAN",
    "GARFA",
    "GEDIK",
    "GEDZA",
    "GENKE",
    "GENTS",
    "GEREL",
    "GESAN",
    "GIPTA",
    "GLBMD",
    "GLYHO",
    "GMTAS",
    "GOKNR",
    "GOLTS",
    "GOODY",
    "GOZDE",
    "GRSEL",
    "GRTRK",
    "GSDHO",
    "GSDDE",
    "GSRAY",
    "GUBRF",
    "GWIND",
    "GVTUR",
    "HALKB",
    "HATEK",
    "HATSN",
    "HDFGS",
    "HEDEF",
    "HEKTS",
    "HKTM",
    "HLGYO",
    "HOROZ",
    "HUBVC",
    "HUNER",
    "HURGZ",
    "ICBCT",
    "ICUGS",
    "IDEAS",
    "IDGYO",
    "IEYHO",
    "IHAAS",
    "IHEVA",
    "IHGZT",
    "IHLGM",
    "IHLAS",
    "INGRM",
    "INTEM",
    "INVEO",
    "INVES",
    "IPEKE",
    "ISATR",
    "ISBTR",
    "ISCTR",
    "ISDMR",
    "ISFIN",
    "ISGSY",
    "ISGYO",
    "ISKPL",
    "ISKUR",
    "ISMEN",
    "ISSEN",
    "ITEKS",
    "ITZRH",
    "IYZICO",
    "IZFAS",
    "IZINV",
    "IZMDC",
    "JANTS",
    "KAEFA",
    "KAPLM",
    "KAREL",
    "KARSN",
    "KARTN",
    "KATMR",
    "KAYSE",
    "KBORU",
    "KCAER",
    "KCHOL",
    "KENT",
    "KRVGD",
    "KGYO",
    "KHOL",
    "KIMMR",
    "KLGYO",
    "KLMSN",
    "KLNMA",
    "KLRZO",
    "KLSER",
    "KLSYN",
    "KMCOR",
    "KNFRT",
    "KONKA",
    "KONTR",
    "KONYA",
    "KOTON",
    "KOZAL",
    "KOZAA",
    "KRDMD",
    "KRDMA",
    "KRDMB",
    "KRPLS",
    "KRSTL",
    "KRTEK",
    "KRVGD",
    "KSTUR",
    "KTLEV",
    "KTSKR",
    "KUTPO",
    "KUZEY",
    "LIDER",
    "LIDFA",
    "LINK",
    "LKMNH",
    "LMKDC",
    "LOGAN",
    "LOGO",
    "LUKSK",
    "MAALT",
    "MACKO",
    "MAGEN",
    "MAKIM",
    "MAKTK",
    "MANAS",
    "MARKA",
    "MAVI",
    "MEDTR",
    "MEGAP",
    "MEGMT",
    "MEPET",
    "MERCN",
    "MERIT",
    "MERKO",
    "METRO",
    "METUR",
    "MHRGY",
    "MIATK",
    "MIPAZ",
    "MMCAS",
    "MNDTR",
    "MOBTL",
    "MOGAN",
    "MPARK",
    "MRGYO",
    "MRSHL",
    "MSGYO",
    "MTRKS",
    "MTRYO",
    "MZHLD",
    "NATEN",
    "NETAS",
    "NIBAS",
    "NTHOL",
    "NUGYO",
    "NUHCM",
    "OBAMS",
    "OBASE",
    "ODAS",
    "OFCAD",
    "OFSYM",
    "ONCSM",
    "ORCA",
    "ORGE",
    "ORMA",
    "OSMEN",
    "OSTIM",
    "OTKAR",
    "OTTO",
    "OYAKC",
    "OYAYO",
    "OYLUM",
    "OYYAT",
    "OZKGY",
    "OZRDN",
    "OZSUB",
    "PAGYO",
    "PAMEL",
    "PAPIL",
    "PARSN",
    "PASEU",
    "PATEK",
    "PCILT",
    "PEKGY",
    "PENTN",
    "PENTA",
    "PETKM",
    "PETUN",
    "PGSUS",
    "PINAR",
    "PKENT",
    "PKART",
    "PLTUR",
    "PNLSN",
    "PNSUT",
    "POLHO",
    "POLTK",
    "PRDGS",
    "PRKAB",
    "PRKME",
    "PRZMA",
    "PSDTC",
    "PSGYO",
    "QUAGR",
    "RALYH",
    "RAYSG",
    "REEDR",
    "RGYAS",
    "RHEAG",
    "RISE",
    "RNPOL",
    "RODRG",
    "ROYAL",
    "RUBNS",
    "RYGYO",
    "RYSAS",
    "SAHOL",
    "SAMAT",
    "SANEL",
    "SANFM",
    "SANKO",
    "SARKY",
    "SASA",
    "SAYAS",
    "SDTTR",
    "SEGMN",
    "SEKFK",
    "SEKUR",
    "SELEC",
    "SELVA",
    "SEYKM",
    "SILVR",
    "SISE",
    "SKBNK",
    "SKTAS",
    "SMART",
    "SMRTG",
    "SMRVA",
    "SODSN",
    "SOKE",
    "SOKM",
    "SONME",
    "SRVGY",
    "SUMAS",
    "SUNTK",
    "SURGY",
    "SUWEN",
    "TABGD",
    "TARKM",
    "TATEN",
    "TATGD",
    "TAVHL",
    "TBORG",
    "TCELL",
    "TDGYO",
    "TEKTN",
    "TERA",
    "TETMT",
    "TEZOL",
    "TGSAS",
    "THYAO",
    "TIRE",
    "TKFEN",
    "TKNSA",
    "TLMAN",
    "TMPOL",
    "TMSN",
    "TNZTP",
    "TOASO",
    "TRGYO",
    "TRILC",
    "TSKB",
    "TSPOR",
    "TUCLK",
    "TUPRS",
    "TUREKS",
    "TURGG",
    "TURSG",
    "UFUK",
    "ULAS",
    "ULKER",
    "ULUFA",
    "ULUSE",
    "UNLU",
    "USAK",
    "VAKBN",
    "VAKFN",
    "VAKKO",
    "VAPOR",
    "VERUS",
    "VESBE",
    "VESTL",
    "VKFYO",
    "VKGYO",
    "YAPRK",
    "YATAS",
    "YAYLA",
    "YEOTK",
    "YGGYO",
    "YGYO",
    "YKBNK",
    "YNKGY",
    "YONGA",
    "YBTAS",
    "YUYAT",
    "YYLGD",
    "ZEDUR",
    "ZOREN",
    "ZRGYO",
]

PROCESSED_KAP_LINKS = set()
SCANNED_TIMES_TODAY = set()


# ============================================================
# YARDIMCI FONKSİYONLAR & YILDIZ HESAPLAYICILAR
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
  except Exception as e:
    print(f"Telegram Gönderim Hatası: {e}")


def get_all_bist_tickers():
  """BİST'teki tüm hisseleri çeker ve tam olarak ~470 Yan Tahtayı garanti eder."""
  try:
    url = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/HisseTeknikVeriler"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    res = requests.get(url, headers=headers, timeout=8)

    if res.status_code == 200:
      data = res.json().get("d", [])
      fetched = {
          item.get("code")
          for item in data
          if item.get("code") and len(item.get("code")) <= 5
      }
      filtered = sorted(list(fetched - BIST_30_SET))
      if len(filtered) >= 400:
        print(f"✅ Canlı veriden {len(filtered)} yan tahta çekildi.")
        return filtered
  except Exception:
    pass

  # Canlı bağlantı kesilse dahi ~470 yan tahta tam kadro taranır
  fallback_yan_tahta = sorted(list(set(FULL_BIST_LIST) - BIST_30_SET))
  print(f"ℹ️ Yerel veritabanından {len(fallback_yan_tahta)} yan tahta yüklendi.")
  return fallback_yan_tahta


def get_dip_stars(rsi):
  if rsi <= 15:
    return "⭐⭐⭐⭐⭐ (Tarihi Dip / Aşırı Satım)"
  elif rsi <= 20:
    return "⭐⭐⭐⭐ (Derin Dip Bölgesi)"
  elif rsi <= 25:
    return "⭐⭐⭐ (Güçlü Dip Seviyesi)"
  else:
    return "⭐⭐ (Kademeli Giriş Bölgesi)"


def get_momentum_stars(rsi, change, rec):
  if rec == "STRONG_BUY" and change >= 4.0 and rsi >= 65:
    return "⭐⭐⭐⭐⭐ (Yüksek Tavan / Hacim Potansiyeli)"
  elif rec == "STRONG_BUY" and change >= 2.5:
    return "⭐⭐⭐⭐ (Güçlü Momentum Sinyali)"
  else:
    return "⭐⭐⭐ (Pozitif Yükseliş Trendi)"


# ============================================================
# 1. TRADINGVIEW TEKNİK ANALİZ MODÜLÜ
# ============================================================
def analyze_tv_stock(symbol):
  try:
    handler = TA_Handler(
        symbol=symbol,
        screener="turkey",
        exchange="BIST",
        interval=Interval.INTERVAL_1_DAY,
    )
    analysis = handler.get_analysis()
    ind = analysis.indicators

    return {
        "close": ind.get("close"),
        "change": ind.get("change"),
        "rsi": ind.get("RSI"),
        "recommendation": analysis.summary.get("RECOMMENDATION"),
    }
  except Exception:
    return None


# ============================================================
# 2. YÜKSEK HABER DEĞERLİ KAP İSTİHBARAT MODÜLÜ (ANLIK)
# ============================================================
def check_kap_news():
  global PROCESSED_KAP_LINKS
  try:
    kap_url = "https://www.kap.org.tr/tr/rss"
    feed = feedparser.parse(kap_url)

    for entry in feed.entries[:20]:
      if entry.link in PROCESSED_KAP_LINKS:
        continue

      title = entry.title
      summary = entry.summary if "summary" in entry else ""
      content = (title + " " + summary).lower()

      for key, (stars, category) in KAP_STAR_MAP.items():
        if key in content:
          PROCESSED_KAP_LINKS.add(entry.link)
          msg = (
              f"🔥 <b>[YÜKSEK HABER DEĞERİ - KAP İSTİHBARATI]</b>\n\n"
              f"<b>Etki Gücü:</b> {stars}\n"
              f"<b>Kategori:</b> {category}\n"
              f"<b>Başlık:</b> {title}\n"
              f"<b>Link:</b> <a href='{entry.link}'>KAP Bildirim Detayı</a>"
          )
          send_telegram_msg(msg)
          break
  except Exception as e:
    print(f"KAP Kontrol Hatası: {e}")


# ============================================================
# 3. 470 HİSSE SÜZGEÇLİ ÖZEL SEANS TARAMASI
# ============================================================
def scan_bist_stocks(symbol_list, scan_time):
  print(
      f"[{datetime.now().strftime('%H:%M:%S')}] {len(symbol_list)} Yan Tahta İçin"
      f" {scan_time} Taraması Başlatıldı..."
  )

  match_count = 0
  for symbol in symbol_list:
    data = analyze_tv_stock(symbol)
    if not data or data["rsi"] is None or data["close"] is None:
      continue

    price = data["close"]
    rsi = data["rsi"]
    change = data["change"] or 0.0
    rec = data["recommendation"] or "N/A"

    # 🛡️ DİP & DEĞER AVCISI
    if rsi <= RSI_DIP_LIMIT:
      stars = get_dip_stars(rsi)
      msg = (
          f"🛡️ <b>[DİP & DEĞER AVCISI - {scan_time} TARAMASI]</b>\n\n"
          f"<b>Hisse Adı:</b> #{symbol}\n"
          f"<b>Derece:</b> {stars}\n"
          f"<b>Fiyat / Değişim:</b> {price:.2f} TL (%{change:+.2f})\n"
          f"<b>RSI (14):</b> {rsi:.1f}\n"
          f"<b>TV Sinyali:</b> {rec}\n"
          f"<b>Strateji:</b> Kademeli Dip Alımı"
      )
      send_telegram_msg(msg)
      match_count += 1

    # 🚀 GÜNLÜK TAVAN ADAYI
    if (
        rsi >= RSI_MOMENTUM_LIMIT
        and change >= CHANGE_MOMENTUM_LIMIT
        and rec in ["STRONG_BUY", "BUY"]
    ):
      stars = get_momentum_stars(rsi, change, rec)
      msg = (
          f"🚀 <b>[GÜNLÜK TAVAN ADAYI - {scan_time} TARAMASI]</b>\n\n"
          f"<b>Hisse Adı:</b> #{symbol}\n"
          f"<b>Derece:</b> {stars}\n"
          f"<b>Fiyat / Değişim:</b> {price:.2f} TL (%{change:+.2f})\n"
          f"<b>RSI (14):</b> {rsi:.1f}\n"
          f"<b>TV Sinyali:</b> {rec} 🔥\n"
          f"<b>Strateji:</b> Günlük Momentum / Trade"
      )
      send_telegram_msg(msg)
      match_count += 1

    time.sleep(0.05)

  print(
      f"[{datetime.now().strftime('%H:%M:%S')}] {scan_time} Taraması Bitti."
      f" Toplam {match_count} adet fırsat bildirildi."
  )


# ============================================================
# ANA ÇALIŞMA DÖNGÜSÜ
# ============================================================
def main():
  send_telegram_msg(
      "🤖 <b>TRADINGVIEW 470 YAN TAHTA BİST BOTU V8 AKTİF!</b>\n⏰ Özel"
      " Tarama Saatleri: <b>09:50</b> ve <b>10:10</b>\n📊 Toplam Taranan Yan"
      " Tahta: <b>~470 Adet</b>\n🔥 KAP Haberleri: Yalnızca Yüksek Değerli"
      " (4-5 Yıldız)"
  )

  while True:
    try:
      now = datetime.now()
      current_time = now.strftime("%H:%M")
      current_date = now.strftime("%Y-%m-%d")

      # 1. Yüksek Değerli KAP Haberlerini Anlık Tara (Gecikmesiz 30 sn)
      check_kap_news()

      # 2. Özel Saat Taramaları (09:50 ve 10:10)
      scan_key = f"{current_date}_{current_time}"

      if (
          current_time in TARGET_SCAN_TIMES
          and scan_key not in SCANNED_TIMES_TODAY
      ):
        target_symbols = get_all_bist_tickers()
        send_telegram_msg(
            f"⏰ <b>[{current_time} SEANS TARAMASI BAŞLADI]</b>\nToplam"
            f" {len(target_symbols)} adet yan tahta taranıyor..."
        )
        scan_bist_stocks(target_symbols, current_time)
        SCANNED_TIMES_TODAY.add(scan_key)
        send_telegram_msg(
            f"✅ <b>[{current_time} SEANS TARAMASI COMPLETED]</b>"
        )

      time.sleep(30)

    except KeyboardInterrupt:
      print("Bot manuel olarak durduruldu.")
      break
    except Exception as e:
      print(f"Döngü Hatası: {e}")
      time.sleep(30)


if __name__ == "__main__":
  main()
