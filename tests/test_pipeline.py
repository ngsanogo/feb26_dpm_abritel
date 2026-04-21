from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from abritel.categorisation import categoriser_avis_multi, evaluer_gravite
from abritel.pipeline import (
    _charger_existant,
    _detect_spikes,
    _enrichir_version,
    _fusionner,
    _keywords_hash,
    enrichir,
    exporter_csv,
    run_pipeline,
    valider_dataframe,
)
from abritel.scraping import avis_jour_paris, dans_fenetre

# --- dans_fenetre ---


def test_dans_fenetre_inside() -> None:
    assert dans_fenetre(date(2025, 6, 15), date(2025, 12, 31), date(2025, 1, 1)) is True


def test_dans_fenetre_on_start_boundary() -> None:
    assert dans_fenetre(date(2025, 1, 1), date(2025, 12, 31), date(2025, 1, 1)) is True


def test_dans_fenetre_on_end_boundary() -> None:
    assert dans_fenetre(date(2025, 12, 31), date(2025, 12, 31), date(2025, 1, 1)) is True


def test_dans_fenetre_before_start() -> None:
    assert dans_fenetre(date(2024, 12, 31), date(2025, 12, 31), date(2025, 1, 1)) is False


def test_dans_fenetre_after_end() -> None:
    assert dans_fenetre(date(2026, 1, 1), date(2025, 12, 31), date(2025, 1, 1)) is False


# --- avis_jour_paris ---


def test_avis_jour_paris_utc_midnight() -> None:
    dt = datetime(2025, 6, 15, 0, 0, 0, tzinfo=UTC)
    # UTC midnight = 2h Paris (CEST) → même jour
    assert avis_jour_paris(dt) == date(2025, 6, 15)


def test_avis_jour_paris_utc_late_night() -> None:
    dt = datetime(2025, 6, 14, 23, 30, 0, tzinfo=UTC)
    # 23:30 UTC = 01:30 Paris (CEST) → jour suivant
    assert avis_jour_paris(dt) == date(2025, 6, 15)


# --- categoriser_avis_multi ---


def test_categoriser_multi_returns_multiple() -> None:
    cats = categoriser_avis_multi("App en anglais, bug de connexion permanent")
    assert "Localisation / Langue" in cats
    assert "Bug Technique" in cats


def test_categoriser_multi_empty_text() -> None:
    assert categoriser_avis_multi("") == []


def test_categoriser_multi_no_match() -> None:
    assert categoriser_avis_multi("super top génial") == []


# --- evaluer_gravite avec catégorie ---


def test_evaluer_gravite_bug_note_2_haute() -> None:
    assert evaluer_gravite("problème quelconque", 2, "Bug Technique") == "Haute"


def test_evaluer_gravite_financier_note_2_haute() -> None:
    assert evaluer_gravite("souci quelconque", 2, "Financier") == "Haute"


def test_evaluer_gravite_autre_note_2_moyenne() -> None:
    assert evaluer_gravite("souci quelconque", 2, "Autre") == "Moyenne"


def test_evaluer_gravite_negation_pas_arnaque() -> None:
    assert evaluer_gravite("ce n'est pas une arnaque", 4) == "Basse"


# --- enrichir ---


def test_enrichir_basic() -> None:
    df = pd.DataFrame(
        {
            "date": [datetime(2025, 6, 1, tzinfo=UTC)],
            "note": [1],
            "texte": ["C'est une arnaque totale"],
            "source": ["Trustpilot"],
        }
    )
    result = enrichir(df)
    assert "Catégorie" in result.columns
    assert "Gravité" in result.columns
    assert "Catégorie_secondaire" in result.columns
    assert "Autre_type" in result.columns
    assert "Catégorie_mots_cles" in result.columns
    assert result.iloc[0]["Catégorie"] == "Financier"
    assert result.iloc[0]["Catégorie_mots_cles"] == "Financier"
    assert result.iloc[0]["Gravité"] == "Haute"
    assert result.iloc[0]["Gravité_texte"] == "Haute"  # "arnaque" → Haute en texte seul aussi
    assert result.iloc[0]["Autre_type"] == ""  # non-Autre → vide


def test_enrichir_empty_df() -> None:
    df = pd.DataFrame(columns=["date", "note", "texte", "source"])
    result = enrichir(df)
    assert len(result) == 0
    assert "Catégorie" in result.columns


