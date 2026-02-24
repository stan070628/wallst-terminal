import streamlit as st
import re
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from engine import analyze_stock
from market_data import get_all_krx_stocks
from style_utils import apply_global_style
from stocks import STOCK_DICT

def _find_ticker_from_name(user_input):
    """한글 이름으로 종목 찾기 (모든 시장 검색)"""
    user_input = user_input.strip()
    
    # 모든 시장에서 검색
    for market, stocks in STOCK_DICT.items():
        if user_input in stocks:
            return stocks[user_input], user_input
    
    return None, None

def _search_stocks(query, market_filter=None):
    """부분 검색: 입력된 텍스트를 포함하는 모든 종목 찾기 (시장 필터 지원)"""
    if not query or len(query.strip()) < 1:
        return []
    
    query = query.strip().lower()
    results = []
    
    # 시장 필터가 있으면 해당 시장만, 없으면 전체 검색
    if market_filter:
        search_markets = {k: v for k, v in STOCK_DICT.items() if k in market_filter}
    else:
        search_markets = STOCK_DICT
    
    for market, stocks in search_markets.items():
        for name, ticker in stocks.items():
            # 한글 이름 또는 티커로 검색 (대소문자 무시)
            if query in name.lower() or query in ticker.lower():
                market_label = "🔵KOSPI" if market == "KOSPI" else "🟢KOSDAQ" if market == "KOSDAQ" else "🌎GLOBAL"
                display_text = f"[{market_label}] {name} ({ticker})"
                results.append({
                    "name": name,
                    "ticker": ticker,
                    "display": display_text,
                    "market": market
                })
    
    # 중복 제거 및 정렬
    seen = set()
    unique_results = []
    for item in results:
        key = item['ticker']
        if key not in seen:
            seen.add(key)
            unique_results.append(item)
    
    return sorted(unique_results, key=lambda x: x['name'])

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
        search_mode = st.radio("📊 분석 시장 선택", ["🇰🇷 국내 주식/ETF", "🌎 글로벌 자산"], horizontal=True, label_visibility="collapsed")
    
    if search_mode == "🇰🇷 국내 주식/ETF":
        # 시장 세부 선택 (KOSPI / KOSDAQ / 전체)
        kr_market_filter = st.radio("📌 시장 필터", ["전체 (KOSPI+KOSDAQ)", "KOSPI만", "KOSDAQ만"], horizontal=True, label_visibility="collapsed")
        
        if kr_market_filter == "KOSPI만":
            market_keys = ["KOSPI"]
        elif kr_market_filter == "KOSDAQ만":
            market_keys = ["KOSDAQ"]
        else:
            market_keys = ["KOSPI", "KOSDAQ"]
        
        # 🚨 [부분 검색 기능] "삼성" → 삼성전자, 삼성SDI, 삼성화재 등 리스트됨
        user_input = st.text_input(
            "📌 종목 검색 (부분 입력 가능)", 
            placeholder="예: '삼성' → 삼성전자, 삼성SDI, 삼성화재... | '금' → 금융, 금현물...",
            help="한글 이름 또는 6자리 코드의 일부만 입력해도 관련 종목이 리스트됩니다"
        ).strip()
        
        target_ticker = None
        target_name = None
        
        if user_input and len(user_input) >= 1:
            # 🎯 부분 검색 실행 (시장 필터 적용)
            search_results = _search_stocks(user_input, market_filter=market_keys)
            
            if search_results:
                # 🔍 검색 결과를 selectbox로 표시
                display_options = [item['display'] for item in search_results]
                st.caption(f"🔎 검색 결과: {len(search_results)}개 종목")
                
                selected_display = st.selectbox(
                    "📊 분석할 종목 선택",
                    options=display_options,
                    label_visibility="collapsed"
                )
                
                # 선택된 항목의 정보 찾기
                for item in search_results:
                    if item['display'] == selected_display:
                        target_ticker = item['ticker']
                        target_name = f"{item['name']} ({item['ticker']})"
                        break
            else:
                st.warning(f"⚠️ '{user_input}'에 매칭되는 종목이 없습니다. 다른 단어로 검색해주세요.")
                target_ticker = "229200.KS"
                target_name = "KODEX 코스닥150 (기본값)"
        else:
            # 입력이 없으면 기본값
            target_ticker = "229200.KS"
            target_name = "KODEX 코스닥150"
    else:
        user_input_global = st.text_input(
            "💱 종목명, 6자리 코드, 또는 코인명",
            value="AAPL",
            placeholder="예: 229200, 비트코인, NVDA",
            help="암호화폐(비트코인/이더리움/리플), 6자리 한국 코드, 또는 미국 티커"
        )

        # [스마트 티커 분류기]
        CRYPTO_MAP = {
            "비트코인": "BTC-USD", "BITCOIN": "BTC-USD", "BTC": "BTC-USD",
            "이더리움": "ETH-USD", "ETHEREUM": "ETH-USD", "ETH": "ETH-USD",
            "리플": "XRP-USD", "XRP": "XRP-USD",
            "솔라나": "SOL-USD", "SOL": "SOL-USD",
            "도지코인": "DOGE-USD", "DOGE": "DOGE-USD",
        }

        clean_input = user_input_global.strip().replace(" ", "").upper()
        ticker = None

        # 1단계: 암호화폐 하이패스 — 절대 .KS/.KQ가 붙지 않음
        for key, val in CRYPTO_MAP.items():
            if key in clean_input:
                ticker = val
                break

        # 직접 '-USD' 또는 '-KRW' 형식으로 입력한 경우 그대로 통과
        if not ticker and ("-KRW" in clean_input or "-USD" in clean_input):
            ticker = clean_input

        # 2단계: 숫자 6자리 → 한국 주식/ETF
        if not ticker:
            numbers_only = re.sub(r'[^0-9]', '', clean_input)
            if len(numbers_only) == 6:
                ticker = f"{numbers_only}.KS"
            else:
                # 영어 알파벳 → 미국 주식 티커 그대로
                ticker = clean_input if clean_input else "AAPL"

        target_ticker = ticker
        target_name = f"{user_input_global.strip()} ({target_ticker})" if user_input_global.strip() else target_ticker

    with col_input2:
        pass
    
    # 분석 버튼
    col_btn = st.columns([1])[0]
    btn_analyze = st.button(f"🚀 {target_name} 분석 시작", type="primary", use_container_width=True, help="9대 지표 통합 분석 시작 (5-10초)")
    
    if btn_analyze:
        # 로딩 애니메이션
        progress_placeholder = st.empty()
        progress_placeholder.info("🔄 분석 중... 데이터 수집 → 지표 계산 → 신호 생성")
        
        try:
            result = analyze_stock(target_ticker, apply_fundamental=True)
            progress_placeholder.empty()
            
            if result:
                df, score, msg, details, stop_loss = result
                
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
                    
                    # ---------------------------------------------------------
                    # 엔진(engine.py)이 보내준 진짜 퀀트 리포트를 details에서 추출해 출력
                    # ---------------------------------------------------------
                    st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
                    
                    closer_opinion = None
                    fund_opinion = None
                    
                    for info in details:
                        if "The Closer's 실시간 의견" in info["title"]:
                            closer_opinion = info["full_comment"]
                        elif "펀더멘털 검증" in info["title"]:
                            fund_opinion = info.get("full_comment") or info.get("comment", "")
                    
                    # 1. 재무 엑스레이 결과 (치명적 결함이 있을 때만 경고)
                    if fund_opinion:
                        st.error(f"**🏢 펀더멘털(재무) 검증:** {fund_opinion}", icon="🚨")
                        st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)
                    
                    # 2. 월스트리트 퀀트 브리핑 (마크다운 완벽 지원)
                    if closer_opinion:
                        st.info(closer_opinion, icon="🎯")
                    else:
                        st.warning(f"💡 전문가 코멘트: {msg}")
                    # ---------------------------------------------------------
                    
                    # AI 판정
                    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='{status_class}'><b>🤖 The Closer's 최종 판정:</b> {msg}</div>", unsafe_allow_html=True)
                    
                    # 기술지표 분석 섹션
                    st.markdown("---")
                    st.markdown("### 🗂️ The Closer's 정밀 타격 분석 (지표 그룹화)")
                    
                    # 최신 지표 값 추출
                    rsi_val = df['rsi'].iloc[-1]
                    mfi_val = df['mfi'].iloc[-1]
                    macd_val = df['macd'].iloc[-1]
                    macd_sig_val = df['macd_sig'].iloc[-1]
                    ichi_a_val = df['ichi_a'].iloc[-1]
                    ichi_b_val = df['ichi_b'].iloc[-1]
                    vwap_val = df['vwap'].iloc[-1]
                    volume_latest = df['Volume'].iloc[-1]
                    volume_avg = df['Volume'].rolling(20).mean().iloc[-1]
                    atr_val = df['atr'].iloc[-1]
                    
                    # --- 1️⃣ [엔진 온도] 모멘텀 및 과열 진단 ---
                    st.markdown("#### 1️⃣ [엔진 온도] 모멘텀 및 과열 진단")
                    st.caption("주가가 얼마나 가파르게 올랐는지, 단기적인 피로도와 돈의 흐름을 측정합니다.")
                    
                    left_col, right_col = st.columns([1.2, 1])
                    
                    with left_col:
                        col1, col2 = st.columns(2)
                        col1.metric("🌡️ RSI (엔진 온도)", f"{rsi_val:.1f}", 
                                   "과매수 (위험)" if rsi_val >= 70 else "과매도" if rsi_val <= 30 else "정상", 
                                   delta_color="inverse" if rsi_val >= 70 or rsi_val <= 30 else "off")
                        col2.metric("💰 MFI (자금 흐름)", f"{mfi_val:.1f}", 
                                   "강세" if mfi_val >= 70 else "약세" if mfi_val <= 30 else "중립", 
                                   delta_color="off")
                        
                        st.info("💡 **전문가 코멘트:** " + 
                               ("가격 엔진(RSI)이 과열 상태이므로, RSI의 회복(70→50)을 기다리거나, 실제 자금 유입(MFI)의 확인이 필수입니다. 속 빈 강정 가능성을 경계하십시오." if rsi_val >= 70 
                               else "엔진이 미지근하므로 단기적 반등 확률이 낮습니다. 명확한 신호를 기다리십시오." 
                               if rsi_val <= 30 else "모멘텀이 정상 범위 내에 있습니다. 안정적 흐름을 기대합니다."))
                    
                    with right_col:
                        # RSI + MFI 차트
                        fig_rsi = make_subplots(specs=[[{"secondary_y": False}]])
                        fig_rsi.add_trace(go.Scatter(x=df.index, y=df['rsi'], name='RSI', line=dict(color='#ff6b6b')), secondary_y=False)
                        fig_rsi.add_trace(go.Scatter(x=df.index, y=df['mfi'], name='MFI', line=dict(color='#4ecdc4')), secondary_y=False)
                        fig_rsi.add_hline(y=70, line_dash="dash", line_color="#ff6b6b", annotation_text="과매수", secondary_y=False)
                        fig_rsi.add_hline(y=30, line_dash="dash", line_color="#4ecdc4", annotation_text="과매도", secondary_y=False)
                        fig_rsi.update_layout(height=250, margin=dict(l=0, r=0, t=20, b=0), hovermode='x unified')
                        st.plotly_chart(fig_rsi, use_container_width=True)
                    
                    st.write("---")
                    
                    # --- 2️⃣ [길잡이] 거시적 추세 및 방향성 ---
                    st.markdown("#### 2️⃣ [길잡이] 거시적 추세 및 방향성")
                    st.caption("잔파도(노이즈)를 걷어내고, 현재 주가가 향하고 있는 굵직한 방향타를 확인합니다.")
                    
                    left_col, right_col = st.columns([1.2, 1])
                    
                    with left_col:
                        macd_signal = "반전 신호 (+)" if macd_val > macd_sig_val else "하락 지속 (-)"
                        ichimoku_signal = "상승 흐름 (구름대 위)" if ichi_a_val > ichi_b_val else "하락 흐름 (구름대 아래)"
                        
                        col3, col4 = st.columns(2)
                        col3.metric("📊 MACD (추세 신호)", macd_signal)
                        col4.metric("📈 일목균형표 (Ichimoku)", ichimoku_signal)
                        
                        st.info("💡 **전문가 코멘트:** " + 
                               ("단기적인 과열에도 불구하고, 굵은 물줄기(MACD, 일목균형표)는 여전히 상승을 가리키고 있습니다. 섣부른 매도(Short)보다는 押し目 매수(Pushback Buy)을 노리십시오." 
                               if macd_val > macd_sig_val and ichi_a_val > ichi_b_val
                               else "주의: 추세가 꺾일 조짐이 보입니다. 상승 신호의 확인을 기다리는 것이 현명합니다."))
                    
                    with right_col:
                        # MACD + Ichimoku 차트
                        fig_macd = make_subplots(specs=[[{"secondary_y": False}]])
                        fig_macd.add_trace(go.Bar(x=df.index, y=df['macd'] - df['macd_sig'], name='MACD Histogram',
                                                  marker_color=['#ff6b6b' if v > 0 else '#4ecdc4' for v in df['macd'] - df['macd_sig']]),
                                          secondary_y=False)
                        fig_macd.add_trace(go.Scatter(x=df.index, y=df['macd'], name='MACD', line=dict(color='#ffa500')), secondary_y=False)
                        fig_macd.add_trace(go.Scatter(x=df.index, y=df['macd_sig'], name='Signal', line=dict(color='#95e1d3')), secondary_y=False)
                        fig_macd.update_layout(height=250, margin=dict(l=0, r=0, t=20, b=0), hovermode='x unified')
                        st.plotly_chart(fig_macd, use_container_width=True)
                    
                    st.write("---")
                    
                    # --- 3️⃣ [폭발력] 변동성 및 가격 밴드 ---
                    st.markdown("#### 3️⃣ [폭발력] 변동성 및 가격 밴드")
                    st.caption("주가가 갇혀있는 박스권의 상/하단 한계치와, 위아래로 튈 수 있는 탄력을 잽니다.")
                    
                    left_col, right_col = st.columns([1.2, 1])
                    
                    with left_col:
                        current_price = df['Close'].iloc[-1]
                        bb_higher_val = df['High'].rolling(20).max().iloc[-1]
                        bb_lower_val = df['Low'].rolling(20).min().iloc[-1]
                        bb_position = "상단 근처" if current_price > (bb_higher_val + bb_lower_val) / 2 else "하단 근처" if current_price < (bb_higher_val + bb_lower_val) / 2 else "중간권역"
                        vol_level = "높음" if atr_val > (df['High'].iloc[-20:] - df['Low'].iloc[-20:]).mean() * 1.2 else "정상"
                        
                        col5, col6 = st.columns(2)
                        col5.metric("💎 볼린저 밴드", bb_position, 
                                   f"변동성: {vol_level}", 
                                   delta_color="inverse" if bb_position == "상단 근처" else "off")
                        col6.metric("🎯 ATR (변동성 범위)", f"{atr_val:.2f}", 
                                   "높은 변동성" if vol_level == "높음" else "정상 변동성")
                        
                        st.info("💡 **전문가 코멘트:** " + 
                               ("밴드 상단에 머물며 팽팽한 긴장감을 유지하고 있습니다. 상단 돌파 시 다음 저항선까지 쏜살같이 상승할 가능성이 높습니다." 
                               if bb_position == "상단 근처" 
                               else "밴드 하단에 접근했습니다. 강한 반등이나 추가 하락이 임박했을 가능성이 있습니다."))
                    
                    with right_col:
                        # BB + ATR 차트
                        bb_upper = df['High'].rolling(20).max()
                        bb_lower = df['Low'].rolling(20).min()
                        bb_mid = (bb_upper + bb_lower) / 2
                        
                        fig_bb = go.Figure()
                        fig_bb.add_trace(go.Scatter(x=df.index, y=bb_upper, name='BB Upper', line=dict(color='rgba(255,107,107,0.4)')))
                        fig_bb.add_trace(go.Scatter(x=df.index, y=bb_lower, name='BB Lower', line=dict(color='rgba(255,107,107,0.4)'), 
                                                    fill='tonexty'))
                        fig_bb.add_trace(go.Scatter(x=df.index, y=df['Close'], name='가격', line=dict(color='#1f77b4')))
                        fig_bb.update_layout(height=250, margin=dict(l=0, r=0, t=20, b=0), hovermode='x unified')
                        st.plotly_chart(fig_bb, use_container_width=True)
                    
                    st.write("---")
                    
                    # --- 4️⃣ [기관의 지문] 수급 및 거래량 프로파일 ---
                    st.markdown("#### 4️⃣ [기관의 지문] 수급 및 거래량 프로파일")
                    st.caption("거대 자본의 평단가와 그들이 쌓아놓은 매물대의 두께를 해부합니다.")
                    
                    left_col, right_col = st.columns([1.2, 1])
                    
                    with left_col:
                        vwap_signal = "VWAP 상향 돌파" if current_price > vwap_val else "VWAP 하향 이탈"
                        volume_signal = f"{volume_latest:,.0f}주" 
                        volume_comment = "평균 이상" if volume_latest > volume_avg else "평균 이하"
                        
                        col7, col8 = st.columns(2)
                        col7.metric("🌊 VWAP (거래량 가중)", vwap_signal)
                        col8.metric("📊 Volume Profile", volume_signal, volume_comment)
                        
                        st.info("💡 **전문가 코멘트:** " + 
                               ("세력의 평단가(VWAP)를 뚫어내고 거래량이 터졌습니다. 만약 하락하더라도 이 라인이 강한 콘크리트 바닥 역할을 할 것입니다. 강세 신호입니다." 
                               if current_price > vwap_val and volume_latest > volume_avg
                               else "거래량이 평균 미만이면서 VWAP 아래에서 출렁이고 있습니다. 동의 부재(Weak Conviction)가 뚜렷합니다."))
                    
                    with right_col:
                        # Volume + VWAP 차트
                        fig_vol = make_subplots(specs=[[{"secondary_y": True}]])
                        fig_vol.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', 
                                                marker_color=['#ff6b6b' if c > o else '#4ecdc4' 
                                                             for c, o in zip(df['Close'], df['Open'])]),
                                        secondary_y=False)
                        fig_vol.add_trace(go.Scatter(x=df.index, y=df['vwap'], name='VWAP', 
                                                    line=dict(color='#ffa500')), secondary_y=True)
                        fig_vol.update_layout(height=250, margin=dict(l=0, r=0, t=20, b=0), hovermode='x unified')
                        st.plotly_chart(fig_vol, use_container_width=True)
                    
                    st.write("---")
                    
                else:
                    st.error(f"❌ '{target_ticker}' 엔진 분석 실패")
                    st.warning("💡 원인: 해당 ETF/주식의 거래 역사가 너무 짧거나(최소 30일 데이터 필요), 상장폐지 종목이거나, Yahoo Finance 서버에 등재되지 않았습니다.")
            else:
                st.error(f"❌ '{target_ticker}' 데이터 로드 불가")
                st.info("💡 입력하신 6자리 코드나 글로벌 티커를 다시 확인하십시오. (예: 국내 229200 → 229200.KS, 글로벌 AAPL)")
            
        except Exception as e:
            progress_placeholder.empty()
            st.error(f"📡 시스템 오류: {str(e)}")
            st.info("💡 시스템 점검  중입니다. 잠시 후 다시 시도해주세요.")
