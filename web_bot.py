import streamlit as st
import os
from stocks import STOCK_DICT
from tab_market import run_market_tab
from tab_scanner import run_scanner_tab
from tab_portfolio import run_portfolio_tab
from style_utils import apply_global_style
from user_manager import verify_user, save_user, load_users

def auth_page():
    st.markdown("<h1 style='text-align:center; color:white;'>🔐 aibox 전문가 터미널</h1>", unsafe_allow_html=True)
    
    # 이 부분의 "모드 선택", "로그인", "가입하기"가 이제 흰색으로 보입니다.
    mode = st.radio("모드 선택", ["로그인", "가입하기"], horizontal=True)
    
    with st.container(border=True):
        u_id = st.text_input("아이디", placeholder="stan.lee")
        u_pw = st.text_input("비밀번호", type="password")
        
        if mode == "로그인":
            if st.button("진입하기", use_container_width=True):
                if verify_user(u_id, u_pw):
                    st.session_state.logged_in = True
                    st.session_state.user_id = u_id
                    st.rerun()
                else: st.error("정보가 일치하지 않습니다. 아이디를 먼저 등록하셨나요?")
        else:
            st.info("💡 새로운 전문가 계정을 등록하십시오.")
            if st.button("신규 가입 및 저장", use_container_width=True):
                if u_id and u_pw:
                    users = load_users()
                    if u_id in users: st.warning("이미 등록된 아이디입니다.")
                    else:
                        save_user(u_id, u_pw) # 여기서 TypeError 해결됨!
                        st.success("🎉 가입 완료! 이제 로그인 모드에서 접속하십시오.")
                else: st.error("모든 항목을 입력해야 합니다.")

    # 마스터 리셋 기능 (로그인 꼬였을 때 사용)
    st.write("---")
    if st.button("⚠️ 시스템 초기화 (모든 계정 삭제)", use_container_width=True):
        if os.path.exists("users.json"):
            os.remove("users.json")
            st.success("✅ 사용자 데이터가 초기화되었습니다. 다시 가입하십시오.")
            st.rerun()

def main():
    st.set_page_config(page_title="aibox - The Closer", layout="wide")
    apply_global_style()
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False

    if not st.session_state.logged_in: auth_page()
    else:
        st.sidebar.markdown(f"**👤 {st.session_state.user_id} 팀장**")
        menu = st.sidebar.radio("메뉴 선택", ["🔥 시장 전수조사", "🔍 종목 정밀 진단", "📊 내 계좌 관리"])
        if st.sidebar.button("시스템 로그아웃"):
            st.session_state.logged_in = False
            st.rerun()
        
        if menu == "🔥 시장 전수조사": run_market_tab(STOCK_DICT)
        elif menu == "🔍 종목 정밀 진단": run_scanner_tab(STOCK_DICT)
        elif menu == "📊 내 계좌 관리": run_portfolio_tab(STOCK_DICT)

if __name__ == "__main__": main()