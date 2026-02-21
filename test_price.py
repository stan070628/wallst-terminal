import FinanceDataReader as fdr

# [확정] 한국투자증권 앱에서 확인된 진짜 티커
ticker = "530089" 
df = fdr.DataReader(ticker)

print(f"\n✅ [검거 성공] {ticker} 삼성 은 선물 ETN(H) 데이터:")
print(df.tail())