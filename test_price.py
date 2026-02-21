import yfinance as yf

# yfinance로 한국 주식 데이터 조회 (한국투자증권 유료 API 불필요)
ticker = "005930.KS"  # 삼성전자
df = yf.download(ticker, period="5d")

print(f"\n✅ [검거 성공] {ticker} 삼성전자 데이터:")
print(df.tail())