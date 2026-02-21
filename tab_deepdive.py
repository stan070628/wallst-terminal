import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from engine import analyze_stock

def run_deepdive_tab(stock_dict):
    st.subheader("🎯 9대 지표 정밀 타격 & 전문가 분석 (Deep Dive)")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        choice = st.selectbox("분석할 타겟 종목을 선택하십시오", list(stock_dict.keys()), label_visibility="collapsed")
    with col2:
        run_btn = st.button(f"⚡ 즉시 분석 개시", use_container_width=True)
        
    st.markdown("---")
    
    if run_btn:
        ticker = stock_dict[choice]
        with st.spinner(f"🔥 {choice} ({ticker}) 심장부 데이터를 뜯어보는 중..."):
            # [수정] 엔진 반환값 5개 명칭 동기화 (details 수령)
            df, score, core_msg, details, stop_loss_price = analyze_stock(ticker)
        
        if df is not None:
            currency = "₩" if ticker.endswith(".KS") or ticker.endswith(".KQ") else "$"
            current_price = df['Close'].iloc[-1]

            if score >= 80: st.success(f"🚀 {core_msg}")
            elif score <= 40: st.error(f"🚨 {core_msg}")
            else: st.warning(f"⚖️ {core_msg}")

            st.markdown("### 📊 The Closer's 타격 지표")
            c1, c2, c3 = st.columns(3)
            c1.metric("현재가", f"{currency}{current_price:,.2f}")
            c2.metric("The Closer 종합 점수", f"{score}점")
            c3.metric("기계적 손절가", f"{currency}{stop_loss_price:,.2f}")
            
            st.markdown("---")

            # [수정] details 객체를 활용한 전문가 리포트 출력
            st.markdown("### 🧐 9대 지표 심층 분석 리포트")
            for item in details:
                with st.expander(f"📍 {item['title']}", expanded=True):
                    st.info(f"**Expert View:** {item['full_comment']}")

            st.markdown("---")

            # 4. 시각화 (기존 로직 유지하되 지표 일관성 확보)
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                               vertical_spacing=0.05, row_heights=[0.5, 0.25, 0.25],
                               subplot_titles=("가격 & VWAP & 일목구름대", "MACD (추세 에너지)", "RSI & MFI (심리 및 자금)"))

            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="가격"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['vwap'], line=dict(color='yellow', width=2), name="VWAP"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['ichi_a'], line=dict(width=0), showlegend=False), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['ichi_b'], fill='tonexty', fillcolor='rgba(128,128,128,0.3)', line=dict(width=0), name="구름대"), row=1, col=1)
            fig.add_hline(y=stop_loss_price, line_dash="dash", line_color="red", row=1, col=1)

            fig.add_trace(go.Scatter(x=df.index, y=df['macd'], name="MACD", line=dict(color='cyan')), row=2, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['macd_sig'], name="Signal", line=dict(color='magenta')), row=2, col=1)

            fig.add_trace(go.Scatter(x=df.index, y=df['rsi'], name="RSI", line=dict(color='orange')), row=3, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['mfi'], name="MFI", line=dict(color='lime', dash='dot')), row=3, col=1)

            fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error(f"❌ 분석 실패: {core_msg}")