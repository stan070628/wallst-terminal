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

def calculate_sharp_score(rsi, mfi, bb_lower, curr_price, macd_diff, is_waterfall=False, is_rsi_hook_failed=False):
    """
    [The Closer's 연속형 채점기 + 폭포수 필터 + RSI Hook 필터]
    """
    rsi_score = max(0.0, min(40.0, (60.0 - rsi) * 1.0))
    mfi_score = max(0.0, min(40.0, (60.0 - mfi) * 1.0))

    bb_ratio = (curr_price / bb_lower) if bb_lower > 0 else 1.0
    bb_score = 0.0
    if bb_ratio <= 1.05:
        bb_score = max(0.0, min(10.0, (1.05 - bb_ratio) * 200.0))

    macd_score = 10.0 if macd_diff > 0 else 0.0

    raw_score = rsi_score + mfi_score + bb_score + macd_score
    final_score = round(min(100.0, max(0.0, raw_score)), 1)

    # 🚨 [The Closer's 폭포수 회피 필터 작동]
    if is_waterfall:
        final_score = min(final_score, 29.0)

    # 🚨 [The Closer's RSI 턴어라운드(Hook) 필터 작동]
    # 바닥권인데 고개를 들지 않고 계속 처박고 있다면 떨어지는 칼날입니다.
    if is_rsi_hook_failed:
        final_score = min(final_score, 29.0)

    return final_score

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

def get_closer_verdict_and_comment(final_score, rsi, mfi, curr_price, bb_lower, macd_diff, fund_penalty=0.0, is_waterfall=False, is_rsi_hook_failed=False):
    """
    [The Closer's 실시간 의견 생성기]
    """
    rsi_score = round(max(0.0, min(40.0, (60.0 - rsi) * 1.0)), 1)
    mfi_score = round(max(0.0, min(40.0, (60.0 - mfi) * 1.0)), 1)
    bb_ratio = (curr_price / bb_lower) if bb_lower > 0 else 1.0
    bb_score = round(max(0.0, min(10.0, (1.05 - bb_ratio) * 200.0)), 1) if bb_ratio <= 1.05 else 0.0
    macd_score = 10.0 if macd_diff > 0 else 0.0

    # 2. 명확한 Action 판정 (폭포수 및 Hook 실패 우선 처리)
    if is_waterfall:
        action = "🔴 [절대 매수 금지 (AVOID)]"
        briefing = "대세 하락장(120일 장기 추세선 하향)에 진입한 '폭포수 차트'입니다. 데드캣 바운스(지하실 입구)를 조심하십시오."
    elif is_rsi_hook_failed:
        action = "🟡 [바닥 확인 대기 (WAIT)]"
        briefing = "지표상 과매도 구간이나, RSI가 아직 고개를 들지 못하고 계속 하락 중입니다(Hook 실패). 바닥을 함부로 예측하지 마시고, 추세가 위로 꺾이는 턴어라운드를 확인한 뒤 진입하십시오."
    elif final_score >= 70:
        action = "🟢 [적극 매수 (BUY)]"
        briefing = "완벽한 과매도 바닥 구간에서 RSI가 턴어라운드(Hook)에 성공했습니다. 떨어지는 칼날이 멈추고 반등이 시작되는 최적의 타점입니다. 분할 매수로 물량을 확보하십시오."
    elif final_score <= 30:
        action = "🔴 [매도 및 회피 (SELL)]"
        briefing = "수급이 완전히 이탈했거나 고점 과열 상태입니다. 신규 진입은 절대 금지합니다."
    else:
        action = "🟡 [보류 및 관망 (HOLD)]"
        briefing = "방향성을 상실한 혼조세 구간입니다. 가격은 횡보하고 수급은 애매합니다. 확실한 타점(70점 이상)이 나올 때까지 소중한 자본을 묶어두지 마십시오."

    comment = f"**{action}**\n\n"
    comment += "📊 **[The Closer's 총점 해부]** \n"
    comment += f"▪️ **RSI** (과매도 강도): **+{rsi_score}점** / 40점 만점  \n"
    comment += f"▪️ **MFI** (세력 자금유입): **+{mfi_score}점** / 40점 만점  \n"
    comment += f"▪️ **BB** (하단 지지력): **+{bb_score}점** / 10점 만점  \n"
    comment += f"▪️ **MACD** (단기 추세): **+{macd_score}점** / 10점 만점"

    if fund_penalty > 0:
        comment += f"  \n🚨 **재무 페널티**: **-{fund_penalty}점** 감점"

    if is_waterfall:
        comment += f"  \n🚨 **폭포수 필터**: 장기 120일선 역배열 (점수 강제 29점 하향)"
    if is_rsi_hook_failed:
        comment += f"  \n🪝 **RSI Hook 필터**: 턴어라운드 실패/하락 진행 중 (점수 강제 29점 하향)"

    comment += f"\n\n💡 **[월스트리트 퀀트 분석]** \n{briefing}"

    return action, comment

