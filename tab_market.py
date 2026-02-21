import streamlit as st
import pandas as pd
from engine import analyze_stock
from market_data import get_categorized_stocks  # [수정] 동적 리스트 엔진 로드
from style_utils import apply_global_style

def run_market_tab(unused_stock_dict):
    apply_global_style()
    st.markdown("<h1 style='color:white; font-weight:800;'>🔥 시장 전수조사 (Top 200 Sweep)</h1>", unsafe_allow_html=True)
    
    # [수정] 동적 시장 카테고리 로드 (모수 200개 확장)
    categories = get_categorized_stocks()
    
    col1, col2, col3 = st.columns(3)
    market_key = None
    if col1.button("🇰🇷 KOSPI 200", use_container_width=True, key="m_kospi"): market_key = "KOSPI 200"
    if col2.button("🇰🇷 KOSDAQ 200", use_container_width=True, key="m_kosdaq"): market_key = "KOSDAQ 200"
    if col3.button("🇺🇸 GLOBAL", use_container_width=True, key="m_global"): market_key = "GLOBAL"

    if market_key:
        stocks_to_scan = categories[market_key]
        
        st.write("---")
        col_f1, col_f2 = st.columns(2)
        with col_f1: min_score = st.slider("최소 신뢰도 점수 (현재 시장 약세 시 45~50점 추천)", 0, 100, 50)
        with col_f2: max_results = st.slider("최대 표시 개수", 5, 50, 20)
        
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, (name, ticker) in enumerate(stocks_to_scan.items()):
            status_text.text(f"🔎 {name} 분석 중... ({i+1}/{len(stocks_to_scan)})")
            # [수정] 현재가 추출 로직 개선 및 엔진 호환
            df, score, signal, _, _ = analyze_stock(ticker)
            
            if df is not None and score >= min_score:
                curr_price = df['Close'].iloc[-1]
                results.append({
                    "종목명": name,
                    "티커": ticker,
                    "신뢰도": score,
                    "평가": signal,
                    "현재가": f"{int(curr_price):,}원" if ".K" in ticker else f"${curr_price:.2f}"
                })
            progress_bar.progress((i + 1) / len(stocks_to_scan))
        
        status_text.empty()
        if results:
            # 점수 높은 순 정렬 및 절삭
            df_res = pd.DataFrame(results).sort_values(by="신뢰도", ascending=False).head(max_results)
            st.success(f"✅ {market_key} 시장 유망 종목 {len(df_res)}개 발굴!")
            st.dataframe(df_res, use_container_width=True, hide_index=True)
            st.balloons()
        else:
            st.warning(f"⚠️ 현재 {min_score}점 이상인 종목이 없습니다. 점수 문턱을 낮추거나 시장을 변경해 보세요.")
            # [The Closer's Tip] 만약 검색 결과가 0개라면?
            if st.button("🔄 민감도 모드로 재조회 (45점 기준)", use_container_width=True):
                min_score = 45 # 강제 조정 후 재실행 유도
                st.rerun()