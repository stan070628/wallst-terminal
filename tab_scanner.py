import streamlit as st
import pandas as pd
from engine import analyze_stock

def run_scanner_tab(stock_dict):
    st.subheader("🔍 시장별 전수조사 스캐너 (The Closer's Scanner)")
    market = st.radio("시장 선택", ["KOSPI", "KOSDAQ", "NASDAQ & BITCOIN"], horizontal=True)
    
    if st.button(f"🔥 {market} 전수조사 및 타겟 발굴"):
        # 1. 시장별 필터링
        targets = {k: v for k, v in stock_dict.items() if (
            v.endswith(".KS") if market == "KOSPI" else
            v.endswith(".KQ") if market == "KOSDAQ" else
            (".KS" not in v and ".KQ" not in v)
        )}
        
        results = []
        prog_bar = st.progress(0)
        status_text = st.empty()
        
        # 2. 전수조사 엔진 가동
        for i, (name, ticker) in enumerate(targets.items()):
            try:
                status_text.text(f"📡 스캔 중: {name} ({ticker})...")
                
                # [수정 핵심] 엔진이 뱉는 5개의 변수를 모두 받아줌 (안 쓰는 건 _ 처리)
                # 데이터, 점수, 핵심메시지, 상세분석, 손절가
                _, score, comment, _, _ = analyze_stock(ticker)
                
                if score is not None:
                    results.append({
                        "종목명": name, 
                        "티커": ticker,
                        "점수": score, 
                        "분석 결과": comment
                    })
            except Exception as e:
                # 개별 종목 에러 시 멈추지 않고 다음 종목으로 패스 (실행력 강조)
                continue
                
            prog_bar.progress((i + 1) / len(targets))
        
        status_text.empty() # 스캔 완료 후 텍스트 제거
        
        # 3. 결과 아웃풋 처리
        if results:
            df_res = pd.DataFrame(results).sort_values(by="점수", ascending=False)
            
            st.markdown("### 🏆 실시간 타격 타겟 Top 15")
            
            # 점수에 따라 색상 하이라이트 적용 (가독성 극대화)
            def highlight_score(val):
                color = 'red' if val >= 70 else 'orange' if val >= 50 else 'white'
                return f'color: {color}; font-weight: bold'

            styled_df = df_res.head(15).style.applymap(highlight_score, subset=['점수'])
            st.dataframe(styled_df, use_container_width=True)
            
            # 요약 통계
            st.info(f"✅ 스캔 완료! 총 {len(targets)}개 종목 중 점수가 높은 상위 종목들을 우선적으로 검토하십시오.")
        else:
            st.error("❌ 유효한 데이터를 수집하지 못했습니다. 시장 데이터 연결 상태를 확인하십시오.")