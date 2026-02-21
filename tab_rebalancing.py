import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from engine import analyze_stock
from style_utils import apply_global_style

def run_rebalancing_tab(my_stocks):
    apply_global_style()
    st.markdown("<h1 style='color:white; font-weight:800;'>⚖️ 전문가 리밸런싱 조언</h1>", unsafe_allow_html=True)
    
    if not my_stocks:
        st.warning("먼저 '내 계좌 관리' 탭에서 종목을 등록하십시오.")
        return

    st.info("💡 본 진단은 AI 신뢰 점수와 기술적 지표를 기반으로 한 포트폴리오 최적화 컨설팅입니다.")

    results = []
    failed_stocks = []
    total_eval_value = 0
    
    with st.status("🚀 포트폴리오 정밀 해부 중...", expanded=True) as status:
        for stock in my_stocks:
            # v5.0 엔진으로 실시간 데이터 및 점수 추출
            try:
                df, score, msg, _, _ = analyze_stock(stock['ticker'])
                if df is not None and score is not None:
                    curr_price = df['Close'].iloc[-1]
                    prev_price = df['Close'].iloc[-2] if len(df) > 1 else curr_price
                    change_rate = ((curr_price - prev_price) / prev_price * 100) if prev_price != 0 else 0
                    eval_val = curr_price * stock['quantity']
                    total_eval_value += eval_val
                    
                    results.append({
                        "종목명": stock['name'],
                        "티커": stock['ticker'],
                        "현재가": curr_price,
                        "보유수량": stock['quantity'],
                        "평가금액": eval_val,
                        "변화율": change_rate,
                        "AI점수": score,
                        "상태": msg
                    })
                else:
                    failed_stocks.append(stock['name'])
            except Exception as e:
                failed_stocks.append(stock['name'])
                
        status.update(label="✅ 포트폴리오 분석 완료", state="complete")
    
    # 로드 실패 종목 알림
    if failed_stocks:
        st.warning(f"⚠️ {', '.join(failed_stocks)} 데이터를 불러올 수 없습니다. 티커를 확인하세요.")

    if results and total_eval_value > 0:
        df_p = pd.DataFrame(results)
        
        # 현재 비중 계산
        df_p['현재비중(%)'] = (df_p['평가금액'] / total_eval_value) * 100
        
        # AI 점수 기반 목표 비중 계산 (점수 정규화)
        score_sum = df_p['AI점수'].sum()
        if score_sum > 0:
            df_p['목표비중(%)'] = (df_p['AI점수'] / score_sum) * 100
        else:
            df_p['목표비중(%)'] = 100 / len(df_p)
        
        # 조정 필요분 (목표 - 현재)
        df_p['조정제안'] = df_p['목표비중(%)'] - df_p['현재비중(%)']
        
        # 조정 필요 금액 계산
        df_p['조정금액'] = (df_p['조정제안'] / 100) * total_eval_value
        
        # 0. 포트폴리오 요약
        st.write("### 📈 포트폴리오 개요")
        col_overview1, col_overview2, col_overview3, col_overview4 = st.columns(4)
        with col_overview1:
            st.metric("총 평가액", f"{int(total_eval_value):,}원")
        with col_overview2:
            st.metric("보유 종목", f"{len(df_p)}개")
        with col_overview3:
            avg_score = df_p['AI점수'].mean()
            st.metric("평균 신뢰도", f"{avg_score:.1f}점")
        with col_overview4:
            total_change = (df_p['평가금액'] * df_p['변화율'] / 100).sum()
            change_color = "📈" if total_change >= 0 else "📉"
            st.metric("총 변화액", f"{change_color} {int(total_change):,}원")
        
        st.write("---")

        # 1. 시각화: 현재 vs 목표 비중 비교
        st.write("### 📊 포트폴리오 리밸런싱 분석")
        c1, c2 = st.columns(2)
        with c1:
            fig_curr = px.pie(df_p, values='현재비중(%)', names='종목명', title="현재 포트폴리오 비중", hole=.3, template="plotly_dark")
            st.plotly_chart(fig_curr, use_container_width=True)
        with c2:
            fig_target = px.pie(df_p, values='목표비중(%)', names='종목명', title="AI 권장 최적 비중", hole=.3, template="plotly_dark")
            st.plotly_chart(fig_target, use_container_width=True)

        # 2. 조정 비중 비교 막대 그래프
        st.write("### 🔄 비중 조정 계획")
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

        st.write("---")

        # 3. 상세 종목별 리밸런싱 전략
        st.write("### 🛠️ 종목별 리밸런싱 전략")
        
        # 리스크 경고: 최대 보유 비중이 40% 이상인 경우
        max_ratio = df_p['현재비중(%)'].max()
        if max_ratio > 40:
            st.warning(f"⚠️ **집중 위험 알림**: {df_p[df_p['현재비중(%)'] == max_ratio]['종목명'].values[0]} 종목에 {max_ratio:.1f}%가 집중되어 있습니다. 분산 투자를 권장합니다.")
        
        for idx, row in df_p.iterrows():
            adjustment = row['조정제안']
            
            # 조정 필요성에 따라 색상 구분
            if adjustment > 5:
                border_color = "🔥"
                action_type = "비중 확대"
            elif adjustment < -5:
                border_color = "🚨"
                action_type = "비중 축소"
            else:
                border_color = "⚖️"
                action_type = "유지"
            
            with st.container(border=True):
                col_name, col_detail = st.columns([1.2, 2.8])
                
                # 좌측: 종목 정보
                with col_name:
                    st.markdown(f"### {border_color} {row['종목명']}")
                    st.caption(f"티커: {row['티커']}")
                    st.metric("AI 신뢰도", f"{row['AI점수']:.0f}점")
                    
                    profit_loss = row['평가금액'] * row['변화율'] / 100
                    profit_icon = "📈" if profit_loss >= 0 else "📉"
                    st.metric(f"{profit_icon} 손익", f"{int(profit_loss):,}원")
                
                # 우측: 상세 조언
                with col_detail:
                    st.write(f"**현재 비중**: {row['현재비중(%)']:.1f}% (평가액: {int(row['평가금액']):,}원)")
                    st.write(f"**목표 비중**: {row['목표비중(%)']:.1f}%")
                    st.write(f"**조정 필요량**: {row['조정제안']:+.1f}% ({int(row['조정금액']):+,}원)")
                    
                    # 조언 로직
                    if adjustment > 5:
                        advice = f"🔥 **비중을 {abs(row['조정금액']):,.0f}원 추가 매수해봐요**: AI 점수 {row['AI점수']:.0f}점으로 강력하지만 현재 비중이 부족해. 큰손들의 평단가 위에서 매수세가 강하게 나가고 있으니 자금을 더 집중하는 게 현명할 거 같아."
                    elif adjustment < -5:
                        reduction = abs(row['조정금액'])
                        advice = f"🚨 **비중을 {int(reduction):,}원 정도 매도해봐요**: 현재 매수 강도가 약하거나 저항벽이 문제가 되고 있어. 수익(손실 방지)을 확정하고 더 강한 종목으로 갈아타는 게 낫겠어. 변화율이 {row['변화율']:+.2f}%인 만큼 타이밍을 잘 판단해봐."
                    else:
                        advice = f"⚖️ **지금은 보유가 최적이야**: 현재 비중이 이미 적절하게 배치되어 있어. 시장의 에너지와 흐름을 관망하면서 다음 변화 신호를 기다려. 무리한 조정은 하지 마."
                    
                    st.info(advice)

        st.write("---")

        # 4. 최종 요약 리포트
        st.write("### 📋 포트폴리오 평가 요약")
        col_summary1, col_summary2, col_summary3 = st.columns(3)
        
        with col_summary1:
            avg_score = df_p['AI점수'].mean()
            if avg_score >= 80:
                grade = "🏆 탁월"
            elif avg_score >= 70:
                grade = "✅ 우수"
            else:
                grade = "⚠️ 보통"
            st.metric("포트폴리오 등급", grade, f"{avg_score:.1f}점")
        
        with col_summary2:
            total_rebalance = df_p[abs(df_p['조정제안']) > 5].shape[0]
            st.metric("조정 필요 종목", f"{total_rebalance}개", f"전체 {len(df_p)}개 中")
        
        with col_summary3:
            diversification = 100 - df_p['현재비중(%)'].max()
            st.metric("다양성 지수", f"{diversification:.1f}%", "✅ 양호" if diversification > 50 else "⚠️ 낮음")
        
        st.success(f"✅ **최종 평가**: 현재 포트폴리오는 AI 신뢰도 **{df_p['AI점수'].mean():.1f}점**으로 양호한 상태예요. 위의 종목별 조정 제안을 참고해서 더 강한 종목에 자원을 집중시키면, 장기적으로 더 안정적이고 수익성 있는 포트폴리오가 될 거야. 조정 전에 손익 현황을 꼭 확인해봐!")
        
    else:
        st.error("❌ 분석 가능한 종목이 없습니다. 데이터를 다시 확인하세요.")