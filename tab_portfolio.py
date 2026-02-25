import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from portfolio_manager import load_portfolio, save_portfolio
from engine import analyze_stock 
from market_data import get_all_krx_stocks  # [수술] 전 종목 엔진 로드
from style_utils import apply_global_style
import yfinance as yf
from datetime import datetime

@st.cache_data(ttl=3600)  # 1시간마다 업데이트
def get_current_exchange_rate():
    """현재 USD/KRW 고시 환율을 실시간으로 가져오기 (한국은행 기준)"""
    try:
        # yfinance에서 USD/KRW 환율 데이터 가져오기
        usd_krw = yf.download("USDKRW=X", period="1d", interval="1d", progress=False)
        if not usd_krw.empty:
            rate = usd_krw['Close'].iloc[-1]
            if hasattr(rate, 'item'):  # numpy scalar 또는 Series
                rate = float(rate.item())
            else:
                rate = float(rate)
            return round(rate, 2)
    except:
        pass
    
    # 실패 시 기본값 (약 1,300원)
    return 1300.0

@st.dialog("🔬 AI 전문가 통합 진단 보고서")
def show_expert_popup(stock):
    apply_global_style() # 팝업 내 가독성 강제 적용
    
    # v5.0 엔진 규격 준수: 5개 변수 수령 및 Shape 오류 방어 완료
    df, score, msg, details, stop_loss = analyze_stock(stock['ticker'], apply_fundamental=True)
    
    if df is not None:
        curr_p = float(df['Close'].iloc[-1])  # yfinance 원본가 (USD 종목은 USD, KRW 종목은 KRW)
        quantity = stock.get('quantity', 0)
        buy_price = stock.get('buy_price', 0)  # 저장된 값 (USD 종목은 원화로 저장됨)
        currency = stock.get('currency', 'KRW')
        exchange_rate = stock.get('exchange_rate', 1.0)
        
        # 🚨 [The Closer's 수익률 계산 수정]
        # 외화 주식은 먼저 USD 기준으로 통일해서 계산한 뒤, 마지막에 화면 표시용으로만 원화 환산
        if currency == "USD":
            # USD 기준 계산
            buy_price_usd = buy_price / exchange_rate  # 저장된 원화 → USD
            curr_p_usd = curr_p  # yfinance에서 가져온 값은 이미 USD
            
            # USD 기준 총액
            invest_usd = buy_price_usd * quantity
            eval_usd = curr_p_usd * quantity
            
            # 수익률 계산 (USD 기준)
            profit = ((eval_usd - invest_usd) / invest_usd) * 100 if invest_usd > 0 else 0
            
            # 화면 표시용 원화 환산
            total_buy = invest_usd * exchange_rate  # 총 투자금 (KRW)
            total_val = eval_usd * exchange_rate    # 평가금액 (KRW)
            total_buy_usd = invest_usd
            total_val_usd = eval_usd
            currency_symbol = "$"
        else:
            # KRW 종목은 그대로
            total_buy = buy_price * quantity
            total_val = curr_p * quantity
            profit = ((curr_p - buy_price) / buy_price) * 100 if buy_price > 0 else 0
            total_buy_usd = total_buy
            total_val_usd = total_val
            curr_p_usd = curr_p
            buy_price_usd = buy_price
            currency_symbol = "₩"
        
        p_color = "up" if profit >= 0 else "down"
        
        st.markdown(f"<h2 style='font-weight:800; color:white;'>{stock['name']} 자산 리포트</h2>", unsafe_allow_html=True)
        
        # 3열 메트릭 레이아웃
        m1, m2, m3 = st.columns(3)
        with m1: st.markdown(f"<div class='m-card'><div style='color:gray; font-size:0.8rem;'>수익률</div><div class='m-value {p_color}'>{profit:+.2f}%</div></div>", unsafe_allow_html=True)
        with m2: 
            if currency == "USD":
                st.markdown(f"<div class='m-card'><div style='color:gray; font-size:0.8rem;'>평가금액</div><div class='m-value'>${total_val_usd:,.2f}</div></div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='m-card'><div style='color:gray; font-size:0.8rem;'>평가금액</div><div class='m-value'>₩{int(total_val_usd):,}</div></div>", unsafe_allow_html=True)
        with m3: st.markdown(f"<div class='m-card'><div style='color:gray; font-size:0.8rem;'>AI 점수</div><div class='m-value' style='color:white;'>{score}점</div></div>", unsafe_allow_html=True)
        
        st.write("---")
        st.markdown(f"#### 🚩 **{msg}**")
        if currency == "USD":
            st.caption(f"보유수량: {quantity:,.2f}주 | 총 투자금: ${total_buy_usd:,.2f} (₩{int(total_buy):,})")
        else:
            st.caption(f"보유수량: {quantity:,}주 | 총 투자금: ₩{int(total_buy):,}")
        
        # ---------------------------------------------------------
        # 엔진 details에서 진짜 퀀트 리포트 추출 후 강조 출력
        # ---------------------------------------------------------
        closer_opinion = None
        fund_opinion = None
        for info in details:
            if "The Closer's 실시간 의견" in info.get("title", ""):
                closer_opinion = info.get("full_comment", "")
            elif "펀더멘털 검증" in info.get("title", ""):
                fund_opinion = info.get("full_comment") or info.get("comment", "")
        
        if fund_opinion:
            st.error(f"**🏢 펀더멘털(재무) 검증:** {fund_opinion}", icon="🚨")
        if closer_opinion:
            st.info(closer_opinion, icon="🎯")
        # ---------------------------------------------------------
        
        # 기술지표 전체 딥 뷰 (접기 가능하도록 expander 처리)
        with st.expander("📊 기술지표 전체 분석 보기", expanded=False):
            for item in details:
                if "실시간 의견" in item.get("title", ""):
                    continue  # 이미 위에서 출력했으므로 스킵
                st.markdown(f"📍 **{item['title']}**<br><span style='font-size:0.85rem; color:#8e8e93;'>{item['full_comment']}</span>", unsafe_allow_html=True)
        
        # 🎯 [신규] 기술지표 차트 렌더링
        st.write("### 📈 가격 추이 & 지표 시각화")
        
        # 캔들스틱 차트 + RSI
        fig = go.Figure()
        
        # 캔들스틱
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
            name='가격'
        ))
        
        # 이동평균선
        if 'Close' in df.columns:
            ma20 = df['Close'].rolling(window=20).mean()
            ma60 = df['Close'].rolling(window=60).mean()
            fig.add_trace(go.Scatter(x=df.index, y=ma20, mode='lines', name='20일 이동평균', line=dict(color='orange')))
            fig.add_trace(go.Scatter(x=df.index, y=ma60, mode='lines', name='60일 이동평균', line=dict(color='blue')))
        
        fig.update_layout(
            title=f"{stock['name']} 캔들스틱 차트 (최근 3개월)",
            xaxis_title="날짜",
            yaxis_title="가격 (원/달러)",
            height=400,
            hovermode='x unified',
            template='plotly_dark'
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # RSI 차트
        if 'rsi' in df.columns:
            fig_rsi = go.Figure()
            fig_rsi.add_trace(go.Scatter(x=df.index, y=df['rsi'], mode='lines', name='RSI(14)', line=dict(color='purple')))
            fig_rsi.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="과매수(70)")
            fig_rsi.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="과매도(30)")
            fig_rsi.update_layout(
                title="RSI (Relative Strength Index)",
                xaxis_title="날짜",
                yaxis_title="RSI",
                height=300,
                hovermode='x unified',
                template='plotly_dark'
            )
            st.plotly_chart(fig_rsi, use_container_width=True)
        
        # MACD 차트
        if 'macd' in df.columns and 'macd_sig' in df.columns:
            fig_macd = go.Figure()
            fig_macd.add_trace(go.Scatter(x=df.index, y=df['macd'], mode='lines', name='MACD', line=dict(color='blue')))
            fig_macd.add_trace(go.Scatter(x=df.index, y=df['macd_sig'], mode='lines', name='Signal', line=dict(color='red')))
            fig_macd.update_layout(
                title="MACD (Moving Average Convergence Divergence)",
                xaxis_title="날짜",
                yaxis_title="MACD",
                height=300,
                hovermode='x unified',
                template='plotly_dark'
            )
            st.plotly_chart(fig_macd, use_container_width=True)
    else: st.error("❌ 데이터 로드 실패")

