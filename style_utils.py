import streamlit as st

def apply_global_style():
    """전체 프로그램을 Deep Black으로 고정하고, 버튼 박스를 흰색으로 하드코딩하여 가독성 해결"""
    st.markdown("""
        <style>
        /* 1. 전역 배경 및 기본 텍스트: 완전한 블랙 & 순백색 글씨 */
        [data-testid="stAppViewContainer"], .stApp, [data-testid="stHeader"], [data-testid="stSidebar"] {
            background-color: #000000 !important;
            color: #ffffff !important;
        }
        
        /* 2. [가독성 유지] 라벨들은 선명한 흰색으로 고정 */
        /* "모드 선택", "비밀번호", "로그인", "가입하기" */
        div[data-testid="stWidgetLabel"] p, 
        label p, 
        div[role="radiogroup"] label div p, 
        div[role="radiogroup"] label p {
            color: #ffffff !important;
            font-size: 1rem !important;
            font-weight: 700 !important;
        }

        /* 3. [핵심 수정] "진입하기", "시스템 초기화" 버튼 박스를 흰색으로 하드코딩 */
        .stButton>button {
            background-color: #ffffff !important; /* 박스 배경: 흰색 */
            color: #000000 !important; /* 글자 색상: 검은색 */
            border: 1px solid #ffffff !important;
            border-radius: 8px !important;
            height: 3em !important;
            width: 100% !important;
            transition: all 0.3s ease !important;
        }

        /* 버튼 내부의 모든 텍스트 요소를 검은색으로 강제 */
        .stButton>button p, .stButton>button div, .stButton>button span {
            color: #000000 !important;
            font-weight: 800 !important;
        }

        /* 호버 시 약간의 변화 (시각적 피드백) */
        .stButton>button:hover {
            background-color: #eeeeee !important;
            border-color: #ff3b30 !important; /* 호버 시 테두리만 레드 포인트 */
        }

        /* 4. 입력창(Input) 설정: 어두운 배경에 흰색 글씨 */
        input, select, textarea, div[data-baseweb="input"] {
            background-color: #1a1c23 !important;
            color: #ffffff !important;
            border: 1px solid #333a47 !important;
        }
        
        /* 5. 하얀색 알림 박스 내 검은색 글씨 고정 */
        div[data-testid="stNotification"], div[role="alert"], .stAlert {
            background-color: #ffffff !important;
        }
        div[role="alert"] p, .stAlert p {
            color: #000000 !important;
            font-weight: 700 !important;
        }
        </style>
    """, unsafe_allow_html=True)