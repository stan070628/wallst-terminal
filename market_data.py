import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta

def get_current_price(ticker):
    """
    [WallSt Pro: 이원화 데이터 수집기 - 최적화 버전]
    - 한국 종목(.KS, .KQ): FinanceDataReader (ETN 포함 완벽 지원 / 최근 7일치만 호출하여 속도 극대화)
    - 미국/글로벌/코인: yfinance
    """
    try:
        # 1. 국내 KOSPI/KOSDAQ 종목 처리 (ETN/ETF 포함)
        if ticker.endswith('.KS') or ticker.endswith('.KQ'):
            raw_ticker = ticker.split('.')[0]
            
            # [핵심 수정] 타임아웃 방지: 최근 7일 데이터만 핀셋 호출
            start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            df = fdr.DataReader(raw_ticker, start=start_date)
            
            if not df.empty:
                return float(df['Close'].iloc[-1])
            else:
                return None

        # 2. 해외 주식 / ETF / 암호화폐 처리 (yfinance)
        else:
            ticker_obj = yf.Ticker(ticker)
            
            if hasattr(ticker_obj, 'fast_info') and 'lastPrice' in ticker_obj.fast_info:
                return float(ticker_obj.fast_info['lastPrice'])
            else:
                df = ticker_obj.history(period="1d")
                if not df.empty:
                    return float(df['Close'].iloc[-1])
                return None
                
    except Exception as e:
        # 터미널에 에러의 진짜 원인을 출력함
        print(f"🔥 [{ticker}] 데이터 수신 치명적 오류: {e}")
        return None