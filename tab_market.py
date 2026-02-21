import streamlit as st
import pandas as pd
from engine import analyze_stock
from style_utils import apply_global_style

def run_market_tab(stock_dict):
    apply_global_style()
    st.markdown("<h1 style='color:white; font-weight:800;'>🔥 시장 전수조사</h1>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    target = None
    if c1.button("🇰🇷 KOSPI 전수조사", use_container_width=True): target = ".KS"
    if c2.button("🇰🇷 KOSDAQ 전수조사", use_container_width=True): target = ".KQ"
    if c3.button("🇺🇸 GLOBAL 전수조사", use_container_width=True): target = "GLOBAL"

    if target:
        stocks_to_scan = [k for k, v in stock_dict.items() if (target in v if target != "GLOBAL" else ".K" not in v)]
        results = []
        
        # 무한 로딩 방지: 프로그레스 바와 상태창 분리
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, name in enumerate(stocks_to_scan):
            status_text.text(f"🔎 {name} 정밀 판독 중... ({i+1}/{len(stocks_to_scan)})")
            _, score, signal, _, price = analyze_stock(stock_dict[name])
            if score >= 70:
                results.append({"종목명": name, "점수": score, "의견": signal, "가격": f"{int(price):,}원"})
            progress_bar.progress((i + 1) / len(stocks_to_scan))
        
        status_text.empty()
        if results:
            results = sorted(results, key=lambda x: x['점수'], reverse=True)
            st.success(f"✅ 총 {len(results)}개의 유망 종목 발굴 완료!")
            st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
        else:
            st.warning("⚠️ 현재 조건에 부합하는 종목이 없습니다.")