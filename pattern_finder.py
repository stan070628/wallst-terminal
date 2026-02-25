import yfinance as yf
import pandas as pd
import numpy as np

def find_similar_patterns(ticker, lookback_days=20, future_days=[20, 60], top_n=3):
    """
    [The Closer's 프랙탈 패턴 레이더]
    현재 주가의 최근 N일 패턴을 과거 3년 치 차트와 대조하여,
    가장 똑같이 생긴 과거의 '도플갱어' 구간을 찾아내고 그 이후의 수익률을 추적합니다.
    """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="3y", auto_adjust=False)

        if len(df) < lookback_days * 3:
            return None, "데이터 부족 (최소 3년치 필요)"

        df = df.ffill().dropna()
        close_prices = df['Close'].values
        dates = df.index

        # 1. 현재 패턴 추출 및 정규화 (최근 N일)
        current_pattern = close_prices[-lookback_days:]
        current_std = np.std(current_pattern)
        if current_std == 0:
            return None, "현재 주가 변동성 0 (거래정지 등)"

        current_norm = (current_pattern - np.mean(current_pattern)) / current_std

        similarities = []

        # 2. 과거 3년치 구간을 슬라이딩하며 현재 패턴과 대조 (최근 N일 구간은 제외)
        scan_limit = len(close_prices) - lookback_days - max(future_days)

        for i in range(scan_limit):
            window = close_prices[i: i + lookback_days]
            window_std = np.std(window)
            if window_std == 0:
                continue

            window_norm = (window - np.mean(window)) / window_std

            # 피어슨 상관계수 계산 (1에 가까울수록 쌍둥이처럼 똑같음)
            corr = np.corrcoef(current_norm, window_norm)[0, 1]

            # 3. 과거 해당 패턴이 발생한 이후 N일 뒤의 주가가 어떻게 되었는지 추적
            past_current_price = close_prices[i + lookback_days - 1]
            future_returns = {}
            for days in future_days:
                future_price = close_prices[i + lookback_days - 1 + days]
                future_returns[f'ret_{days}'] = ((future_price - past_current_price) / past_current_price) * 100

            similarities.append({
                'start_date': dates[i].strftime('%y.%m.%d'),
                'end_date': dates[i + lookback_days - 1].strftime('%y.%m.%d'),
                'similarity': corr * 100,
                'idx': i,
                **future_returns
            })

        sim_df = pd.DataFrame(similarities).dropna()

        # 4. 싱크로율(유사도)이 가장 높은 순으로 정렬
        sim_df = sim_df.sort_values(by='similarity', ascending=False)

        # ---------------------------------------------------------
        # 🚨 5. 중복 구간 완벽 제거 (The Closer's 다중 겹침 방지 필터)
        # ---------------------------------------------------------
        filtered_matches = []
        selected_indices = [] # 선택된 '모든' 인덱스를 기억하는 배열
        
        for _, row in sim_df.iterrows():
            idx = int(row['idx'])
                
            # 이미 장바구니에 담긴 '모든' 패턴들의 날짜와 비교합니다.
            # 하나라도 겹치는 구간(lookback_days 즉 20일 이내)이 있다면 과감히 버립니다.
            is_overlap = any(abs(idx - s_idx) < lookback_days for s_idx in selected_indices)
            
            if not is_overlap:
                filtered_matches.append(row)
                selected_indices.append(idx)
                
            if len(filtered_matches) >= top_n:
                break
                
        if not filtered_matches:
            return None, "유사 패턴을 찾을 수 없습니다."
        # ---------------------------------------------------------

        # 6. 통계 종합 (평균 수익률 도출)
        result_df = pd.DataFrame(filtered_matches)
        avg_ret_20 = result_df['ret_20'].mean()
        avg_ret_60 = result_df['ret_60'].mean()

        summary = {
            'avg_ret_20': avg_ret_20,
            'avg_ret_60': avg_ret_60,
            'top_matches': result_df.to_dict('records')
        }

        return summary, "Success"

    except Exception as e:
        return None, f"오류 발생: {e}"
