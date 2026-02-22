#!/usr/bin/env python3
import yfinance as yf
from stocks import STOCK_DICT
from engine import analyze_stock

user_inputs = ["KODEX코스닥150", "229200", "229200.KS"]

print("=" * 60)
print("🔍 KODEX 코스닥150 조회 테스트")
print("=" * 60 + "\n")

for user_input in user_inputs:
    print(f"📍 테스트: '{user_input}'")
    
    # Stage 4: 숫자만 입력 처리
    clean_input = user_input.replace(" ", "").upper()
    ticker = None
    
    if clean_input.isdigit():
        ticker = f"{clean_input}.KS"
        print(f"   → Stage 4 숫자 입력: {ticker}")
    elif clean_input == "KODEX코스닥150":
        ticker = "229200.KS"
        print(f"   → 정확한 매칭: {ticker}")
    
    # yfinance 테스트
    if ticker:
        try:
            df = yf.download(ticker, period="1d", progress=False)
            if not df.empty:
                print(f"   ✅ yfinance 조회 성공: {len(df)} 줄")
                
                # engine 분석
                result = analyze_stock(ticker)
                if result:
                    score = result[1]
                    print(f"   ✅ engine 분석 성공: {score}점")
                else:
                    print(f"   ❌ engine 분석 실패")
            else:
                print(f"   ❌ yfinance 조회 실패 (빈 데이터)")
        except Exception as e:
            print(f"   ❌ 에러: {str(e)[:60]}")
    print()

print("\n" + "=" * 60)
print("stocks.py 확인")
print("=" * 60)
ticker_from_stocks = STOCK_DICT["KOSDAQ"].get("KODEX 코스닥150")
print(f"STOCK_DICT['KOSDAQ']['KODEX 코스닥150'] = {ticker_from_stocks}")
