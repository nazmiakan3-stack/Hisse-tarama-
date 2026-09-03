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

TARGET_SCAN_TIMES = {"09:50", "10:10"}

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
    "TKNSA", "TLMAN", "TMPOL", "TMSN", "TNZTP", "TOASO", "TRGYO", "TRIL
