import streamlit as st
import pandas as pd
from portfolio_manager import load_portfolio, save_portfolio
# engine.py에서 정의된 정확한 함수명을 가져옵니다.
from engine import analyze_stock 

def run_portfolio_tab(stock_dict):
    st.header("📊 내 계좌 정밀 진단")
    st.write("---")

    if 'my_stocks' not in st.session_state:
        st.session_state.my_stocks = load_portfolio()

    # [1] 종목 추가 UI (기존 로직 유지)
    with st.expander("➕ 내 종목 추가하기", expanded=True):
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            selected_name = st.selectbox("분석할 종목 선택", list(stock_dict.keys()))
        with col2:
            avg_price = st.number_input("매수 평단가 (원)", min_value=0, value=0, step=100)
        with col3:
            quantity = st.number_input("보유 수량", min_value=0.0, value=0.0, step=1.0)

        if st.button("🚀 종목 등록 및 영구 저장", use_container_width=True):
            if quantity > 0:
                new_item = {
                    "name": selected_name,
                    "ticker": stock_dict[selected_name],
                    "avg_price": avg_price,
                    "quantity": quantity
                }
                st.session_state.my_stocks.append(new_item)
                save_portfolio(st.session_state.my_stocks)
                st.success(f"✅ {selected_name} 등록 완료!")
                st.rerun()

    # [2] 현재 내 포트폴리오 리스트
    st.subheader("📂 현재 내 포트폴리오")
    if not st.session_state.my_stocks:
        st.info("등록된 종목이 없습니다.")
    else:
        for idx, stock in enumerate(reversed(st.session_state.my_stocks)):
            actual_idx = len(st.session_state.my_stocks) - 1 - idx
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([1.5, 1, 1, 0.5])
                with c1: st.write(f"**{stock['name']}**"); st.caption(f"티커: {stock['ticker']}")
                with c2: st.write(f"평단: {stock['avg_price']:,}원")
                with c3: st.write(f"수량: {stock['quantity']:,}주")
                with c4:
                    if st.button("🗑️", key=f"del_{actual_idx}"):
                        st.session_state.my_stocks.pop(actual_idx); save_portfolio(st.session_state.my_stocks); st.rerun()

        # [3] 통합 스캔 로직 (engine.py 연동 완료)
        st.write("---")
        if st.button("🔍 전체 포트폴리오 9대 지표 통합 스캔 시작", type="primary", use_container_width=True):
            with st.status("🚀 전 종목 정밀 분석 중...", expanded=True) as status:
                results_data = []
                for stock in st.session_state.my_stocks:
                    st.write(f"🔎 {stock['name']} 분석 중...")
                    
                    # engine.py의 analyze_stock 함수 호출
                    # 반환값: data(df), score(float), core_msg(str), analysis(list), stop_loss_price(float)
                    res_df, score, signal, analysis_list, stop_loss = analyze_stock(stock['ticker'])
                    
                    if res_df is not None and not res_df.empty:
                        # 현재가 추출 (데이터프레임의 마지막 종가)
                        current_price = int(res_df.iloc[-1]['Close'])
                        # 수익률 계산
                        profit_pct = ((current_price - stock['avg_price']) / stock['avg_price'] * 100) if stock['avg_price'] > 0 else 0
                        
                        results_data.append({
                            "종목명": stock['name'],
                            "현재가": f"{current_price:,}원",
                            "수익률": f"{profit_pct:+.2f}%",
                            "AI 점수": f"{score}점",
                            "투자의견": signal,
                            "수학적 손절가": f"{int(stop_loss):,}원"
                        })
                    else:
                        results_data.append({
                            "종목명": stock['name'],
                            "현재가": "N/A", "수익률": "N/A", "AI 점수": "0점",
                            "투자의견": "데이터 오류", "수학적 손절가": "N/A"
                        })
                status.update(label="✅ 분석 완료!", state="complete", expanded=False)
            
            # 분석 결과 표 출력
            st.subheader("📋 통합 진단 결과 리포트")
            if results_data:
                df_res = pd.DataFrame(results_data)
                # 인덱스 없이 깔끔하게 표로 출력
                st.dataframe(df_res, use_container_width=True, hide_index=True)
                
                # 추가 조언 (ENTP 스탠을 위한 핵심 요약)
                st.info("💡 **Closer's Tip:** '적극 매수' 신호가 뜬 종목 중 수익률이 마이너스라면 물타기 적기이며, '탈출' 신호가 뜬 종목은 손절가를 반드시 준수하십시오.")