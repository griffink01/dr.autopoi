from scanner import calculate_signal, format_report


def test_calculate_signal_filters_by_notional() -> None:
    ticker = {
        "market": "KRW-ABC",
        "acc_trade_price_24h": 1_000,
        "opening_price": 100,
        "high_price": 120,
        "low_price": 90,
        "trade_price": 110,
        "signed_change_rate": 0.05,
    }
    assert calculate_signal(ticker, min_notional_krw=2_000) is None


def test_calculate_signal_score_and_report() -> None:
    ticker = {
        "market": "KRW-ABC",
        "acc_trade_price_24h": 60_000_000_000,
        "opening_price": 100,
        "high_price": 120,
        "low_price": 90,
        "trade_price": 120,
        "signed_change_rate": 0.1,
    }
    signal = calculate_signal(ticker, min_notional_krw=2_000)
    assert signal is not None
    assert signal.market == "KRW-ABC"
    assert signal.day_range_position == 1.0
    assert signal.score > 0

    report = format_report([signal])
    assert "KRW-ABC" in report
    assert "Change%" in report
