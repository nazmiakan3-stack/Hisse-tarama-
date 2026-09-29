#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import threading
import logging
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, HTTPServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("BISTSim")

try:
    import requests
    import feedparser
    import yfinance as yf
    import pandas as pd
    import pandas_ta as ta
except ModuleNotFoundError as e:
    print(f"❌ EKSİK KÜTÜPHANE: {e}")
    exit(1)

# ==================== AYARLAR ====================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1734551753")

TZ = timezone(timedelta(hours=3))
TARGET_SCAN_TIMES = ["23:00"]          # Sadece gece tarama
PORTFOLIO_FILE = "sanal_portfoy.json"
TRADE_HISTORY_FILE = "islem_gecmisi.json"
STARTING_BALANCE = 20000.0             # Başlangıç sanal bakiye

FULL_BIST_LIST = [  # Kısaltılmış örnek liste, istersen eskisini koyabilirsin
    "THYAO", "GARAN", "AKBNK", "EREGL", "SISE", "TUPRS", "ASELS", "KCHOL",
    "SAHOL", "BIMAS", "TOASO", "FROTO", "PGSUS", "TCELL", "ISCTR", "YKBNK",
    "HALKB", "VAKBN", "ENKAI", "PETKM", "SASA", "KOZAL", "GUBRF", "HEKTS"
]

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")
    def log_message(self, *args): pass

def start_health_check():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), HealthCheckHandler).serve_forever()

threading.Thread(target=start_health_check, daemon=True).start()

def send_telegram(msg, sound=False):
    if not TELEGRAM_BOT_TOKEN or "YOUR_TELEGRAM" in TELEGRAM_BOT_TOKEN:
        print(msg)
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_notification": not sound},
            timeout=12
        )
    except Exception as e:
        logger.warning(f"Telegram hatası: {e}")

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    return {
        "balance": STARTING_BALANCE,
        "positions": {},          # açık pozisyonlar
        "last_scan_date": None
    }

