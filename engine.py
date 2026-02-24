import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

try:
    from ta.momentum import RSIIndicator
    from ta.volatility import AverageTrueRange, BollingerBands, KeltnerChannel
    from ta.volume import MFIIndicator, OnBalanceVolumeIndicator
    from ta.trend import MACD, IchimokuIndicator
    from ta.volume import VolumeWeightedAveragePrice
except ImportError:
    RSIIndicator = None
    AverageTrueRange = None
    BollingerBands = None
    KeltnerChannel = None
    MFIIndicator = None
    OnBalanceVolumeIndicator = None
    MACD = None
    IchimokuIndicator = None
    VolumeWeightedAveragePrice = None

def calculate_sharp_score(rsi, mfi, bb_lower, curr_price, macd_diff,
                          ichi_a=None, ichi_b=None, vwap=None, macd_diff_pct=None):
    """
    [The Closer's Multi-Factor 채점기 v2 — 다중공선성 해소 버전]

    기존 RSI+MFI 80점 집중(다중공선성) 폐기.
    6개 독립 팩터로 분산하여 보다 정밀한 신호 추출:

    팩터           만점   비고
    ─────────────────────────────────────────
    RSI  (과매도)   20pt  오실레이터: 절반으로 축소
    MFI  (수급)     20pt  오실레이터: 절반으로 축소
    BB   (밴드 위치)15pt  하단 이탈 강도
    MACD (추세 크기)15pt  방향+크기 반영 (기존 이진 폐기)
    Ichimoku(클라우드)15pt 독립 추세선
    VWAP (수급 이탈)15pt  VWAP 괴리율
    ─────────────────────────────────────────
    합계            100pt
    """
    # 1. RSI Score (0~20pt): RSI < 60 → 선형, RSI ≤ 20 → 20점 만점
    rsi_score = max(0.0, min(20.0, (60.0 - rsi) * 0.5))

    # 2. MFI Score (0~20pt): 동일 로직 — 하지만 RSI와 가중치 절반으로 분리
    mfi_score = max(0.0, min(20.0, (60.0 - mfi) * 0.5))

    # 3. Bollinger Band (0~15pt): 하단 이탈 강도 (5%→15pt 상향 스케일)
    bb_ratio = (curr_price / bb_lower) if bb_lower and bb_lower > 0 else 1.0
    if bb_ratio <= 1.05:
        bb_score = max(0.0, min(15.0, (1.05 - bb_ratio) * 300.0))
    else:
        bb_score = 0.0

    # 4. MACD Score (0~15pt): 방향 + 크기 비례 (기존 이진 10pt 폐기)
    #    macd_diff > 0이면 기본 7pt + 크기 보너스, 0 이하면 0pt
    if macd_diff > 0:
        # macd_diff_pct가 없으면 diff 절대값의 로그 스케일 사용
        if macd_diff_pct and macd_diff_pct > 0:
            magnitude_bonus = min(8.0, macd_diff_pct * 200.0)
        else:
            magnitude_bonus = min(8.0, abs(macd_diff) * 5.0)
        macd_score = min(15.0, 7.0 + magnitude_bonus)
    else:
        macd_score = 0.0

    # 5. Ichimoku Cloud Score (0~15pt): 독립 추세선
    #    가격이 구름 아래/구름 상승 배열 시 매수 기회 신호
    ichi_score = 0.0
    if ichi_a is not None and ichi_b is not None:
        cloud_top = max(ichi_a, ichi_b)
        cloud_bot = min(ichi_a, ichi_b)
        if curr_price < cloud_bot:          # 가격이 구름 완전 하단 → 강한 과매도
            ichi_score = 12.0
        elif curr_price < cloud_top:        # 구름 내부 진입 → 중립
            ichi_score = 6.0
        # 구름 위는 0점 (과매수 구간)
        if ichi_a > ichi_b:                 # 상승 구름 배열 보너스
            ichi_score = min(15.0, ichi_score + 3.0)
    else:
        ichi_score = 7.5  # 데이터 없으면 중립값

    # 6. VWAP Divergence Score (0~15pt): VWAP 대비 괴리율
    #    현재가가 VWAP 아래 → 수급 불균형으로 인한 저평가 가능성
    vwap_score = 0.0
    if vwap and vwap > 0:
        divergence = (vwap - curr_price) / vwap  # 양수 = VWAP 아래
        if divergence > 0:
            vwap_score = min(15.0, divergence * 300.0)
        # VWAP 위는 0점 (이미 프리미엄 구간)
    else:
        vwap_score = 7.5  # 데이터 없으면 중립값

    raw_score = rsi_score + mfi_score + bb_score + macd_score + ichi_score + vwap_score
    return round(min(100.0, max(0.0, raw_score)), 1)

