import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
import streamlit as st

@st.cache_data(ttl=3600)
def get_categorized_stocks():
    """[The Closer] 글로벌 모수를 주요 섹터별 50선으로 전격 확장"""
    try:
        # 국내 시장 (상위 200개 유지)
        kospi_raw = fdr.StockListing('KOSPI')
        sort_col = 'MarCap' if 'MarCap' in kospi_raw.columns else kospi_raw.columns[-1]
        kospi_df = kospi_raw.sort_values(sort_col, ascending=False).head(200)
        
        kosdaq_raw = fdr.StockListing('KOSDAQ')
        kosdaq_df = kosdaq_raw.sort_values(sort_col, ascending=False).head(200)
        
        # [확장] 글로벌 50선: 섹터별 대장주 엄선
        global_assets = {
            # 지수 및 주요 ETF
            "나스닥 100(QQQ)": "QQQ", "S&P 500(SPY)": "SPY", "반도체(SOXX)": "SOXX", "배당주(SCHD)": "SCHD",
            # 빅테크 (Magnificent 7)
            "애플(AAPL)": "AAPL", "마이크로소프트(MSFT)": "MSFT", "엔비디아(NVDA)": "NVDA", 
            "구글(GOOGL)": "GOOGL", "아마존(AMZN)": "AMZN", "메타(META)": "META", "테슬라(TSLA)": "TSLA",
            # 반도체 및 테크 대장주
            "TSMC(TSM)": "TSM", "ASML(ASML)": "ASML", "브로드컴(AVGO)": "AVGO", "AMD(AMD)": "AMD", 
            "퀄컴(QCOM)": "QCOM", "인텔(INTC)": "INTC", "마이크론(MU)": "MU", "ARM(ARM)": "ARM", 
            "어플라이드(AMAT)": "AMAT", "램리서치(LRCX)": "LRCX",
            # 소프트웨어 및 성장주
            "넷플릭스(NFLX)": "NFLX", "어도비(ADBE)": "ADBE", "세일즈포스(CRM)": "CRM", "오라클(ORCL)": "ORCL",
            "팔란티어(PLTR)": "PLTR", "스노우플레이크(SNOW)": "SNOW", "우버(UBER)": "UBER", "에어비앤비(ABNB)": "ABNB",
            # 금융 및 전통 가치주
            "버크셔(BRK-B)": "BRK-B", "JP모건(JPM)": "JPM", "비자(V)": "V", "마스터카드(MA)": "MA", 
            "월마트(WMT)": "WMT", "코스트코(COST)": "COST", "일라이릴리(LLY)": "LLY", "화이자(PFE)": "PFE",
            # 가상자산 (Major Crypto)
            "비트코인(BTC)": "BTC-USD", "이더리움(ETH)": "ETH-USD", "솔라나(SOL)": "SOL-USD", 
            "리플(XRP)": "XRP-USD", "도지코인(DOGE)": "DOGE-USD", "에이다(ADA)": "ADA-USD"
        }
        
        return {
            "KOSPI 200": {row['Name']: f"{row['Code']}.KS" for _, row in kospi_df.iterrows()},
            "KOSDAQ 200": {row['Name']: f"{row['Code']}.KQ" for _, row in kosdaq_df.iterrows()},
            "GLOBAL": global_assets
        }
    except Exception as e:
        st.error(f"⚠️ 글로벌 엔진 로드 중 오류: {e}")
        return {"KOSPI 200": {"삼성전자": "005930.KS"}, "GLOBAL": {"비트코인": "BTC-USD"}}

@st.cache_data(ttl=86400)
def get_all_krx_stocks():
    """정밀 진단용 전 자산 통합 리스트 (ETF/ETN 포함)"""
    try:
        krx_df = fdr.StockListing('KRX')
        etf_df = fdr.StockListing('ETF/KR')
        all_assets = {}
        for _, row in krx_df.iterrows():
            suffix = ".KQ" if row['Market'] == 'KOSDAQ' else ".KS"
            all_assets[row['Name']] = f"{row['Code']}{suffix}"
        for _, row in etf_df.iterrows():
            all_assets[row['Name']] = f"{row['Symbol']}.KS"
        return all_assets
    except:
        return {"삼성전자": "005930.KS"}