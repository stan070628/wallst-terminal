import streamlit as st
from portfolio_manager import load_portfolio, save_portfolio
from engine import analyze_stock 
from style_utils import apply_global_style

@st.dialog("🔬 AI 전문가 통합 진단 보고서")
def show_expert_popup(stock):
    apply_global_style() # 팝업 내 가독성 강제 적용
    df, score, signal, details, stop_loss = analyze_stock(stock['ticker'])
    
    if df is not None:
        curr_p = int(df['Close'].iloc[-1])
        profit = ((curr_p - stock['avg_price']) / stock['avg_price']) * 100
        p_color = "up" if profit >= 0 else "down"
        
        st.markdown(f"<h2 style='font-weight:800; color:white;'>{stock['name']} 전문가 제언</h2>", unsafe_allow_html=True)
        m1, m2, m3 = st.columns(3)
        with m1: st.markdown(f"<div class='m-card'><div style='color:gray; font-size:0.8rem;'>내 평단</div><div class='m-value'>{stock['avg_price']:,}원</div></div>", unsafe_allow_html=True)
        with m2: st.markdown(f"<div class='m-card'><div style='color:gray; font-size:0.8rem;'>현재가</div><div class='m-value {p_color}'>{curr_p:,}원<br><small>{profit:+.2f}%</small></div></div>", unsafe_allow_html=True)
        with m3: st.markdown(f"<div class='m-card'><div style='color:gray; font-size:0.8rem;'>AI 점수</div><div class='m-value' style='color:white;'>{score}점</div></div>", unsafe_allow_html=True)
        
        st.write("---")
        # 심층 리포트 출력 (생략 가능하나 가독성을 위해 간략히 노출)
        st.markdown(f"#### 🚩 **{signal}**")
        for item in details:
            st.markdown(f"📍 **{item['title']}**<br><span style='font-size:0.85rem; color:#8e8e93;'>{item['view']}</span>", unsafe_allow_html=True)
    else: st.error("데이터 로드 실패")

def run_portfolio_tab(stock_dict):
    apply_global_style()
    st.markdown("<h1 style='color:white; font-weight:800;'>📊 내 계좌 정밀 진단</h1>", unsafe_allow_html=True)
    if 'my_stocks' not in st.session_state: st.session_state.my_stocks = load_portfolio(st.session_state.user_id)

    for idx, stock in enumerate(reversed(st.session_state.my_stocks)):
        actual_idx = len(st.session_state.my_stocks) - 1 - idx
        with st.container(border=True):
            _, score, msg, _, _ = analyze_stock(stock['ticker'])
            c1, c2, c3, c4 = st.columns([1.5, 3.2, 1.2, 0.5])
            with c1: 
                if st.button(f"🔍 {stock['name']}", key=f"b_{actual_idx}", use_container_width=True): show_expert_popup(stock)
            with c2: 
                # [복원] 점수와 한줄평 표시
                st.markdown(f"<span style='color:#888;'>[{score}점]</span> **{msg}**", unsafe_allow_html=True)
            with c3: st.write(f"**{stock['avg_price']:,}원**")
            with c4:
                if st.button("🗑️", key=f"d_{actual_idx}"):
                    st.session_state.my_stocks.pop(actual_idx)
                    save_portfolio(st.session_state.user_id, st.session_state.my_stocks)
                    st.rerun()