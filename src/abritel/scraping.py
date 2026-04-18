"""Scrapers pour Google Play, App Store et Trustpilot."""

from __future__ import annotations

import json
import logging
import random
import threading
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from bs4 import BeautifulSoup
from google_play_scraper import Sort, reviews

LOG = logging.getLogger(__name__)

TZ_FR = ZoneInfo("Europe/Paris")
# Date de début fixe : collecte exhaustive de tous les avis depuis le 01/01/2025.
# Ne pas modifier — c'est le référentiel de l'analyse produit.
DATE_DEBUT_INCLUSIVE = date(2025, 1, 1)

# --- Constantes sources ---

GP_APP_ID = "com.vacationrentals.homeaway"
GP_TAILLE_LOT = 200
GP_PAGES_MAX = 2000

APPSTORE_APP_ID = "642441300"

TRUSTPILOT_URL = "https://fr.trustpilot.com/review/abritel.fr"
TRUSTPILOT_PAGES_PAR_FILTRE = 10

# --- Session HTTP ---

_USER_AGENTS = [
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
]

_THREAD_LOCAL = threading.local()


def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = random.choice(_USER_AGENTS)
    return s


def _get_session() -> requests.Session:
    s = getattr(_THREAD_LOCAL, "session", None)
    if s is None:
        s = _make_session()
        _THREAD_LOCAL.session = s
    return s


# --- Helpers ---


def date_fin_inclusive(tz: ZoneInfo = TZ_FR) -> date:
    """Aujourd'hui (date civile) dans le fuseau `tz`."""
    return datetime.now(tz).date()


def avis_jour_paris(avis_at: datetime) -> date:
    """Convertit une date d'avis en jour civil à Paris."""
    ts = pd.Timestamp(avis_at)
    if ts.tz is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert(TZ_FR).date()


def dans_fenetre(jour: date, date_fin: date, date_debut: date = DATE_DEBUT_INCLUSIVE) -> bool:
    return date_debut <= jour <= date_fin


def _joindre_texte(titre: str, contenu: str) -> str:
    """Fusionne titre + contenu avec fallback '(sans commentaire)'."""
    titre = (titre or "").strip()
    contenu = (contenu or "").strip()
    texte = f"{titre}. {contenu}".strip(". ") if titre else contenu
    return texte if texte else "(sans commentaire)"


def _deduquer_et_trier(df: pd.DataFrame) -> pd.DataFrame:
    """Trie par date décroissante et déduplique sur (source, date, note, texte)."""
    if df.empty:
        return df
    return df.sort_values("date", ascending=False).drop_duplicates(
        subset=["source", "date", "note", "texte"],
        keep="first",
    )


def _backoff_delay(attempt: int, err: requests.RequestException) -> float:
    """Calcule le délai de retry : respecte Retry-After (429) ou backoff exponentiel."""
    resp = getattr(err, "response", None)
    if resp is not None and resp.status_code == 429:
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), 120)
            except ValueError:
                pass
    return min(2**attempt + random.uniform(0, 0.5), 10)


def _http_get(url: str, *, parse_json: bool = False, timeout_s: int = 15, tentatives: int = 5):
    """GET avec retries et backoff exponentiel. Retourne JSON (dict) ou texte (str), ou None.

    Avec 5 tentatives, le backoff atteint ~10s au 4e retry (cap actif).
    """
    session = _get_session()
    last_err: Exception | None = None
    for i in range(tentatives):
        try:
            headers = {"User-Agent": random.choice(_USER_AGENTS)}
            resp = session.get(url, timeout=timeout_s, headers=headers)
            resp.raise_for_status()
            return resp.json() if parse_json else resp.text
        except requests.RequestException as e:
            last_err = e
            time.sleep(_backoff_delay(i, e))
    LOG.warning("HTTP — échec après %s tentatives: %s", tentatives, last_err)
    return None


def get_json(url: str, *, timeout_s: int = 15, tentatives: int = 5) -> dict | None:
    """GET JSON avec retries et backoff exponentiel."""
    return _http_get(url, parse_json=True, timeout_s=timeout_s, tentatives=tentatives)


def get_text(url: str, *, timeout_s: int = 15, tentatives: int = 5) -> str | None:
    """GET HTML/text avec retries et backoff exponentiel."""
    return _http_get(url, parse_json=False, timeout_s=timeout_s, tentatives=tentatives)


def parse_datetime_utc(value: str) -> datetime | None:
    """Parse tolérant vers datetime aware UTC (None si invalide)."""
    if not value:
        return None
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.to_pydatetime()


# --- Scrapers ---


