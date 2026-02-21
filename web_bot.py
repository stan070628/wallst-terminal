import streamlit as st
from stocks import STOCK_DICT
from tab_scanner import run_scanner_tab
from tab_deepdive import run_deepdive_tab
from tab_portfolio import run_portfolio_tab  # 신규 모듈 호출

st.set_page_config(page_title="WallSt Pro Terminal", layout="wide")
st.title("📈 WallSt Pro AI Terminal")

# 탭을 3개로 확장
tab1, tab2, tab3 = st.tabs(["🔍 시장 스캐너", "🎯 종목 딥다이브", "💼 내 계좌 정밀 진단"])

with tab1:
    run_scanner_tab(STOCK_DICT)

with tab2:
    run_deepdive_tab(STOCK_DICT)

with tab3:
    run_portfolio_tab(STOCK_DICT)