def save_portfolio(data):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_history():
    if os.path.exists(TRADE_HISTORY_FILE):
        with open(TRADE_HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_history(history):
    with open(TRADE_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def analyze_ticker(symbol):
    try:
        t = yf.Ticker(f"{symbol}.IS")
        df = t.history(period="3mo", interval="1d", auto_adjust=True)
        if df is None or len(df) < 30:
            return None

        close = float(df["Close"].iloc[-1])
        prev = float(df["Close"].iloc[-2])
        change = ((close - prev) / prev) * 100
        if change <= 0:
            return None

        vol = float(df["Volume"].iloc[-1]) * close
        rsi = df.ta.rsi(length=14)
        if rsi is None:
            return None
        rsi_val = float(rsi.iloc[-1])

        atr = df.ta.atr(length=14)
        if atr is None:
            return None
        atr_val = float(atr.iloc[-1])

        sl = round(close - 1.5 * atr_val, 2)
        tp = round(close + 3.0 * atr_val, 2)

        # Basit filtre: RSI düşük + hacim makul
        if rsi_val < 35 and vol > 5_000_000:
            return {
                "symbol": symbol,
                "price": round(close, 2),
                "change": round(change, 2),
                "rsi": round(rsi_val, 1),
                "sl": sl,
                "tp": tp,
                "volume": vol
            }
    except:
        pass
    return None

def night_scan():
    logger.info("Gece taraması başlıyor...")
    candidates = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(analyze_ticker, s): s for s in FULL_BIST_LIST}
        for f in as_completed(futures):
            res = f.result()
            if res:
                candidates.append(res)

    candidates.sort(key=lambda x: x["rsi"])
    selected = candidates[:5]  # En iyi 5 aday

    portfolio = load_portfolio()
    portfolio["last_scan_date"] = datetime.now(TZ).strftime("%Y-%m-%d")
    portfolio["pending"] = selected  # Ertesi gün giriş için bekleyenler
    save_portfolio(portfolio)

    if selected:
        msg = "🌙 <b>GECE SEÇİLEN ADAYLAR</b>\n\n"
        for c in selected:
            msg += f"🔹 <b>#{c['symbol']}</b> | {c['price']} TL\n├ RSI: {c['rsi']} | Değişim: %+{c['change']}\n├ SL: {c['sl']} | TP: {c['tp']}\n\n"
        msg += f"💰 Güncel Sanal Bakiye: <b>{portfolio['balance']:,.0f} TL</b>"
        send_telegram(msg)
    else:
        send_telegram("🌙 Gece taraması: Uygun aday bulunamadı.")

def check_and_enter_positions():
    portfolio = load_portfolio()
    pending = portfolio.get("pending", [])
    if not pending:
        return

    today = datetime.now(TZ).strftime("%Y-%m-%d")
    if portfolio.get("last_scan_date") == today:
        return  # Aynı gün tekrar girme

    for item in pending:
        symbol = item["symbol"]
        entry = item["price"]
        # Basit pozisyon büyüklüğü: bakiyenin %15'i
        amount = portfolio["balance"] * 0.15
        qty = amount / entry

        portfolio["positions"][symbol] = {
            "entry": entry,
            "sl": item["sl"],
            "tp": item["tp"],
            "qty": qty,
            "entry_date": today
        }
        logger.info(f"Giriş yapıldı: {symbol} @ {entry}")

    portfolio["pending"] = []
    save_portfolio(portfolio)
    send_telegram(f"✅ {len(pending)} hisse için sanal giriş yapıldı.")

def check_exits():
    portfolio = load_portfolio()
    positions = portfolio.get("positions", {})
    if not positions:
        return

    history = load_history()
    closed = []

    for symbol, pos in list(positions.items()):
        try:
            t = yf.Ticker(f"{symbol}.IS")
            df = t.history(period="5d", interval="1d")
            if df is None or df.empty:
                continue
            current = float(df["Close"].iloc[-1])

            exit_price = None
            result = None
            if current >= pos["tp"]:
                exit_price = pos["tp"]
                result = "TP"
            elif current <= pos["sl"]:
                exit_price = pos["sl"]
                result = "SL"

            if exit_price:
                pnl = (exit_price - pos["entry"]) * pos["qty"]
                pnl_pct = ((exit_price - pos["entry"]) / pos["entry"]) * 100
                portfolio["balance"] += pnl

                trade = {
                    "symbol": symbol,
                    "entry": pos["entry"],
                    "exit": exit_price,
                    "tp": pos["tp"],
                    "sl": pos["sl"],
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "result": result,
                    "date": datetime.now(TZ).strftime("%Y-%m-%d %H:%M"),
                    "balance_after": round(portfolio["balance"], 2)
                }
                history.append(trade)
                closed.append(trade)
                del portfolio["positions"][symbol]
        except Exception as e:
            logger.debug(f"{symbol} çıkış kontrol hatası: {e}")

    if closed:
        save_portfolio(portfolio)
        save_history(history)

        msg = "📊 <b>SANAL İŞLEM SONUÇLARI</b>\n\n"
        for t in closed:
            emoji = "✅" if t["pnl"] > 0 else "❌"
            msg += f"{emoji} <b>#{t['symbol']}</b>\n"
            msg += f"Giriş: {t['entry']} → Çıkış: {t['exit']} ({t['result']})\n"
            msg += f"Kâr/Zarar: <b>{t['pnl']:+.2f} TL</b> (%{t['pnl_pct']:+.2f})\n"
            msg += f"Yeni Bakiye: <b>{t['balance_after']:,.0f} TL</b>\n\n"
        send_telegram(msg, sound=True)

def main():
    send_telegram(
        f"🤖 <b>SANAL PORTFÖY BOTU BAŞLATILDI</b>\n\n"
        f"💰 Başlangıç Bakiye: <b>{STARTING_BALANCE:,.0f} TL</b>\n"
        f"• Gece 23:00 → Aday seçimi\n"
        f"• Ertesi gün → Sanal giriş\n"
        f"• TP / SL → Otomatik kapanış\n"
        f"• Tüm işlemler kaydedilir ve raporlanır\n"
        f"🚀 Gerçek emir gönderilmez (Paper Trading)"
    )

    while True:
        now = datetime.now(TZ)
        current_time = now.strftime("%H:%M")

        if current_time == "23:00":
            night_scan()
            time.sleep(60)

        # Her 30 dakikada bir açık pozisyonları kontrol et
        if now.minute % 30 == 0:
            check_and_enter_positions()
            check_exits()

        time.sleep(20)

if __name__ == "__main__":
    main()
