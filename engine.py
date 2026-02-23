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
    추세 추종(Momentum) 중심의 현실적 점수 평정
    저점 매수만이 아닌 '가는 놈이 더 가는' 추세 추종 로직으로 전환
    """
    base_score = 40  # 기본 점수: 보정치 (0이 아닌 40에서 시작)
    multipliers = 1.0
    
    # 1. RSI (기준 완화: 30이하 → 40이하로 확대)
    if rsi <= 40:
        base_score += 30      # 과매도 기준 완화
    elif rsi >= 70:
        base_score -= 20      # 과매수 감점 유지

    # 2. MFI (수급 기준 완화: 20이하 → 40이하로 확대)
    if mfi <= 40:
        base_score += 15      # 자금 유입 신호

    # 3. 볼린저 밴드 (기존 유지)
    if curr_price <= bb_lower:
        base_score += 20      # BB 하단 돌파
        if rsi <= 35:
            multipliers += 0.5

    # 4. MACD (추세 가중치 강화: 10→20으로 상향, 승수 +0.3→+0.2로 변경)
    if macd_diff > 0:
        base_score += 20      # 추세 신호 가산점 대폭 상승
        multipliers += 0.2    # 추세가 살아있으면 1.2배 가산

    # 최종 점수 계산: 0~100점 제한
    final_score = min(100, max(0, int(base_score * multipliers)))
    
    return final_score

@st.cache_data(ttl=300)
def analyze_stock(ticker, period="6mo"):
    """
    고해상도 타격 시스템: Convergence Weight 기반
    여러 지표가 동시에 신호를 주면 점수 폭발 → 진정한 선별과 0점 남발 구분
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
        
        curr_price = close.iloc[-1]
        
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
        final_score = calculate_sharp_score(rsi_val, mfi_val, bb_lower_val, curr_price, macd_diff_val)
        
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
