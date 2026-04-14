from datetime import UTC, datetime

from abritel.scraping import parse_datetime_utc


def test_parse_datetime_utc_z_suffix() -> None:
    dt = parse_datetime_utc("2026-04-11T18:09:14Z")
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.astimezone(UTC) == datetime(2026, 4, 11, 18, 9, 14, tzinfo=UTC)


def test_parse_datetime_utc_empty() -> None:
    assert parse_datetime_utc("") is None


def test_parse_datetime_utc_invalid() -> None:
    assert parse_datetime_utc("not a date") is None
