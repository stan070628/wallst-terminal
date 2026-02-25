"""
test_auto_auth.py — AutoLoginClient pytest 테스트 스위트
=========================================================
실행: .venv/bin/python3 -m pytest test_auto_auth.py -v
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Dict
from unittest.mock import MagicMock, patch

import pytest

from auto_auth import (
    AutoLoginClient,
    CredentialsMissingError,
    InvalidTokenError,
    SessionError,
    SessionPersistence,
    _build_robust_session,
)


# ─────────────────────────────────────────────
# 공통 픽스처
# ─────────────────────────────────────────────

@pytest.fixture
def session_file(tmp_path: Path) -> str:
    return str(tmp_path / "test_sessions.json")


@pytest.fixture
def client(session_file: str) -> AutoLoginClient:
    """auth_manager.verify_user를 패치한 테스트용 클라이언트."""
    with patch("auto_auth.verify_user", return_value=True):
        c = AutoLoginClient(session_file=session_file, ttl_hours=1)
        yield c


@pytest.fixture
def client_bad_pw(session_file: str) -> AutoLoginClient:
    """verify_user가 항상 False인 클라이언트 (비밀번호 불일치 시뮬레이션)."""
    with patch("auto_auth.verify_user", return_value=False):
        c = AutoLoginClient(session_file=session_file, ttl_hours=1)
        yield c


# ─────────────────────────────────────────────
# 1. SessionPersistence 단위 테스트
# ─────────────────────────────────────────────

class TestSessionPersistence:

    def test_save_and_load_roundtrip(self, tmp_path):
        sp = SessionPersistence(str(tmp_path / "s.json"))
        data = {"token_abc": {"user_id": "stan.lee", "expires_at": 9999999999}}
        sp.save(data)
        loaded = sp.load()
        assert loaded == data

    def test_load_missing_file_returns_empty(self, tmp_path):
        sp = SessionPersistence(str(tmp_path / "nonexistent.json"))
        assert sp.load() == {}

    def test_load_corrupted_file_returns_empty(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("not_json!!!", encoding="utf-8")
        sp = SessionPersistence(str(f))
        assert sp.load() == {}

    def test_purge_expired_removes_old(self, tmp_path):
        sp = SessionPersistence(str(tmp_path / "s.json"))
        now = time.time()
        sessions = {
            "expired_token" : {"user_id": "a", "expires_at": now - 100},
            "valid_token"   : {"user_id": "b", "expires_at": now + 3600},
        }
        sp.save(sessions)
        removed = sp.purge_expired()
        assert removed == 1
        assert "valid_token" in sp.load()
        assert "expired_token" not in sp.load()

    def test_purge_empty_store_returns_zero(self, tmp_path):
        sp = SessionPersistence(str(tmp_path / "s.json"))
        assert sp.purge_expired() == 0


# ─────────────────────────────────────────────
# 2. AutoLoginClient — 토큰 생성/검증
# ─────────────────────────────────────────────

class TestTokenSignature:

    def test_create_token_has_three_parts(self, client):
        token = client._create_token("stan.lee")
        assert len(token.split(":")) == 4   # user_id:expires_ts:nonce:sig

    def test_verify_valid_token(self, client):
        token = client._create_token("stan.lee")
        user_id, _ = client._verify_signature(token)
        assert user_id == "stan.lee"

    def test_tampered_token_raises(self, client):
        token = client._create_token("stan.lee")
        parts = token.split(":")
        parts[0] = "hacker"          # user_id 변조
        tampered = ":".join(parts)
        with pytest.raises(InvalidTokenError):
            client._verify_signature(tampered)

    def test_wrong_format_raises(self, client):
        with pytest.raises(InvalidTokenError):
            client._verify_signature("bad:token")

    def test_empty_token_raises(self, client):
        with pytest.raises(InvalidTokenError):
            client._verify_signature("")


# ─────────────────────────────────────────────
# 3. AutoLoginClient — login()
# ─────────────────────────────────────────────

class TestLogin:

    def test_login_success_returns_token(self, client):
        token = client.login("stan.lee", "correct_pw")
        assert isinstance(token, str)
        assert len(token.split(":")) == 4   # user_id:expires_ts:nonce:sig

    def test_login_stores_session(self, client):
        token = client.login("stan.lee", "correct_pw")
        sessions = client.persistence.load()
        assert token in sessions
        assert sessions[token]["user_id"] == "stan.lee"

    def test_login_wrong_password_raises(self, client_bad_pw):
        with pytest.raises(SessionError):
            client_bad_pw.login("stan.lee", "wrong_pw")

    def test_login_empty_user_id_raises(self, client):
        with pytest.raises(CredentialsMissingError):
            client.login("", "some_pw")

    def test_login_empty_password_raises(self, client):
        with pytest.raises(CredentialsMissingError):
            client.login("stan.lee", "")

    def test_login_both_empty_raises(self, client):
        with pytest.raises(CredentialsMissingError):
            client.login("", "")


# ─────────────────────────────────────────────
# 4. AutoLoginClient — get_user_from_token()
# ─────────────────────────────────────────────

class TestGetUserFromToken:

    def test_valid_token_returns_user_id(self, client):
        token = client.login("stan.lee", "pw")
        assert client.get_user_from_token(token) == "stan.lee"

    def test_none_token_returns_none(self, client):
        assert client.get_user_from_token(None) is None

    def test_empty_token_returns_none(self, client):
        assert client.get_user_from_token("") is None

    def test_tampered_token_returns_none(self, client):
        token = client.login("stan.lee", "pw")
        parts = token.split(":")
        parts[0] = "evil"
        tampered = ":".join(parts)
        assert client.get_user_from_token(tampered) is None

    def test_unknown_token_returns_none(self, client):
        """서명은 맞지만 서버에 없는 토큰 → None."""
        # 다른 클라이언트 인스턴스로 만든 토큰은 서버 저장소에 없음
        other = AutoLoginClient(
            session_file=client.persistence.file_path.with_suffix(".other.json").as_posix()
        )
        with patch("auto_auth.verify_user", return_value=True):
            token = other.login("ghost", "pw")
        # client의 session_file에는 없으므로 None
        assert client.get_user_from_token(token) is None

    def test_expired_token_returns_none(self, session_file):
        """TTL 0초 클라이언트로 즉시 만료 시나리오."""
        with patch("auto_auth.verify_user", return_value=True):
            tiny_ttl_client = AutoLoginClient(session_file=session_file, ttl_hours=0)
            token = tiny_ttl_client.login("stan.lee", "pw")

        # 세션 expires_at을 과거로 수동 조작
        sessions = tiny_ttl_client.persistence.load()
        sessions[token]["expires_at"] = int(time.time()) - 1
        tiny_ttl_client.persistence.save(sessions)

        assert tiny_ttl_client.get_user_from_token(token) is None


# ─────────────────────────────────────────────
# 5. AutoLoginClient — revoke_token()
# ─────────────────────────────────────────────

class TestRevokeToken:

    def test_revoke_removes_session(self, client):
        token = client.login("stan.lee", "pw")
        client.revoke_token(token)
        assert client.get_user_from_token(token) is None

    def test_revoke_none_token_safe(self, client):
        """None 전달 시 예외 없이 조용히 무시."""
        client.revoke_token(None)  # should not raise

    def test_revoke_unknown_token_safe(self, client):
        """없는 토큰 revoke도 예외 없이 처리."""
        client.revoke_token("ghost:12345:abcdef")  # should not raise


# ─────────────────────────────────────────────
# 6. AutoLoginClient — refresh_token()
# ─────────────────────────────────────────────

class TestRefreshToken:

    def test_refresh_returns_new_token(self, client):
        old = client.login("stan.lee", "pw")
        new = client.refresh_token(old)
        assert new is not None
        assert new != old

    def test_old_token_invalidated_after_refresh(self, client):
        old = client.login("stan.lee", "pw")
        new = client.refresh_token(old)
        assert client.get_user_from_token(old) is None
        assert client.get_user_from_token(new) == "stan.lee"

    def test_refresh_expired_returns_none(self, client):
        """만료 토큰 갱신 시도 → None."""
        token = client.login("stan.lee", "pw")
        sessions = client.persistence.load()
        sessions[token]["expires_at"] = int(time.time()) - 1
        client.persistence.save(sessions)
        assert client.refresh_token(token) is None


# ─────────────────────────────────────────────
# 7. 전체 자동 로그인 플로우 통합 테스트
# ─────────────────────────────────────────────

class TestAutoLoginFlow:

    def test_full_flow_login_persist_autologin_logout(self, client):
        """
        1. 최초 로그인 → 토큰 발급
        2. 페이지 리프레시 시뮬레이션 → 토큰으로 자동 로그인
        3. 로그아웃 → 토큰 무효화
        """
        # 1. 최초 로그인
        token = client.login("stan.lee", "pw")
        assert token

        # 2. 자동 로그인 (토큰 검증)
        user = client.get_user_from_token(token)
        assert user == "stan.lee"

        # 3. 로그아웃
        client.revoke_token(token)
        assert client.get_user_from_token(token) is None

    def test_session_survives_new_client_instance(self, session_file):
        """세션 파일이 있으면 새 인스턴스도 자동 로그인 가능."""
        with patch("auto_auth.verify_user", return_value=True):
            c1 = AutoLoginClient(session_file=session_file)
            token = c1.login("stan.lee", "pw")

        with patch("auto_auth.verify_user", return_value=True):
            c2 = AutoLoginClient(session_file=session_file)
            user = c2.get_user_from_token(token)

        assert user == "stan.lee"

    def test_multiple_users_independent_sessions(self, session_file):
        """서로 다른 유저의 세션이 독립적으로 유지됨."""
        with patch("auto_auth.verify_user", return_value=True):
            c = AutoLoginClient(session_file=session_file)
            t1 = c.login("user_a", "pw")
            t2 = c.login("user_b", "pw")

        assert c.get_user_from_token(t1) == "user_a"
        assert c.get_user_from_token(t2) == "user_b"

        c.revoke_token(t1)
        assert c.get_user_from_token(t1) is None
        assert c.get_user_from_token(t2) == "user_b"   # 다른 유저 세션 유지


# ─────────────────────────────────────────────
# 8. _build_robust_session 단위 테스트
# ─────────────────────────────────────────────

class TestBuildRobustSession:

    def test_session_has_both_mounts(self):
        import requests
        s = _build_robust_session()
        assert isinstance(s, requests.Session)
        assert "https://" in s.adapters
        assert "http://" in s.adapters
