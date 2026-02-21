import streamlit as st
import plotly.graph_objects as go
from engine import analyze_stock
from style_utils import apply_global_style

def run_scanner_tab(stock_dict):
    apply_global_style()
    st.markdown("<h1 style='font-weight:800;'>🔍 전문가 종목 정밀 진단</h1>", unsafe_allow_html=True)
    name = st.selectbox("진단할 종목 선택", list(stock_dict.keys()))
    
    if st.button("🔬 전문가 9대 지표 통합 분석 가동", type="primary", use_container_width=True):
        # 엔진 반환값 5개 완벽 수령 (ValueError 해결)
        df, score, msg, details, stop_loss = analyze_stock(stock_dict[name])
        
        if df is not None:
            # 1. 상단 하이라이트: 점수와 단호한 한줄평
            st.markdown(f"#### AI 신뢰 점수: <span style='color:white; font-size:3.2rem; font-weight:800;'>{score}점</span>", unsafe_allow_html=True)
            st.markdown(f"### **{msg}**")
            st.error(f"📍 최종 방어선 (손절가): {int(stop_loss):,}원")
            st.write("---")

            # 2. [핵심 수술] 전문가 의견 + 개별 지표 차트 (Set 구성)
            # 고객 입장에서 '쏠림 현상' 없이 각 지표를 정밀하게 판독하도록 설계
            for item in details:
                col_txt, col_chart = st.columns([1, 1.8])
                
                with col_txt:
                    st.markdown(f"### 📍 {item['title']}")
                    st.write(f"**판독 결과:** {item['res']}")
                    st.info(f"**Closer's View:** {item['view']}")
                
                with col_chart:
                    fig = go.Figure()
                    
                    # 지표 성격에 맞는 차트 구성
                    if "VWAP" in item['title'] or "일목균형표" in item['title']:
                        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'))
                        if "VWAP" in item['title']:
                            fig.add_trace(go.Scatter(x=df.index, y=df['vwap'], name='VWAP', line=dict(color='orange', width=2)))
                        else: # 일목균형표 구름대
                            fig.add_trace(go.Scatter(x=df.index, y=df['ichi_a'], line=dict(width=0), name='A'))
                            fig.add_trace(go.Scatter(x=df.index, y=df['ichi_b'], line=dict(width=0), fill='tonexty', fillcolor='rgba(255, 255, 255, 0.1)', name='B'))
                    
                    elif "RSI" in item['title']:
                        fig.add_trace(go.Scatter(x=df.index, y=df['rsi'], name='RSI', line=dict(color='yellow')))
                        fig.add_hline(y=70, line_dash="dash", line_color="red")
                        fig.add_hline(y=30, line_dash="dash", line_color="blue")
                        fig.update_yaxes(range=[0, 100])

                    fig.update_layout(
                        title=dict(text=f"📊 {item['title']} 판독 차트", x=0.5, font=dict(color="white")),
                        height=350, margin=dict(l=0,r=0,t=50,b=0), xaxis_rangeslider_visible=False, 
                        template="plotly_dark", plot_bgcolor='black', paper_bgcolor='black'
                    )
                    st.plotly_chart(fig, use_container_width=True)
                st.write("---")

            # 3. [쏠림 해결] MACD 추세 에너지 정밀 분석 세트
            st.markdown("### 📊 MACD 추세 에너지 정밀 분석")
            c_txt, c_chart = st.columns([1, 1.8])
            with c_txt:
                st.write("**지표 설명:** 추세의 방향과 변곡점의 에너지를 판독해.")
                st.info("**Closer's View:** 히스토그램이 임계선(빨간/파란 점선)에 닿으면 추세가 과부화되었다는 뜻이야. 곧 반전이 일어날 확률이 90% 이상이지.")
            
            with c_chart:
                fig_macd = go.Figure()
                df['macd_hist'] = df['macd'] - df['macd_sig']
                fig_macd.add_trace(go.Bar(x=df.index, y=df['macd_hist'], name='Energy', marker_color=['#ff3b30' if x > 0 else '#007aff' for x in df['macd_hist']]))
                fig_macd.add_trace(go.Scatter(x=df.index, y=df['macd'], name='MACD Line', line=dict(color='white')))
                
                # [고객 요청] 상한선 및 하한선 임계치 표시 (데이터에 맞춰 자동 스케일링 권장하나 가독성 위해 고정값 예시)
                limit = df['macd'].std() * 2 # 동적 임계치: 표준편차의 2배 적용
                fig_macd.add_hline(y=limit, line_dash="dot", line_color="red", annotation_text="과열 임계치")
                fig_macd.add_hline(y=-limit, line_dash="dot", line_color="blue", annotation_text="침체 임계치")
                
                fig_macd.update_layout(
                    title=dict(text="📈 MACD 에너지 & 임계치 통합 차트", x=0.5, font=dict(color="white")),
                    height=400, margin=dict(l=0,r=0,t=50,b=0), template="plotly_dark", showlegend=False
                )
                st.plotly_chart(fig_macd, use_container_width=True)