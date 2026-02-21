import streamlit as st

def apply_global_style():
    """Deep Black 배경에 최적화된 전체 UI 스타일 - 대조비 WCAG 표준 준수"""
    st.markdown("""
        <style>
        /* ============================================
           1. 전역 배경 및 기본 텍스트
           ============================================ */
        [data-testid="stAppViewContainer"], .stApp, [data-testid="stHeader"], [data-testid="stSidebar"] {
            background-color: #000000 !important;
            color: #ffffff !important;
        }
        
        /* ============================================
           2. 라벨 스타일 (명확한 흰색)
           ============================================ */
        div[data-testid="stWidgetLabel"] p, 
        label p, 
        div[role="radiogroup"] label div p, 
        div[role="radiogroup"] label p {
            color: #ffffff !important;
            font-size: 1rem !important;
            font-weight: 700 !important;
        }

        /* ============================================
           3. 버튼 스타일 (활성)
           ============================================ */
        .stButton>button {
            background-color: #ffffff !important;
            color: #000000 !important;
            border: 1px solid #ffffff !important;
            border-radius: 8px !important;
            height: 3em !important;
            width: 100% !important;
            transition: all 0.3s ease !important;
            font-weight: 800 !important;
        }

        /* 버튼 내부의 모든 텍스트 요소를 검은색으로 강제 */
        .stButton>button p, .stButton>button div, .stButton>button span {
            color: #000000 !important;
            font-weight: 800 !important;
        }

        /* 호버 시 시각적 피드백 */
        .stButton>button:hover {
            background-color: #f0f0f0 !important;
            border-color: #ff3b30 !important;
            box-shadow: 0 0 10px rgba(255, 59, 48, 0.3) !important;
        }

        /* 버튼 비활성화 상태 */
        .stButton>button:disabled {
            background-color: #666666 !important;
            color: #999999 !important;
            border-color: #666666 !important;
            opacity: 0.6 !important;
        }

        /* ============================================
           4. 입력창 스타일 (대조비 개선)
           ============================================ */
        input, select, textarea, div[data-baseweb="input"] {
            background-color: #1e1e1e !important;
            color: #ffffff !important;
            border: 1.5px solid #444444 !important;
            border-radius: 6px !important;
            font-size: 0.95rem !important;
        }

        input::placeholder {
            color: #aaaaaa !important;
        }

        /* 입력창 포커스 상태 */
        input:focus, select:focus, textarea:focus {
            border-color: #ff3b30 !important;
            box-shadow: 0 0 5px rgba(255, 59, 48, 0.2) !important;
        }

        /* ============================================
           5. 알림 박스 (타입별 처리)
           ============================================ */
        /* Success (초록색 배경) */
        div[data-testid="stNotification"] > [data-testid="stNotificationContent"],
        .stSuccess {
            background-color: #1a4d2e !important;
            border-color: #2d7a4a !important;
            color: #ffffff !important;
        }
        .stSuccess p, div[data-testid="stNotification"] p {
            color: #ffffff !important;
            font-weight: 600 !important;
        }

        /* Error (빨간색 배경) */
        .stError {
            background-color: #4a1a1a !important;
            border-color: #7a2d2d !important;
            color: #ffffff !important;
        }
        .stError p {
            color: #ffffff !important;
            font-weight: 600 !important;
        }

        /* Warning (노란색 배경) */
        .stWarning {
            background-color: #4a3a1a !important;
            border-color: #7a6a2d !important;
            color: #ffffff !important;
        }
        .stWarning p {
            color: #ffffff !important;
            font-weight: 600 !important;
        }

        /* Info (파란색 배경) */
        .stInfo {
            background-color: #1a2a4a !important;
            border-color: #2d4a7a !important;
            color: #ffffff !important;
        }
        .stInfo p {
            color: #ffffff !important;
            font-weight: 600 !important;
        }

        /* ============================================
           6. 라디오 버튼 & 체크박스
           ============================================ */
        input[type="radio"], input[type="checkbox"] {
            accent-color: #ff3b30 !important;
        }

        div[role="radiogroup"], div[role="group"] {
            color: #ffffff !important;
        }

        /* ============================================
           7. 메트릭 (숫자 표시)
           ============================================ */
        [data-testid="metric-container"] {
            background-color: #0a0a0a !important;
            border: 1px solid #333333 !important;
            border-radius: 8px !important;
            padding: 1rem !important;
        }

        [data-testid="metric-container"] > div:first-child {
            color: #ffffff !important;
            font-weight: 600 !important;
        }

        [data-testid="metric-container"] > div:nth-child(2) {
            color: #ff3b30 !important;
            font-size: 1.8rem !important;
            font-weight: 800 !important;
        }

        /* ============================================
           8. 데이터프레임 (표)
           ============================================ */
        [data-testid="stDataFrame"] {
            background-color: #0a0a0a !important;
        }

        [data-testid="stDataFrame"] > div > div > table {
            color: #ffffff !important;
        }

        [data-testid="stDataFrame"] > div > div > table thead th {
            background-color: #1a1a1a !important;
            color: #ffffff !important;
            border-bottom: 2px solid #ff3b30 !important;
            font-weight: 800 !important;
        }

        [data-testid="stDataFrame"] > div > div > table tbody tr:hover {
            background-color: #1a1a1a !important;
        }

        [data-testid="stDataFrame"] > div > div > table tbody td {
            color: #ffffff !important;
            border-bottom: 1px solid #333333 !important;
        }

        /* ============================================
           9. Expander (펼치기)
           ============================================ */
        .streamlit-expanderHeader {
            background-color: #0a0a0a !important;
            border: 1px solid #333333 !important;
            border-radius: 6px !important;
            color: #ffffff !important;
            font-weight: 700 !important;
        }

        .streamlit-expanderHeader:hover {
            background-color: #1a1a1a !important;
            border-color: #ff3b30 !important;
        }

        .streamlit-expanderContent {
            background-color: #0a0a0a !important;
            border: 1px solid #333333 !important;
            border-top: 0 !important;
            border-radius: 0 0 6px 6px !important;
        }

        /* ============================================
           10. Selectbox & Multiselect
           ============================================ */
        [data-baseweb="select"] {
            background-color: #1e1e1e !important;
            border: 1.5px solid #444444 !important;
        }

        [data-baseweb="select"] > div {
            background-color: #1e1e1e !important;
            color: #ffffff !important;
        }

        /* ============================================
           11. Slider
           ============================================ */
        [data-testid="stSlider"] > div > div > div > div {
            color: #ffffff !important;
        }

        [data-baseweb="slider"] {
            background-color: #1e1e1e !important;
        }

        /* ============================================
           12. 탭 (Tabs)
           ============================================ */
        [role="tablist"] button {
            color: #cccccc !important;
            background-color: transparent !important;
            border: none !important;
            border-bottom: 2px solid transparent !important;
            transition: all 0.3s ease !important;
        }

        [role="tablist"] button[aria-selected="true"] {
            color: #ffffff !important;
            border-bottom-color: #ff3b30 !important;
            font-weight: 800 !important;
        }

        [role="tablist"] button:hover {
            color: #ffffff !important;
        }

        /* ============================================
           13. 제목 (h1, h2, h3 등)
           ============================================ */
        h1, h2, h3, h4, h5, h6 {
            color: #ffffff !important;
            font-weight: 800 !important;
        }

        /* ============================================
           14. 일반 텍스트
           ============================================ */
        p, div, span {
            color: #ffffff !important;
        }

        /* ============================================
           15. 링크 스타일
           ============================================ */
        a {
            color: #ff3b30 !important;
            text-decoration: none !important;
            font-weight: 600 !important;
        }

        a:hover {
            color: #ffffff !important;
            text-decoration: underline !important;
        }

        /* ============================================
           16. 스크롤바 커스터마이징
           ============================================ */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }

        ::-webkit-scrollbar-track {
            background-color: #1a1a1a !important;
        }

        ::-webkit-scrollbar-thumb {
            background-color: #ff3b30 !important;
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background-color: #ff5c52 !important;
        }

        /* ============================================
           17. 구분선 (hr)
           ============================================ */
        hr {
            background-color: #333333 !important;
            border: none !important;
            height: 1px !important;
        }

        /* ============================================
           18. 코드 블록
           ============================================ */
        code, pre {
            background-color: #0a0a0a !important;
            color: #00ff00 !important;
            border: 1px solid #333333 !important;
            border-radius: 4px !important;
            padding: 4px 8px !important;
        }

        /* ============================================
           19. 상태 메시지 (status)
           ============================================ */
        [data-testid="stStatus"] {
            background-color: #0a0a0a !important;
            border: 1px solid #333333 !important;
        }

        [data-testid="stStatus"] > div > p {
            color: #ffffff !important;
        }
        </style>
    """, unsafe_allow_html=True)