#!/usr/bin/env python3
"""tab_deepdive.py의 검색 로직 테스트"""

from stocks import STOCK_DICT
import yfinance as yf

# 실제 탭_deepdive.py의 검색 로직 재현
def test_search(user_input):
    print(f"🔍 입력: '{user_input}'")
    
    ticker = None
    choice_name = user_input
    
    # [Stage 1] 띄어쓰기 제거 및 대소문자 통일
    clean_input = user_input.replace(" ", "").upper()
    print(f"   정규화: '{clean_input}'")
    
    # [Stage 2] ETF/ETN 강제 하드코딩
    etf_map = {
        "삼성은선물": "530089.KS",
        "ACEKRX금선물": "411060.KS",
        "ACEKRX금현물": "411060.KS",
        "KODEX코스피100": "237350.KS",
        "KODEX코스닥150": "229200.KS",
        "KODEX코스피": "226490.KS",
        "KODEX500": "069500.KS"
    }
    
    # 정확한 키 매칭
    for key, val in etf_map.items():
        if key == clean_input:
            ticker = val
            print(f"   ✅ Stage 2 정확한 매칭: {val}")
            break
    
    # 부분 포함 매칭
    if not ticker:
        for key, val in etf_map.items():
            if key in clean_input or clean_input in key:
                ticker = val
                print(f"   ✅ Stage 2 부분 매칭: {val}")
                break
    
    # [Stage 3] STOCK_DICT 검색
    if not ticker:
        for category in STOCK_DICT:
            if isinstance(STOCK_DICT[category], dict):
                for name, code in STOCK_DICT[category].items():
                    clean_dict_name = name.replace(" ", "").upper()
                    if clean_dict_name == clean_input:
                        ticker = code
                        print(f"   ✅ Stage 3 정확한 매칭: {code}")
                        break
                    elif clean_input in clean_dict_name or clean_dict_name in clean_input:
                        ticker = code
                        print(f"   ✅ Stage 3 부분 매칭: {code}")
                        break
            if ticker:
                break
    
    # [Stage 4] 숫자만 입력
    if not ticker:
        if clean_input.isdigit():
            ticker = f"{clean_input}.KS"
            print(f"   ✅ Stage 4 숫자 입력: {ticker}")
    
    # yfinance 시뮬레이션
    if ticker:
        try:
            df = yf.download(ticker, period="1d", progress=False)
            if not df.empty:
                print(f"   ✅ yfinance 조회 성공 ({len(df)} 줄)")
            else:
                print(f"   ❌ yfinance 빈 데이터")
        except Exception as e:
            print(f"   ❌ yfinance 에러: {str(e)[:50]}")
    else:
        print(f"   ❌ 모든 매칭 실패")
    
    print()
    return ticker

# 테스트
test_inputs = [
    "KODEX코스닥150",
    "KODEX 코스닥 150",
    "229200",
    "229200.KS",
    "코스닥150"
]

print("=" * 70)
print("탭_deepdive.py 검색 로직 상세 테스트")
print("=" * 70 + "\n")

for inp in test_inputs:
    test_search(inp)

print("\nstocks.py 상태 확인:")
kodex = STOCK_DICT["KOSDAQ"].get("KODEX 코스닥150")
print(f"STOCK_DICT['KOSDAQ']['KODEX 코스닥150'] = {kodex}")