def show_rebalancing_analysis(my_stocks):
    """포트폴리오 리밸런싱 분석 함수 - Enhanced UI"""
    if not my_stocks:
        st.warning("먼저 종목을 등록하십시오.")
        return

    st.info("💡 본 진단은 AI 신뢰 점수와 기술적 지표를 기반으로 한 포트폴리오 최적화 컨설팅입니다.")

    results = []
    failed_stocks = []
    total_eval_value = 0
    # 해외(USD) 원문 합계(USD 기준)
    total_eval_value_usd = 0.0
    
    with st.status("🚀 포트폴리오 정밀 해부 중...", expanded=True) as status:
        # [환율 전역 캐시] 루프 전 1회 호출 — 루프 내 반복 API 호출 제거
        fx_rate_session = float(get_current_exchange_rate())

        for stock in my_stocks:
            try:
                df, score, msg, _, _ = analyze_stock(stock['ticker'], apply_fundamental=True)
                if df is not None and score is not None:
                    # 원화 환산 처리: 글로벌(USD) 자산은 환율을 적용하여 KRW로 통일
                    curr_price = float(df['Close'].iloc[-1])
                    prev_price = float(df['Close'].iloc[-2]) if len(df) > 1 else curr_price

                    currency = stock.get('currency', 'KRW')
                    exchange_rate = stock.get('exchange_rate', None)
                    # 루프 밖에서 가져온 환율 사용 (API 중복 호출 제거)
                    if currency == 'USD' and (not exchange_rate or exchange_rate == 1.0):
                        exchange_rate = fx_rate_session

                    if currency == 'USD':
                        curr_price_krw = curr_price * exchange_rate
                        prev_price_krw = prev_price * exchange_rate
                        # 원문(USD) 합계에 더함
                        total_eval_value_usd += curr_price * float(stock.get('quantity', 0))
                    else:
                        curr_price_krw = curr_price
                        prev_price_krw = prev_price

                    change_rate = ((curr_price_krw - prev_price_krw) / prev_price_krw * 100) if prev_price_krw != 0 else 0
                    eval_val = curr_price_krw * stock['quantity']
                    total_eval_value += eval_val
                    
                    results.append({
                        "종목명": stock['name'],
                        "티커": stock['ticker'],
                        # 현재가는 원화 기준으로 통일하여 표시
                        "현재가": curr_price_krw,
                        # 원문 가격/통화 정보도 함께 보관
                        "원문현재가": curr_price,
                        "원문통화": currency,
                        "보유수량": stock['quantity'],
                        "평가금액": eval_val,
                        "원문평가금액": curr_price * stock['quantity'] if currency == 'USD' else None,
                        "변화율": change_rate,
                        "AI점수": score,
                        "상태": msg,
                        "통화": stock.get('currency', 'KRW'),
                        "환율": exchange_rate if exchange_rate is not None else 1.0
                    })
                else:
                    failed_stocks.append(stock['name'])
            except Exception as e:
                failed_stocks.append(stock['name'])
                
        status.update(label="✅ 포트폴리오 분석 완료", state="complete")
    
    if failed_stocks:
        st.warning(f"⚠️ {', '.join(failed_stocks)} 데이터를 불러올 수 없습니다. 티커를 확인하세요.")

    if results and total_eval_value > 0:
        df_p = pd.DataFrame(results)
        
        # 현재 비중 계산
        df_p['현재비중(%)'] = (df_p['평가금액'] / total_eval_value) * 100
        
        # AI 점수 기반 목표 비중 계산
        score_sum = df_p['AI점수'].sum()
        if score_sum > 0:
            df_p['목표비중(%)'] = (df_p['AI점수'] / score_sum) * 100
        else:
            df_p['목표비중(%)'] = 100 / len(df_p)
        
        df_p['조정제안'] = df_p['목표비중(%)'] - df_p['현재비중(%)']
        df_p['조정금액'] = (df_p['조정제안'] / 100) * total_eval_value
        
        # 색상 그라데이션: 조정 필요도
        def get_action_color(adjustment):
            if adjustment > 10:
                return "#ff4444"  # 강한 매수
            elif adjustment > 5:
                return "#ff8844"  # 약한 매수
            elif adjustment < -10:
                return "#4444ff"  # 강한 매도
            elif adjustment < -5:
                return "#8844ff"  # 약한 매도
            else:
                return "#44ff44"  # 유지
        
        df_p['색상'] = df_p['조정제안'].apply(get_action_color)
        
        # 0. 포트폴리오 개요
        st.markdown("### 📈 포트폴리오 개요")
        col_overview1, col_overview2, col_overview3, col_overview4 = st.columns(4)
        with col_overview1:
            st.metric("총 평가액 (KRW)", str(f"{int(float(total_eval_value)):,}원"))
            # 해외(USD) 원문 합계 표시
            try:
                if total_eval_value_usd > 0:
                    st.caption(f"해외 평가 합계: ${total_eval_value_usd:,.2f} (원문 기준)")
            except:
                pass
        with col_overview2:
            st.metric("보유 종목", str(f"{len(df_p)}개"))
        with col_overview3:
            avg_score = float(df_p['AI점수'].mean())
            st.metric("평균 신뢰도", str(f"{avg_score:.1f}점"))
        with col_overview4:
            total_change = float((df_p['평가금액'] * df_p['변화율'] / 100).sum())
            change_color = "📈" if total_change >= 0 else "📉"
            st.metric("총 변화액", str(f"{change_color} {int(total_change):,}원"))
        
        st.write("---")

        # 1. 현재 vs 목표 비중 비교
        st.markdown("### 📊 포트폴리오 리밸런싱 분석")
        st.write("**현재 비중 vs AI 권장 최적 비중 비교**: 각 종목이 현재 얼마의 비중을 차지하고 있으며, AI가 제시하는 최적 비중은 얼마인지 시각화합니다.")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            fig_curr = px.pie(df_p, values='현재비중(%)', names='종목명', title="현재 포트폴리오", hole=.3, template="plotly_dark")
            st.plotly_chart(fig_curr, use_container_width=True)
        with c2:
            fig_target = px.pie(df_p, values='목표비중(%)', names='종목명', title="AI 권장 최적 비중", hole=.3, template="plotly_dark")
            st.plotly_chart(fig_target, use_container_width=True)
        with c3:
            # 조정 후 예상 비중
            df_p['조정후비중(%)'] = df_p['현재비중(%)'] + df_p['조정제안']
            fig_after = px.pie(df_p, values='조정후비중(%)', names='종목명', title="조정 후 예상 비중", hole=.3, template="plotly_dark")
            st.plotly_chart(fig_after, use_container_width=True)

        # 2. 비중 조정 계획
        st.markdown("### 🔄 비중 조정 계획")
        st.write("**막대 그래프 해석**: 파란색은 현재 비중, 빨간색은 목표 비중입니다. 금액 차이가 클수록 더 큰 조정이 필요합니다.")
        
        fig_adjust = go.Figure(data=[
            go.Bar(name='현재 비중', x=df_p['종목명'], y=df_p['현재비중(%)'], marker_color='#3498db'),
            go.Bar(name='목표 비중', x=df_p['종목명'], y=df_p['목표비중(%)'], marker_color='#e74c3c')
        ])
        fig_adjust.update_layout(
            barmode='group',
            title="현재 비중 vs 목표 비중",
            xaxis_title="종목",
            yaxis_title="비중 (%)",
            template="plotly_dark",
            height=400
        )
        st.plotly_chart(fig_adjust, use_container_width=True)

        # 3. Risk-Return Scatter
        st.markdown("### 📉 Risk-Return 분석")
        st.write("**차트 해석**: X축은 변동성(위험도), Y축은 AI 신뢰도(수익성)입니다. 우상향은 높은 수익 잠재력, 하좌향은 낮은 위험을 의미합니다.")
        
        df_p['변동성'] = abs(df_p['변화율'])
        fig_risk = go.Figure()
        
        for idx, row in df_p.iterrows():
            fig_risk.add_trace(go.Scatter(
                x=[row['변동성']], y=[row['AI점수']], 
                mode='markers+text',
                marker=dict(size=int(row['현재비중(%)']*5)+10, color=row['색상'], opacity=0.6),
                text=row['종목명'],
                textposition='top center',
                hovertemplate=f"<b>{row['종목명']}</b><br>변동성: {row['변동성']:.2f}%<br>AI점수: {row['AI점수']:.0f}점<extra></extra>"
            ))
        
        fig_risk.update_layout(
            title="Risk-Return 포지셔닝",
            xaxis_title="변동성 (위험도)",
            yaxis_title="AI 신뢰도 (수익성)",
            template="plotly_dark",
            height=400,
            showlegend=False
        )
        st.plotly_chart(fig_risk, use_container_width=True)

        st.write("---")

        # 4. 종목별 상세 리밸런싱 전략
        st.markdown("### 🛠️ 종목별 리밸런싱 전략")
        
        max_ratio = df_p['현재비중(%)'].max()
        if max_ratio > 40:
            st.warning(f"⚠️ **집중 위험 알림**: 포트폴리오 다양성이 부족합니다. 최대 보유 비중이 {max_ratio:.1f}%입니다.")
        
        # 요약 테이블
        st.markdown("#### 📋 종목별 요약")
        summary_df = df_p[[
            '종목명', 'AI점수', '현재비중(%)', '목표비중(%)', 
            '조정제안', '조정금액', '변화율'
        ]].copy()
        summary_df['AI점수'] = summary_df['AI점수'].apply(lambda x: f"{x:.0f}점")
        summary_df['현재비중(%)'] = summary_df['현재비중(%)'].apply(lambda x: f"{x:.1f}%")
        summary_df['목표비중(%)'] = summary_df['목표비중(%)'].apply(lambda x: f"{x:.1f}%")
        summary_df['조정제안'] = summary_df['조정제안'].apply(lambda x: f"{x:+.1f}%")
        summary_df['조정금액'] = summary_df['조정금액'].apply(lambda x: f"{int(x):+,}원")
        summary_df['변화율'] = summary_df['변화율'].apply(lambda x: f"{x:+.2f}%")
        
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
        
        st.write("")
        
        # 상세 카드
        for idx, row in df_p.iterrows():
            adjustment = float(row['조정제안'])
            
            # 액션 타입 결정
            if adjustment > 5:
                action_emoji = "🔥"
                action_label = "비중 확대"
                action_color = "🟢"
            elif adjustment < -5:
                action_emoji = "🚨"
                action_label = "비중 축소"
                action_color = "🔴"
            else:
                action_emoji = "⚖️"
                action_label = "유지"
                action_color = "🟡"
            
            with st.container(border=True):
                # 상단: 종목명과 액션
                col_header = st.columns([2, 1])
                with col_header[0]:
                    st.markdown(f"### {action_emoji} {row['종목명']} ({row['티커']})")
                with col_header[1]:
                    st.markdown(f"<div style='text-align: right; font-size: 1.5rem;'>{action_color} {action_label}</div>", unsafe_allow_html=True)
                
                st.write("---")
                
                # 좌측: AI 점수와 손익 | 우측: 비중 정보
                col_left, col_mid, col_right = st.columns([1.2, 1.5, 1.5])
                
                with col_left:
                    st.markdown("#### 📊 AI 분석")
                    ai_score = float(row['AI점수'])
                    if ai_score >= 80:
                        score_emoji = "🏆"
                    elif ai_score >= 70:
                        score_emoji = "✅"
                    else:
                        score_emoji = "⚠️"
                    st.metric(f"{score_emoji} AI 신뢰도", str(f"{ai_score:.0f}점"))
                    
                    profit_loss = float(row['평가금액']) * float(row['변화율']) / 100
                    profit_icon = "📈" if profit_loss >= 0 else "📉"
                    st.metric(f"{profit_icon} 손익", str(f"{int(profit_loss):,}원"), 
                             delta=str(f"{float(row['변화율']):+.2f}%"))
                
                with col_mid:
                    st.markdown("#### 💰 비중 현황")
                    st.metric("현재 비중", str(f"{float(row['현재비중(%)']):,.1f}%"))
                    st.metric("목표 비중", str(f"{float(row['목표비중(%)']):,.1f}%"))
                
                with col_right:
                    st.markdown("#### 🎯 조정 제안")
                    st.metric("조정 필요량", str(f"{adjustment:+.1f}%"))
                    adjustment_amount = float(row['조정금액'])
                    st.metric("조정 금액", str(f"{int(adjustment_amount):+,}원"))
                
                st.write("---")
                
                # 전문가 코멘트
                if adjustment > 10:
                    advice = f"""
🔥 **강한 매수 권장**

{row['종목명']}의 AI 신뢰도가 **{ai_score:.0f}점**으로 높지만, 현재 비중({float(row['현재비중(%)']):,.1f}%)이 목표 비중({float(row['목표비중(%)']):,.1f}%)보다 크게 부족합니다.

**추가 매수 금액**: {int(abs(adjustment_amount)):,}원
**현재 강점**: {row['상태']}

추세 흐름이 상승하고 있으니, 자금 여유가 있다면 이 구간에서 추가 매수를 고려하실 타이밍입니다. 
큰손들의 수급이 활발한 상황이므로 적극적으로 포지션을 키우는 것도 좋아요.
                    """
                elif adjustment > 5:
                    advice = f"""
📈 **중약한 매수 추천**

{row['종목명']}은 AI 신뢰도 {ai_score:.0f}점으로 양호하지만, 현재 비중 조정이 필요합니다.

**추가 매수 금액**: {int(abs(adjustment_amount)):,}원

점진적으로 비중을 높여나가는 것을 권장합니다. 지표의 재확인 신호를 기다린 후 단계적으로 매수하면 위험을 줄일 수 있습니다.
                    """
                elif adjustment < -10:
                    advice = f"""
🚨 **강한 매도 권장**

{row['종목명']}의 비중({float(row['현재비중(%)']):,.1f}%)이 목표 비중({float(row['목표비중(%)']):,.1f}%)보다 크게 초과되어 있습니다.

**매도 권장 금액**: {int(abs(adjustment_amount)):,}원
**현재 상태**: {row['상태']}

수익 확정이나 손절을 고려해야 할 시점입니다. 더 강한 종목으로 갈아타거나 위험 노출을 줄이시길 권장합니다.
                    """
                elif adjustment < -5:
                    advice = f"""
📉 **중약한 매도 추천**

{row['종목명']}의 비중 재조정이 필요합니다.

**매도 권장 금액**: {int(abs(adjustment_amount)):,}원

현재 포지션의 일부를 정리하고 더 강한 신호를 보이는 종목으로 자금을 이동시키는 것을 고려하세요.
시장 상황을 보며 단계적으로 정리하시는 것이 현명합니다.
                    """
                else:
                    advice = f"""
⚖️ **현재 보유 유지**

{row['종목명']}은 현재 비중 배치가 적절합니다.

**AI 신뢰도**: {ai_score:.0f}점
**평가액**: {int(float(row['평가금액'])):,}원

추가 매수나 매도할 필요가 없습니다. 시장 흐름을 관망하면서 
다음 신호를 기다리세요. 무리한 조정은 오히려 수익 기회를 놓칠 수 있습니다.
                    """
                
                st.info(advice)
                
                # 매수/매도 액션 버튼
                action_col1, action_col2, action_col3, action_col4 = st.columns(4)
                
                with action_col1:
                    if st.button(f"🛒 주문 시뮬레이션", key=f"action_{idx}", use_container_width=True):
                        st.session_state[f"simulate_{idx}"] = not st.session_state.get(f"simulate_{idx}", False)
                
                # 시뮬레이션 결과 표시
                if st.session_state.get(f"simulate_{idx}", False):
                    st.success(f"""
✅ **{row['종목명']} 주문 시뮬레이션**

**현재 상태**
- 현재 비중: {float(row['현재비중(%)']):,.1f}%
- 평가액: {int(float(row['평가금액'])):,}원

**조정 후 예상**
- 목표 비중: {float(row['목표비중(%)']):,.1f}%
- 조정 금액: {int(abs(adjustment_amount)):,}원
- 예상 비중: {float(row['조정후비중(%)']):,.1f}%

이 시뮬레이션은 실제 주문이 아닙니다. 참고만 하시기 바랍니다.
                    """)
        
        st.write("---")

        # 5. 최종 요약 리포트
        st.markdown("### 📋 포트폴리오 평가 최종 보고서")
        col_summary1, col_summary2, col_summary3 = st.columns(3)
        
        with col_summary1:
            avg_score = float(df_p['AI점수'].mean())
            if avg_score >= 80:
                grade = "🏆 탁월"
            elif avg_score >= 70:
                grade = "✅ 우수"
            else:
                grade = "⚠️ 보통"
            st.metric("포트폴리오 등급", str(grade))
        
        with col_summary2:
            total_rebalance = int(df_p[abs(df_p['조정제안']) > 5].shape[0])
            st.metric("조정 필요 종목", str(f"{total_rebalance}개"))
        
        with col_summary3:
            diversification = float(100 - df_p['현재비중(%)'].max())
            st.metric("다양성 지수", str(f"{diversification:.1f}%"))
        
        final_summary = f"""
✅ **최종 평가**: 현재 포트폴리오는 AI 신뢰도 **{float(df_p['AI점수'].mean()):.1f}점**으로 양호한 상태입니다.

**조정 방향**:
- 📈 매수 추천: {len(df_p[df_p['조정제안'] > 5])}개 종목
- 📉 매도 추천: {len(df_p[df_p['조정제안'] < -5])}개 종목  
- ⚖️ 유지: {len(df_p[abs(df_p['조정제안']) <= 5])}개 종목

위의 종목별 조정 제안을 참고해서 더 강한 종목에 자원을 집중시키면, 
장기적으로 더 안정적이고 수익성 있는 포트폴리오가 될 거야. 

**주의**: 조정 전에 손익 현황과 세금을 꼭 확인해봐!
        """
        
        st.success(final_summary)
        
    else:
        st.error("❌ 분석 가능한 종목이 없습니다. 데이터를 다시 확인하세요.")

