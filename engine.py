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
    is_waterfall: bool = False,         # [The Closer] 폭포수 여부
    is_rsi_hook_failed: bool = False,   # [The Closer] RSI 훅 실패 여부
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

    [The Closer's Penalty Logic]
    - is_waterfall=True       -> Score capped at 29.0
    - is_rsi_hook_failed=True -> Score capped at 29.0
    """
    total = (
        score_rsi(rsi)
        + score_mfi(mfi)
        + score_bb(curr_price, bb_lower)
        + score_macd(macd_diff, macd_diff_pct)
        + score_ichimoku(curr_price, ichi_a, ichi_b)
        + score_vwap(curr_price, vwap)
    )
    final_score = round(min(100.0, max(0.0, total)), 1)

    # 🚨 [The Closer's 폭포수 회피 필터 작동]
    if is_waterfall:
        final_score = min(final_score, 29.0)

    # 🚨 [The Closer's RSI 턴어라운드(Hook) 필터 작동]
    # 바닥권인데 고개를 들지 않고 계속 처박고 있다면 떨어지는 칼날입니다.
    if is_rsi_hook_failed:
        final_score = min(final_score, 29.0)

    return final_score


def calculate_trend_score(
    rsi: float,
    mfi: float,
    bb_upper: float,
    curr_price: float,
    macd_diff: float,
    ichi_a: Optional[float] = None,
    ichi_b: Optional[float] = None,
    vwap: Optional[float] = None,
    is_waterfall: bool = False,
) -> float:
    """
    [Mode: Trend Following / Breakout]
    추세 추종 모드 채점기. 기존 로직과 정반대로 작동합니다.
    강한 상승 모멘텀(RSI 60+, 밴드 상단 돌파)에 높은 점수를 부여합니다.
    """
    score = 0.0

    # 1. RSI (모멘텀): 50~75 구간이 베스트, 75 이상은 초강세 유지
    if 50 <= rsi <= 75:
        score += 20.0 * ((rsi - 50) / 25)  # 50->0점, 75->20점
    elif rsi > 75:
        score += 20.0  # 초강세 유지

    # 2. MFI (자금 유입): 50 이상일 때 가점
    if mfi >= 50:
        score += min(20.0, (mfi - 50) * 0.8)

    # 3. BB (상단 돌파): 현재가가 상단 밴드 근처거나 뚫었을 때
    if bb_upper > 0:
        ratio = curr_price / bb_upper
        if ratio >= 0.98:  # 상단 2% 근접부터 만점
            score += 15.0
        else:
            score += max(0.0, (ratio - 0.90) * 150)  # 0.90~0.98 구간 점수

    # 4. MACD (추세 강도): 양수일 때만 점수
    if macd_diff > 0:
        score += 15.0

    # 5. Ichimoku (정배열): 구름 위에 있을 때
    cloud_top = max(ichi_a, ichi_b) if (ichi_a and ichi_b) else 0
    if cloud_top > 0 and curr_price > cloud_top:
        score += 15.0
        if ichi_a and ichi_b and ichi_a > ichi_b:  # 양운(상승구름)이면 보너스
            score += 5.0

    # 6. VWAP (지지): VWAP 위에 놀아야 함
    if vwap and curr_price > vwap:
        score += 15.0

    final_score = round(min(100.0, score), 1)

    # 🚨 추세 추종 필터: 역배열(폭포수)에서는 돌파 매매 금지 (가짜 반등 확률 높음)
    if is_waterfall:
        final_score = min(final_score, 40.0)

    return final_score


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
    yfinance 래퍼. 데이터 수집 실패를 최소화하도록 개조됨.
    """

    # 🚨 최소 행 수를 10으로 낮춰 데이터 누락 시에도 분석을 강행
    MIN_ROWS = 10

    def fetch(self, ticker: str, period: str = "6mo") -> pd.DataFrame:
        try:
            stock = yf.Ticker(ticker)
            df = self._try_download(stock, period)
        except Exception as exc:
            # 🚨 실패 시 None을 던지지 말고 구체적인 에러를 찍어 리스트에서 확인하게 함
            raise DataFetchError(f"[{ticker}] 수집 실패: {str(exc)[:20]}")

        return self._clean(df, ticker)

    # ── 내부 헬퍼 ──────────────────────────────

    def _try_download(self, stock: yf.Ticker, period: str) -> pd.DataFrame:
        """데이터 확보를 위해 시도 횟수를 늘리고 기간을 유연하게 조정."""
        # 'max'와 '1mo'를 추가하여 어떻게든 데이터를 긁어옴
        attempts = [period, "1y", "2y", "max", "1mo"]
        for p in attempts:
            for auto_adj in (False, True):
                try:
                    df = stock.history(period=p, auto_adjust=auto_adj)
                    if df is not None and not df.empty and len(df) >= self.MIN_ROWS:
                        return df
                except:
                    continue

        raise InsufficientDataError(f"데이터 전멸 (최소 {self.MIN_ROWS}행 미달)")

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
        strategy: str = "mean_reversion",  # 'mean_reversion' (저점매수) or 'trend' (돌파매매)
    ) -> AnalysisResult:
        """
        전체 분석 파이프라인.
        실패해도 예외를 던지지 않고 success=False인 AnalysisResult를 반환.
        
        Args:
            strategy: 'mean_reversion' (역추세/저점매수) or 'trend' (추세추종/돌파매매)
        """
        try:
            df = self._client.fetch(self.ticker, period)

            curr_price = self._get_live_price(df)
            snap, df   = self._ind_eng.compute(df, curr_price)

            # --- [추가된 필터 로직] ---
            # Waterfall (120일선) 체크
            is_waterfall = False
            if len(df) >= 20:
                ma_long = df['Close'].rolling(window=min(len(df), 120)).mean()
                if ma_long.iloc[-1] < ma_long.iloc[-min(len(ma_long), 20)]:
                    is_waterfall = True

            # RSI Hook (저점매수용) 체크
            is_rsi_hook_failed = False
            if strategy == "mean_reversion":
                if snap.rsi <= 40 and len(df) >= 2:
                    if df['rsi'].iloc[-1] <= df['rsi'].iloc[-2]:
                        is_rsi_hook_failed = True
            # -----------------------

            # 🎯 전략에 따른 점수 계산 분기
            if strategy == "trend":
                tech_score = calculate_trend_score(
                    rsi=snap.rsi, mfi=snap.mfi, bb_upper=snap.bb_upper,
                    curr_price=curr_price, macd_diff=snap.macd_diff,
                    ichi_a=snap.ichi_a, ichi_b=snap.ichi_b, vwap=snap.vwap,
                    is_waterfall=is_waterfall
                )
            else:
                # 기존 역추세(Mean Reversion) 로직
                tech_score = calculate_sharp_score(
                    rsi=snap.rsi, mfi=snap.mfi, bb_lower=snap.bb_lower,
                    curr_price=curr_price, macd_diff=snap.macd_diff,
                    ichi_a=snap.ichi_a, ichi_b=snap.ichi_b, vwap=snap.vwap,
                    macd_diff_pct=snap.macd_diff_pct,
                    is_waterfall=is_waterfall,
                    is_rsi_hook_failed=is_rsi_hook_failed
                )

            fund_result = FundamentalsResult(penalty=0.0)
            if apply_fundamental:
                fund_result = self._fund_chk.check(yf.Ticker(self.ticker))

            final_score = round(
                max(0.0, min(100.0, tech_score - fund_result.penalty)), 1
            )

            # 전략 정보를 포함한 상세 분석
            verdict, detail = self._build_detail_v2(
                snap, curr_price, df, fund_result, final_score,
                strategy, is_waterfall, is_rsi_hook_failed
            )
            stop_loss  = self._dynamic_stop(curr_price, snap.atr)

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

    def _build_detail_v2(
        self,
        snap: IndicatorSnapshot,
        curr_price: float,
        df: pd.DataFrame,
        fund_result: FundamentalsResult,
        final_score: float,
        strategy: str,
        is_waterfall: bool,
        is_rsi_hook_failed: bool,
    ) -> Tuple[str, List[Dict[str, str]]]:
        """
        전략(strategy)에 따라 다른 해석을 제공하는 상세 분석 생성.
        Returns: (verdict_label, detail_list)
        """
        # 1. 기본 지표 카드 생성
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

        # 폭포수/RSI Hook 필터 카드
        detail.append({
            "title": "📉 장기 추세 (120일선)",
            "full_comment": (
                "🚨 위험 — 폭포수 하락 중 (120일선 역배열)"
                if is_waterfall else
                "✅ 안전 — 추세 지지 또는 상승 중"
            ),
        })

        if strategy == "mean_reversion":
            detail.append({
                "title": "🪝 RSI 턴어라운드 (Hook)",
                "full_comment": (
                    "🚨 턴어라운드 실패 — RSI가 계속 하향 중 (떨어지는 칼날, 관망 필수)"
                    if is_rsi_hook_failed else
                    "✅ 턴어라운드 성공 또는 해당 없음 (안전)"
                ),
            })

        # 펀더멘털 카드
        if fund_result.penalty > 0 or fund_result.messages:
            detail.append({
                "title": "🏢 펀더멘털 검증",
                "full_comment": " / ".join(fund_result.messages),
            })

        # 2. 종합 의견 생성 (전략별 분기)
        action_label = ""
        briefing = ""

        # [A] 역추세(Mean Reversion) 전략일 때 코멘트
        if strategy == "mean_reversion":
            if is_waterfall:
                action_label = "🔴 [절대 매수 금지 (AVOID)]"
                briefing = "120일선 아래로 꺾인 '폭포수 차트'입니다. 저점인 줄 알았으나 지하실이 있을 수 있습니다."
            elif is_rsi_hook_failed:
                action_label = "🟡 [관망 (Falling Knife)]"
                briefing = "과매도 구간이지만 브레이크가 걸리지 않았습니다. RSI가 고개를 드는(Hook) 것을 확인하고 들어가십시오."
            elif final_score >= 70:
                action_label = "🟢 [적극 매수 (BUY)]"
                briefing = "과매도 + 지지선 도달 + 추세 반전 시그널이 겹쳤습니다. 기술적 반등이 임박했습니다."
            elif final_score <= 30:
                # 🚨 점수가 낮은 이유를 구분
                if snap.rsi >= 65:
                    action_label = "🟠 [과열 경고 (Overheated)]"
                    briefing = "현재가는 강력한 상승세(RSI 과열)로 인해 본 엔진(저점매수형)의 타점이 아닙니다. 보유자의 영역이며, 신규 진입 시 고점 물림에 주의하십시오."
                else:
                    action_label = "⚪ [중립/모멘텀 부재]"
                    briefing = "뚜렷한 과매도 신호도, 상승 신호도 없는 애매한 구간입니다."
            else:
                action_label = "🟡 [관망 (HOLD)]"
                briefing = "매수 근거가 부족합니다. 확실한 과매도 시그널(70점 이상)을 기다리십시오."

        # [B] 추세추종(Trend) 전략일 때 코멘트
        else:
            if is_waterfall:
                action_label = "🔴 [가짜 반등 주의 (Fakeout)]"
                briefing = "단기 반등이 나왔으나 장기 추세(120일선)는 하락 중입니다. 돌파 매매 실패 확률이 높습니다."
            elif final_score >= 75:
                action_label = "🚀 [강력 돌파 (Strong Buy)]"
                briefing = "RSI와 수급이 살아있고 밴드 상단을 뚫는 강력한 모멘텀이 발생했습니다. 추세에 편승하십시오."
            elif final_score <= 40:
                action_label = "💤 [추세 소멸 (No Trend)]"
                briefing = "상승 모멘텀이 약하거나 횡보 중입니다. 돌파 매매를 시도하기에 에너지가 부족합니다."
            else:
                action_label = "🟡 [추세 관찰 (Watch)]"
                briefing = "상승 흐름은 있으나 폭발적인 시세 분출 전입니다. 거래량 실린 돌파를 기다리십시오."

        # 점수 해부
        if strategy == "mean_reversion":
            r_sc = score_rsi(snap.rsi)
            m_sc = score_mfi(snap.mfi)
            b_sc = score_bb(curr_price, snap.bb_lower)
            mac_sc = score_macd(snap.macd_diff, snap.macd_diff_pct)
            i_sc = score_ichimoku(curr_price, snap.ichi_a, snap.ichi_b)
            v_sc = score_vwap(curr_price, snap.vwap)
            score_breakdown = (
                f"📊 **[역추세(저점매수) 총점 해부]**  \n"
                f"▪️ RSI (과매도): +{r_sc}점 / 20점  \n"
                f"▪️ MFI (세력 자금): +{m_sc}점 / 20점  \n"
                f"▪️ BB (하단 지지): +{b_sc}점 / 15점  \n"
                f"▪️ MACD (추세 크기): +{mac_sc}점 / 15점  \n"
                f"▪️ Ichimoku (구름): +{i_sc}점 / 15점  \n"
                f"▪️ VWAP (수급): +{v_sc}점 / 15점"
            )
        else:
            score_breakdown = (
                f"📊 **[추세추종(돌파매매) 총점 해부]**  \n"
                f"▪️ RSI 모멘텀(50~75): {'✅' if 50 <= snap.rsi <= 75 else '⚡' if snap.rsi > 75 else '❌'}\n"
                f"▪️ MFI 유입(50+): {'✅' if snap.mfi >= 50 else '❌'}\n"
                f"▪️ BB 상단 돌파: {'✅' if curr_price >= snap.bb_upper * 0.98 else '❌'}\n"
                f"▪️ MACD 양수: {'✅' if snap.macd_diff > 0 else '❌'}\n"
                f"▪️ 구름 위 위치: {'✅' if curr_price > max(snap.ichi_a, snap.ichi_b) else '❌'}\n"
                f"▪️ VWAP 지지: {'✅' if curr_price > snap.vwap else '❌'}"
            )

        # 최종 조립
        strategy_label = "📉 역추세(저점잡기)" if strategy == "mean_reversion" else "📈 추세추종(돌파매매)"
        full_comment = f"**전략 모드: {strategy_label}**\n\n"
        full_comment += f"**{action_label}**\n\n"
        full_comment += score_breakdown

        if fund_result.penalty > 0:
            full_comment += f"  \n🚨 **재무 리스크**: -{fund_result.penalty}점 감점 요인 있음"

        if is_waterfall:
            full_comment += f"  \n🚨 **폭포수 필터**: 장기 120일선 역배열"
        if is_rsi_hook_failed and strategy == "mean_reversion":
            full_comment += f"  \n🪝 **RSI Hook 필터**: 턴어라운드 실패"

        # ATR 손절선
        if snap.atr > 0:
            ds = self._dynamic_stop(curr_price, snap.atr)
            pct = abs((ds - curr_price) / curr_price * 100) if curr_price > 0 else 0
            full_comment += f"  \n🛡️ **ATR 동적 손절선**: **{ds:,.1f}** ({pct:.1f}% below)"

        full_comment += f"\n\n💡 **[The Closer's 분석]**  \n{briefing}"

        # Detail 리스트에 최종 의견 추가
        detail.append({
            "title": "🎯 The Closer's 실시간 의견",
            "full_comment": full_comment,
        })

        return action_label, detail

    def _error_result(self, error_type: str, msg: str) -> AnalysisResult:
        return AnalysisResult(
            ticker     = self.ticker,
            success    = False,
            error_type = error_type,
            error_msg  = msg,
        )

