import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
from ta.volume import MFIIndicator, OnBalanceVolumeIndicator, VolumeWeightedAveragePrice
from ta.volatility import BollingerBands, AverageTrueRange
from ta.momentum import RSIIndicator
from ta.trend import MACD, IchimokuIndicator

def analyze_stock(ticker):
    try:
        # 1. 데이터 수집 (투트랙 엔진)
        if ticker.endswith('.KS') or ticker.endswith('.KQ'):
            raw_ticker = ticker.split('.')[0]
            start_date = (datetime.now() - timedelta(days=250)).strftime('%Y-%m-%d')
            data = fdr.DataReader(raw_ticker, start=start_date)
            if not data.empty:
                data = data.tail(150)
        else:
            data = yf.download(ticker, period="150d", interval="1d", progress=False)
            if isinstance(data.columns, pd.MultiIndex): 
                data.columns = [col[0] for col in data.columns]
        
        if data is None or data.empty or len(data) < 60: 
            return None, 0, "데이터 부족", [], 0
            
        data = data.ffill().dropna()

        # 2. 기술적 지표 계산
        data['ma60'] = data['Close'].rolling(window=60).mean()
        data['rsi'] = RSIIndicator(close=data['Close']).rsi()
        macd_ind = MACD(close=data['Close'])
        data['macd'], data['macd_sig'] = macd_ind.macd(), macd_ind.macd_signal()
        data['mfi'] = MFIIndicator(high=data['High'], low=data['Low'], close=data['Close'], volume=data['Volume']).money_flow_index()
        data['obv'] = OnBalanceVolumeIndicator(close=data['Close'], volume=data['Volume']).on_balance_volume()
        data['vwap'] = VolumeWeightedAveragePrice(high=data['High'], low=data['Low'], close=data['Close'], volume=data['Volume'], window=20).volume_weighted_average_price()
        ichi = IchimokuIndicator(high=data['High'], low=data['Low'])
        data['ichi_a'], data['ichi_b'] = ichi.ichimoku_a(), ichi.ichimoku_b()
        data['atr'] = AverageTrueRange(high=data['High'], low=data['Low'], close=data['Close'], window=14).average_true_range()

        last = data.iloc[-1]
        prev = data.iloc[-2]
        
        # 🎯 [The Closer's 냉혹한 스코어링] - 변별력 끝판왕 버전
        score = 50.0 
        analysis = []

        # (1) VWAP 기관 수급 (격차에 따른 정밀 보상/징벌)
        vwap_diff = ((last['Close'] - last['vwap']) / last['vwap']) * 100
        # 단순히 위면 +15가 아니라, 0~5% 사이일 때만 최고점. 너무 멀어지면 과열로 간주.
        if 0 < vwap_diff <= 5:
            score += 15; analysis.append(f"🏢 [VWAP] 기관 평단 근접 상향 돌파 (최적 매수권 +15)")
        elif vwap_diff > 5:
            score += 5; analysis.append(f"🏢 [VWAP] 기관 수익권이나 이격 과다 (추격 주의 +5)")
        else:
            score -= 15; analysis.append(f"🏢 [VWAP] 기관 단가 아래. 강력한 저항 예상 (-15)")

        # (2) 일목균형표 구름대 (위치에 따른 가차없는 감점)
        cloud_top = max(last['ichi_a'], last['ichi_b'])
        if last['Close'] > cloud_top:
            score += 10; analysis.append("☁️ [일목] 구름대 위 안착. 매물대 지지 확인 (+10)")
        else:
            score -= 20; analysis.append("⛈️ [일목] 구름대 아래 매몰. 탈출 시급 (-20)")

        # (3) RSI (상승 탄력 vs 과매수 페널티)
        if 50 <= last['rsi'] <= 65:
            score += 15; analysis.append(f"💎 [RSI] 상승 에너지가 가장 응집된 구간 (+15)")
        elif last['rsi'] > 70:
            score -= 10; analysis.append(f"🔥 [RSI] {last['rsi']:.1f}로 과열권 진입. 익절 압박 (-10)")
        elif last['rsi'] < 35:
            score += 5; analysis.append(f"🧊 [RSI] {last['rsi']:.1f}로 과매도 구간. 기술적 반등 대기 (+5)")

        # (4) MACD & OBV (추세 및 세력 합치도)
        macd_gap = last['macd'] - last['macd_sig']
        if macd_gap > 0 and last['obv'] > prev['obv']:
            score += 10; analysis.append("🚀 [추세/수급] MACD 골든크로스와 OBV 매집 동시 발생 (+10)")
        elif macd_gap < 0:
            score -= 10; analysis.append("🔻 [추세] MACD 데드크로스 발생. 하락 전환 신호 (-10)")

        # 최종 점수 보정 (0~100점 사이로 제한)
        score = max(0, min(100.0, round(score, 1)))
        
        # 3. ATR 기반 수학적 손절가
        stop_loss_price = last['Close'] - (last['atr'] * 2.5) # 조금 더 보수적으로 2.5배 적용

        # 4. 핵심 메시지 판독
        if score >= 80: core_msg = "🔥 [적극 매수] 모든 지표가 승리를 가리킵니다. 비중을 실으십시오."
        elif score >= 60: core_msg = "⚖️ [부분 매수/홀딩] 추세는 살아있으나 단기 조정을 경계하십시오."
        elif score >= 40: core_msg = "⏳ [관망] 확실한 수급 유입이 보일 때까지 현금을 지키십시오."
        else: core_msg = "🚨 [탈출/매도] 엔진이 강력한 위험 신호를 보내고 있습니다."

        return data, score, core_msg, analysis, stop_loss_price
        
    except Exception as e:
        print(f"🔥 엔진 크래시: {e}")
        return None, 0, f"에러: {str(e)}", [], 0