"""
auto_auth.py — AutoLoginClient for aibox Streamlit App
=======================================================
기능:
  - HMAC-SHA256 서명 토큰 기반 세션 관리
  - 서버사이드 세션 파일(auto_sessions.json) 영속화
  - 지수 백오프 재시도(Exponential Backoff Retry)
  - 세션 만료 / 강제 폐기(revoke)
  - auth_manager.verify_user 와 연동
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib3.util.retry import Retry

import requests
from requests.adapters import HTTPAdapter

from auth_manager import verify_user

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 설정 상수
# ─────────────────────────────────────────────
# [Security Fix] 하드코딩된 Secret 제거. 환경변수가 없으면 매번 랜덤 생성 (재시작 시 세션 만료됨)
_SECRET_KEY  = os.environ.get("SESSION_SECRET")
if not _SECRET_KEY:
    _SECRET_KEY = secrets.token_hex(32)
    logger.warning("⚠️ SESSION_SECRET not found in env. Generated temporary random key.")

_SESSION_FILE = os.environ.get("SESSION_FILE", "auto_sessions.json")
_TOKEN_TTL_HOURS = int(os.environ.get("SESSION_TTL_HOURS", "72"))   # 기본 3일


# ─────────────────────────────────────────────
# 커스텀 예외
# ─────────────────────────────────────────────
class SessionError(Exception):
    """세션 관련 오류의 기반 클래스."""

class InvalidTokenError(SessionError):
    """서명이 맞지 않거나 만료된 토큰."""

class CredentialsMissingError(SessionError):
    """자격 증명(ID/PW)이 비어있음."""


# ─────────────────────────────────────────────
# 1. 세션 파일 영속화 레이어
# ─────────────────────────────────────────────
class SessionPersistence:
    """서버사이드 세션 토큰 파일 읽기/쓰기 전담."""

    def __init__(self, file_path: str = _SESSION_FILE) -> None:
        self.file_path = Path(file_path)

    def save(self, sessions: Dict[str, dict]) -> None:
        """세션 맵 전체를 파일에 저장."""
        try:
            self.file_path.write_text(
                json.dumps(sessions, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.error("세션 저장 실패 (권한 오류?): %s", exc)
            raise SessionError(f"세션 파일 쓰기 실패: {exc}") from exc

    def load(self) -> Dict[str, dict]:
        """파일에서 세션 맵 로드. 없거나 손상됐으면 빈 딕셔너리 반환."""
        if not self.file_path.exists():
            return {}
        try:
            return json.loads(self.file_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("세션 파일 손상, 초기화합니다: %s", exc)
            return {}

    def purge_expired(self) -> int:
        """만료된 세션 항목 정리. 삭제된 개수 반환."""
        sessions = self.load()
        now = time.time()
        before = len(sessions)
        sessions = {
            token: meta
            for token, meta in sessions.items()
            if meta.get("expires_at", 0) > now
        }
        removed = before - len(sessions)
        if removed:
            self.save(sessions)
            logger.info("만료 세션 %d건 정리.", removed)
        return removed


# ─────────────────────────────────────────────
# 2. requests.Session 기반 재시도 헬퍼 (외부 API 연동용)
# ─────────────────────────────────────────────
def _build_robust_session(
    total_retries: int = 3,
    backoff_factor: float = 1.0,
) -> requests.Session:
    """
    지수 백오프 재시도가 설정된 requests.Session 생성.
    재시도 대상: 429, 500, 502, 503, 504
    """
    session = requests.Session()
    retry = Retry(
        total=total_retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# ─────────────────────────────────────────────
# 3. AutoLoginClient — 핵심 클래스
# ─────────────────────────────────────────────
class AutoLoginClient:
    """
    aibox 전용 자동 로그인 클라이언트.

    흐름::

        client = AutoLoginClient()

        # 최초 로그인 (브라우저에서 비밀번호 입력 후)
        token = client.login("stan.lee", "my_password")   # → 서명 토큰 반환

        # 페이지 리프레시 시 (브라우저 쿠키의 토큰으로 자동 로그인)
        user_id = client.get_user_from_token(token)       # → "stan.lee" 또는 None

        # 로그아웃
        client.revoke_token(token)
    """

    def __init__(
        self,
        session_file: str = _SESSION_FILE,
        secret_key: str = _SECRET_KEY,
        ttl_hours: int = _TOKEN_TTL_HOURS,
    ) -> None:
        self.persistence = SessionPersistence(session_file)
        self._secret    = secret_key.encode("utf-8")
        self.ttl        = timedelta(hours=ttl_hours)
        self.http       = _build_robust_session()   # 외부 API 연동용

    # ── 공개 API ────────────────────────────────

    def login(self, user_id: str, password: str) -> str:
        """
        비밀번호를 검증한 뒤 서명된 세션 토큰을 반환.

        Raises:
            CredentialsMissingError: user_id 또는 password가 비어있을 때.
            SessionError: 비밀번호 불일치(인증 실패).
        """
        if not user_id or not password:
            raise CredentialsMissingError("user_id와 password 모두 필요합니다.")

        if not verify_user(user_id, password):
            raise SessionError(f"[{user_id}] 비밀번호 불일치.")

        token = self._create_token(user_id)
        self._store_token(user_id, token)
        logger.info("로그인 성공 — 세션 토큰 발급: user=%s", user_id)
        return token

    def get_user_from_token(self, token: str) -> Optional[str]:
        """
        토큰이 유효하면 user_id를 반환, 만료/위조 시 None 반환.
        """
        if not token:
            return None
        try:
            self._verify_signature(token)
        except InvalidTokenError:
            return None

        sessions = self.persistence.load()
        meta = sessions.get(token)
        if not meta:
            return None  # 서버에 없는 토큰 (폐기됐거나 다른 서버)

        if meta["expires_at"] < time.time():
            self._remove_token(token, sessions)
            logger.info("만료된 세션 토큰 삭제.")
            return None

        return meta.get("user_id")

    def revoke_token(self, token: str) -> None:
        """토큰을 세션 저장소에서 즉시 삭제 (로그아웃)."""
        if not token:
            return
        sessions = self.persistence.load()
        if token in sessions:
            self._remove_token(token, sessions)
            logger.info("세션 토큰 폐기 완료.")

    def refresh_token(self, old_token: str) -> Optional[str]:
        """
        유효한 토큰을 갱신(TTL 연장).
        만료된 토큰이면 None 반환.
        """
        user_id = self.get_user_from_token(old_token)
        if not user_id:
            return None
        self.revoke_token(old_token)
        new_token = self._create_token(user_id)
        self._store_token(user_id, new_token)
        logger.info("세션 토큰 갱신: user=%s", user_id)
        return new_token

    def purge_expired_sessions(self) -> int:
        """만료된 세션 정리 (주기적 호출 권장). 삭제 건수 반환."""
        return self.persistence.purge_expired()

    # ── 내부 헬퍼 ──────────────────────────────

    def _create_token(self, user_id: str) -> str:
        """
        HMAC-SHA256 서명 토큰 생성.
        형식: {user_id}:{expires_ts}:{nonce}:{signature}
        nonce 로 같은 초내 중복 발급 방지.
        """
        expires_ts = int(time.time() + self.ttl.total_seconds())
        nonce      = secrets.token_hex(8)
        payload    = f"{user_id}:{expires_ts}:{nonce}"
        sig        = hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}:{sig}"

    def _verify_signature(self, token: str) -> Tuple[str, int]:
        """
        토큰 서명 검증. 유효하면 (user_id, expires_ts) 반환.

        Raises:
            InvalidTokenError: 형식 오류 또는 서명 불일치.
        """
        parts = token.split(":")
        if len(parts) != 4:
            raise InvalidTokenError("토큰 형식이 잘못됨.")
        user_id, expires_ts_str, nonce, provided_sig = parts
        payload = f"{user_id}:{expires_ts_str}:{nonce}"
        expected_sig = hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig, provided_sig):
            raise InvalidTokenError("서명 불일치 — 토큰 위조 의심.")
        return user_id, int(expires_ts_str)

    def _store_token(self, user_id: str, token: str) -> None:
        sessions = self.persistence.load()
        now_ts = time.time()
        sessions[token] = {
            "user_id"   : user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": int(now_ts + self.ttl.total_seconds()),
        }
        self.persistence.save(sessions)

    def _remove_token(self, token: str, sessions: Dict[str, dict]) -> None:
        sessions.pop(token, None)
        self.persistence.save(sessions)


# ─────────────────────────────────────────────
# 모듈 레벨 싱글턴 (Streamlit에서 import하여 사용)
# ─────────────────────────────────────────────
_client: Optional[AutoLoginClient] = None


def get_client() -> AutoLoginClient:
    """AutoLoginClient 싱글턴 반환."""
    global _client
    if _client is None:
        _client = AutoLoginClient()
    return _client
