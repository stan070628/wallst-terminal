import streamlit as st
import datetime
from datetime import timedelta

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
_COOKIE_NAME = "auth_token"

@st.cache_resource
def _get_auth_client() -> AutoLoginClient:
    """앱 전체에서 싱글턴으로 공유되는 AutoLoginClient."""
    return AutoLoginClient()


# 🚨 [1] 쿠키 매니저 접근자
# CookieManager는 Streamlit 컴포넌트이므로 매 스크립트 실행마다
# 생성자를 호출해야 브라우저와 통신이 가능합니다.
# main()에서 매번 생성 → 여기서는 이미 생성된 인스턴스 반환만 합니다.
def _get_cookie_manager():
    """main()에서 매 실행마다 생성한 CookieManager를 반환."""
    return st.session_state._cm


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
    st.session_state.logged_in     = True
    st.session_state.user_id       = user_id
    st.session_state.session_token = token


def _logout_user() -> None:
    client = _get_auth_client()
    token  = st.session_state.get("session_token")
    if token:
        client.revoke_token(token)               # 서버사이드 세션 폐기

    # 브라우저 쿠키 삭제 (출입증 압수)
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
# 🚨 [2] 하이패스 검증기: 앱 시작 시 쿠키를 검사
# ─────────────────────────────────────────────

def check_auto_login() -> bool:
    """
    브라우저 쿠키에 저장된 세션 토큰이 유효하면 자동 로그인(하이패스).
    성공 시 True, 실패(토큰 없음/만료/위조) 시 False.

    CookieManager의 get_all()을 사용하여 브라우저가 보낸 쿠키 전체를
    확인합니다. 첫 렌더 사이클에서는 JS 컴포넌트가 아직 마운트되지
    않아 None/빈 dict를 반환할 수 있으며, 이 경우 False를 반환합니다.
    (main()에서 1회 재시도 로직이 처리합니다.)
    """
    if st.session_state.logged_in:
        return True

    try:
        cm = _get_cookie_manager()
        # get_all()로 브라우저 쿠키 전체를 조회
        all_cookies = cm.get_all()
    except Exception:
        return False

    # 컴포넌트가 아직 준비되지 않은 상태
    if not all_cookies or not isinstance(all_cookies, dict):
        return False

    token = all_cookies.get(_COOKIE_NAME)
    if not token:
        return False

    # AutoLoginClient로 토큰 서버사이드 검증
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
# 🚨 [3] 로그인 / 가입 UI (자동 로그인 체크박스 포함)
# ─────────────────────────────────────────────

def login_page() -> None:
    st.markdown(
        "<h1 style='text-align:center; color:white;'>🔐 The Closer's Terminal Login</h1>",
        unsafe_allow_html=True,
    )

    mode = st.radio("모드 선택", ["로그인", "가입하기"], horizontal=True, key="login_mode_radio")

    if mode == "로그인":
        with st.form("login_form"):
            u_id = st.text_input("ID", placeholder="stan.lee", max_chars=20)
            u_pw = st.text_input("Password", type="password", max_chars=50)
            # ✅ 자동 로그인 체크박스 추가
            keep_login = st.checkbox("자동 로그인 유지 (30일)", key="keep_login_checkbox")

            submitted = st.form_submit_button("접속 (Login)", use_container_width=True)

            if submitted:
                if not u_id or not u_pw:
                    st.error("아이디와 비밀번호를 모두 입력해주세요.")
                else:
                    try:
                        client = _get_auth_client()
                        token  = client.login(u_id, u_pw)   # 검증 + 토큰 발급

                        # '자동 로그인'을 체크했다면 브라우저에 30일짜리 쿠키(출입증)를 굽습니다.
                        if keep_login:
                            cm = _get_cookie_manager()
                            expire_date = datetime.datetime.now() + timedelta(days=30)
                            cm.set(
                                _COOKIE_NAME,
                                token,
                                expires_at=expire_date,
                            )

                        _login_user(u_id, token)
                        st.success("인증 완료. 브라우저에 출입증을 발급하는 중입니다... ⏳")
                        
                        # 🚨 [The Closer's 강제 동기화 해킹] 
                        # 브라우저가 쿠키를 물리적으로 저장할 시간을 강제로 1초 벌어줍니다.
                        import time
                        time.sleep(1.0) 
                        
                        st.rerun()

                    except CredentialsMissingError:
                        st.error("아이디와 비밀번호를 모두 입력해주세요.")
                    except SessionError:
                        st.error("접근 거부: 인증 정보가 일치하지 않습니다.")

    else:   # 가입하기
        with st.container(border=True):
            u_id = st.text_input("아이디", placeholder="stan.lee", max_chars=20, key="signup_id")
            u_pw = st.text_input("비밀번호", type="password", max_chars=50, key="signup_pw")
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
# 🚨 [4] 메인 컨트롤러 (앱의 시작점)
# ─────────────────────────────────────────────

def main() -> None:
    st.set_page_config(page_title="aibox - The Closer", layout="wide")
    apply_global_style()

    _init_session_state()

    # ── CookieManager: 매 실행마다 반드시 생성자를 호출해야 함 ──
    # Streamlit 컴포넌트는 생성자 호출 = DOM에 렌더링.
    # 렌더링하지 않으면 브라우저 쿠키를 읽을 수 없습니다.
    st.session_state._cm = stx.CookieManager(key="global_cookie_manager")

    # ── 자동 로그인 하이패스 ──
    # 1단계: 세션이 False더라도 쿠키가 유효하면 하이패스 통과
    if not st.session_state.logged_in:
        auto_ok = check_auto_login()

        # 첫 렌더 사이클에서는 JS CookieManager 컴포넌트가 아직
        # 마운트되지 않아 쿠키를 못 읽을 수 있습니다.
        # → 1회만 재시도하여 컴포넌트가 준비된 후 다시 확인합니다.
        if not auto_ok and "_cookie_checked" not in st.session_state:
            st.session_state["_cookie_checked"] = True
            st.rerun()

    # 2단계: 로그인 상태에 따라 화면 분기
    if not st.session_state.logged_in:
        login_page()
    else:
        try:
            st.sidebar.markdown(f"**👤 {st.session_state.user_id} 팀장**")
            menu = st.sidebar.radio("메뉴 선택", [
                "🔥 시장 전수조사",
                "🔍 종목 정밀 진단",
                "📊 내 계좌 관리",
            ])
            # 로그아웃 버튼 (쿠키 삭제)
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
            if st.button("로그인 페이지로 돌아가기", key="back_to_login_btn"):
                st.session_state.logged_in = False
                st.session_state.user_id   = None
                st.rerun()


if __name__ == "__main__":
    main()