# 📈 WallSt Pro AI Terminal
> **9대 기술적 지표를 활용한 실시간 주식/코인 정밀 진단 시스템**

이 프로젝트는 한국 시장(KOSPI, KOSDAQ)과 글로벌 시장(NASDAQ, Crypto)의 데이터를 실시간으로 스캔하고, 기관 수급 및 기술적 지표를 분석하여 최적의 타격 지점을 찾아주는 AI 터미널입니다.

## ✨ 주요 기능 (Key Features)
- **투트랙 데이터 엔진**: `yfinance`와 `FinanceDataReader`를 결합하여 국내외 전 종목 완벽 지원.
- **9대 지표 정밀 진단**: RSI, MACD, 일목균형표, VWAP, ATR 등 전문가급 지표 분석.
- **The Closer's 스코어링**: 0.1점 단위의 초정밀 알고리즘을 통한 종목 서열화.
- **실시간 포트폴리오 관리**: 내 평단가 대비 실시간 수익률 및 ATR 기반 기계적 손절가 제시.

## 🛠️ 기술 스택 (Tech Stack)
- **Frontend**: Streamlit
- **Analysis**: Pandas, TA-Lib (ta)
- **Visualization**: Plotly
- **Data Source**: Yahoo Finance, KRX (via FinanceDataReader)

## 🚀 시작하기 (Getting Started)

### 1. 환경 설정
프로젝트를 로컬 환경에 복제하고 필요한 라이브러리를 설치합니다.
```bash
git clone [https://github.com/네아이디/저장소이름.git](https://github.com/네아이디/저장소이름.git)
cd auto_bot
pip install -r requirements.txt