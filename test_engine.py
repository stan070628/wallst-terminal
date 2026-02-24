"""
test_engine.py — The Closer's Pytest Test Suite
================================================
실행 방법:
    cd /Users/seungminlee/Desktop/auto_bot
    .venv/bin/python3 -m pytest test_engine.py -v

테스트 레이어:
    1. 순수 채점 함수 (네트워크 없음, 빠름)
    2. FundamentalsChecker (yfinance.Ticker mock)
    3. IndicatorEngine (pandas DataFrame mock)
    4. DataClient (yfinance mock / InsufficientDataError)
    5. StockAnalyzer 통합 (전체 파이프라인 mock)
    6. 실제 API 연동 테스트 (느림, --runslow 옵션으로 활성화)
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from engine_v2 import (
    AnalysisResult,
    DataClient,
    DataFetchError,
    FundamentalsChecker,
    FundamentalsResult,
    IndicatorEngine,
    IndicatorSnapshot,
    InsufficientDataError,
    StockAnalyzer,
    calculate_sharp_score,
    score_bb,
    score_ichimoku,
    score_macd,
    score_mfi,
    score_rsi,
    score_vwap,
)


# ─────────────────────────────────────────────
# 공통 픽스처
# ─────────────────────────────────────────────

@pytest.fixture
def sample_df() -> pd.DataFrame:
    """최소 60행의 OHLCV 더미 데이터."""
    n = 60
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    high  = close + rng.uniform(0.5, 2.0, n)
    low   = close - rng.uniform(0.5, 2.0, n)
    volume = rng.integers(100_000, 1_000_000, n)
    return pd.DataFrame(
        {"Close": close, "High": high, "Low": low, "Volume": volume},
        index=pd.date_range("2025-01-01", periods=n, freq="B"),
    )


@pytest.fixture
def mock_ticker_info() -> dict:
    return {
        "quoteType": "EQUITY",
        "shortName": "Test Corp",
        "marketCap": 500_000_000_000,   # 5000억
        "trailingEps": 5.0,
        "revenueGrowth": 0.15,
        "debtToEquity": 80.0,
        "industry": "semiconductor",
        "sector": "technology",
    }


# ─────────────────────────────────────────────
# 1. 순수 채점 함수 단위 테스트
# ─────────────────────────────────────────────

class TestScoringFunctions:
    """score_* 순수 함수들: 네트워크 없음, 빠른 수행."""

    # ── RSI ──────────────────────────────
    def test_rsi_oversold_max(self):
        """RSI 0일 때 최대 20점."""
        assert score_rsi(0.0) == 20.0

    def test_rsi_threshold_60(self):
        """RSI 60 → 0점 경계."""
        assert score_rsi(60.0) == 0.0

    def test_rsi_overbought_zero(self):
        """RSI 80 → 0점 (과매수)."""
        assert score_rsi(80.0) == 0.0

    def test_rsi_midpoint(self):
        """RSI 40 → (60-40)*0.5 = 10점."""
        assert score_rsi(40.0) == 10.0

    def test_rsi_clamp_no_negative(self):
        """RSI 100 → 음수 없음."""
        assert score_rsi(100.0) == 0.0

    # ── MFI ──────────────────────────────
    def test_mfi_low_max(self):
        assert score_mfi(0.0) == 20.0

    def test_mfi_high_zero(self):
        assert score_mfi(75.0) == 0.0

    def test_mfi_symmetric_with_rsi(self):
        """RSI 와 MFI 채점 함수는 동일 로직이어야 함."""
        for v in [10, 30, 50, 60, 80]:
            assert score_rsi(float(v)) == score_mfi(float(v))

    # ── BB ──────────────────────────────
    def test_bb_price_below_lower(self):
        """현재가 < BB하단 → 양수 점수."""
        score = score_bb(curr_price=95.0, bb_lower=100.0)
        assert score > 0.0

    def test_bb_price_far_above_lower(self):
        """현재가가 BB하단 대비 10% 위 → 0점."""
        assert score_bb(curr_price=110.0, bb_lower=100.0) == 0.0

    def test_bb_max_clamp(self):
        """극단적으로 이탈해도 15점 초과 불가."""
        assert score_bb(curr_price=50.0, bb_lower=100.0) <= 15.0

    def test_bb_zero_lower_safe(self):
        """bb_lower=0 → ZeroDivisionError 없이 0점."""
        assert score_bb(curr_price=100.0, bb_lower=0.0) == 0.0

    # ── MACD ──────────────────────────────
    def test_macd_positive_base(self):
        """macd_diff > 0 → 최소 7점."""
        assert score_macd(0.01) >= 7.0

    def test_macd_negative_zero(self):
        """macd_diff ≤ 0 → 0점."""
        assert score_macd(-1.0) == 0.0
        assert score_macd(0.0) == 0.0

    def test_macd_max_clamp(self):
        """극단적 크기도 15점 초과 불가."""
        assert score_macd(9999.0, macd_diff_pct=100.0) == 15.0

    def test_macd_pct_bonus(self):
        """macd_diff_pct 제공 시 보너스 반영."""
        base  = score_macd(0.1, macd_diff_pct=None)
        bonus = score_macd(0.1, macd_diff_pct=0.05)
        assert bonus >= base

    # ── Ichimoku ──────────────────────────────
    def test_ichi_below_cloud(self):
        """가격이 구름 완전 하단 → 높은 점수."""
        s = score_ichimoku(curr_price=80.0, ichi_a=100.0, ichi_b=105.0)
        assert s >= 12.0

    def test_ichi_inside_cloud(self):
        s = score_ichimoku(curr_price=102.0, ichi_a=100.0, ichi_b=105.0)
        assert 0.0 < s < 12.0

    def test_ichi_above_cloud_zero(self):
        """가격이 구름 위 → 0점 (상승 구름 보너스 제외)."""
        s = score_ichimoku(curr_price=115.0, ichi_a=100.0, ichi_b=105.0)
        # ichi_a < ichi_b → 하락 구름, 보너스 없음 → 0점
        assert s == 0.0

    def test_ichi_bullish_cloud_bonus(self):
        """ichi_a > ichi_b(상승 배열) 시 +3점 보너스."""
        s_bull = score_ichimoku(95.0, ichi_a=105.0, ichi_b=100.0)  # 상승 배열, 가격 하단
        s_bear = score_ichimoku(95.0, ichi_a=100.0, ichi_b=105.0)  # 하락 배열, 가격 하단
        assert s_bull > s_bear

    def test_ichi_none_neutral(self):
        """데이터 없으면 중립 7.5."""
        assert score_ichimoku(100.0, None, None) == 7.5

    # ── VWAP ──────────────────────────────
    def test_vwap_below_vwap(self):
        """현재가 < VWAP → 양수 점수."""
        assert score_vwap(curr_price=95.0, vwap=100.0) > 0.0

    def test_vwap_above_vwap_zero(self):
        """현재가 > VWAP → 0점."""
        assert score_vwap(curr_price=105.0, vwap=100.0) == 0.0

    def test_vwap_none_neutral(self):
        assert score_vwap(100.0, None) == 7.5

    # ── calculate_sharp_score (통합) ──────────────────────────────
    def test_total_score_range(self):
        """점수는 항상 [0, 100] 범위."""
        for rsi in [10, 30, 50, 70, 90]:
            for mfi in [10, 50, 90]:
                s = calculate_sharp_score(rsi, mfi, bb_lower=100, curr_price=98, macd_diff=0.5)
                assert 0.0 <= s <= 100.0, f"범위 초과: rsi={rsi}, mfi={mfi}, score={s}"

    def test_perfect_oversold_high_score(self):
        """극단적 과매도 → 높은 점수 (70+)."""
        s = calculate_sharp_score(
            rsi=5, mfi=5, bb_lower=100, curr_price=94,
            macd_diff=0.8, ichi_a=120.0, ichi_b=125.0, vwap=105.0
        )
        assert s >= 70.0, f"과매도 바닥인데 점수가 낮음: {s}"

    def test_overbought_low_score(self):
        """과매수 + 모든 지표 부정적 → 낮은 점수."""
        s = calculate_sharp_score(
            rsi=85, mfi=85, bb_lower=100, curr_price=115,
            macd_diff=-2.0, ichi_a=90.0, ichi_b=88.0, vwap=95.0
        )
        assert s <= 10.0, f"과매수 상태인데 점수가 높음: {s}"

    def test_missing_optional_params(self):
        """선택 파라미터 없어도 오류 없이 동작."""
        s = calculate_sharp_score(rsi=40, mfi=40, bb_lower=100, curr_price=98, macd_diff=0.2)
        assert 0.0 <= s <= 100.0

    @pytest.mark.parametrize("rsi,mfi,expected_min", [
        (10, 10, 30),   # RSI+MFI 모두 과매도 → 최소 30점
        (60, 60, 0),    # RSI+MFI 중립 → RSI/MFI 기여 0
        (90, 90, 0),    # RSI+MFI 과매수 → 0
    ])
    def test_rsi_mfi_parametrized(self, rsi: int, mfi: int, expected_min: int):
        s = calculate_sharp_score(rsi, mfi, 100, 100, 0)
        assert s >= expected_min


# ─────────────────────────────────────────────
# 2. FundamentalsChecker 단위 테스트
# ─────────────────────────────────────────────

class TestFundamentalsChecker:

    def _make_ticker(self, info: dict) -> MagicMock:
        t = MagicMock()
        t.ticker = info.get("_ticker", "TEST")
        t.info   = info
        return t

    def test_etf_exempt(self):
        ticker = self._make_ticker({"quoteType": "ETF", "shortName": "KODEX 200", "_ticker": "226490.KS"})
        result = FundamentalsChecker().check(ticker)
        assert result.is_exempt is True
        assert result.penalty == 0.0

    def test_crypto_exempt(self):
        ticker = self._make_ticker({"quoteType": "CRYPTOCURRENCY", "shortName": "Bitcoin", "_ticker": "BTC-USD"})
        result = FundamentalsChecker().check(ticker)
        assert result.is_exempt is True

    def test_small_cap_korean_penalty(self):
        """시가총액 300억 미만 한국주 → -25점."""
        ticker = self._make_ticker({
            "quoteType": "EQUITY", "shortName": "소형주",
            "marketCap": 20_000_000_000,  # 200억
            "trailingEps": 1.0, "debtToEquity": 50.0,
            "industry": "tech", "sector": "tech", "_ticker": "999999.KS",
        })
        result = FundamentalsChecker().check(ticker)
        assert result.penalty == 25.0

    def test_micro_cap_global_penalty(self):
        """$200M 미만 글로벌 → -25점."""
        ticker = self._make_ticker({
            "quoteType": "EQUITY", "shortName": "MicroCap",
            "marketCap": 100_000_000,  # $1억
            "trailingEps": 1.0, "debtToEquity": 50.0,
            "industry": "tech", "sector": "tech", "_ticker": "TINY",
        })
        result = FundamentalsChecker().check(ticker)
        assert result.penalty == 25.0

    def test_eps_negative_penalty(self):
        """EPS < 0, 매출 성장 없음 → -20점."""
        ticker = self._make_ticker({
            "quoteType": "EQUITY", "shortName": "LossCo",
            "marketCap": 1_000_000_000_000,
            "trailingEps": -2.0, "revenueGrowth": 0.05,
            "debtToEquity": 50.0,
            "industry": "tech", "sector": "tech", "_ticker": "LOSS",
        })
        result = FundamentalsChecker().check(ticker)
        assert result.penalty == 20.0

    def test_eps_negative_growth_exempt(self):
        """EPS < 0이지만 매출 20%↑ → 면제."""
        ticker = self._make_ticker({
            "quoteType": "EQUITY", "shortName": "GrowthCo",
            "marketCap": 1_000_000_000_000,
            "trailingEps": -1.0, "revenueGrowth": 0.35,
            "debtToEquity": 50.0,
            "industry": "software", "sector": "technology", "_ticker": "GROW",
        })
        result = FundamentalsChecker().check(ticker)
        assert result.penalty == 0.0
        assert any("면제" in m for m in result.messages)

    def test_debt_high_penalty(self):
        """부채비율 200% 초과 비금융 → -10점."""
        ticker = self._make_ticker({
            "quoteType": "EQUITY", "shortName": "HighDebt",
            "marketCap": 1_000_000_000_000,
            "trailingEps": 1.0, "revenueGrowth": 0.1,
            "debtToEquity": 250.0,
            "industry": "manufacturing", "sector": "industrials", "_ticker": "DEBT",
        })
        result = FundamentalsChecker().check(ticker)
        assert result.penalty == 10.0

    def test_debt_financial_exempt(self):
        """금융업종 부채비율 패널티 면제."""
        ticker = self._make_ticker({
            "quoteType": "EQUITY", "shortName": "BigBank",
            "marketCap": 30_000_000_000_000,
            "trailingEps": 10.0,
            "debtToEquity": 800.0,
            "industry": "banking", "sector": "financial",
            "_ticker": "105550.KS",
        })
        result = FundamentalsChecker().check(ticker)
        assert result.penalty == 0.0

    def test_healthy_fundamentals_zero_penalty(self):
        """모두 정상 → 0점 패널티."""
        ticker = self._make_ticker({
            "quoteType": "EQUITY", "shortName": "Healthy",
            "marketCap": 50_000_000_000_000,
            "trailingEps": 15.0, "revenueGrowth": 0.10,
            "debtToEquity": 80.0,
            "industry": "semiconductor", "sector": "technology",
            "_ticker": "AAPL",
        })
        result = FundamentalsChecker().check(ticker)
        assert result.penalty == 0.0

    def test_info_exception_safe(self):
        """ticker.info 자체가 예외를 던져도 패널티 0으로 안전하게 처리."""
        t = MagicMock()
        t.ticker = "BROKEN"
        type(t).info = property(lambda self: (_ for _ in ()).throw(Exception("API Error")))
        result = FundamentalsChecker().check(t)
        assert isinstance(result, FundamentalsResult)
        assert result.penalty == 0.0


# ─────────────────────────────────────────────
# 3. IndicatorEngine 단위 테스트
# ─────────────────────────────────────────────

class TestIndicatorEngine:

    def test_returns_snapshot_and_df(self, sample_df):
        ie = IndicatorEngine()
        snap, df_out = ie.compute(sample_df, curr_price=float(sample_df["Close"].iloc[-1]))
        assert isinstance(snap, IndicatorSnapshot)
        assert isinstance(df_out, pd.DataFrame)

    def test_snapshot_fields_finite(self, sample_df):
        """모든 지표 값이 유한한 실수여야 함."""
        ie = IndicatorEngine()
        snap, _ = ie.compute(sample_df, curr_price=100.0)
        for fname in IndicatorSnapshot.__dataclass_fields__:
            val = getattr(snap, fname)
            assert np.isfinite(float(val)), f"{fname} = {val} 는 유한하지 않음"

    def test_df_has_indicator_columns(self, sample_df):
        ie = IndicatorEngine()
        _, df_out = ie.compute(sample_df, curr_price=100.0)
        expected = {"rsi", "mfi", "bb_lower", "bb_upper", "macd", "ichi_a", "ichi_b", "vwap", "atr"}
        assert expected.issubset(set(df_out.columns))

    def test_rsi_fallback_no_ta(self, sample_df, monkeypatch):
        """ta 라이브러리 없이도 RSI 계산 가능 (수동 구현 폴백)."""
        monkeypatch.setattr("engine_v2._TA_AVAILABLE", False)
        ie = IndicatorEngine()
        snap, _ = ie.compute(sample_df, curr_price=100.0)
        assert 0.0 <= snap.rsi <= 100.0


# ─────────────────────────────────────────────
# 4. DataClient 단위 테스트 (mock)
# ─────────────────────────────────────────────

class TestDataClient:

    def _make_good_df(self, n: int = 60) -> pd.DataFrame:
        rng = np.random.default_rng(0)
        c = 100 + np.cumsum(rng.normal(0, 1, n))
        return pd.DataFrame(
            {"Close": c, "High": c + 1, "Low": c - 1, "Volume": rng.integers(1000, 10000, n)},
            index=pd.date_range("2025-01-01", periods=n, freq="B"),
        )

    def test_clean_normalizes_columns(self, monkeypatch):
        client = DataClient()
        raw = self._make_good_df()
        raw.columns = [c.lower() for c in raw.columns]
        df = client._clean(raw, "TEST")
        assert all(c[0].isupper() for c in df.columns)

    def test_clean_replaces_zero_volume(self, monkeypatch):
        client = DataClient()
        raw = self._make_good_df()
        raw["Volume"] = 0
        df = client._clean(raw, "TEST")
        assert (df["Volume"] == 1).all()

    def test_insufficient_data_raises(self, monkeypatch):
        """짧은 데이터(< 30행) → InsufficientDataError."""
        short_df = self._make_good_df(n=10)

        mock_ticker = MagicMock()
        mock_ticker.ticker = "SHORT"
        mock_ticker.history.return_value = short_df

        with patch("engine_v2.yf.Ticker", return_value=mock_ticker):
            client = DataClient()
            with pytest.raises(InsufficientDataError):
                client.fetch("SHORT")

    def test_api_exception_raises_datafetch_error(self, monkeypatch):
        """history() 자체가 네트워크 예외 → DataFetchError."""
        mock_ticker = MagicMock()
        mock_ticker.ticker = "NETERR"
        mock_ticker.history.side_effect = ConnectionError("timeout")

        with patch("engine_v2.yf.Ticker", return_value=mock_ticker):
            client = DataClient()
            with pytest.raises((DataFetchError, InsufficientDataError)):
                client.fetch("NETERR")


# ─────────────────────────────────────────────
# 5. StockAnalyzer 통합 테스트 (full mock)
# ─────────────────────────────────────────────

class TestStockAnalyzer:

    def test_empty_ticker_raises(self):
        with pytest.raises(ValueError):
            StockAnalyzer("")

    def test_whitespace_ticker_raises(self):
        with pytest.raises(ValueError):
            StockAnalyzer("   ")

    def test_ticker_normalized_to_upper(self):
        az = StockAnalyzer("aapl")
        assert az.ticker == "AAPL"

    def test_analyze_success(self, sample_df):
        """정상 데이터 → success=True, score in [0,100]."""
        mock_client = MagicMock(spec=DataClient)
        mock_client.fetch.return_value = sample_df

        mock_ind = MagicMock(spec=IndicatorEngine)
        snap = IndicatorSnapshot(
            rsi=40.0, mfi=35.0, macd_diff=0.5, macd_diff_pct=0.3,
            bb_lower=95.0, bb_upper=110.0,
            ichi_a=105.0, ichi_b=102.0,
            vwap=101.0, atr=1.5, obv=123456.0,
            current_price=98.0,
        )
        mock_ind.compute.return_value = (snap, sample_df)

        with patch("engine_v2.yf.Ticker") as mock_yf:
            mock_yf.return_value.fast_info.last_price = 98.0
            az = StockAnalyzer("AAPL", data_client=mock_client, indicator_engine=mock_ind)
            result = az.analyze()

        assert result.success is True
        assert 0.0 <= result.score <= 100.0
        assert result.current_price == 98.0
        assert len(result.detail_info) > 0

    def test_analyze_insufficient_data_returns_failure(self, sample_df):
        mock_client = MagicMock(spec=DataClient)
        mock_client.fetch.side_effect = InsufficientDataError("no data")
        az = StockAnalyzer("INVALID_TICKER_12345", data_client=mock_client)
        result = az.analyze()
        assert result.success is False
        assert result.error_type == "InsufficientData"
        assert "no data" in (result.error_msg or "")

    def test_analyze_datafetch_error_returns_failure(self, sample_df):
        mock_client = MagicMock(spec=DataClient)
        mock_client.fetch.side_effect = DataFetchError("network timeout")
        az = StockAnalyzer("AAPL", data_client=mock_client)
        result = az.analyze()
        assert result.success is False
        assert result.error_type == "DataFetch"

    def test_analyze_unexpected_error_safe(self, sample_df):
        """예기치 않은 예외도 success=False로 안전하게 반환."""
        mock_client = MagicMock(spec=DataClient)
        mock_client.fetch.side_effect = RuntimeError("unexpected!")
        az = StockAnalyzer("AAPL", data_client=mock_client)
        result = az.analyze()
        assert result.success is False
        assert result.error_type == "Analysis"

    def test_score_logic_oversold(self, sample_df):
        """극단적 과매도 지표 → score >= 70."""
        mock_client = MagicMock(spec=DataClient)
        mock_client.fetch.return_value = sample_df

        mock_ind = MagicMock(spec=IndicatorEngine)
        snap = IndicatorSnapshot(
            rsi=8.0, mfi=8.0, macd_diff=1.0, macd_diff_pct=1.0,
            bb_lower=110.0, bb_upper=130.0,      # curr_price < bb_lower
            ichi_a=120.0, ichi_b=125.0,          # curr_price < cloud
            vwap=120.0, atr=2.0, obv=0.0,
            current_price=90.0,
        )
        mock_ind.compute.return_value = (snap, sample_df)

        with patch("engine_v2.yf.Ticker") as mock_yf:
            mock_yf.return_value.fast_info.last_price = 90.0
            az = StockAnalyzer("TEST", data_client=mock_client, indicator_engine=mock_ind)
            result = az.analyze()

        assert result.success is True
        assert result.score >= 70.0, f"과매도인데 점수 낮음: {result.score}"

    def test_score_logic_overbought(self, sample_df):
        """극단적 과매수 → score <= 15."""
        mock_client = MagicMock(spec=DataClient)
        mock_client.fetch.return_value = sample_df

        mock_ind = MagicMock(spec=IndicatorEngine)
        snap = IndicatorSnapshot(
            rsi=90.0, mfi=90.0, macd_diff=-1.0, macd_diff_pct=0.0,
            bb_lower=80.0, bb_upper=95.0,         # curr < bb_upper
            ichi_a=90.0, ichi_b=88.0,             # curr > cloud (위)
            vwap=90.0, atr=1.0, obv=0.0,
            current_price=110.0,                  # curr > vwap, curr > bb_upper
        )
        mock_ind.compute.return_value = (snap, sample_df)

        with patch("engine_v2.yf.Ticker") as mock_yf:
            mock_yf.return_value.fast_info.last_price = 110.0
            az = StockAnalyzer("TEST", data_client=mock_client, indicator_engine=mock_ind)
            result = az.analyze()

        assert result.success is True
        assert result.score <= 15.0, f"과매수인데 점수 높음: {result.score}"

    def test_fundamental_penalty_applied(self, sample_df):
        """펀더멘털 패널티가 최종 점수에 정확히 반영됨."""
        mock_client = MagicMock(spec=DataClient)
        mock_client.fetch.return_value = sample_df

        mock_ind = MagicMock(spec=IndicatorEngine)
        snap = IndicatorSnapshot(
            rsi=40.0, mfi=40.0, macd_diff=0.5, macd_diff_pct=0.3,
            bb_lower=95.0, bb_upper=115.0, ichi_a=105.0, ichi_b=102.0,
            vwap=102.0, atr=1.5, obv=0.0, current_price=98.0,
        )
        mock_ind.compute.return_value = (snap, sample_df)

        mock_fund = MagicMock(spec=FundamentalsChecker)
        mock_fund.check.return_value = FundamentalsResult(
            penalty=20.0, messages=["EPS 마이너스 -20점"]
        )

        with patch("engine_v2.yf.Ticker") as mock_yf:
            mock_yf.return_value.fast_info.last_price = 98.0
            az = StockAnalyzer(
                "TEST", data_client=mock_client,
                indicator_engine=mock_ind, fundamentals_checker=mock_fund,
            )
            result_no_fund  = az.analyze(apply_fundamental=False)
            result_with_fund = az.analyze(apply_fundamental=True)

        diff = round(result_no_fund.score - result_with_fund.score, 1)
        assert diff == 20.0, f"패널티 반영 오류: 차이={diff}"

    def test_dynamic_stop_loss_below_price(self, sample_df):
        """손절선은 항상 현재가 이하여야 함."""
        mock_client = MagicMock(spec=DataClient)
        mock_client.fetch.return_value = sample_df

        mock_ind = MagicMock(spec=IndicatorEngine)
        snap = IndicatorSnapshot(
            rsi=50.0, mfi=50.0, macd_diff=0.0, macd_diff_pct=0.0,
            bb_lower=95.0, bb_upper=115.0, ichi_a=100.0, ichi_b=100.0,
            vwap=100.0, atr=2.0, obv=0.0, current_price=100.0,
        )
        mock_ind.compute.return_value = (snap, sample_df)

        with patch("engine_v2.yf.Ticker") as mock_yf:
            mock_yf.return_value.fast_info.last_price = 100.0
            az = StockAnalyzer("TEST", data_client=mock_client, indicator_engine=mock_ind)
            result = az.analyze()

        assert result.stop_loss < result.current_price

    def test_verdict_label_correct(self):
        """_verdict_label 판정 문자열 매핑 검증."""
        az = StockAnalyzer("AAPL")
        assert "매수" in az._verdict_label(80.0)      # 💎 분할 매수
        assert "정찰병" in az._verdict_label(50.0)    # ✅ 애매한 반등 - 정찰병만 투입
        assert "관망" in az._verdict_label(30.0)      # ⚠️ 추세 하락 - 관망
        assert "도망" in az._verdict_label(10.0)      # 🛑 폭락/인버스 - 도망


# ─────────────────────────────────────────────
# 6. 실제 API 통합 테스트 (느림 — 기본 비활성)
# ─────────────────────────────────────────────
# pytest_addoption 및 runslow 픽스처는 conftest.py 에서 정의됩니다.

@pytest.fixture
def runslow(request):
    return request.config.getoption("--runslow", default=False)


@pytest.mark.parametrize("ticker", ["AAPL", "005930.KS"])
def test_real_api_integration(ticker: str, runslow: bool):
    """실제 yfinance API 호출 — pytest --runslow 옵션 필요."""
    if not runslow:
        pytest.skip("느린 API 테스트: pytest --runslow 로 실행하세요.")

    result = StockAnalyzer(ticker).analyze(apply_fundamental=False)
    assert result.success is True, f"[{ticker}] API 실패: {result.error_msg}"
    assert result.current_price > 0
    assert 0.0 <= result.score <= 100.0
    assert result.indicators is not None
    assert len(result.detail_info) >= 7
