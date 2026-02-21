import streamlit as st
import pandas as pd
from engine import analyze_stock

def run_portfolio_tab(stock_dict):
    # 🎯 [신규 기능] 타이틀과 새로고침 버튼을 최상단에 나란히 배치
    col_title, col_refresh = st.columns([4, 1])
    with col_title:
        st.subheader("💼 내 계좌 정밀 진단 (The Closer's Portfolio)")
    with col_refresh:
        st.write("") # 버튼 높이 정렬용
        if st.button("🔄 실시간 데이터 강제 동기화", use_container_width=True):
            st.toast("📡 월스트리트 최신 데이터를 긁어옵니다...", icon="🔥")
            st.rerun() # 엔진 강제 재가동
            
    st.markdown("---")
    
    # 세션 스테이트 초기화
    if 'portfolio' not in st.session_state:
        st.session_state.portfolio = []

    # 1. 다중 입력부 (소수점 입력 완벽 지원)
    with st.expander("➕ 내 보유 종목 일괄 장전 (미장/코인 소수점 지원)", expanded=True):
        st.write("미장 및 암호화폐의 소수점 매매(예: 0.15주)까지 지원합니다. 빈칸을 채우고 **[일괄 장전]**을 누르십시오.")

        if 'input_df' not in st.session_state:
            st.session_state.input_df = pd.DataFrame(
                [{"종목명": "", "매수평단가": 0.0, "보유수량": 0.0} for _ in range(3)]
            )

        # 데이터 에디터
        edited_df = st.data_editor(
            st.session_state.input_df,
            num_rows="dynamic",
            column_config={
                "종목명": st.column_config.SelectboxColumn(
                    "종목명 (클릭하여 선택)", options=[""] + list(stock_dict.keys()), required=True
                ),
                "매수평단가": st.column_config.NumberColumn("매수 평단가 (원/$)", min_value=0.0, format="%.2f"),
                "보유수량": st.column_config.NumberColumn("보유 수량", min_value=0.0000, step=0.01, format="%.4f")
            },
            use_container_width=True,
            key="portfolio_editor"
        )

        if st.button("🔥 포트폴리오 일괄 장전"):
            added_count = 0
            for index, row in edited_df.iterrows():
                name = row["종목명"]
                price = row["매수평단가"]
                qty = row["보유수량"]

                if pd.isna(name) or name == "" or price <= 0 or qty <= 0:
                    continue

                if any(item['name'] == name for item in st.session_state.portfolio):
                    st.warning(f"⚠️ {name}은(는) 이미 장전되어 있습니다. 하단에서 삭제 후 다시 등록하십시오.")
                    continue

                st.session_state.portfolio.append({
                    'name': name,
                    'ticker': stock_dict[name],
                    'avg_price': float(price),
                    'qty': float(qty)
                })
                added_count += 1

            if added_count > 0:
                st.success(f"✅ {added_count}개 종목 장전 완료!")
                st.session_state.input_df = pd.DataFrame([{"종목명": "", "매수평단가": 0.0, "보유수량": 0.0} for _ in range(3)])
                st.rerun()
            else:
                st.error("새로 장전할 유효한 종목이 없습니다. 종목명, 평단가, 수량을 정확히 입력하십시오.")

    # 2. 실시간 계좌 현황 및 9대 지표 정밀 진단
    st.write("### 📊 실시간 계좌 현황 및 9대 지표 정밀 진단")
    
    if not st.session_state.portfolio:
        st.info("현재 장전된 종목이 없습니다. 위 표에서 종목을 입력하고 장전하십시오.")
        return

    for idx, item in enumerate(st.session_state.portfolio):
        name = item['name']
        ticker = item['ticker']
        avg_p = item['avg_price']
        qty = item['qty']

        with st.container():
            st.markdown(f"#### 🎯 {name} (나의 평단가: {avg_p:,.2f} / 수량: {qty:,.4f})")
            
            with st.spinner(f"{name} 실시간 엔진 구동 중..."):
                result = analyze_stock(ticker)
                
            if result and len(result) == 5 and result[0] is not None:
                df, score, core_msg, analysis, stop_loss_price = result
                current_price = df.iloc[-1]['Close']
                currency = "$" if ".KS" not in ticker and ".KQ" not in ticker else "₩"
                
                # 수익률 및 평가금액 자동 계산
                return_rate = ((current_price - avg_p) / avg_p) * 100
                total_value = current_price * qty
                profit_loss = (current_price - avg_p) * qty
                
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("현재가", f"{currency}{current_price:,.2f}")
                c2.metric("나의 평단가", f"{currency}{avg_p:,.2f}")
                c3.metric("수익률", f"{return_rate:,.2f}%", delta=f"{return_rate:,.2f}%")
                c4.metric("평가 손익", f"{currency}{profit_loss:,.2f}", delta=f"{profit_loss:,.2f}")
                c5.metric("총 평가금액", f"{currency}{total_value:,.2f}")

                st.markdown("---")

                col_action, col_deepdive = st.columns([1, 1.5])
                
                with col_action:
                    st.write("##### ⚡ The Closer's Action Plan")
                    if return_rate < 0:
                        if current_price < stop_loss_price:
                            st.error(f"🚨 [기계적 손절 발동] 현재 {return_rate:,.2f}% 손실. 기계적 손절가({stop_loss_price:,.2f}) 붕괴. 즉시 전량 매도하여 계좌를 지키십시오.")
                        elif score >= 65:
                            st.info(f"⚖️ [기회의 물타기] 손실 중이나 9대 지표({score}점)가 매수를 외칩니다. 평단가를 낮출 강력한 기회입니다.")
                        else:
                            st.warning(f"⏳ [관망] 손실 중이나 손절가 방어 중. 추가 매수 없이 대기하십시오.")
                    else:
                        if score < 40:
                            st.success(f"💰 [전량 익절 권장] {return_rate:,.2f}% 수익! 지표가 무너지고 있습니다({score}점). 꼭지에서 팔 생각 말고 당장 수익 확정하십시오.")
                        elif df.iloc[-1]['rsi'] > 75:
                            st.warning(f"🔥 [부분 익절] 강력한 수익 구간이나 단기 과열(RSI 75 초과) 상태입니다. 절반 익절 후 나머지만 들고 가십시오.")
                        else:
                            st.success(f"🚀 [강력 홀딩] 완벽한 추세 탑승! 아직 매도 신호가 없으니 랠리를 끝까지 쥐어짜십시오.")
                            
                    st.metric("기계적 손절가 (ATR 기반)", f"{currency}{stop_loss_price:,.2f}")

                with col_deepdive:
                    st.write("##### 🧐 9대 지표 심층 분석 리포트")
                    for line in analysis:
                        st.write(line)

                _, del_col = st.columns([8, 1])
                with del_col:
                    if st.button(f"🗑️ 삭제", key=f"del_{idx}"):
                        st.session_state.portfolio.pop(idx)
                        st.rerun()
            else:
                st.error(f"❌ {name} 실시간 데이터를 불러오지 못했습니다.")
        st.markdown("<br><br>", unsafe_allow_html=True)