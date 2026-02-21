import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from engine import analyze_stock

def run_deepdive_tab(stock_dict):
    st.subheader("🎯 9대 지표 정밀 타격 & 전문가 분석 (Deep Dive)")
    
    # UI 개선: 종목 선택과 실행 버튼을 한 줄에 배치하여 실행력 극대화
    col1, col2 = st.columns([3, 1])
    with col1:
        choice = st.selectbox("분석할 타겟 종목을 선택하십시오", list(stock_dict.keys()), label_visibility="collapsed")
    with col2:
        run_btn = st.button(f"⚡ 즉시 분석 개시", use_container_width=True)
        
    st.markdown("---")
    
    if run_btn:
        ticker = stock_dict[choice]
        
        # 엔진 구동 중 시각적 피드백 제공
        with st.spinner(f"🔥 {choice} ({ticker}) 심장부 데이터를 뜯어보는 중..."):
            df, score, core_msg, analysis, stop_loss_price = analyze_stock(ticker)
        
        if df is not None:
            # 티커를 분석하여 통화 기호 자동 할당 (한국: ₩, 글로벌/코인: $)
            currency = "₩" if ticker.endswith(".KS") or ticker.endswith(".KQ") else "$"
            current_price = df['Close'].iloc[-1]

            # 1. [최상단 배너] 매수/매도/손절 핵심 메시지
            if "적극 매수" in core_msg: st.success(f"🚀 {core_msg}")
            elif "매도/손절" in core_msg: st.error(f"🚨 {core_msg}")
            else: st.warning(f"⚖️ {core_msg}")

            # 2. 스코어 및 손절가 직관적 노출
            st.markdown("### 📊 The Closer's 타격 지표")
            c1, c2, c3 = st.columns(3)
            c1.metric("현재가", f"{currency}{current_price:,.2f}")
            c2.metric("The Closer 종합 점수", f"{score}점")
            c3.metric("기계적 손절가 (ATR 기반)", f"{currency}{stop_loss_price:,.2f}")
            
            st.markdown("---")

            # 3. 지표 상세 브리핑
            st.markdown("### 🧐 9대 지표 심층 분석 리포트")
            for line in analysis:
                st.write(line)

            st.markdown("---")

            # 4. 시각화 (VWAP, 일목구름대, 손절가 라인 탑재)
            st.markdown("### 📈 세력 수급 & 차트 정밀 스캔")
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                               vertical_spacing=0.05, row_heights=[0.5, 0.25, 0.25],
                               subplot_titles=("가격 & VWAP(기관단가) & 일목구름대", "MACD (추세 모멘텀)", "RSI & MFI (투자 심리 및 자금 유입)"))

            # 캔들 & VWAP (노란선)
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="가격"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['vwap'], line=dict(color='yellow', width=2), name="VWAP"), row=1, col=1)

            # 일목균형표 구름대 색칠 (회색 영역)
            fig.add_trace(go.Scatter(x=df.index, y=df['ichi_a'], line=dict(color='rgba(0,0,0,0)'), showlegend=False), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['ichi_b'], fill='tonexty', fillcolor='rgba(128,128,128,0.3)', line=dict(color='rgba(0,0,0,0)'), name="매물대(구름)"), row=1, col=1)

            # 손절가 라인 (붉은 점선)
            fig.add_hline(y=stop_loss_price, line_dash="dash", line_color="red", annotation_text="ATR 손절선", row=1, col=1)

            # MACD
            fig.add_trace(go.Scatter(x=df.index, y=df['macd'], name="MACD", line=dict(color='cyan')), row=2, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['macd_sig'], name="Signal", line=dict(color='magenta')), row=2, col=1)

            # RSI & MFI
            fig.add_trace(go.Scatter(x=df.index, y=df['rsi'], name="RSI", line=dict(color='orange')), row=3, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['mfi'], name="MFI", line=dict(color='lime', dash='dot')), row=3, col=1)

            fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.error(f"❌ 분석 실패: 데이터 수신 에러. ({core_msg})")