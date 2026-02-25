import streamlit as st
import pandas as pd
import concurrent.futures
from engine import analyze_stock
from stocks import STOCK_DICT, get_all_tickers
from style_utils import apply_global_style


# ─────────────────────────────────────────────
# [역방향 매핑] 코드 → 종목명 변환 유틸리티 (검색 속도 최적화)
# ─────────────────────────────────────────────
TICKER_TO_NAME_MAP = {}
for mkt, stocks in STOCK_DICT.items():
    for name, code in stocks.items():
        TICKER_TO_NAME_MAP[code] = name

def get_name_from_ticker(ticker_code):
    """티커(코드)를 입력하면 종목명을 반환, 없으면 코드 그대로 반환"""
    return TICKER_TO_NAME_MAP.get(ticker_code, ticker_code)


# ─────────────────────────────────────────────
# 🚨 [1] 스캐너 엔진 (데스노트 실패 로그 추적 포함)
# ─────────────────────────────────────────────
def scan_multiple_stocks(ticker_list):
    """
    [The Closer's 1,000연발 융단 폭격 스캐너 + 데스노트(실패 로그)]
    """
    results = []
    failed_logs = []  # 🚨 엔진이 가차 없이 쳐낸 종목들을 기록하는 블랙박스

    progress_text = "🚀 다중 스레드 레이더 가동 중... (야후 서버 타격 중)"
    my_bar = st.progress(0, text=progress_text)
    total = len(ticker_list)
    completed = 0

    # 🚨 야후 밴(Ban) 방지를 위해 워커 수는 절대 15를 넘기지 마십시오.
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        future_to_ticker = {
            executor.submit(analyze_stock, ticker, "1y", False): ticker
            for ticker in ticker_list
        }

        for future in concurrent.futures.as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            completed += 1

            progress_percent = int((completed / total) * 100)
            my_bar.progress(
                progress_percent,
                text=f"🚀 타격 진행 중... ({completed}/{total}) - 융단 폭격 중",
            )

            try:
                df, final_score, verdict, detail_info, stop_loss = future.result()
                # 엔진이 정상적으로 차트를 분석하고 살려둔 경우
                if df is not None and not df.empty:
                    results.append({
                        "ticker": ticker,
                        "score": final_score,
                        "verdict": verdict,
                        "close": df["Close"].iloc[-1],
                    })
                else:
                    # 데이터가 30일 미만이거나, 폭포수 계산이 불가하여 엔진이 쳐낸 경우
                    failed_logs.append({
                        "ticker": ticker,
                        "reason": verdict if verdict else "조건 미달 (데이터 부족/상폐/거래정지)",
                    })
            except Exception as exc:
                failed_logs.append({
                    "ticker": ticker,
                    "reason": f"서버 타임아웃/수신 거부 ({exc})",
                })

    my_bar.empty()
    return results, failed_logs


# ─────────────────────────────────────────────
# 🚨 [2] 시장 전수조사 UI (3대 시장 통합 + 1,000개 리미트 해제)
# ─────────────────────────────────────────────
def run_market_tab(unused_stock_dict):
    apply_global_style()
    st.markdown(
        "<h1 style='color:white;'>🔥 시장 전수조사 (1,000연발 융단 폭격 모드)</h1>",
        unsafe_allow_html=True,
    )

    # ---------------------------------------------------------
    # 🚨 [여기서부터 UI 교체] 시장 선택 및 1000개 리미트 해제
    # ---------------------------------------------------------
    st.markdown("### 📊 스캔할 시장을 선택하십시오")

    # 코스피, 코스닥, 글로벌, 그리고 '전체' 옵션 추가
    market_choice = st.radio(
        "시장 타겟",
        ["🇰🇷 KOSPI", "🇰🇷 KOSDAQ", "🌎 GLOBAL", "🔥 전체 통합 스캔 (ALL)"],
        horizontal=True,
        label_visibility="collapsed",        key="market_scan_radio"    )

    # 리미트 슬라이더를 1,000개까지 확장
    st.markdown("### 🎚️ 최대 스캔 개수 (융단 폭격 모드)")
    scan_limit = st.slider(
        "검색량",
        min_value=50,
        max_value=1000,
        value=200,
        step=50,
        label_visibility="collapsed",
        help="1,000개 풀스캔 시 약 30~60초가 소요됩니다. 야후 서버 상태에 따라 튕기는 종목이 발생할 수 있습니다.",
        key="market_scan_limit"
    )

    st.markdown("---")

    # 🚨 실행 버튼
    if st.button(
        f"🚀 {market_choice} ({scan_limit}개) 융단 폭격 시작",
        type="primary",
        use_container_width=True,
        key="market_scan_btn"
    ):
        # ── 시장 키 결정 ──
        if "ALL" in market_choice or "전체" in market_choice:
            market_key = "ALL"
        elif "KOSPI" in market_choice:
            market_key = "KOSPI"
        elif "KOSDAQ" in market_choice:
            market_key = "KOSDAQ"
        else:
            market_key = "GLOBAL"

        # ── 종목 리스트 구성 (FinanceDataReader 실시간) ──
        with st.spinner("🎯 시장 데이터베이스 동기화 중..."):
            raw_items = get_all_tickers(market_key)
            st.info(f"📋 FinanceDataReader에서 {len(raw_items)}개 종목을 확보했습니다.")

        # 티커만 추출 + 리미트 적용
        items = raw_items[:scan_limit]
        ticker_list = [code for _name, code in items]

        # 🚨 FDR에서 가져온 종목명으로 동적 매핑 생성 (STOCK_DICT에 없는 종목 대응)
        fdr_name_map = {code: name for name, code in items}

        # ── 엔진 가동 ──
        results, failed_logs = scan_multiple_stocks(ticker_list)

        # ── 결과 요약 ──
        st.success(
            f"✅ 총 {len(ticker_list)}발 발사 ➡️ {len(results)}개 종목 타격 성공! "
            f"(폐기됨: {len(failed_logs)}개)"
        )

        # 🚨 [신규] 실패한 쓰레기 데이터들의 데스노트 출력 (아코디언 형태)
        if failed_logs:
            with st.expander(
                f"⚠️ 쳐내진 종목 / 스캔 실패 명단 ({len(failed_logs)}개) - 클릭하여 펼치기"
            ):
                st.markdown(
                    "엔진이 아래의 사유로 방아쇠를 당기지 않고 즉각 폐기 처분한 종목들입니다."
                )
                for log in failed_logs:
                    # FDR 매핑 우선, 없으면 STOCK_DICT 매핑, 그래도 없으면 코드 그대로
                    name = fdr_name_map.get(log['ticker'], get_name_from_ticker(log['ticker']))
                    st.markdown(f"- 🔴 **{name}** (`{log['ticker']}`): {log['reason']}")

        # ── 성공한 결과 데이터프레임 출력 ──
        if results:
            df_res = (
                pd.DataFrame(results)
                .sort_values(by="score", ascending=False)
                .reset_index(drop=True)
            )
            # 🚨 종목명 컬럼 추가 (FDR 매핑 우선, STOCK_DICT 폴백)
            df_res['종목명'] = df_res['ticker'].apply(
                lambda t: fdr_name_map.get(t, get_name_from_ticker(t))
            )
            cols = ['종목명', 'ticker', 'score', 'verdict', 'close']
            df_res = df_res[[c for c in cols if c in df_res.columns]]
            st.dataframe(df_res, use_container_width=True)
            st.balloons()
        else:
            st.error(
                "조건을 만족하는 종목이 단 하나도 없습니다. "
                "시장이 완전한 하락장이거나 서버가 응답하지 않습니다."
            )

