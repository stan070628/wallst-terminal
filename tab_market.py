import streamlit as st
import pandas as pd
from engine import analyze_stock
from style_utils import apply_global_style

def run_market_tab(stock_dict):
    apply_global_style()
    st.markdown("<h1 style='color:white; font-weight:800;'>🔥 시장 전수조사</h1>", unsafe_allow_html=True)
    
    # 시장 선택 (버튼 키 충돌 해결)
    col1, col2, col3 = st.columns(3)
    with col1:
        kospi_btn = st.button("🇰🇷 KOSPI 전수조사", use_container_width=True, key="btn_kospi")
    with col2:
        kosdaq_btn = st.button("🇰🇷 KOSDAQ 전수조사", use_container_width=True, key="btn_kosdaq")
    with col3:
        global_btn = st.button("🇺🇸 GLOBAL 전수조사", use_container_width=True, key="btn_global")
    
    target = None
    if kospi_btn:
        target = ".KS"
    elif kosdaq_btn:
        target = ".KQ"
    elif global_btn:
        target = "GLOBAL"

    if target:
        # 필터링 로직 개선 (명확하게)
        if target == "GLOBAL":
            stocks_to_scan = [k for k, v in stock_dict.items() if ".K" not in v]
        else:
            stocks_to_scan = [k for k, v in stock_dict.items() if target in v]
        
        # 사용자 맞춤 필터 옵션
        st.write("---")
        col_filter1, col_filter2, col_filter3 = st.columns(3)
        with col_filter1:
            min_score = st.slider("최소 신뢰도 점수", 0, 100, 70, key="min_score")
        with col_filter2:
            sort_by = st.selectbox("정렬 기준", ["점수 (높음순)", "점수 (낮음순)", "가격 (높음순)", "가격 (낮음순)"], key="sort_by")
        with col_filter3:
            max_results = st.slider("최대 표시 개수", 5, 100, 50, key="max_results")
        
        st.write("---")
        
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 분석 실행
        for i, name in enumerate(stocks_to_scan):
            try:
                ticker = stock_dict[name]
                status_text.text(f"🔎 {name} 정밀 판독 중... ({i+1}/{len(stocks_to_scan)})")
                
                df, score, signal, _, _ = analyze_stock(ticker)
                
                # 데이터 로드 성공 여부 확인
                if df is not None and score is not None:
                    curr_price = df['Close'].iloc[-1]
                    prev_price = df['Close'].iloc[-2] if len(df) > 1 else curr_price
                    change_rate = ((curr_price - prev_price) / prev_price * 100) if prev_price != 0 else 0
                    
                    if score >= min_score:
                        results.append({
                            "종목명": name,
                            "신뢰도": f"{int(score)}점",
                            "평가": signal,
                            "현재가": f"{int(curr_price):,}원",
                            "변화율": f"{change_rate:+.2f}%",
                            "거래량": f"{int(df['Volume'].iloc[-1]/(1e6)):,.0f}M"
                        })
            except Exception as e:
                # 개별 종목 분석 실패 시 계속 진행
                continue
            
            progress_bar.progress((i + 1) / len(stocks_to_scan))
        
        status_text.empty()
        progress_bar.empty()
        
        # 결과 정렬
        if results:
            if sort_by == "점수 (높음순)":
                results = sorted(results, key=lambda x: int(x['신뢰도'].replace('점', '')), reverse=True)
            elif sort_by == "점수 (낮음순)":
                results = sorted(results, key=lambda x: int(x['신뢰도'].replace('점', '')))
            elif sort_by == "가격 (높음순)":
                results = sorted(results, key=lambda x: int(x['현재가'].replace('원', '').replace(',', '')), reverse=True)
            elif sort_by == "가격 (낮음순)":
                results = sorted(results, key=lambda x: int(x['현재가'].replace('원', '').replace(',', '')))
            
            # 최대 개수로 제한
            results = results[:max_results]
            
            st.success(f"✅ 조건에 부합하는 유망 종목 {len(results)}개 발굴 완료!")
            
            # 데이터프레임 표시
            df_results = pd.DataFrame(results)
            st.dataframe(df_results, use_container_width=True, hide_index=True)
            
            # 추가 정보: 시장 요약
            st.write("---")
            col_summary1, col_summary2, col_summary3 = st.columns(3)
            with col_summary1:
                st.metric("조사 대상 종목", len(stocks_to_scan))
            with col_summary2:
                st.metric("조건 부합 종목", len(results), f"({min_score}점 이상)")
            with col_summary3:
                success_rate = (len(results) / len(stocks_to_scan) * 100) if stocks_to_scan else 0
                st.metric("성공률", f"{success_rate:.1f}%")
        else:
            st.warning(f"⚠️ 신뢰도 {min_score}점 이상인 유망 종목이 없습니다. 기준을 낮춰보세요.")