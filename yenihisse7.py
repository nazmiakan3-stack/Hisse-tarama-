#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BIST Bot – Profesyonel Sanal Portföy (TEK DOSYA)
================================================
- 4 Strateji: DIP, BB, BREAKOUT, MOMENTUM
- 20.000 ₺ sanal cüzdan
- Risk bazlı pozisyon büyüklüğü (%1.5 risk)
- Hafta içi 09:00-18:00 + resmi tatil hariç
- Yüksek hacim + momentum → satmama
- %2 kâr → SL girişe (zarar etmeme)
- SQLite kalıcı portföy
- Telegram bildirimleri
"""

import os
import sys
import time
import json
import logging
import sqlite3
import asyncio
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Dict, Any, Optional, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager

# ===================== KÜTÜPHANELER =====================
try:
    import requests
    import yfinance as yf
    import pandas as pd
    import pandas_ta as ta
    import httpx
except ModuleNotFoundError as e:
    print(f"\n❌ Eksik kütüphane: {e}")
    print("Kurulum: pip install requests yfinance pandas pandas-ta httpx python-dotenv\n")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ===================== AYARLAR =====================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "1734551753")

INITIAL_CAPITAL      = float(os.getenv("INITIAL_CAPITAL", "20000"))
MAX_POSITIONS        = int(os.getenv("MAX_POSITIONS", "5"))
RISK_PER_TRADE_PCT   = float(os.getenv("RISK_PER_TRADE_PCT", "1.5"))
MAX_POSITION_PCT     = float(os.getenv("MAX_POSITION_PCT", "25.0"))
BREAKEVEN_TRIGGER    = float(os.getenv("BREAKEVEN_TRIGGER_PCT", "2.0"))

RSI_DAILY_MAX        = 30.0
RSI_WEEKLY_MAX       = 32.0
MIN_VOLUME_TL_DIP    = 20_000_000
MIN_RVOL             = 1.0
MIN_RVOL_MOMENTUM    = 2.0
BREAKOUT_RVOL_MIN    = 1.8
BREAKOUT_VOLUME_MIN  = 15_000_000
BB_VOLUME_MIN        = 8_000_000

TZ = ZoneInfo("Europe/Istanbul")
SCAN_TIMES   = ["09:50", "10:10", "17:45", "23:00"]
TRADING_START = "09:00"
TRADING_END   = "18:00"

BASE_DIR  = Path(__file__).resolve().parent
DB_PATH   = BASE_DIR / "portfolio.db"
LOG_DIR   = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

HOLIDAYS_FULL = {
    "2026-01-01", "2026-03-20", "2026-03-21", "2026-03-22",
    "2026-04-23", "2026-05-01", "2026-05-19",
    "2026-05-27", "2026-05-28", "2026-05-29", "2026-05-30",
    "2026-07-15", "2026-08-30", "2026-10-29",
}
HALF_DAY_HOLIDAYS = {"2026-03-19", "2026-05-26", "2026-10-28"}

# ===================== LOGGING =====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("BISTBot")

# ===================== TELEGRAM =====================
def send_telegram(message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print(f"\n[TELEGRAM MOCK]\n{message}\n")
        return True
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=12)
        return r.status_code == 200
    except Exception as e:
        logger.warning(f"Telegram hata: {e}")
        return False

# ===================== İŞLEM SAATİ =====================
def is_trading_time(now: datetime = None) -> bool:
    if now is None:
        now = datetime.now(TZ)
    today = now.strftime("%Y-%m-%d")
    weekday = now.weekday()
    current = now.strftime("%H:%M")
    if weekday >= 5:
        return False
    if today in HOLIDAYS_FULL:
        return False
    if today in HALF_DAY_HOLIDAYS:
        return TRADING_START <= current < "13:00"
    return TRADING_START <= current <= TRADING_END

def is_scan_time(now: datetime = None) -> bool:
    if now is None:
        now = datetime.now(TZ)
    return now.strftime("%H:%M") in SCAN_TIMES

# ===================== VERİ & STRATEJİ =====================
FULL_BIST_LIST = [
    "A1CAP","AAVTUR","ACSEL","ADEL","ADESE","AEFES","AFYON","AGESA","AGHOL","AGROT",
    "AHGAZ","AKCNS","AKENR","AKFGY","AKFYE","AKGRT","AKMGY","AKSA","AKSEN","AKSGY",
    "ALBRK","ALCAR","ALCTL","ALFAS","ALGYO","ALKA","ALKIM","ALMAD","ALTNY","ALVES",
    "ANELE","ANGEN","ANHYT","ANSGR","ARASE","ARCLK","ARDYZ","ARENA","ARSAN","ARTMS",
    "ARZUM","ASGYO","ASUZU","ATAGY","ATAKP","ATATP","ATEKS","ATLAS","ATSYH","AVGYO",
    "AVHOL","AVOD","AVPGY","AYCES","AYDEM","AYEN","AYES","AYGAZ","AZTEK","BAGFS",
    "BAKAB","BALAT","BANVT","BARMA","BASGZ","BAYRK","BEAYO","BEYAZ","BFREN","BIENY",
    "BIGCH","BINHO","BIOEN","BIZIM","BJKAS","BLCYT","BMSCH","BMSTL","BNTAS","BOBET",
    "BORLS","BORSK","BOSSA","BRISA","BRKO","BRKSN","BRKVY","BRLSM","BRMEN","BRYAT",
    "BSOKE","BTCIM","BUCIM","BURCE","BURVA","BVSAN","BYDNR","CANTE","CASA","CATES",
    "CCOLA","CELHA","CEMAS","CEMTS","CEOEM","CIMSA","CLEBI","CMBTN","CMENT","CONSE",
    "COSMO","CRDFA","CRFSA","CUSAN","CVKMD","CWENE","DAGHL","DAGI","DAPGM","DARDL",
    "DATA","DEFVA","DERHL","DERIM","DESA","DESPC","DEVA","DGNMO","DIRIT","DITAS",
    "DMRGD","DMSAS","DOBUR","DOCO","DOFER","DOGUB","DOHOL","DOKTA","DURDO","DYOBY",
    "DZGYO","EBEBK","ECILC","ECZYT","EDATA","EDIP","EGEEN","EGEPO","EGERT","EGPRO",
    "EGSER","EKIZ","EKOS","EKSUN","ELITE","EMKEL","ENERY","ENJSA","ENTRA","EPLAS",
    "ERBOS","ERCAN","ERSU","ESCAR","ESCOM","ESEN","ETILR","ETYAT","EUHOL","EUREN",
    "EUYO","EYGYO","FADE","FENER","FLAP","FMIZP","FONET","FORMT","FORTE","FRIGO",
    "FSYGM","FZLGY","GARFA","GENTS","GEREL","GESAN","GIPTA","GLBMD","GLCVY","GLRYH",
    "GLYHO","GMTAS","GOKNR","GOLTS","GOODY","GOZDE","GRNYO","GRSEL","GRTRK","GSDDE",
    "GSDHO","GSRAY","GWIND","GZNMI","HALKB","HATEK","HATSN","HDFGS","HEDEF","HKTM",
    "HLGYO","HRZNO","HSCSM","HUBVC","HUNER","HURGZ","ICBCT","ICUGS","IDGYO","IEYHO",
    "IHAAS","IHEVA","IHGZT","IHLAS","IHLGM","IHYAY","IMASM","INDES","INFO","INGRM",
    "INTEM","INVEO","INVES","IPEKE","ISATR","ISBIR","ISBTR","ISDMR","ISFIN","ISGSY",
    "ISGYO","ISKPL","ISKUR","ISMEN","ISSEN","ISYAT","ITTFH","IZENR","IZFAS","IZINV",
    "IZMDC","JANTS","KALES","KALEK","KARSN","KARTN","KARYE","KATMR","KCAER","KENT",
    "KERVN","KERVT","KFEIN","KGYO","KIMMR","KLGYO","KLKIM","KLMSN","KLNMA","KLRHO",
    "KLSYN","KMPUR","KNFRT","KOCMT","KONKA","KONYA","KOPOL","KORDS","KOZAA","KRDMA",
    "KRDMB","KRGYO","KRONT","KRPLS","KRSTL","KRTEK","KRVGD","KSTUR","KTLEV","KTSKR",
    "KUTPO","KUVVA","KUYAS","KZBGY","KZGYO","LIDER","LIDFA","LINK","LKMNH","LOGO",
    "LRSHO","LUKSK","MAALT","MACKO","MACRO","MAGEN","MAKIM","MAKTK","MANAS","MARKA",
    "MARTI","MAVI","MAXOT","MEDTR","MEGAP","MEKAG","MEPET","MERCN","MERIT","MERKO",
    "METRO","METUR","MGROS","MHRGY","MIATK","MIPAZ","MMCAS","MNDRS","MNDTR","MOBTL",
    "MOGAN","MPARK","MRGYO","MRSHL","MSGYO","MTRKS","MTRYO","MUHAL","MUREN","NASHQ",
    "NATEN","NETAS","NIBAS","NTGAZ","NTHOL","NUGYO","NUHCM","OBASE","OBAMS","ODINE",
    "OFSYM","ONCSM","ORCAY","ORGE","ORMA","OSMEN","OSTIM","OTKAR","OTTO","OYAYO",
    "OYLUM","OYYAT","OZGYO","OZKGY","OZRDN","OZSUB","PAGYO","PAMEL","PAPIL","PARSN",
    "PASEU","PATEK","PCILT","PEGYO","PEKGY","PENGD","PENTA","PETUN","PINSU","PKART",
    "PKENT","PLTUR","PNLSN","PNSUT","POLHO","POLTK","PRDGS","PRKAB","PRKME","PRZMA",
    "PSDTC","PSGYO","QNBFL","QUAGR","RALYH","RAYSG","REEDR","RNPOL","RODRG","ROYAL",
    "RTALB","RUBNS","RYGYO","RYSAS","SAMAT","SANEL","SANFM","SANKO","SARKY","SAYAS",
    "SDTTR","SEGYO","SEKFK","SEKUR","SELEC","SELGD","SELVA","SEYKM","SILVR","SKBNK",
    "SKTAS","SMART","SMRTG","SNGYO","SNICA","SNKRN","SNPAM","SNTCD","SOKE","SOKM",
    "SONME","SRVGY","SUMAS","SUNTK","SURGY","SUWEN","TABGD","TARKM","TATEN","TATGD",
    "TAVHL","TBORG","TDGYO","TEKTU","TERA","TETMT","TEZOL","TGSAS","TKFEN","TKNSA",
    "TLMAN","TMPOL","TMSN","TRCAS","TRGYO","TRILC","TSGYO","TSKB","TSPOR","TTKOM",
    "TTRAK","TUCLK","TUKAS","TUREX","TURGG","TURSG","UFUK","ULAS","ULKER","ULUFA",
    "ULUSE","ULUUN","UMPAS","UNLU","USAK","UZERB","VAKBN","VAKFN","VAKKO","VANGD",
    "VBTYZ","VERTU","VERUS","VESBE","VESTL","VKFYO","VKGYO","VKING","VRGYO","YAPRK",
    "YATAS","YAYLA","YBTAS","YEOTK","YESIL","YGGYO","YGYO","YKBNK","YKSLN","YONGA",
    "YUNSA","YYAPI","ZEDUR","ZOREN","ZRGYO",
    "AKBNK","ALARK","ASELS","ASTOR","BIMAS","BRSAN","DOAS","EKGYO","ENKAI","EREGL",
    "FROTO","GARAN","GUBRF","HEKTS","ISCTR","KCHOL","KONTR","KOZAL","KRDMD","ODAS",
    "OYAKC","PETKM","PGSUS","SAHOL","SASA","SISE","TCELL","THYAO","TOASO","TUPRS",
]
def get_all_tickers() -> List[str]:
    try:
        url = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/HisseTeknikVeriler"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        if res.status_code == 200:
            data = res.json().get("d", [])
            fetched = {item.get("code") for item in data if item.get("code") and len(item.get("code","")) <= 5}
            if len(fetched) >= 300:
                logger.info(f"Canlı liste: {len(fetched)} hisse")
                return sorted(list(fetched))
    except Exception as e:
        logger.warning(f"Canlı liste alınamadı: {e}")
    return sorted(list(set(FULL_BIST_LIST)))

def fetch_ohlcv(symbol: str, period: str = "6mo", interval: str = "1d") -> Optional[pd.DataFrame]:
    try:
        t = yf.Ticker(f"{symbol}.IS")
        df = t.history(period=period, interval=interval, auto_adjust=True)
        if df is None or df.empty or len(df) < 30:
            return None
        return df
    except Exception:
        return None

def analyze_symbol(symbol: str) -> Optional[Dict[str, Any]]:
    try:
        df_daily = fetch_ohlcv(symbol, "6mo", "1d")
        df_weekly = fetch_ohlcv(symbol, "1y", "1wk")
        if df_daily is None or df_weekly is None or len(df_daily) < 40:
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

        rsi_d = float(df_daily.ta.rsi(length=14).iloc[-1])
        rsi_w = float(df_weekly.ta.rsi(length=14).iloc[-1])

        stoch = df_daily.ta.stoch(k=14, d=3, smooth_k=3)
        if stoch is None or stoch.empty:
            return None
        k_col = next((c for c in stoch.columns if "STOCHk" in c), None)
        stoch_k = float(stoch[k_col].iloc[-1])
        stoch_alimda = stoch_k < 20 or stoch_k < 35

        bb = df_daily.ta.bbands(length=20, std=2)
        bb_destek = False
        if bb is not None and not bb.empty:
            lower_col = next((c for c in bb.columns if "BBL" in c), None)
            if lower_col:
                bb_lower = float(bb[lower_col].iloc[-1])
                bb_destek = last_close <= (bb_lower * 1.03) and last_close >= (bb_lower * 0.97)

        atr_val = float(df_daily.ta.atr(length=14).iloc[-1])
        stop_loss = max(0.01, last_close - 1.5 * atr_val)
        take_profit = last_close + 3.0 * atr_val

        ema20 = df_daily.ta.ema(length=20)
        ema50 = df_daily.ta.ema(length=50)
        above_ema20 = last_close > float(ema20.iloc[-1]) if ema20 is not None else False
        above_ema50 = last_close > float(ema50.iloc[-1]) if ema50 is not None else False

        # STRATEJİLER
        strateji_dip = (
            rsi_d < RSI_DAILY_MAX and rsi_w < RSI_WEEKLY_MAX and stoch_alimda
            and hacim_tl >= MIN_VOLUME_TL_DIP and rvol >= MIN_RVOL and change_pct > 0
        )
        strateji_bb = (
            bb_destek and rvol_5 >= 1.2 and hacim_tl >= BB_VOLUME_MIN and change_pct > -1
        )
        strateji_breakout = (
            rvol >= BREAKOUT_RVOL_MIN and hacim_tl >= BREAKOUT_VOLUME_MIN
            and change_pct >= 3.0 and above_ema20 and above_ema50
        )
        strateji_momentum = (
            change_pct >= 5.0 and rvol >= 2.0 and hacim_tl >= 25_000_000
            and 50 < rsi_d < 75
        )

        if not (strateji_dip or strateji_bb or strateji_breakout or strateji_momentum):
            return None

        if strateji_dip:
            primary = "DIP"
        elif strateji_bb:
            primary = "BB"
        elif strateji_breakout:
            primary = "BREAKOUT"
        else:
            primary = "MOMENTUM"

        return {
            "symbol": symbol,
            "fiyat": round(last_close, 2),
            "change_pct": round(change_pct, 2),
            "rsi_d": round(rsi_d, 1),
            "stoch_k": round(stoch_k, 1),
            "rvol": round(rvol, 2),
            "hacim_tl": round(hacim_tl, 0),
            "sl": round(stop_loss, 2),
            "tp": round(take_profit, 2),
            "strateji_dip": strateji_dip,
            "strateji_bb": strateji_bb,
            "strateji_breakout": strateji_breakout,
            "strateji_momentum": strateji_momentum,
            "primary_strategy": primary,
        }
    except Exception as e:
        logger.debug(f"{symbol}: {e}")
        return None

def scan_symbols(symbols: List[str], max_workers: int = 6) -> List[Dict]:
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(analyze_symbol, s): s for s in symbols}
        for fut in as_completed(futures):
            res = fut.result()
            if res:
                results.append(res)
    priority = {"DIP": 4, "BB": 3, "BREAKOUT": 2, "MOMENTUM": 1}
    results.sort(key=lambda x: (priority.get(x["primary_strategy"], 0), x["rvol"]), reverse=True)
    return results
    priority = {"DIP": 4, "BB": 3, "BREAKOUT": 2, "MOMENTUM": 1}
    results.sort(key=lambda x: (priority.get(x["primary_strategy"], 0), x["rvol"]), reverse=True)
    return results

# ===================== PORTFÖY (SQLite) =====================
class PortfolioManager:
    def __init__(self):
        self.db_path = DB_PATH
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS portfolio (
                    id INTEGER PRIMARY KEY, capital REAL, cash REAL, updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS positions (
                    symbol TEXT PRIMARY KEY, entry REAL, qty INTEGER, sl REAL, tp REAL,
                    original_sl REAL, cost REAL, entry_date TEXT, strategy TEXT,
                    breakeven_moved INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS closed_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, entry REAL,
                    exit REAL, qty INTEGER, pnl REAL, pnl_pct REAL, reason TEXT, closed_at TEXT
                );
            """)
            if conn.execute("SELECT COUNT(*) FROM portfolio").fetchone()[0] == 0:
                conn.execute(
                    "INSERT INTO portfolio (id, capital, cash, updated_at) VALUES (1,?,?,?)",
                    (INITIAL_CAPITAL, INITIAL_CAPITAL, datetime.now(TZ).isoformat())
                )

    def get_state(self) -> Dict:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM portfolio WHERE id=1").fetchone()
            positions = {p["symbol"]: dict(p) for p in conn.execute("SELECT * FROM positions")}
            return {"capital": row["capital"], "cash": row["cash"], "positions": positions}

    def _calc_qty(self, price: float, sl: float, cash: float, capital: float) -> int:
        if price <= 0 or sl >= price:
            return 0
        risk_amount = capital * (RISK_PER_TRADE_PCT / 100)
        risk_per_share = price - sl
        if risk_per_share <= 0:
            return 0
        qty = int(risk_amount / risk_per_share)
        max_cost = capital * (MAX_POSITION_PCT / 100)
        qty = min(qty, int(max_cost / price))
        if qty * price > cash:
            qty = int(cash / price)
        return max(qty, 0)

    def open_positions(self, candidates: List[Dict]):
        if not is_trading_time():
            logger.info("İşlem saatleri dışında – alım yok")
            return
        if not candidates:
            return
        state = self.get_state()
        if len(state["positions"]) >= MAX_POSITIONS:
            return
        available = [c for c in candidates if c["symbol"] not in state["positions"]]
        if not available:
            return
        slots = MAX_POSITIONS - len(state["positions"])
        to_buy = available[:slots]
        cash = state["cash"]
        capital = state["capital"]
        if cash < 500:
            return
        opened = []
        with self._conn() as conn:
            for item in to_buy:
                symbol, price, sl = item["symbol"], item["fiyat"], item["sl"]
                qty = self._calc_qty(price, sl, cash, capital)
                if qty < 1:
                    continue
                cost = qty * price
                if cost > cash:
                    continue
                strategy = item.get("primary_strategy", "DIP")
                conn.execute("""
                    INSERT INTO positions
                    (symbol, entry, qty, sl, tp, original_sl, cost, entry_date, strategy, breakeven_moved)
                    VALUES (?,?,?,?,?,?,?,?,?,0)
                """, (symbol, price, qty, sl, item["tp"], sl, round(cost,2),
                      datetime.now(TZ).strftime("%Y-%m-%d"), strategy))
                cash -= cost
                opened.append({"symbol": symbol, "qty": qty, "entry": price,
                               "sl": sl, "tp": item["tp"], "cost": cost, "strategy": strategy})
                logger.info(f"ALIM → {symbol} {qty} adet @ {price} [{strategy}]")
            conn.execute("UPDATE portfolio SET cash=?, updated_at=? WHERE id=1",
                         (round(cash,2), datetime.now(TZ).isoformat()))
        if opened:
            msg = "💰 <b>SANAL CÜZDAN — YENİ POZİSYONLAR</b>\n"
            msg += f"📅 {datetime.now(TZ).strftime('%d.%m.%Y %H:%M')}\n"
            msg += f"💵 Kalan Nakit: <b>{cash:,.2f} ₺</b>\n\n"
            for p in opened:
                msg += (f"🔹 <b>#{p['symbol']}</b> [{p['strategy']}]\n"
                        f"├ Giriş: {p['entry']} × {p['qty']}\n"
                        f"├ 🛑 SL: {p['sl']} | 🎯 TP: {p['tp']}\n"
                        f"└ Maliyet: {p['cost']:,.2f} ₺\n\n")
            send_telegram(msg)

    def update(self):
        state = self.get_state()
        if not state["positions"]:
            return
        closed = []
        with self._conn() as conn:
            for symbol, pos in list(state["positions"].items()):
                df = fetch_ohlcv(symbol, "10d", "1d")
                if df is None or len(df) < 5:
                    continue
                current = float(df["Close"].iloc[-1])
                prev = float(df["Close"].iloc[-2])
                today_chg = ((current - prev) / prev) * 100
                last_vol = float(df["Volume"].iloc[-1])
                avg5 = float(df["Volume"].iloc[-6:-1].mean())
                rvol = last_vol / avg5 if avg5 > 0 else 0
                last3 = df["Close"].iloc[-3:].values
                is_rising = all(last3[i] <= last3[i+1] for i in range(len(last3)-1))
                strong_momentum = (rvol >= MIN_RVOL_MOMENTUM and today_chg > 0
                                   and is_rising and current > pos["entry"])

                entry, qty = pos["entry"], pos["qty"]
                pnl_pct = ((current - entry) / entry) * 100

                if not pos["breakeven_moved"] and pnl_pct >= BREAKEVEN_TRIGGER:
                    conn.execute("UPDATE positions SET sl=?, breakeven_moved=1 WHERE symbol=?",
                                 (entry, symbol))
                    logger.info(f"{symbol} → SL girişe çekildi")

                if strong_momentum:
                    logger.info(f"{symbol} → Momentum güçlü, satılmıyor (RVOL {rvol:.2f})")
                    continue

                if current >= pos["tp"]:
                    pnl = (current - entry) * qty
                    self._close(conn, symbol, current, qty, entry, pnl, pnl_pct, "TP")
                    closed.append({"symbol": symbol, "reason": "TP", "pnl": pnl, "pnl_pct": pnl_pct,
                                   "entry": entry, "exit": current, "qty": qty})
                    continue

                row = conn.execute("SELECT sl, breakeven_moved FROM positions WHERE symbol=?", (symbol,)).fetchone()
                if row and current <= row["sl"]:
                    pnl = (current - entry) * qty
                    reason = "BREAKEVEN" if row["breakeven_moved"] else "SL"
                    self._close(conn, symbol, current, qty, entry, pnl, pnl_pct, reason)
                    closed.append({"symbol": symbol, "reason": reason, "pnl": pnl, "pnl_pct": pnl_pct,
                                   "entry": entry, "exit": current, "qty": qty})
        if closed:
            state = self.get_state()
            msg = "🔔 <b>POZİSYON KAPANDI</b>\n\n"
            for c in closed:
                emoji = "🟢" if c["pnl"] >= 0 else "🔴"
                msg += (f"{emoji} <b>#{c['symbol']}</b> → {c['reason']}\n"
                        f"├ {c['entry']} → {c['exit']} | Adet: {c['qty']}\n"
                        f"└ PnL: <b>{c['pnl']:+.2f} ₺ (%{c['pnl_pct']:+.2f})</b>\n\n")
            msg += f"💵 Nakit: <b>{state['cash']:,.2f} ₺</b>"
            send_telegram(msg)

    def _close(self, conn, symbol, exit_price, qty, entry, pnl, pnl_pct, reason):
        conn.execute("DELETE FROM positions WHERE symbol=?", (symbol,))
        conn.execute("""INSERT INTO closed_trades
            (symbol, entry, exit, qty, pnl, pnl_pct, reason, closed_at)
            VALUES (?,?,?,?,?,?,?,?)""",
            (symbol, entry, exit_price, qty, round(pnl,2), round(pnl_pct,2),
             reason, datetime.now(TZ).isoformat()))
        conn.execute("UPDATE portfolio SET cash = cash + ?, updated_at=? WHERE id=1",
                     (exit_price * qty, datetime.now(TZ).isoformat()))
        logger.info(f"KAPANDI → {symbol} | {reason} | {pnl:+.2f}")