def test_enrichir_invalid_note() -> None:
    df = pd.DataFrame(
        {
            "date": [datetime(2025, 6, 1, tzinfo=UTC)],
            "note": ["abc"],
            "texte": ["Commentaire normal"],
            "source": ["Google Play"],
        }
    )
    result = enrichir(df)
    assert len(result) == 1
    assert pd.isna(result.iloc[0]["note"])


# --- _charger_existant ---


def test_charger_existant_file_missing(tmp_path: Path) -> None:
    assert _charger_existant(tmp_path / "absent.csv") is None


def test_charger_existant_valid_csv(tmp_path: Path) -> None:
    csv = tmp_path / "avis.csv"
    df = pd.DataFrame(
        {
            "date": ["2025-06-01T10:00:00+00:00", "2025-06-02T12:00:00+00:00"],
            "note": [3, 5],
            "texte": ["ok", "super"],
            "source": ["Google Play", "App Store"],
        }
    )
    df.to_csv(csv, index=False, encoding="utf-8-sig")
    result = _charger_existant(csv)
    assert result is not None
    assert len(result) == 2
    assert result["date"].dt.tz is not None  # doit être tz-aware UTC


def test_charger_existant_corrupt_csv(tmp_path: Path) -> None:
    csv = tmp_path / "bad.csv"
    csv.write_text("not,a,valid\ncsv,file,!!!")
    # Should not crash, returns a DataFrame (or None if parsing fails)
    result = _charger_existant(csv)
    # The file is technically parseable CSV but with wrong columns;
    # _charger_existant will try pd.to_datetime on missing "date" col → warning → None
    assert result is None


# --- _fusionner ---


def test_fusionner_deduplication() -> None:
    ancien = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-06-01T10:00:00+00:00"], utc=True),
            "note": [3],
            "texte": ["duplicata"],
            "source": ["Google Play"],
            "Catégorie": ["Autre"],
            "Gravité": ["Basse"],
            "Catégorie_secondaire": [""],
        }
    )
    nouveau = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2025-06-01T10:00:00+00:00", "2025-06-03T08:00:00+00:00"], utc=True
            ),
            "note": [3, 1],
            "texte": ["duplicata", "nouveau avis"],
            "source": ["Google Play", "Trustpilot"],
        }
    )
    result = _fusionner(ancien, nouveau)
    assert len(result) == 2  # duplicata dédupliqué
    assert "Catégorie" not in result.columns  # colonnes enrichies retirées


def test_fusionner_preserves_ollama_cache() -> None:
    """_fusionner conserve Catégorie_ollama de l'ancien CSV pour le cache incrémental."""
    ancien = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-06-01T10:00:00+00:00"], utc=True),
            "note": [1],
            "texte": ["avis ancien"],
            "source": ["Google Play"],
            "Catégorie": ["Autre"],
            "Catégorie_ollama": ["Financier"],  # résultat Ollama du run précédent
            "Gravité": ["Haute"],
        }
    )
    nouveau = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-06-05T08:00:00+00:00"], utc=True),
            "note": [5],
            "texte": ["avis nouveau"],
            "source": ["App Store"],
        }
    )
    result = _fusionner(ancien, nouveau)
    assert len(result) == 2
    assert "Catégorie_ollama" in result.columns  # cache préservé
    # L'ancien avis garde son cache Ollama
    ancien_row = result[result["texte"] == "avis ancien"].iloc[0]
    assert ancien_row["Catégorie_ollama"] == "Financier"
    # Le nouvel avis n'a pas de cache
    import math

    nouveau_row = result[result["texte"] == "avis nouveau"].iloc[0]
    assert nouveau_row["Catégorie_ollama"] == "" or (
        isinstance(nouveau_row["Catégorie_ollama"], float)
        and math.isnan(nouveau_row["Catégorie_ollama"])
    )


def test_fusionner_sort_descending() -> None:
    ancien = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-06-01T10:00:00+00:00"], utc=True),
            "note": [3],
            "texte": ["ancien"],
            "source": ["Google Play"],
            "Catégorie": ["Autre"],
            "Gravité": ["Basse"],
            "Catégorie_secondaire": [""],
        }
    )
    nouveau = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-06-05T08:00:00+00:00"], utc=True),
            "note": [5],
            "texte": ["récent"],
            "source": ["App Store"],
        }
    )
    result = _fusionner(ancien, nouveau)
    assert result.iloc[0]["texte"] == "récent"  # le plus récent en premier