def check_fundamentals(ticker_obj):
    """
    [The Closer's X-Ray 필터]
    재무제표가 썩은 한계기업을 찾아내어 패널티(감점) 폭탄을 투하합니다.
    """
    penalty = 0.0
    messages = []
    try:
        info = ticker_obj.info

        # [정상 참작] ETF, ETN, 코인은 재무제표가 없으므로 패스
        if info.get('quoteType') in ['ETF', 'MUTUALFUND', 'CRYPTOCURRENCY'] or 'ETF' in info.get('shortName', ''):
            return 0.0, ["💡 [자산 분류] ETF/펀드/암호화폐 (재무 검증 면제)"]

        # 1. 시가총액 검증 (동전주 기준 폐기 → 시총 절대 기준)
        #    한국주 < 300억원, 글로벌 < $2억 → 유동성/상폐 위험 페널티
        market_cap = info.get('marketCap', 0)
        ticker_sym = getattr(ticker_obj, 'ticker', '').upper()
        is_korean = ticker_sym.endswith('.KS') or ticker_sym.endswith('.KQ')
        if market_cap and market_cap > 0:
            if is_korean and market_cap < 30_000_000_000:    # 300억 미만
                penalty += 25.0
                messages.append(f"🚨 [유동성 경고] 시가총액 {market_cap/1e8:.0f}억원 — 300억 미달 소형주 (-25점)")
            elif not is_korean and market_cap < 200_000_000:  # $2억 미만
                penalty += 25.0
                messages.append(f"🚨 [유동성 경고] 시가총액 ${market_cap/1e6:.0f}M — $200M 미달 마이크로캡 (-25점)")

        # 2. 실적 검증 (EPS — 성장주 예외 반영)
        #    적자기업이라도 매출성장 > 20% YoY이면 성장주 패스
        eps = info.get('trailingEps', 0)
        revenue_growth = info.get('revenueGrowth', 0) or 0  # e.g. 0.35 = 35%
        if eps is not None and eps < 0:
            if revenue_growth > 0.20:  # 매출 20%↑ 이상 성장: 성장주 예외
                messages.append(f"💡 [성장주 예외] 적자이나 매출 성장 {revenue_growth*100:.0f}%↑ — EPS 페널티 면제")
            else:
                penalty += 20.0
                messages.append("⚠️ [재무 경고] 최근 실적 지속 적자 (EPS 마이너스, -20점 감점)")

        # 3. 빚쟁이 검증 (부채비율 200% 초과) - 금융/은행업 예외 처리
        debt_equity = info.get('debtToEquity', 0)
        industry = info.get('industry', '').lower()
        sector = info.get('sector', '').lower()

        # 'bank', 'financial', 'insurance' 등 금융 섹터는 예외
        is_financial = any(keyword in industry or keyword in sector for keyword in ['bank', 'financial', 'insurance'])

        if debt_equity is not None and debt_equity > 200:
            if is_financial:
                messages.append("💡 [재무 참고] 금융업종 특수성 (부채비율 패널티 면제)")
            else:
                penalty += 10.0
                messages.append("⚠️ [부채 경고] 부채비율 200% 초과 (자본 잠식 우려, -10점 감점)")

        if penalty == 0.0:
            messages.append("✅ [재무 건전성] 펀더멘털 양호 (적자/자본잠식 징후 없음)")

    except Exception:
        messages.append("⚠️ 야후 파이낸스 재무 데이터 수신 불가 (정보 누락)")

    return penalty, messages