portfolio = PortfolioManager()

# ===================== TARAMA =====================
def run_scan(label: str = "TARAMA"):
    now_str = datetime.now(TZ).strftime("%H:%M:%S")
    logger.info(f"[{now_str}] {label} başlıyor...")
    symbols = get_all_tickers()
    results = scan_symbols(symbols, max_workers=6)

    buy_list = [r for r in results if r.get("strateji_dip") or r.get("strateji_bb") or r.get("strateji_breakout")]

    tarih = datetime.now(TZ).strftime("%d.%m.%Y - %H:%M")
    baslik = "🌙 GECE BÜLTENİ" if "23:00" in label else "GÜN İÇİ"

    if results:
        msg = f"🎯 <b>[SİNYALLER | {baslik}]</b>\n📅 <i>{tarih}</i>\n\n"
        for item in results[:12]:
            msg += (f"🔹 <b>#{item['symbol']}</b> | {item['fiyat']} TL (%+{item['change_pct']})\n"
                    f"├ Strateji: <b>{item['primary_strategy']}</b>\n"
                    f"├ Hacim: {item['hacim_tl']:,.0f} | RVOL: {item['rvol']}x\n"
                    f"├ RSI: {item['rsi_d']} | Stoch: {item['stoch_k']}\n"
                    f"├ 🛑 SL: {item['sl']} | 🎯 TP: {item['tp']}\n\n")
            if len(msg) > 3500:
                send_telegram(msg)
                msg = ""
        if msg.strip():
            send_telegram(msg)
    else:
        send_telegram(f"ℹ️ <b>{label}</b> — Sinyal yok.")

    if buy_list:
        portfolio.open_positions(buy_list)
    portfolio.update()
    logger.info(f"Bitti → Sinyal: {len(results)} | Alım adayı: {len(buy_list)}")
    return results

