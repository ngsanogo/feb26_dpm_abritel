from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from bs4 import BeautifulSoup
from google_play_scraper import Sort, reviews

TZ_FR = ZoneInfo("Europe/Paris")
DATE_DEBUT_INCLUSIVE = date(2025, 1, 1)

# Google Play
GP_APP_ID = "com.vacationrentals.homeaway"
GP_TAILLE_LOT = 200
GP_PAGES_MAX = 2000

# App Store
APPSTORE_APP_ID = "642441300"

# Trustpilot
TRUSTPILOT_URL = "https://fr.trustpilot.com/review/abritel.fr"
TRUSTPILOT_PAGES_PAR_FILTRE = 10  # limite imposée par Trustpilot sans login

LOG = logging.getLogger(__name__)

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


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


def get_json(url: str, *, timeout_s: int = 15, tentatives: int = 3) -> dict | None:
    """GET JSON avec retries simples (sans dépendance externe)."""
    last_err: Exception | None = None
    for i in range(tentatives):
        try:
            resp = requests.get(url, headers=HTTP_HEADERS, timeout=timeout_s)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            last_err = e
            time.sleep(0.8 * (i + 1))
    LOG.warning("HTTP JSON — échec après %s tentatives: %s", tentatives, last_err)
    return None


def get_text(url: str, *, timeout_s: int = 15, tentatives: int = 3) -> str | None:
    """GET HTML/text avec retries simples (sans dépendance externe)."""
    last_err: Exception | None = None
    for i in range(tentatives):
        try:
            resp = requests.get(url, headers=HTTP_HEADERS, timeout=timeout_s)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            last_err = e
            time.sleep(0.8 * (i + 1))
    LOG.warning("HTTP text — échec après %s tentatives: %s", tentatives, last_err)
    return None


def parse_datetime_utc(value: str) -> datetime | None:
    """Parse tolérant vers datetime aware UTC (None si invalide)."""
    if not value:
        return None
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.to_pydatetime()


def telecharger_avis_google_play(*, date_debut: date = DATE_DEBUT_INCLUSIVE) -> pd.DataFrame:
    """Pagination complète du plus récent au plus ancien, filtre sur la fenêtre."""
    fin = date_fin_inclusive()
    lignes: list[dict] = []
    token = None
    pages = 0

    while pages < GP_PAGES_MAX:
        lot: list[dict] = []
        for tentative in range(3):
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
            except Exception as e:
                if tentative == 2:
                    LOG.warning("Google Play — erreur après 3 tentatives: %s", e)
                time.sleep(0.8 * (tentative + 1))
        pages += 1
        if not lot:
            break

        for avis in lot:
            jour = avis_jour_paris(avis["at"])
            if not dans_fenetre(jour, fin, date_debut):
                continue
            texte = (avis.get("content") or "").strip() or "(sans commentaire)"
            lignes.append(
                {
                    "date": avis["at"],
                    "note": avis["score"],
                    "texte": texte,
                    "source": "Google Play",
                }
            )

        plus_ancien = avis_jour_paris(lot[-1]["at"])
        if plus_ancien < date_debut or token is None:
            break
        time.sleep(0.2)  # éviter de marteler l'API non-officielle

    out = pd.DataFrame(lignes)
    if not out.empty:
        out = out.sort_values("date", ascending=False).drop_duplicates(
            subset=["source", "date", "note", "texte"],
            keep="first",
        )
    LOG.info("Google Play: %s page(s), %s avis retenus", pages, len(out))
    return out


