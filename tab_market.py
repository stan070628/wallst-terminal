import streamlit as st
import pandas as pd
from engine import analyze_stock
from stocks import STOCK_DICT
from style_utils import apply_global_style

def run_market_tab(unused_stock_dict):
    apply_global_style()
    st.markdown("<h1 style='color:white;'>🔥 시장 전수조사 (200+ 스캔 모드)</h1>", unsafe_allow_html=True)
    
    # [시장 선택]
    market_choice = st.radio(
        "📊 스캔할 시장을 선택하십시오", 
        ["🇰🇷 KOSPI (200)", "🇰🇷 KOSDAQ (200)", "🌎 GLOBAL"],
        horizontal=True
    )
    
    # 선택된 시장의 딕셔너리 추출
    market_key = "KOSPI" if "KOSPI" in market_choice else "KOSDAQ" if "KOSDAQ" in market_choice else "GLOBAL"
    target_market = STOCK_DICT.get(market_key, {})

    st.write("---")
    max_scan = st.slider("최대 스캔 개수", 10, 200, 200)  # 기본값을 200으로 설정

    if st.button(f"🚀 {market_choice} 스캔 시작", use_container_width=True, type="primary"):
        results = []

        # [The Closer's 강력한 시장 필터링]
        filtered_items = []
        for name, code in target_market.items():
            code_upper = code.upper()
            # 1. KOSPI를 선택했는데 꼬리가 .KS가 아니면 가차없이 버림
            if "KOSPI" in market_choice and not code_upper.endswith(".KS"):
                continue
            # 2. KOSDAQ을 선택했는데 꼬리가 .KQ가 아니면 가차없이 버림
            elif "KOSDAQ" in market_choice and not code_upper.endswith(".KQ"):
                continue
            # 3. GLOBAL은 필터 없이 통과

            filtered_items.append((name, code))

        # 오염된 데이터를 걸러낸 순도 100%의 리스트로만 스캔 진행
        items = filtered_items[:max_scan]

        prog = st.progress(0)
        status_text = st.empty()
        
        # [The Closer's High-Speed Loop]
        for idx, (name, code) in enumerate(items):
            status_text.text(f"🔎 분석 중 [{idx+1}/{len(items)}]: {name}")
            try:
                # engine.py의 analyze_stock 함수 활용
                result = analyze_stock(code)
                if result:
                    df, score, signal, _, _ = result
                    if not df.empty:
                        curr_price = df['Close'].iloc[-1]
                        results.append({
                            "종목명": name,
                            "티커": code,
                            "신뢰도": score,
                            "평가": signal,
                            "현재가": f"{int(curr_price):,}원" if ".K" in code else f"${curr_price:.2f}"
                        })
            except:
                continue  # 한 종목 에러나도 멈추지 않고 전진
            
            prog.progress((idx + 1) / len(items))
        
        status_text.empty()
        
        if results:
            df_res = pd.DataFrame(results).sort_values(by="신뢰도", ascending=False)
            st.success(f"✅ {len(df_res)}개 종목 스캔 완료!")
            st.dataframe(df_res, use_container_width=True, hide_index=True)
            st.balloons()
        else:
            st.error("❌ 분석 결과가 없습니다.")