# ─────────────────────────────────────────────
# [Legacy Support] 기존 engine.py 호환 함수
# ─────────────────────────────────────────────

def analyze_stock(ticker: str, period: str = "1y", apply_fundamental: bool = False) -> Tuple[pd.DataFrame, float, str, List[Dict], float]:
    """
    기존 engine.py 호환 래퍼 — **절대 None을 반환하지 않음**.
    데이터 수집 실패 시에도 빈 DataFrame + 0점을 반환하여
    호출부가 "이 종목은 데이터가 꼬였다"는 것을 인지할 수 있게 합니다.
    """
    try:
        # 1. 데이터 가져오기 (실패 시 0점 반환, None 반환 금지)
        client = DataClient()
        try:
            df = client.fetch(ticker, period)
        except Exception as fetch_err:
            return pd.DataFrame(), 0.0, f"🔴 데이터 수집 실패 ({str(fetch_err)[:30]})", [], 0.0
        
        # 2. 현재가 계산
        if df.empty:
            return pd.DataFrame(), 0.0, "🔴 데이터 없음", [], 0.0
        curr_price = float(df['Close'].iloc[-1])
        
        # 3. 지표 계산
        ind_eng = IndicatorEngine()
        snap, df_ind = ind_eng.compute(df, curr_price)
        
        # 4. [The Closer] 추가 필터 로직 (Waterfall & RSI Hook)
        # 4-1. Waterfall — 120일선이 없으면 50일이라도 체크 (데이터 부족해도 죽이지 않음)
        is_waterfall = False
        if len(df_ind) >= 50:
            window = min(len(df_ind), 120)
            ma_long = df_ind['Close'].rolling(window=window).mean()
            lookback = min(len(ma_long), 20)
            if ma_long.iloc[-1] < ma_long.iloc[-lookback]:
                is_waterfall = True
        
        # 4-2. RSI Hook Check
        # RSI가 40 이하인 과매도 구간에서 전일 대비 상승하지 못했으면 "Hook Failed"
        is_rsi_hook_failed = False
        rsi_series = df_ind['rsi']
        if len(rsi_series) >= 2:
            rsi_curr = rsi_series.iloc[-1]
            rsi_prev = rsi_series.iloc[-2]
            if rsi_curr <= 40 and rsi_curr <= rsi_prev:
                 is_rsi_hook_failed = True

        # 5. 점수 계산 (업데이트된 calculate_sharp_score 사용)
        final_score = calculate_sharp_score(
            rsi=snap.rsi,
            mfi=snap.mfi,
            bb_lower=snap.bb_lower,
            curr_price=curr_price,
            macd_diff=snap.macd_diff,
            ichi_a=snap.ichi_a,
            ichi_b=snap.ichi_b,
            vwap=snap.vwap,
            macd_diff_pct=snap.macd_diff_pct,
            is_waterfall=is_waterfall,
            is_rsi_hook_failed=is_rsi_hook_failed
        )
        
        # 6. 펀더멘털 검증
        fund_penalty = 0.0
        fund_msgs = []
        if apply_fundamental:
            fund_chk = FundamentalsChecker()
            yf_ticker = yf.Ticker(ticker) 
            fund_res = fund_chk.check(yf_ticker)
            fund_penalty = fund_res.penalty
            fund_msgs = fund_res.messages
            
            # 펀더멘털 패널티 적용
            final_score = round(max(0.0, final_score - fund_penalty), 1)

        # ──────────────────────────────────────────────
        # 7. [The Closer's 월스트리트 분석 코멘트 생성]
        #    보조지표별 가점을 해부하여 전문가 수준의 코멘트를 산출
        # ──────────────────────────────────────────────

        # 7-1. 보조지표별 개별 점수 추출
        r_sc  = score_rsi(snap.rsi)
        m_sc  = score_mfi(snap.mfi)
        b_sc  = score_bb(curr_price, snap.bb_lower)
        mac_sc = score_macd(snap.macd_diff, snap.macd_diff_pct)
        i_sc  = score_ichimoku(curr_price, snap.ichi_a, snap.ichi_b)
        v_sc  = score_vwap(curr_price, snap.vwap)

        # 7-2. Action 판정 (폭포수 / Hook 실패 우선 처리)
        if is_waterfall:
            verdict = "🔴 [절대 매수 금지 (AVOID)]"
            briefing = (
                "대세 하락장(120일 장기 추세선 역배열)에 진입한 **'폭포수 차트'**입니다. "
                "데드캣 바운스(일시적 반등)에 속지 마십시오. 추세가 완전히 바닥을 다지고 "
                "120일선을 재탈환하기 전까지는 어떤 매수도 금지합니다."
            )
        elif is_rsi_hook_failed:
            verdict = "🟡 [바닥 확인 대기 (WAIT)]"
            briefing = (
                "지표상 과매도 구간이나, RSI가 아직 고개를 들지 못하고 "
                "계속 하락 중입니다(**Hook 실패**). 바닥을 함부로 예측하지 마시고, "
                "RSI가 위로 꺾이는 **턴어라운드를 확인한 뒤** 진입하십시오."
            )
        elif final_score >= 70:
            verdict = "🟢 [적극 매수 (BUY)]"
            briefing = (
                "완벽한 과매도 바닥 구간에서 RSI가 턴어라운드(Hook)에 성공했습니다. "
                "떨어지는 칼날이 멈추고 반등이 시작되는 최적의 타점입니다. "
                "철저한 **분할 매수**로 물량을 확보하십시오."
            )
        elif final_score <= 30:
            verdict = "🔴 [매도 및 회피 (SELL)]"
            briefing = (
                "수급이 완전히 이탈했거나 고점 과열 상태입니다. "
                "신규 진입은 절대 금지하며, 보유자는 즉각 비중을 축소하십시오."
            )
        else:
            verdict = "🟡 [보류 및 관망 (HOLD)]"
            briefing = (
                "방향성을 상실한 혼조세 구간입니다. 가격은 횡보하고 수급은 애매합니다. "
                "확실한 타점(70점 이상)이 나올 때까지 소중한 자본을 묶어두지 마십시오."
            )

        # 7-3. ATR 동적 손절선 계산
        stop_line = ""
        if snap.atr > 0:
            dynamic_stop = curr_price - (snap.atr * 2.0)
            pct = abs((dynamic_stop - curr_price) / curr_price * 100) if curr_price > 0 else 0
            stop_line = f"  \n🛡️ **ATR 동적 손절선**: **{dynamic_stop:,.1f}** ({pct:.1f}% below)"

        # 7-4. 월스트리트 종합 코멘트 조립
        wall_street_comment  = f"**{verdict}**\n\n"
        wall_street_comment += "📊 **[The Closer's 총점 해부]**  \n"
        wall_street_comment += f"▪️ **RSI** (과매도 강도): **+{r_sc}점** / 20점 만점  \n"
        wall_street_comment += f"▪️ **MFI** (세력 자금유입): **+{m_sc}점** / 20점 만점  \n"
        wall_street_comment += f"▪️ **BB** (하단 지지력): **+{b_sc}점** / 15점 만점  \n"
        wall_street_comment += f"▪️ **MACD** (추세 방향·크기): **+{mac_sc}점** / 15점 만점  \n"
        wall_street_comment += f"▪️ **Ichimoku** (구름 추세): **+{i_sc}점** / 15점 만점  \n"
        wall_street_comment += f"▪️ **VWAP** (수급 괴리): **+{v_sc}점** / 15점 만점"

        if fund_penalty > 0:
            wall_street_comment += f"  \n🚨 **재무 페널티**: **-{fund_penalty}점** 감점"

        if is_waterfall:
            wall_street_comment += f"  \n🚨 **폭포수 필터**: 장기 120일선 역배열 (점수 강제 29점 하향)"
        if is_rsi_hook_failed:
            wall_street_comment += f"  \n🪝 **RSI Hook 필터**: 턴어라운드 실패/하락 진행 중 (점수 강제 29점 하향)"

        wall_street_comment += stop_line
        wall_street_comment += f"\n\n💡 **[월스트리트 퀀트 분석]**  \n{briefing}"

        # ──────────────────────────────────────────────
        # 8. Detail Info 구성 (보조지표별 해부 카드)
        # ──────────────────────────────────────────────
        detail_info = [
            {"title": "🌡️ RSI (엔진 온도)", "full_comment": (
                f"RSI {snap.rsi:.1f} → "
                f"{'🔥 극심한 과매도 (강한 반등 가능성)' if snap.rsi < 25 else '📉 과매도 구간 (바닥 근처)' if snap.rsi < 30 else '⚖️ 중립 구간' if snap.rsi < 70 else '📈 과매수 (고점 주의)'}"
                f"  |  가점 +{r_sc}점"
            )},
            {"title": "🪝 RSI 턴어라운드 (Hook)", "full_comment": (
                "🚨 턴어라운드 실패 — RSI가 계속 하향 중 (떨어지는 칼날, 관망 필수)"
                if is_rsi_hook_failed else
                "✅ 턴어라운드 성공 또는 해당 없음 (안전)"
            )},
            {"title": "💰 MFI (세력 자금 흐름)", "full_comment": (
                f"MFI {snap.mfi:.1f} → "
                f"{'💸 세력 대규모 유입 (강한 매집 신호)' if snap.mfi < 20 else '📉 자금 약세 (바닥 탐색 중)' if snap.mfi < 30 else '⚖️ 중립 수급' if snap.mfi < 70 else '🚨 자금 과열 (차익 실현 주의)'}"
                f"  |  가점 +{m_sc}점"
            )},
            {"title": "💎 볼린저 밴드 (변동성)", "full_comment": (
                f"하단 {snap.bb_lower:,.1f} | 현재가 {curr_price:,.1f} → "
                f"{'🎯 하단 이탈 (극단적 저평가)' if curr_price <= snap.bb_lower else '📉 하단 근접 (지지력 테스트 중)' if curr_price <= snap.bb_lower * 1.02 else '⚖️ 밴드 중간 권역' if curr_price < snap.bb_upper else '📈 상단 돌파 (과열 주의)'}"
                f"  |  가점 +{b_sc}점"
            )},
            {"title": "📊 MACD (추세 신호)", "full_comment": (
                f"MACD Diff {snap.macd_diff:+.2f} → "
                f"{'🟢 골든크로스 (추세 반전 신호)' if snap.macd_diff > 0 else '🔴 데드크로스 (하락 추세 지속)'}"
                f"  |  가점 +{mac_sc}점"
            )},
            {"title": "📈 일목균형표 (Ichimoku)", "full_comment": (
                f"선행A {snap.ichi_a:,.1f} / 선행B {snap.ichi_b:,.1f} → "
                f"{'🟢 구름 아래 (반등 여력 큼)' if curr_price < min(snap.ichi_a, snap.ichi_b) else '🟡 구름 내부 (방향성 모색 중)' if curr_price < max(snap.ichi_a, snap.ichi_b) else '⚖️ 구름 위 (안정적 상승 추세)'}"
                f"  |  가점 +{i_sc}점"
            )},
            {"title": "🌊 VWAP (거래량 가중)", "full_comment": (
                f"VWAP {snap.vwap:,.1f} | 현재가 {curr_price:,.1f} → "
                f"{'🟢 VWAP 하회 (평균 매입가 대비 저평가)' if curr_price < snap.vwap else '🔴 VWAP 상회 (평균 매입가 대비 고평가)'}"
                f"  |  가점 +{v_sc}점"
            )},
            {"title": "📉 장기 추세 (120일선)", "full_comment": (
                "🚨 위험 — 폭포수 하락 중 (120일선 역배열)"
                if is_waterfall else
                "✅ 안전 — 추세 지지 또는 상승 중"
            )},
            {"title": "🎯 ATR (변동성 범위)", "full_comment": (
                f"ATR {snap.atr:,.2f} → 일중 예상 변동폭 ±{snap.atr:,.1f}"
            )},
        ]

        if fund_msgs:
            detail_info.append({
                "title": "🏢 펀더멘털 검증 (재무제표)",
                "full_comment": " / ".join(fund_msgs)
            })

        # 🎯 최종 월스트리트 의견 카드
        detail_info.append({
            "title": "🎯 The Closer's 실시간 의견",
            "full_comment": wall_street_comment
        })

        # 9. Stop Loss
        stop_loss = curr_price * 0.90
        
        return df_ind, final_score, verdict, detail_info, stop_loss

    except Exception as e:
        # 🚨 에러가 나도 빈 DataFrame + 0점 반환 (None 절대 금지)
        return pd.DataFrame(), 0.0, f"⚠️ 분석불가({str(e)[:30]})", [], 0.0
