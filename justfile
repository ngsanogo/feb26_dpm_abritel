# Justfile — raccourcis DevX pour le projet Abritel
# Usage : just <commande>  (installer just : https://just.systems/man/en/)

# Affiche les commandes disponibles
default:
    @just --list

# Installe les dépendances + hooks pre-commit (crée .venv/ via uv)
setup:
    uv sync --extra dev
    uv run pre-commit install

# Lance le linting (ruff check + format)
lint:
    uv run ruff check .
    uv run ruff format --check .

# Corrige automatiquement le formatage et les imports
fix:
    uv run ruff check --fix .
    uv run ruff format .

# Lance les tests rapides (sans réseau, parallèle)
test *ARGS:
    uv run pytest -q -n auto {{ ARGS }}

# Lance les tests contract (réseau réel)
test-slow:
    uv run pytest -m slow -v --override-ini addopts=

# CI locale complète : lint + tests
ci: lint test

# CI locale dans Docker (identique à GitHub Actions)
ci-docker:
    ./scripts/ci_docker.sh

# Lance le pipeline de scraping → data/avis_enrichis.csv
pipeline:
    uv run python 1_pipeline.py

# Lance le pipeline avec Ollama activé
pipeline-ollama:
    ABRITEL_OLLAMA_TIMEOUT=300 uv run python 1_pipeline.py

# Vérifie la cohérence du build (lint + test + no orphans)
check: lint test
    @echo "--- Vérification fichiers orphelins ---"
    git ls-files --ignored --exclude-standard -c
    @echo "✓ Build complet OK"