# --- valider_dataframe ---


def test_valider_dataframe_valid() -> None:
    df = pd.DataFrame(
        {
            "date": [datetime(2025, 6, 1, tzinfo=UTC)],
            "note": [3],
            "texte": ["Un avis normal"],
            "source": ["Google Play"],
            "longueur_texte": [3],
            "n_caracteres": [14],
            "Catégorie": ["Autre"],
            "Catégorie_secondaire": [""],
            "Catégorie_mots_cles": ["Autre"],
            "Gravité": ["Basse"],
            "Gravité_texte": ["Basse"],
            "Autre_type": ["neutre"],
            "type_avis": ["neutre"],
            "profil_auteur": ["Locataire"],
        }
    )
    assert valider_dataframe(df) == []


def test_valider_dataframe_note_hors_bornes() -> None:
    df = pd.DataFrame(
        {
            "date": [datetime(2025, 6, 1, tzinfo=UTC)],
            "note": [6],
            "texte": ["test"],
            "source": ["Google Play"],
            "longueur_texte": [1],
            "n_caracteres": [4],
            "Catégorie": ["Autre"],
            "Catégorie_secondaire": [""],
            "Catégorie_mots_cles": ["Autre"],
            "Gravité": ["Basse"],
            "Gravité_texte": ["Basse"],
            "Autre_type": ["neutre"],
        }
    )
    anomalies = valider_dataframe(df)
    assert any("hors [1, 5]" in a for a in anomalies)


def test_valider_dataframe_categorie_inconnue() -> None:
    df = pd.DataFrame(
        {
            "date": [datetime(2025, 6, 1, tzinfo=UTC)],
            "note": [3],
            "texte": ["test"],
            "source": ["Google Play"],
            "longueur_texte": [1],
            "n_caracteres": [4],
            "Catégorie": ["Inventée"],
            "Catégorie_secondaire": [""],
            "Catégorie_mots_cles": ["Inventée"],
            "Gravité": ["Basse"],
            "Gravité_texte": ["Basse"],
            "Autre_type": [""],
        }
    )
    anomalies = valider_dataframe(df)
    assert any("inconnues" in a for a in anomalies)


def test_valider_dataframe_empty() -> None:
    df = pd.DataFrame(
        columns=[
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
    )
    assert valider_dataframe(df) == []


# --- exporter_csv ---


def test_exporter_csv_bom_and_header(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "date": [datetime(2025, 6, 1, tzinfo=UTC)],
            "note": [3],
            "texte": ["Un avis"],
            "source": ["Google Play"],
            "longueur_texte": [2],
            "Catégorie": ["Autre"],
            "Catégorie_secondaire": [""],
            "Gravité": ["Basse"],
        }
    )
    out = tmp_path / "export.csv"
    exporter_csv(df, out)
    raw = out.read_bytes()
    assert raw[:3] == b"\xef\xbb\xbf", "UTF-8 BOM manquant"
    header = raw.decode("utf-8-sig").splitlines()[0]
    assert header == "date,note,texte,source,longueur_texte,Catégorie,Catégorie_secondaire,Gravité"
    assert raw.count(b"\n") == 2  # header + 1 data row


def test_exporter_csv_strict_blocks_anomalies(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "date": [datetime(2025, 6, 1, tzinfo=UTC)],
            "note": [99],
            "texte": ["test"],
            "source": ["Google Play"],
            "longueur_texte": [1],
            "Catégorie": ["Autre"],
            "Catégorie_secondaire": [""],
            "Gravité": ["Basse"],
        }
    )
    out = tmp_path / "export.csv"
    try:
        exporter_csv(df, out, strict=True)
        raise AssertionError("ValueError attendu")
    except ValueError as e:
        assert "anomalie" in str(e).lower()
    assert not out.exists(), "Le fichier ne doit pas être créé en mode strict"


