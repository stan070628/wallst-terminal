import streamlit as st
import os

from stocks import STOCK_DICT
from tab_market import run_market_tab
from tab_scanner import run_scanner_tab
from tab_portfolio import run_portfolio_tab
from style_utils import apply_global_style
# auth_manager: 해시 기반 인증 (user_manager 완전 대체)
from auth_manager import verify_user, save_user

def auth_page():
    st.markdown("<h1 style='text-align:center; color:white;'>🔐 aibox 전문가 터미널</h1>", unsafe_allow_html=True)
    
    mode = st.radio("모드 선택", ["로그인", "가입하기"], horizontal=True)
    
    with st.container(border=True):
        u_id = st.text_input("아이디", placeholder="stan.lee", max_chars=20)
        u_pw = st.text_input("비밀번호", type="password", max_chars=50)
        
        if mode == "로그인":
            if st.button("진입하기", use_container_width=True, key="login_btn"):
                if not u_id or not u_pw:
                    st.error("아이디와 비밀번호를 모두 입력해주세요.")
                elif verify_user(u_id, u_pw):
                    login_user(u_id)
                    st.rerun()
                else:
                    st.error("정보가 일치하지 않습니다. 아이디를 먼저 등록하셨나요?")
        else:
            st.info("💡 새로운 전문가 계정을 등록하십시오.")
            if st.button("신규 가입 및 저장", use_container_width=True, key="signup_btn"):
                if not u_id or not u_pw:
                    st.error("아이디와 비밀번호를 모두 입력해야 합니다.")
                elif len(u_id) < 3:
                    st.error("아이디는 3자 이상이어야 합니다.")
                elif len(u_pw) < 4:
                    st.error("비밀번호는 4자 이상이어야 합니다.")
                else:
                    ok, msg = save_user(u_id, u_pw)
                    if ok:
                        st.success("🎉 가입 완료! 이제 로그인 모드에서 접속하십시오.")
                    else:
                        st.warning(msg) if "이미 등록" in msg else st.error(f"가입 실패: {msg}")



def login_user(username):
    st.session_state.logged_in = True
    st.session_state.user_id = username

def logout_user():
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.rerun()

# 전역 자동 로그인 체크 코드 제거
# saved_user = cookie_manager.get("user_session")
# if 'logged_in' not in st.session_state:
#     if saved_user:
#         st.session_state.logged_in = True
#         st.session_state.user_id = saved_user
#     else:
#         st.session_state.logged_in = False
#         st.session_state.user_id = None

def main():
    st.set_page_config(page_title="aibox - The Closer", layout="wide")
    apply_global_style()
    
    # st.session_state만 사용 (브라우저 탭별 독립 세션 보장)
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user_id = None

    if not st.session_state.logged_in:
        auth_page()
    else:
        try:
            st.sidebar.markdown(f"**👤 {st.session_state.user_id} 팀장**")
            menu = st.sidebar.radio("메뉴 선택", [
                "🔥 시장 전수조사", 
                "🔍 종목 정밀 진단", 
                "📊 내 계좌 관리"
            ])
            if st.sidebar.button("시스템 로그아웃", key="logout_btn"):
                logout_user()
            # 메뉴 선택에 따라 탭 실행
            if menu == "🔥 시장 전수조사":
                run_market_tab(STOCK_DICT)
            elif menu == "🔍 종목 정밀 진단":
                run_scanner_tab(STOCK_DICT)
            elif menu == "📊 내 계좌 관리":
                run_portfolio_tab(STOCK_DICT)
        except Exception as e:
            st.error(f"❌ 메뉴 실행 중 오류가 발생했습니다: {str(e)}")
            if st.button("로그인 페이지로 돌아가기"):
                st.session_state.logged_in = False
                st.session_state.user_id = None
                st.rerun()

if __name__ == "__main__": main()