def analyze_stock(ticker, period="1y", apply_fundamental=False):
    # 🚨 기본 period를 1y로 변경 (120일선을 구하려면 최소 6개월치 데이터 필수)
    try:
        stock = yf.Ticker(ticker)
        df = None
        for auto_adj in [False, True]:
            try:
                df = stock.history(period=period, auto_adjust=auto_adj)
                if df is not None and not df.empty and len(df) >= 30:
                    break
            except:
                continue

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
            return None, 0, "데이터 수집 실패", [], 0

        df.columns = [c.capitalize() for c in df.columns]
        df = df.ffill().dropna()
        if 'Volume' in df.columns:
            df['Volume'] = df['Volume'].replace(0, 1)

        close = df['Close'].astype(float)
        high = df['High'].astype(float)
        low = df['Low'].astype(float)
        volume = df['Volume'].astype(float)

        curr_price = close.iloc[-1]
        try:
            live_price = stock.fast_info.last_price
            if live_price and live_price > 0:
                curr_price = float(live_price)
        except:
            pass

        # 🚨 [The Closer's 폭포수 센서 (120일선 검증)]
        is_waterfall = False
        try:
            ma120 = close.rolling(window=120).mean()
            if len(close) >= 125:
                # 현재가가 120일선 아래에 있고 & 120일선 자체가 하락 중일 때 (5일 전과 비교)
                is_waterfall = (curr_price < ma120.iloc[-1]) and (ma120.iloc[-1] < ma120.iloc[-5])
            else:
                ma60 = close.rolling(window=60).mean() # 상장 초기 종목은 60일선 대체
                if len(close) >= 65:
                    is_waterfall = (curr_price < ma60.iloc[-1]) and (ma60.iloc[-1] < ma60.iloc[-5])
        except:
            pass

        # 지표 계산
        rsi = RSIIndicator(close=close, window=14).rsi() if RSIIndicator else pd.Series([50]*len(close), index=close.index)
        mfi = MFIIndicator(high=high, low=low, close=close, volume=volume, window=14).money_flow_index() if MFIIndicator else pd.Series([50]*len(close), index=close.index)
        bb = BollingerBands(close=close, window=20, window_dev=2) if BollingerBands else None
        bb_lower = bb.bollinger_lband() if bb else pd.Series([curr_price]*len(close), index=close.index)
        bb_higher = bb.bollinger_hband() if bb else pd.Series([curr_price]*len(close), index=close.index)
        macd_obj = MACD(close=close, window_fast=12, window_slow=26, window_sign=9) if MACD else None
        macd_line = macd_obj.macd() if macd_obj else pd.Series([0]*len(close), index=close.index)
        macd_sig = macd_obj.macd_signal() if macd_obj else pd.Series([0]*len(close), index=close.index)
        macd_diff = macd_obj.macd_diff() if macd_obj else pd.Series([0]*len(close), index=close.index)

        # Ichimoku, VWAP, OBV, ATR 계산 (기존 코드와 동일하게 유지)
        ichi = IchimokuIndicator(high=high, low=low, window1=9, window2=26, window3=52) if IchimokuIndicator else None
        ichi_a = ichi.ichimoku_a() if ichi else close.copy()
        ichi_b = ichi.ichimoku_b() if ichi else close.copy()
        vwap = VolumeWeightedAveragePrice(high=high, low=low, close=close, volume=volume, window=20).volume_weighted_average_price() if VolumeWeightedAveragePrice else close.copy()
        obv = OnBalanceVolumeIndicator(close=close, volume=volume).on_balance_volume() if OnBalanceVolumeIndicator else pd.Series(range(len(close)), index=close.index).astype(float)
        atr = AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range() if AverageTrueRange else pd.Series([(high.iloc[-1] - low.iloc[-1])]*len(close), index=close.index)

        rsi_val = rsi.iloc[-1]
        # 🚨 [The Closer's RSI Hook 센서] 어제 RSI 값 추출 (데이터가 부족하면 오늘 값으로 대체)
        rsi_prev = rsi.iloc[-2] if len(rsi) >= 2 else rsi_val

        mfi_val = mfi.iloc[-1]
        bb_lower_val = bb_lower.iloc[-1]
        macd_diff_val = macd_diff.iloc[-1]

        # 🚨 [RSI Hook 실패 판독]
        # RSI가 40 이하(과매도/매수타점)인데, 오늘 RSI가 어제보다 작거나 같다면 아직 바닥을 안 찍고 추락 중이라는 뜻
        is_rsi_hook_failed = False
        if rsi_val <= 40 and rsi_val <= rsi_prev:
            is_rsi_hook_failed = True

        # 4. 고해상도 점수 계산 (is_rsi_hook_failed 파라미터 추가 전달)
        raw_tech_score = calculate_sharp_score(rsi_val, mfi_val, bb_lower_val, curr_price, macd_diff_val, is_waterfall, is_rsi_hook_failed)
        final_score = round(min(100.0, max(0.0, raw_tech_score)), 1)

        # 5. 판정 (이후 코드는 동일)
        if final_score >= 80:
            verdict = "💎 [천재지변급 기회 - 분할 매수 즉시]"
        elif final_score >= 50:
            verdict = "✅ [애매한 반등 - 정찰병만 투입]"
        elif final_score >= 30:
            verdict = "⚠️ [추세 하락 - 관망]"
        else:
            verdict = "🛑 [폭락/인버스 - 도망]"

        detail_info = [
            {"title": "🌡️ RSI (엔진 온도)", "full_comment": f"{rsi_val:.1f} {'(과매도)' if rsi_val < 30 else '(정상)' if rsi_val < 70 else '(과매수)'}"},
            # 🚨 상세 정보에 Hook 필터 상태 추가
            {"title": "🪝 RSI 턴어라운드 (Hook)", "full_comment": "🚨 턴어라운드 실패 (관망)" if is_rsi_hook_failed else "✅ 턴어라운드 성공 (또는 해당 없음)"},
            {"title": "💰 MFI (자금 흐름)", "full_comment": f"{mfi_val:.1f} {'(약세)' if mfi_val < 30 else '(중립)' if mfi_val < 70 else '(강세)'}"},
            {"title": "📊 MACD (추세 신호)", "full_comment": f"{'반전 신호 (+)' if macd_diff_val > 0 else '하락 지속 (-)'}"},
            {"title": "📉 장기 추세 (120일선)", "full_comment": "🚨 위험 (폭포수 하락 중)" if is_waterfall else "✅ 안전 (추세 지지 또는 상승)"},
            {"title": "📈 일목균형표 (Ichimoku)", "full_comment": f"클라우드 해석: {'상승 흐름' if ichi_a.iloc[-1] > ichi_b.iloc[-1] else '하락 흐름'}"},
            {"title": "💎 볼린저 밴드 (변동성)", "full_comment": f"현재가 {('하단 근처' if curr_price <= bb_lower_val else '상단 근처' if curr_price >= bb_higher.iloc[-1] else '중간권역')}"},
            {"title": "🎯 ATR (변동성 범위)", "full_comment": "일중 변동성 계산 중..."},
            {"title": "🌊 VWAP (거래량 가중)", "full_comment": f"{'VWAP 상향 돌파' if curr_price > vwap.iloc[-1] else 'VWAP 하향 이탈'}"},
            {"title": "📊 Volume Profile", "full_comment": f"거래량: {volume.iloc[-1]:,.0f}주 (평균: {volume.mean():,.0f}주)"},
            {"title": "⚡ 매매 신호 종합", "full_comment": f"최종 판정: {verdict}"}
        ]

        fund_penalty = 0.0
        fund_msgs = []
        if apply_fundamental:
            fund_penalty, fund_msgs = check_fundamentals(stock)
            final_score = round(max(0.0, final_score - fund_penalty), 1)
            fund_combined_text = " / ".join(fund_msgs)
            detail_info.append({"title": "🏢 펀더멘털 검증 (재무제표)", "full_comment": fund_combined_text})

        # 🚨 [The Closer's 실시간 의견 교체 (is_rsi_hook_failed 인자 추가)]
        short_verdict, full_wallstreet_comment = get_closer_verdict_and_comment(
            final_score, rsi_val, mfi_val, curr_price, bb_lower_val, macd_diff_val, fund_penalty, is_waterfall, is_rsi_hook_failed
        )
        verdict = short_verdict
        detail_info.append({"title": "🎯 The Closer's 실시간 의견", "full_comment": full_wallstreet_comment})

        stop_loss = close.iloc[-1] * 0.90 if len(close) > 0 else 0

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
        return None, 0, f"분석 오류: {e}", [], 0
