"""Orchestration du pipeline : collecte → enrichissement → export."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import statistics
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from abritel.categorisation import (
    _CATEGORIES_KEYWORDS,
    _NEGATION_CAT_RE,
    CATEGORIES_ABRITEL,
    categoriser_avis,
    categoriser_avis_multi,
    evaluer_gravite,
    evaluer_gravite_texte,
    profil_auteur,
    sous_cat_autre,
    type_avis,
)
from abritel.ollama_categorisation import appliquer_categorisation_ollama, ollama_actif
from abritel.scraping import (
    DATE_DEBUT_INCLUSIVE,
    TZ_FR,
    avis_jour_paris,
    dans_fenetre,
    date_fin_inclusive,
    parse_datetime_utc,
    telecharger_avis_app_store,
    telecharger_avis_google_play,
    telecharger_avis_trustpilot,
)

LOG = logging.getLogger(__name__)

# Marge calendaire (Europe/Paris) en mode incrémental : au-delà de la dernière date
# CSV, on rescrape N jours en arrière (avis publiés en retard, décalage fuseau).
# 7 jours limite les faux positifs du circuit breaker (0 avis sur une fenêtre trop courte).
MARGE_JOURS_INCREMENTAL = 7
_ENV_SOFT_CIRCUIT_BREAKER = "ABRITEL_SOFT_CIRCUIT_BREAKER"

# Ré-export pour compatibilité des imports existants (1_pipeline.py, tests)
__all__ = [
    "CATEGORIES_ABRITEL",
    "DATE_DEBUT_INCLUSIVE",
    "MARGE_JOURS_INCREMENTAL",
    "TZ_FR",
    "appliquer_categorisation_ollama",
    "avis_jour_paris",
    "categoriser_avis",
    "categoriser_avis_multi",
    "dans_fenetre",
    "date_fin_inclusive",
    "enrichir",
    "evaluer_gravite",
    "evaluer_gravite_texte",
    "exporter_csv",
    "ollama_actif",
    "parse_datetime_utc",
    "profil_auteur",
    "run_pipeline",
    "sous_cat_autre",
    "type_avis",
    "telecharger_avis_app_store",
    "telecharger_avis_google_play",
    "telecharger_avis_trustpilot",
    "valider_dataframe",
]


def _keywords_hash() -> str:
    """Hash MD5 court des mots-clés de catégorisation (8 chars).

    Détecte les changements de keywords entre deux runs successifs et permet de
    tracer les re-catégorisations dans pipeline_meta.json.
    """
    raw = str(_CATEGORIES_KEYWORDS).encode() + _NEGATION_CAT_RE.pattern.encode()
    return hashlib.md5(raw).hexdigest()[:8]  # noqa: S324 — non cryptographique, traçabilité seule


def enrichir(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute Catégorie, Catégorie_secondaire, Gravité, longueur_texte et Autre_type."""
    df = df.copy()
    notes = pd.to_numeric(df["note"], errors="coerce")
    n_invalid = int(notes.isna().sum())
    if n_invalid:
        LOG.warning("enrichir: %s note(s) invalide(s) mises à NA", n_invalid)
    df["note"] = notes.astype("Int64")
    df["longueur_texte"] = df["texte"].apply(
        lambda t: len(str(t).split()) if isinstance(t, str) else 0
    )
    df["n_caracteres"] = df["texte"].apply(lambda t: len(str(t)) if isinstance(t, str) else 0)
    multi = df["texte"].map(categoriser_avis_multi)
    # Catégorie principale = premier élément du classement score-based (ou "Autre")
    df["Catégorie"] = multi.map(lambda cats: cats[0] if cats else "Autre")
    # Garder le résultat mots-clés pour traçabilité (avant éventuel override Ollama)
    df["Catégorie_mots_cles"] = df["Catégorie"]
    # Catégorie secondaire = deuxième élément si existant, en excluant la principale
    df["Catégorie_secondaire"] = multi.map(lambda cats: cats[1] if len(cats) > 1 else "")
    df["Gravité"] = [
        evaluer_gravite(tx, int(n) if pd.notna(n) else 0, cat)
        for tx, n, cat in zip(df["texte"], df["note"], df["Catégorie"], strict=True)
    ]
    # Gravité indépendante : basée uniquement sur le texte (mots de colère, urgence légale)
    # pour casser la tautologie note→gravité du champ Gravité principal
    df["Gravité_texte"] = df["texte"].map(evaluer_gravite_texte)
    # Sous-catégorie pour les avis « Autre » : distingue positifs courts / thématiques / négatifs / neutres
    df["Autre_type"] = [
        sous_cat_autre(int(n) if pd.notna(n) else 0, lng, tx) if cat == "Autre" else ""
        for n, lng, tx, cat in zip(
            df["note"], df["longueur_texte"], df["texte"], df["Catégorie"], strict=True
        )
    ]
    # Type d'avis : positif / négatif / neutre (basé sur la note)
    df["type_avis"] = [type_avis(int(n) if pd.notna(n) else 0) for n in df["note"]]
    # Profil auteur : Locataire / Propriétaire (détection par mots-clés)
    df["profil_auteur"] = df["texte"].map(profil_auteur)
    return df


