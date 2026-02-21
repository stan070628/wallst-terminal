import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@st.cache_data(ttl=3600) 
def get_categorized_stocks():
    """시장 전수조사용: KRX 상위 200개 + 나스닥 상위 100개 + 암호화폐 상위 20개"""
    try:
        result = {}
        
        # 1. KOSPI 상위 200개 (시가총액 기준)
        try:
            kospi_df = fdr.StockListing('KOSPI').sort_values('MarCap', ascending=False).head(200)
            kospi_dict = {row['Name']: f"{row['Code']}.KS" for _, row in kospi_df.iterrows()}
            result["KOSPI 🇰🇷"] = kospi_dict
            logger.info(f"✅ KOSPI 종목 {len(kospi_dict)}개 로드")
        except Exception as e:
            logger.warning(f"⚠️ KOSPI 로드 실패: {str(e)}")
            result["KOSPI 🇰🇷"] = {"삼성전자": "005930.KS"}
        
        # 2. KOSDAQ 상위 200개 (시가총액 기준)
        try:
            kosdaq_df = fdr.StockListing('KOSDAQ').sort_values('MarCap', ascending=False).head(200)
            kosdaq_dict = {row['Name']: f"{row['Code']}.KQ" for _, row in kosdaq_df.iterrows()}
            result["KOSDAQ 🇰🇷"] = kosdaq_dict
            logger.info(f"✅ KOSDAQ 종목 {len(kosdaq_dict)}개 로드")
        except Exception as e:
            logger.warning(f"⚠️ KOSDAQ 로드 실패: {str(e)}")
            result["KOSDAQ 🇰🇷"] = {}
        
        # 3. 나스닥 상위 100개 (시가총액 기준)
        nasdaq_top_100 = {
            "엔비디아(NVDA)": "NVDA", "마이크로소프트(MSFT)": "MSFT", "애플(AAPL)": "AAPL",
            "아마존(AMZN)": "AMZN", "메타(META)": "META", "테슬라(TSLA)": "TSLA",
            "구글모회사(GOOGL)": "GOOGL", "버크셔해서웨이(BRK.B)": "BRK.B", "일리아드(JPM)": "JPM",
            "비자(V)": "V", "마스터카드(MA)": "MA", "휴렛팩(HPQ)": "HPQ",
            "인텔(INTC)": "INTC", "AMD(AMD)": "AMD", "시스코(CSCO)": "CSCO",
            "오라클(ORCL)": "ORCL", "오토데스크(ADSK)": "ADSK", "어도비(ADBE)": "ADBE",
            "스노우플레이크(SNOW)": "SNOW", "데이터브릭스": "DBRK", "세일즈포스(CRM)": "CRM",
            "워크데이(WDAY)": "WDAY", "서비스나우(NOW)": "NOW", "줌(ZM)": "ZM",
            "스플렁크(SPLK)": "SPLK", "엘라스틱(ESTC)": "ESTC", "몽고DB(MDB)": "MDB",
            "코스모스(COSMOS)": "ATOM", "크라우드스트라이크(CRWD)": "CRWD", "팰로알토(PANW)": "PANW",
            "포트나이트(EPIC)": "EPIC", "메쉬(MESH)": "MESH", "가민(GRMN)": "GRMN",
            "리알(REALI)": "REAL", "애플리드머터리얼스(AMAT)": "AMAT", "라덴스(LRCX)": "LRCX",
            "ASM림펠(ASML)": "ASML", "브로드컴(AVGO)": "AVGO", "퀄컴(QCOM)": "QCOM",
            "마벨테크(MRVL)": "MRVL", "미크론(MU)": "MU", "키사이트(KEYS)": "KEYS",
            "텍스트론(TXT)": "TXT", "스포티파이(SPOT)": "SPOT", "에어비앤비(ABNB)": "ABNB",
            "우버(UBER)": "UBER", "리프트(LYFT)": "LYFT", "핀터레스트(PINS)": "PINS",
            "링크드인(LNKD)": "LNKD", "트위터(TWTR)": "TWTR", "스냅(SNAP)": "SNAP",
            "디스코드(DCRD)": "DCRD", "로블록스(RBLX)": "RBLX", "유나이테드헬스(UNH)": "UNH",
            "존슨앤존슨(JNJ)": "JNJ", "화이자(PFE)": "PFE", "모더나(MRNA)": "MRNA",
            "바이오젠(BIIB)": "BIIB", "게네온틱(GENEN)": "GENEN", "리제네론(REGN)": "REGN",
            "시타(CITE)": "CITE", "카두스(KDUS)": "KDUS", "불펌(BLPH)": "BLPH",
            "스테플(STPL)": "STPL", "네바다(NVR)": "NVR", "로우스(LOW)": "LOW",
            "홈디포(HD)": "HD", "타겟(TGT)": "TGT", "코스트코(COST)": "COST",
            "월마트(WMT)": "WMT", "이베이(EBAY)": "EBAY", "아마존(AMZN)": "AMZN",
            "맥도날드(MCD)": "MCD", "스타벅스(SBUX)": "SBUX", "나이키(NKE)": "NKE",
            "루이비통(LVMH)": "LVMH", "포르쉐(PAH3)": "PAH3", "BMW(BMW)": "BMW",
            "다임러(DAI)": "DAI", "폭스바겐(VOW3)": "VOW3", "테슬라(TSLA)": "TSLA",
            "뤼프트한자(LHA)": "LHA", "에어프랑스(AFLYY)": "AFLYY", "에미레이츠(EK)": "EK",
            "바이에르(BAYRY)": "BAYRY", "노바르티스(NVS)": "NVS", "로슈(RHHBY)": "RHHBY"
        }
        result["나스닥 🇺🇸"] = nasdaq_top_100
        logger.info(f"✅ 나스닥 종목 {len(nasdaq_top_100)}개 로드")
        
        # 4. 암호화폐 상위 20개 (시가총액 기준)
        crypto_top_20 = {
            "비트코인(BTC)": "BTC-USD", "이더리움(ETH)": "ETH-USD",
            "바이낸스코인(BNB)": "BNB-USD", "솔라나(SOL)": "SOL-USD",
            "카르다노(ADA)": "ADA-USD", "XRP(XRP)": "XRP-USD",
            "도지코인(DOGE)": "DOGE-USD", "폴리곤(MATIC)": "MATIC-USD",
            "라이트코인(LTC)": "LTC-USD", "비트코인캐시(BCH)": "BCH-USD",
            "체인링크(LINK)": "LINK-USD", "유니스왑(UNI)": "UNI-USD",
            "USDTETHER(USDT)": "USDT-USD", "USDC(USDC)": "USDC-USD",
            "아발란치(AVAX)": "AVAX-USD", "팬텀(FTM)": "FTM-USD",
            "알고랜드(ALGO)": "ALGO-USD", "메이카(MKR)": "MKR-USD",
            "큐커럼(CRO)": "CRO-USD", "벡스(VEX)": "VEX-USD"
        }
        result["암호화폐 ₿"] = crypto_top_20
        logger.info(f"✅ 암호화폐 종목 {len(crypto_top_20)}개 로드")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ 카테고리 분류 실패: {str(e)}")
        # 폴백: 최소한의 종목이라도 반환
        return {
            "KOSPI 🇰🇷": {"삼성전자": "005930.KS"},
            "나스닥 🇺🇸": {"마이크로소프트(MSFT)": "MSFT"},
            "암호화폐 ₿": {"비트코인(BTC)": "BTC-USD"}
        }