def test_exporter_csv_atomic_no_partial_on_error(tmp_path: Path) -> None:
    out = tmp_path / "export.csv"
    out.write_text("données existantes")
    try:
        # Un objet non-sérialisable provoquera une erreur dans to_csv
        exporter_csv("not a dataframe", out)  # type: ignore[arg-type]
    except Exception:
        pass
    # Le fichier original doit être intact
    assert out.read_text() == "données existantes"


# --- run_pipeline e2e ---


def _make_scraper_df(source: str, n: int = 3) -> pd.DataFrame:
    rows = []
    for i in range(n):
        rows.append(
            {
                "date": pd.Timestamp(f"2025-06-{10 + i}T10:00:00+00:00"),
                "note": (i % 5) + 1,
                "texte": f"Avis test {source} #{i}",
                "source": source,
            }
        )
    return pd.DataFrame(rows)


@patch("abritel.pipeline.telecharger_avis_trustpilot")
@patch("abritel.pipeline.telecharger_avis_app_store")
@patch("abritel.pipeline.telecharger_avis_google_play")
def test_run_pipeline_e2e(mock_gp, mock_as, mock_tp, tmp_path: Path) -> None:
    mock_gp.return_value = _make_scraper_df("Google Play", 5)
    mock_as.return_value = _make_scraper_df("App Store", 3)
    mock_tp.return_value = _make_scraper_df("Trustpilot", 4)

    csv_path = tmp_path / "data" / "avis.csv"
    result = run_pipeline(chemin_csv=csv_path, date_debut=date(2025, 1, 1))

    assert csv_path.exists()
    assert len(result) == 12
    assert set(result["source"].unique()) == {"Google Play", "App Store", "Trustpilot"}
    assert "Catégorie" in result.columns
    assert "Gravité" in result.columns
    assert "Autre_type" in result.columns
    assert "Catégorie_mots_cles" in result.columns
    assert "Catégorie_ollama" in result.columns
    assert valider_dataframe(result) == []


@patch("abritel.pipeline.telecharger_avis_trustpilot")
@patch("abritel.pipeline.telecharger_avis_app_store")
@patch("abritel.pipeline.telecharger_avis_google_play")
def test_run_pipeline_incremental_dedup(mock_gp, mock_as, mock_tp, tmp_path: Path) -> None:
    mock_gp.return_value = _make_scraper_df("Google Play", 2)
    mock_as.return_value = _make_scraper_df("App Store", 1)
    mock_tp.return_value = _make_scraper_df("Trustpilot", 1)

    csv_path = tmp_path / "avis.csv"
    # Premier run
    run_pipeline(chemin_csv=csv_path, date_debut=date(2025, 1, 1))
    df1 = pd.read_csv(csv_path, encoding="utf-8-sig")
    n_first = len(df1)

    # Deuxième run avec les mêmes données → pas de doublons
    run_pipeline(chemin_csv=csv_path, date_debut=date(2025, 1, 1))
    df2 = pd.read_csv(csv_path, encoding="utf-8-sig")
    assert len(df2) == n_first


@patch("abritel.pipeline.telecharger_avis_trustpilot")
@patch("abritel.pipeline.telecharger_avis_app_store")
@patch("abritel.pipeline.telecharger_avis_google_play")
def test_run_pipeline_circuit_breaker(mock_gp, mock_as, mock_tp, tmp_path: Path) -> None:
    mock_gp.return_value = _make_scraper_df("Google Play", 3)
    mock_as.return_value = _make_scraper_df("App Store", 2)
    mock_tp.return_value = _make_scraper_df("Trustpilot", 2)

    csv_path = tmp_path / "avis.csv"
    run_pipeline(chemin_csv=csv_path, date_debut=date(2025, 1, 1))

    # Deuxième run : Google Play retourne 0 avis → circuit breaker
    mock_gp.return_value = pd.DataFrame(columns=["date", "note", "texte", "source"])
    mock_as.return_value = _make_scraper_df("App Store", 2)
    mock_tp.return_value = _make_scraper_df("Trustpilot", 2)

    with patch.dict("os.environ", {"CI": "true"}):
        try:
            run_pipeline(chemin_csv=csv_path, date_debut=date(2025, 1, 1))
            raise AssertionError("SystemExit attendu (circuit breaker)")
        except SystemExit as e:
            assert e.code == 1

    # Le CSV doit toujours contenir les anciennes données Google Play
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    assert (df["source"] == "Google Play").sum() > 0