# Délai de grâce (jours) pour l'attribution version : un avis publié dans ce délai
# après une release est attribué à la version précédente (l'utilisateur n'a probablement
# pas encore mis à jour l'app ou réagit à l'ancienne version).
_VERSION_GRACE_PERIOD_DAYS = 2


def _enrichir_version(
    df: pd.DataFrame, chemin_releases: Path, *, grace_days: int = _VERSION_GRACE_PERIOD_DAYS
) -> pd.DataFrame:
    """Ajoute ``version_release`` : version de l'app active au moment de l'avis.

    Un délai de grâce de ``grace_days`` jours est appliqué : un avis publié dans
    les N jours suivant une release est attribué à la version précédente.
    """
    if not chemin_releases.is_file():
        return df
    try:
        rel = pd.read_csv(chemin_releases)
        rel["date"] = pd.to_datetime(rel["date"]).dt.tz_localize("UTC")
        rel = rel.sort_values("date").reset_index(drop=True)
        # Décaler les dates de release par le délai de grâce
        grace = pd.Timedelta(days=grace_days)
        dates_shifted = rel["date"] + grace
        versions_list = rel["version"].tolist()
        n_rel = len(rel)
        result: list[str] = []
        for dt in df["date"]:
            idx = int(dates_shifted.searchsorted(dt, side="right")) - 1
            result.append(str(versions_list[idx]) if 0 <= idx < n_rel else "")
        df["version_release"] = result
    except Exception as e:
        LOG.warning("Enrichissement version impossible : %s", e)
    return df


_COLONNES_ATTENDUES = [
    "date",
    "note",
    "texte",
    "source",
    "longueur_texte",
    "n_caracteres",
    "Catégorie",
    "Catégorie_secondaire",
    "Catégorie_mots_cles",
    "Gravité",
    "Gravité_texte",
    "Autre_type",
    "type_avis",
    "profil_auteur",
]
_CATEGORIES_VALIDES = frozenset(CATEGORIES_ABRITEL)
_GRAVITES_VALIDES = {"Haute", "Moyenne", "Basse"}
_SOURCES_VALIDES = {"Google Play", "App Store", "Trustpilot"}