# ===================== ANA DÖNGÜ =====================
def main():
    logger.info("=" * 50)
    logger.info(f"BIST Bot başlıyor | Sermaye: {INITIAL_CAPITAL:,.0f} ₺")
    logger.info("=" * 50)

    send_telegram(
        "🤖 <b>BİST BOT – TEK DOSYA</b>\n"
        "────────────────────\n"
        f"💰 Cüzdan: <b>{INITIAL_CAPITAL:,.0f} ₺</b>\n"
        f"📊 Max Pozisyon: {MAX_POSITIONS}\n"
        f"🎯 Risk/İşlem: %{RISK_PER_TRADE_PCT}\n"
        f"🕐 İşlem: {TRADING_START}-{TRADING_END} (tatil hariç)\n"
        f"⏰ Tarama: {' | '.join(SCAN_TIMES)}\n"
        "🚀 Aktif..."
    )

    try:
        run_scan("AÇILIŞ TESTİ")
        send_telegram("✅ Açılış tamam. Saatler bekleniyor.")
    except Exception as e:
        logger.exception("Açılış hatası")
        send_telegram(f"❌ Açılış hatası: {e}")

    scanned = set()
    while True:
        try:
            now = datetime.now(TZ)
            hm = now.strftime("%H:%M")
            key = f"{now.strftime('%Y-%m-%d')}_{hm}"
            if is_scan_time(now) and key not in scanned:
                run_scan(hm)
                scanned.add(key)
                if hm == "23:00":
                    scanned.clear()
            time.sleep(25)
        except KeyboardInterrupt:
            send_telegram("🛑 Bot durduruldu.")
            break
        except Exception as e:
            logger.exception("Döngü hatası")
            time.sleep(30)

if __name__ == "__main__":
    main()
