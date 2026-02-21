import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import fcntl

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ====== 포트폴리오 데이터 스키마 ======
SCHEMA = {
    "name": str,           # 종목명 (예: "삼성전자")
    "ticker": str,         # 티커 (예: "005930.KS")
    "quantity": (int, float),  # 보유 수량
    "buy_price": (int, float), # 매입가
    "buy_date": str        # 매입일 (YYYY-MM-DD)
}

def get_user_path(user_id: str) -> str:
    """사용자 ID별 고유 파일 경로를 생성합니다."""
    if not user_id:
        raise ValueError("사용자 ID가 필요합니다.")
    return f"portfolio_{user_id}.json"

def validate_stock_entry(entry: Dict) -> Tuple[bool, str]:
    """포트폴리오 항목의 유효성을 검사합니다."""
    
    # 필수 필드 확인
    required_fields = ["name", "ticker", "quantity", "buy_price", "buy_date"]
    for field in required_fields:
        if field not in entry:
            return False, f"필수 필드 누락: {field}"
    
    # 데이터 타입 확인
    if not isinstance(entry["name"], str) or not entry["name"].strip():
        return False, "종목명은 공백이 아닌 문자열이어야 합니다."
    
    if not isinstance(entry["ticker"], str) or not entry["ticker"].strip():
        return False, "티커는 공백이 아닌 문자열이어야 합니다."
    
    # 수량 확인
    try:
        quantity = float(entry["quantity"])
        if quantity <= 0:
            return False, "수량은 0보다 커야 합니다."
    except (ValueError, TypeError):
        return False, "수량은 숫자여야 합니다."
    
    # 매입가 확인
    try:
        buy_price = float(entry["buy_price"])
        if buy_price < 0:
            return False, "매입가는 0 이상이어야 합니다."
    except (ValueError, TypeError):
        return False, "매입가는 숫자여야 합니다."
    
    # 매입일 확인
    try:
        datetime.strptime(entry["buy_date"], "%Y-%m-%d")
    except ValueError:
        return False, "매입일은 YYYY-MM-DD 형식이어야 합니다."
    
    return True, "✅ 유효한 항목"

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

def load_portfolio(user_id: str) -> List[Dict]:
    """특정 사용자의 저장된 포트폴리오 데이터를 불러옵니다."""
    if not user_id:
        logger.warning("사용자 ID가 없습니다.")
        return []
    
    path = get_user_path(user_id)
    
    if not os.path.exists(path):
        logger.info(f"포트폴리오 파일이 존재하지 않습니다: {path}")
        return []
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            _lock_file(f)
            data = json.load(f)
            _unlock_file(f)
            
            # 메타데이터는 제외하고 포트폴리오만 반환
            if isinstance(data, dict) and "stocks" in data:
                logger.info(f"포트폴리오 로드 성공 ({user_id}): {len(data['stocks'])}개 종목")
                return data["stocks"]
            else:
                logger.warning(f"포트폴리오 형식이 잘못되었습니다: {path}")
                return []
    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 에러 ({user_id}): {e}")
        return []
    except Exception as e:
        logger.error(f"데이터 로드 에러 ({user_id}): {e}")
        return []

def save_portfolio(user_id: str, portfolio_list: List[Dict]) -> bool:
    """특정 사용자의 포트폴리오 데이터를 안전하게 저장합니다."""
    if not user_id:
        logger.warning("사용자 ID가 없습니다.")
        return False
    
    # 데이터 검증
    for i, entry in enumerate(portfolio_list):
        is_valid, msg = validate_stock_entry(entry)
        if not is_valid:
            logger.error(f"포트폴리오 항목 {i}번 유효성 검사 실패: {msg}")
            return False
    
    path = get_user_path(user_id)
    
    try:
        # 메타데이터와 함께 저장
        data = {
            "metadata": {
                "user_id": user_id,
                "created_at": None,
                "updated_at": datetime.now().isoformat(),
                "stock_count": len(portfolio_list)
            },
            "stocks": portfolio_list
        }
        
        # 기존 파일이 있으면 생성일 유지
        if os.path.exists(path):
            try:
                existing = json.load(open(path, "r", encoding="utf-8"))
                if "metadata" in existing:
                    data["metadata"]["created_at"] = existing["metadata"].get("created_at")
            except:
                pass
        
        if not data["metadata"]["created_at"]:
            data["metadata"]["created_at"] = datetime.now().isoformat()
        
        # 임시 파일에 먼저 저장 후 이동 (원자성 보장)
        temp_path = path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            _lock_file(f)
            json.dump(data, f, ensure_ascii=False, indent=4)
            _unlock_file(f)
        
        # 임시 파일을 최종 파일로 이동
        if os.path.exists(path):
            os.remove(path)
        os.rename(temp_path, path)
        
        logger.info(f"포트폴리오 저장 성공 ({user_id}): {len(portfolio_list)}개 종목")
        return True
    except Exception as e:
        logger.error(f"데이터 저장 에러 ({user_id}): {e}")
        # 임시 파일 정리
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False