def telecharger_avis_google_play(*, date_debut: date = DATE_DEBUT_INCLUSIVE) -> pd.DataFrame:
    """Pagination complète du plus récent au plus ancien, filtre sur la fenêtre."""
    fin = date_fin_inclusive()
    lignes: list[dict] = []
    token = None
    pages = 0

    while pages < GP_PAGES_MAX:
        lot: list[dict] = []
        for tentative in range(5):
            try:
                lot, token = reviews(
                    GP_APP_ID,
                    lang="fr",
                    country="fr",
                    sort=Sort.NEWEST,
                    count=GP_TAILLE_LOT,
                    continuation_token=token,
                )
                break
            except (requests.RequestException, ValueError, TypeError) as e:
                if tentative == 4:
                    LOG.warning("Google Play — erreur après 5 tentatives: %s", e)
                time.sleep(min(2**tentative + random.uniform(0, 0.5), 10))
        pages += 1
        if not lot:
            break

        for avis in lot:
            # google_play_scraper retourne des datetimes naives en heure
            # locale du système — on les convertit en UTC aware.
            dt_raw = avis["at"]
            if isinstance(dt_raw, datetime) and dt_raw.tzinfo is None:
                dt_utc = dt_raw.astimezone(ZoneInfo("UTC"))
            else:
                dt_utc = dt_raw
            jour = avis_jour_paris(dt_utc)
            if not dans_fenetre(jour, fin, date_debut):
                continue
            texte = (avis.get("content") or "").strip() or "(sans commentaire)"
            lignes.append(
                {
                    "date": dt_utc,
                    "note": avis["score"],
                    "texte": texte,
                    "source": "Google Play",
                }
            )

        dt_last = lot[-1]["at"]
        if isinstance(dt_last, datetime) and dt_last.tzinfo is None:
            dt_last = dt_last.astimezone(ZoneInfo("UTC"))
        plus_ancien = avis_jour_paris(dt_last)
        if plus_ancien < date_debut or token is None:
            break
        time.sleep(0.5 + random.uniform(0, 0.3))

    out = _deduquer_et_trier(pd.DataFrame(lignes))
    LOG.info("Google Play: %s page(s), %s avis retenus", pages, len(out))
    return out


def telecharger_avis_app_store(*, date_debut: date = DATE_DEBUT_INCLUSIVE) -> pd.DataFrame:
    """API RSS Apple : 500 avis les plus récents (10 pages de 50)."""
    fin = date_fin_inclusive()
    lignes: list[dict] = []
    pages_ok = 0

    for page in range(1, 11):
        url = (
            f"https://itunes.apple.com/fr/rss/customerreviews"
            f"/page={page}/id={APPSTORE_APP_ID}/sortBy=mostRecent/json"
        )
        payload = get_json(url, timeout_s=15, tentatives=3)
        if payload is None:
            LOG.warning("App Store — page %s échouée, on continue", page)
            continue

        entries = payload.get("feed", {}).get("entry", [])
        if not entries:
            break

        for entry in entries:
            rating = entry.get("im:rating", {}).get("label")
            if rating is None:
                continue

            dt = parse_datetime_utc(entry.get("updated", {}).get("label", ""))
            if dt is None:
                continue

            jour = avis_jour_paris(dt)
            if not dans_fenetre(jour, fin, date_debut):
                continue

            texte = _joindre_texte(
                entry.get("title", {}).get("label", ""),
                entry.get("content", {}).get("label", ""),
            )

            lignes.append(
                {
                    "date": dt,
                    "note": int(rating),
                    "texte": texte,
                    "source": "App Store",
                }
            )

        pages_ok += 1

    out = _deduquer_et_trier(pd.DataFrame(lignes))
    LOG.info("App Store: %s page(s), %s avis retenus", pages_ok, len(out))
    return out


def _trustpilot_pages(params: str, *, date_debut: date = DATE_DEBUT_INCLUSIVE) -> list[dict]:
    """Pagine Trustpilot (max TRUSTPILOT_PAGES_PAR_FILTRE) pour un jeu de paramètres."""
    fin = date_fin_inclusive()
    lignes: list[dict] = []

    for page in range(1, TRUSTPILOT_PAGES_PAR_FILTRE + 1):
        sep = "&" if params else "?"
        url = (
            f"{TRUSTPILOT_URL}?{params}{sep}page={page}"
            if params
            else f"{TRUSTPILOT_URL}?page={page}"
        )
        html = get_text(url, timeout_s=15, tentatives=3)
        if html is None:
            break

        soup = BeautifulSoup(html, "html.parser")
        script = soup.find("script", id="__NEXT_DATA__")
        if not script or not script.string:
            break

        try:
            data = json.loads(script.string)
        except json.JSONDecodeError:
            break

        avis_list = data.get("props", {}).get("pageProps", {}).get("reviews", [])
        if not avis_list:
            break

        page_hors_fenetre = True
        for avis in avis_list:
            dt = parse_datetime_utc(avis.get("dates", {}).get("publishedDate", ""))
            if dt is None:
                continue

            jour = avis_jour_paris(dt)
            if jour > fin:
                continue
            if jour >= date_debut:
                page_hors_fenetre = False
            if not dans_fenetre(jour, fin, date_debut):
                continue

            texte = _joindre_texte(avis.get("title", ""), avis.get("text", ""))

            lignes.append(
                {
                    "date": dt,
                    "note": avis.get("rating", 0),
                    "texte": texte,
                    "source": "Trustpilot",
                }
            )

        if page_hors_fenetre:
            break

    return lignes


def telecharger_avis_trustpilot(*, date_debut: date = DATE_DEBUT_INCLUSIVE) -> pd.DataFrame:
    """Pagination par filtre d'étoiles (1-5) pour maximiser la couverture."""
    lignes: list[dict] = []

    for stars in range(1, 6):
        if stars > 1:
            time.sleep(3 + random.uniform(0, 1))
        batch = _trustpilot_pages(f"stars={stars}", date_debut=date_debut)
        lignes.extend(batch)
        LOG.info("Trustpilot: %s étoile(s): %s avis", stars, len(batch))

    out = _deduquer_et_trier(pd.DataFrame(lignes))
    LOG.info("Trustpilot: %s avis retenus (filtre par étoiles)", len(out))
    return out
