import yfinance as yf
import pandas as pd
import numpy as np
import warnings
# engine.py is now the v2 engine
from engine import calculate_sharp_score

# TA lib import check
try:
    from ta.momentum import RSIIndicator
    from ta.volume import MFIIndicator
    from ta.volatility import BollingerBands
    from ta.trend import MACD
except ImportError:
    pass

warnings.filterwarnings('ignore')

def run_multi_backtest(ticker_dict, period="2y", target_days=20, target_score=70):
    print(f"\n🚀 [테스트 3] 60일선 정배열(모멘텀) 필터 / 쿨다운: {target_days}일")
    print("="*65)

    total_wins = 0
    total_losses = 0
    all_returns = []

    for name, ticker in ticker_dict.items():
        print(f"📡 {name}({ticker}) 스캔 중...", end="")
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period, auto_adjust=False)
            if len(df) < 120:
                print(" 🚨 패스 (데이터 부족)")
                continue

            # 컬럼 표준화
            df.columns = [c.capitalize() for c in df.columns]
            df = df.ffill().dropna()
            close = df['Close'].astype(float)

            # 지표 계산
            # TA 라이브러리 가정
            df['rsi'] = RSIIndicator(close=close, window=14).rsi()
            df['mfi'] = MFIIndicator(high=df['High'], low=df['Low'], close=close, volume=df['Volume'], window=14).money_flow_index()
            bb = BollingerBands(close=close, window=20, window_dev=2)
            df['bb_lower'] = bb.bollinger_lband()
            macd = MACD(close=close, window_fast=12, window_slow=26, window_sign=9)
            df['macd_diff'] = macd.macd_diff()
            
            df = df.dropna()
            # 60일 이평선
            df['ma60'] = df['Close'].rolling(window=60).mean()

            scores = []
            # calculate_sharp_score(rsi, mfi, bb_lower, curr_price, macd_diff, is_waterfall=...)
            # engine_v2 requires keyword arguments for is_waterfall/is_rsi_hook_failed if we skip middle args
            
            for i in range(len(df)):
                curr_price = float(df.iloc[i]['Close'])
                
                # Waterfall Check
                past_data = close.iloc[:i+1]
                is_waterfall = False
                if len(past_data) >= 125:
                    ma120 = past_data.rolling(window=120).mean()
                    if len(ma120) >= 5:
                         is_waterfall = (curr_price < ma120.iloc[-1]) and (ma120.iloc[-1] < ma120.iloc[-5])

                # [Engine v2 Compatible Call]
                s = calculate_sharp_score(
                    rsi=float(df.iloc[i]['rsi']), 
                    mfi=float(df.iloc[i]['mfi']), 
                    bb_lower=float(df.iloc[i]['bb_lower']), 
                    curr_price=curr_price, 
                    macd_diff=float(df.iloc[i]['macd_diff']), 
                    is_waterfall=is_waterfall
                )
                scores.append(s)
            
            df['ai_score'] = scores # type: ignore

            # 점수 70점 이상 AND 현재 주가가 60일선 위에 있을 때만 진입
            buy_signals = df[(df['ai_score'] >= target_score) & (df['Close'] > df['ma60'])]
            
            if buy_signals.empty:
                print(" ⚠️ 타점 없음")
                continue

            wins = 0
            losses = 0
            last_buy_idx = -9999

            for date, row in buy_signals.iterrows():
                idx = df.index.get_loc(date)
                if idx - last_buy_idx < target_days:
                    continue
                if idx + target_days >= len(df):
                    continue

                buy_price = row['Close']
                sell_price = df['Close'].iloc[idx + target_days]
                return_rate = ((sell_price - buy_price) / buy_price) * 100

                all_returns.append(return_rate)
                if return_rate > 0:
                    wins += 1
                else:
                    losses += 1
                last_buy_idx = idx

            if (wins + losses) > 0:
                print(f" ✅ {wins+losses}번 진입 (승률: {(wins/(wins+losses)*100):.1f}%)")
                total_wins += wins
                total_losses += losses
            else:
                print(" ⚠️ 실질 진입 없음")

        except Exception as e:
            # print(f" 🚨 오류: {e}")
            pass

    if total_wins + total_losses > 0:
        print("\n" + "="*65)
        print(f"💡 [테스트 3] 종합 승률: {(total_wins / (total_wins + total_losses) * 100):.1f}%")
        print(f"💰 평균 수익률: {np.mean(all_returns):+.2f}%")
        print("="*65)

if __name__ == "__main__":
    TEST_TARGETS = {
        "삼성전자": "005930.KS",
        # "SK하이닉스": "000660.KS",
        "NAVER": "035420.KS",
        # "카카오": "035720.KS",
        # "카카오뱅크": "323410.KS",
        # "에코프로": "086520.KQ",
        # "HLB": "028300.KQ",
        # "알테오젠": "196170.KQ",
        # "KODEX CS": "233740.KS",
        # "TIGER US": "381180.KS"
    }
    
    run_multi_backtest(TEST_TARGETS, period="2y", target_days=20, target_score=70)
