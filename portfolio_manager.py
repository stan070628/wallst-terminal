import json
import os

# 데이터 저장 파일 경로
PORTFOLIO_PATH = "my_portfolio.json"

def load_portfolio():
    """저장된 포트폴리오 데이터를 불러옵니다."""
    if os.path.exists(PORTFOLIO_PATH):
        try:
            with open(PORTFOLIO_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_portfolio(portfolio_list):
    """포트폴리오 데이터를 파일에 영구 저장합니다."""
    with open(PORTFOLIO_PATH, "w", encoding="utf-8") as f:
        json.dump(portfolio_list, f, ensure_ascii=False, indent=4)