def valider_dataframe(df: pd.DataFrame) -> list[str]:
    """Vérifie la cohérence du DataFrame enrichi. Retourne une liste d'anomalies."""
    anomalies: list[str] = []

    # Colonnes
    manquantes = set(_COLONNES_ATTENDUES) - set(df.columns)
    if manquantes:
        anomalies.append(f"Colonnes manquantes : {manquantes}")

    if df.empty:
        return anomalies

    # Notes hors [1, 5]
    notes = pd.to_numeric(df["note"], errors="coerce")
    notes_valides = notes.dropna()
    hors_bornes = ((notes_valides < 1) | (notes_valides > 5)).sum()
    if hors_bornes:
        anomalies.append(f"{hors_bornes} note(s) hors [1, 5]")

    # Catégories inconnues
    if "Catégorie" in df.columns:
        inconnues = set(df["Catégorie"].dropna().unique()) - _CATEGORIES_VALIDES
        if inconnues:
            anomalies.append(f"Catégories inconnues : {inconnues}")

    # Gravités inconnues
    if "Gravité" in df.columns:
        grav_inconnues = set(df["Gravité"].dropna().unique()) - _GRAVITES_VALIDES
        if grav_inconnues:
            anomalies.append(f"Gravités inconnues : {grav_inconnues}")

    # Sources inconnues
    if "source" in df.columns:
        src_inconnues = set(df["source"].dropna().unique()) - _SOURCES_VALIDES
        if src_inconnues:
            anomalies.append(f"Sources inconnues : {src_inconnues}")

    # Textes vides
    if "texte" in df.columns:
        vides = df["texte"].isna().sum() + (df["texte"].astype(str).str.strip() == "").sum()
        if vides:
            anomalies.append(f"{vides} texte(s) vide(s)")

    return anomalies


def exporter_csv(df: pd.DataFrame, chemin: Path, *, strict: bool = False) -> None:
    anomalies = valider_dataframe(df)
    for a in anomalies:
        LOG.warning("   ⚠ Validation : %s", a)
    if strict and anomalies:
        raise ValueError(f"Export bloqué — {len(anomalies)} anomalie(s) : {anomalies}")
    chemin.parent.mkdir(parents=True, exist_ok=True)
    # Écriture atomique : temp file + os.replace() pour éviter la corruption
    # si le process est tué mid-write.
    fd, tmp_path = tempfile.mkstemp(dir=chemin.parent, suffix=".tmp")
    os.close(fd)
    try:
        df.to_csv(tmp_path, index=False, encoding="utf-8-sig")
        os.replace(tmp_path, chemin)
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise
    LOG.info("OK — %s avis enregistrés dans: %s", len(df), chemin.resolve())


def _charger_existant(chemin_csv: Path) -> pd.DataFrame | None:
    """Charge le CSV existant s'il existe, sinon None."""
    if not chemin_csv.is_file():
        return None
    try:
        df = pd.read_csv(chemin_csv, encoding="utf-8-sig")
        df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
        LOG.info("   CSV existant chargé : %d avis", len(df))
        return df
    except Exception as e:
        LOG.error("   CSV existant corrompu ou illisible : %s", e)
        bak = chemin_csv.with_suffix(".csv.bak")
        shutil.copy2(chemin_csv, bak)
        LOG.error("   Sauvegarde de secours créée : %s", bak)
        return None


def _fusionner(ancien: pd.DataFrame, nouveau: pd.DataFrame) -> pd.DataFrame:
    """Fusionne ancien + nouveau, déduplique, trie par date décroissante.

    Préserve ``Catégorie_ollama`` des anciens avis pour le cache incrémental :
    les avis déjà traités par Ollama ne repasseront pas par le LLM au prochain run.
    """
    cols_brutes = ["date", "note", "texte", "source"]
    # Préserver le cache Ollama pour le mode incrémental
    cols_cache = [c for c in ["Catégorie_ollama"] if c in ancien.columns]
    ancien_brut = ancien[cols_brutes + cols_cache].copy()
    combine = pd.concat([ancien_brut, nouveau[cols_brutes]], ignore_index=True)
    combine["date"] = pd.to_datetime(combine["date"], utc=True)
    combine = combine.drop_duplicates(
        subset=["source", "date", "note", "texte"],
        keep="first",  # "first" → priorité à ancien_brut (avec cache Ollama)
    )
    return combine.sort_values("date", ascending=False).reset_index(drop=True)


