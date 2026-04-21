"""Tests des scrapers avec mocks HTTP (responses + unittest.mock)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from unittest.mock import patch

import responses

from abritel.scraping import (
    APPSTORE_APP_ID,
    TRUSTPILOT_URL,
    get_json,
    get_text,
    telecharger_avis_app_store,
    telecharger_avis_google_play,
    telecharger_avis_trustpilot,
)

# --- Helpers HTTP ---


@responses.activate
def test_get_json_success() -> None:
    responses.get("https://example.com/api", json={"ok": True}, status=200)
    result = get_json("https://example.com/api", tentatives=1)
    assert result == {"ok": True}


@responses.activate
def test_get_json_failure_returns_none() -> None:
    responses.get("https://example.com/api", status=500)
    responses.get("https://example.com/api", status=500)
    result = get_json("https://example.com/api", tentatives=2)
    assert result is None


@responses.activate
def test_get_text_success() -> None:
    responses.get("https://example.com/page", body="<html>ok</html>", status=200)
    result = get_text("https://example.com/page", tentatives=1)
    assert result == "<html>ok</html>"


@responses.activate
def test_get_text_failure_returns_none() -> None:
    responses.get("https://example.com/page", status=404)
    result = get_text("https://example.com/page", tentatives=1)
    assert result is None


# --- Google Play (mock google_play_scraper.reviews) ---


@patch("abritel.scraping.time.sleep")
@patch("abritel.scraping.reviews")
def test_telecharger_google_play_basic(mock_reviews, mock_sleep) -> None:
    dt = datetime(2025, 6, 10, 12, 0, 0, tzinfo=UTC)
    mock_reviews.return_value = (
        [{"at": dt, "score": 4, "content": "Très bien"}],
        None,  # token=None → stop pagination
    )
    df = telecharger_avis_google_play(date_debut=date(2025, 1, 1))
    assert len(df) == 1
    assert df.iloc[0]["source"] == "Google Play"
    assert df.iloc[0]["note"] == 4
    assert df.iloc[0]["texte"] == "Très bien"


@patch("abritel.scraping.time.sleep")
@patch("abritel.scraping.reviews")
def test_telecharger_google_play_filters_old(mock_reviews, mock_sleep) -> None:
    old = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)
    recent = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
    mock_reviews.return_value = (
        [
            {"at": recent, "score": 5, "content": "Super"},
            {"at": old, "score": 1, "content": "Nul"},
        ],
        None,
    )
    df = telecharger_avis_google_play(date_debut=date(2025, 1, 1))
    assert len(df) == 1
    assert df.iloc[0]["texte"] == "Super"


@patch("abritel.scraping.time.sleep")
@patch("abritel.scraping.reviews")
def test_telecharger_google_play_empty_content(mock_reviews, mock_sleep) -> None:
    dt = datetime(2025, 6, 10, 12, 0, 0, tzinfo=UTC)
    mock_reviews.return_value = (
        [{"at": dt, "score": 3, "content": ""}],
        None,
    )
    df = telecharger_avis_google_play(date_debut=date(2025, 1, 1))
    assert df.iloc[0]["texte"] == "(sans commentaire)"


# --- App Store (mock HTTP via responses) ---


def _appstore_feed(entries: list[dict]) -> dict:
    """Construit un payload RSS App Store minimal."""
    return {"feed": {"entry": entries}}


def _appstore_entry(rating: int, updated: str, title: str, content: str) -> dict:
    return {
        "im:rating": {"label": str(rating)},
        "updated": {"label": updated},
        "title": {"label": title},
        "content": {"label": content},
    }


@responses.activate
def test_telecharger_app_store_basic() -> None:
    entry = _appstore_entry(5, "2025-06-10T10:00:00+00:00", "Génial", "Fonctionne bien")
    for page in range(1, 11):
        url = (
            f"https://itunes.apple.com/fr/rss/customerreviews"
            f"/page={page}/id={APPSTORE_APP_ID}/sortBy=mostRecent/json"
        )
        if page == 1:
            responses.get(url, json=_appstore_feed([entry]))
        else:
            responses.get(url, json=_appstore_feed([]))

    df = telecharger_avis_app_store(date_debut=date(2025, 1, 1))
    assert len(df) == 1
    assert df.iloc[0]["source"] == "App Store"
    assert df.iloc[0]["note"] == 5
    assert "Génial" in df.iloc[0]["texte"]


@responses.activate
def test_telecharger_app_store_filters_old() -> None:
    old_entry = _appstore_entry(2, "2024-03-01T10:00:00+00:00", "Bof", "Ancien")
    for page in range(1, 11):
        url = (
            f"https://itunes.apple.com/fr/rss/customerreviews"
            f"/page={page}/id={APPSTORE_APP_ID}/sortBy=mostRecent/json"
        )
        if page == 1:
            responses.get(url, json=_appstore_feed([old_entry]))
        else:
            responses.get(url, json=_appstore_feed([]))

    df = telecharger_avis_app_store(date_debut=date(2025, 1, 1))
    assert len(df) == 0


# --- Trustpilot (mock HTTP via responses) ---


def _trustpilot_html(reviews_list: list[dict]) -> str:
    """Construit un HTML Trustpilot minimal avec __NEXT_DATA__."""
    data = {"props": {"pageProps": {"reviews": reviews_list}}}
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></html>'


def _trustpilot_review(rating: int, published: str, title: str, text: str) -> dict:
    return {
        "rating": rating,
        "dates": {"publishedDate": published},
        "title": title,
        "text": text,
    }


@responses.activate
@patch("abritel.scraping._playwright_disponible", return_value=False)
@patch("abritel.scraping.time.sleep")
def test_telecharger_trustpilot_basic(mock_sleep, _mock_pw) -> None:
    review = _trustpilot_review(1, "2025-06-10T10:00:00Z", "Nul", "Service affreux")

    # Register URLs for all 5 star filters × pages
    for stars in range(1, 6):
        for page in range(1, 11):
            url = f"{TRUSTPILOT_URL}?stars={stars}&page={page}"
            if page == 1 and stars == 1:
                responses.get(url, body=_trustpilot_html([review]))
            else:
                responses.get(url, body=_trustpilot_html([]))

    df = telecharger_avis_trustpilot(date_debut=date(2025, 1, 1))
    assert len(df) == 1
    assert df.iloc[0]["source"] == "Trustpilot"
    assert df.iloc[0]["note"] == 1
    assert "Nul" in df.iloc[0]["texte"]


@responses.activate
@patch("abritel.scraping._playwright_disponible", return_value=False)
@patch("abritel.scraping.time.sleep")
def test_telecharger_trustpilot_deduplicates(mock_sleep, _mock_pw) -> None:
    review = _trustpilot_review(3, "2025-06-10T10:00:00Z", "Ok", "Moyen")

    for stars in range(1, 6):
        for page in range(1, 11):
            url = f"{TRUSTPILOT_URL}?stars={stars}&page={page}"
            if page == 1:
                # Same review appears for multiple star filters
                responses.get(url, body=_trustpilot_html([review]))
            else:
                responses.get(url, body=_trustpilot_html([]))

    df = telecharger_avis_trustpilot(date_debut=date(2025, 1, 1))
    # Same review appears 5 times but should be deduplicated to 1
    assert len(df) == 1
