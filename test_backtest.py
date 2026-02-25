import yfinance as yf
import pandas as pd
import numpy as np
from engine import calculate_sharp_score

# 경고 메시지 무시
import warnings
warnings.filterwarnings('ignore')

# 보조지표 라이브러리 (engine.py와 동일)
from ta.momentum import RSIIndicator
from ta.volume import MFIIndicator
from ta.volatility import BollingerBands
from ta.trend import MACD

def run_backtest(ticker, period="2y", target_days=20):
    """
    [The Closer's 백테스트 엔진]
    과거 2년간 매일매일 AI 점수를 계산하고, 
    80점 이상(강력 매수) 떴을 때 진입해서 target_days(예: 20거래일=약 1달) 보유했을 때의 수익률을 추적합니다.
    """
    print(f"\n📡 [{ticker}] 과거 {period} 데이터 추출 및 타임머신 가동 중...")
    
    stock = yf.Ticker(ticker)
    df = stock.history(period=period, auto_adjust=False)
    
    if df.empty or len(df) < 50:
        print("데이터가 부족하여 백테스트를 종료합니다.")
        return
        
    df.columns = [c.capitalize() for c in df.columns]
    df = df.ffill().dropna()
    if 'Volume' in df.columns:
        df['Volume'] = df['Volume'].replace(0, 1)

    close = df['Close'].astype(float)
    high = df['High'].astype(float)
    low = df['Low'].astype(float)
    volume = df['Volume'].astype(float)

    # 1. 과거 데이터 전체에 대해 지표 일괄 계산
    df['rsi'] = RSIIndicator(close=close, window=14).rsi()
    df['mfi'] = MFIIndicator(high=high, low=low, close=close, volume=volume, window=14).money_flow_index()
    
    bb = BollingerBands(close=close, window=20, window_dev=2)
    df['bb_lower'] = bb.bollinger_lband()
    
    macd = MACD(close=close, window_fast=12, window_slow=26, window_sign=9)
    df['macd_diff'] = macd.macd_diff()

    # NaN 데이터 제거 (초기 계산 기간)
    df = df.dropna()

    # 2. 매일매일의 AI 신뢰도 점수 계산
    df['ai_score'] = df.apply(lambda row: calculate_sharp_score(
        row['rsi'], row['mfi'], row['bb_lower'], row['Close'], row['macd_diff']
    ), axis=1)

    # 3. 타점(Signal) 추적 및 수익률 계산
    # 80점 이상을 받은 날만 '매수 타점'으로 기록
    buy_signals = df[df['ai_score'] >= 80]
    
    if buy_signals.empty:
        print("⚠️ 80점 이상의 '천재지변급 기회'가 단 한 번도 없었습니다. (엔진이 매우 보수적임)")
        return

    print(f"🎯 총 {len(buy_signals)}번의 [강력 매수] 타점이 발견되었습니다.\n")
    
    wins = 0
    losses = 0
    total_returns = []

    for date, row in buy_signals.iterrows():
        # 매수일(Signal Date)의 인덱스 번호 찾기
        idx = df.index.get_loc(date)
        
        # 미래 데이터가 부족하면 패스 (최근에 시그널이 뜬 경우)
        if idx + target_days >= len(df):
            continue
            
        buy_price = row['Close']
        # 진입 후 N일 뒤의 매도 가격
        sell_date = df.index[idx + target_days]
        sell_price = df['Close'].iloc[idx + target_days]
        
        # 진입 후 N일간의 최고점 (최대 수익 가능성)
        max_price_in_period = df['High'].iloc[idx : idx + target_days].max()
        
        # 수익률 계산
        return_rate = ((sell_price - buy_price) / buy_price) * 100
        max_return = ((max_price_in_period - buy_price) / buy_price) * 100
        total_returns.append(return_rate)
        
        if return_rate > 0:
            wins += 1
            result_str = "🟢 WIN "
        else:
            losses += 1
            result_str = "🔴 LOSS"
            
        print(f"[{date.strftime('%Y-%m-%d')}] 매수가: {buy_price:,.0f}원 ➡️ {target_days}일 뒤: {sell_price:,.0f}원 | {result_str} ({return_rate:+.2f}%) | 기간 내 최대 상승: {max_return:+.2f}%")

    # 4. 최종 리포트 출력
    if wins + losses > 0:
        win_rate = (wins / (wins + losses)) * 100
        avg_return = np.mean(total_returns)
        print("\n" + "="*50)
        print("💡 [The Closer's 백테스트 최종 성적표]")
        print("="*50)
        print(f"▪️ 타겟 종목: {ticker}")
        print(f"▪️ 보유 기간: {target_days} 거래일 (약 1개월)")
        print(f"▪️ 총 진입 횟수: {wins + losses}회")
        print(f"▪️ 승률 (Win Rate): {win_rate:.1f}% ({wins}승 {losses}패)")
        print(f"▪️ 평균 수익률: {avg_return:+.2f}%")
        print("="*50)

if __name__ == "__main__":
    # 테스트하고 싶은 종목 코드를 넣으십시오.
    # 삼성전자 (005930.KS), 코스닥150 (229200.KS), SK하이닉스 (000660.KS)
    target_ticker = "005930.KS" 
    run_backtest(target_ticker, period="2y", target_days=20)