def telecharger_avis_app_store(*, date_debut: date = DATE_DEBUT_INCLUSIVE) -> pd.DataFrame:
    """
    L'API RSS Apple renvoie les 500 avis les plus récents (10 pages de 50).
    On pagine de la page 1 à 10 et on filtre sur la fenêtre temporelle.
    """
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
            break

        entries = payload.get("feed", {}).get("entry", [])
        if not entries:
            break

        for entry in entries:
            # La première entrée de la page 1 est la fiche app, pas un avis
            rating = entry.get("im:rating", {}).get("label")
            if rating is None:
                continue

            dt = parse_datetime_utc(entry.get("updated", {}).get("label", ""))
            if dt is None:
                continue

            jour = avis_jour_paris(dt)
            if not dans_fenetre(jour, fin, date_debut):
                continue

            titre = (entry.get("title", {}).get("label") or "").strip()
            contenu = (entry.get("content", {}).get("label") or "").strip()
            texte = f"{titre}. {contenu}".strip(". ") if titre else contenu
            if not texte:
                texte = "(sans commentaire)"

            lignes.append(
                {
                    "date": dt,
                    "note": int(rating),
                    "texte": texte,
                    "source": "App Store",
                }
            )

        pages_ok += 1

    out = pd.DataFrame(lignes)
    if not out.empty:
        out = out.sort_values("date", ascending=False).drop_duplicates(
            subset=["source", "date", "note", "texte"],
            keep="first",
        )
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

            titre = (avis.get("title") or "").strip()
            contenu = (avis.get("text") or "").strip()
            texte = f"{titre}. {contenu}".strip(". ") if titre else contenu
            if not texte:
                texte = "(sans commentaire)"

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
    """
    Trustpilot limite la pagination à ~10 pages sans authentification.
    Pour maximiser la couverture, on pagine par filtre d'étoiles (1 à 5)
    ce qui donne jusqu'à 5 x 10 pages = 1000 avis.
    """
    lignes: list[dict] = []

    for stars in range(1, 6):
        batch = _trustpilot_pages(f"stars={stars}", date_debut=date_debut)
        lignes.extend(batch)
        LOG.info("Trustpilot: %s étoile(s): %s avis", stars, len(batch))

    out = pd.DataFrame(lignes)
    if not out.empty:
        out = out.sort_values("date", ascending=False).drop_duplicates(
            subset=["source", "date", "note", "texte"],
            keep="first",
        )
    LOG.info("Trustpilot: %s avis retenus (filtre par étoiles)", len(out))
    return out


def categoriser_avis(texte: str) -> str:
    if not isinstance(texte, str) or not texte.strip():
        return "Autre"

    t = texte.lower()

    if any(
        mot in t
        for mot in (
            "français",
            "francais",
            "anglais",
            "allemand",
            "langue",
            "traduction",
            "traduire",
            "euros",
            "dollars",
            "devise",
            " € ",
            " $ ",
            "en anglais",
            "en allemand",
            "en français",
            "language",
            "currency",
            "nzd",
            "dollar",
        )
    ):
        return "Localisation / Langue"

    if any(
        mot in t
        for mot in (
            "annulé",
            "annulée",
            "annulation",
            "annuler",
            "réservation annul",
            "reservation annul",
            "réservation non",
            "reservation non",
            "indisponible",
            "dernière minute",
            "réservation refusée",
            "non garanti",
            "non confirmé",
        )
    ):
        return "Annulation / Réservation"

    if any(
        mot in t
        for mot in (
            "caution",
            "remboursement",
            "remboursé",
            "rembours",
            "paiement",
            "payer",
            "frais",
            "facture",
            "prix",
            "tarif",
            "argent",
            "carte bancaire",
            "prélèvement",
            "dépôt",
            "arnaque",
            "escroquerie",
            "voleur",
            "commission",
            "versement",
        )
    ):
        return "Financier"

    if any(
        mot in t
        for mot in (
            "bug",
            "beug",
            "plante",
            "planté",
            "crash",
            "erreur",
            "ne fonctionne",
            "ne marche",
            "lent",
            "lenteur",
            "connexion",
            "mot de passe",
            "login",
            "chargement",
            "mise à jour",
            "compatible",
            "figée",
            "bloqué",
            "bloquer",
            "dysfonctionne",
            "impossible d'ouvrir",
            "impossible de se connecter",
            "impossible de me connecter",
        )
    ):
        return "Bug Technique"

    if any(
        mot in t
        for mot in (
            "intuitif",
            "ergonomique",
            "compliqué",
            "complexe",
            "mal fait",
            "mal pensé",
            "pas pratique",
            "fastidieuse",
            "on ne comprend",
            "comprend rien",
            "pas clair",
            "difficile à utiliser",
            "labyrinthe",
            "convivial",
        )
    ):
        return "UX / Ergonomie"

    if any(
        mot in t
        for mot in (
            "service client",
            "sav",
            "support",
            "assistance",
            "conseiller",
            "réponse",
            "contact",
            "joindre",
            "injoignable",
            "aucune réponse",
            "attente",
            "mail",
            "email",
            "téléphone",
            "aucune aide",
            "aide",
        )
    ):
        return "Service Client"

    if any(
        mot in t
        for mot in (
            "logement",
            "appartement",
            "maison",
            "location",
            "annonce",
            "photo",
            "sale",
            "propreté",
            "hôte",
            "propriétaire",
            "description",
            "non conforme",
            "déception",
            "insalubre",
            "odeur",
        )
    ):
        return "Qualité du bien"

    return "Autre"


