import yfinance as yf
import pandas as pd
import streamlit as st
from stocks import STOCK_DICT

@st.cache_data(ttl=3600)
def get_categorized_stocks():
    """[The Closer] 글로벌 모수를 주요 섹터별 50선으로 전격 확장"""
    try:
        # stocks.py의 STOCK_DICT를 활용
        return {
            "KOSPI 200": STOCK_DICT.get("KOSPI", {}),
            "KOSDAQ 200": STOCK_DICT.get("KOSDAQ", {}),
            "GLOBAL": STOCK_DICT.get("GLOBAL", {})
        }
    except Exception as e:
        st.error(f"⚠️ 글로벌 엔진 로드 중 오류: {e}")
        return {"KOSPI 200": {"삼성전자": "005930.KS"}, "GLOBAL": {"비트코인": "BTC-USD"}}

@st.cache_data(ttl=86400)
def get_all_krx_stocks():
    """정밀 진단용 전 자산 통합 리스트 (ETF/ETN 포함)"""
    try:
        # KOSPI + KOSDAQ 통합 리스트
        all_assets = {}
        all_assets.update(STOCK_DICT.get("KOSPI", {}))
        all_assets.update(STOCK_DICT.get("KOSDAQ", {}))
        return all_assets
    except:
        return {"삼성전자": "005930.KS"}