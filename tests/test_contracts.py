"""Tests de contrat API — vérifient que la structure des sources n'a pas changé.

Marqués @pytest.mark.slow car ils font de vraies requêtes HTTP.
Exclus du CI standard : pytest -m "not slow"
Exécutés dans un workflow GH Actions hebdomadaire dédié.
"""

from __future__ import annotations

import json

import pytest
import requests
from bs4 import BeautifulSoup

APPSTORE_APP_ID = "642441300"
TRUSTPILOT_URL = "https://fr.trustpilot.com/review/abritel.fr"
GP_APP_ID = "com.vacationrentals.homeaway"


@pytest.mark.slow
def test_appstore_rss_returns_entries() -> None:
    """L'API RSS Apple retourne des entrées avec rating, title, content, updated."""
    url = (
        f"https://itunes.apple.com/fr/rss/customerreviews"
        f"/page=1/id={APPSTORE_APP_ID}/sortBy=mostRecent/json"
    )
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    entries = data.get("feed", {}).get("entry", [])
    assert len(entries) > 0, "Aucune entrée dans le flux RSS App Store"

    entry = entries[0]
    assert "im:rating" in entry, "Champ im:rating manquant"
    assert "label" in entry["im:rating"], "im:rating.label manquant"
    assert "updated" in entry, "Champ updated manquant"
    assert "label" in entry["updated"], "updated.label manquant"


@pytest.mark.slow
def test_trustpilot_has_next_data_script() -> None:
    """La page Trustpilot contient un <script id='__NEXT_DATA__'> avec des reviews."""
    resp = requests.get(f"{TRUSTPILOT_URL}?stars=5&page=1", timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    assert script is not None, "<script id='__NEXT_DATA__'> introuvable"
    assert script.string, "Script __NEXT_DATA__ vide"

    data = json.loads(script.string)
    reviews = data.get("props", {}).get("pageProps", {}).get("reviews", [])
    assert len(reviews) > 0, "Aucun avis dans __NEXT_DATA__"

    review = reviews[0]
    assert "dates" in review, "Champ dates manquant"
    assert "publishedDate" in review["dates"], "dates.publishedDate manquant"
    assert "rating" in review, "Champ rating manquant"


@pytest.mark.slow
def test_google_play_scraper_returns_reviews() -> None:
    """Le scraper Google Play retourne des avis avec les champs attendus."""
    from google_play_scraper import Sort, reviews

    result, _ = reviews(
        GP_APP_ID,
        lang="fr",
        country="fr",
        sort=Sort.NEWEST,
        count=5,
    )
    assert len(result) > 0, "Aucun avis retourné par google_play_scraper"

    avis = result[0]
    assert "at" in avis, "Champ 'at' (datetime) manquant"
    assert "score" in avis, "Champ 'score' manquant"
    assert "content" in avis, "Champ 'content' manquant"
    assert isinstance(avis["score"], int), f"score n'est pas un int: {type(avis['score'])}"
