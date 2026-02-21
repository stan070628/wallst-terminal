import json
import os
import hashlib
import logging
from datetime import datetime
from typing import Tuple, Dict, Optional
import re
import fcntl
import stat

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

USER_DB = "users.json"
MIN_PASSWORD_LENGTH = 4
MIN_USER_ID_LENGTH = 3

def _lock_file(f):
    """파일 잠금 (Unix/Linux/Mac)"""
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    except:
        pass  # Windows에서는 무시

def _unlock_file(f):
    """파일 잠금 해제"""
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except:
        pass

def _set_secure_permissions(filepath: str):
    """파일 권한을 600 (owner-only)으로 설정"""
    try:
        os.chmod(filepath, stat.S_IRUSR | stat.S_IWUSR)
    except Exception as e:
        logger.warning(f"파일 권한 설정 실패: {e}")

def validate_user_id(user_id: str) -> Tuple[bool, str]:
    """사용자 ID 유효성 검사"""
    if not user_id or not isinstance(user_id, str):
        return False, "사용자 ID는 문자열이어야 합니다."
    
    user_id = user_id.strip()
    
    if len(user_id) < MIN_USER_ID_LENGTH:
        return False, f"사용자 ID는 {MIN_USER_ID_LENGTH}자 이상이어야 합니다."
    
    if len(user_id) > 50:
        return False, "사용자 ID는 50자 이하여야 합니다."
    
    if not re.match(r'^[a-zA-Z0-9._\-]+$', user_id):
        return False, "사용자 ID는 영문, 숫자, ._%- 만 허용됩니다."
    
    return True, "✅ 유효한 ID"

def validate_password(password: str) -> Tuple[bool, str]:
    """비밀번호 강도 검사"""
    if not password or not isinstance(password, str):
        return False, "비밀번호는 문자열이어야 합니다."
    
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"비밀번호는 {MIN_PASSWORD_LENGTH}자 이상이어야 합니다."
    
    if len(password) > 100:
        return False, "비밀번호는 100자 이하여야 합니다."
    
    return True, "✅ 유효한 비밀번호"

def hash_password(password: str) -> str:
    """SHA256으로 비밀번호를 해싱합니다 (Salt 포함)"""
    # Salt는 사용자 ID의 처음 8자 + 고정 값
    salt = "aibox_2026"
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return hashed

def _load_users() -> Dict:
    """사용자 데이터베이스를 로드합니다"""
    if not os.path.exists(USER_DB):
        return {}
    
    try:
        with open(USER_DB, "r", encoding="utf-8") as f:
            _lock_file(f)
            data = json.load(f)
            _unlock_file(f)
            return data
    except json.JSONDecodeError:
        logger.error(f"JSON 파싱 에러: {USER_DB}")
        return {}
    except Exception as e:
        logger.error(f"사용자 데이터 로드 실패: {e}")
        return {}

def _save_users(users: Dict) -> bool:
    """사용자 데이터베이스를 저장합니다"""
    try:
        temp_path = USER_DB + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            _lock_file(f)
            json.dump(users, f, ensure_ascii=False, indent=4)
            _unlock_file(f)
        
        # 파일 권한 설정 (보안)
        _set_secure_permissions(temp_path)
        
        # 기존 파일 삭제
        if os.path.exists(USER_DB):
            os.remove(USER_DB)
        
        # 임시 파일을 최종 파일로 이동
        os.rename(temp_path, USER_DB)
        
        # 최종 파일 권한 설정
        _set_secure_permissions(USER_DB)
        
        logger.info(f"사용자 데이터 저장 성공")
        return True
    except Exception as e:
        logger.error(f"사용자 데이터 저장 실패: {e}")
        # 임시 파일 정리
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False

# ============================================================
# 사용자 인증 관련 함수
# ============================================================

def verify_user(user_id: str, password: str) -> bool:
    """사용자 인증 (로그인)"""
    # 입력값 검증
    is_valid, _ = validate_user_id(user_id)
    if not is_valid:
        logger.warning(f"로그인 실패 - 유효하지 않은 ID: {user_id}")
        return False
    
    is_valid, _ = validate_password(password)
    if not is_valid:
        logger.warning(f"로그인 실패 - 유효하지 않은 비밀번호: {user_id}")
        return False
    
    try:
        users = _load_users()
        
        if user_id not in users:
            logger.warning(f"로그인 실패 - 존재하지 않는 사용자: {user_id}")
            return False
        
        user_data = users[user_id]
        hashed_password = hash_password(password)
        
        if user_data["password_hash"] != hashed_password:
            logger.warning(f"로그인 실패 - 잘못된 비밀번호: {user_id}")
            return False
        
        # 로그인 성공 - last_login 업데이트
        user_data["last_login"] = datetime.now().isoformat()
        _save_users(users)
        
        logger.info(f"로그인 성공: {user_id}")
        return True
    except Exception as e:
        logger.error(f"사용자 인증 중 오류: {e}")
        return False

