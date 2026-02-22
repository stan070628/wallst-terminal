import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from engine import analyze_stock
from stocks import STOCK_DICT
import yfinance as yf
import re

def run_deepdive_tab(stock_dict):
    st.subheader("🎯 9대 지표 정밀 타격 & 전문가 분석 (Deep Dive)")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        user_input = st.text_input(
            "종목명 또는 티커 (예: 229200, KODEX코스닥150, 삼성은선물, AAPL)",
            placeholder="검색...",
            label_visibility="collapsed",
            key="expert_search_smart"
        )
    with col2:
        run_btn = st.button(f"⚡ 즉시 분석 개시", use_container_width=True)
        
    st.markdown("---")
    
    if run_btn and user_input:
        # 🚨 [The Closer's 슈퍼 ETF 검색 엔진 - 어떤 입력이든 6자리 티커로 강제 변환]
        ticker = None
        choice_name = user_input
        clean_input = user_input.replace(" ", "").upper()
        
        # [Stage 1] 헷갈리는 주요 ETF 강제 매핑 (부분 문자열 매칭)
        ETF_MASTER_DICT = {
            "코스닥150": "229200.KS",
            "KODEX코스닥150": "229200.KS",
            "코스피100": "237350.KS",
            "KODEX코스피100": "237350.KS",
            "KODEX200": "069500.KS",
            "금선물": "411060.KS",  # 오타 방어
            "금현물": "411060.KS",
            "ACEKRX금현물": "411060.KS",
            "삼성은선물": "530089.KS",
            "삼성은선물ETN": "530089.KS",
            "KODEX코스피": "226490.KS"
        }
        
        # 부분 문자열 매칭으로 검색 (키 in 입력값)
        for key, val in ETF_MASTER_DICT.items():
            if key in clean_input:
                ticker = val
                break
                
        # [Stage 2] 숫자만 6자리 입력했을 경우의 절대 방어
        if not ticker:
            numbers_only = re.sub(r'[^0-9]', '', clean_input)
            if len(numbers_only) == 6:
                ticker = f"{numbers_only}.KS"  # 한국 ETF는 무조건 .KS
            else:
                # 위 조건에 다 안 맞으면 원래 입력값을 티커로 간주
                ticker = user_input.upper()

        with st.spinner(f"📡 ETF 타겟 확인 완료. [{ticker}] 데이터 강제 추출 중..."):
            result = analyze_stock(ticker)
            
            if result:
                df, score, core_msg, details, stop_loss_price = result
                st.success(f"✅ {ticker} 분석 완료! ETF 엔진 정상 가동.")
                render_deepdive_analysis(df, score, core_msg, details, stop_loss_price, ticker)
            else:
                st.error(f"❌ '{ticker}' 데이터를 분석할 수 없습니다.")
                st.info("💡 엔진 거부 원인: 해당 ETF의 상장 기간이 너무 짧거나(최소 30일 필요), Yahoo Finance 서버 누락입니다.")


