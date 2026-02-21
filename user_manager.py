import json
import os

USER_FILE = "users.json"

def load_users():
    if os.path.exists(USER_FILE):
        # [수정] 빈 파일(0바이트)일 경우 발생하는 JSONDecodeError 방지
        if os.path.getsize(USER_FILE) == 0:
            return {}
        try:
            with open(USER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {} # 파일 내용이 깨져있어도 빈 값 반환
    return {}

def save_user(user_id, user_pw):
    users = load_users()
    users[user_id] = user_pw
    with open(USER_FILE, "w", encoding="utf-8") as f:
        # ensure_ascii로 오타 수정 완료
        json.dump(users, f, ensure_ascii=False, indent=2)

def verify_user(user_id, user_pw):
    users = load_users()
    return users.get(user_id) == user_pw