def save_user(user_id: str, password: str) -> Tuple[bool, str]:
    """새 사용자를 등록합니다"""
    # 입력값 검증
    is_valid, msg = validate_user_id(user_id)
    if not is_valid:
        logger.warning(f"사용자 등록 실패 - {msg}")
        return False, msg
    
    is_valid, msg = validate_password(password)
    if not is_valid:
        logger.warning(f"사용자 등록 실패 - {msg}")
        return False, msg
    
    try:
        users = _load_users()
        
        if user_id in users:
            logger.warning(f"사용자 등록 실패 - 이미 존재: {user_id}")
            return False, f"이미 등록된 사용자입니다: {user_id}"
        
        # 새 사용자 생성
        users[user_id] = {
            "password_hash": hash_password(password),
            "created_at": datetime.now().isoformat(),
            "last_login": None,
            "is_active": True
        }
        
        success = _save_users(users)
        
        if success:
            logger.info(f"사용자 등록 성공: {user_id}")
            return True, f"사용자 '{user_id}'를 등록했습니다."
        else:
            return False, "사용자 저장 실패"
    except Exception as e:
        logger.error(f"사용자 등록 중 오류: {e}")
        return False, f"등록 실패: {str(e)}"

def load_users() -> Dict:
    """모든 사용자 정보를 로드합니다 (비밀번호 제외)"""
    try:
        users = _load_users()
        
        # 비밀번호 제외하고 반환
        public_users = {}
        for user_id, user_data in users.items():
            public_users[user_id] = {
                "created_at": user_data.get("created_at"),
                "last_login": user_data.get("last_login"),
                "is_active": user_data.get("is_active", True)
            }
        
        logger.info(f"사용자 목록 로드: {len(public_users)}명")
        return public_users
    except Exception as e:
        logger.error(f"사용자 목록 로드 실패: {e}")
        return {}

# ============================================================
# 비밀번호 및 계정 관리
# ============================================================

def change_password(user_id: str, old_password: str, new_password: str) -> Tuple[bool, str]:
    """비밀번호를 변경합니다"""
    # 현재 비밀번호 확인
    if not verify_user(user_id, old_password):
        logger.warning(f"비밀번호 변경 실패 - 인증 실패: {user_id}")
        return False, "현재 비밀번호가 잘못되었습니다."
    
    # 새 비밀번호 검증
    is_valid, msg = validate_password(new_password)
    if not is_valid:
        return False, msg
    
    # 같은 비밀번호인지 확인
    if old_password == new_password:
        return False, "새 비밀번호가 기존 비밀번호와 같습니다."
    
    try:
        users = _load_users()
        
        if user_id not in users:
            return False, "사용자를 찾을 수 없습니다."
        
        # 비밀번호 변경
        users[user_id]["password_hash"] = hash_password(new_password)
        users[user_id]["password_changed_at"] = datetime.now().isoformat()
        
        success = _save_users(users)
        
        if success:
            logger.info(f"비밀번호 변경 성공: {user_id}")
            return True, "비밀번호를 변경했습니다."
        else:
            return False, "저장 실패"
    except Exception as e:
        logger.error(f"비밀번호 변경 중 오류: {e}")
        return False, f"변경 실패: {str(e)}"

def deactivate_user(user_id: str, password: str) -> Tuple[bool, str]:
    """사용자 계정을 비활성화합니다 (삭제 대신)"""
    # 인증
    if not verify_user(user_id, password):
        logger.warning(f"계정 비활성화 실패 - 인증 실패: {user_id}")
        return False, "비밀번호가 잘못되었습니다."
    
    try:
        users = _load_users()
        
        if user_id not in users:
            return False, "사용자를 찾을 수 없습니다."
        
        # 계정 비활성화
        users[user_id]["is_active"] = False
        users[user_id]["deactivated_at"] = datetime.now().isoformat()
        
        success = _save_users(users)
        
        if success:
            logger.info(f"계정 비활성화: {user_id}")
            return True, "계정을 비활성화했습니다."
        else:
            return False, "저장 실패"
    except Exception as e:
        logger.error(f"계정 비활성화 중 오류: {e}")
        return False, f"비활성화 실패: {str(e)}"

def delete_user(user_id: str, password: str) -> Tuple[bool, str]:
    """사용자를 완전히 삭제합니다"""
    # 인증
    if not verify_user(user_id, password):
        logger.warning(f"계정 삭제 실패 - 인증 실패: {user_id}")
        return False, "비밀번호가 잘못되었습니다."
    
    try:
        users = _load_users()
        
        if user_id not in users:
            return False, "사용자를 찾을 수 없습니다."
        
        # 사용자 삭제
        del users[user_id]
        
        success = _save_users(users)
        
        if success:
            logger.info(f"계정 완전 삭제: {user_id}")
            return True, "계정을 완전히 삭제했습니다."
        else:
            return False, "저장 실패"
    except Exception as e:
        logger.error(f"계정 삭제 중 오류: {e}")
        return False, f"삭제 실패: {str(e)}"

# ============================================================
# 관리자 함수
# ============================================================

def reset_all_users() -> Tuple[bool, str]:
    """모든 사용자 데이터를 삭제합니다 (관리자 전용)"""
    try:
        if os.path.exists(USER_DB):
            os.remove(USER_DB)
            logger.warning("모든 사용자 데이터 초기화")
            return True, "모든 사용자 데이터를 초기화했습니다."
        else:
            return False, "사용자 데이터가 없습니다."
    except Exception as e:
        logger.error(f"초기화 실패: {e}")
        return False, f"초기화 실패: {str(e)}"

def get_user_info(user_id: str) -> Optional[Dict]:
    """특정 사용자의 정보를 조회합니다 (비밀번호 제외)"""
    try:
        users = _load_users()
        
        if user_id not in users:
            return None
        
        user_data = users[user_id].copy()
        # 비밀번호 제외
        user_data.pop("password_hash", None)
        
        return user_data
    except Exception as e:
        logger.error(f"사용자 정보 조회 실패: {e}")
        return None