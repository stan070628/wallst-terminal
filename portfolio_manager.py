import json
import os

def get_user_path(user_id):
    """사용자 ID별 고유 파일 경로를 생성합니다."""
    # 예: portfolio_stan.json, portfolio_guest1.json
    return f"portfolio_{user_id}.json"

def load_portfolio(user_id):
    """특정 사용자의 저장된 포트폴리오 데이터를 불러옵니다."""
    if not user_id:
        return []
        
    path = get_user_path(user_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ 데이터 로드 에러 ({user_id}): {e}")
            return []
    return []

def save_portfolio(user_id, portfolio_list):
    """특정 사용자의 포트폴리오 데이터를 별도의 파일에 영구 저장합니다."""
    if not user_id:
        return False
        
    path = get_user_path(user_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(portfolio_list, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"⚠️ 데이터 저장 에러 ({user_id}): {e}")
        return False