def get_closer_verdict_and_comment(final_score, rsi, mfi, curr_price, bb_lower, macd_diff, fund_penalty=0.0,
                                    ichi_a=None, ichi_b=None, vwap=None, macd_diff_pct=None, atr_val=None):
    """
    [The Closer's 실시간 의견 생성기 — Multi-Factor v2]
    점수 내역을 6팩터 기준으로 낱낱이 해부합니다.
    """
    # 점수 역산 (engine 로직과 100% 동일)
    rsi_score = round(max(0.0, min(20.0, (60.0 - rsi) * 0.5)), 1)
    mfi_score = round(max(0.0, min(20.0, (60.0 - mfi) * 0.5)), 1)
    bb_ratio  = (curr_price / bb_lower) if bb_lower and bb_lower > 0 else 1.0
    bb_score  = round(max(0.0, min(15.0, (1.05 - bb_ratio) * 300.0)), 1) if bb_ratio <= 1.05 else 0.0
    if macd_diff > 0:
        mb = min(8.0, (macd_diff_pct * 200.0) if macd_diff_pct and macd_diff_pct > 0 else min(8.0, abs(macd_diff) * 5.0))
        macd_score = round(min(15.0, 7.0 + mb), 1)
    else:
        macd_score = 0.0

    ichi_score = 7.5
    if ichi_a is not None and ichi_b is not None:
        cloud_bot = min(ichi_a, ichi_b)
        cloud_top = max(ichi_a, ichi_b)
        ichi_score = 0.0
        if curr_price < cloud_bot:
            ichi_score = 12.0
        elif curr_price < cloud_top:
            ichi_score = 6.0
        if ichi_a > ichi_b:
            ichi_score = min(15.0, ichi_score + 3.0)
        ichi_score = round(ichi_score, 1)

    vwap_score = 7.5
    if vwap and vwap > 0:
        div = (vwap - curr_price) / vwap
        vwap_score = round(min(15.0, div * 300.0), 1) if div > 0 else 0.0

    if final_score >= 70:
        action  = "🟢 [적극 매수 (BUY)]"
        briefing = "완벽한 과매도 바닥 구간(RSI/MFI)과 추세 반전이 교집합을 이뤘습니다. 기관과 세력의 자금이 유입되는 징후가 포착되었습니다. 철저한 분할 매수로 물량을 확보하십시오."
    elif final_score <= 30:
        action  = "🔴 [매도 및 회피 (SELL)]"
        briefing = "수급이 완전히 이탈했거나 고점 과열 상태입니다. 바닥 밑에 지하실이 열려있습니다. 보유자는 즉각 비중을 축소하고, 신규 진입은 절대 금지합니다."
    else:
        action  = "🟡 [보류 및 관망 (HOLD)]"
        briefing = "방향성을 상실한 혼조세 구간입니다. 가격은 횡보하고 수급은 애매합니다. 확실한 타점(70점 이상)이 나올 때까지 소중한 자본을 묶어두지 마십시오."

    stop_info = ""
    if atr_val and atr_val > 0 and curr_price > 0:
        dynamic_stop = max(curr_price - 2 * atr_val, curr_price * 0.85)
        stop_pct = abs((dynamic_stop - curr_price) / curr_price * 100)
        stop_info = f"  \n🛡️ **ATR 동적 손절선**: **{dynamic_stop:,.1f}** ({stop_pct:.1f}% below, 2×ATR 기준)"

    comment  = f"**{action}**\n\n"
    comment += "📊 **[The Closer's Multi-Factor 총점 해부]**  \n"
    comment += f"▪️ **RSI** (과매도): **+{rsi_score}점** / 20점  \n"
    comment += f"▪️ **MFI** (세력 자금): **+{mfi_score}점** / 20점  \n"
    comment += f"▪️ **BB** (하단 지지력): **+{bb_score}점** / 15점  \n"
    comment += f"▪️ **MACD** (추세 크기): **+{macd_score}점** / 15점  \n"
    comment += f"▪️ **Ichimoku** (구름 위치): **+{ichi_score}점** / 15점  \n"
    comment += f"▪️ **VWAP** (수급 구형): **+{vwap_score}점** / 15점"

    if fund_penalty > 0:
        comment += f"  \n🚨 **재무 페널티**: **-{fund_penalty}점** (적자/부채/시총 미달)"

    comment += stop_info
    comment += f"\n\n💡 **[월스트리트 퀀트 분석]**  \n{briefing}"

    return action, comment

