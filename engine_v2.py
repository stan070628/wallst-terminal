"""
engine_v2.py — The Closer's Refactored Quant Engine
=====================================================
기존 engine.py의 Multi-Factor v2 로직을 클래스로 캡슐화.

변경 사항:
  - UI 의존성 제거 (no streamlit import)
  - 타입 힌트 전면 적용
  - 예외를 세 가지로 분류: DataFetchError / InsufficientDataError / AnalysisError
  - AnalysisResult dataclass로 반환값 표준화
  - FundamentalsChecker 분리 (UI와 완전 독립)
  - 순수 함수들(calculate_sharp_score 등)은 그대로 재사용 가능
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

try:
    from ta.momentum import RSIIndicator
    from ta.trend import MACD, IchimokuIndicator
    from ta.volatility import AverageTrueRange, BollingerBands
    from ta.volume import MFIIndicator, OnBalanceVolumeIndicator, VolumeWeightedAveragePrice
    _TA_AVAILABLE = True
except ImportError:
    _TA_AVAILABLE = False

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 커스텀 예외 계층
# ─────────────────────────────────────────────

class AnalysisBaseError(Exception):
    """분석 오류의 공통 기반 클래스."""


class DataFetchError(AnalysisBaseError):
    """yfinance API 호출 실패 (네트워크, API 제한 등)."""


class InsufficientDataError(AnalysisBaseError):
    """데이터 부족 (상장 폐지, 잘못된 티커 등)."""


class AnalysisError(AnalysisBaseError):
    """지표 계산 또는 채점 중 예기치 않은 오류."""


# ─────────────────────────────────────────────
# 불변 결과 객체
# ─────────────────────────────────────────────

@dataclass
class IndicatorSnapshot:
    """계산된 기술 지표의 최신값 스냅샷."""
    rsi: float
    mfi: float
    macd_diff: float
    macd_diff_pct: float
    bb_lower: float
    bb_upper: float
    ichi_a: float
    ichi_b: float
    vwap: float
    atr: float
    obv: float
    current_price: float


@dataclass
class FundamentalsResult:
    """재무제표 검증 결과."""
    penalty: float
    messages: List[str] = field(default_factory=list)
    is_exempt: bool = False   # ETF/코인은 면제


@dataclass
class AnalysisResult:
    """analyze() 반환값. 성공/실패 모두 이 타입으로 반환."""
    ticker: str
    success: bool
    score: float = 0.0
    verdict: str = ""
    current_price: float = 0.0
    stop_loss: float = 0.0
    indicators: Optional[IndicatorSnapshot] = None
    detail_info: List[Dict[str, str]] = field(default_factory=list)
    df: Optional[pd.DataFrame] = None
    error_msg: Optional[str] = None
    error_type: Optional[str] = None    # 'DataFetch' | 'InsufficientData' | 'Analysis'


# ─────────────────────────────────────────────
# 순수 함수 (Pure Functions) — 테스트 가능
# ─────────────────────────────────────────────

def score_rsi(rsi: float) -> float:
    """RSI 과매도 점수 (0~20pt)."""
    return round(max(0.0, min(20.0, (60.0 - rsi) * 0.5)), 1)


def score_mfi(mfi: float) -> float:
    """MFI 수급 점수 (0~20pt)."""
    return round(max(0.0, min(20.0, (60.0 - mfi) * 0.5)), 1)


def score_bb(curr_price: float, bb_lower: float) -> float:
    """볼린저 밴드 하단 이탈 강도 (0~15pt)."""
    if not bb_lower or bb_lower <= 0:
        return 0.0
    ratio = curr_price / bb_lower
    if ratio > 1.05:
        return 0.0
    return round(max(0.0, min(15.0, (1.05 - ratio) * 300.0)), 1)


def score_macd(macd_diff: float, macd_diff_pct: Optional[float] = None) -> float:
    """MACD 추세 방향 + 크기 점수 (0~15pt)."""
    if macd_diff <= 0:
        return 0.0
    if macd_diff_pct and macd_diff_pct > 0:
        bonus = min(8.0, macd_diff_pct * 200.0)
    else:
        bonus = min(8.0, abs(macd_diff) * 5.0)
    return round(min(15.0, 7.0 + bonus), 1)


def score_ichimoku(curr_price: float, ichi_a: Optional[float],
                   ichi_b: Optional[float]) -> float:
    """일목균형표 구름 위치 점수 (0~15pt). 데이터 없으면 중립 7.5."""
    if ichi_a is None or ichi_b is None:
        return 7.5
    cloud_top = max(ichi_a, ichi_b)
    cloud_bot = min(ichi_a, ichi_b)
    if curr_price < cloud_bot:
        base = 12.0
    elif curr_price < cloud_top:
        base = 6.0
    else:
        base = 0.0
    bonus = 3.0 if ichi_a > ichi_b else 0.0   # 상승 구름 배열
    return round(min(15.0, base + bonus), 1)


def score_vwap(curr_price: float, vwap: Optional[float]) -> float:
    """VWAP 대비 괴리율 점수 (0~15pt). 데이터 없으면 중립 7.5."""
    if not vwap or vwap <= 0:
        return 7.5
    divergence = (vwap - curr_price) / vwap
    if divergence <= 0:
        return 0.0
    return round(min(15.0, divergence * 300.0), 1)


def calculate_sharp_score(
    rsi: float,
    mfi: float,
    bb_lower: float,
    curr_price: float,
    macd_diff: float,
    ichi_a: Optional[float] = None,
    ichi_b: Optional[float] = None,
    vwap: Optional[float] = None,
    macd_diff_pct: Optional[float] = None,
) -> float:
    """
    [The Closer's Multi-Factor 채점기 v2 — 6팩터 100점]
    순수 함수: I/O 없음, 사이드 이펙트 없음.

    Factor         Max   Description
    ——————————————————————————————————
    RSI (과매도)    20pt  오실레이터 과매도 강도
    MFI (수급)      20pt  세력 자금 유입 강도
    BB  (하단 지지) 15pt  밴드 하단 이탈 심도
    MACD(추세 크기) 15pt  방향 + 크기 비례
    Ichimoku        15pt  구름 기반 독립 추세선
    VWAP (수급 구형)15pt  VWAP 괴리율
    ——————————————————————————————————
    합계            100pt
    """
    total = (
        score_rsi(rsi)
        + score_mfi(mfi)
        + score_bb(curr_price, bb_lower)
        + score_macd(macd_diff, macd_diff_pct)
        + score_ichimoku(curr_price, ichi_a, ichi_b)
        + score_vwap(curr_price, vwap)
    )
    return round(min(100.0, max(0.0, total)), 1)


# ─────────────────────────────────────────────
# 재무제표 검증기 (독립 클래스)
# ─────────────────────────────────────────────

class FundamentalsChecker:
    """
    재무제표 X-Ray. UI 코드에 의존하지 않으며 단독 테스트 가능.
    """

    EXEMPT_QUOTE_TYPES = {"ETF", "MUTUALFUND", "CRYPTOCURRENCY"}

    def check(self, ticker_obj: yf.Ticker) -> FundamentalsResult:
        try:
            info = ticker_obj.info
        except Exception as exc:
            return FundamentalsResult(
                penalty=0.0,
                messages=["⚠️ 재무 데이터 수신 불가 (정보 누락)"],
            )

        # ETF/펀드/코인 면제
        quote_type = info.get("quoteType", "")
        short_name = info.get("shortName", "")
        if quote_type in self.EXEMPT_QUOTE_TYPES or "ETF" in short_name:
            return FundamentalsResult(
                penalty=0.0,
                messages=["💡 ETF/펀드/암호화폐 — 재무 검증 면제"],
                is_exempt=True,
            )

        penalty = 0.0
        messages: List[str] = []

        # 1. 시가총액
        market_cap: int = info.get("marketCap", 0) or 0
        ticker_sym: str = getattr(ticker_obj, "ticker", "").upper()
        is_korean = ticker_sym.endswith(".KS") or ticker_sym.endswith(".KQ")

        if market_cap > 0:
            if is_korean and market_cap < 30_000_000_000:
                penalty += 25.0
                messages.append(
                    f"🚨 시가총액 {market_cap / 1e8:.0f}억원 — 300억 미달 (-25점)"
                )
            elif not is_korean and market_cap < 200_000_000:
                penalty += 25.0
                messages.append(
                    f"🚨 시가총액 ${market_cap / 1e6:.0f}M — $200M 미달 (-25점)"
                )

        # 2. EPS / 성장주 예외
        eps: Optional[float] = info.get("trailingEps")
        revenue_growth: float = info.get("revenueGrowth") or 0.0

        if eps is not None and eps < 0:
            if revenue_growth > 0.20:
                messages.append(
                    f"💡 성장주 예외 — 매출성장 {revenue_growth * 100:.0f}%↑ EPS 패널티 면제"
                )
            else:
                penalty += 20.0
                messages.append("⚠️ 지속 적자 (EPS<0) — -20점")

        # 3. 부채비율 (금융업 예외)
        debt_equity: Optional[float] = info.get("debtToEquity")
        industry: str = info.get("industry", "").lower()
        sector: str = info.get("sector", "").lower()
        is_financial = any(
            kw in industry or kw in sector
            for kw in ("bank", "financial", "insurance")
        )

        if debt_equity is not None and debt_equity > 200:
            if is_financial:
                messages.append("💡 금융업종 — 부채비율 패널티 면제")
            else:
                penalty += 10.0
                messages.append("⚠️ 부채비율 200% 초과 — -10점")

        if penalty == 0.0 and not messages:
            messages.append("✅ 펀더멘털 양호")

        return FundamentalsResult(penalty=penalty, messages=messages)


# ─────────────────────────────────────────────
# 데이터 수집 계층
# ─────────────────────────────────────────────

class DataClient:
    """
    yfinance 래퍼. 나중에 다른 provider(FinanceDataReader 등)로 교체 가능.
    """

    MIN_ROWS = 30

    def fetch(self, ticker: str, period: str = "6mo") -> pd.DataFrame:
        """
        데이터를 가져오고, 표준 컬럼명 / ffill / Volume 보정까지 완료한 DataFrame 반환.

        Raises:
            DataFetchError: API 호출 자체가 실패한 경우.
            InsufficientDataError: 데이터가 MIN_ROWS 미만인 경우.
        """
        try:
            stock = yf.Ticker(ticker)
            df = self._try_download(stock, period)
        except (DataFetchError, InsufficientDataError):
            raise
        except Exception as exc:
            raise DataFetchError(
                f"[{ticker}] yfinance 호출 중 예외 발생: {exc}"
            ) from exc

        return self._clean(df, ticker)

    # ── 내부 헬퍼 ──────────────────────────────

    def _try_download(self, stock: yf.Ticker, period: str) -> pd.DataFrame:
        """다양한 auto_adjust 설정과 복수의 기간(period)을 순서대로 시도."""
        attempts = [period, "1y", "2y"]
        for p in attempts:
            for auto_adj in (False, True):
                try:
                    df = stock.history(period=p, auto_adjust=auto_adj)
                    if df is not None and not df.empty and len(df) >= self.MIN_ROWS:
                        return df
                except Exception:
                    continue

        raise InsufficientDataError(
            f"[{stock.ticker}] {self.MIN_ROWS}행 이상 데이터를 수집할 수 없음 "
            f"(상장폐지 또는 잘못된 티커 가능성)"
        )

    def _clean(self, df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """컬럼 표준화, ffill, Volume=0 보정."""
        df.columns = [str(c).capitalize() for c in df.columns]
        df = df.ffill().dropna()

        if df.empty:
            raise InsufficientDataError(
                f"[{ticker}] ffill 후 데이터 없음 (NaN 과다)"
            )

        if "Volume" in df.columns:
            df["Volume"] = df["Volume"].replace(0, 1)

        return df


# ─────────────────────────────────────────────
# 지표 계산 계층
# ─────────────────────────────────────────────

class IndicatorEngine:
    """
    순수 기술 지표 계산. DataFrame을 받아 IndicatorSnapshot을 반환.
    ta 라이브러리 없이도 폴백 값으로 동작.
    """

    def compute(self, df: pd.DataFrame, curr_price: float) -> Tuple[IndicatorSnapshot, pd.DataFrame]:
        """
        Returns:
            snapshot: 최신 값만 담긴 IndicatorSnapshot
            df:       모든 지표 컬럼이 추가된 DataFrame (차트용)
        """
        close  = df["Close"].astype(float)
        high   = df["High"].astype(float)
        low    = df["Low"].astype(float)
        volume = df["Volume"].astype(float)

        rsi_s    = self._rsi(close)
        mfi_s    = self._mfi(high, low, close, volume)
        bb_lo, bb_hi = self._bb(close)
        macd_line, macd_sig, macd_diff_s = self._macd(close)
        ichi_a_s, ichi_b_s = self._ichimoku(high, low)
        vwap_s   = self._vwap(high, low, close, volume)
        obv_s    = self._obv(close, volume)
        atr_s    = self._atr(high, low, close)

        # DataFrame에 지표 컬럼 추가 (차트용)
        df = df.copy()
        df["rsi"]      = rsi_s
        df["mfi"]      = mfi_s
        df["bb_lower"] = bb_lo
        df["bb_upper"] = bb_hi
        df["macd"]     = macd_line
        df["macd_sig"] = macd_sig
        df["macd_diff"]= macd_diff_s
        df["ichi_a"]   = ichi_a_s
        df["ichi_b"]   = ichi_b_s
        df["vwap"]     = vwap_s
        df["obv"]      = obv_s
        df["atr"]      = atr_s

        macd_diff_val = float(macd_diff_s.iloc[-1])
        macd_diff_pct = abs(macd_diff_val) / curr_price * 100.0 if curr_price > 0 else 0.0

        snap = IndicatorSnapshot(
            rsi          = float(rsi_s.iloc[-1]),
            mfi          = float(mfi_s.iloc[-1]),
            macd_diff    = macd_diff_val,
            macd_diff_pct= macd_diff_pct,
            bb_lower     = float(bb_lo.iloc[-1]),
            bb_upper     = float(bb_hi.iloc[-1]),
            ichi_a       = float(ichi_a_s.iloc[-1]),
            ichi_b       = float(ichi_b_s.iloc[-1]),
            vwap         = float(vwap_s.iloc[-1]),
            atr          = float(atr_s.iloc[-1]),
            obv          = float(obv_s.iloc[-1]),
            current_price= curr_price,
        )
        return snap, df

    # ── 각 지표 헬퍼 (ta 없으면 수동 계산 또는 폴백) ──

    def _rsi(self, close: pd.Series) -> pd.Series:
        if _TA_AVAILABLE:
            try:
                return RSIIndicator(close=close, window=14).rsi()
            except Exception:
                pass
        delta = close.diff()
        gain  = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss  = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        rs    = gain / (loss + 1e-9)
        return pd.Series(100 - (100 / (1 + rs)), index=close.index).fillna(50.0)

    def _mfi(self, high: pd.Series, low: pd.Series,
             close: pd.Series, volume: pd.Series) -> pd.Series:
        if _TA_AVAILABLE:
            try:
                return MFIIndicator(high=high, low=low, close=close,
                                    volume=volume, window=14).money_flow_index()
            except Exception:
                pass
        return pd.Series(50.0, index=close.index)

    def _bb(self, close: pd.Series) -> Tuple[pd.Series, pd.Series]:
        if _TA_AVAILABLE:
            try:
                bb = BollingerBands(close=close, window=20, window_dev=2)
                return bb.bollinger_lband(), bb.bollinger_hband()
            except Exception:
                pass
        return close.copy(), close.copy()

    def _macd(self, close: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        if _TA_AVAILABLE:
            try:
                m = MACD(close=close, window_fast=12, window_slow=26, window_sign=9)
                return m.macd(), m.macd_signal(), m.macd_diff()
            except Exception:
                pass
        zero = pd.Series(0.0, index=close.index)
        return zero, zero, zero

    def _ichimoku(self, high: pd.Series, low: pd.Series) -> Tuple[pd.Series, pd.Series]:
        if _TA_AVAILABLE:
            try:
                ichi = IchimokuIndicator(high=high, low=low, window1=9, window2=26, window3=52)
                return ichi.ichimoku_a(), ichi.ichimoku_b()
            except Exception:
                pass
        mid = (high + low) / 2
        return mid.copy(), mid.copy()

    def _vwap(self, high: pd.Series, low: pd.Series,
              close: pd.Series, volume: pd.Series) -> pd.Series:
        if _TA_AVAILABLE:
            try:
                return VolumeWeightedAveragePrice(
                    high=high, low=low, close=close, volume=volume, window=20
                ).volume_weighted_average_price()
            except Exception:
                pass
        return close.copy()

    def _obv(self, close: pd.Series, volume: pd.Series) -> pd.Series:
        if _TA_AVAILABLE:
            try:
                return OnBalanceVolumeIndicator(close=close, volume=volume).on_balance_volume()
            except Exception:
                pass
        return pd.Series(range(len(close)), index=close.index, dtype=float)

    def _atr(self, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        if _TA_AVAILABLE:
            try:
                return AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range()
            except Exception:
                pass
        return pd.Series(float(high.iloc[-1] - low.iloc[-1]), index=close.index)


# ─────────────────────────────────────────────
# 통합 분석기 (Facade)
# ─────────────────────────────────────────────

class StockAnalyzer:
    """
    단일 진입점. UI(Streamlit)에서 직접 호출하거나 CLI/스케줄러에서도 사용 가능.

    사용 예::

        from engine_v2 import StockAnalyzer

        result = StockAnalyzer("005930.KS").analyze(apply_fundamental=True)
        if result.success:
            print(result.score, result.verdict)
        else:
            print(result.error_type, result.error_msg)
    """

    def __init__(
        self,
        ticker: str,
        data_client: Optional[DataClient] = None,
        indicator_engine: Optional[IndicatorEngine] = None,
        fundamentals_checker: Optional[FundamentalsChecker] = None,
    ) -> None:
        if not ticker or not ticker.strip():
            raise ValueError("ticker 심볼은 비어 있을 수 없습니다.")
        self.ticker = ticker.strip().upper()
        self._client    = data_client or DataClient()
        self._ind_eng   = indicator_engine or IndicatorEngine()
        self._fund_chk  = fundamentals_checker or FundamentalsChecker()

    # ── Public API ───────────────────────────────

    def analyze(
        self,
        period: str = "6mo",
        apply_fundamental: bool = False,
    ) -> AnalysisResult:
        """
        전체 분석 파이프라인.
        실패해도 예외를 던지지 않고 success=False인 AnalysisResult를 반환.
        """
        try:
            df = self._client.fetch(self.ticker, period)

            curr_price = self._get_live_price(df)
            snap, df   = self._ind_eng.compute(df, curr_price)

            tech_score = calculate_sharp_score(
                rsi          = snap.rsi,
                mfi          = snap.mfi,
                bb_lower     = snap.bb_lower,
                curr_price   = snap.current_price,
                macd_diff    = snap.macd_diff,
                ichi_a       = snap.ichi_a,
                ichi_b       = snap.ichi_b,
                vwap         = snap.vwap,
                macd_diff_pct= snap.macd_diff_pct,
            )

            fund_result = FundamentalsResult(penalty=0.0)
            if apply_fundamental:
                fund_result = self._fund_chk.check(yf.Ticker(self.ticker))

            final_score = round(
                max(0.0, min(100.0, tech_score - fund_result.penalty)), 1
            )

            verdict    = self._verdict_label(final_score)
            stop_loss  = self._dynamic_stop(curr_price, snap.atr)
            detail     = self._build_detail(snap, curr_price, df, fund_result, final_score)

            return AnalysisResult(
                ticker        = self.ticker,
                success       = True,
                score         = final_score,
                verdict       = verdict,
                current_price = curr_price,
                stop_loss     = stop_loss,
                indicators    = snap,
                detail_info   = detail,
                df            = df,
            )

        except InsufficientDataError as exc:
            logger.warning("[%s] InsufficientDataError: %s", self.ticker, exc)
            return self._error_result("InsufficientData", str(exc))

        except DataFetchError as exc:
            logger.error("[%s] DataFetchError: %s", self.ticker, exc)
            return self._error_result("DataFetch", str(exc))

        except Exception as exc:
            logger.exception("[%s] 예기치 않은 분석 오류", self.ticker)
            return self._error_result("Analysis", str(exc))

    # ── 내부 헬퍼 ──────────────────────────────

    def _get_live_price(self, df: pd.DataFrame) -> float:
        """fast_info로 실시간 현재가를 시도하고, 실패 시 종가를 사용."""
        base = float(df["Close"].iloc[-1])
        try:
            live = yf.Ticker(self.ticker).fast_info.last_price
            if live and live > 0:
                return float(live)
        except Exception:
            pass
        return base

    @staticmethod
    def _verdict_label(score: float) -> str:
        if score >= 80:
            return "💎 [천재지변급 기회 - 분할 매수 즉시]"
        if score >= 50:
            return "✅ [애매한 반등 - 정찰병만 투입]"
        if score >= 30:
            return "⚠️ [추세 하락 - 관망]"
        return "🛑 [폭락/인버스 - 도망]"

    @staticmethod
    def _dynamic_stop(curr_price: float, atr: float) -> float:
        """2×ATR 동적 손절선 (하드 플로어 -15%)."""
        if atr > 0:
            stop = curr_price - 2.0 * atr
            return round(max(stop, curr_price * 0.85), 2)
        return round(curr_price * 0.90, 2)

    def _build_detail(
        self,
        snap: IndicatorSnapshot,
        curr_price: float,
        df: pd.DataFrame,
        fund_result: FundamentalsResult,
        final_score: float,
    ) -> List[Dict[str, str]]:
        """detail_info 리스트 생성 (기존 engine.py와 동일한 구조)."""
        detail: List[Dict[str, str]] = [
            {
                "title": "🌡️ RSI (엔진 온도)",
                "full_comment": (
                    f"{snap.rsi:.1f} "
                    f"{'(과매도)' if snap.rsi < 30 else '(정상)' if snap.rsi < 70 else '(과매수)'}"
                ),
            },
            {
                "title": "💰 MFI (자금 흐름)",
                "full_comment": (
                    f"{snap.mfi:.1f} "
                    f"{'(약세)' if snap.mfi < 30 else '(중립)' if snap.mfi < 70 else '(강세)'}"
                ),
            },
            {
                "title": "📊 MACD (추세 신호)",
                "full_comment": (
                    "반전 신호 (+)" if snap.macd_diff > 0 else "하락 지속 (-)"
                ),
            },
            {
                "title": "📈 일목균형표 (Ichimoku)",
                "full_comment": (
                    f"클라우드: {'상승 흐름' if snap.ichi_a > snap.ichi_b else '하락 흐름'}"
                ),
            },
            {
                "title": "💎 볼린저 밴드 (변동성)",
                "full_comment": (
                    f"현재가 "
                    f"{'하단 근처' if curr_price <= snap.bb_lower else '상단 근처' if curr_price >= snap.bb_upper else '중간권역'}"
                ),
            },
            {
                "title": "🎯 ATR (동적 손절선)",
                "full_comment": (
                    f"ATR={snap.atr:.2f} → 손절선: "
                    f"{self._dynamic_stop(curr_price, snap.atr):,.1f}"
                ),
            },
            {
                "title": "🌊 VWAP (거래량 가중)",
                "full_comment": (
                    "VWAP 상향 돌파" if curr_price > snap.vwap else "VWAP 하향 이탈"
                ),
            },
        ]

        if fund_result.penalty > 0 or fund_result.messages:
            detail.append({
                "title": "🏢 펀더멘털 검증",
                "full_comment": " / ".join(fund_result.messages),
            })

        # The Closer 종합 의견 (engine.py의 get_closer_verdict_and_comment 내용)
        action, briefing = self._closer_verdict(final_score, snap, curr_price, fund_result)
        detail.append({"title": "🎯 The Closer's 실시간 의견", "full_comment": f"{action}\n\n{briefing}"})

        return detail

    def _closer_verdict(
        self,
        final_score: float,
        snap: IndicatorSnapshot,
        curr_price: float,
        fund_result: FundamentalsResult,
    ) -> Tuple[str, str]:
        """점수 해부 + Action 판정 문자열 생성."""
        r_sc  = score_rsi(snap.rsi)
        m_sc  = score_mfi(snap.mfi)
        b_sc  = score_bb(curr_price, snap.bb_lower)
        mac_sc= score_macd(snap.macd_diff, snap.macd_diff_pct)
        i_sc  = score_ichimoku(curr_price, snap.ichi_a, snap.ichi_b)
        v_sc  = score_vwap(curr_price, snap.vwap)

        if final_score >= 70:
            action   = "🟢 [적극 매수 (BUY)]"
            briefing = "완벽한 과매도 바닥 구간과 추세 반전이 교집합을 이뤘습니다. 철저한 분할 매수로 물량을 확보하십시오."
        elif final_score <= 30:
            action   = "🔴 [매도 및 회피 (SELL)]"
            briefing = "수급이 완전히 이탈했거나 고점 과열 상태입니다. 보유자는 즉각 비중을 축소하십시오."
        else:
            action   = "🟡 [보류 및 관망 (HOLD)]"
            briefing = "방향성을 상실한 혼조세 구간입니다. 확실한 타점(70점 이상)이 나올 때까지 관망하십시오."

        stop_line = ""
        if snap.atr > 0:
            ds = self._dynamic_stop(curr_price, snap.atr)
            pct = abs((ds - curr_price) / curr_price * 100) if curr_price > 0 else 0
            stop_line = f"  \n🛡️ **ATR 동적 손절선**: **{ds:,.1f}** ({pct:.1f}% below)"

        body  = "📊 **[Multi-Factor 총점 해부]**  \n"
        body += f"▪️ RSI (과매도): +{r_sc}점 / 20점  \n"
        body += f"▪️ MFI (세력 자금): +{m_sc}점 / 20점  \n"
        body += f"▪️ BB (하단 지지): +{b_sc}점 / 15점  \n"
        body += f"▪️ MACD (추세 크기): +{mac_sc}점 / 15점  \n"
        body += f"▪️ Ichimoku (구름): +{i_sc}점 / 15점  \n"
        body += f"▪️ VWAP (수급): +{v_sc}점 / 15점"

        if fund_result.penalty > 0:
            body += f"  \n🚨 재무 패널티: -{fund_result.penalty}점"

        body += stop_line
        body += f"\n\n💡 {briefing}"

        return action, body

    def _error_result(self, error_type: str, msg: str) -> AnalysisResult:
        return AnalysisResult(
            ticker     = self.ticker,
            success    = False,
            error_type = error_type,
            error_msg  = msg,
        )