def _detect_spikes(df: pd.DataFrame) -> list[str]:
    """Détecte les catégories en spike cette semaine vs la moyenne des 4 semaines précédentes.

    Requiert au moins 5 semaines de données et ≥ 5 avis la semaine courante.
    Retourne une liste de messages d'alerte (vide si pas de spike ou pas assez d'historique).
    """
    if df.empty or "date" not in df.columns or "Catégorie" not in df.columns:
        return []

    df2 = df[["date", "Catégorie"]].copy()
    df2["_date"] = pd.to_datetime(df2["date"], utc=True, errors="coerce")
    # Supprimer l'info de timezone avant to_period (pandas ne supporte pas Period tz-aware)
    df2["_semaine"] = df2["_date"].dt.tz_localize(None).dt.to_period("W")

    semaines = sorted(df2["_semaine"].dropna().unique())
    if len(semaines) < 5:
        return []  # Pas assez d'historique pour une comparaison fiable

    sem_courante = semaines[-1]
    sems_precedentes = semaines[-5:-1]

    df_c = df2[df2["_semaine"] == sem_courante]
    if len(df_c) < 5:  # Trop peu d'avis cette semaine pour être significatif
        return []

    alertes: list[str] = []
    for cat in df2["Catégorie"].unique():
        pct_c = (df_c["Catégorie"] == cat).mean() * 100

        pcts_prev: list[float] = []
        for s in sems_precedentes:
            df_s = df2[df2["_semaine"] == s]
            if len(df_s) >= 3:  # Ignorer les semaines trop peu peuplées
                pcts_prev.append((df_s["Catégorie"] == cat).mean() * 100)

        if len(pcts_prev) < 3:
            continue  # Pas assez de données historiques pour cette catégorie

        moyenne = statistics.mean(pcts_prev)
        try:
            ecart_type = statistics.stdev(pcts_prev)
        except statistics.StatisticsError:
            continue

        # Double condition : > 2σ ET > 5 points de pourcentage au-dessus de la moyenne
        if ecart_type > 0 and pct_c > moyenne + 2 * ecart_type and pct_c > moyenne + 5:
            alertes.append(
                f"SPIKE {cat} : {pct_c:.1f}% cette semaine "
                f"vs {moyenne:.1f}% ± {ecart_type:.1f}% (4 sem. préc.)"
            )

    return alertes


def _log_rapport(df: pd.DataFrame, n_ancien: int = 0, spikes: list[str] | None = None) -> None:
    """Affiche un résumé structuré de la catégorisation."""
    n = len(df)
    if n == 0:
        return
    cat_counts = df["Catégorie"].value_counts()
    pct_autre = 100 * cat_counts.get("Autre", 0) / n
    pct_haute = 100 * (df["Gravité"] == "Haute").sum() / n

    LOG.info("\n   RAPPORT DE CATÉGORISATION")
    LOG.info("   %-30s %5s %6s", "Catégorie", "N", "%")
    LOG.info("   " + "-" * 43)
    for cat, count in cat_counts.items():
        LOG.info("   %-30s %5d %5.1f%%", cat, count, 100 * count / n)
    LOG.info("   " + "-" * 43)
    LOG.info("   Taux « Autre » : %.1f%%", pct_autre)
    LOG.info("   Taux gravité Haute : %.1f%%", pct_haute)
    LOG.info("   Note moyenne : %.2f / 5", df["note"].mean())

    multi_count = (df["Catégorie_secondaire"] != "").sum()
    if multi_count:
        LOG.info("   Avis multi-catégorie : %d (%.1f%%)", multi_count, 100 * multi_count / n)

    # Décomposition des avis « Autre »
    if "Autre_type" in df.columns:
        autres = df[df["Catégorie"] == "Autre"]
        if not autres.empty:
            LOG.info("\n   DÉCOMPOSITION « Autre » (%d avis)", len(autres))
            for typ, cnt in autres["Autre_type"].value_counts().items():
                LOG.info("   %-30s %5d %5.1f%%", typ, cnt, 100 * cnt / len(autres))

    if n_ancien > 0:
        n_nouveaux = n - n_ancien
        LOG.info("\n   DELTA vs run précédent")
        LOG.info("   Avis existants : %d", n_ancien)
        LOG.info("   Nouveaux avis : %d", n_nouveaux)

    # Spikes temporels
    if spikes:
        LOG.warning("\n   ⚠ ALERTES SPIKE TEMPOREL")
        for s in spikes:
            LOG.warning("   %s", s)

    # Alertes sources vides
    for source in ("Google Play", "App Store", "Trustpilot"):
        count_src = (df["source"] == source).sum()
        if count_src == 0:
            LOG.warning("   ⚠ ALERTE : 0 avis pour %s — vérifier le scraper", source)


