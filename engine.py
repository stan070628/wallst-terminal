import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, timedelta
from ta.volume import VolumeWeightedAveragePrice, MFIIndicator, OnBalanceVolumeIndicator
from ta.trend import MACD, IchimokuIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

@st.cache_data(ttl=300)
def analyze_stock(ticker):
    try:
        # 1. 데이터 수집
        if ticker.endswith('.KS') or ticker.endswith('.KQ'):
            raw_ticker = ticker.split('.')[0]
            data = fdr.DataReader(raw_ticker, start=(datetime.now() - timedelta(days=250)).strftime('%Y-%m-%d'))
        else:
            data = yf.download(ticker, period="150d", interval="1d", progress=False, auto_adjust=True)
            if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
        
        if data is None or data.empty: return None, 0, "데이터 수집 실패", [], 0
        
        # 2. 데이터 정제 및 9대 지표 계산
        data = data.ffill().dropna()
        h, l, c, v = data['High'], data['Low'], data['Close'], data['Volume']
        
        # [9대 지표 리스트] Price, VWAP, Ichimoku, MACD, RSI, MFI, OBV, Volume, ATR
        data['vwap'] = VolumeWeightedAveragePrice(high=h, low=l, close=c, volume=v, window=20).volume_weighted_average_price()
        data['rsi'] = RSIIndicator(close=c).rsi()
        macd_ind = MACD(close=c)
        data['macd'], data['macd_sig'] = macd_ind.macd(), macd_ind.macd_signal()
        ichi = IchimokuIndicator(high=h, low=l)
        data['ichi_a'], data['ichi_b'] = ichi.ichimoku_a(), ichi.ichimoku_b()
        data['atr'] = AverageTrueRange(high=h, low=l, close=c).average_true_range()
        data['mfi'] = MFIIndicator(high=h, low=l, close=c, volume=v).money_flow_index()
        data['obv'] = OnBalanceVolumeIndicator(close=c, volume=v).on_balance_volume()

        # 3. 실시간 판독 코멘트 생성 (KeyWord 일치 작업)
        data = data.dropna()
        last = data.iloc[-1]
        score, details = 50.0, []

        # VWAP 판독
        v_dist = (last['Close'] - last['vwap']) / last['vwap'] * 100
        score += np.clip(v_dist * 8, -25, 25)
        details.append({
            "title": "⚖️ 세력 평단가 (VWAP)", # 'VWAP' 키워드 포함
            "full_comment": f"현재 주가가 세력 평단가 대비 {abs(v_dist):.1f}% {'위에 위치하여 지지' if v_dist > 0 else '아래에 위치하여 저항'}를 받고 있습니다."
        })

        # 구름대 판독
        cloud_top = max(last['ichi_a'], last['ichi_b'])
        i_dist = (last['Close'] - cloud_top) / last['Close'] * 100
        score += np.clip(i_dist * 5, -20, 20)
        details.append({
            "title": "☁️ 매물대 진단 (구름)", # '구름' 키워드 포함
            "full_comment": f"주가가 매물 구름대 {'위로 안착하여 상승 궤도' if i_dist > 0 else '아래로 이탈하여 하락 압력'}에 직면해 있습니다."
        })

        # RSI 판독
        r_val = last['rsi']
        details.append({
            "title": "🌡️ 엔진 온도 (RSI)", # 'RSI' 키워드 포함
            "full_comment": f"현재 RSI 지수는 {r_val:.1f}로 시장의 매수 심리가 {'과열권에 진입' if r_val > 70 else '안정적인 궤도'}에 있습니다."
        })

        final_score = np.clip(round(score, 1), 0, 100)
        stop_loss = last['Close'] - (last['atr'] * 2.5)
        msg = "🚀 [적극 매수]" if final_score >= 75 else "⚖️ [보유/관망]" if final_score >= 55 else "🚨 [위험/매도]"

        return data, final_score, msg, details, stop_loss
    except Exception as e: return None, 0, f"엔진 오류: {e}", [], 0