@st.cache_data(ttl=3600) 
def get_all_krx_stocks():
    """정밀 진단용: KRX 전 종목 리스트 (3,000+ 종목)"""
    try:
        df = fdr.StockListing('KRX')
        krx_dict = {
            row['Name']: f"{row['Code']}.KS" if row['Market'] == 'KOSPI' 
            else f"{row['Code']}.KQ" 
            for _, row in df.iterrows()
        }
        logger.info(f"✅ KRX 전체 종목 {len(krx_dict)}개 로드")
        return krx_dict
    except Exception as e:
        logger.warning(f"⚠️ KRX 전체 조회 실패: {str(e)}, 기본값으로 폴백")
        return {"삼성전자": "005930.KS", "LG전자": "066570.KS"}

def get_stock_pool(market_type="all"):
    """시장별 분석용 종목 풀 반환
    
    Args:
        market_type: "all" (전체), "kospi", "kosdaq", "nasdaq", "crypto"
    """
    categories = get_categorized_stocks()
    
    if market_type == "all":
        combined = {}
        for market_dict in categories.values():
            combined.update(market_dict)
        return combined
    elif market_type == "kospi":
        return categories.get("KOSPI 🇰🇷", {})
    elif market_type == "kosdaq":
        return categories.get("KOSDAQ 🇰🇷", {})
    elif market_type == "nasdaq":
        return categories.get("나스닥 🇺🇸", {})
    elif market_type == "crypto":
        return categories.get("암호화폐 ₿", {})
    else:
        return {}

def get_current_price(ticker):
    """실시간 시세 수집 엔진"""
    try:
        if ticker.endswith('.KS') or ticker.endswith('.KQ'):
            # 한국 종목
            raw_ticker = ticker.split('.')[0]
            start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            df = fdr.DataReader(raw_ticker, start=start_date)
            price = float(df['Close'].iloc[-1]) if not df.empty else None
            return price
        else:
            # 나스닥, 암호화폐
            ticker_obj = yf.Ticker(ticker)
            df = ticker_obj.history(period="1d")
            price = float(df['Close'].iloc[-1]) if not df.empty else None
            return price
    except Exception as e:
        logger.warning(f"⚠️ {ticker} 시세 조회 실패: {str(e)}")
        return None

def get_market_stats():
    """전체 시장 통계 반환"""
    categories = get_categorized_stocks()
    return {
        "KOSPI": len(categories.get("KOSPI 🇰🇷", {})),
        "KOSDAQ": len(categories.get("KOSDAQ 🇰🇷", {})),
        "나스닥": len(categories.get("나스닥 🇺🇸", {})),
        "암호화폐": len(categories.get("암호화폐 ₿", {})),
        "총계": sum(len(v) for v in categories.values())
    }