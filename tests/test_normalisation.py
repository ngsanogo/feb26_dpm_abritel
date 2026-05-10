"""Tests pour la normalisation des accents et son impact sur la catégorisation."""

from abritel.categorisation import categoriser_avis, normaliser_texte


def test_normaliser_texte_accents() -> None:
    assert normaliser_texte("Compliqué") == "complique"
    assert normaliser_texte("français") == "francais"
    assert normaliser_texte("réservation") == "reservation"


def test_normaliser_texte_mixed_accents() -> None:
    """Accents mal encodés ou fantaisistes."""
    assert normaliser_texte("Compliqueè") == "compliquee"
    assert normaliser_texte("gîte") == "gite"


def test_categoriser_accents_francais() -> None:
    """Le mot 'français' avec ou sans accents doit matcher."""
    assert categoriser_avis("tout en français") == "Localisation / Langue"
    assert categoriser_avis("tout en francais") == "Localisation / Langue"


def test_categoriser_accent_gite() -> None:
    """'gîte' et 'gite' doivent matcher Qualité du bien."""
    assert categoriser_avis("le gîte était sale") == "Qualité du bien"
    assert categoriser_avis("le gite était sale") == "Qualité du bien"


def test_categoriser_accent_complique() -> None:
    """Différentes graphies de 'compliqué'."""
    assert categoriser_avis("trop Compliqueè") == "UX / Ergonomie"
    assert categoriser_avis("c'est compliqué") == "UX / Ergonomie"
    assert categoriser_avis("c'est complique") == "UX / Ergonomie"


def test_categoriser_probleme_technique() -> None:
    assert categoriser_avis("problème technique fréquent") == "Bug Technique"


def test_categoriser_pirater() -> None:
    assert categoriser_avis("je me suis fait pirater mon compte") == "Bug Technique"


def test_categoriser_impossible_utiliser() -> None:
    assert categoriser_avis("impossible à utiliser") == "Bug Technique"


def test_categoriser_obliger_telecharger() -> None:
    assert categoriser_avis("obliger de télécharger l'appli") == "UX / Ergonomie"
