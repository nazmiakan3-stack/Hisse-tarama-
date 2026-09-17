import time
import requests
import schedule
import pandas as pd
import pandas_ta as ta
import yfinance as yf
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# ==========================================
# AYARLAR & YAPILANDIRMA (MEVCUT BİLGİLERİNİZİ GİRİN)
# ==========================================
TELEGRAM_TOKEN = "BOT_TOKEN_BURAYA"
TELEGRAM_CHAT_ID = "CHAT_ID_BURAYA"

# ==========================================
# YARDIMCI VE VERİ ÇEKME FONKSİYONLARI
# ==========================================

def get_all_bist_tickers():
    """İş Yatırım API üzerinden BİST'teki TÜM aktif hisseleri çeker."""
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
    # Hata anında en azından test için majör hisseleri döner
    return ["THYAO.IS", "GARAN.IS", "AKBNK.IS", "EREGL.IS", "ASELS.IS", "SISE.IS", "BIMAS.IS"]

def send_telegram_message(text):
    """Telegram grubuna / kanalına mesaj gönderir."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Telegram Gönderim Hatası: {e}")

def get_kap_news(symbol):
    """Hisseye ait son KAP duyurusunu çeker ve içeriğini filtreler."""
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
                return f"{tag} {baslik}: {ozet[:60]}...", is_important
    except Exception:
        pass
    return "Aktif KAP bildirimi yok", False

def check_sig_tahta(df_daily):
    """Hacme göre sığ tahta uyarısı verir (Son 20 gün ortalaması < 500K Lot)."""
    avg_lot_20 = df_daily['Volume'].iloc[-20:].mean()
    if avg_lot_20 < 500_000:
        return f"⚠️ Sığ Tahta (~{int(avg_lot_20/1000)}K Lot)"
    return "🟢 Likit Tahta"

# ==========================================
# TEKNİK ANALİZ VE YENİ STRATEJİ FİLTRESİ
# ==========================================

def analyze_ticker(symbol):
    """Fiyat, Hacim, RSI, Stoch ve EMA9 Trend Kırılımı şartlarını analiz eder."""
    try:
        ticker_obj = yf.Ticker(symbol)
        df_daily = ticker_obj.history(period="6m", interval="1d")
        df_weekly = ticker_obj.history(period="1y", interval="1wk")

        if len(df_daily) < 30 or len(df_weekly) < 14:
            return None

        # 1. RSI ve Stoch Kriterleri
        rsi_daily = df_daily.ta.rsi(length=14).iloc[-1]
        rsi_weekly = df_weekly.ta.rsi(length=14).iloc[-1]
        stoch = df_daily.ta.stoch(k=14, d=3, smooth_k=3)
        stoch_k = stoch['STOCHk_14_3_3'].iloc[-1]
        stoch_d = stoch['STOCHd_14_3_3'].iloc[-1]
        stoch_alimda = (stoch_k < 20) or (stoch_k > stoch_d and stoch_k < 35)

        # 2. Hacim ve Fiyat Değişimi
        last_close = df_daily['Close'].iloc[-1]
        prev_close = df_daily['Close'].iloc[-2]
        change_pct = ((last_close - prev_close) / prev_close) * 100
        
        last_volume = df_daily['Volume'].iloc[-1]
        hacim_tl = last_volume * last_close

        avg_vol_10 = df_daily['Volume'].iloc[-11:-1].mean()
        rvol = last_volume / avg_vol_10 if avg_vol_10 > 0 else 0

        # 3. Trend Kırılımı (EMA 9)
        ema9 = df_daily.ta.ema(length=9)
        trend_kirilimi = (last_close > ema9.iloc[-1]) and (prev_close <= ema9.iloc[-2])

        # 4. ATR (Risk Yönetimi) ve Tahta Durumu
        atr = df_daily.ta.atr(length=14).iloc[-1]
        stop_loss = max(0, last_close - (1.5 * atr))
        take_profit = last_close + (3.0 * atr)
        tahta_durumu = check_sig_tahta(df_daily)

        # === DİP + HACİM STRATEJİSİ ONAY KOŞULLARI ===
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
            
            # Dinamik Yıldız Hesaplama (Maksimum 5 Yıldız)
            yildiz_sayisi = 3 
            if rvol >= 2.5: yildiz_sayisi += 1 # Ekstra Hacim Patlaması
            if trend_kirilimi: yildiz_sayisi += 1 # Trend Kırılımı (EMA9 Kesimi)
            yildizlar = "⭐" * min(yildiz_sayisi, 5)

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
                'kap_onemli': kap_onemli,
                'trend_kirilimi': trend_kirilimi,
                'yildizlar': yildizlar
            }

    except Exception:
        pass
    return None

# ==========================================
# ANA ÇALIŞTIRICI: ÇOKLU İŞLEM, SIRALAMA VE RAPORLAMA
# ==========================================

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] BİST Taraması Başlatılıyor...")
    bist_hisseleri = get_all_bist_tickers()
    eslesenler = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(analyze_ticker, bist_hisseleri)
        for res in results:
            if res:
                eslesenler.append(res)

    if eslesenler:
        # === SIRALAMA ALGORİTMASI ===
        # Önce KAP'ı önemli olanlar en üste gelir, ardından Göreceli Hacime (RVOL) göre yüksekten düşüğe sıralanır.
        eslesenler.sort(key=lambda x: (x['kap_onemli'], x['rvol']), reverse=True)
        
        mesaj = "🎯 *[DİP + HACİM PATLAMASI AVCISI]*\n"
        mesaj += f"📅 `{datetime.now().strftime('%d.%m.%Y - %H:%M')}`\n\n"
        
        for item in eslesenler:
            uyari_simgesi = "🚨" if item['kap_onemli'] else ""
            
            # Trend durumuna göre yıldızlı özel bildirim
            if item['trend_kirilimi']:
                durum_etiketi = f"🚀 *Durum:* EMA9 KIRILDI (Trend Yükselişi) {item['yildizlar']}"
            else:
                durum_etiketi = f"📊 *Durum:* Dipte Güç Topluyor {item['yildizlar']}"
            
            hisse_str = (
                f"🔹 *#{item['symbol']}* | {item['fiyat']} TL (%+{item['change_pct']}) {uyari_simgesi}\n"
                f"├ {durum_etiketi}\n"
                f"├ *Göreceli Hacim:* {item['rvol']}x | *Hacim:* {item['hacim_m']}M TL\n"
                f"├ *RSI (G/H):* {item['rsi_d']}/{item['rsi_w']} | *Stoch:* {item['stoch_k']}\n"
                f"├ *Tahta:* {item['tahta_durumu']}\n"
                f"├ 🛑 *SL:* {item['sl']} TL | 🎯 *TP:* {item['tp']} TL\n"
                f"└ 📢 *KAP:* {item['kap_ozeti']}\n\n"
            )
            
            if len(mesaj) + len(hisse_str) > 4000:
                send_telegram_message(mesaj)
                mesaj = ""
                time.sleep(1)
                
            mesaj += hisse_str
            
        if mesaj: 
            send_telegram_message(mesaj)
            
        print(f"✅ Rapor Telegrama gönderildi! ({len(eslesenler)} hisse)")
    else:
        print("Taramada stratejiye uyan hisse bulunamadı.")

# ==========================================
# ZAMANLAYICI (SCHEDULER) UYGULAMASI
# ==========================================

def zamanli_tarama():
    """Hafta sonu kontrolü yaparak taramayı tetikler."""
    if datetime.today().weekday() < 5: 
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Zamanlanmış görev tetiklendi.")
        main()
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Hafta sonu! Borsa kapalı olduğu için tarama atlandı.")

if __name__ == "__main__":
    print("Bot sunucuda başlatıldı. Belirlenen saatler bekleniyor (09:50, 10:15, 23:00)...")
    
    schedule.every().day.at("09:50").do(zamanli_tarama)
    schedule.every().day.at("10:15").do(zamanli_tarama)
    schedule.every().day.at("23:00").do(zamanli_tarama)
    
    # Sunucuda (Screen içerisinde) arka planda 7/24 uyuyup uyanarak saati takip eder
    while True:
        schedule.run_pending()
        time.sleep(30) 
