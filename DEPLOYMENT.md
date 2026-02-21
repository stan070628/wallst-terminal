# 🚀 Streamlit Cloud 배포 가이드

## 데이터 유지 관리

### 클라우드 배포 시 로컬 파일 시스템의 한계
Streamlit Cloud에서 Python 스크립트가 실행될 때마다 파일 시스템이 초기화되기 때문에, 로컬의 `users.json`과 `portfolio_*.json`은 유지되지 않습니다.

**해결 방법:**
- **Option 1**: Streamlit Cloud의 **Secrets** 기능 사용
- **Option 2**: 상용 database 연동 (MySQL, PostgreSQL, Firebase)
- **Option 3**: 테스트 목적으로만 배포 시, `.streamlit/secrets.toml`에 하드코딩

## 배포 단계

### Step 1: GitHub 저장소 생성
```bash
git init
git add .
git commit -m "Initial commit: AI Stock Analysis Bot"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/auto_bot.git
git push -u origin main
```

### Step 2: Streamlit Cloud 연동
1. [Streamlit Cloud](https://share.streamlit.io)에 GitHub 계정으로 로그인
2. **"New app"** 클릭
3. GitHub 저장소 선택: `YOUR_USERNAME/auto_bot`
4. Main file path: `web_bot.py`
5. Deploy 클릭

### Step 3: Secrets 설정 (선택사항)

배포된 앱 설정 페이지에서:
```toml
# .streamlit/secrets.toml
test_user_id = "demo"
test_password = "demo1234"
```

### Step 4: 로컬 테스트 (배포 전 권장)
```bash
streamlit run web_bot.py
```

---

## 알려진 제한사항

| 기능 | 로컬 | 클라우드 |
|------|------|--------|
| 데이터 분석 | ✅ | ✅ |
| 사용자 등록/로그인 | ✅ | ⚠️ (재시작 시 초기화) |
| 포트폴리오 저장 | ✅ | ⚠️ (재시작 시 초기화) |

---

## 클라우드 환경에서의 조정안

`web_bot.py`에 다음을 추가하여 "데모 모드" 활성화 가능:

```python
import os

# 클라우드 환경 감지
is_cloud = "STREAMLIT_SERVER_HEADLESS" in os.environ

if is_cloud:
    # 고정 데모 계정만 사용
    st.info("☁️ 클라우드 테스트 환경: 데모 계정으로 접속하세요 (ID: demo / PW: demo1234)")
```

---

## 추천 DB 연동 (프로덕션용)

### Firebase Realtime Database
```python
import firebase_admin
from firebase_admin import db

# Streamlit Secrets에서 credential 로드
firebase_config = st.secrets["firebase"]
cred = firebase_admin.credentials.Certificate(firebase_config)
firebase_admin.initialize_app(cred, {"databaseURL": "YOUR_DB_URL"})

# 데이터 읽기/쓰기
ref = db.reference("users").child(user_id)
```

### Supabase (PostgreSQL)
```python
import supabase

url = st.secrets["supabase_url"]
key = st.secrets["supabase_key"]
client = supabase.create_client(url, key)

# 사용자 데이터
data = client.table("users").select("*").execute()
```

---

## 문제 해결

### 배포 후 로그인 실패
- ✅ `users.json` 초기화로 계정 재등록 필요
- ✅ `.streamlit/secrets.toml`에서 테스트 계정 설정

### 데이터가 저장되지 않음
- ✅ Streamlit Cloud 파일 시스템은 일시적 → DB 마이그레이션 추천
- ✅ 로컬 환경에서는 정상 작동

### 데이터 로드 시간 초과
- ✅ `@st.cache_data` 데코레이터로 캐싱 최적화
- ✅ 전 종목 대신 선택 종목만 분석하도록 설정

---

**배포 완료!** 🎉  
앱 URL: `https://share.streamlit.io/YOUR_USERNAME/auto_bot`