# --- Autre_type dans enrichir ---


def test_enrichir_autre_type_positif_court() -> None:
    """Un avis Autre court avec note 5 → Autre_type = 'positif court'."""
    df = pd.DataFrame(
        {
            "date": [datetime(2025, 6, 1, tzinfo=UTC)],
            "note": [5],
            "texte": ["Super top"],  # 2 mots, note 5 → positif court
            "source": ["Google Play"],
        }
    )
    result = enrichir(df)
    assert result.iloc[0]["Catégorie"] == "Autre"
    assert result.iloc[0]["Autre_type"] == "positif court"


def test_enrichir_autre_type_negatif_long() -> None:
    """Un avis Autre long avec note 1 → Autre_type = 'négatif non catégorisé'."""
    texte_long = " ".join(["mot"] * 35)  # 35 mots, sans mots-clés
    df = pd.DataFrame(
        {
            "date": [datetime(2025, 6, 1, tzinfo=UTC)],
            "note": [1],
            "texte": [texte_long],
            "source": ["Trustpilot"],
        }
    )
    result = enrichir(df)
    assert result.iloc[0]["Catégorie"] == "Autre"
    assert result.iloc[0]["Autre_type"] == "négatif non catégorisé"


def test_enrichir_autre_type_vide_pour_non_autre() -> None:
    """Un avis catégorisé (non Autre) a Autre_type vide."""
    df = pd.DataFrame(
        {
            "date": [datetime(2025, 6, 1, tzinfo=UTC)],
            "note": [1],
            "texte": ["Remboursement refusé, arnaque totale"],
            "source": ["Trustpilot"],
        }
    )
    result = enrichir(df)
    assert result.iloc[0]["Catégorie"] == "Financier"
    assert result.iloc[0]["Autre_type"] == ""


# --- _detect_spikes ---


def _make_weekly_df(weeks: int, cat_normal: str = "Bug Technique") -> pd.DataFrame:
    """Génère un DataFrame avec `weeks` semaines d'avis équilibrés entre 2 catégories."""
    rows = []
    base = datetime(2025, 1, 6, tzinfo=UTC)  # mardi
    for w in range(weeks):
        for _ in range(10):
            rows.append(
                {
                    "date": base + pd.Timedelta(weeks=w),
                    "note": 3,
                    "texte": "avis neutre",
                    "source": "Google Play",
                    "Catégorie": cat_normal,
                }
            )
        for _ in range(5):
            rows.append(
                {
                    "date": base + pd.Timedelta(weeks=w),
                    "note": 4,
                    "texte": "ok",
                    "source": "App Store",
                    "Catégorie": "Autre",
                }
            )
    return pd.DataFrame(rows)


def test_detect_spikes_no_spike_stable_data() -> None:
    df = _make_weekly_df(6)
    assert _detect_spikes(df) == []


def test_detect_spikes_insufficient_history() -> None:
    df = _make_weekly_df(3)  # < 5 semaines
    assert _detect_spikes(df) == []


def test_detect_spikes_detects_spike() -> None:
    """Injecte un spike clair la dernière semaine sur une catégorie.

    Les semaines historiques ont une légère variance pour que stdev > 0.
    """
    rows = []
    base = datetime(2025, 1, 6, tzinfo=UTC)
    # 5 semaines avec variance : Bug entre 2 et 4 avis sur 15 → ~15-27%
    bug_counts_history = [2, 3, 4, 2, 3]
    for w, n_bug in enumerate(bug_counts_history):
        for _ in range(n_bug):
            rows.append({"date": base + pd.Timedelta(weeks=w), "Catégorie": "Bug Technique"})
        for _ in range(15 - n_bug):
            rows.append({"date": base + pd.Timedelta(weeks=w), "Catégorie": "Autre"})
    # Semaine 5 (courante) : spike Bug à 90% (vs ~20% habituel) — largement > 2σ + 5pts
    for _ in range(18):
        rows.append({"date": base + pd.Timedelta(weeks=5), "Catégorie": "Bug Technique"})
    for _ in range(2):
        rows.append({"date": base + pd.Timedelta(weeks=5), "Catégorie": "Autre"})

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    alertes = _detect_spikes(df)
    assert any("Bug Technique" in a for a in alertes)


