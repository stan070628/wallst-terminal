# conftest.py — pytest 전역 설정
def pytest_addoption(parser):
    parser.addoption(
        "--runslow",
        action="store_true",
        default=False,
        help="실제 yfinance API를 호출하는 느린 통합 테스트 실행",
    )