def analyze_stock(ticker, period="6mo", apply_fundamental=False):
    """
    고해상도 타격 시스템: Convergence Weight 기반
    여러 지표가 동시에 신호를 주면 점수 폭발 → 진정한 선별과 0점 남발 구분
    apply_fundamental=True 시 재무 X-Ray 패널티 적용 (개별 분석 전용, 전수조사 시 False)
    """
    try:
        stock = yf.Ticker(ticker)
        # 🚨 [핵심] ETF는 auto_adjust=False로 가져오는 것이 NaN 누락 방지에 유리
        # 암호화폐/글로벌 자산은 auto_adjust=True 폴백
        df = None
        for auto_adj in [False, True]:
            try:
                df = stock.history(period=period, auto_adjust=auto_adj)
                if df is not None and not df.empty and len(df) >= 30:
                    break
            except:
                continue
        
        # [데이터 부족 시 자동 확대] 30일 미만이면 더 긴 기간 요청
        if df is None or df.empty or len(df) < 30:
            for p in ["1y", "2y"]:
                for auto_adj in [False, True]:
                    try:
                        df = stock.history(period=p, auto_adjust=auto_adj)
                        if df is not None and not df.empty and len(df) >= 30:
                            break
                    except:
                        continue
                if df is not None and not df.empty and len(df) >= 30:
                    break
            
        if df is None or df.empty or len(df) < 30:
            return None, 0, "데이터 수집 실패 (최소 30일 필요)", [], 0
        
        # 🚨 [The Closer's ETF 생존 코드 1] 비어있는 데이터(NaN)를 이전 날짜 가격으로 강제 복사하여 채움
        df.columns = [c.capitalize() for c in df.columns]  # 컬럼명 대문자화 (Close, High, Low, Volume 등)
        df = df.ffill().dropna()  # 포워드필 + NaN 제거
        
        # 🚨 [The Closer's ETF 생존 코드 2] 거래량이 0인 날을 1로 강제 치환 (MFI, VWAP 계산 시 0으로 나누기 에러 방지)
        if 'Volume' in df.columns:
            df['Volume'] = df['Volume'].replace(0, 1)
        
        # 2. 데이터 정제
        close = df['Close'].astype(float)
        high = df['High'].astype(float)
        low = df['Low'].astype(float)
        volume = df['Volume'].astype(float)
        
        # 🚨 [The Closer's 실시간 현재가 보정]
        # close.iloc[-1]은 전일 종가 → 장 중 조회 시 실제 주가와 불일치 발생
        # fast_info.last_price로 오버라이드하여 항상 실제 현재가 표시
        curr_price = close.iloc[-1]
        try:
            live_price = stock.fast_info.last_price
            if live_price and live_price > 0:
                curr_price = float(live_price)
        except Exception:
            pass  # 실패 시 close.iloc[-1] 유지
        
        # 3. 지표 계산 (모든 지표를 계산하되, 없으면 안전하게 처리)
        try:
            if RSIIndicator:
                rsi = RSIIndicator(close=close, window=14).rsi()
            else:
                rsi = pd.Series([50] * len(close), index=close.index)
        except:
            rsi = pd.Series([50] * len(close), index=close.index)
        
        try:
            if MFIIndicator:
                mfi = MFIIndicator(high=high, low=low, close=close, volume=volume, window=14).money_flow_index()
            else:
                mfi = pd.Series([50] * len(close), index=close.index)
        except:
            mfi = pd.Series([50] * len(close), index=close.index)
        
        # BB 계산
        try:
            if BollingerBands:
                bb = BollingerBands(close=close, window=20, window_dev=2)
                bb_lower = bb.bollinger_lband()
                bb_higher = bb.bollinger_hband()
            else:
                bb_lower = pd.Series([close.iloc[-1]] * len(close), index=close.index)
                bb_higher = pd.Series([close.iloc[-1]] * len(close), index=close.index)
        except:
            bb_lower = pd.Series([close.iloc[-1]] * len(close), index=close.index)
            bb_higher = pd.Series([close.iloc[-1]] * len(close), index=close.index)
        
        # MACD 신호 계산
        try:
            if MACD:
                macd_obj = MACD(close=close, window_fast=12, window_slow=26, window_sign=9)
                macd_line = macd_obj.macd()
                macd_sig = macd_obj.macd_signal()
                macd_diff = macd_obj.macd_diff()
            else:
                macd_line = pd.Series([0] * len(close), index=close.index)
                macd_sig = pd.Series([0] * len(close), index=close.index)
                macd_diff = pd.Series([0] * len(close), index=close.index)
        except:
            macd_line = pd.Series([0] * len(close), index=close.index)
            macd_sig = pd.Series([0] * len(close), index=close.index)
            macd_diff = pd.Series([0] * len(close), index=close.index)
        
        # Ichimoku 계산
        try:
            if IchimokuIndicator:
                ichi = IchimokuIndicator(high=high, low=low, window1=9, window2=26, window3=52)
                ichi_a = ichi.ichimoku_a()
                ichi_b = ichi.ichimoku_b()
            else:
                ichi_a = close.copy()
                ichi_b = close.copy()
        except:
            ichi_a = close.copy()
            ichi_b = close.copy()
        
        # VWAP 계산
        try:
            if VolumeWeightedAveragePrice:
                vwap = VolumeWeightedAveragePrice(high=high, low=low, close=close, volume=volume, window=20).volume_weighted_average_price()
            else:
                vwap = close.copy()
        except:
            vwap = close.copy()
        
        # OBV 계산
        try:
            if OnBalanceVolumeIndicator:
                obv = OnBalanceVolumeIndicator(close=close, volume=volume).on_balance_volume()
            else:
                obv = pd.Series(range(len(close)), index=close.index).astype(float)
        except:
            obv = pd.Series(range(len(close)), index=close.index).astype(float)
        
        # ATR 계산 (변동성)
        try:
            if AverageTrueRange:
                atr = AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range()
            else:
                atr = pd.Series([(high.iloc[-1] - low.iloc[-1])] * len(close), index=close.index)
        except:
            atr = pd.Series([(high.iloc[-1] - low.iloc[-1])] * len(close), index=close.index)
        
        # 최신 값 추출
        rsi_val = rsi.iloc[-1]
        mfi_val = mfi.iloc[-1]
        bb_lower_val = bb_lower.iloc[-1]
        macd_diff_val = macd_diff.iloc[-1]
        
        # 4. Multi-Factor 점수 계산 (v2 — 6팩터 독립 입력)
        ichi_a_val = ichi_a.iloc[-1]
        ichi_b_val = ichi_b.iloc[-1]
        vwap_val   = vwap.iloc[-1]
        atr_val    = atr.iloc[-1]
        # MACD diff의 가격 대비 비율 (크기 정규화)
        macd_pct = abs(macd_diff_val) / curr_price * 100.0 if curr_price > 0 else 0.0
        raw_tech_score = calculate_sharp_score(
            rsi_val, mfi_val, bb_lower_val, curr_price, macd_diff_val,
            ichi_a=ichi_a_val, ichi_b=ichi_b_val, vwap=vwap_val, macd_diff_pct=macd_pct
        )

        # 4-1. 기술 점수 확정 (펀더멘털 패널티는 detail_info 생성 후 적용)
        final_score = round(min(100.0, max(0.0, raw_tech_score)), 1)

        # 5. 판정 기준 (신뢰도 점수 해석법)
        if final_score >= 80:
            verdict = "💎 [천재지변급 기회 - 분할 매수 즉시]"
        elif final_score >= 50:
            verdict = "✅ [애매한 반등 - 정찰병만 투입]"
        elif final_score >= 30:
            verdict = "⚠️ [추세 하락 - 관망]"
        else:
            verdict = "🛑 [폭락/인버스 - 도망]"
        
        # 6. 상세 정보 (9대 지표)
        detail_info = [
            {
                "title": "🌡️ RSI (엔진 온도)",
                "full_comment": f"{rsi_val:.1f} {'(과매도)' if rsi_val < 30 else '(정상)' if rsi_val < 70 else '(과매수)'}"
            },
            {
                "title": "💰 MFI (자금 흐름)",
                "full_comment": f"{mfi_val:.1f} {'(약세)' if mfi_val < 30 else '(중립)' if mfi_val < 70 else '(강세)'}"
            },
            {
                "title": "📊 MACD (추세 신호)",
                "full_comment": f"{'반전 신호 (+)' if macd_diff_val > 0 else '하락 지속 (-)'}"
            },
            {
                "title": "📈 일목균형표 (Ichimoku)",
                "full_comment": f"클라우드 해석: {'상승 흐름' if ichi_a.iloc[-1] > ichi_b.iloc[-1] else '하락 흐름'}"
            },
            {
                "title": "💎 볼린저 밴드 (변동성)",
                "full_comment": f"현재가 {('하단 근처' if curr_price <= bb_lower_val else '상단 근처' if curr_price >= bb_higher.iloc[-1] else '중간권역')} - 변동성: {'높음' if (bb_higher.iloc[-1] - bb_lower_val) > (close.mean() * 0.05) else '정상'}"
            },
            {
                "title": "🎯 ATR (동적 손절선)",
                "full_comment": f"ATR={atr_val:.2f} → 2×ATR 손절선: {max(curr_price - 2*atr_val, curr_price*0.85):,.1f} ({abs((max(curr_price-2*atr_val, curr_price*0.85)-curr_price)/curr_price*100):.1f}% below)"
            },
            {
                "title": "🌊 VWAP (거래량 가중)",
                "full_comment": f"{'VWAP 상향 돌파' if curr_price > vwap.iloc[-1] else 'VWAP 하향 이탈'}"
            },
            {
                "title": "📊 Volume Profile",
                "full_comment": f"거래량: {volume.iloc[-1]:,.0f}주 (평균: {volume.mean():,.0f}주)"
            },
            {
                "title": "⚡ 매매 신호 종합",
                "full_comment": f"최종 판정: {verdict}"
            }
        ]
        # 🚨 [The Closer's 펀더멘털 검증]
        fund_penalty = 0.0
        fund_msgs = []
        if apply_fundamental:
            fund_penalty, fund_msgs = check_fundamentals(stock)
            final_score = round(max(0.0, final_score - fund_penalty), 1)
            fund_combined_text = " / ".join(fund_msgs)
            detail_info.append({
                "title": "🏢 펀더멘털 검증 (재무제표)",
                "full_comment": fund_combined_text
            })

        # 🚨 [The Closer's 실시간 의견 교체 — Multi-Factor v2 파라미터 전달]
        short_verdict, full_wallstreet_comment = get_closer_verdict_and_comment(
            final_score, rsi_val, mfi_val, curr_price, bb_lower_val, macd_diff_val, fund_penalty,
            ichi_a=ichi_a_val, ichi_b=ichi_b_val, vwap=vwap_val, macd_diff_pct=macd_pct, atr_val=atr_val
        )
        verdict = short_verdict
        detail_info.append({
            "title": "🎯 The Closer's 실시간 의견",
            "full_comment": full_wallstreet_comment
        })

        # [ATR 기반 동적 손절선] 2×ATR — 일괄 10% 고정 폐기
        try:
            atr_val_latest = atr.iloc[-1]
            if atr_val_latest > 0:
                stop_loss = round(curr_price - (2.0 * atr_val_latest), 2)
                stop_loss = max(stop_loss, curr_price * 0.85)  # 하드 플로어: 최대 15% 이탈 방지
            else:
                stop_loss = curr_price * 0.90  # ATR 이상 시 폴백
        except:
            stop_loss = curr_price * 0.90
        
        # DataFrame에 모든 지표 추가
        df['rsi'] = rsi
        df['mfi'] = mfi
        df['macd'] = macd_line
        df['macd_sig'] = macd_sig
        df['ichi_a'] = ichi_a
        df['ichi_b'] = ichi_b
        df['vwap'] = vwap
        df['obv'] = obv
        df['atr'] = atr

        return df, final_score, verdict, detail_info, stop_loss
    except Exception as e:
        return None, 0, f"분석 오류", [], 0