def test_detect_spikes_empty_df() -> None:
    assert _detect_spikes(pd.DataFrame()) == []


# --- _keywords_hash ---


def test_keywords_hash_returns_8_chars() -> None:
    h = _keywords_hash()
    assert isinstance(h, str)
    assert len(h) == 8


def test_keywords_hash_stable() -> None:
    assert _keywords_hash() == _keywords_hash()


# --- _enrichir_version ---


def test_enrichir_version_adds_column(tmp_path: Path) -> None:
    """Ajoute version_release en fonction de la date de l'avis (avec délai de grâce)."""
    releases = tmp_path / "releases.csv"
    releases.write_text(
        "date,version,plateforme,description\n"
        "2025-01-01,25.01,iOS,init\n"
        "2025-06-01,25.06,iOS,update\n"
    )
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2025-03-15T10:00:00+00:00", "2025-07-01T10:00:00+00:00"], utc=True
            ),
            "note": [3, 5],
            "texte": ["ok", "super"],
            "source": ["Google Play", "App Store"],
        }
    )
    result = _enrichir_version(df, releases)
    assert "version_release" in result.columns
    assert result.iloc[0]["version_release"] == "25.01"  # avant 25.06
    assert result.iloc[1]["version_release"] == "25.06"  # après 25.06 + grâce


def test_enrichir_version_grace_period(tmp_path: Path) -> None:
    """Un avis publié 1 jour après une release est attribué à la version précédente."""
    releases = tmp_path / "releases.csv"
    releases.write_text(
        "date,version,plateforme,description\n"
        "2025-01-01,25.01,iOS,init\n"
        "2025-06-01,25.06,iOS,update\n"
    )
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2025-06-02T10:00:00+00:00"],
                utc=True,  # 1 jour après release 25.06
            ),
            "note": [3],
            "texte": ["ok"],
            "source": ["Google Play"],
        }
    )
    # Avec grâce de 2 jours : 2025-06-02 < 2025-06-01 + 2j → version précédente
    result = _enrichir_version(df, releases, grace_days=2)
    assert result.iloc[0]["version_release"] == "25.01"

    # Sans grâce : 2025-06-02 > 2025-06-01 → version 25.06
    result_no_grace = _enrichir_version(df.copy(), releases, grace_days=0)
    assert result_no_grace.iloc[0]["version_release"] == "25.06"


def test_enrichir_version_no_file(tmp_path: Path) -> None:
    """Sans fichier releases.csv, pas de colonne ajoutée."""
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-03-15T10:00:00+00:00"], utc=True),
            "note": [3],
            "texte": ["ok"],
            "source": ["Google Play"],
        }
    )
    result = _enrichir_version(df, tmp_path / "releases.csv")
    assert "version_release" not in result.columns


@patch("abritel.pipeline.telecharger_avis_trustpilot")
@patch("abritel.pipeline.telecharger_avis_app_store")
@patch("abritel.pipeline.telecharger_avis_google_play")
def test_run_pipeline_circuit_breaker_soft_ci(
    mock_gp, mock_as, mock_tp, tmp_path: Path, capsys
) -> None:
    """ABRITEL_SOFT_CIRCUIT_BREAKER=1 : pas de SystemExit en CI, annotation GitHub sur stdout."""
    mock_gp.return_value = _make_scraper_df("Google Play", 2)
    mock_as.return_value = _make_scraper_df("App Store", 1)
    mock_tp.return_value = _make_scraper_df("Trustpilot", 1)

    csv_path = tmp_path / "avis_soft.csv"
    run_pipeline(chemin_csv=csv_path, date_debut=date(2025, 1, 1))

    mock_gp.return_value = pd.DataFrame(columns=["date", "note", "texte", "source"])
    mock_as.return_value = _make_scraper_df("App Store", 1)
    mock_tp.return_value = _make_scraper_df("Trustpilot", 1)

    with patch.dict(
        "os.environ",
        {"CI": "true", "ABRITEL_SOFT_CIRCUIT_BREAKER": "1"},
    ):
        run_pipeline(chemin_csv=csv_path, date_debut=date(2025, 1, 1))

    assert "::warning::" in capsys.readouterr().out
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    assert (df["source"] == "Google Play").sum() > 0
