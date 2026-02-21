import os
import requests
import json
from dotenv import load_dotenv

# 1. .env 파일 로드
load_dotenv()

# 2. 환경 변수 가져오기 (이름이 .env 파일과 정확히 일치해야 함)
# 만약 .env에 KIS_APP_KEY라고 적었다면 여기서도 똑같이 불러와야 합니다.
APP_KEY = os.getenv("KIS_APP_KEY")
APP_SECRET = os.getenv("KIS_APP_SECRET")

# 3. 모의투자 주소
URL_BASE = "https://openapivts.koreainvestment.com:29443"

def get_access_token():
    # 여기서 APP_KEY가 제대로 로드됐는지 체크
    if not APP_KEY or not APP_SECRET:
        print("\n[에러] .env 파일에서 키를 읽어오지 못했습니다.")
        print("1. .env 파일 이름 앞에 점(.)이 있는지 확인하세요.")
        print("2. .env 파일 안에 KIS_APP_KEY=... 형식이 맞는지 확인하세요.")
        return

    print(f"연결 시도 중... (App Key 앞자리: {APP_KEY[:5]}***)")
    
    headers = {"content-type": "application/json"}
    body = {
        "grant_type": "client_credentials",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET
    }
    
    URL = f"{URL_BASE}/oauth2/tokenP"
    
    try:
        res = requests.post(URL, headers=headers, data=json.dumps(body))
        res.raise_for_status()
        
        token = res.json().get("access_token")
        if token:
            print("\n" + "="*50)
            print("[성공] 한국투자증권 서버 연결 완료!")
            print(f"Access Token: {token[:30]}...")
            print("="*50)
        else:
            print("\n[실패] 응답값 오류:", res.text)
            
    except Exception as e:
        print(f"\n[통신 오류 발생] {e}")

if __name__ == "__main__":
    get_access_token()