import streamlit as st
import os
from datetime import datetime, timedelta

import extra_streamlit_components as stx

from stocks import STOCK_DICT
from tab_market import run_market_tab
from tab_scanner import run_scanner_tab
from tab_portfolio import run_portfolio_tab
from style_utils import apply_global_style
from auth_manager import save_user
from auto_auth import AutoLoginClient, SessionError, CredentialsMissingError

# ─────────────────────────────────────────────
# 브라우저 쿠키 + 자동 로그인 설정
# ─────────────────────────────────────────────
_COOKIE_NAME = "aibox_session"
_COOKIE_TTL_DAYS = 3          # 브라우저 쿠키 만료 (서버 TTL과 일치)

@st.cache_resource
def _get_auth_client() -> AutoLoginClient:
    """앱 전체에서 싱글턴으로 공유되는 AutoLoginClient."""
    return AutoLoginClient()

@st.cache_resource
def _get_cookie_manager() -> stx.CookieManager:
    """싱글턴 CookieManager (중복 렌더링 방지)."""
    return stx.CookieManager()

# ─────────────────────────────────────────────
# 세션 상태 헬퍼
# ─────────────────────────────────────────────

def _init_session_state() -> None:
    defaults = {
        "logged_in": False,
        "user_id"  : None,
        "session_token": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _login_user(user_id: str, token: str) -> None:
    st.session_state.logged_in    = True
    st.session_state.user_id      = user_id
    st.session_state.session_token = token


def _logout_user() -> None:
    client = _get_auth_client()
    token  = st.session_state.get("session_token")
    if token:
        client.revoke_token(token)               # 서버사이드 세션 폐기

    # 브라우저 쿠키 삭제
    try:
        cm = _get_cookie_manager()
        cm.delete(_COOKIE_NAME)
    except Exception:
        pass

    st.session_state.logged_in     = False
    st.session_state.user_id       = None
    st.session_state.session_token = None
    st.rerun()


# ─────────────────────────────────────────────
# 자동 로그인: 브라우저 쿠키 → 토큰 검증
# ─────────────────────────────────────────────

def _try_auto_login() -> bool:
    """
    쿠키에 저장된 세션 토큰이 유효하면 자동 로그인.
    성공 시 True, 실패(토큰 없음/만료/위조) 시 False.
    """
    if st.session_state.logged_in:
        return True

    try:
        cm    = _get_cookie_manager()
        token = cm.get(_COOKIE_NAME)
    except Exception:
        return False

    if not token:
        return False

    client  = _get_auth_client()
    user_id = client.get_user_from_token(token)

    if user_id:
        _login_user(user_id, token)
        return True

    # 만료/위조 토큰 → 쿠키 정리
    try:
        cm.delete(_COOKIE_NAME)
    except Exception:
        pass
    return False


# ─────────────────────────────────────────────
# 로그인 / 가입 UI
# ─────────────────────────────────────────────

def auth_page() -> None:
    st.markdown(
        "<h1 style='text-align:center; color:white;'>🔐 aibox 전문가 터미널</h1>",
        unsafe_allow_html=True,
    )

    mode = st.radio("모드 선택", ["로그인", "가입하기"], horizontal=True)

    with st.container(border=True):
        u_id = st.text_input("아이디", placeholder="stan.lee", max_chars=20)
        u_pw = st.text_input("비밀번호", type="password", max_chars=50)

        if mode == "로그인":
            if st.button("진입하기", use_container_width=True, key="login_btn"):
                if not u_id or not u_pw:
                    st.error("아이디와 비밀번호를 모두 입력해주세요.")
                else:
                    try:
                        client = _get_auth_client()
                        token  = client.login(u_id, u_pw)   # 검증 + 토큰 발급

                        # 브라우저 쿠키에 토큰 저장 (TTL 3일)
                        cm = _get_cookie_manager()
                        expires = datetime.now() + timedelta(days=_COOKIE_TTL_DAYS)
                        cm.set(_COOKIE_NAME, token, expires=expires)

                        _login_user(u_id, token)
                        st.rerun()

                    except CredentialsMissingError:
                        st.error("아이디와 비밀번호를 모두 입력해주세요.")
                    except SessionError:
                        st.error("정보가 일치하지 않습니다. 아이디를 먼저 등록하셨나요?")

        else:   # 가입하기
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


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────

def main() -> None:
    st.set_page_config(page_title="aibox - The Closer", layout="wide")
    apply_global_style()

    _init_session_state()

    # 자동 로그인 시도 (쿠키 토큰 검증)
    _try_auto_login()

    if not st.session_state.logged_in:
        auth_page()
    else:
        try:
            st.sidebar.markdown(f"**👤 {st.session_state.user_id} 팀장**")
            menu = st.sidebar.radio("메뉴 선택", [
                "🔥 시장 전수조사",
                "🔍 종목 정밀 진단",
                "📊 내 계좌 관리",
            ])
            if st.sidebar.button("시스템 로그아웃", key="logout_btn"):
                _logout_user()

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
                st.session_state.user_id   = None
                st.rerun()


if __name__ == "__main__":
    main()