def render_deepdive_analysis(df, score, core_msg, details, stop_loss_price, ticker):
    """분석 결과를 시각화하고 렌더링하는 함수 - The Closer's 유명 UI"""
    currency = "₩" if ticker.endswith(".KS") or ticker.endswith(".KQ") else "$"
    current_price = float(df['Close'].iloc[-1])
    stop_loss_price = float(stop_loss_price)
    
    # 최신 지표 값들 추출
    rsi_val = df['rsi'].iloc[-1]
    mfi_val = df['mfi'].iloc[-1]
    macd_val = df['macd'].iloc[-1]
    macd_sig_val = df['macd_sig'].iloc[-1]
    ichi_a_val = df['ichi_a'].iloc[-1]
    ichi_b_val = df['ichi_b'].iloc[-1]
    bb_higher_val = df['High'].rolling(20).max().iloc[-1]  # 간단 계산
    bb_lower_val = df['Low'].rolling(20).min().iloc[-1]
    vwap_val = df['vwap'].iloc[-1]
    atr_val = df['atr'].iloc[-1]
    volume_latest = df['Volume'].iloc[-1]
    volume_avg = df['Volume'].rolling(20).mean().iloc[-1]

    # 판정 표시 (색상 구분)
    if score >= 80: 
        st.success(f"🚀 {core_msg}")
    elif score <= 40: 
        st.error(f"🚨 {core_msg}")
    else: 
        st.warning(f"⚖️ {core_msg}")

    st.markdown("---")
    
    # 상단 요약 지표
    st.markdown("### 📊 The Closer's 타격 지표")
    c1, c2, c3 = st.columns(3)
    c1.metric("현재가", str(f"{currency}{current_price:,.2f}"))
    c2.metric("The Closer 종합 점수", str(f"{score}점"))
    c3.metric("기계적 손절가", str(f"{currency}{stop_loss_price:,.2f}"))

    st.markdown("---")

    # ===== 🗂️ 지표 그룹화 UI =====
    st.markdown("### 🗂️ The Closer's 정밀 타격 분석 (지표 그룹화)")

    # --- 1️⃣ [모멘텀 & 과열] 카테고리 ---
    with st.container():
        st.markdown("#### 1️⃣ [엔진 온도] 단기 추진력 및 자금 흐름")
        st.caption("주가가 얼마나 빠르게 움직이는지, 그리고 실제 자금이 따라오는지 확인합니다.")
        
        col1, col2 = st.columns(2)
        col1.metric("🌡️ RSI (가격 추진력)", f"{rsi_val:.1f}", 
                   "과열 ⚠️" if rsi_val >= 70 else "약함 📉" if rsi_val <= 30 else "정상 ✅", 
                   delta_color="inverse" if rsi_val >= 70 or rsi_val <= 30 else "off")
        col2.metric("💰 MFI (자금 흐름)", f"{mfi_val:.1f}", 
                   "강세 📈" if mfi_val >= 70 else "약세 📉" if mfi_val <= 30 else "중립 ⚖️", 
                   delta_color="off")
        
        if rsi_val >= 70 and mfi_val < 70:
            comment_line1 = "⚠️ **의견: 신중하게 접근** - 가격은 과열됐지만 자금은 뒷받침이 약함"
            comment_line2 = "**근거**: RSI 70 이상은 매도 신호. MFI가 따라오지 못하면 가격 조정(고점 회피) 가능성 높음"
            comment_line3 = "**차트 분석**: RSI 과열도에서 하락 반전하는 경우가 자주 생김. 되돌림 매수(저가 매입) 기회 대기"
        elif rsi_val >= 70 and mfi_val >= 70:
            comment_line1 = "✅ **의견: 강력한 매수 신호** - 가격과 자금이 모두 강세"
            comment_line2 = "**근거**: 둘 다 70 이상이면 강한 상승 기조. 주가가 맞춤새(재진입) 후 추가 상승 가능"
            comment_line3 = "**차트 분석**: 이런 상황에서는 상승세가 계속될 확률이 높음. 강한 저항대까지 상승 노리기"
        elif rsi_val <= 30:
            comment_line1 = "🚀 **의견: 반등 대기** - 과매도 구간, 반등 기회 임박"
            comment_line2 = "**근거**: RSI 30 이하는 극도의 약세. 자금이 빠져나간 상태. 반등 신호 대기 필수"
            comment_line3 = "**차트 분석**: 이 구간에서는 추가 하락보다 반등이 유력. MFI 회복 신호와 함께 매수 검토"
        else:
            comment_line1 = "⚖️ **의견: 정상 흐름** - 가격 추진력이 건강함"
            comment_line2 = "**근거**: RSI/MFI가 모두 중립 구간(30~70). 명백한 매수/매도 신호 없음"
            comment_line3 = "**차트 분석**: 이 상태라면 다른 지표(추세, 거래량)를 참고해서 방향 결정하기"
        
        st.info(f"{comment_line1}\n\n{comment_line2}\n\n{comment_line3}")
        st.write("---")

    # --- 2️⃣ [추세 & 방향성] 카테고리 ---
    with st.container():
        st.markdown("#### 2️⃣ [길잡이] 중기 추세 및 방향성")
        st.caption("노이즈를 무시하고 현재 주가의 큰 흐름(상승/하락)을 확인합니다.")
        
        macd_signal = "상승 신호 📈" if macd_val > macd_sig_val else "하락 신호 📉"
        ichimoku_signal = "상승 흐름 📈" if ichi_a_val > ichi_b_val else "하락 흐름 📉"
        
        col3, col4 = st.columns(2)
        col3.metric("📊 MACD (단기 추세)", macd_signal)
        col4.metric("📈 장기 추세 신호", ichimoku_signal)
        
        if macd_val > macd_sig_val and ichi_a_val > ichi_b_val:
            comment_line1 = "✅ **의견: 강한 매수 신호** - 단기, 중기 모두 상승세"
            comment_line2 = "**근거**: MACD 상향 돌파 + 장기 추세선 상향 = 강한 상승 흐름. 이 상황에서는 조정(하락) 후 다시 상승이 유력"
            comment_line3 = "**차트 분석**: MACD는 추세 방향을, 추세선은 강도를 보여줍니다. 둘 다 상승이면 상승 모멘텀이 강함"
        elif macd_val > macd_sig_val and ichi_a_val < ichi_b_val:
            comment_line1 = "⚠️ **의견: 단기는 강하지만 중기는 약함** - 조정 가능성 주의"
            comment_line2 = "**근거**: MACD는 상향이지만 장기 추세는 약세. 조정(하락) 후 재상승 패턴일 가능성 높음"
            comment_line3 = "**차트 분석**: 단기와 중기 신호 불일치. 중기 추세선 돌파 대기하며 매수 타이밍 체계 필수"
        elif macd_val < macd_sig_val and ichi_a_val > ichi_b_val:
            comment_line1 = "⚠️ **의견: 중기는 상승이지만 단기 조정** - 재진입 대기"
            comment_line2 = "**근거**: 장기 추세는 강하지만 단기 MACD가 약세. 조정 후 재진입 신호(MACD 상향)를 기다리는 것이 현명"
            comment_line3 = "**차트 분석**: 큰 흐름은 좋지만 단기 피로. 좋은 매수 기회가 (조정 구간에서) 임박"
        else:
            comment_line1 = "🛑 **의견: 신중하게 접근** - 추세가 약세이거나 리스크 높음"
            comment_line2 = "**근거**: MACD 하향 + 장기 추세선 약세 = 추가 하락 가능성. 명확한 반전 신호까지 관망 추천"
            comment_line3 = "**차트 분석**: 두 지표 모두 약세는 하락 관성이 강함. 추세 전환(바닥) 신호 대기 필수"
        
        st.info(f"{comment_line1}\n\n{comment_line2}\n\n{comment_line3}")
        st.write("---")

    # --- 3️⃣ [변동성 & 밴드] 카테고리 ---
    with st.container():
        st.markdown("#### 3️⃣ [폭발력] 변동성 및 가격 범위")
        st.caption("주가가 움직일 수 있는 공간(위/아래 한계)과 변동성의 크기를 파악합니다.")
        
        bb_position = "상단 근처 📈" if current_price > (bb_higher_val + bb_lower_val) / 2 else "하단 근처 📉" if current_price < (bb_higher_val + bb_lower_val) / 2 else "중간"
        vol_level = "높음" if atr_val > (df['High'].iloc[-20:] - df['Low'].iloc[-20:]).mean() * 1.2 else "정상"
        
        col5, col6 = st.columns(2)
        col5.metric("💎 가격 범위 (볼린저밴드)", bb_position, 
                   f"변동성: {vol_level}", 
                   delta_color="inverse" if bb_position == "상단 근처" else "off")
        col6.metric("🎯 ATR (변동 폭)", f"{atr_val:.2f}", 
                   "높은 변동성 ⚡" if vol_level == "높음" else "정상 변동성")
        
        if bb_position == "상단 근처" and vol_level == "높음":
            comment_line1 = "🔥 **의견: 상승 추진력 강함** - 변동성 높으면서 상단 도달"
            comment_line2 = "**근거**: 상단 근처 + 높은 변동성 = 상승 모멘텀이 강함. 저항 돌파 시 급등 가능"
            comment_line3 = "**차트 분석**: 상단에서의 높은 변동성은 매도 압력이 있지만, 상승세가 강하다는 신호. 돌파 여부가 핵심"
        elif bb_position == "상단 근처" and vol_level == "정상":
            comment_line1 = "⚠️ **의견: 고점 근처, 조정 가능성** - 변동성은 정상이지만 상단"
            comment_line2 = "**근거**: 상단이면서 변동성이 낮으면 매도 신호. 추가 상승보다 조정(하락) 확률이 높음"
            comment_line3 = "**차트 분석**: 저항대에서 변동성이 줄어들면 가격 조정이 임박했다는 신호. 익절(수익 실현) 타이밍 고려"
        elif bb_position == "하단 근처":
            comment_line1 = "🚀 **의견: 반등 기회 임박** - 바닥 근처에서 기회 포착"
            comment_line2 = "**근거**: 하단 = 저가 매수 기회. 변동성이 높으면 급반등, 낮으면 천천히 반등할 가능성"
            comment_line3 = "**차트 분석**: 밴드 하단은 강한 지지대. 여기서 반등 신호(거래량 증가)가 나오면 좋은 매수 기회"
        else:
            comment_line1 = "⚖️ **의견: 중간 지점, 추세 추종** - 방향 신호 다른 지표 참고"
            comment_line2 = "**근거**: 중간 근처면 밴드 상하 한계로의 방향 결정 필요. 추세 지표 확인 필수"
            comment_line3 = "**차트 분석**: 이 위치에서는 가격 추진력(MACD, RSI) 같은 다른 신호와 조합해서 판단해야 함"
        
        st.info(f"{comment_line1}\n\n{comment_line2}\n\n{comment_line3}")
        st.write("---")

    # --- 4️⃣ [수급 & 세력선] 카테고리 ---
    with st.container():
        st.markdown("#### 4️⃣ [기관의 지문] 수급 상황 및 거래량")
        st.caption("큰 자금(기관/외국인)의 평단가와 거래량 상황으로 장기 추세를 읽습니다.")
        
        vwap_signal = "높은 수준 📈" if current_price > vwap_val else "낮은 수준 📉"
        volume_signal = f"{volume_latest:,.0f}주" 
        volume_comment = "평균 이상 💪" if volume_latest > volume_avg else "평균 이하 😐"
        
        col7, col8 = st.columns(2)
        col7.metric("🌊 기관 평단가 (VWAP)", vwap_signal)
        col8.metric("📊 거래량", volume_signal, volume_comment)
        
        if current_price > vwap_val and volume_latest > volume_avg:
            comment_line1 = "✅ **의견: 강한 매수 신호** - 기관 평단가 상향 + 거래량 증가"
            comment_line2 = "**근거**: VWAP 돌파는 기관 평단가 극복. 높은 거래량과 함께면 추세가 진정성 있음. 추가 상승 유력"
            comment_line3 = "**차트 분석**: 기관의 평단가를 뚫으면 그 라인이 지지대가 됨. 거래량 함께면 조정 후 재상승 패턴"
        elif current_price > vwap_val and volume_latest < volume_avg:
            comment_line1 = "⚠️ **의견: 거래량 약증** - 가격은 높지만 매수 동의 부족"
            comment_line2 = "**근거**: VWAP 상향이지만 거래량 짧음 = 느슨한 상승. 큰 하락에 취약. 거래량 회복 대기 필요"
            comment_line3 = "**차트 분석**: 가격 상승 + 거래량 저하 = 약한 신호. 추가 상승보다 조정 후 재진입이 더 안전"
        elif current_price < vwap_val and volume_latest > volume_avg:
            comment_line1 = "📉 **의견: 하락 중이지만 거래량 있음** - 공매도 가능성 높음"
            comment_line2 = "**근거**: 기관 평단가 아래 + 높은 거래량 = 기관/큰손들이 손절하거나 공매도. 바닥 신호 대기"
            comment_line3 = "**차트 분석**: 이 상황이 계속되면 더 내려갈 수 있으나, 바닥에서는 강한 반등 가능성도 있음"
        else:
            comment_line1 = "📉 **의견: 약세 신호** - 기관 평단가 아래 + 거래량 부족"
            comment_line2 = "**근거**: 기관들이 이미 떠난 상태 + 거래량 없음 = 추가 하락 가능성. 명확한 바닥 신호 대기"
            comment_line3 = "**차트 분석**: 이 구간에서는 섣부른 매수 피하고, 거래량 증가 + VWAP 회복 신호 대기 권장"
        
        st.info(f"{comment_line1}\n\n{comment_line2}\n\n{comment_line3}")
        st.write("---")

    # --- ⚡ 최종 종합 결론 ---
    st.markdown("### ⚡ 최종 매매 판정")
    
    if score >= 80:
        st.success(f"✅ **최종 판정**: {core_msg}")
        st.markdown("""
**🔥 매수 신호 - 가장 강한 신호**

모든 지표가 "매수하세요" 신호를 보내고 있습니다.
- 단기 추진력 ✅
- 중기 추세 ✅  
- 변동성과 가격 위치 ✅
- 거래량과 기관 자금 ✅

**할 일**: 자금 관리를 철저히 한 후, 이 구간에서 매수를 집중하세요. 
        """)
    elif score >= 60:
        st.warning(f"⚠️ **최종 판정**: {core_msg}")
        st.markdown("""
**🟡 관망 또는 분할 매수 - 신호가 혼합됨**

일부 지표는 강하지만 다른 지표는 약한 상황입니다.
- 추세가 명확한가? 다시 확인하세요.
- 거래량이 뒷받침 되는가? 확인하세요.

**할 일**: 
1) 약한 신호가 강해질 때까지 기다리거나
2) 조금만 매수하고 추가 상승 신호 대기하기
가 현명합니다.
        """)
    elif score >= 40:
        st.warning(f"⚠️ **최종 판정**: {core_msg}")
        st.markdown("""
**🟠 신중 - 신호가 약함**

현재는 매수하기엔 신호가 약합니다.
- 여러 지표가 "기다려" 신호 중입니다.

**할 일**: 
1) 더 명확한 반등 신호 대기 (RSI <30에서 회복, 거래량 증가)
2) 현재 보유 중이라면 손절가 설정 필수
        """)
    else:
        st.error(f"🛑 **최종 판정**: {core_msg}")
        st.markdown("""
**🔴 매도 신호 - 가장 약한 신호**

지표들이 하락 또는 약세를 보이고 있습니다.
- 단기/중기 추세 모두 약함
- 거래량 부족
- 기관 자금 이탈 신호

**할 일**: 
1) 신규 매수 금지
2) 현재 보유 중이라면 손절 고려
3) 명확한 반전 신호(바닥권 신호들) 대기
        """)

    st.markdown("---")

    # 기술적 차트 (기존 유지)
    st.markdown("### 📈 기술적 지표 & 차트")
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