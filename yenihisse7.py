import time
import requests
import pandas as pd
import pandas_ta as ta
import yfinance as yf
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# ==========================================
# AYARLAR & YAPILANDIRMA
# ==========================================
TELEGRAM_TOKEN = "BOT_TOKEN_BURAYA"
TELEGRAM_CHAT_ID = "CHAT_ID_BURAYA"

# ==========================================
# YARDIMCI VE VERİ ÇEKME FONKSİYONLARI
# ==========================================

def get_all_bist_tickers():
    """İş Yatırım API üzerinden BİST'teki TÜM aktif hisseleri .IS uzantısıyla çeker."""
    url = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/GetHisseList"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            tickers = [f"{item['code']}.IS" for item in data if 'code' in item]
            print(f"✅ Toplam {len(tickers)} adet BİST hissesi yüklendi.")
            return tickers
    except Exception as e:
        print(f"Hisse listesi çekilirken hata: {e}")
    
    # Hata durumunda yedek ana liste
    return ["THYAO.IS", "GARAN.IS", "AKBNK.IS", "EREGL.IS", "ASELS.IS", "SISE.IS", "BIMAS.IS"]

def send_telegram_message(text):
    """Telegram grubuna veya kanalına mesaj gönderir."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Telegram Gönderim Hatası: {e}")

def get_kap_news(symbol):
    """Hisseye ait son KAP duyurusunu kontrol eder ve kritik haberleri analiz eder."""
    clean_ticker = symbol.replace(".IS", "")
    onemli_kategoriler = [
        "Yeni İş İlişkisi", "İhale", "Finansal Rapor", "Bilanço", 
        "Kar Payı", "Temettü", "Sermaye Artırımı", "Pay Alım", "Birleşme"
    ]
    
    try:
        url = f"https://www.kap.org.tr/tr/api/disclosures?code={clean_ticker}"
        response = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                son_haber = data[0]
                baslik = son_haber.get("title", "Özel Durum Açıklaması")
                ozet = son_haber.get("summary", "") or baslik
                
                full_text = f"{baslik} {ozet}".lower()
                is_important = any(kat.lower() in full_text for kat in onemli_kategoriler)
                
                tag = "🔥 [ÖNEMLİ KAP]" if is_important else "ℹ️ [GENEL KAP]"
                return f"{tag} {baslik}: {ozet[:70]}...", is_important
    except Exception:
        pass
        
    return "Aktif KAP bildirimi yok", False

def check_sig_tahta(df_daily):
    """Son 20 günlük ortalama lot hacmine göre sığ tahta tespiti yapar."""
    avg_lot_20 = df_daily['Volume'].iloc[-20:].mean()
    if avg_lot_20 < 500_000:
        return True, f"⚠️ Sığ Tahta (~{round(avg_lot_20/1000)}K Lot/Gün)"
    return False, "🟢 Likit Tahta"

# ==========================================
# TEKNİK ANALİZ VE STRATEJİ FİLTRESİ
# ==========================================

def analyze_ticker(symbol):
    """Hisse verilerini çekip birleşik strateji koşullarını değerlendirir."""
    try:
        ticker_obj = yf.Ticker(symbol)
        
        # Günlük ve Haftalık Verileri Çek
        df_daily = ticker_obj.history(period="6m", interval="1d")
        df_weekly = ticker_obj.history(period="1y", interval="1wk")

        if len(df_daily) < 30 or len(df_weekly) < 14:
            return None

        # 1. RSI (Günlük & Haftalık < 30)
        rsi_daily = df_daily.ta.rsi(length=14).iloc[-1]
        rsi_weekly = df_weekly.ta.rsi(length=14).iloc[-1]

        # 2. Stokastik Osilatör (Günlük)
        stoch = df_daily.ta.stoch(k=14, d=3, smooth_k=3)
        stoch_k = stoch['STOCHk_14_3_3'].iloc[-1]
        stoch_d = stoch['STOCHd_14_3_3'].iloc[-1]
        stoch_alimda = (stoch_k < 20) or (stoch_k > stoch_d and stoch_k < 35)

        # 3. Fiyat Değişimi ve Hacim (Minimum 20M TL)
        last_close = df_daily['Close'].iloc[-1]
        prev_close = df_daily['Close'].iloc[-2]
        change_pct = ((last_close - prev_close) / prev_close) * 100
        
        last_volume = df_daily['Volume'].iloc[-1]
        hacim_tl = last_volume * last_close

        # 4. Göreceli Hacim (RVOL >= 1.5)
        avg_vol_10 = df_daily['Volume'].iloc[-11:-1].mean()
        rvol = last_volume / avg_vol_10 if avg_vol_10 > 0 else 0

        # 5. ATR Risk Yönetimi (1.5x SL / 3.0x TP)
        atr = df_daily.ta.atr(length=14).iloc[-1]
        stop_loss = max(0, last_close - (1.5 * atr))
        take_profit = last_close + (3.0 * atr)

        # 6. Sığ Tahta Kontrolü
        is_sig, tahta_durumu = check_sig_tahta(df_daily)

        # === BİRLEŞİK STRATEJİ FİLTRE KOŞULLARI ===
        teknik_onay = (
            rsi_daily < 30 and
            rsi_weekly < 30 and
            stoch_alimda and
            hacim_tl >= 20_000_000 and
            rvol >= 1.5 and
            change_pct > 0
        )

        if teknik_onay:
            kap_ozeti, kap_onemli = get_kap_news(symbol)
            return {
                'symbol': symbol.replace(".IS", ""),
                'fiyat': round(last_close, 2),
                'change_pct': round(change_pct, 2),
                'rsi_d': round(rsi_daily, 1),
                'rsi_w': round(rsi_weekly, 1),
                'stoch_k': round(stoch_k, 1),
                'rvol': round(rvol, 2),
                'hacim_m': round(hacim_tl / 1_000_000, 1),
                'tahta_durumu': tahta_durumu,
                'atr': round(atr, 2),
                'sl': round(stop_loss, 2),
                'tp': round(take_profit, 2),
                'kap_ozeti': kap_ozeti,
                'kap_onemli': kap_onemli
            }

    except Exception:
        pass
        
    return None

# ==========================================
# ANA ÇALIŞTIRICI
# ==========================================

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] BİST Taraması Başlatılıyor...")
    
    # TÜM BİST HİSSELERİ ÇEKİLİYOR
    bist_hisseleri = get_all_bist_tickers()
    
    eslesenler = []

    # 10 Thread ile paralelde hızlı tarama yürütülür
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(analyze_ticker, bist_hisseleri)
        for res in results:
            if res:
                eslesenler.append(res)

    if eslesenler:
        print(f"\n✅ Toplam {len(eslesenler)} hisse kriterleri karşıladı. Telegram'a iletiliyor...")
        for item in eslesenler:
            uyari_simgesi = "🚨 " if item['kap_onemli'] else ""
            
            mesaj = (
                f"🎯 *[DİP + HACİM PATLAMASI AVCISI]*\n"
                f"───────────────────\n"
                f"🔹 *#{item['symbol']}* | {item['fiyat']} TL (%+{item['change_pct']}) {uyari_simgesi}\n"
                f"├ *RSI (G/H):* {item['rsi_d']} / {item['rsi_w']}\n"
                f"├ *Stokastik %K:* {item['stoch_k']} (Alımda)\n"
                f"├ *Göreceli Hacim:* {item['rvol']}x (RVOL)\n"
                f"├ *Hacim:* {item['hacim_m']}M TL\n"
                f"├ *Tahta Yapısı:* {item['tahta_durumu']}\n"
                f"├ *ATR (14):* {item['atr']} TL\n"
                f"├ 🛑 *Stop Loss (-1.5 ATR):* {item['sl']} TL\n"
                f"├ 🎯 *Take Profit (+3.0 ATR):* {item['tp']} TL\n"
                f"└ 📢 *KAP:* {item['kap_ozeti']}"
            )
            
            send_telegram_message(mesaj)
            time.sleep(0.5)
    else:
        print("Taramada stratejiye uyan hisse bulunamadı.")

if __name__ == "__main__":
    main()