def run_portfolio_tab(unused_stock_dict):
    user_id = st.session_state.user_id
    st.session_state.my_stocks = load_portfolio(user_id)

    # --- 0. AI 컨설팅 버튼 ---
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 3])
    with col_btn1:
        if st.button("⚖️ AI 리밸런싱 조언", use_container_width=True):
            st.session_state.show_rebalancing = True
    with col_btn2:
        if st.button("❌ 닫기", use_container_width=True):
            st.session_state.show_rebalancing = False
    
    # 리밸런싱 분석 표시
    if st.session_state.get('show_rebalancing', False):
        st.write("---")
        st.markdown("### ⚖️ 전문가 리밸런싱 조언")
        show_rebalancing_analysis(st.session_state.my_stocks)
        st.write("---")

    # --- 1. [핵심 수술] 국내 vs 글로벌 등록 모드 이원화 ---
    reg_mode = st.radio("등록할 시장을 선택하십시오", ["🇰🇷 국내 주식", "🌎 글로벌 자산"], horizontal=True)
    
    with st.container(border=True):
        st.markdown(f"### ➕ {reg_mode} 신규 등록")
        
        if reg_mode == "🇰🇷 국내 주식":
            c1, c2, c3, c4 = st.columns([2, 1.2, 1.2, 0.8])
            
            with c1:
                kr_stocks = get_all_krx_stocks()
                reg_name = st.selectbox("종목 검색", list(kr_stocks.keys()), key="kr_reg_sb")
                reg_ticker = kr_stocks[reg_name]
            with c2: 
                reg_price = st.number_input("평균 매수가 (원)", min_value=0.0, step=100.0, key="p_reg_ni")
            with c3: 
                reg_qty = st.number_input("보유좌수 (주)", min_value=0.0, step=1.0, key="q_reg_ni")
            with c4:
                st.write(" ")
                if st.button("등록", type="primary", use_container_width=True):
                    if reg_ticker and reg_price > 0 and reg_qty > 0:
                        new_item = {
                            "name": reg_name, 
                            "ticker": reg_ticker, 
                            "buy_price": reg_price,
                            "quantity": reg_qty,
                            "buy_date": datetime.now().strftime("%Y-%m-%d")
                        }
                        st.session_state.my_stocks.append(new_item)
                        if save_portfolio(user_id, st.session_state.my_stocks):
                            st.session_state.my_stocks = load_portfolio(user_id)
                            st.success(f"✅ {reg_name} 등록 완료!")
                            st.rerun()
                        else:
                            st.error("❌ 등록 중 오류가 발생했습니다.")
                    else: 
                        st.error("⚠️ 모든 항목을 입력하고 가격/수량은 0보다 커야 합니다.")
        
        else:  # 글로벌 자산
            # 💱 통화 선택 및 고시 환율 자동 조회
            c_mode, c_rate = st.columns([1, 1.5])
            with c_mode:
                price_currency = st.radio("가격 통화", ["USD 🇺🇸", "KRW 🇰🇷"], horizontal=True, key="currency_mode")
            with c_rate:
                # 고시 환율 자동 조회 (캐시됨, 1시간마다 업데이트)
                exchange_rate = float(get_current_exchange_rate())
                st.write(f"### 📊 현재 고시 환율: 1 USD = ₩{float(exchange_rate):,.0f}")
            
            # 글로벌 자산 등록 필드
            c1, c2, c3, c4, c5 = st.columns([1.5, 1.0, 1.0, 1.0, 0.7])
            
            with c1:
                reg_ticker = st.text_input("글로벌 티커 입력", placeholder="예: TSLA, AAPL, BTC-USD", key="gl_reg_ti").strip().upper()
                reg_name = reg_ticker
            
            with c2:
                if price_currency == "USD 🇺🇸":
                    reg_price_input = st.number_input(f"평균 매수가 (USD)", min_value=0.0, step=1.0, key="p_usd_ni")
                else:
                    reg_price_input = st.number_input(f"평균 매수가 (KRW)", min_value=0.0, step=100.0, key="p_krw_ni")
            
            with c3:
                reg_qty = st.number_input("보유수량", min_value=0.0, step=0.01, key="q_gl_ni")
            
            with c4:
                # 원화 환산 미리보기 (총 투자금 = 단가 × 수량 × 환율)
                if price_currency == "USD 🇺🇸":
                    total_usd = float(reg_price_input) * float(reg_qty)
                    converted_krw = total_usd * float(exchange_rate)
                    st.metric("환산 원화 (총액)", str(f"₩{int(converted_krw):,}"))
                else:
                    st.write(" ")
            
            with c5:
                st.write(" ")
                if st.button("등록", type="primary", use_container_width=True, key="btn_gl_reg"):
                    if reg_ticker and reg_price_input > 0 and reg_qty > 0:
                        # 최종 저장 시 원화로 통일
                        final_price = reg_price_input * exchange_rate if price_currency == "USD 🇺🇸" else reg_price_input
                        
                        new_item = {
                            "name": reg_name, 
                            "ticker": reg_ticker, 
                            "buy_price": final_price,
                            "quantity": reg_qty,
                            "buy_date": datetime.now().strftime("%Y-%m-%d"),
                            "currency": price_currency.split()[0],  # "USD" 또는 "KRW"
                            "exchange_rate": exchange_rate if price_currency == "USD 🇺🇸" else 1.0
                        }
                        st.session_state.my_stocks.append(new_item)
                        if save_portfolio(user_id, st.session_state.my_stocks):
                            st.session_state.my_stocks = load_portfolio(user_id)
                            st.success(f"✅ {reg_name} 등록 완료! (₩{final_price:,.0f})")
                            st.rerun()
                        else:
                            st.error("❌ 등록 중 오류가 발생했습니다.")
                    else: 
                        st.error("⚠️ 모든 항목을 입력하고 가격/수량은 0보다 커야 합니다.")

    st.write("---")

    # --- 2. 등록된 종목 리스트 ---
    if not st.session_state.my_stocks:
        st.info("현재 등록된 종목이 없습니다. 상단에서 시장을 선택하고 종목을 추가하십시오.")
    else:
        # 최신 등록 종목이 위로 오도록 역순 출력
        for idx, stock in enumerate(reversed(st.session_state.my_stocks)):
            actual_idx = len(st.session_state.my_stocks) - 1 - idx
            with st.container(border=True):
                try:
                    result = analyze_stock(stock['ticker'], apply_fundamental=True)
                    if result and result[0] is not None:
                        _, score, msg, _, _ = result
                    else:
                        score = 0
                        msg = "⚠️ 데이터 로드 실패 (티커 확인 필요)"
                except Exception:
                    score = 0
                    msg = "⚠️ API 연결 오류"
                qty = stock.get('quantity', 0)
                buy_price = stock.get('buy_price', 0)
                currency = stock.get('currency', 'KRW')
                exchange_rate = stock.get('exchange_rate', 1.0)
                
                c1, c2, c3, c4 = st.columns([1.5, 3.0, 1.5, 0.5])
                with c1: 
                    if st.button(f"🔍 {stock['name']}", key=f"b_{actual_idx}", use_container_width=True): 
                        show_expert_popup(stock)
                with c2: 
                    st.markdown(f"<span style='color:#888;'>[{score}점]</span> **{msg}**", unsafe_allow_html=True)
                with c3:
                    if currency == "USD":
                        usd_price = buy_price / exchange_rate
                        st.write(f"**${usd_price:,.2f}** (₩{buy_price:,.0f})")
                        st.caption(f"{qty:,.2f}주 보유 중")
                    else:
                        st.write(f"**₩{buy_price:,}**")
                        st.caption(f"{qty:,}주 보유 중")
                with c4:
                    if st.button("🗑️", key=f"d_{actual_idx}"):
                        st.session_state.my_stocks.pop(actual_idx)
                        save_portfolio(user_id, st.session_state.my_stocks)
                        st.session_state.my_stocks = load_portfolio(user_id)
                        st.rerun()