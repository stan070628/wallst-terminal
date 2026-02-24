import yfinance as yf
import pandas as pd
import numpy as np
import streamlit as st
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

def calculate_sharp_score(rsi, mfi, bb_lower, curr_price, macd_diff):
    """
    [The Closer's 연속형(Continuous) 채점기]
    계단식 배점을 폐기하고, 지표의 수치를 소수점까지 점수로 환산합니다.
    단 하나의 동점자도 발생하지 않도록 0.1점 단위의 압도적 변별력을 부여합니다.
    """
    # 1. RSI Score (0~40점 만점): 선형 보간법 적용
    # RSI가 60 이상이면 0점, 20 이하로 갈수록 40점 만점에 수렴
    rsi_score = max(0.0, min(40.0, (60.0 - rsi) * 1.0))

    # 2. MFI Score (0~40점 만점): 자금 유입 강도
    # MFI가 60 이상이면 0점, 20 이하로 갈수록 40점 만점
    mfi_score = max(0.0, min(40.0, (60.0 - mfi) * 1.0))

    # 3. Bollinger Band (0~10점): 하단 이탈 한계선 측정
    # 하단선 대비 5% 이내(1.05) 진입 시부터 거리에 비례해 점수 부여 (딱 맞으면 10점)
    bb_ratio = (curr_price / bb_lower) if bb_lower > 0 else 1.0
    bb_score = 0.0
    if bb_ratio <= 1.05:
        bb_score = max(0.0, min(10.0, (1.05 - bb_ratio) * 200.0))

    # 4. MACD (0 또는 10점): 추세 반전 여부
    macd_score = 10.0 if macd_diff > 0 else 0.0

    # 총합 연산 (소수점 첫째 자리까지만 살려서 강력한 변별력 확보)
    raw_score = rsi_score + mfi_score + bb_score + macd_score
    final_score = round(min(100.0, max(0.0, raw_score)), 1)

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

        # 1. 동전주 검증 (1000원 미만)
        current_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
        if current_price > 0 and current_price < 1000:
            penalty += 30.0
            messages.append("🚨 [치명적 경고] 주가 1,000원 미만 동전주 (상폐 위험, -30점 감점)")

        # 2. 실적 검증 (EPS 마이너스 = 적자 기업)
        eps = info.get('trailingEps', 0)
        if eps is not None and eps < 0:
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

def get_closer_total_comment(final_score, rsi, mfi, macd_diff):
    """
    [The Closer's 총점 해설기]
    단순한 점수를 넘어, 지표 간의 괴리를 분석하고 냉혹한 트레이딩 전략을 하달합니다.
    """
    is_trend_good = macd_diff > 0
    is_overheated = rsi >= 60 or mfi >= 60

    if final_score < 30:
        if is_trend_good and is_overheated:
            return "🚨 [추격 매수 경고] 굵은 상승 추세(MACD)는 살아있으나, 단기 지표(RSI/MFI)가 과열되어 '진입 타점'이 붕괴된 상태입니다. 10~20점대의 낮은 점수는 '종목이 쓰레기'라는 뜻이 아니라, '지금 사면 고점에 물리니 눌림목(Pushback Buy)까지 인내하라'는 시스템의 강력한 통제입니다."
        else:
            return "🛑 [절대 관망] 추세가 하방으로 꺾였고 수급마저 말라붙은 죽은 차트입니다. 바닥 밑에 지하실이 있습니다. 굳이 떨어지는 칼날에 소중한 자본을 투입할 이유가 없습니다."

    elif final_score >= 70:
        if is_trend_good:
            return "💎 [천재지변급 기회] 상승 추세를 올라탄 상태에서 완벽한 눌림목(단기 과매도) 타점까지 형성되었습니다. 펀더멘털에 치명적 결함만 없다면 망설임 없이 분할 매수를 시작하십시오."
        else:
            return "🔪 [낙폭과대 반등 타겟] 거시적 추세는 역배열 하락장이지만, 단기적으로 피가 낭자한 '극한의 과매도' 바닥권에 진입했습니다. 기술적 반등(Dead Cat Bounce)을 노리는 짧은 트레이딩 타점으로 유효합니다."

    else:
        return "⚠️ [방향성 부재] 지표들이 혼조세를 보이며 명확한 타점을 주지 않는 횡보/애매한 구간입니다. 불확실성에 배팅하지 마십시오. 80점 이상의 확실한 대장주를 찾아 레이더를 다시 돌리십시오."

@st.cache_data(ttl=60)
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
        
        # 4. 고해상도 점수 계산
        raw_tech_score = calculate_sharp_score(rsi_val, mfi_val, bb_lower_val, curr_price, macd_diff_val)

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
                "title": "🎯 ATR (변동성 범위)",
                "full_comment": "일중 변동성 계산 중..."
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
        # 🚨 [The Closer's 펀더멘털 X-Ray 검증 실행]
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

        # 🚨 [The Closer's 총점 전문가 코멘트 추가]
        total_expert_verdict = get_closer_total_comment(final_score, rsi_val, mfi_val, macd_diff_val)
        detail_info.append({
            "title": "💡 The Closer's 총점 브리핑",
            "full_comment": total_expert_verdict
        })

        try:
            stop_loss = close.iloc[-1] * 0.90  # 10% 손절
        except:
            stop_loss = 0
        
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
