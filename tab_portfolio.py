import streamlit as st
from portfolio_manager import load_portfolio, save_portfolio
from engine import analyze_stock 
from style_utils import apply_global_style

@st.dialog("🔬 AI 전문가 통합 진단 보고서")
def show_expert_popup(stock):
    apply_global_style()
    # 엔진 v4.0 규격 준수
    df, score, msg, details, stop_loss = analyze_stock(stock['ticker'])
    
    if df is not None:
        curr_p = int(df['Close'].iloc[-1])
        quantity = stock.get('quantity', 0) # 보유좌수 가져오기
        total_buy = stock['avg_price'] * quantity
        total_val = curr_p * quantity
        profit = ((curr_p - stock['avg_price']) / stock['avg_price']) * 100
        p_color = "up" if profit >= 0 else "down"
        
        st.markdown(f"<h2 style='font-weight:800; color:white;'>{stock['name']} 자산 리포트</h2>", unsafe_allow_html=True)
        
        # 1열: 가격 정보 / 2열: 수량 및 금액 / 3열: AI 점수
        m1, m2, m3 = st.columns(3)
        with m1: 
            st.markdown(f"<div class='m-card'><div style='color:gray; font-size:0.8rem;'>수익률</div><div class='m-value {p_color}'>{profit:+.2f}%</div></div>", unsafe_allow_html=True)
        with m2: 
            st.markdown(f"<div class='m-card'><div style='color:gray; font-size:0.8rem;'>평가금액</div><div class='m-value'>{total_val:3,}원</div></div>", unsafe_allow_html=True)
        with m3: 
            st.markdown(f"<div class='m-card'><div style='color:gray; font-size:0.8rem;'>AI 점수</div><div class='m-value' style='color:white;'>{score}점</div></div>", unsafe_allow_html=True)
        
        st.write("---")
        st.markdown(f"#### 🚩 **{msg}**")
        st.caption(f"보유수량: {quantity:,}주 | 총 투자금: {total_buy:,}원")
        for item in details:
            st.markdown(f"📍 **{item['title']}**<br><span style='font-size:0.85rem; color:#8e8e93;'>{item['view']}</span>", unsafe_allow_html=True)
    else: st.error("데이터 로드 실패")

def run_portfolio_tab(stock_dict):
    apply_global_style()
    st.markdown("<h1 style='color:white; font-weight:800;'>📊 내 계좌 정밀 진단</h1>", unsafe_allow_html=True)
    
    if 'my_stocks' not in st.session_state:
        st.session_state.my_stocks = load_portfolio(st.session_state.user_id)

    # --- 1. [상시 노출] 신규 종목 등록 섹션 (보유좌수 추가) ---
    with st.container(border=True):
        st.markdown("### ➕ 분석 종목 신규 등록")
        c1, c2, c3, c4 = st.columns([2, 1.2, 1.2, 0.8])
        with c1:
            new_name = st.selectbox("종목 선택", list(stock_dict.keys()), key="reg_name")
        with c2:
            new_price = st.number_input("평균 매수가 (원)", min_value=0, step=100, key="reg_price")
        with c3:
            # [핵심 추가] 보유좌수 입력칸
            new_qty = st.number_input("보유좌수 (주)", min_value=0, step=1, key="reg_qty")
        with c4:
            st.write(" ") # 수직 정렬용
            if st.button("등록", type="primary", use_container_width=True):
                new_item = {
                    "name": new_name, 
                    "ticker": stock_dict[new_name], 
                    "avg_price": new_price,
                    "quantity": new_qty # 수량 저장
                }
                st.session_state.my_stocks.append(new_item)
                save_portfolio(st.session_state.user_id, st.session_state.my_stocks)
                st.rerun()

    st.write("---")

    # --- 2. 내 종목 리스트 ---
    if not st.session_state.my_stocks:
        st.info("현재 등록된 종목이 없습니다. 위 등록 섹션에서 종목을 추가하십시오.")
    else:
        for idx, stock in enumerate(reversed(st.session_state.my_stocks)):
            actual_idx = len(st.session_state.my_stocks) - 1 - idx
            with st.container(border=True):
                _, score, msg, _, _ = analyze_stock(stock['ticker'])
                qty = stock.get('quantity', 0)
                
                c1, c2, c3, c4 = st.columns([1.5, 3.0, 1.5, 0.5])
                with c1: 
                    if st.button(f"🔍 {stock['name']}", key=f"b_{actual_idx}", use_container_width=True): 
                        show_expert_popup(stock)
                with c2: 
                    st.markdown(f"<span style='color:#888;'>[{score}점]</span> **{msg}**", unsafe_allow_html=True)
                with c3: 
                    st.write(f"**{stock['avg_price']:,}원**")
                    st.caption(f"{qty:,}주 보유 중")
                with c4:
                    if st.button("🗑️", key=f"d_{actual_idx}"):
                        st.session_state.my_stocks.pop(actual_idx)
                        save_portfolio(st.session_state.user_id, st.session_state.my_stocks)
                        st.rerun()