def evaluer_gravite(texte: str, note: int) -> str:
    if not isinstance(texte, str):
        texte = ""
    t = texte.lower()

    if any(
        mot in t
        for mot in (
            "arnaque",
            "honte",
            "plainte",
            "escroc",
            "tribunal",
            "justice",
            "avocat",
            "illégal",
            "scandale",
        )
    ):
        return "Haute"

    if note == 1:
        return "Haute"
    if note == 2:
        return "Moyenne"
    return "Basse"


def enrichir(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    notes = pd.to_numeric(df["note"], errors="coerce").fillna(0).astype(int)
    df["note"] = notes
    df["Catégorie"] = df["texte"].map(categoriser_avis)
    df["Gravité"] = [
        evaluer_gravite(tx, int(n)) for tx, n in zip(df["texte"], df["note"], strict=True)
    ]
    return df


def exporter_csv(df: pd.DataFrame, chemin: Path) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(chemin, index=False, encoding="utf-8-sig")
    LOG.info("OK — %s avis enregistrés dans: %s", len(df), chemin.resolve())


def run_pipeline(*, chemin_csv: Path, date_debut: date = DATE_DEBUT_INCLUSIVE) -> pd.DataFrame:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    LOG.info("=== Démarrage du pipeline Abritel (3 sources, France) ===")
    fin = date_fin_inclusive()
    LOG.info("Période cible : %s → %s (Europe/Paris)", date_debut.isoformat(), fin.isoformat())
    LOG.info("")

    LOG.info("ÉTAPE 1 — Collecte des avis")

    LOG.info("  [1/3] Google Play Store…")
    df_gp = telecharger_avis_google_play(date_debut=date_debut)

    LOG.info("  [2/3] Apple App Store…")
    df_as = telecharger_avis_app_store(date_debut=date_debut)

    LOG.info("  [3/3] Trustpilot…")
    df_tp = telecharger_avis_trustpilot(date_debut=date_debut)

    brut = pd.concat([df_gp, df_as, df_tp], ignore_index=True)
    brut["date"] = pd.to_datetime(brut["date"], utc=True)
    brut = brut.sort_values("date", ascending=False).reset_index(drop=True)
    LOG.info(
        "\n   TOTAL : %s avis (%s GP + %s AS + %s TP)",
        len(brut),
        len(df_gp),
        len(df_as),
        len(df_tp),
    )

    if not brut.empty:
        LOG.info(
            "   Répartition par note :\n%s", brut["note"].value_counts().sort_index().to_string()
        )
        LOG.info("   Répartition par source :\n%s", brut["source"].value_counts().to_string())

    LOG.info("\nÉTAPE 2 — Catégorisation et gravité (mots-clés)…")
    LOG.info("ÉTAPE 3 — Export CSV…")
    out = enrichir(brut)
    exporter_csv(out, chemin_csv)

    LOG.info("\n=== Pipeline terminé ===")
    return out
