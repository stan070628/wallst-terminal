import streamlit as st
import plotly.graph_objects as go
from engine import analyze_stock
from market_data import get_all_krx_stocks
from style_utils import apply_global_style

def run_scanner_tab(unused_stock_dict):
    apply_global_style()
    
    # 고급 스타일링
    st.markdown("""
    <style>
        .score-badge-excellent { background-color: #ff3b30; padding: 4px 10px; border-radius: 6px; color: white; font-weight: bold; font-size: 1.1rem; }
        .score-badge-good { background-color: #ff9500; padding: 4px 10px; border-radius: 6px; color: white; font-weight: bold; font-size: 1.1rem; }
        .score-badge-neutral { background-color: #5ac8fa; padding: 4px 10px; border-radius: 6px; color: white; font-weight: bold; font-size: 1.1rem; }
        .score-badge-poor { background-color: #4cd964; padding: 4px 10px; border-radius: 6px; color: white; font-weight: bold; font-size: 1.1rem; }
        .metric-card { text-align: center; padding: 18px; background: linear-gradient(135deg, #1a1a1a 0%, #262626 100%); border-radius: 10px; border: 1px solid #333; box-shadow: 0 4px 8px rgba(0,0,0,0.3); }
        .metric-label { color: #888; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }
        .metric-value { color: white; font-size: 2rem; font-weight: 800; }
        .section-title { border-bottom: 3px solid #ff9500; padding-bottom: 10px; margin-top: 25px; margin-bottom: 15px; }
        .status-good { background-color: rgba(76, 217, 100, 0.1); border-left: 4px solid #4cd964; padding: 15px; border-radius: 8px; }
        .status-warning { background-color: rgba(255, 149, 0, 0.1); border-left: 4px solid #ff9500; padding: 15px; border-radius: 8px; }
        .status-danger { background-color: rgba(255, 59, 48, 0.1); border-left: 4px solid #ff3b30; padding: 15px; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)
    
    # 헤더
    col_header = st.columns([1])[0]
    st.markdown("## 🔍 전문가 종목 정밀 진단", unsafe_allow_html=False)
    st.caption("**The Closer's AI 분석엔진** — 9대 기술지표 통합 진단 (가격·수급·시장심리·자금흐름)")
    
    st.markdown("---")
    
    # 입력 섹션
    col_input1, col_input2 = st.columns([2, 1.2])
    
    with col_input1:
        search_mode = st.radio("📊 분석 시장 선택", ["🇰🇷 국내 주식", "🌎 글로벌 자산"], horizontal=True, label_visibility="collapsed")
    
    if search_mode == "🇰🇷 국내 주식":
        all_stocks = get_all_krx_stocks()
        target_name = st.selectbox("📌 종목 검색", list(all_stocks.keys()), key="krx_select")
        target_ticker = all_stocks[target_name]
    else:
        target_ticker = st.text_input("💱 글로벌 티커 입력", value="AAPL", placeholder="AAPL, TSLA, BTC-USD").strip().upper()
        target_name = target_ticker

    with col_input2:
        pass
    
    # 분석 버튼
    col_btn = st.columns([1])[0]
    btn_analyze = st.button(f"🚀 {target_name} 분석 시작", type="primary", use_container_width=True, help="9대 지표 통합 분석 시작 (5-10초)")
    
    if btn_analyze:
        # 로딩 애니메이션
        progress_placeholder = st.empty()
        progress_placeholder.info("🔄 분석 중... 데이터 수집 → 지표 계산 → 신호 생성")
        
        df, score, msg, details, stop_loss = analyze_stock(target_ticker)
        progress_placeholder.empty()
        
        if df is not None:
            # 신뢰도 레벨 결정
            if score >= 75:
                score_badge = f"<span class='score-badge-excellent'>{score}점 🔥</span>"
                level_color = "🔴"
                status_class = "status-danger"
            elif score >= 55:
                score_badge = f"<span class='score-badge-good'>{score}점 ⚖️</span>"
                level_color = "🟡"
                status_class = "status-warning"
            elif score >= 40:
                score_badge = f"<span class='score-badge-neutral'>{score}점 ❄️</span>"
                level_color = "🔵"
                status_class = "status-warning"
            else:
                score_badge = f"<span class='score-badge-poor'>{score}점 ⛔</span>"
                level_color = "🟢"
                status_class = "status-good"
            
            # 메트릭 대시보드
            st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
            
            m1, m2, m3, m4 = st.columns(4, gap="medium")
            
            with m1:
                st.markdown(f"""<div class='metric-card'>
                <div class='metric-label'>🎯 AI 신뢰도</div>
                <div class='metric-value'>{score_badge}</div>
                </div>""", unsafe_allow_html=True)
            
            with m2:
                current_price = int(df['Close'].iloc[-1]) if df['Close'].iloc[-1] > 100 else round(df['Close'].iloc[-1], 2)
                st.markdown(f"""<div class='metric-card'>
                <div class='metric-label'>💹 현재가</div>
                <div class='metric-value' style='font-size: 1.8rem;'>{current_price:,}</div>
                </div>""", unsafe_allow_html=True)
            
            with m3:
                stop_loss_val = int(stop_loss) if stop_loss > 100 else round(stop_loss, 2)
                st.markdown(f"""<div class='metric-card'>
                <div class='metric-label'>🛑 손절가</div>
                <div class='metric-value' style='color: #ff3b30; font-size: 1.8rem;'>{stop_loss_val:,}</div>
                </div>""", unsafe_allow_html=True)
            
            with m4:
                st.markdown(f"""<div class='metric-card'>
                <div class='metric-label'>⚡ 판정</div>
                <div class='metric-value' style='font-size: 2.5rem;'>{level_color}</div>
                </div>""", unsafe_allow_html=True)
            
            # AI 판정
            st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='{status_class}'><b>🤖 The Closer's 최종 판정:</b> {msg}</div>", unsafe_allow_html=True)
            
            st.markdown(f"---")
            st.markdown(f"**📊 엔진 판정:** {msg}")
            
            # 나머지 분석 결과...
            for item in details:
                st.write(f"**{item['title']}**")
                st.caption(item['full_comment'])
        else:
            st.error(f"❌ '{target_name}' 분석 실패\n데이터를 확인하고 다시 시도해주세요.")
        
        if df is not None:
            # 상단 핵심 배너
            st.markdown(f"#### {target_name} AI 신뢰 점수: <span style='color:white; font-size:3.2rem; font-weight:800;'>{score}점</span>", unsafe_allow_html=True)
            st.error(f"📍 최종 방어선 (손절가): {stop_loss:,.2f} (ATR 기반)")
            st.info(f"**The Closer's 판정:** {msg}")

            # 헬퍼 함수: 엔진의 코멘트를 UI 키워드와 매칭
            def get_realtime_view(keywords):
                for d in details:
                    if any(k in d['title'] for k in keywords): return d['full_comment']
                return "엔진에서 해당 지표의 실시간 데이터를 판독 중입니다."

            # --- [SET 1] 가격/수급/매물 (Indicator 1,2,3,4) ---
            st.write("---")
            st.markdown("### 📊 SET 1. 가격 흐름과 세력의 에너지 (Price, VWAP, 구름, MACD)")
            c1, c2 = st.columns([1, 1.8])
            with c1:
                st.info(f"""
                **💡 지표 이해:** VWAP은 세력 평단가, 구름대는 매물 저항입니다.
                **🎯 실시간 판독:**
                * **세력 수급**: {get_realtime_view(['VWAP', '평단가'])}
                * **매물 저항**: {get_realtime_view(['구름', '일목'])}
                """)
            with c2:
                fig1 = go.Figure()
                fig1.add_trace(go.Scatter(x=df.index, y=df['ichi_a'], line=dict(width=0), showlegend=False))
                fig1.add_trace(go.Scatter(x=df.index, y=df['ichi_b'], fill='tonexty', fillcolor='rgba(128, 128, 128, 0.2)', line=dict(width=0), name='구름대'))
                fig1.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='주가'))
                fig1.add_trace(go.Scatter(x=df.index, y=df['vwap'], name='VWAP', line=dict(color='orange', width=2)))
                # MACD 분포 Overlay
                m_h = df['macd'] - df['macd_sig']
                fig1.add_trace(go.Bar(x=df.index, y=m_h, marker_color=['rgba(255, 59, 48, 0.3)' if x > 0 else 'rgba(0, 122, 255, 0.3)' for x in m_h], yaxis='y2', name='MACD에너지'))
                fig1.update_layout(height=450, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False,
                                  yaxis2=dict(overlaying='y', side='right', showgrid=False, range=[-max(abs(m_h))*4, max(abs(m_h))*4]))
                st.plotly_chart(fig1, use_container_width=True)

            # --- [SET 2] 시장 온도 (Indicator 5,6) ---
            st.write("---")
            st.markdown("### 🌡️ SET 2. 시장의 과열도 및 심리 (RSI, MFI)")
            c3, c4 = st.columns([1, 1.8])
            with c3:
                st.info(f"""
                **💡 지표 이해:** RSI와 MFI는 시장의 체온입니다.
                **🎯 실시간 판독:**
                * **엔진 온도**: {get_realtime_view(['RSI', '온도'])}
                """)
            with c4:
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=df.index, y=df['rsi'], name='RSI', line=dict(color='yellow')))
                fig2.add_trace(go.Scatter(x=df.index, y=df['mfi'], name='MFI', line=dict(color='lime', dash='dot')))
                fig2.add_hline(y=70, line_dash="dash", line_color="red"); fig2.add_hline(y=30, line_dash="dash", line_color="blue")
                fig2.update_layout(height=300, template="plotly_dark")
                st.plotly_chart(fig2, use_container_width=True)

            # --- [SET 3] 자금 흐름 (Indicator 7,8) ---
            st.write("---")
            st.markdown("### 💰 SET 3. 거래량과 자금 매집 흔적 (OBV, Volume)")
            c5, c6 = st.columns([1, 1.8])
            with c5:
                obv_status = "매집 중" if df['obv'].iloc[-1] > df['obv'].iloc[-5] else "이탈 중"
                st.info(f"""
                **💡 지표 이해:** OBV는 거래량의 누적 에너지를 보여줍니다.
                **🎯 실시간 판독:**
                * **자금 유출입**: 현재 {target_name}의 큰손들은 자금을 **{obv_status}**인 것으로 분석됩니다.
                """)
            with c6:
                fig3 = go.Figure()
                fig3.add_trace(go.Scatter(x=df.index, y=df['obv'], name='OBV', line=dict(color='cyan')))
                fig3.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color='gray', opacity=0.3, yaxis='y2', name='Volume'))
                fig3.update_layout(height=300, template="plotly_dark", yaxis2=dict(overlaying='y', side='right', showgrid=False), showlegend=False)
                st.plotly_chart(fig3, use_container_width=True)

        else:
            st.error("❌ 데이터 로드 실패: 티커 형식을 확인하십시오.")