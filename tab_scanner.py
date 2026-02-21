import streamlit as st
import plotly.graph_objects as go
from engine import analyze_stock
from market_data import get_all_krx_stocks  # [수술] 전 종목 엔진 로드
from style_utils import apply_global_style

def run_scanner_tab(unused_stock_dict):
    apply_global_style() # 전역 가독성 패치 적용
    st.markdown("<h1 style='font-weight:800;'>🔍 전문가 종목 정밀 진단</h1>", unsafe_allow_html=True)
    
    # 1. 조회 모드 분리 (국내 vs 글로벌)
    search_mode = st.radio("진단 시장 선택", ["🇰🇷 국내 주식 (KOSPI/KOSDAQ)", "🌎 글로벌 자산 (US/Crypto)"], horizontal=True)
    
    target_ticker = None
    target_name = ""

    # 2. 시장별 전용 입력 시스템
    if search_mode == "🇰🇷 국내 주식 (KOSPI/KOSDAQ)":
        all_stocks = get_all_krx_stocks() # 삼천당제약 포함 전 종목 리스트
        col_kr, _ = st.columns([2, 1])
        with col_kr:
            target_name = st.selectbox("진단할 국내 종목 검색", list(all_stocks.keys()), index=0)
            target_ticker = all_stocks[target_name]
        btn_label = f"🔬 {target_name} 정밀 분석 가동"
    else:
        col_gl, _ = st.columns([2, 1])
        with col_gl:
            target_ticker = st.text_input("글로벌 티커 직접 입력", placeholder="예: TSLA, NVDA, BTC-USD").strip().upper()
            target_name = target_ticker
        btn_label = f"🚀 {target_ticker if target_ticker else 'Global'} 자산 분석 가동"

    st.write("---")

    # 3. 분석 집행
    if st.button(btn_label, type="primary", use_container_width=True):
        if not target_ticker:
            st.warning("분석할 티커를 입력하거나 선택하십시오.")
            return

        df, score, msg, details, stop_loss = analyze_stock(target_ticker)
        
        if df is not None:
            # 최상단 점수 리포트 출력
            st.markdown(f"#### {target_name} AI 신뢰 점수: <span style='color:white; font-size:3.2rem; font-weight:800;'>{score}점</span>", unsafe_allow_html=True)
            st.markdown(f"### **{msg}**")
            st.error(f"📍 최종 방어선 (손절가): {int(stop_loss):,}원")
            st.write("---")

            # 4. [수술] 전문가 의견 고도화 (VWAP, 일목, RSI 용어 정리)
            for item in details:
                col_txt, col_chart = st.columns([1, 1.8])
                
                # 지표명 및 의견 재설정 (전문가 용어 이식)
                title = item['title']
                view_text = item['full_comment']
                
                if "VWAP" in title:
                    title = "⚖️ 세력의 진짜 평단가 (VWAP)"
                    # [요청 반영] 그래프 의미 전달형 코멘트
                    if "위에" in view_text:
                        view_text = f"{item['res']} 이 의미는 현재 가격이 세력의 매수 원가보다 높다는 거야. 세력이 자기 수익을 지키기 위해 이 라인을 강력한 **'지지선'**으로 만들 가능성이 90% 이상이야."
                    else:
                        view_text = f"{item['res']} 이 의미는 현재 가격이 세력의 평단가 아래에 있다는 뜻이야. 세력이 물량을 던지고 도망갔거나, 이 라인이 뚫기 힘든 **'무거운 천장'**이 되어 주가를 누를 거야."
                
                elif "일목균형표" in title:
                    title = "☁️ 심리적 매물벽 (일목 구름대)"
                    if "안착" in view_text:
                        view_text = f"{item['res']} 이 의미는 주가가 모든 매물 저항을 뚫고 **'고속도로'**에 진입했다는 뜻이야. 가로막는 매물벽이 없으니 추세가 가파르게 상승할 수 있는 최적의 상태지."
                    else:
                        view_text = f"{item['res']} 이 의미는 주가 위쪽에 탈출하지 못한 매물들이 **'산더미'**처럼 쌓여있다는 뜻이야. 반등하려 해도 머리를 누르는 매물벽이 너무 두꺼워 상승이 제한적일 거야."
                
                elif "RSI" in title:
                    title = "🌡️ 매수 강도 측정기 (RSI)"
                    if "과열" in view_text:
                        view_text = f"{item['res']} 시장의 매수 열기가 **'과도하게 뜨거운'** 상태라는 거야. 엔진이 식어야 하는 시점이 곧 올 거야. 이런 시점에 추격해서 사들어가는 건 피하는 게 현명할 거 같아. 조정이 올 확률이 높거든."
                    else:
                        view_text = f"{item['res']} 매수 강도가 **'적정'**하거나 혹은 아직 여유가 있다는 뜻이야. 엔진이 무리 없이 계속 가동될 수 있는 충분한 에너지가 남아있다는 신호지. 추세를 믿고 가져도 괜찮은 상태야."

                with col_txt:
                    st.markdown(f"### 📍 {title}")
                    st.info(f"**전문가 분석:**\n\n{view_text}")
                
                with col_chart:
                    fig = go.Figure()
                    if "VWAP" in item['title'] or "일목균형표" in item['title']:
                        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'))
                        if "VWAP" in item['title']:
                            fig.add_trace(go.Scatter(x=df.index, y=df['vwap'], name='VWAP', line=dict(color='orange', width=2)))
                        else:
                            fig.add_trace(go.Scatter(x=df.index, y=df['ichi_a'], line=dict(width=0), name='A'))
                            fig.add_trace(go.Scatter(x=df.index, y=df['ichi_b'], line=dict(width=0), fill='tonexty', fillcolor='rgba(255, 255, 255, 0.1)', name='B'))
                    elif "RSI" in item['title']:
                        fig.add_trace(go.Scatter(x=df.index, y=df['rsi'], name='RSI', line=dict(color='yellow')))
                        fig.add_hline(y=70, line_dash="dash", line_color="red")
                        fig.add_hline(y=30, line_dash="dash", line_color="blue")
                        fig.update_yaxes(range=[0, 100])

                    fig.update_layout(height=350, margin=dict(l=0,r=0,t=50,b=0), xaxis_rangeslider_visible=False, template="plotly_dark", plot_bgcolor='black', paper_bgcolor='black', showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
                st.write("---")

            # 5. MACD 신호 분석
            st.markdown("### 📊 MACD로 보는 매수/매도 세력")
            c_txt, c_chart = st.columns([1, 1.8])
            
            df['macd_hist'] = df['macd'] - df['macd_sig']
            curr_hist = df['macd_hist'].iloc[-1]
            limit = df['macd'].std() * 2 
            
            with c_txt:
                with st.expander("📝 MACD 지표 읽는 법", expanded=True):
                    st.write("⚪ **흰색 꺾은선**: 주가의 큰 방향을 보여주는 선 (위쪽은 사려는 사람들이 이기고 아래쪽은 팔려는 사람들이 이기고 있어)")
                    st.write("🔴 **빨간 막대**: 사려는 사람들이 얼마나 강한지 보여줘 (길수록 매수세가 강함)")
                    st.write("🔵 **파란 막대**: 팔려는 사람들이 얼마나 강한지 보여줘 (길수록 매도세가 강함)")
                    st.write("░ **점선**: 정상 범위를 벗어난 과도한 신호의 경계선")
                
                if curr_hist >= limit:
                    impact = "🔴 **매수세가 정점에 달했어요**: 사려는 사람들이 너무 많아져서 지금 상태가 이상적이지 않다는 거야. 여기서 계속 사들어가면 손해볼 가능성이 높으니 주의해야 해. 곧 가격이 조정받을 준비가 되어있다는 신호야."
                elif curr_hist <= -limit:
                    impact = "🔵 **매도세가 극단적으로 강해요**: 팔려는 사람들이 최대한 강하게 나가고 있다는 거야. 이런 상태는 오래가지 않아. 에너지가 다 떨어지면 매수세가 나타나서 가격이 올라갈 가능성이 정말 높거든. 만약 여기서 샀다면 조금만 더 참아봐."
                else:
                    impact = "⚪ **정상적인 상태예요**: 지금은 사려는 사람과 팔려는 사람의 힘이 균형을 이루고 있는 거야. 과도한 신호 없이 자연스럽게 움직이고 있으니 추세를 믿고 가져도 돼."
                
                st.info(f"**전문가 의견:**\n\n{impact}")

            with c_chart:
                fig_macd = go.Figure()
                fig_macd.add_trace(go.Bar(x=df.index, y=df['macd_hist'], marker_color=['#ff3b30' if x > 0 else '#007aff' for x in df['macd_hist']]))
                fig_macd.add_trace(go.Scatter(x=df.index, y=df['macd'], line=dict(color='white')))
                fig_macd.add_hline(y=limit, line_dash="dot", line_color="red")
                fig_macd.add_hline(y=-limit, line_dash="dot", line_color="blue")
                fig_macd.update_layout(height=400, margin=dict(l=0,r=0,t=50,b=0), template="plotly_dark", showlegend=False)
                st.plotly_chart(fig_macd, use_container_width=True)
        else:
            st.error(f"❌ '{target_name}' 데이터를 불러올 수 없습니다. 티커를 확인하십시오.")