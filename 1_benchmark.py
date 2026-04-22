# =============================================================================
# 1_benchmark.py — Benchmark Abritel vs Airbnb vs Booking
# =============================================================================
# Exécute le même pipeline (scraping + catégorisation + gravité) pour chaque
# marque, puis fusionne les résultats dans un CSV unique pour comparaison
# dans Power BI / Jupyter.
#
# Usage : uv run python 1_benchmark.py
# =============================================================================

import logging
from pathlib import Path

import pandas as pd

from abritel.pipeline import run_pipeline
from abritel.scraping import DATE_DEBUT_INCLUSIVE, MARQUES


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    benchmark_dir = Path("data/benchmark")

    frames: list[pd.DataFrame] = []

    for key, marque in MARQUES.items():
        print(f"\n{'=' * 60}")
        print(f"  BENCHMARK — {marque.nom}")
        print(f"{'=' * 60}\n")

        chemin = benchmark_dir / key / "avis_enrichis.csv"
        df = run_pipeline(
            chemin_csv=chemin,
            date_debut=DATE_DEBUT_INCLUSIVE,
            marque=marque,
        )
        frames.append(df)

    # CSV combiné pour comparaison
    if frames:
        combined = pd.concat(frames, ignore_index=True)
        combined = combined.sort_values("date", ascending=False).reset_index(drop=True)
        benchmark_dir.mkdir(parents=True, exist_ok=True)
        combined.to_csv(
            benchmark_dir / "benchmark_complet.csv",
            index=False,
            encoding="utf-8-sig",
        )

        print(f"\n{'=' * 60}")
        print("  BENCHMARK TERMINE")
        for _key, marque in MARQUES.items():
            n = (combined["marque"] == marque.nom).sum()
            print(f"  {marque.nom:10s} : {n:5d} avis")
        print(f"  {'TOTAL':10s} : {len(combined):5d} avis")
        print(f"  -> {benchmark_dir / 'benchmark_complet.csv'}")
        print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
