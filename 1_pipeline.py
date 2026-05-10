# =============================================================================
# 1_pipeline.py — « La machine à récolter » (MVP Abritel)
# =============================================================================
# Ce script collecte les avis utilisateurs depuis 3 sources :
#   1) Google Play Store (API non officielle via google-play-scraper)
#   2) Apple App Store (API RSS JSON officielle)
#   3) Trustpilot (extraction du JSON __NEXT_DATA__ embarqué dans la page)
#
# Chaque avis est ensuite étiqueté (catégorie + gravité) par mots-clés
# et le tout est exporté dans un fichier CSV unique pour Power BI / Jupyter.
# =============================================================================

from pathlib import Path

from abritel.pipeline import DATE_DEBUT_INCLUSIVE, run_pipeline


def main() -> None:
    run_pipeline(chemin_csv=Path("data") / "avis_enrichis.csv", date_debut=DATE_DEBUT_INCLUSIVE)


if __name__ == "__main__":
    main()
