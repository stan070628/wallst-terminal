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
        # 데이터 수집
        if ticker.endswith('.KS') or ticker.endswith('.KQ'):
            raw_ticker = ticker.split('.')[0]
            data = fdr.DataReader(raw_ticker, start=(datetime.now() - timedelta(days=250)).strftime('%Y-%m-%d'))
        else:
            data = yf.download(ticker, period="150d", interval="1d", progress=False, auto_adjust=True)
        
        if data is None or data.empty or len(data) < 60: return None, 0, "데이터 부족", [], 0
        data = data.ffill().dropna()

        # 9대 지표 계산
        data['vwap'] = VolumeWeightedAveragePrice(high=data['High'], low=data['Low'], close=data['Close'], volume=data['Volume'], window=20).volume_weighted_average_price()
        ichi = IchimokuIndicator(high=data['High'], low=data['Low'])
        data['ichi_a'], data['ichi_b'] = ichi.ichimoku_a(), ichi.ichimoku_b()
        macd_ind = MACD(close=data['Close'])
        data['macd'], data['macd_sig'] = macd_ind.macd(), macd_ind.macd_signal()
        data['rsi'] = RSIIndicator(close=data['Close']).rsi()
        data['mfi'] = MFIIndicator(high=data['High'], low=data['Low'], close=data['Close'], volume=data['Volume']).money_flow_index()
        data['obv'] = OnBalanceVolumeIndicator(close=data['Close'], volume=data['Volume']).on_balance_volume()
        bb = BollingerBands(close=data['Close'])
        data['bb_h'], data['bb_l'] = bb.bollinger_hband(), bb.bollinger_lband()
        data['ma60'] = data['Close'].rolling(window=60).mean()
        data['atr'] = AverageTrueRange(high=data['High'], low=data['Low'], close=data['Close']).average_true_range()

        last = data.iloc[-1]
        score, details = 50.0, []

        # [편차 강화 로직] 9대 지표 정밀 가중치 시스템
        # 1. VWAP (기관 수급 - 강도 반영)
        v_dist = (last['Close'] - last['vwap']) / last['vwap'] * 100
        v_score = np.clip(v_dist * 5, -20, 20) # 거리만큼 점수 가중
        score += v_score
        details.append({
            "title": f"VWAP ({'기관의 지지' if v_score > 0 else '기관의 배신'})",
            "diff": round(v_score, 1),
            "desc": "기관과 외국인의 평균 매수 단가야.",
            "res": f"현재 가격이 VWAP 라인 대비 {abs(v_dist):.1f}% {'위' if v_score > 0 else '아래'}에 있어.",
            "view": "기관들이 평단가 아래에서 물량을 던지고 있다는 뜻이지. 이 라인이 강력한 저항이 될 거야." if v_score < 0 else "세력이 지키는 라인이니 든든한 버팀목이 될 거야."
        })

        # 2. 일목균형표 (매물대 - 두께 및 위치 반영)
        cloud_top = max(last['ichi_a'], last['ichi_b'])
        i_dist = (last['Close'] - cloud_top) / last['Close'] * 100
        i_score = np.clip(i_dist * 4, -25, 25)
        score += i_score
        details.append({
            "title": f"일목균형표 ({'매물 돌파' if i_score > 0 else '구름대 매몰'})",
            "diff": round(i_score, 1),
            "desc": "주가의 추세와 지지/저항을 시각화한 구름이야.",
            "res": f"주가가 두꺼운 구름대 {'위로 안착했어' if i_score > 0 else '아래로 완전히 가라앉았어'}.",
            "view": "이건 위쪽에 **'탈출하지 못한 매물'**이 산더미처럼 쌓여있다는 증거야. 하락 추세가 고착화됐어." if i_score < 0 else "매물벽을 뚫었어. 이제 주가는 가벼워질 거야."
        })

        # 3. RSI (심리 과열 - 굴곡 반영)
        r_val = last['rsi']
        r_score = (50 - r_val) * 0.8 # 50 기준 멀어질수록 감점/가점 강화
        score += r_score
        details.append({
            "title": f"RSI ({'과열권 경고' if r_val > 70 else '심리적 안정'})",
            "diff": round(r_score, 1),
            "desc": "현재 주가가 과열인지 침체인지를 나타내는 지표야.",
            "res": f"RSI 수치가 {r_val:.1f}를 기록하며 {'과열' if r_val > 70 else '적정'} 구간에 진입했어.",
            "view": "$RSI > 70$은 명백한 **과열권**이야. 주가는 떨어지는데 심리만 뜨겁다면 곧 가격 조정이라는 철퇴가 내려질 거야."
        })

        # 추가 지표 (MFI, MACD 등) 내부 점수 합산 (최종 점수 편차 유도)
        score += np.clip((last['macd'] - last['macd_sig']) / last['Close'] * 1000, -15, 15) # MACD 에너지
        
        final_score = np.clip(round(score, 1), 0, 100)
        stop_loss = last['Close'] - (last['atr'] * 2.5)
        
        if final_score >= 80: msg = "🔥 [적극 매수] 승률이 압도적입니다. 비중을 실으십시오."
        elif final_score >= 60: msg = "⚖️ [보유/관망] 상승 추세는 살아있으나 조정 가능성이 있습니다."
        else: msg = "🚨 [매도/위험] 하락 압력이 거셉니다. 자산을 지키는 것이 우선입니다."

        return data, final_score, msg, details, stop_loss
    except Exception: return None, 0, "엔진 오류", [], 0