def _ecrire_meta(
    df: pd.DataFrame,
    chemin_csv: Path,
    *,
    n_ancien: int,
    breaker: bool,
    spikes: list[str] | None = None,
) -> None:
    """Écrit pipeline_meta.json à côté du CSV pour le monitoring Power BI / dashboard."""
    from datetime import UTC, datetime

    n_total = len(df)
    src_counts = df["source"].value_counts().to_dict() if not df.empty else {}
    pct_autre = 0.0
    autre_breakdown: dict[str, int] = {}
    if not df.empty and "Catégorie" in df.columns:
        pct_autre = round(100 * (df["Catégorie"] == "Autre").sum() / n_total, 1)
        if "Autre_type" in df.columns:
            autres = df[df["Catégorie"] == "Autre"]
            autre_breakdown = {
                str(k): int(v) for k, v in autres["Autre_type"].value_counts().items()
            }

    # Hash des mots-clés : permet de détecter les changements de catégorisation entre runs
    kw_hash = _keywords_hash()

    # Avertir si le hash a changé par rapport au dernier run
    chemin_meta = chemin_csv.with_name("pipeline_meta.json")
    if chemin_meta.exists():
        try:
            prev = json.loads(chemin_meta.read_text(encoding="utf-8"))
            prev_hash = prev.get("keywords_hash")
            if prev_hash and prev_hash != kw_hash:
                LOG.warning(
                    "   ⚠ KEYWORDS MODIFIÉS : hash %s → %s "
                    "(tous les avis ont été re-catégorisés ce run)",
                    prev_hash,
                    kw_hash,
                )
        except Exception:
            pass

    meta = {
        "last_run": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_avis_total": n_total,
        "n_avis_nouveaux": n_total - n_ancien,
        "sources": {k: int(v) for k, v in src_counts.items()},
        "pct_autre": pct_autre,
        "autre_breakdown": autre_breakdown,
        "circuit_breaker_triggered": breaker,
        "spikes": spikes or [],
        "keywords_hash": kw_hash,
    }
    try:
        chemin_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        LOG.info("   Métadonnées : %s", chemin_meta.resolve())
    except Exception as e:
        LOG.warning("   Impossible d'écrire pipeline_meta.json : %s", e)


def _soft_circuit_breaker_ci() -> bool:
    """Si vrai avec CI, un circuit breaker ne fait pas échouer le processus (exit 0)."""
    v = (os.getenv(_ENV_SOFT_CIRCUIT_BREAKER) or "").strip().lower()
    return v in {"1", "true", "yes", "on"}


