from datetime import UTC, datetime, timedelta

from liveness import is_stale, market_open


def test_market_open_est_and_edt():
    assert market_open(datetime(2026, 11, 19, 18, 0, tzinfo=UTC))
    assert not market_open(datetime(2026, 11, 19, 21, 30, tzinfo=UTC))
    assert not market_open(datetime(2026, 11, 21, 18, 0, tzinfo=UTC))
    assert market_open(datetime(2026, 7, 15, 13, 35, tzinfo=UTC))
    assert not market_open(datetime(2026, 7, 15, 13, 25, tzinfo=UTC))


def test_is_stale_uses_session_limit():
    market = datetime(2026, 11, 19, 18, 0, tzinfo=UTC)
    night = datetime(2026, 11, 20, 3, 0, tzinfo=UTC)
    assert is_stale(market - timedelta(seconds=130), market)
    assert not is_stale(market - timedelta(seconds=100), market)
    assert not is_stale(night - timedelta(seconds=130), night)
    assert is_stale(night - timedelta(seconds=700), night)