# ====== CRUD 작업 함수 ======

def add_stock(user_id: str, name: str, ticker: str, quantity: float, 
              buy_price: float, buy_date: str = None) -> Tuple[bool, str]:
    """포트폴리오에 종목을 추가합니다."""
    
    if buy_date is None:
        buy_date = datetime.now().strftime("%Y-%m-%d")
    
    # 새 항목 생성
    new_entry = {
        "name": name,
        "ticker": ticker,
        "quantity": quantity,
        "buy_price": buy_price,
        "buy_date": buy_date
    }
    
    # 유효성 검사
    is_valid, msg = validate_stock_entry(new_entry)
    if not is_valid:
        logger.warning(f"종목 추가 실패: {msg}")
        return False, msg
    
    # 포트폴리오 로드
    portfolio = load_portfolio(user_id)
    
    # 중복 확인 (같은 티커가 이미 있으면 수량 합산)
    for item in portfolio:
        if item["ticker"] == ticker:
            item["quantity"] += quantity
            logger.info(f"기존 종목 수량 증가 ({user_id}, {ticker}): +{quantity}")
            success = save_portfolio(user_id, portfolio)
            return success, f"'{name}' 수량을 {quantity}개 추가했습니다." if success else "저장 실패"
    
    # 새 종목 추가
    portfolio.append(new_entry)
    success = save_portfolio(user_id, portfolio)
    return success, f"'{name}' 종목을 추가했습니다." if success else "저장 실패"

def remove_stock(user_id: str, ticker: str) -> Tuple[bool, str]:
    """포트폴리오에서 종목을 제거합니다."""
    
    portfolio = load_portfolio(user_id)
    original_count = len(portfolio)
    
    portfolio = [item for item in portfolio if item["ticker"] != ticker]
    
    if len(portfolio) == original_count:
        logger.warning(f"제거할 종목이 없습니다: {ticker}")
        return False, f"티커 '{ticker}' 종목을 찾을 수 없습니다."
    
    success = save_portfolio(user_id, portfolio)
    if success:
        logger.info(f"종목 제거 성공 ({user_id}, {ticker})")
    
    return success, f"종목을 제거했습니다." if success else "저장 실패"

def update_stock(user_id: str, ticker: str, quantity: Optional[float] = None, 
                 buy_price: Optional[float] = None) -> Tuple[bool, str]:
    """포트폴리오의 종목 정보를 수정합니다."""
    
    portfolio = load_portfolio(user_id)
    found = False
    
    for item in portfolio:
        if item["ticker"] == ticker:
            found = True
            if quantity is not None:
                if quantity <= 0:
                    return False, "수량은 0보다 커야 합니다."
                item["quantity"] = quantity
            if buy_price is not None:
                if buy_price < 0:
                    return False, "매입가는 0 이상이어야 합니다."
                item["buy_price"] = buy_price
            break
    
    if not found:
        logger.warning(f"수정할 종목이 없습니다: {ticker}")
        return False, f"티커 '{ticker}' 종목을 찾을 수 없습니다."
    
    success = save_portfolio(user_id, portfolio)
    if success:
        logger.info(f"종목 수정 성공 ({user_id}, {ticker})")
    
    return success, "종목 정보를 수정했습니다." if success else "저장 실패"

def get_stock(user_id: str, ticker: str) -> Optional[Dict]:
    """특정 종목의 정보를 조회합니다."""
    
    portfolio = load_portfolio(user_id)
    
    for item in portfolio:
        if item["ticker"] == ticker:
            return item
    
    logger.info(f"종목을 찾을 수 없습니다: {ticker}")
    return None

# ====== 포트폴리오 분석 함수 ======

def calculate_portfolio_stats(user_id: str, current_prices: Dict[str, float]) -> Dict:
    """포트폴리오의 통계를 계산합니다."""
    
    portfolio = load_portfolio(user_id)
    
    if not portfolio:
        return {
            "total_invest": 0,
            "current_value": 0,
            "profit_loss": 0,
            "profit_loss_rate": 0,
            "stock_count": 0
        }
    
    total_invest = 0  # 총 매입 금액
    current_value = 0  # 현재 평가 금액
    
    for item in portfolio:
        invest = item["quantity"] * item["buy_price"]
        total_invest += invest
        
        current_price = current_prices.get(item["ticker"], item["buy_price"])
        current = item["quantity"] * current_price
        current_value += current
    
    profit_loss = current_value - total_invest
    profit_loss_rate = (profit_loss / total_invest * 100) if total_invest > 0 else 0
    
    return {
        "total_invest": total_invest,
        "current_value": current_value,
        "profit_loss": profit_loss,
        "profit_loss_rate": profit_loss_rate,
        "stock_count": len(portfolio)
    }