def run_pipeline(*, chemin_csv: Path, date_debut: date = DATE_DEBUT_INCLUSIVE) -> pd.DataFrame:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    LOG.info("=== Démarrage du pipeline Abritel (3 sources, France) ===")
    fin = date_fin_inclusive()

    # Détecter si les mots-clés ont changé depuis le dernier run → force Ollama complet
    chemin_meta = chemin_csv.with_name("pipeline_meta.json")
    kw_changed = False
    if chemin_meta.exists():
        try:
            prev_meta = json.loads(chemin_meta.read_text(encoding="utf-8"))
            prev_hash = prev_meta.get("keywords_hash")
            curr_hash = _keywords_hash()
            if prev_hash and prev_hash != curr_hash:
                kw_changed = True
                LOG.warning(
                    "   ⚠ KEYWORDS MODIFIÉS (hash %s → %s) — Ollama repassera sur tous les avis",
                    prev_hash,
                    curr_hash,
                )
        except Exception:
            pass

    # Mode incrémental : si le CSV existe, ne scraper que les avis récents
    existant = _charger_existant(chemin_csv)
    n_ancien = 0
    if existant is not None and not existant.empty:
        n_ancien = len(existant)
        date_max = existant["date"].max()
        # Marge calendaire pour les avis publiés en retard / fuseau.
        # .date() sur UTC donnerait la date UTC ; on convertit en Paris
        # pour rester cohérent avec le filtrage des scrapers.
        date_debut_incremental = date_max.tz_convert(TZ_FR).date() - timedelta(
            days=MARGE_JOURS_INCREMENTAL
        )
        if date_debut_incremental > date_debut:
            date_debut = date_debut_incremental
            LOG.info(
                "   Mode incrémental : scraping depuis %s (%sj de marge)",
                date_debut,
                MARGE_JOURS_INCREMENTAL,
            )

    LOG.info("Période cible : %s → %s (Europe/Paris)", date_debut.isoformat(), fin.isoformat())
    LOG.info("")

    LOG.info("ÉTAPE 1 — Collecte des avis (3 sources en parallèle)")

    scrapers = {
        "Google Play": telecharger_avis_google_play,
        "App Store": telecharger_avis_app_store,
        "Trustpilot": telecharger_avis_trustpilot,
    }
    results: dict[str, pd.DataFrame] = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(fn, date_debut=date_debut): name for name, fn in scrapers.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            results[name] = future.result()
            LOG.info("  ✓ %s : %s avis", name, len(results[name]))

    df_gp = results["Google Play"]
    df_as = results["App Store"]
    df_tp = results["Trustpilot"]

    brut = pd.concat([df_gp, df_as, df_tp], ignore_index=True)
    brut["date"] = pd.to_datetime(brut["date"], utc=True)
    brut = brut.sort_values("date", ascending=False).reset_index(drop=True)
    LOG.info(
        "\n   Scraping : %s avis (%s GP + %s AS + %s TP)",
        len(brut),
        len(df_gp),
        len(df_as),
        len(df_tp),
    )

    # Circuit breaker : si une source retourne 0 avis EN MODE INCRÉMENTAL alors qu'elle
    # en avait DANS LA MÊME FENÊTRE TEMPORELLE, c'est suspect (API cassée / HTML changé).
    # On compare uniquement sur la fenêtre scrapée (date_debut → aujourd'hui), pas sur
    # tout le CSV historique — une source à faible volume (App Store FR) peut légitimement
    # ne publier aucun nouvel avis sur 7 jours sans que l'API soit cassée.
    sources_circuit_breaker: list[str] = []
    if existant is not None and not existant.empty:
        date_debut_ts = pd.Timestamp(date_debut).tz_localize("UTC")
        for nom, df_src in [("Google Play", df_gp), ("App Store", df_as), ("Trustpilot", df_tp)]:
            avait_dans_fenetre = (
                (existant["source"] == nom) & (existant["date"] >= date_debut_ts)
            ).any()
            a_maintenant = len(df_src) > 0
            if avait_dans_fenetre and not a_maintenant:
                sources_circuit_breaker.append(nom)
                LOG.warning(
                    "   ⚠ CIRCUIT BREAKER : %s a retourné 0 avis sur la fenêtre %s → %s "
                    "alors qu'elle en avait — API potentiellement cassée.",
                    nom,
                    date_debut,
                    fin,
                )
        if sources_circuit_breaker:
            LOG.warning(
                "   Diagnostic circuit breaker — source(s) à 0 avis ce run : %s",
                ", ".join(sources_circuit_breaker),
            )
    breaker_triggered = bool(sources_circuit_breaker)

    # Fusion avec les données existantes
    if existant is not None and not existant.empty:
        brut = _fusionner(existant, brut)
        LOG.info("   Après fusion + déduplique : %s avis", len(brut))
    else:
        if not brut.empty:
            LOG.info(
                "   Répartition par note :\n%s",
                brut["note"].value_counts().sort_index().to_string(),
            )
            LOG.info("   Répartition par source :\n%s", brut["source"].value_counts().to_string())

    LOG.info("\nÉTAPE 2 — Catégorisation et gravité (mots-clés)…")
    out = enrichir(brut)
    if ollama_actif():
        LOG.info("\nÉTAPE 2b — Validation Ollama (tous les avis, mode incrémental)…")

        def _checkpoint_ollama(df_partial: pd.DataFrame, done: int, total: int) -> None:
            LOG.info("   Ollama checkpoint %d/%d — sauvegarde CSV…", done, total)
            exporter_csv(df_partial, chemin_csv, strict=False)

        out = appliquer_categorisation_ollama(
            out, force_rerun=kw_changed, on_progress=_checkpoint_ollama
        )
    # Enrichissement version release (si fichier disponible)
    out = _enrichir_version(out, chemin_csv.parent / "releases.csv")

    spikes = _detect_spikes(out)
    _log_rapport(out, n_ancien=n_ancien, spikes=spikes)

    # Colonnes de traçabilité toujours présentes (même si Ollama n'a pas tourné)
    if "Catégorie_mots_cles" not in out.columns:
        out["Catégorie_mots_cles"] = out["Catégorie"]
    if "Catégorie_ollama" not in out.columns:
        out["Catégorie_ollama"] = ""

    # Ordre des colonnes pour Power BI : données brutes → catégorisation → gravité
    _colonnes_ordre = [
        "date",
        "note",
        "texte",
        "source",
        "longueur_texte",
        "n_caracteres",
        "Catégorie",
        "Catégorie_secondaire",
        "Catégorie_mots_cles",
        "Catégorie_ollama",
        "Gravité",
        "Gravité_texte",
        "Autre_type",
        "type_avis",
        "profil_auteur",
        "version_release",
    ]
    cols = [c for c in _colonnes_ordre if c in out.columns]
    extras = [c for c in out.columns if c not in cols]
    out = out[cols + extras]

    LOG.info("\nÉTAPE 3 — Export CSV…")
    exporter_csv(out, chemin_csv, strict=True)

    _ecrire_meta(out, chemin_csv, n_ancien=n_ancien, breaker=breaker_triggered, spikes=spikes)

    LOG.info("\n=== Pipeline terminé ===")
    if breaker_triggered:
        detail = ", ".join(sources_circuit_breaker)
        msg = (
            f"⚠ Circuit breaker ({detail}) : au moins une source a retourné 0 avis. "
            "Le CSV a été exporté avec les données existantes préservées."
        )
        ci = os.getenv("GITHUB_ACTIONS") == "true" or os.getenv("CI") == "true"
        if ci and _soft_circuit_breaker_ci():
            # Annotation visible dans l’onglet Actions sans faire échouer le job.
            safe = msg.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            print(f"::warning::{safe}", flush=True)
            LOG.error(
                "%s Mode %s=1 : exit 0 (commit / suite du workflow autorisés).",
                msg,
                _ENV_SOFT_CIRCUIT_BREAKER,
            )
            return out
        if ci:
            LOG.error("%s Exit code 1 pour alerter CI.", msg)
            sys.exit(1)
        LOG.warning("%s", msg)
    return out
