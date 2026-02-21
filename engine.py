import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, timedelta
from ta.volume import MFIIndicator, OnBalanceVolumeIndicator, VolumeWeightedAveragePrice
from ta.trend import MACD, IchimokuIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange, BollingerBands

@st.cache_data(ttl=300)
def analyze_stock(ticker):
    try:
        # 1. [핵심 수정] 데이터 수집 및 1차원 강제 압축 (Shape 오류 해결)
        if ticker.endswith('.KS') or ticker.endswith('.KQ'):
            raw_ticker = ticker.split('.')[0]
            data = fdr.DataReader(raw_ticker, start=(datetime.now() - timedelta(days=250)).strftime('%Y-%m-%d'))
        else:
            # yfinance 데이터 수집 시 Multi-index 컬럼 제거 및 1차원화
            data = yf.download(ticker, period="150d", interval="1d", progress=False, auto_adjust=True)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
        
        if data is None or data.empty or len(data) < 60: return None, 0, "데이터 부족", [], 0
        
        # [수정] 모든 컬럼을 1차원 Series로 강제 변환하여 ta 라이브러리 오류 방지
        data = data.ffill().dropna()
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if col in data.columns:
                data[col] = data[col].squeeze() # 2D(150, 1) -> 1D(150,) 변환

        # 9대 지표 계산
        data['vwap'] = VolumeWeightedAveragePrice(high=data['High'], low=data['Low'], close=data['Close'], volume=data['Volume'], window=20).volume_weighted_average_price()
        ichi = IchimokuIndicator(high=data['High'], low=data['Low'])
        data['ichi_a'], data['ichi_b'] = ichi.ichimoku_a(), ichi.ichimoku_b()
        macd_ind = MACD(close=data['Close'])
        data['macd'], data['macd_sig'] = macd_ind.macd(), macd_ind.macd_signal()
        data['rsi'] = RSIIndicator(close=data['Close']).rsi()
        data['mfi'] = MFIIndicator(high=data['High'], low=data['Low'], close=data['Close'], volume=data['Volume']).money_flow_index()
        data['obv'] = OnBalanceVolumeIndicator(close=data['Close'], volume=data['Volume']).on_balance_volume()
        data['atr'] = AverageTrueRange(high=data['High'], low=data['Low'], close=data['Close']).average_true_range()

        last = data.iloc[-1]
        score, details = 50.0, []

        # 2. [요청사항 반영] 전문가 코멘트 고도화 (수치 + 의미 해석)
        # VWAP (기관 수급)
        v_dist = (last['Close'] - last['vwap']) / last['vwap'] * 100
        v_score = np.clip(v_dist * 5, -20, 20)
        score += v_score
        v_view = "세력이 지키는 라인이니 든든한 버팀목이 될 거야." if v_dist > 0 else "기관들이 물량을 던지고 있어 강력한 저항이 될 거야."
        details.append({
            "title": f"VWAP ({'기관 지지' if v_dist > 0 else '기관 배신'})",
            "res": f"VWAP 대비 {abs(v_dist):.1f}% {'위' if v_dist > 0 else '아래'}에 위치",
            "view": v_view,
            "full_comment": f"현재 가격이 VWAP 라인 대비 {abs(v_dist):.1f}% {'위에' if v_dist > 0 else '아래에'} 있어. 이 의미는 {v_view}"
        })

        # 일목균형표 (매물대)
        cloud_top = max(last['ichi_a'], last['ichi_b'])
        i_dist = (last['Close'] - cloud_top) / last['Close'] * 100
        i_score = np.clip(i_dist * 4, -25, 25)
        score += i_score
        i_view = "매물벽을 뚫었어. 이제 주가는 가벼워질 거야." if i_dist > 0 else "위쪽에 탈출하지 못한 매물이 산더미처럼 쌓여있어 하락 추세가 고착화됐어."
        details.append({
            "title": f"일목균형표 ({'추세 돌파' if i_dist > 0 else '저항 매몰'})",
            "res": f"구름대 상단 대비 {abs(i_dist):.1f}% {'안착' if i_dist > 0 else '이탈'}",
            "view": i_view,
            "full_comment": f"주가가 구름대 상단 대비 {abs(i_dist):.1f}% {'안착한' if i_dist > 0 else '이탈한'} 상태야. 이 의미는 {i_view}"
        })

        # RSI (심리)
        r_val = last['rsi']
        r_score = (50 - r_val) * 0.8
        score += r_score
        r_view = "아직 심리적 과열이 없어 추가 상승 여력이 충분해." if r_val < 70 else "주가는 떨어지는데 심리만 뜨거워. 곧 가격 조정이라는 철퇴가 내려질 거야."
        details.append({
            "title": f"RSI ({'심리 안정' if r_val < 70 else '과열 경고'})",
            "res": f"RSI 지수 {r_val:.1f} 기록",
            "view": r_view,
            "full_comment": f"RSI 수치가 {r_val:.1f}를 기록하며 {'적정' if r_val < 70 else '과열'} 구간에 있어. 이 의미는 {r_view}"
        })

        final_score = np.clip(round(score, 1), 0, 100)
        stop_loss = last['Close'] - (last['atr'] * 2.5)
        
        if final_score >= 80: msg = "🔥 [적극 매수] 승률이 압도적입니다. 비중을 실으십시오."
        elif final_score >= 60: msg = "⚖️ [보유/관망] 상승 추세는 살아있으나 조정 가능성이 있습니다."
        else: msg = "🚨 [매도/위험] 하락 압력이 거셉니다. 자산을 지키는 것이 우선입니다."

        return data, final_score, msg, details, stop_loss
    except Exception as e: return None, 0, f"엔진 오류: {str(e)}", [], 0