def get_portfolio_composition(user_id: str, current_prices: Dict[str, float]) -> List[Dict]:
    """포트폴리오의 비중을 계산합니다."""
    
    portfolio = load_portfolio(user_id)
    composition = []
    
    total_value = 0
    for item in portfolio:
        current_price = current_prices.get(item["ticker"], item["buy_price"])
        value = item["quantity"] * current_price
        total_value += value
    
    for item in portfolio:
        current_price = current_prices.get(item["ticker"], item["buy_price"])
        value = item["quantity"] * current_price
        ratio = (value / total_value * 100) if total_value > 0 else 0
        
        composition.append({
            "name": item["name"],
            "ticker": item["ticker"],
            "quantity": item["quantity"],
            "buy_price": item["buy_price"],
            "current_price": current_price,
            "current_value": value,
            "ratio": ratio,
            "profit_loss": value - (item["quantity"] * item["buy_price"])
        })
    
    return sorted(composition, key=lambda x: x["current_value"], reverse=True)

# ====== 포트폴리오 관리 함수 ======

def clear_portfolio(user_id: str) -> Tuple[bool, str]:
    """포트폴리오를 초기화합니다 (모든 종목 제거)."""
    
    success = save_portfolio(user_id, [])
    
    if success:
        logger.info(f"포트폴리오 초기화 ({user_id})")
    
    return success, "포트폴리오를 초기화했습니다." if success else "초기화 실패"

def delete_portfolio(user_id: str) -> Tuple[bool, str]:
    """포트폴리오 파일 자체를 삭제합니다."""
    
    path = get_user_path(user_id)
    
    try:
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"포트폴리오 파일 삭제 ({user_id}): {path}")
            return True, "포트폴리오 파일을 삭제했습니다."
        else:
            return False, "포트폴리오 파일이 존재하지 않습니다."
    except Exception as e:
        logger.error(f"포트폴리오 파일 삭제 실패 ({user_id}): {e}")
        return False, f"삭제 실패: {str(e)}"

def export_portfolio(user_id: str, format: str = "json") -> Optional[str]:
    """포트폴리오를 내보냅니다."""
    
    portfolio = load_portfolio(user_id)
    
    if not portfolio:
        logger.warning(f"내보낼 포트폴리오가 없습니다 ({user_id})")
        return None
    
    try:
        if format == "json":
            return json.dumps(portfolio, ensure_ascii=False, indent=4)
        elif format == "csv":
            import csv
            from io import StringIO
            
            output = StringIO()
            if portfolio:
                writer = csv.DictWriter(output, fieldnames=portfolio[0].keys())
                writer.writeheader()
                writer.writerows(portfolio)
            
            return output.getvalue()
        else:
            logger.warning(f"지원하지 않는 형식: {format}")
            return None
    except Exception as e:
        logger.error(f"포트폴리오 내보내기 실패: {e}")
        return None

def import_portfolio(user_id: str, data: str, format: str = "json") -> Tuple[bool, str]:
    """포트폴리오를 가져옵니다."""
    
    try:
        if format == "json":
            portfolio = json.loads(data)
        else:
            logger.warning(f"지원하지 않는 형식: {format}")
            return False, f"지원하지 않는 형식입니다: {format}"
        
        if not isinstance(portfolio, list):
            return False, "유효한 포트폴리오 형식이 아닙니다."
        
        # 각 항목 검증
        for i, item in enumerate(portfolio):
            is_valid, msg = validate_stock_entry(item)
            if not is_valid:
                return False, f"항목 {i}: {msg}"
        
        success = save_portfolio(user_id, portfolio)
        
        if success:
            logger.info(f"포트폴리오 가져오기 성공 ({user_id}): {len(portfolio)}개 종목")
        
        return success, "포트폴리오를 가져왔습니다." if success else "가져오기 실패"
    except json.JSONDecodeError:
        logger.error("JSON 형식이 유효하지 않습니다.")
        return False, "유효한 JSON 형식이 아닙니다."
    except Exception as e:
        logger.error(f"포트폴리오 가져오기 실패: {e}")
        return False, f"가져오기 실패: {str(e)}"