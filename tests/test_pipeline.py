from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from abritel.pipeline import (
    _charger_existant,
    _fusionner,
    avis_jour_paris,
    categoriser_avis_multi,
    dans_fenetre,
    enrichir,
    evaluer_gravite,
    exporter_csv,
    run_pipeline,
    valider_dataframe,
)

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
    assert result.iloc[0]["Catégorie"] == "Financier"
    assert result.iloc[0]["Gravité"] == "Haute"


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
            "Catégorie": ["Autre"],
            "Catégorie_secondaire": [""],
            "Gravité": ["Basse"],
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
            "Catégorie": ["Autre"],
            "Catégorie_secondaire": [""],
            "Gravité": ["Basse"],
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
            "Catégorie": ["Inventée"],
            "Catégorie_secondaire": [""],
            "Gravité": ["Basse"],
        }
    )
    anomalies = valider_dataframe(df)
    assert any("inconnues" in a for a in anomalies)


def test_valider_dataframe_empty() -> None:
    df = pd.DataFrame(
        columns=["date", "note", "texte", "source", "Catégorie", "Catégorie_secondaire", "Gravité"]
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
    assert header == "date,note,texte,source,Catégorie,Catégorie_secondaire,Gravité"
    assert raw.count(b"\n") == 2  # header + 1 data row


def test_exporter_csv_strict_blocks_anomalies(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "date": [datetime(2025, 6, 1, tzinfo=UTC)],
            "note": [99],
            "texte": ["test"],
            "source": ["Google Play"],
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

    try:
        run_pipeline(chemin_csv=csv_path, date_debut=date(2025, 1, 1))
        raise AssertionError("SystemExit attendu (circuit breaker)")
    except SystemExit as e:
        assert e.code == 1

    # Le CSV doit toujours contenir les anciennes données Google Play
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    assert (df["source"] == "Google Play").sum() > 0
